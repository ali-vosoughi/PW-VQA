"""Safety regressions for environment patching; no ML packages are required."""

import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "apply_patches.py"
SPEC = importlib.util.spec_from_file_location("pwvqa_patch_installer", SCRIPT)
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)


class PatchInstallerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.prefix = self.root / "environment"
        self.site = self.prefix / "site-packages"
        self.patches = self.root / "patches"
        self.roots = {name: self.site / name for name in installer.PACKAGES}
        self.entries = []
        self.destinations = []
        for package, relative, payload in (
            ("bootstrap", "models/metrics/accuracy.py", b"patched accuracy\n"),
            ("block", "external/VQA/api.py", b"restored API\n"),
        ):
            self.roots[package].mkdir(parents=True)
            source = self.patches / package / relative
            source.parent.mkdir(parents=True)
            source.write_bytes(payload)
            self.entries.append({
                "package": package, "path": relative,
                "sha256": hashlib.sha256(payload).hexdigest(),
                "note": "Isolated replacement fixture.",
            })
            self.destinations.append(self.roots[package] / relative)
        self.original = b"original accuracy\n"
        self.entries[0]["upstream_sha256"] = hashlib.sha256(self.original).hexdigest()
        self.destinations[0].parent.mkdir(parents=True)
        self.destinations[0].write_bytes(self.original)
        self.write_manifest()

        for patch in (
            mock.patch.object(installer, "PATCH_ROOT", self.patches),
            mock.patch.object(installer.sys, "prefix", str(self.prefix)),
            mock.patch.object(installer.importlib.metadata, "distribution",
                              side_effect=self.distribution),
            mock.patch.object(installer.importlib.util, "find_spec",
                              side_effect=lambda name: SimpleNamespace(
                                  submodule_search_locations=[str(self.roots[name])])),
        ):
            patch.start()
            self.addCleanup(patch.stop)

    def distribution(self, name):
        versions = dict(installer.PACKAGES.values())
        return SimpleNamespace(version=versions[name],
                               locate_file=lambda path: self.site / path)

    def write_manifest(self):
        (self.patches / "manifest.json").write_text(
            json.dumps(self.entries), encoding="utf-8")

    def snapshot(self):
        return {
            str(path.relative_to(self.prefix)): (
                path.read_bytes() if path.is_file() else None,
                path.stat().st_mtime_ns,
            )
            for path in self.prefix.rglob("*")
        }

    def run_installer(self, *args):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return installer.main(list(args))

    def assert_refused_without_writes(self, *args):
        before = self.snapshot()
        self.assertEqual(self.run_installer(*args), 2)
        self.assertEqual(self.snapshot(), before)

    def test_apply_then_check_and_reapply_preserve_bytes_and_mtimes(self):
        self.assertEqual(self.run_installer(), 0)
        self.assertEqual(self.destinations[0].read_bytes(), b"patched accuracy\n")
        self.assertEqual(self.destinations[1].read_bytes(), b"restored API\n")
        before = self.snapshot()
        self.assertEqual(self.run_installer("--check"), 0)
        self.assertEqual(self.run_installer(), 0)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(list(self.site.rglob(".pwvqa-patch-*")))

    def test_check_missing_and_modified_files_is_read_only(self):
        before = self.snapshot()
        self.assertEqual(self.run_installer("--check"), 1)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.run_installer(), 0)
        self.destinations[1].write_bytes(b"local change\n")
        self.assert_refused_without_writes("--check")

    def test_local_change_in_later_destination_prevents_all_replacements(self):
        self.destinations[1].parent.mkdir(parents=True)
        self.destinations[1].write_bytes(b"local change\n")
        self.assert_refused_without_writes()
        self.assertEqual(self.destinations[0].read_bytes(), self.original)

    def test_missing_or_wrong_distribution_is_refused(self):
        with mock.patch.object(installer.importlib.metadata, "distribution",
                               side_effect=installer.importlib.metadata.PackageNotFoundError):
            self.assert_refused_without_writes()
        with mock.patch.object(installer.importlib.metadata, "distribution",
                               return_value=SimpleNamespace(version="9.0")):
            self.assert_refused_without_writes()

    def test_package_outside_environment_or_shadowing_distribution_is_refused(self):
        with mock.patch.object(installer.sys, "prefix", str(self.root / "other-env")):
            self.assert_refused_without_writes()
        shadow = self.prefix / "shadow" / "bootstrap"
        shadow.mkdir(parents=True)
        with mock.patch.object(installer.importlib.util, "find_spec",
                               return_value=SimpleNamespace(
                                   submodule_search_locations=[str(shadow)])):
            self.assert_refused_without_writes()

    def test_corrupt_or_missing_later_payload_prevents_all_replacements(self):
        source = self.patches / "block" / self.entries[1]["path"]
        source.write_bytes(b"corrupt payload\n")
        self.assert_refused_without_writes()
        source.unlink()
        self.assert_refused_without_writes()

    def test_unsafe_manifest_paths_are_refused(self):
        for path in ("../escape.py", "/absolute.py", "C:/escape.py", "dir\\escape.py"):
            with self.subTest(path=path):
                self.entries[1]["path"] = path
                self.write_manifest()
                self.assert_refused_without_writes()

    def test_non_directory_ancestor_is_refused_before_other_files_change(self):
        (self.roots["block"] / "external").write_bytes(b"not a directory")
        self.assert_refused_without_writes()

    def test_python39_metadata_normalized_names_are_supported(self):
        def normalized_only(name):
            if "." in name:
                raise installer.importlib.metadata.PackageNotFoundError(name)
            return self.distribution(name.replace("_", "."))
        with mock.patch.object(installer.importlib.metadata, "distribution",
                               side_effect=normalized_only):
            self.assertEqual(self.run_installer(), 0)
            self.assertEqual(self.run_installer("--check"), 0)

    def test_staging_failure_does_not_replace_existing_files(self):
        create_temporary = installer.tempfile.NamedTemporaryFile
        calls = []

        def fail_second_stage(*args, **kwargs):
            calls.append(None)
            if len(calls) == 2:
                raise OSError("simulated full disk")
            return create_temporary(*args, **kwargs)

        with mock.patch.object(installer.tempfile, "NamedTemporaryFile",
                               side_effect=fail_second_stage):
            self.assertEqual(self.run_installer(), 2)
        self.assertEqual(self.destinations[0].read_bytes(), self.original)
        self.assertFalse(self.destinations[1].exists())
        self.assertFalse(list(self.site.rglob(".pwvqa-patch-*")))


if __name__ == "__main__":
    unittest.main()

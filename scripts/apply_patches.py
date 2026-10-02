#!/usr/bin/env python3
"""Install PW-VQA's vendored fixes into this interpreter's environment.

Only the standard library is used: importing torch is not required to inspect or
repair its surrounding packages. Run with --check for a read-only byte check.
"""

import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
import tempfile


PATCH_ROOT = Path(__file__).resolve().parents[1] / "patches"
PACKAGES = {
    "bootstrap": ("bootstrap.pytorch", "0.0.13"),
    "block": ("block.bootstrap.pytorch", "0.1.6"),
}


class PatchError(Exception):
    """An unsafe or incomplete installation that requires user action."""


def _inside(path, root):
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _safe_path(root, relative):
    """Reject traversal, symlinks, and Windows paths in portable manifests."""
    parts = PurePosixPath(relative).parts
    if (not parts or PurePosixPath(relative).is_absolute()
            or any(part in (".", "..") or ":" in part or "\\" in part
                   for part in parts)):
        raise PatchError("Unsafe patch path: {!r}".format(relative))
    result = root.joinpath(*parts)
    cursor = result
    while cursor != root:
        if cursor.is_symlink():
            raise PatchError("Refusing symlink in patch path: {}".format(cursor))
        cursor = cursor.parent
    if not _inside(result.resolve(), root.resolve()):
        raise PatchError("Patch path escapes its package: {}".format(result))
    return result


def _package_roots():
    prefix = Path(sys.prefix).resolve()
    roots = {}
    for package, (distribution_name, version) in PACKAGES.items():
        try:
            try:
                distribution = importlib.metadata.distribution(distribution_name)
            except importlib.metadata.PackageNotFoundError:
                # Python 3.9's metadata finder does not normalize dots in names;
                # newer installers write canonical underscore dist-info names.
                normalized = re.sub(r"[-_.]+", "_", distribution_name)
                distribution = importlib.metadata.distribution(normalized)
        except importlib.metadata.PackageNotFoundError as exc:
            raise PatchError(
                "{}=={} is missing for {}. Run this environment's python -m "
                "pip install -r requirements.txt first."
                .format(distribution_name, version, sys.executable)
            ) from exc
        if distribution.version != version:
            raise PatchError(
                "{}=={} is installed; this patch requires =={}. Install the "
                "pinned requirements with this interpreter."
                .format(distribution_name, distribution.version, version)
            )
        # A top-level spec lookup does not execute either package's __init__.
        spec = importlib.util.find_spec(package)
        locations = list(spec.submodule_search_locations or []) if spec else []
        if len(locations) != 1:
            raise PatchError("Cannot uniquely locate installed package {}."
                             .format(package))
        root = Path(locations[0]).resolve()
        metadata_root = Path(distribution.locate_file("")).resolve()
        if (not root.is_dir() or not _inside(root, prefix)
                or not _inside(metadata_root, prefix)):
            raise PatchError(
                "Refusing to patch {} outside the active environment {}. "
                "Use its own Python and install requirements without "
                "--user or --system-site-packages."
                .format(root, prefix)
            )
        if root.parent != metadata_root:
            raise PatchError("{} is shadowed by {} rather than its installed "
                             "distribution at {}. Remove that PYTHONPATH entry."
                             .format(package, root, metadata_root))
        roots[package] = root
    return roots


def _preflight():
    """Read and validate every payload and destination before any mutation."""
    roots = _package_roots()
    manifest_path = PATCH_ROOT / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PatchError("Cannot read {}: {}".format(manifest_path, exc)) from exc
    if not isinstance(manifest, list) or not manifest:
        raise PatchError("Patch manifest must be a nonempty list.")
    plan = []
    seen = set()
    for entry in manifest:
        if (not isinstance(entry, dict)
                or not all(isinstance(entry.get(key), str)
                           for key in ("package", "path", "sha256", "note"))
                or entry["package"] not in roots):
            raise PatchError("Invalid patch manifest entry: {!r}".format(entry))
        package = entry["package"]
        relative = entry["path"]
        source = _safe_path(PATCH_ROOT, package + "/" + relative)
        destination = _safe_path(roots[package], relative)
        if destination in seen:
            raise PatchError("Duplicate destination: {}".format(destination))
        seen.add(destination)
        try:
            payload = source.read_bytes()
            current = destination.read_bytes() if destination.exists() else None
        except OSError as exc:
            raise PatchError("Cannot read patch files: {}".format(exc)) from exc
        if hashlib.sha256(payload).hexdigest() != entry["sha256"]:
            raise PatchError("Vendored patch is corrupt or modified: {}".format(source))
        # Refuse to overwrite unrelated local modifications. The accuracy fix
        # accepts the pinned upstream file; block's omitted resources may be new.
        if current is not None and current != payload:
            current_hash = hashlib.sha256(current).hexdigest()
            if current_hash != entry.get("upstream_sha256"):
                raise PatchError(
                    "Unexpected contents at {}. Reinstall the pinned package "
                    "in a clean environment before applying patches."
                    .format(destination)
                )
        parent = destination.parent
        while parent != roots[package]:
            if parent.exists() and not parent.is_dir():
                raise PatchError("Patch parent is not a directory: {}".format(parent))
            parent = parent.parent
        plan.append((destination, payload, current == payload))
    return plan


def _apply(plan):
    """Stage all changed files, then atomically replace each destination."""
    staged = []
    try:
        for destination, payload, matches in plan:
            if matches:
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                prefix=".pwvqa-patch-", dir=str(destination.parent), delete=False
            ) as stream:
                temporary = Path(stream.name)
                staged.append((temporary, destination))
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            if destination.exists():
                temporary.chmod(destination.stat().st_mode)
            else:
                temporary.chmod(0o644)
        for temporary, destination in staged:
            os.replace(str(temporary), str(destination))
    finally:
        for temporary, _ in staged:
            if temporary.exists():
                temporary.unlink()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="check installed bytes without writing files")
    args = parser.parse_args(argv)
    try:
        plan = _preflight()
        changed = [destination for destination, _, matches in plan if not matches]
        if args.check:
            if changed:
                for destination in changed:
                    print("NEEDS PATCH: {}".format(destination))
                print("Run {} scripts/apply_patches.py to apply {} patch file(s)."
                      .format(sys.executable, len(changed)))
                return 1
            print("OK: all {} patch files match in {}."
                  .format(len(plan), sys.prefix))
            return 0
        _apply(plan)
        if any(destination.read_bytes() != payload
               for destination, payload, _ in plan):
            raise PatchError("Post-install byte verification failed.")
        print("Applied {} file(s); {} already match. Environment: {}"
              .format(len(changed), len(plan) - len(changed), sys.prefix))
        return 0
    except (PatchError, OSError, ImportError, ValueError) as exc:
        print("Patch error: {}".format(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

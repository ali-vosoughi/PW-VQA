# Reproduction report - 2026-10-01

Repository: `ali-vosoughi/PW-VQA`

Local branch: `repro-2026-10`

Starting commit: `a46c34e`

Session ID: `01a0fa4c-cc0f-7143-8ab6-551b0b9ef31e`

The repair replaces the undocumented environment copies with a checked,
idempotent installer and exact dependency locks. It preserves the model code
and original patch contents. The historical paper environment cannot be fully
recovered from the repository; newly selected versions are identified below.

## What the manual copies did

The README's first copy replaced `bootstrap/models/metrics/accuracy.py`.
Compared with the published `bootstrap.pytorch==0.0.13` source, the only code
change is `.contiguous()` before `.view(-1)` on the transposed top-k correctness
tensor. The unpatched function fails with a tensor-stride error on the regression
fixture; the replacement computes the expected result.

The second copy installed the complete `external/VQA/` tree under
`block/external/VQA/`. The `block.bootstrap.pytorch==0.1.6` PyPI distribution
omits that directory. The repository's 11 files match upstream BLOCK commit
`e938e9e269d2ec67499db327b903edbe821fed5f`; this copy restores omitted files
without changing the upstream VQA scoring rules. The two runtime modules are
`PythonHelperTools/vqaTools/vqa.py` and
`PythonEvaluationTools/vqaEvaluation/vqaEval.py`. The other nine files are
package initializers, demos, documentation, question types, and a bundled fake
results example. That example is neither a dataset download nor a checkpoint.

The exact upstream projects are
[Cadene/bootstrap.pytorch](https://github.com/Cadene/bootstrap.pytorch) and
[Cadene/block.bootstrap.pytorch](https://github.com/Cadene/block.bootstrap.pytorch).
Their selected published versions are
[Bootstrap 0.0.13](https://pypi.org/project/bootstrap.pytorch/0.0.13/) and
[BLOCK 0.1.6](https://pypi.org/project/block.bootstrap.pytorch/0.1.6/).
These were previously unspecified. Bootstrap's published accuracy file matches
commit `6550ae1c0598da071976a0a48f6d5329033eeb87`; current Git HEAD is different
code despite retaining the version string. The comparison used the published
source archive, not an assumed Git HEAD.

## Replacement and documentation

- Moved all 12 original files to `patches/`, preserving their Git-blob bytes.
  `patches/manifest.json` records per-file SHA-256 values and one-line notes;
  `patches/README.md` explains each target.
- Added `scripts/apply_patches.py`. It discovers the packages belonging to the
  invoking interpreter, checks exact distribution versions and all source and
  destination files before writing, stages replacements, and atomically replaces
  each changed file. It refuses unexpected local modifications and paths outside
  the active environment. Python 3.9's distribution-name normalization difference
  is handled. It imports only the standard library.
- `--check` performs a read-only byte comparison and exits nonzero for missing,
  changed, or incompatible files. A second application leaves matching files
  and their modification times unchanged.
- Added Python/runtime/build pins, CPU and CUDA lock files, and
  `scripts/setup.sh`. Setup creates an isolated venv, installs the selected lock,
  applies patches, runs the smoke test, and checks dependency consistency.
  `PWVQA_VENV` can select a different venv directory.
- Rewrote installation, training, and evaluation as numbered commands. Corrected
  the malformed Bash fence and closed the previously unterminated citation fence.
  The upstream attribution paragraphs and BibTeX contents are unchanged.
- Fixed the dataset shell scripts to resolve paths from their repository root
  and stop on failure. The old VQA2 script nested the feature directory under
  `data/vqa/data/vqa/`, inconsistent with the model configuration.
- Documented the three upstream Skip-Thought files required by the text encoder,
  the absence of released PW-VQA checkpoints, and the Linux/CUDA model-run
  requirement. The audit read every tracked Python/shell script, all supplied
  options, and relevant history. No notebooks or checkpoint files occur in that
  history; the GitHub releases endpoint returned an empty list.

## Pins and provenance

The repository's `a34a28313cf82f0013f21dd9a93eef8fd70aff87` change from
2024-06-07 supplies the historical exact pins. Those are evidence of declared
requirements, not proof of a captured training environment.

| Component | Exact selection | Provenance/reason |
| --- | --- | --- |
| Python | 3.9.23 | README specified Python 3.9; patch release chosen from the managed builds provided by the pinned setup tool. Bootstrap uses `collections.Mapping`, which prevents an unmodified Python 3.10+ setup. |
| Plotly | 3.10.0 | Historical requirement; Bootstrap imports the old `plotly.plotly` API. |
| h5py | 3.7.0 | Historical requirement. |
| PyYAML | 5.4.1 | Historical requirement; Bootstrap calls `yaml.load` without a Loader argument. |
| tqdm | 4.64.1 | Historical requirement. |
| SciPy | 1.9.3 | Historical requirement. |
| Bootstrap / BLOCK | 0.0.13 / 0.1.6 | Historical exact versions not recorded; latest published releases selected and imported successfully. |
| PyTorch / TorchVision | 2.8.0+cpu / 0.23.0+cpu | Latest compatible Python 3.9 releases selected from official PyTorch wheels and checked on CPU. CUDA lock selects matching `+cu128` builds, which were not executed. |
| NumPy | 1.25.2 | Latest version compatible with the retained SciPy requirement `numpy<1.26`. |
| OpenCV | 4.11.0.86 | Latest compatible version; newer releases require NumPy 2 on Python 3.9. Required by BLOCK's imported dataset modules. |
| skipthoughts / pretrainedmodels | 0.0.1 / 0.7.4 | Latest published upstream dependencies; original exact versions not recorded. |
| pip | 26.0.1 | Latest release compatible with Python 3.9; Bootstrap invokes `pip freeze` when starting an experiment. |
| uv | 0.8.17 | Setup/resolution tool used in this session, explicitly pinned. |
| setuptools / wheel / packaging | 82.0.1 / 0.48.0 / 26.3 | Latest Python 3.9-compatible isolated build dependencies, pinned in `requirements-build.txt`. |

All remaining transitive runtime versions are exact in `requirements.txt` and
`requirements-cu128.txt`. They were previously unspecified and were resolved to
the latest compatible versions under the constraints above. Platform markers
separate Windows and Linux dependencies. The primary package sources are PyPI
and the official PyTorch wheel indexes. `pyproject.toml` records the inputs;
the generated lock headers record their exact resolution commands. Setup uses
both official indexes with exact pins because the PyTorch mirror also contains
older copies of general Python dependencies.

CLIP, LAVIS, vit-pytorch, ftfy, and regex were removed from this reproduction
environment because none is imported by the released scripts. The previous
requirements pinned ftfy 6.1.1 and regex 2022.10.31, but used unpinned Git URLs for
CLIP/LAVIS and only a lower bound for vit-pytorch. Installing these unused
frameworks would not improve reproducibility of the documented S-MRL run.

## Evaluation command and paper metric

After the README's data preparation and local training:

```bash
python -m bootstrap.run \
  -o logs/vqacp2/smrl_pwvqa/options.yaml \
  --exp.resume last \
  --dataset.train_split \
  --dataset.eval_split val \
  --misc.logs_name test
```

The bare `--dataset.train_split` parses as `None`, disabling training and
optimizer restoration. The loader maps published VQA-CP v2 test questions and
annotations to its local `val` split. The old README incorrectly said there was
no test set.

The paper metric is overall open-ended VQA consensus accuracy, reported as
`eval_epoch.overall` in
`logs/vqacp2/smrl_pwvqa/test_pwvqa_val_oe.json`, with Yes/No, Number, and Other
breakdowns. The `accuracy_pwvqa_top1` field is a different, single-answer proxy.
See [Table I of the paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC11485245/#T1).
No paper score is copied because the original README did not identify a table.
The command evaluates the last locally trained checkpoint; no released checkpoint
establishes correspondence to a particular paper row. Metric workers run
asynchronously, so their output can appear after the main process exits.

## Verification

The final `scripts/setup.sh cpu` completed successfully in the newly created
`.venv-final` on Windows x86-64, using Git Bash and Python 3.9.23. It installed
77 pinned packages, including `torch==2.8.0+cpu`, and applied all 12 payloads.
Both `python` and `pip` resolved inside that venv after activation.

| Check | Result |
| --- | --- |
| Fresh venv installation from `requirements.txt` through `scripts/setup.sh cpu` | Passed; 77 packages installed. |
| `python scripts/apply_patches.py --check` | Passed; all 12 installed files match. |
| Second `python scripts/apply_patches.py` | Passed; 0 files changed, 12 already match. |
| `python scripts/smoke_test.py` | Passed; 18 runtime imports, noncontiguous top-k regression, synthetic VQA consensus score, and evaluation argument parsing. |
| `python -m pip check` and setup's `uv pip check` | Passed; no incompatible or missing dependencies. |
| `python -m unittest discover -s tests -v` | All 10 installer regression tests passed in Python 3.9. |
| `bash -n` on setup and both dataset scripts | Passed; dataset scripts were not executed. |
| Original patch payload comparison | All 12 files equal their starting-commit Git blobs. |
| Attribution/citation comparison and Markdown fence check | Passed; citation contents unchanged, fences balanced. |
| `git diff --check` | Passed. |

The installer tests cover no writes during checks/refusals, idempotence including
modification times, wrong/missing package versions, environment boundaries,
package shadowing, corrupt/missing payloads, path traversal, invalid destination
ancestors, Python 3.9 metadata normalization, and staging failure cleanup.
The smoke check parses the same evaluation overrides against the supplied model
options without constructing a model or dataset. The patched VQA helper,
evaluator, and `block.models.metrics.compute_oe_accuracy` imports succeed.
Bootstrap emits its inherited PyYAML deprecation warning while parsing options;
the check completes successfully.

## What could not be verified

No dataset, image features, or pretrained text-encoder weights were downloaded,
and no model was trained. No full evaluation, GPU execution, checkpoint loading,
or paper score was reproduced. CUDA and Linux dependencies were resolved, but
those installations were not executed. Native Windows only supports the checked
setup/import path: the current model contains direct `.cuda()` calls and the
upstream runner uses Unix shell commands and `os.uname()`.

Historical framework, Torch, and transitive versions cannot be established from
the repository. The replacement environment is a tested reconstruction. Existing
source archives/download links and large model assets were not validated by a
full download. PyTorch 2.8's changed `torch.load` default may affect external
legacy pickle artifacts; none was available to test. The bundled VQA evaluation
demo retains its original Python 2 syntax; it is copied for parity with the old
manual step and is not part of the Python 3 reproduction path.

The local commit message is
`Reproducible setup: pinned environment, automated patches, verified commands`.
No push is performed, and no AI co-author trailer is added.

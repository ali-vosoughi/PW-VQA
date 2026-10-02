# Environment patches

These payloads preserve the original repository files byte for byte. Apply them
with `python scripts/apply_patches.py`, using the Python interpreter of the
environment to repair; use `--check` for a read-only byte comparison. The script
accepts only `bootstrap.pytorch==0.0.13` and `block.bootstrap.pytorch==0.1.6`,
validates every source and destination before replacing files, and refuses paths
outside that interpreter's environment or unexpected local modifications.

`bootstrap/models/metrics/accuracy.py` replaces the same file in
[Cadene/bootstrap.pytorch](https://github.com/Cadene/bootstrap.pytorch)'s PyPI
0.0.13 release. Its only code change adds `.contiguous()` before `.view(-1)` on a
transposed tensor; the upstream file can otherwise fail with a stride error.

The complete `block/external/` tree restores resources missing from the
[Cadene/block.bootstrap.pytorch](https://github.com/Cadene/block.bootstrap.pytorch)
0.1.6 PyPI distribution. It matches that repository's
`e938e9e269d2ec67499db327b903edbe821fed5f` tree and does not change the evaluator's
semantics. This preserves the original README's `cp -r external .../block/` step,
including the demo files. The inherited README inside that tree documents the
original VQA release; use this repository's main README for the active environment.

`manifest.json` records a SHA-256 digest and a one-line change note for every file:

| File beneath `patches/` | Change |
| --- | --- |
| `bootstrap/models/metrics/accuracy.py` | Make top-k correctness contiguous before flattening with `view()`. |
| `block/external/VQA/.gitignore` | Restore omitted VQA helper ignore rules. |
| `block/external/VQA/README.md` | Restore omitted upstream VQA API/evaluation documentation. |
| `block/external/VQA/PythonEvaluationTools/vqaEvalDemo.py` | Restore the omitted VQA evaluation demo. |
| `block/external/VQA/PythonEvaluationTools/vqaEvaluation/vqaEval.py` | Restore the omitted VQA answer normalization and consensus-accuracy evaluator. |
| `block/external/VQA/PythonEvaluationTools/vqaEvaluation/__init__.py` | Restore the omitted evaluator package initializer. |
| `block/external/VQA/PythonHelperTools/vqaDemo.py` | Restore the omitted VQA API demo. |
| `block/external/VQA/PythonHelperTools/vqaTools/vqa.py` | Restore the omitted VQA annotation/question/result-loading API. |
| `block/external/VQA/PythonHelperTools/vqaTools/__init__.py` | Restore the omitted API package initializer. |
| `block/external/VQA/QuestionTypes/abstract_v002_question_types.txt` | Restore the omitted abstract-scene question types. |
| `block/external/VQA/QuestionTypes/mscoco_question_types.txt` | Restore the omitted MS COCO question types. |
| `block/external/VQA/Results/OpenEnded_mscoco_train2014_fake_results.json` | Restore the omitted fake-results demo resource; it is not a checkpoint or evaluation result. |

Payload text conversion is disabled in `.gitattributes` so identical bytes are
installed on Windows and Unix. Re-running the installer leaves matching files
untouched. It stages all changed files before atomic replacement of each file;
an interrupted run can safely be rerun. It does not import the ML packages or
download data. A successful `--check` confirms file contents, not model accuracy.

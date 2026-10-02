"""Check runtime imports, CLI parsing and patched metrics without downloading data."""
import importlib
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    subprocess.run([sys.executable, "-m", "pip", "--version"], check=True)
    subprocess.run([sys.executable, str(ROOT / "scripts/apply_patches.py"), "--check"],
                   check=True)
    modules = [
        "torch", "torchvision", "numpy", "scipy", "h5py", "cv2",
        "bootstrap.run", "bootstrap.models.metrics.accuracy",
        "block.models.metrics.compute_oe_accuracy",
        "block.external.VQA.PythonHelperTools.vqaTools.vqa",
        "block.external.VQA.PythonEvaluationTools.vqaEvaluation.vqaEval",
        "pwvqa.datasets.factory", "pwvqa.models.networks.factory",
        "pwvqa.models.networks.smrl_net", "pwvqa.models.networks.updn_net",
        "pwvqa.models.networks.san_net", "pwvqa.models.criterions.factory",
        "pwvqa.models.metrics.factory", "pwvqa.optimizers.factory",
    ]
    for name in modules:
        importlib.import_module(name)
        print("Import OK:", name)

    import torch
    from bootstrap.models.metrics.accuracy import accuracy
    from block.external.VQA.PythonHelperTools.vqaTools.vqa import VQA
    from block.external.VQA.PythonEvaluationTools.vqaEvaluation.vqaEval import VQAEval
    from bootstrap.lib.options import Options

    # A batch and k > 1 exercise the transpose/view regression in Bootstrap.
    logits = torch.tensor([[9., 8., 7., 6., 5., 4.], [1., 2., 3., 4., 5., 6.]])
    scores = accuracy(logits, torch.tensor([0, 0]), topk=[1, 5])
    assert [s.item() for s in scores] == [50.0, 50.0], scores

    # Exercise the actual VQA evaluator on one synthetic, unanimous answer.
    ground_truth, predictions = VQA(), VQA()
    ground_truth.dataset = {"annotations": [{"question_id": 1}]}
    ground_truth.qa = {1: {
        "answers": [{"answer_id": i, "answer": "yes"} for i in range(10)],
        "question_type": "is", "answer_type": "yes/no",
    }}
    predictions.qa = {1: {"answer": "yes"}}
    evaluator = VQAEval(ground_truth, predictions)
    evaluator.evaluate()
    assert evaluator.accuracy["overall"] == 100.0

    # Parse the evaluation overrides without constructing a dataset or model.
    # --dataset.train_split with no value becomes None and skips optimizer resume.
    original_argv = sys.argv
    try:
        sys.argv = ["smoke_test", "--exp.resume", "last", "--dataset.train_split",
                    "--dataset.eval_split", "val", "--misc.logs_name", "test"]
        options = Options(str(ROOT / "pwvqa/options/vqacp2/smrl_pwvqa.yaml"))
        assert options["dataset.train_split"] is None
        assert options["dataset.eval_split"] == "val"
        assert options["exp.resume"] == "last"
        assert options["misc.logs_name"] == "test"
    finally:
        sys.argv = original_argv
    print("PASS: imports, patched top-k accuracy, synthetic VQA score, evaluation options")
    print("No dataset, pretrained weights, training or full evaluation used.")


if __name__ == "__main__":
    main()

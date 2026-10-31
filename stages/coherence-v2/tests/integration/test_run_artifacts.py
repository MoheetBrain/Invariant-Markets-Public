import json

from invariant.cli import run
from invariant.core.types import SimulationResult


EXPECTED_FIGURES = {
    "expected_claim_vs_portfolio_size.png",
    "claim_probability_vs_portfolio_size.png",
    "expected_shortfall_99_5_vs_portfolio_size.png",
    "baseline_portfolio_return_distribution.png",
    "baseline_guarantee_claim_distribution.png",
}


def test_run_writes_complete_artifact_set_and_honours_seed_override(repository_root, tmp_path):
    run_directory = run(
        repository_root / "configs" / "base.yaml",
        tmp_path / "runs",
        seed=42,
    )
    assert {path.name for path in run_directory.iterdir()} == {
        "config.yaml", "results.json", "summary.md", "manifest.json", "figures"
    }
    assert {path.name for path in (run_directory / "figures").iterdir()} == EXPECTED_FIGURES
    result_data = json.loads((run_directory / "results.json").read_text())
    assert SimulationResult.from_dict(result_data).as_dict() == result_data
    manifest = json.loads((run_directory / "manifest.json").read_text())
    assert manifest["random_seed"] == 42
    assert manifest["config_hash"]
    assert manifest["python_version"]
    assert manifest["model_version"] == "0.2.0-synthetic"


def test_same_seed_reproduces_numerical_results_exactly(repository_root, tmp_path):
    first = run(repository_root / "configs" / "base.yaml", tmp_path / "first", seed=42)
    second = run(repository_root / "configs" / "base.yaml", tmp_path / "second", seed=42)
    assert (first / "results.json").read_bytes() == (second / "results.json").read_bytes()

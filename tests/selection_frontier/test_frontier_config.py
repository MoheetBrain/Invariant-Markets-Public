import hashlib
import json

import pytest

from invariant.experiments.frontiers import solve_decreasing_frontier, solve_increasing_frontier
from invariant.experiments.planner import plan_experiments
from invariant.reporting.artifacts import canonical_hash


def test_frozen_s2a_config_hash(repository_root):
    assert _sha256(repository_root / "configs" / "base.yaml") == (
        "bfa87da2cb59fcf6e396ee95f1f844b0d89e5ecf5f408ed7c74f001fab197710"
    )


def test_frozen_s2b_a_config_hash(repository_root):
    assert _sha256(repository_root / "configs" / "calibrated_terminal_v1.yaml") == (
        "8fda6c37e56db97ef99b5c82021328fcafcb9c2a01d759a865fcf5d085f10852"
    )


def test_no_scenario_assumption_is_observed_or_fitted(selection_frontier_config):
    forbidden = {"OBSERVED", "FITTED", "OBSERVED_RAW", "OBSERVED_AGGREGATE"}
    assert all(
        assumption["provenance"] not in forbidden
        for assumption in selection_frontier_config["assumptions"].values()
    )


def test_experiment_plan_has_every_stage(selection_frontier_config):
    plan = plan_experiments(selection_frontier_config)
    assert {item.tier for item in plan} >= {
        "core",
        "sensitivity",
        "discovery",
        "refinement",
        "stress",
    }
    assert all(item.number_of_paths >= 100_000 for item in plan if item.tier == "core")


def test_increasing_frontier_interpolates():
    result = solve_increasing_frontier((0.0, 0.5, 1.0), (0.0, 0.10, 0.20), 0.05)
    assert result.boundary == pytest.approx(0.25)
    assert result.status == "interpolated"


def test_decreasing_frontier_interpolates():
    result = solve_decreasing_frontier((0.0, 1.0, 2.0), (0.20, 0.10, 0.0), 0.05)
    assert result.boundary == pytest.approx(1.5)


def test_serialization_hash_is_mapping_order_invariant():
    assert canonical_hash({"a": 1, "b": [2, 3]}) == canonical_hash(
        {"b": [2, 3], "a": 1}
    )


def test_json_serialization_is_deterministic():
    value = {"z": 1.0, "a": [True, None]}
    first = json.dumps(value, sort_keys=True, separators=(",", ":"))
    second = json.dumps(value, sort_keys=True, separators=(",", ":"))
    assert first == second


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

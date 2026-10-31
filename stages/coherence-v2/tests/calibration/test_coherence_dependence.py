import csv
import hashlib
from pathlib import Path

import numpy as np
import pytest
import yaml

from invariant.calibration.coherence_dependence import (
    OBSERVATION_OBJECT_TYPES,
    _baseline_spec,
    build_rho_grid,
    claim_metrics,
    coherence_weights,
    interpolate_breakpoint,
    load_observation_audit,
    require_investor_moic_mapping,
    simulate_nested_portfolios,
    validate_observation_rows,
)
from invariant.models.terminal.empirical_mixture import inverse_terminal_return_cdf


ROOT = Path(__file__).resolve().parents[2]


def _config():
    with (ROOT / "configs/research/empirical_coherence_dependence_v2.yaml").open() as handle:
        return yaml.safe_load(handle)


def _portfolio(paths=1000):
    return simulate_nested_portfolios(
        _baseline_spec(_config()),
        family="gaussian_factor",
        rho=0.2,
        portfolio_sizes=(20,),
        number_of_paths=paths,
        random_seed=17,
    )[20]


def test_rho_grid_is_exactly_zero_to_point_four_by_point_zero_one():
    grid = build_rho_grid(0.0, 0.4, 0.01)
    assert len(grid) == 41
    assert grid[0] == 0.0
    assert grid[-1] == 0.4
    assert np.allclose(np.diff(grid), 0.01)


def test_breakpoint_solver_interpolates_analytical_linear_case():
    solved = interpolate_breakpoint([0.0, 0.1, 0.2], [0.0, 0.04, 0.08], 0.05)
    assert solved["status"] == "INTERPOLATED"
    assert solved["rho"] == pytest.approx(0.125)


def test_breakpoint_solver_reports_outside_grid():
    assert interpolate_breakpoint([0, 1], [0.1, 0.2], 0.05)["status"] == "BELOW_GRID_MIN"
    assert interpolate_breakpoint([0, 1], [0.1, 0.2], 0.25)["status"] == "ABOVE_GRID_MAX"


@pytest.mark.parametrize("probability", [0.62, 0.65, 0.68])
@pytest.mark.parametrize("scale", [0.5, 0.75, 1.0])
def test_coherence_mixture_weights_are_valid(probability, scale):
    weights = coherence_weights(probability, scale)
    assert sum(weights.values_for_sampling) == pytest.approx(1.0)
    weights.validate()


def test_increasing_floor_cannot_reduce_claim():
    portfolio = _portfolio()
    low = claim_metrics(portfolio, 0.75)
    high = claim_metrics(portfolio, 0.90)
    assert high["expected_claim_per_unit"] >= low["expected_claim_per_unit"]
    assert high["probability_claim"] >= low["probability_claim"]


def test_deleting_value_cannot_reduce_path_claim():
    portfolio = _portfolio()
    normal = np.maximum(0.9 - portfolio.terminal_multiples, 0.0)
    without_top1 = np.maximum(0.9 - portfolio.without_top1, 0.0)
    without_top5 = np.maximum(0.9 - portfolio.without_top5, 0.0)
    without_10x = np.maximum(0.9 - portfolio.without_ge_10x, 0.0)
    assert np.all(without_top1 >= normal)
    assert np.all(without_top5 >= without_top1)
    assert np.all(without_10x >= normal)


def test_same_seed_reproduces_dependence_outputs():
    first = _portfolio(paths=250)
    second = _portfolio(paths=250)
    np.testing.assert_array_equal(first.terminal_multiples, second.terminal_multiples)
    np.testing.assert_array_equal(first.without_ge_50x, second.without_ge_50x)


@pytest.mark.parametrize("rho", [-0.01, 1.01])
def test_invalid_correlation_is_rejected(rho):
    with pytest.raises(ValueError):
        simulate_nested_portfolios(
            _baseline_spec(_config()),
            family="gaussian_factor",
            rho=rho,
            portfolio_sizes=(10,),
            number_of_paths=10,
            random_seed=1,
        )


def test_observation_audit_has_required_explicit_object_types():
    rows = load_observation_audit(ROOT / "data/calibration/unit_of_observation_audit_v2.csv")
    assert len(rows) == 22
    assert {row["object_measured"] for row in rows} <= OBSERVATION_OBJECT_TYPES
    assert {"FINANCING_ROUND", "FUND_TVPI", "FOUNDER_PROCEEDS"} <= {
        row["object_measured"] for row in rows
    }


def test_fund_tvpi_requires_explicit_investor_moic_mapping():
    observation = {"object_measured": "FUND_TVPI"}
    with pytest.raises(ValueError, match="explicit mapping"):
        require_investor_moic_mapping(observation)
    assert require_investor_moic_mapping(observation, "DOCUMENTED_BRIDGE") == "DOCUMENTED_BRIDGE"


def test_financing_round_cannot_be_silently_labelled_unique_company():
    with (ROOT / "data/calibration/unit_of_observation_audit_v2.csv").open(newline="") as handle:
        row = next(csv.DictReader(handle))
    row["object_measured"] = "UNIQUE_COMPANY"
    with pytest.raises(ValueError, match="financing-round"):
        validate_observation_rows([row])


def test_frozen_v1_inputs_are_byte_unchanged():
    expected = {
        "configs/calibrated_terminal_v1.yaml": "8fda6c37e56db97ef99b5c82021328fcafcb9c2a01d759a865fcf5d085f10852",
        "data/calibration/empirical_constraints_v1.yaml": "6cc609ddd6888fe4d12b79f27c1559d1960d84371e8f2a4c6ca0461010533adc",
        "data/calibration/source_registry.yaml": "6133db75db90a5180d7b7b1834738488c1323f6b07adb7b981c0c057bd907021",
    }
    for name, digest in expected.items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest


def test_v1_marginal_constraints_and_mean_remain_reproducible():
    spec = _baseline_spec(_config())
    values = inverse_terminal_return_cdf((np.arange(500_000) + 0.5) / 500_000, spec)
    assert np.mean(values < 1) == pytest.approx(0.65, abs=1e-6)
    assert np.mean(values >= 5) == pytest.approx(0.10, abs=1e-6)
    assert np.mean(values >= 10) == pytest.approx(0.04, abs=1e-6)
    assert np.mean(values >= 50) == pytest.approx(0.004, abs=2e-5)
    assert np.mean(values) == pytest.approx(2.3396, abs=0.01)

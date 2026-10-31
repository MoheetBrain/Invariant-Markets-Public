import subprocess

import pytest

from invariant.calibration.constraints import (
    load_empirical_constraints,
    load_source_registry,
    source_ids_used,
)
from invariant.calibration.diagnostics import (
    model_implied_constraint_probabilities,
    tail_beta_from_constraints,
    validate_terminal_constraints,
)
from invariant.calibration.parameter_models import (
    CorrelationSpec,
    EmpiricalMixtureSpec,
    TailSpec,
    calibrate_survival_tail_beta,
    derive_mixture_weights,
    pareto_survival_probability,
)
from invariant.models.terminal.empirical_mixture import inverse_terminal_return_cdf


@pytest.fixture
def source_registry(repository_root):
    return load_source_registry(repository_root / "data" / "calibration" / "source_registry.yaml")


@pytest.fixture
def empirical_constraints(repository_root, source_registry):
    return load_empirical_constraints(
        repository_root / "data" / "calibration" / "empirical_constraints_v1.yaml",
        source_registry,
    )


def _baseline_spec(empirical_constraints):
    weights = derive_mixture_weights(empirical_constraints)
    beta = tail_beta_from_constraints(empirical_constraints)
    return EmpiricalMixtureSpec(
        name="test",
        body=__import__("invariant.calibration.parameter_models", fromlist=["BodySpec"]).BodySpec(
            "log_uniform"
        ),
        tail=TailSpec(
            name="capped_1000x",
            survival_tail_exponent_beta=beta,
            cap=1000.0,
            mode="capped_pareto",
        ),
        correlation=CorrelationSpec(name="independent", model="independent"),
        weights=weights,
    )


def test_source_registry_contains_no_orphan_constraint_source_ids(
    source_registry, empirical_constraints
):
    assert source_ids_used(empirical_constraints) <= set(source_registry["sources"])


def test_observed_constraints_are_not_backed_by_expert_or_model_risk_sources(
    source_registry, empirical_constraints
):
    risky = {"EXPERT", "MODEL_RISK_SCENARIO", "UNKNOWN"}
    for source_id in source_ids_used(empirical_constraints):
        source = source_registry["sources"][source_id]
        if source["provenance_classification"].startswith("OBSERVED"):
            assert source["provenance_classification"] not in risky


def test_s2a_base_configuration_is_unchanged_from_tag(repository_root):
    tagged = subprocess.run(
        ["git", "show", "v0.2.0-s2a:configs/base.yaml"],
        cwd=repository_root,
        check=True,
        capture_output=True,
    ).stdout
    assert (repository_root / "configs" / "base.yaml").read_bytes() == tagged


def test_empirical_probabilities_are_internally_consistent(empirical_constraints):
    weights = derive_mixture_weights(empirical_constraints)
    weights.validate()
    assert sum(weights.values_for_sampling) == pytest.approx(1.0)
    assert weights.complete_loss == pytest.approx(0.39)
    assert weights.partial_loss == pytest.approx(0.26)
    assert weights.tail_10x_plus == pytest.approx(0.04)


def test_tail_beta_calibration_reproduces_10x_50x_ratio(empirical_constraints):
    beta = calibrate_survival_tail_beta(0.04, 0.004, 10.0, 50.0)
    assert beta == pytest.approx(tail_beta_from_constraints(empirical_constraints))
    assert pareto_survival_probability(50.0, 10.0, beta) == pytest.approx(0.1)


def test_model_implied_probabilities_match_baseline_constraints(empirical_constraints):
    spec = _baseline_spec(empirical_constraints)
    implied = model_implied_constraint_probabilities(spec)
    assert implied["below_1x"] == pytest.approx(0.65)
    assert implied["above_5x"] == pytest.approx(0.10)
    assert implied["above_10x"] == pytest.approx(0.04)
    assert implied["above_50x"] == pytest.approx(0.004)


def test_sampled_marginal_reproduces_constraints_with_tolerance(empirical_constraints):
    spec = _baseline_spec(empirical_constraints)
    import numpy as np

    rng = np.random.default_rng(123)
    returns = inverse_terminal_return_cdf(rng.random(300_000), spec)
    residuals = validate_terminal_constraints(returns, empirical_constraints)
    assert all(item.within_tolerance for item in residuals)

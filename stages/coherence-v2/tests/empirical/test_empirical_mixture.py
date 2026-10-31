import numpy as np
import pytest

from invariant.calibration.diagnostics import tail_beta_from_constraints
from invariant.calibration.parameter_models import (
    BodySpec,
    CorrelationSpec,
    EmpiricalMixtureSpec,
    TailSpec,
    derive_mixture_weights,
)
from invariant.calibration.uncertainty import (
    draw_parameter_universes,
    summarize_parameter_draws,
)
from invariant.models.terminal.empirical_mixture import (
    EmpiricalTerminalMixtureModel,
    build_empirical_metrics,
    empirical_diluted_warrant_fraction,
    inverse_terminal_return_cdf,
)


def _spec(empirical_constraints, *, tail_mode="capped_pareto", cap=1000.0, correlation=None):
    return EmpiricalMixtureSpec(
        name=f"test_{tail_mode}_{correlation.model if correlation else 'independent'}",
        body=BodySpec("log_uniform"),
        tail=TailSpec(
            name=tail_mode,
            survival_tail_exponent_beta=tail_beta_from_constraints(empirical_constraints),
            cap=cap,
            mode=tail_mode,
        ),
        correlation=correlation or CorrelationSpec(name="independent", model="independent"),
        weights=derive_mixture_weights(empirical_constraints),
    )


def test_sampled_returns_are_non_negative(empirical_constraints):
    spec = _spec(empirical_constraints)
    values = inverse_terminal_return_cdf(np.linspace(0, 0.999999, 10_000), spec)
    assert np.all(values >= 0)


def test_tail_sampling_respects_threshold_and_capped_pareto_cap(empirical_constraints):
    spec = _spec(empirical_constraints, tail_mode="capped_pareto", cap=500.0)
    values = inverse_terminal_return_cdf(np.linspace(0.961, 0.999999, 10_000), spec)
    assert np.all(values >= 10.0)
    assert np.max(values) <= 500.0


def test_no_mega_winner_stress_generates_no_50x_winners(empirical_constraints):
    spec = _spec(empirical_constraints, tail_mode="no_mega_winner", cap=50.0)
    values = inverse_terminal_return_cdf(np.linspace(0.961, 0.999999, 10_000), spec)
    assert np.max(values) < 50.0


def test_same_seed_and_spec_reproduce_portfolio_outputs(empirical_constraints):
    spec = _spec(empirical_constraints)
    model = EmpiricalTerminalMixtureModel()
    first = model.simulate_portfolio(spec, portfolio_size=25, number_of_paths=500, random_seed=7)
    second = model.simulate_portfolio(spec, portfolio_size=25, number_of_paths=500, random_seed=7)
    np.testing.assert_allclose(first.terminal_multiples, second.terminal_multiples)
    np.testing.assert_array_equal(first.count_ge_10x, second.count_ge_10x)


def test_parameter_draws_are_reproducible_and_bounded(empirical_constraints):
    first = draw_parameter_universes(empirical_constraints, number_of_draws=20, random_seed=5)
    second = draw_parameter_universes(empirical_constraints, number_of_draws=20, random_seed=5)
    assert first == second
    summary = summarize_parameter_draws(first)
    assert summary["survival_tail_exponent_beta"]["min"] > 0
    for draw in first:
        weights = draw["weights"]
        total = (
            weights["complete_loss"]
            + weights["partial_loss"]
            + weights["ordinary_success_1_5x"]
            + weights["strong_success_5_10x"]
            + weights["tail_10x_plus"]
        )
        assert total == pytest.approx(1.0)


def test_correlation_specs_validate_factor_bounds():
    CorrelationSpec(name="ok", model="gaussian_factor", rho_macro=0.3).validate()
    with pytest.raises(ValueError):
        CorrelationSpec(name="bad", model="gaussian_factor", rho_macro=1.2).validate()
    with pytest.raises(ValueError):
        CorrelationSpec(name="bad_t", model="student_t_factor", rho_macro=0.2, degrees_of_freedom=1).validate()


def test_rho_zero_factor_preserves_one_dimensional_marginal(empirical_constraints):
    independent = _spec(empirical_constraints)
    gaussian_zero = _spec(
        empirical_constraints,
        correlation=CorrelationSpec(name="rho0", model="gaussian_factor", rho_macro=0.0),
    )
    model = EmpiricalTerminalMixtureModel()
    base = model.simulate_portfolio(independent, portfolio_size=20, number_of_paths=4000, random_seed=9)
    rho0 = model.simulate_portfolio(gaussian_zero, portfolio_size=20, number_of_paths=4000, random_seed=9)
    assert abs(np.mean(base.terminal_multiples) - np.mean(rho0.terminal_multiples)) < 0.15


def test_increasing_rho_does_not_change_marginal_calibration_by_construction(empirical_constraints):
    low = _spec(
        empirical_constraints,
        correlation=CorrelationSpec(name="rho0", model="gaussian_factor", rho_macro=0.0),
    )
    high = _spec(
        empirical_constraints,
        correlation=CorrelationSpec(name="rho30", model="gaussian_factor", rho_macro=0.3),
    )
    u = np.linspace(0.000001, 0.999999, 50_000)
    low_returns = inverse_terminal_return_cdf(u, low)
    high_returns = inverse_terminal_return_cdf(u, high)
    np.testing.assert_allclose(low_returns, high_returns)


def test_removing_top_winners_cannot_increase_nav_or_decrease_claim(empirical_constraints):
    spec = _spec(empirical_constraints)
    portfolio = EmpiricalTerminalMixtureModel().simulate_portfolio(
        spec, portfolio_size=50, number_of_paths=1000, random_seed=11
    )
    assert np.all(portfolio.terminal_without_top1 <= portfolio.terminal_multiples)
    assert np.all(portfolio.terminal_without_top3 <= portfolio.terminal_without_top1)
    claim = np.maximum(0.75 - portfolio.terminal_multiples, 0.0)
    claim_without_top1 = np.maximum(0.75 - portfolio.terminal_without_top1, 0.0)
    claim_without_top3 = np.maximum(0.75 - portfolio.terminal_without_top3, 0.0)
    assert np.all(claim_without_top1 >= claim)
    assert np.all(claim_without_top3 >= claim_without_top1)


def test_var_es_sign_convention_and_warrant_arithmetic(empirical_constraints):
    spec = _spec(empirical_constraints)
    portfolio = EmpiricalTerminalMixtureModel().simulate_portfolio(
        spec, portfolio_size=25, number_of_paths=1000, random_seed=13
    )
    warrant = empirical_diluted_warrant_fraction(0.02, (0.205, 0.201))
    metrics = build_empirical_metrics(
        portfolio,
        protection_fraction=0.75,
        terminal_warrant_fraction=warrant,
        stop_loss_attachment=0.05,
        stop_loss_limit=0.35,
    )
    assert metrics["guarantee_claim_var_99.5_per_unit"] >= metrics["guarantee_claim_var_95_per_unit"]
    assert (
        metrics["guarantee_claim_expected_shortfall_99.5_per_unit"]
        >= metrics["guarantee_claim_var_99.5_per_unit"]
    )
    assert warrant == pytest.approx(0.02 * (1 - 0.205) * (1 - 0.201))

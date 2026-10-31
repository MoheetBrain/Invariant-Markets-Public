import numpy as np
import pytest

from invariant.experiments.model_factory import (
    exponential_tilt_marginals,
    factor_specification,
    target_selection_marginals,
)
from invariant.portfolio.factor_model import (
    FactorSpecification,
    compose_latent_scores,
    factor_variance_coefficients,
    literal_all_failure_probability_one_factor,
)
from invariant.portfolio.failure_tolerance import (
    effective_portfolio_size,
    failure_tolerance,
    portfolio_multiple_from_failure_count,
)
from invariant.portfolio.simulation import (
    SelectedFactorPortfolioModel,
    exact_empirical_expected_shortfall,
    innovation_barbell_returns,
)
from invariant.selection.models import marginal_diagnostics


def test_zero_recovery_failure_formula():
    result = failure_tolerance(1000, 0.75, 1.5, 0.0)
    assert result.maximum_failures == 500
    assert result.maximum_failure_fraction == 0.5


def test_positive_recovery_failure_formula():
    result = failure_tolerance(1000, 0.75, 1.5, 0.25)
    assert result.maximum_failures == 600
    assert result.maximum_failure_fraction == 0.6


def test_zero_failure_infeasibility_is_not_reported_as_zero_tolerance():
    result = failure_tolerance(1000, 1.0, 0.75, 0.0)
    assert result.maximum_failures is None
    assert not result.zero_failures_cover_floor


@pytest.mark.parametrize("portfolio_size", [100, 250, 500, 1000, 2000])
def test_failure_count_never_exceeds_portfolio_size(portfolio_size):
    result = failure_tolerance(portfolio_size, 0.5, 10.0, 0.25)
    assert result.maximum_failures is not None
    assert 0 <= result.maximum_failures <= portfolio_size


@pytest.mark.parametrize(
    ("portfolio_size", "floor", "survivor", "recovery"),
    [(100, 0.9, 2.0, 0.0), (250, 0.75, 1.25, 0.1), (2000, 1.0, 5.0, 0.25)],
)
def test_analytical_failure_boundary_matches_direct_arithmetic(
    portfolio_size, floor, survivor, recovery
):
    result = failure_tolerance(portfolio_size, floor, survivor, recovery)
    assert result.maximum_failures is not None
    covered = portfolio_multiple_from_failure_count(
        portfolio_size, result.maximum_failures, survivor, recovery
    )
    assert covered >= floor - 1e-12
    if result.maximum_failures < portfolio_size:
        breached = portfolio_multiple_from_failure_count(
            portfolio_size, result.maximum_failures + 1, survivor, recovery
        )
        assert breached < floor + 1e-12


def test_effective_portfolio_size_boundaries():
    assert effective_portfolio_size(1000, 0.0) == pytest.approx(1000)
    assert effective_portfolio_size(1000, 0.2) == pytest.approx(
        1 / (0.2 + 0.8 / 1000)
    )


def test_target_selection_probabilities_sum_to_one(
    selection_frontier_config, empirical_base_spec
):
    marginals = target_selection_marginals(
        selection_frontier_config,
        empirical_base_spec,
        selection_frontier_config["baseline_tail_model"],
    )
    for marginal in marginals.values():
        assert sum(marginal.spec.weights.values_for_sampling) == pytest.approx(1.0)


def test_unselected_target_selection_reproduces_base_exactly(
    selection_frontier_config, empirical_base_spec
):
    unselected = target_selection_marginals(
        selection_frontier_config,
        empirical_base_spec,
        selection_frontier_config["baseline_tail_model"],
    )["unselected"]
    probabilities = np.linspace(0, np.nextafter(1.0, 0.0), 10_001)
    np.testing.assert_array_equal(
        unselected.ppf(probabilities),
        __import__(
            "invariant.models.terminal.empirical_mixture", fromlist=["inverse_terminal_return_cdf"]
        ).inverse_terminal_return_cdf(probabilities, empirical_base_spec),
    )


def test_stronger_target_selection_reduces_loss_probability(
    selection_frontier_config, empirical_base_spec
):
    marginals = target_selection_marginals(
        selection_frontier_config,
        empirical_base_spec,
        selection_frontier_config["baseline_tail_model"],
    )
    weak = marginal_diagnostics(marginals["weak"], 20_000)
    hyper = marginal_diagnostics(marginals["hyper"], 20_000)
    assert hyper["probability_below_1x"] < weak["probability_below_1x"]
    assert hyper["expected_multiple"] > weak["expected_multiple"]


def test_exponential_tilt_zero_is_exact(selection_frontier_config, empirical_base_spec):
    tilt = exponential_tilt_marginals(selection_frontier_config, empirical_base_spec)[0.0]
    probabilities = np.linspace(0, np.nextafter(1.0, 0.0), 10_001)
    from invariant.models.terminal.empirical_mixture import inverse_terminal_return_cdf

    np.testing.assert_array_equal(
        tilt.ppf(probabilities), inverse_terminal_return_cdf(probabilities, empirical_base_spec)
    )


def test_stronger_exponential_tilt_improves_marginal(
    selection_frontier_config, empirical_base_spec
):
    tilts = exponential_tilt_marginals(selection_frontier_config, empirical_base_spec)
    baseline = marginal_diagnostics(tilts[0.0], 20_000)
    strong = marginal_diagnostics(tilts[0.5], 20_000)
    assert strong["expected_multiple"] > baseline["expected_multiple"]
    assert strong["probability_below_1x"] < baseline["probability_below_1x"]


def test_factor_variance_coefficients_sum_to_one():
    spec = _factor_spec(0.1, 0.3)
    assert sum(factor_variance_coefficients(spec)) == pytest.approx(1.0)


def test_invalid_rho_combination_rejected():
    with pytest.raises(ValueError, match="must not exceed one"):
        _factor_spec(0.7, 0.4).validate()


def test_zero_rho_composition_reproduces_idiosyncratic_scores():
    spec = _factor_spec(0.0, 0.0)
    macro = np.array([2.0, -1.0])
    sectors = np.array([[4.0, -4.0], [3.0, -3.0]])
    epsilon = np.array([[0.1, 0.2], [-0.1, -0.2]])
    actual = compose_latent_scores(macro, sectors, epsilon, np.array([0, 1]), spec)
    np.testing.assert_array_equal(actual, epsilon)


def test_ai_companies_share_one_sector_factor():
    spec = FactorSpecification(
        name="ai",
        portfolio_type="ai_only",
        sector_names=("AI",),
        sector_weights=(1.0,),
        rho_macro=0.0,
        rho_sector=1.0,
    )
    scores = compose_latent_scores(
        np.zeros(1), np.array([[2.0]]), np.zeros((1, 3)), np.zeros(3, dtype=int), spec
    )
    np.testing.assert_array_equal(scores, np.array([[2.0, 2.0, 2.0]]))


def test_different_sectors_do_not_share_sector_factor():
    spec = _factor_spec(0.0, 1.0)
    scores = compose_latent_scores(
        np.zeros(1),
        np.array([[2.0, -3.0]]),
        np.zeros((1, 2)),
        np.array([0, 1]),
        spec,
    )
    np.testing.assert_array_equal(scores, np.array([[2.0, -3.0]]))


def test_one_factor_all_failure_reduces_to_independent_probability():
    assert literal_all_failure_probability_one_factor(0.39, 10, 0.0, 20) == pytest.approx(
        0.39**10
    )


def test_same_seed_reproduces_portfolio(selection_frontier_config, empirical_base_spec):
    model, marginal, factor = _small_model(selection_frontier_config, empirical_base_spec)
    first = model.simulate(marginal, factor, 20, 200, 123)
    second = model.simulate(marginal, factor, 20, 200, 123)
    np.testing.assert_array_equal(first.terminal_multiples, second.terminal_multiples)


def test_different_seed_changes_portfolio(selection_frontier_config, empirical_base_spec):
    model, marginal, factor = _small_model(selection_frontier_config, empirical_base_spec)
    first = model.simulate(marginal, factor, 20, 200, 123)
    second = model.simulate(marginal, factor, 20, 200, 124)
    assert not np.array_equal(first.terminal_multiples, second.terminal_multiples)


def test_removing_winners_cannot_increase_nav(selection_frontier_config, empirical_base_spec):
    model, marginal, factor = _small_model(selection_frontier_config, empirical_base_spec)
    result = model.simulate(marginal, factor, 20, 200, 125)
    assert np.all(result.terminal_without_top3 >= 0)
    assert np.all(result.terminal_without_top1 >= 0)
    assert np.all(result.terminal_without_top3 <= result.terminal_without_top1)
    assert np.all(result.terminal_without_top1 <= result.terminal_multiples)


def test_public_sleeve_is_a_separate_weighted_sum():
    venture = np.array([0.0, 2.0])
    public = np.array([1.0, 1.0])
    np.testing.assert_array_equal(
        innovation_barbell_returns(venture, public, 0.25), np.array([0.25, 1.75])
    )


def test_expected_shortfall_uses_exact_tail_mass_when_var_is_zero():
    losses = np.array([0.0, 0.0, 0.0, 1.0])
    es_75, count_75, _ = exact_empirical_expected_shortfall(losses, 0.75)
    es_50, count_50, _ = exact_empirical_expected_shortfall(losses, 0.50)
    assert es_75 == pytest.approx(1.0)
    assert count_75 == 1
    assert es_50 == pytest.approx(0.5)
    assert count_50 == 2


def _factor_spec(rho_macro, rho_sector):
    return FactorSpecification(
        name="test",
        portfolio_type="frontier",
        sector_names=("AI", "energy"),
        sector_weights=(0.5, 0.5),
        rho_macro=rho_macro,
        rho_sector=rho_sector,
    )


def _small_model(config, base_spec):
    marginal = target_selection_marginals(config, base_spec, config["baseline_tail_model"])[
        "moderate"
    ]
    factor = factor_specification(config, "hyper_selected_frontier", 0.05, 0.10)
    return SelectedFactorPortfolioModel(batch_size=50), marginal, factor

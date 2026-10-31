from dataclasses import replace

import numpy as np

from invariant.core.config import load_config
from invariant.core.enums import MacroState
from invariant.models.terminal.structural import TerminalStructuralModel


def _small(config, seed=None):
    return replace(
        config,
        number_of_simulations=120,
        random_seed=config.random_seed if seed is None else seed,
    )


def test_identical_seed_and_config_produce_identical_results(base_config):
    config = _small(base_config, seed=42)
    assert TerminalStructuralModel().simulate(config).as_dict() == TerminalStructuralModel().simulate(config).as_dict()


def test_different_seeds_change_stochastic_results(base_config):
    first = TerminalStructuralModel().simulate(_small(base_config, seed=42))
    second = TerminalStructuralModel().simulate(_small(base_config, seed=43))
    assert first.baseline_terminal_multiples != second.baseline_terminal_multiples


def test_full_portfolio_and_protection_grid_is_calculated(base_config):
    result = TerminalStructuralModel().simulate(_small(base_config))
    assert len(result.grid_results) == 8 * 5
    assert {(point.portfolio_size, point.protection_fraction) for point in result.grid_results} == {
        (size, protection)
        for size in (1, 10, 50, 100, 250, 500, 1000, 2500)
        for protection in (0.0, 0.25, 0.50, 0.75, 1.0)
    }


def test_zero_protection_grid_points_have_zero_claim_metrics(base_config):
    result = TerminalStructuralModel().simulate(_small(base_config))
    zero_points = [point for point in result.grid_results if point.protection_fraction == 0.0]
    assert all(point.metrics["expected_guarantee_claim_per_unit"] == 0.0 for point in zero_points)
    assert all(point.metrics["guarantee_claim_var_99.5_per_unit"] == 0.0 for point in zero_points)


def test_total_wipeout_is_analytically_exact(repository_root):
    config = _small(load_config(repository_root / "configs" / "stress" / "total_wipeout.yaml"))
    result = TerminalStructuralModel().simulate(config)
    assert np.allclose(result.baseline_terminal_multiples, 0.0)
    assert np.allclose(result.baseline_guarantee_claims_per_unit, 0.75)
    assert result.baseline_metrics["probability_nav_below_protected_principal"] == 1.0


def test_shared_macro_state_counts_cover_every_path(base_config):
    config = _small(base_config)
    result = TerminalStructuralModel().simulate(config)
    assert set(result.baseline_macro_state_counts) == {state.value for state in MacroState}
    assert sum(result.baseline_macro_state_counts.values()) == config.number_of_simulations


def test_founder_warrants_remain_separate_from_guarantee_claim(base_config):
    result = TerminalStructuralModel().simulate(_small(base_config))
    expected_claims = np.maximum(
        result.baseline_protection_fraction - np.asarray(result.baseline_terminal_multiples),
        0.0,
    )
    np.testing.assert_allclose(result.baseline_guarantee_claims_per_unit, expected_claims)

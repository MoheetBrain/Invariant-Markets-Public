import pytest

from invariant.core.config import config_from_dict, config_to_dict, load_config
from invariant.core.enums import MacroState
from invariant.core.types import OUTCOME_BAND_NAMES


def test_base_configuration_contains_required_grid(base_config):
    assert base_config.assumption_status == "SYNTHETIC_SCENARIO"
    assert set(base_config.portfolio_parameters.portfolio_sizes) >= {
        1, 10, 50, 100, 250, 500, 1000, 2500
    }
    assert {float(value.value) for value in base_config.guarantee_terms.protection_fractions} >= {
        0.0, 0.25, 0.50, 0.75, 1.0
    }


def test_all_startup_return_assumptions_are_visibly_scenario(base_config):
    for regime in base_config.macro_parameters.regimes.values():
        for band in regime.outcome_bands.values():
            assert band.probability.status.value == "SCENARIO"
            assert band.minimum_return_multiple.status.value == "SCENARIO"
            assert band.maximum_return_multiple.status.value == "SCENARIO"


def test_each_regime_probability_distribution_sums_to_one(base_config):
    for regime in base_config.macro_parameters.regimes.values():
        assert set(regime.outcome_bands) == set(OUTCOME_BAND_NAMES)
        assert sum(float(band.probability.value) for band in regime.outcome_bands.values()) == pytest.approx(1.0)


def test_configuration_rejects_outcome_probabilities_that_do_not_sum_to_one(base_config):
    data = config_to_dict(base_config)
    data["macro"]["regimes"]["normal"]["outcome_bands"]["partial_recovery"]["probability"]["value"] = 0.14
    with pytest.raises(ValueError, match="outcome probabilities must sum to 1"):
        config_from_dict(data)


def test_configuration_roundtrip_preserves_values(base_config):
    reconstructed = config_from_dict(config_to_dict(base_config))
    assert config_to_dict(reconstructed) == config_to_dict(base_config)


def test_all_inherited_scenarios_validate(repository_root):
    s2a_root_paths = [
        path
        for path in sorted((repository_root / "configs").glob("*.yaml"))
        if path.name
        not in {"calibrated_terminal_v1.yaml", "selection_frontier_v1.yaml"}
    ]
    paths = s2a_root_paths + sorted(
        (repository_root / "configs" / "stress").glob("*.yaml")
    )
    assert all(load_config(path).scenario_name for path in paths)

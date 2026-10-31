"""YAML configuration loading, inheritance, provenance and validation."""

from pathlib import Path
from typing import Any

import yaml

from invariant.core.enums import MacroState
from invariant.core.provenance import Parameter, ProvenanceStatus
from invariant.core.types import (
    OUTCOME_BAND_NAMES,
    FounderWarrantTerms,
    GuaranteeTerms,
    MacroParameters,
    MacroRegimeParameters,
    OutcomeBandParameters,
    PortfolioParameters,
    SimulationConfig,
)


def _parameter(data: dict[str, Any]) -> Parameter[Any]:
    return Parameter.from_dict(data)


def _probability(parameter: Parameter[float], label: str) -> None:
    if not 0 <= float(parameter.value) <= 1:
        raise ValueError(f"{label} must be in [0, 1]")


def _non_negative(parameter: Parameter[float], label: str) -> None:
    if float(parameter.value) < 0:
        raise ValueError(f"{label} must be non-negative")


def _require_scenario(parameter: Parameter[Any], label: str) -> None:
    if parameter.status is not ProvenanceStatus.SCENARIO:
        raise ValueError(f"{label} must remain explicitly SCENARIO in S2a")


def _outcome_band(name: str, data: dict[str, Any]) -> OutcomeBandParameters:
    band = OutcomeBandParameters(
        probability=_parameter(data["probability"]),
        minimum_return_multiple=_parameter(data["minimum_return_multiple"]),
        maximum_return_multiple=_parameter(data["maximum_return_multiple"]),
    )
    _probability(band.probability, f"{name}.probability")
    _non_negative(band.minimum_return_multiple, f"{name}.minimum_return_multiple")
    _non_negative(band.maximum_return_multiple, f"{name}.maximum_return_multiple")
    if float(band.minimum_return_multiple.value) > float(band.maximum_return_multiple.value):
        raise ValueError(f"{name} minimum return multiple cannot exceed maximum")
    for field_name in band.__dataclass_fields__:
        _require_scenario(getattr(band, field_name), f"{name}.{field_name}")
    return band


def _validate_band_boundaries(bands: dict[str, OutcomeBandParameters]) -> None:
    bounds = {
        name: (
            float(band.minimum_return_multiple.value),
            float(band.maximum_return_multiple.value),
        )
        for name, band in bands.items()
    }
    if bounds["total_failure"] != (0.0, 0.0):
        raise ValueError("total_failure must be exactly 0x")
    if not 0 <= bounds["partial_recovery"][0] <= bounds["partial_recovery"][1] <= 1:
        raise ValueError("partial_recovery must lie in [0x, 1x]")
    if not 1 <= bounds["modest_success"][0] <= bounds["modest_success"][1] <= 5:
        raise ValueError("modest_success must lie in [1x, 5x]")
    if not 5 <= bounds["large_success"][0] <= bounds["large_success"][1] <= 20:
        raise ValueError("large_success must lie in [5x, 20x]")
    if bounds["extreme_winner"][0] <= 20:
        raise ValueError("extreme_winner minimum must exceed 20x")


def _regime(state: MacroState, data: dict[str, Any]) -> MacroRegimeParameters:
    raw_bands = data["outcome_bands"]
    if set(raw_bands) != set(OUTCOME_BAND_NAMES):
        raise ValueError(
            f"macro.regimes.{state.value}.outcome_bands must define {OUTCOME_BAND_NAMES}"
        )
    bands = {name: _outcome_band(f"{state.value}.{name}", raw_bands[name]) for name in OUTCOME_BAND_NAMES}
    probability_total = sum(float(band.probability.value) for band in bands.values())
    if abs(probability_total - 1.0) > 1e-9:
        raise ValueError(f"{state.value} outcome probabilities must sum to 1")
    _validate_band_boundaries(bands)
    result = MacroRegimeParameters(
        outcome_bands=bands,
        follow_on_probability=_parameter(data["follow_on_probability"]),
        exit_probability=_parameter(data["exit_probability"]),
    )
    _probability(result.follow_on_probability, f"{state.value}.follow_on_probability")
    _probability(result.exit_probability, f"{state.value}.exit_probability")
    return result


def config_from_dict(data: dict[str, Any]) -> SimulationConfig:
    """Build and validate a typed config from a canonical mapping."""

    macro_data = data["macro"]
    state_probabilities = {
        MacroState(state): _parameter(spec)
        for state, spec in macro_data["initial_state_probabilities"].items()
    }
    if set(state_probabilities) != set(MacroState):
        raise ValueError("macro.initial_state_probabilities must define every MacroState")
    for state, parameter in state_probabilities.items():
        _probability(parameter, f"macro.initial_state_probabilities.{state.value}")
        _require_scenario(parameter, f"macro.initial_state_probabilities.{state.value}")
    if abs(sum(float(value.value) for value in state_probabilities.values()) - 1.0) > 1e-9:
        raise ValueError("macro.initial_state_probabilities must sum to 1")

    regimes = {
        MacroState(state): _regime(MacroState(state), spec)
        for state, spec in macro_data["regimes"].items()
    }
    if set(regimes) != set(MacroState):
        raise ValueError("macro.regimes must define every MacroState")

    portfolio_data = data["portfolio"]
    portfolio = PortfolioParameters(
        portfolio_sizes=tuple(int(size) for size in portfolio_data["portfolio_sizes"]),
        baseline_portfolio_size=int(portfolio_data["baseline_portfolio_size"]),
        equal_weighted=bool(portfolio_data.get("equal_weighted", True)),
    )
    required_sizes = {1, 10, 50, 100, 250, 500, 1000, 2500}
    if not required_sizes.issubset(portfolio.portfolio_sizes):
        raise ValueError(f"portfolio_sizes must include {sorted(required_sizes)}")
    if len(set(portfolio.portfolio_sizes)) != len(portfolio.portfolio_sizes):
        raise ValueError("portfolio_sizes cannot contain duplicates")
    if any(size <= 0 for size in portfolio.portfolio_sizes):
        raise ValueError("portfolio_sizes must be positive")
    if portfolio.baseline_portfolio_size not in portfolio.portfolio_sizes:
        raise ValueError("baseline_portfolio_size must be included in portfolio_sizes")
    if not portfolio.equal_weighted:
        raise ValueError("S2a supports equal-weighted portfolios only")

    guarantee_data = data["guarantee"]
    protection_fractions = tuple(
        _parameter(spec) for spec in guarantee_data["protection_fractions"]
    )
    for index, parameter in enumerate(protection_fractions):
        _probability(parameter, f"guarantee.protection_fractions[{index}]")
        _require_scenario(parameter, f"guarantee.protection_fractions[{index}]")
    required_protections = {0.0, 0.25, 0.50, 0.75, 1.0}
    protection_values = {float(parameter.value) for parameter in protection_fractions}
    if not required_protections.issubset(protection_values):
        raise ValueError(f"protection_fractions must include {sorted(required_protections)}")
    baseline_protection = _parameter(guarantee_data["baseline_protection_fraction"])
    _probability(baseline_protection, "guarantee.baseline_protection_fraction")
    _require_scenario(baseline_protection, "guarantee.baseline_protection_fraction")
    if float(baseline_protection.value) not in protection_values:
        raise ValueError("baseline_protection_fraction must be in protection_fractions")
    guarantee = GuaranteeTerms(
        protection_fractions=protection_fractions,
        baseline_protection_fraction=baseline_protection,
        stop_loss_attachment_fraction=_parameter(
            guarantee_data["stop_loss_attachment_fraction"]
        ),
        stop_loss_limit_fraction=_parameter(guarantee_data["stop_loss_limit_fraction"]),
    )
    _non_negative(guarantee.stop_loss_attachment_fraction, "stop_loss attachment")
    _non_negative(guarantee.stop_loss_limit_fraction, "stop_loss limit")

    warrant_data = data["founder_warrant"]
    warrant = FounderWarrantTerms(
        initial_warrant_percentage=_parameter(warrant_data["initial_warrant_percentage"]),
        number_of_financing_rounds=_parameter(warrant_data["number_of_financing_rounds"]),
        dilution_percentage_per_round=_parameter(
            warrant_data["dilution_percentage_per_round"]
        ),
    )
    _probability(warrant.initial_warrant_percentage, "initial_warrant_percentage")
    _probability(warrant.dilution_percentage_per_round, "dilution_percentage_per_round")
    if int(warrant.number_of_financing_rounds.value) < 0:
        raise ValueError("number_of_financing_rounds must be non-negative")
    for field_name in warrant.__dataclass_fields__:
        _require_scenario(getattr(warrant, field_name), f"founder_warrant.{field_name}")

    config = SimulationConfig(
        model_version=str(data["model_version"]),
        scenario_name=str(data["scenario_name"]),
        scenario_description=str(data.get("description", "")),
        assumption_status=str(data["assumption_status"]),
        initial_principal=_parameter(data["initial_principal"]),
        horizon_years=int(data["horizon_years"]),
        number_of_simulations=int(data["number_of_simulations"]),
        random_seed=int(data["random_seed"]),
        portfolio_parameters=portfolio,
        macro_parameters=MacroParameters(state_probabilities, regimes),
        guarantee_terms=guarantee,
        founder_warrant_terms=warrant,
    )
    if float(config.initial_principal.value) <= 0:
        raise ValueError("initial_principal must be positive")
    if config.assumption_status != "SYNTHETIC_SCENARIO":
        raise ValueError("S2a assumption_status must be SYNTHETIC_SCENARIO")
    if config.horizon_years <= 0 or config.number_of_simulations <= 0:
        raise ValueError("horizon_years and number_of_simulations must be positive")
    return config


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if key == "extends":
            continue
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(path: str | Path) -> SimulationConfig:
    """Load one YAML config, applying one explicit relative inheritance layer."""

    path = Path(path)
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError("Configuration root must be a mapping")
    if data.get("extends"):
        base_path = path.parent / str(data["extends"])
        with base_path.open(encoding="utf-8") as handle:
            base_data = yaml.safe_load(handle)
        if not isinstance(base_data, dict):
            raise ValueError("Extended configuration root must be a mapping")
        data = _merge(base_data, data)
    return config_from_dict(data)


def config_to_dict(config: SimulationConfig) -> dict[str, Any]:
    """Serialize typed configuration to the canonical YAML shape."""

    def parameter(value: Parameter[Any]) -> dict[str, Any]:
        return value.as_dict()

    def band(value: OutcomeBandParameters) -> dict[str, Any]:
        return {
            field_name: parameter(getattr(value, field_name))
            for field_name in value.__dataclass_fields__
        }

    return {
        "model_version": config.model_version,
        "scenario_name": config.scenario_name,
        "description": config.scenario_description,
        "assumption_status": config.assumption_status,
        "initial_principal": parameter(config.initial_principal),
        "horizon_years": config.horizon_years,
        "number_of_simulations": config.number_of_simulations,
        "random_seed": config.random_seed,
        "portfolio": {
            "portfolio_sizes": list(config.portfolio_parameters.portfolio_sizes),
            "baseline_portfolio_size": config.portfolio_parameters.baseline_portfolio_size,
            "equal_weighted": config.portfolio_parameters.equal_weighted,
        },
        "macro": {
            "initial_state_probabilities": {
                state.value: parameter(value)
                for state, value in config.macro_parameters.initial_state_probabilities.items()
            },
            "regimes": {
                state.value: {
                    "outcome_bands": {
                        name: band(regime.outcome_bands[name])
                        for name in OUTCOME_BAND_NAMES
                    },
                    "follow_on_probability": parameter(regime.follow_on_probability),
                    "exit_probability": parameter(regime.exit_probability),
                }
                for state, regime in config.macro_parameters.regimes.items()
            },
        },
        "guarantee": {
            "protection_fractions": [parameter(value) for value in config.guarantee_terms.protection_fractions],
            "baseline_protection_fraction": parameter(
                config.guarantee_terms.baseline_protection_fraction
            ),
            "stop_loss_attachment_fraction": parameter(
                config.guarantee_terms.stop_loss_attachment_fraction
            ),
            "stop_loss_limit_fraction": parameter(
                config.guarantee_terms.stop_loss_limit_fraction
            ),
        },
        "founder_warrant": {
            "initial_warrant_percentage": parameter(
                config.founder_warrant_terms.initial_warrant_percentage
            ),
            "number_of_financing_rounds": parameter(
                config.founder_warrant_terms.number_of_financing_rounds
            ),
            "dilution_percentage_per_round": parameter(
                config.founder_warrant_terms.dilution_percentage_per_round
            ),
        },
    }


def dump_config(config: SimulationConfig, path: str | Path) -> None:
    """Write canonical YAML including every provenance field."""

    with Path(path).open("w", encoding="utf-8") as handle:
        yaml.safe_dump(config_to_dict(config), handle, sort_keys=False)

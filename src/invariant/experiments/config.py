"""Loading and validation for the S2b-a.1 selection-frontier configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


REQUIRED_ASSUMPTION_FIELDS = {
    "name",
    "value",
    "unit",
    "meaning",
    "provenance",
    "reason",
    "mathematical_role",
    "sensitivity_range",
    "evidence_required",
}


def load_selection_frontier_config(path: str | Path) -> dict[str, Any]:
    """Load and fully validate one canonical selection-frontier YAML mapping."""

    with Path(path).open(encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict):
        raise ValueError("selection-frontier configuration must be a mapping")
    validate_selection_frontier_config(config)
    return config


def validate_selection_frontier_config(config: dict[str, Any]) -> None:
    """Reject incomplete provenance, invalid probability grids, and hidden scope drift."""

    if config.get("assumption_status") != "EMPIRICAL_BASE_WITH_MODEL_RISK_SCENARIOS":
        raise ValueError("selection-frontier assumption status is invalid")
    simulation = config["simulation"]
    if int(simulation["core_paths"]) < 100_000:
        raise ValueError("principal core scenarios require at least 100,000 paths")
    if int(simulation["frontier_discovery_paths"]) <= 0:
        raise ValueError("frontier discovery paths must be positive")
    if int(simulation["batch_size"]) <= 0:
        raise ValueError("batch_size must be positive")
    confidence = tuple(float(value) for value in simulation["confidence_levels"])
    if any(not 0 < value < 1 for value in confidence):
        raise ValueError("confidence levels must lie in (0, 1)")

    portfolio = config["portfolio"]
    required_sizes = {100, 250, 500, 1000, 2000}
    if set(int(value) for value in portfolio["sizes"]) != required_sizes:
        raise ValueError("portfolio sizes must match the S2b-a.1 required grid")
    required_floors = {0.50, 0.75, 0.90, 1.00}
    if set(float(value) for value in portfolio["protection_fractions"]) != required_floors:
        raise ValueError("protection fractions must match the required grid")
    if portfolio.get("equal_weighted") is not True:
        raise ValueError("the first selection-frontier baseline must remain equal weighted")
    if int(portfolio["canonical_reporting_size"]) not in required_sizes:
        raise ValueError("canonical reporting size must be in the portfolio grid")
    if float(portfolio["canonical_reporting_floor"]) not in required_floors:
        raise ValueError("canonical reporting floor must be in the protection grid")
    if not set(float(value) for value in portfolio["surface_protection_fractions"]).issubset(
        required_floors
    ):
        raise ValueError("surface protection fractions must be in the protection grid")
    for name, construction in portfolio["constructions"].items():
        weights = tuple(float(value) for value in construction["sector_weights"])
        if any(value < 0 for value in weights) or abs(sum(weights) - 1.0) > 1e-10:
            raise ValueError(f"{name} sector weights must be non-negative and sum to one")
        _require_scenario_provenance(construction["provenance"], f"portfolio.{name}")

    selections = config["selection"]["target_constraint_scenarios"]
    if [item["name"] for item in selections] != [
        "unselected",
        "weak",
        "moderate",
        "strong",
        "hyper",
        "extreme_hypothesis",
    ]:
        raise ValueError("target-constraint selection levels must retain required ordering")
    for item in selections:
        loss = float(item["probability_below_1x"])
        tail = float(item["probability_ge_10x"])
        if loss < 0 or tail < 0 or loss + tail >= 1:
            raise ValueError("selection targets must form a valid probability partition")
        _require_scenario_provenance(item["provenance"], f"selection.{item['name']}")
    strengths = tuple(float(value) for value in config["selection"]["exponential_tilt"]["strengths"])
    if not strengths or strengths[0] != 0 or any(value < 0 for value in strengths):
        raise ValueError("exponential tilt strengths must begin at zero and be non-negative")

    dependence = config["dependence"]
    for family in (dependence["central"].values(), dependence["levels"].values()):
        for item in family:
            _validate_rho(item)
    for item in dependence["feasibility_path"]:
        _validate_rho(item)
    path_indices = {
        float(item["dependence_index"]) for item in dependence["feasibility_path"]
    }
    if not set(
        float(value) for value in dependence["selection_frontier_indices"].values()
    ).issubset(path_indices):
        raise ValueError("selection frontier indices must lie on the feasibility path")
    if any(
        float(macro) + float(sector) > 1
        for macro in dependence["detailed_macro_grid"]
        for sector in dependence["detailed_sector_grid"]
    ):
        raise ValueError("detailed rho grid contains an invalid macro/sector sum")

    required_tail_names = {
        "unbounded_pareto",
        "capped_500x",
        "capped_1000x",
        "truncated_pareto",
        "no_mega_winner",
    }
    tails = {item["name"]: item for item in config["tail_models"]}
    if set(tails) != required_tail_names:
        raise ValueError("tail model set does not match the required model-risk grid")
    if config["baseline_tail_model"] not in tails:
        raise ValueError("baseline_tail_model is not defined")
    for name, tail in tails.items():
        if float(tail["beta"]) <= 0 or float(tail["threshold"]) <= 0:
            raise ValueError(f"{name} tail beta and threshold must be positive")
        _require_scenario_provenance(tail["provenance"], f"tail_models.{name}")

    economics = config["platform_economics"]
    for acceptance in economics["founder_acceptance_rates"]:
        if not 0 <= float(acceptance) <= 1:
            raise ValueError("founder acceptance rates must lie in [0, 1]")
    for price in economics["external_risk_provider_prices"]:
        if float(price) < 0:
            raise ValueError("external protection prices cannot be negative")
    if economics["valuation"]["provenance"] != "ILLUSTRATIVE_VALUATION_MULTIPLE":
        raise ValueError("valuation multiples must remain explicitly illustrative")

    assumptions = config.get("assumptions")
    if not isinstance(assumptions, dict) or not assumptions:
        raise ValueError("configuration must define a non-empty assumptions register")
    for assumption_id, assumption in assumptions.items():
        missing = REQUIRED_ASSUMPTION_FIELDS - set(assumption)
        if missing:
            raise ValueError(f"{assumption_id} is missing assumption fields {sorted(missing)}")
        provenance = str(assumption["provenance"])
        if provenance in {"OBSERVED", "FITTED", "OBSERVED_RAW", "OBSERVED_AGGREGATE"}:
            raise ValueError(f"scenario assumption {assumption_id} cannot be labelled {provenance}")


def _validate_rho(item: dict[str, Any]) -> None:
    macro = float(item["rho_macro"])
    sector = float(item["rho_sector"])
    if macro < 0 or sector < 0 or macro + sector > 1:
        raise ValueError("rho_macro and rho_sector must be non-negative and sum to at most one")


def _require_scenario_provenance(value: Any, label: str) -> None:
    if str(value) not in {"MODEL_RISK_SCENARIO", "HYPOTHETICAL_SELECTION_SKILL"}:
        raise ValueError(f"{label} must remain explicitly scenario-labelled")

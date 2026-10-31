"""Factories connecting the frozen empirical universe to scenario layers."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from invariant.calibration.constraints import (
    load_empirical_constraints,
    load_source_registry,
)
from invariant.calibration.parameter_models import (
    BodySpec,
    CorrelationSpec,
    EmpiricalMixtureSpec,
    TailSpec,
    calibrate_survival_tail_beta,
    derive_mixture_weights,
)
from invariant.portfolio.factor_model import FactorSpecification
from invariant.selection.models import ExponentialTiltSelection, TargetConstraintSelection


def load_empirical_base(
    config: dict[str, Any], repository_root: Path
) -> tuple[dict[str, Any], dict[str, Any], EmpiricalMixtureSpec]:
    """Load S2b-a evidence and reconstruct its baseline marginal unchanged."""

    registry = load_source_registry(repository_root / config["source_registry_path"])
    constraints = load_empirical_constraints(
        repository_root / config["empirical_constraints_path"], registry
    )
    returns = constraints["investment_return_constraints"]
    beta = calibrate_survival_tail_beta(
        float(returns["above_10x"]["probability"]),
        float(returns["above_50x"]["probability"]),
        10.0,
        50.0,
    )
    tail_config = tail_config_by_name(config, str(config["baseline_tail_model"]))
    configured_beta = float(tail_config["beta"])
    if abs(beta - configured_beta) > 1e-9:
        raise ValueError("selection frontier beta must reproduce the frozen S2b-a calibration")
    spec = EmpiricalMixtureSpec(
        name="s2b_a_frozen_base",
        body=BodySpec(name="log_uniform"),
        tail=_tail_spec(tail_config),
        correlation=CorrelationSpec(name="independent", model="independent"),
        weights=derive_mixture_weights(constraints),
    )
    spec.validate()
    return registry, constraints, spec


def target_selection_marginals(
    config: dict[str, Any], base_spec: EmpiricalMixtureSpec, tail_name: str
) -> dict[str, TargetConstraintSelection]:
    """Construct all target-constraint scenarios for one tail convention."""

    tail_spec = _tail_spec(tail_config_by_name(config, tail_name))
    tail_base = replace(base_spec, name=f"s2b_a_{tail_name}", tail=tail_spec)
    return {
        item["name"]: TargetConstraintSelection(
            name=f"target_{item['name']}_{tail_name}",
            base_spec=tail_base,
            probability_below_1x=float(item["probability_below_1x"]),
            probability_ge_10x=float(item["probability_ge_10x"]),
        )
        for item in config["selection"]["target_constraint_scenarios"]
    }


def exponential_tilt_marginals(
    config: dict[str, Any], base_spec: EmpiricalMixtureSpec
) -> dict[float, ExponentialTiltSelection]:
    """Construct every configured smooth selection tilt."""

    points = int(config["simulation"]["exponential_tilt_quadrature_points"])
    return {
        float(strength): ExponentialTiltSelection(
            name=f"exponential_tilt_s_{float(strength):g}",
            base_spec=base_spec,
            strength=float(strength),
            quadrature_points=points,
        )
        for strength in config["selection"]["exponential_tilt"]["strengths"]
    }


def factor_specification(
    config: dict[str, Any],
    construction_name: str,
    rho_macro: float,
    rho_sector: float,
    *,
    name_suffix: str = "",
    macro_shift: float = 0.0,
    sector_shifts: tuple[float, ...] = (),
) -> FactorSpecification:
    """Map one portfolio construction and dependence pair to the copula spec."""

    construction = config["portfolio"]["constructions"][construction_name]
    all_sectors = tuple(str(value) for value in config["portfolio"]["sectors"])
    weights = tuple(float(value) for value in construction["sector_weights"])
    if construction["portfolio_type"] == "ai_only":
        sectors = (all_sectors[0],)
    else:
        sectors = all_sectors
    specification = FactorSpecification(
        name=(
            f"{construction_name}_macro_{rho_macro:g}_sector_{rho_sector:g}"
            f"{name_suffix}"
        ),
        portfolio_type=str(construction["portfolio_type"]),
        sector_names=sectors,
        sector_weights=weights,
        rho_macro=float(rho_macro),
        rho_sector=float(rho_sector),
        macro_shift=float(macro_shift),
        sector_shifts=sector_shifts,
    )
    specification.validate()
    return specification


def tail_config_by_name(config: dict[str, Any], name: str) -> dict[str, Any]:
    for item in config["tail_models"]:
        if item["name"] == name:
            return item
    raise KeyError(f"unknown tail model {name!r}")


def _tail_spec(item: dict[str, Any]) -> TailSpec:
    return TailSpec(
        name=str(item["name"]),
        survival_tail_exponent_beta=float(item["beta"]),
        threshold_u=float(item["threshold"]),
        cap=None if item.get("cap") is None else float(item["cap"]),
        mode=str(item["mode"]),
    )

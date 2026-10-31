"""Canonical S2b-a.1 selection and portfolio feasibility experiment."""

from __future__ import annotations

import hashlib
import subprocess
from collections import defaultdict
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
from invariant.calibration.parameter_models import EmpiricalMixtureSpec
from invariant.core.contracts import diluted_warrant_fraction
from invariant.economics.platform import (
    COMMERCIAL_PRICE_PROVENANCE,
    PlatformEconomicsInputs,
    TenYearBusinessInputs,
    break_even_issuance,
    illustrative_enterprise_values,
    maximum_external_protection_price,
    minimum_demand_uplift,
    model_platform_economics,
    model_ten_year_business,
    steady_state_contribution_rate,
)
from invariant.experiments.config import load_selection_frontier_config
from invariant.experiments.frontiers import solve_decreasing_frontier, solve_increasing_frontier
from invariant.experiments.model_factory import (
    exponential_tilt_marginals,
    factor_specification,
    load_empirical_base,
    target_selection_marginals,
)
from invariant.experiments.planner import plan_experiments
from invariant.portfolio.factor_model import literal_all_failure_probability_one_factor
from invariant.portfolio.failure_tolerance import (
    effective_portfolio_size,
    failure_tolerance,
)
from invariant.portfolio.simulation import (
    SelectedFactorPortfolioModel,
    build_selected_portfolio_metrics,
    innovation_barbell_returns,
)
from invariant.reporting.artifacts import canonical_hash, file_hash
from invariant.reporting.selection_frontier import write_selection_frontier_artifact
from invariant.selection.models import TargetConstraintSelection, marginal_diagnostics


PRIMARY_CONSTRUCTIONS = (
    "broad_venture",
    "hyper_selected_ai",
    "hyper_selected_frontier",
)


def run_selection_feasibility_frontier(
    config_path: str | Path,
    output_directory: str | Path,
) -> Path:
    """Run the complete staged experiment and write its canonical artifact."""

    config_path = Path(config_path)
    output_directory = Path(output_directory)
    config = load_selection_frontier_config(config_path)
    repository_root = config_path.resolve().parent.parent
    registry, constraints, base_spec = load_empirical_base(config, repository_root)
    plan = plan_experiments(config)
    model = SelectedFactorPortfolioModel(int(config["simulation"]["batch_size"]))
    terminal_warrant_fraction = diluted_warrant_fraction(
        float(config["protection_support"]["founder_warrant"]["initial_fraction"]),
        tuple(
            float(value)
            for value in config["protection_support"]["founder_warrant"][
                "dilution_fractions"
            ]
        ),
    )

    print("[selection-frontier] analytical tables")
    failure_rows = _failure_tolerance_rows(config)
    effective_n_rows = _effective_n_rows(config)
    selection_diagnostics = _selection_diagnostics(config, base_spec)

    print("[selection-frontier] high-path core portfolios")
    core_rows, core_path_results = _run_core(
        config, base_spec, model, terminal_warrant_fraction
    )
    print("[selection-frontier] selection/dependence surfaces")
    surface_rows = _run_selection_dependence_surface(
        config, base_spec, model, terminal_warrant_fraction
    )
    print("[selection-frontier] tail and detailed factor sensitivities")
    tail_rows = _run_tail_sensitivity(
        config, base_spec, model, terminal_warrant_fraction
    )
    detailed_dependence_rows = _run_detailed_dependence_grid(
        config, base_spec, model
    )

    print("[selection-frontier] coarse feasibility frontier discovery")
    discovery_rows = _run_frontier_discovery(config, base_spec, model)
    feasibility_rows = _solve_feasibility_frontiers(config, discovery_rows)
    selection_frontier_rows = _solve_target_selection_frontiers(config, discovery_rows)
    print("[selection-frontier] exponential-tilt selection inversion")
    tilt_discovery_rows, tilt_frontier_rows = _run_tilt_frontiers(
        config, base_spec, model
    )
    print("[selection-frontier] high-path boundary checks and convergence")
    refinement_rows = _run_frontier_refinements(
        config, base_spec, model, feasibility_rows
    )
    convergence_rows = _run_convergence(config, base_spec, model)

    saturation_rows = _portfolio_saturation_rows(config, core_rows)
    comparison = _selection_concentration_comparison(config, core_rows, surface_rows)
    canonical_size = int(config["portfolio"]["canonical_reporting_size"])
    public_sleeve_rows = _public_sleeve_rows(
        config,
        core_path_results["hyper_selected_frontier"][canonical_size].terminal_multiples,
    )
    print("[selection-frontier] hostile risk and commercial stresses")
    stress_rows = _run_stresses(
        config, base_spec, model, terminal_warrant_fraction, core_rows
    )
    business_rows, profit_rows, scoreboard_rows, valuation_rows = _business_outputs(
        config, core_rows
    )

    risk_rows = core_rows + surface_rows + tail_rows
    results: dict[str, Any] = {
        "model_version": config["model_version"],
        "artifact_status": (
            "S2b-a.1 hypothetical selection and feasibility scenarios; not insurance pricing, "
            "commercial validation, or a guarantee."
        ),
        "core_risk_results": core_rows,
        "selection_dependence_results": surface_rows,
        "tail_sensitivity_results": tail_rows,
        "detailed_dependence_discovery": detailed_dependence_rows,
        "frontier_discovery": discovery_rows,
        "feasibility_frontier": feasibility_rows,
        "selection_frontier": selection_frontier_rows,
        "exponential_tilt_discovery": tilt_discovery_rows,
        "exponential_tilt_frontier": tilt_frontier_rows,
        "frontier_refinement_checks": refinement_rows,
        "portfolio_size_saturation": saturation_rows,
        "selection_vs_concentration": comparison,
        "convergence": convergence_rows,
        "selection_marginal_diagnostics": selection_diagnostics,
        "effective_n_diagnostic": effective_n_rows,
        "optional_public_innovation_sleeve": public_sleeve_rows,
        "stress_tests": stress_rows,
        "platform_scoreboard": scoreboard_rows,
        "business_scenario_count": len(business_rows),
        "profit_frontier_count": len(profit_rows),
        "illustrative_valuation_sensitivity": valuation_rows,
    }
    validation = _validation_payload(
        config=config,
        repository_root=repository_root,
        constraints=constraints,
        base_spec=base_spec,
        selection_diagnostics=selection_diagnostics,
        core_rows=core_rows,
        failure_rows=failure_rows,
        convergence_rows=convergence_rows,
        plan=plan,
    )
    return write_selection_frontier_artifact(
        config_path=config_path,
        config=config,
        repository_root=repository_root,
        output_directory=output_directory,
        registry=registry,
        constraints=constraints,
        plan=plan,
        results=results,
        failure_rows=failure_rows,
        surface_rows=surface_rows,
        feasibility_rows=feasibility_rows,
        selection_frontier_rows=selection_frontier_rows + tilt_frontier_rows,
        profit_rows=profit_rows,
        business_rows=business_rows,
        scoreboard_rows=scoreboard_rows,
        valuation_rows=valuation_rows,
        validation=validation,
        risk_rows=risk_rows,
        effective_n_rows=effective_n_rows,
        saturation_rows=saturation_rows,
        comparison=comparison,
    )


def _failure_tolerance_rows(config: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for portfolio_size in config["portfolio"]["sizes"]:
        for protection in config["portfolio"]["protection_fractions"]:
            for survivor in config["portfolio"]["survivor_multiples"]:
                for recovery in config["portfolio"]["failure_recoveries"]:
                    result = failure_tolerance(
                        int(portfolio_size),
                        float(protection),
                        float(survivor),
                        float(recovery),
                    )
                    rows.append(
                        {
                            "portfolio_size": result.portfolio_size,
                            "protection_fraction": result.protection_fraction,
                            "survivor_multiple": result.survivor_multiple,
                            "failure_recovery_multiple": result.failure_recovery_multiple,
                            "maximum_failures": result.maximum_failures,
                            "maximum_failure_percentage": (
                                None
                                if result.maximum_failure_fraction is None
                                else 100.0 * result.maximum_failure_fraction
                            ),
                            "zero_failures_cover_floor": result.zero_failures_cover_floor,
                            "all_failures_cover_floor": result.all_failures_cover_floor,
                        }
                    )
    return rows


def _effective_n_rows(config: dict[str, Any]) -> list[dict[str, Any]]:
    diagnostic = config["dependence"]["equal_correlation_diagnostic"]
    return [
        {
            "actual_portfolio_size": int(size),
            "equal_correlation": float(rho),
            "effective_portfolio_size": effective_portfolio_size(int(size), float(rho)),
            "interpretation": "linear equal-correlation intuition only",
        }
        for size in diagnostic["portfolio_sizes"]
        for rho in diagnostic["rho_values"]
    ]


def _selection_diagnostics(
    config: dict[str, Any], base_spec: EmpiricalMixtureSpec
) -> dict[str, list[dict[str, Any]]]:
    evaluation_points = int(config["simulation"]["marginal_evaluation_points"])
    targets = target_selection_marginals(config, base_spec, config["baseline_tail_model"])
    target_rows = [
        {
            "selection_model": "target_constraint",
            "selection_level": name,
            "provenance": marginal.provenance,
            **marginal_diagnostics(marginal, evaluation_points),
        }
        for name, marginal in targets.items()
    ]
    tilts = exponential_tilt_marginals(config, base_spec)
    tilt_rows = [
        {
            "selection_model": "exponential_tilt",
            "selection_strength": strength,
            "score_function": config["selection"]["exponential_tilt"]["score_function"],
            "provenance": marginal.provenance,
            **marginal_diagnostics(marginal, evaluation_points),
        }
        for strength, marginal in tilts.items()
    ]
    return {"target_constraint": target_rows, "exponential_tilt": tilt_rows}


def _run_core(
    config: dict[str, Any],
    base_spec: EmpiricalMixtureSpec,
    model: SelectedFactorPortfolioModel,
    terminal_warrant_fraction: float,
) -> tuple[list[dict[str, Any]], dict[str, dict[int, Any]]]:
    rows: list[dict[str, Any]] = []
    path_results: dict[str, dict[int, Any]] = {}
    marginal_by_name = target_selection_marginals(
        config, base_spec, config["baseline_tail_model"]
    )
    sizes = tuple(int(value) for value in config["portfolio"]["sizes"])
    for construction_name in PRIMARY_CONSTRUCTIONS:
        construction = config["portfolio"]["constructions"][construction_name]
        selection_level = str(construction["selection_level"])
        dependence = config["dependence"]["central"][construction_name]
        factor = factor_specification(
            config,
            construction_name,
            float(dependence["rho_macro"]),
            float(dependence["rho_sector"]),
            name_suffix="_core",
        )
        simulations = model.simulate_nested(
            marginal_by_name[selection_level],
            factor,
            sizes,
            int(config["simulation"]["core_paths"]),
            int(config["simulation"]["random_seed"]),
        )
        path_results[construction_name] = simulations
        for size, result in simulations.items():
            for floor in config["portfolio"]["protection_fractions"]:
                row = _full_metric_row(
                    config,
                    result,
                    float(floor),
                    terminal_warrant_fraction,
                    {
                        "experiment_tier": "core",
                        "portfolio_construction": construction_name,
                        "portfolio_type": construction["portfolio_type"],
                        "selection_model": "target_constraint",
                        "selection_level": selection_level,
                        "tail_model": config["baseline_tail_model"],
                        "rho_macro": float(dependence["rho_macro"]),
                        "rho_sector": float(dependence["rho_sector"]),
                        "portfolio_size": size,
                        "protection_fraction": float(floor),
                    },
                )
                if construction["portfolio_type"] == "ai_only":
                    probability_zero = marginal_by_name[selection_level].spec.weights.complete_loss
                    row["analytical_literal_all_zero_probability"] = (
                        literal_all_failure_probability_one_factor(
                            probability_zero,
                            size,
                            float(dependence["rho_macro"])
                            + float(dependence["rho_sector"]),
                            int(config["simulation"]["all_failure_quadrature_nodes"]),
                        )
                    )
                rows.append(row)
    return rows, path_results


def _full_metric_row(
    config: dict[str, Any],
    result: Any,
    protection_fraction: float,
    terminal_warrant_fraction: float,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    support = config["protection_support"]
    metrics = build_selected_portfolio_metrics(
        result,
        protection_fraction,
        terminal_warrant_fraction,
        float(support["generic_stop_loss"]["attachment_fraction"]),
        float(support["generic_stop_loss"]["limit_fraction"]),
        tuple(float(value) for value in config["simulation"]["confidence_levels"]),
    )
    return {**metadata, **metrics}


def _run_selection_dependence_surface(
    config: dict[str, Any],
    base_spec: EmpiricalMixtureSpec,
    model: SelectedFactorPortfolioModel,
    terminal_warrant_fraction: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    marginals = target_selection_marginals(
        config, base_spec, config["baseline_tail_model"]
    )
    all_sizes = tuple(int(value) for value in config["portfolio"]["sizes"])
    reporting_size = int(config["portfolio"]["canonical_reporting_size"])
    surface_floors = tuple(
        float(value) for value in config["portfolio"]["surface_protection_fractions"]
    )
    for construction_name in ("hyper_selected_ai", "hyper_selected_frontier"):
        construction = config["portfolio"]["constructions"][construction_name]
        for selection_level, marginal in marginals.items():
            for dependence_level, dependence in config["dependence"]["levels"].items():
                sizes = (
                    all_sizes
                    if construction_name == "hyper_selected_frontier"
                    and dependence_level == "medium"
                    else (reporting_size,)
                )
                factor = factor_specification(
                    config,
                    construction_name,
                    float(dependence["rho_macro"]),
                    float(dependence["rho_sector"]),
                    name_suffix=f"_surface_{selection_level}_{dependence_level}",
                )
                simulations = model.simulate_nested(
                    marginal,
                    factor,
                    sizes,
                    int(config["simulation"]["surface_paths"]),
                    int(config["simulation"]["random_seed"]) + 101,
                )
                for size, result in simulations.items():
                    floors = (
                        config["portfolio"]["protection_fractions"]
                        if len(sizes) > 1
                        else surface_floors
                    )
                    for floor in floors:
                        rows.append(
                            _full_metric_row(
                                config,
                                result,
                                float(floor),
                                terminal_warrant_fraction,
                                {
                                    "experiment_tier": "sensitivity",
                                    "portfolio_construction": construction_name,
                                    "portfolio_type": construction["portfolio_type"],
                                    "selection_model": "target_constraint",
                                    "selection_level": selection_level,
                                    "dependence_level": dependence_level,
                                    "tail_model": config["baseline_tail_model"],
                                    "rho_macro": float(dependence["rho_macro"]),
                                    "rho_sector": float(dependence["rho_sector"]),
                                    "portfolio_size": size,
                                    "protection_fraction": float(floor),
                                },
                            )
                        )
    return rows


def _run_tail_sensitivity(
    config: dict[str, Any],
    base_spec: EmpiricalMixtureSpec,
    model: SelectedFactorPortfolioModel,
    terminal_warrant_fraction: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    reporting_size = int(config["portfolio"]["canonical_reporting_size"])
    surface_floors = tuple(
        float(value) for value in config["portfolio"]["surface_protection_fractions"]
    )
    for construction_name in PRIMARY_CONSTRUCTIONS:
        construction = config["portfolio"]["constructions"][construction_name]
        selection_level = str(construction["selection_level"])
        dependence = config["dependence"]["central"][construction_name]
        factor = factor_specification(
            config,
            construction_name,
            float(dependence["rho_macro"]),
            float(dependence["rho_sector"]),
            name_suffix="_tail_sensitivity",
        )
        for tail in config["tail_models"]:
            marginal = target_selection_marginals(
                config, base_spec, str(tail["name"])
            )[selection_level]
            result = model.simulate(
                marginal,
                factor,
                reporting_size,
                int(config["simulation"]["tail_sensitivity_paths"]),
                int(config["simulation"]["random_seed"]) + 202,
            )
            for floor in surface_floors:
                rows.append(
                    _full_metric_row(
                        config,
                        result,
                        floor,
                        terminal_warrant_fraction,
                        {
                            "experiment_tier": "sensitivity",
                            "portfolio_construction": construction_name,
                            "portfolio_type": construction["portfolio_type"],
                            "selection_model": "target_constraint",
                            "selection_level": selection_level,
                            "tail_model": tail["name"],
                            "rho_macro": float(dependence["rho_macro"]),
                            "rho_sector": float(dependence["rho_sector"]),
                            "portfolio_size": reporting_size,
                            "protection_fraction": floor,
                        },
                    )
                )
    return rows


def _run_detailed_dependence_grid(
    config: dict[str, Any],
    base_spec: EmpiricalMixtureSpec,
    model: SelectedFactorPortfolioModel,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    marginal = target_selection_marginals(
        config, base_spec, config["baseline_tail_model"]
    )["hyper"]
    paths = int(config["simulation"]["frontier_discovery_paths"])
    reporting_size = int(config["portfolio"]["canonical_reporting_size"])
    surface_floors = tuple(
        float(value) for value in config["portfolio"]["surface_protection_fractions"]
    )
    for construction_name in ("hyper_selected_ai", "hyper_selected_frontier"):
        for rho_macro in config["dependence"]["detailed_macro_grid"]:
            for rho_sector in config["dependence"]["detailed_sector_grid"]:
                if float(rho_macro) + float(rho_sector) > 1:
                    continue
                factor = factor_specification(
                    config,
                    construction_name,
                    float(rho_macro),
                    float(rho_sector),
                    name_suffix="_detailed_grid",
                )
                nav = model.simulate_nav_nested(
                    marginal,
                    factor,
                    (reporting_size,),
                    paths,
                    int(config["simulation"]["random_seed"]) + 303,
                    random_stream_name=f"detailed_{construction_name}",
                )[reporting_size]
                for floor in surface_floors:
                    claims = np.maximum(floor - nav, 0.0)
                    rows.append(
                        {
                            "experiment_tier": "discovery",
                            "portfolio_construction": construction_name,
                            "selection_level": "hyper",
                            "portfolio_size": reporting_size,
                            "protection_fraction": floor,
                            "rho_macro": float(rho_macro),
                            "rho_sector": float(rho_sector),
                            "expected_claim_per_unit": float(np.mean(claims)),
                            "probability_claim": float(np.mean(claims > 0)),
                            "number_of_paths": paths,
                        }
                    )
    return rows


def _run_frontier_discovery(
    config: dict[str, Any],
    base_spec: EmpiricalMixtureSpec,
    model: SelectedFactorPortfolioModel,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    paths = int(config["simulation"]["frontier_discovery_paths"])
    seed = int(config["simulation"]["random_seed"]) + 404
    sizes = tuple(int(value) for value in config["portfolio"]["sizes"])
    total = (
        len(PRIMARY_CONSTRUCTIONS)
        * len(config["tail_models"])
        * len(config["selection"]["target_constraint_scenarios"])
        * len(config["dependence"]["feasibility_path"])
    )
    completed = 0
    for construction_name in PRIMARY_CONSTRUCTIONS:
        construction = config["portfolio"]["constructions"][construction_name]
        for tail in config["tail_models"]:
            marginals = target_selection_marginals(config, base_spec, str(tail["name"]))
            for selection_level, marginal in marginals.items():
                stream = f"frontier_{construction_name}_{selection_level}_{tail['name']}"
                for dependence in config["dependence"]["feasibility_path"]:
                    factor = factor_specification(
                        config,
                        construction_name,
                        float(dependence["rho_macro"]),
                        float(dependence["rho_sector"]),
                        name_suffix="_frontier",
                    )
                    nav_by_size = model.simulate_nav_nested(
                        marginal,
                        factor,
                        sizes,
                        paths,
                        seed,
                        random_stream_name=stream,
                    )
                    for size, nav in nav_by_size.items():
                        for floor in config["portfolio"]["protection_fractions"]:
                            claims = np.maximum(float(floor) - nav, 0.0)
                            rows.append(
                                {
                                    "portfolio_construction": construction_name,
                                    "portfolio_type": construction["portfolio_type"],
                                    "selection_level": selection_level,
                                    "tail_model": tail["name"],
                                    "portfolio_size": size,
                                    "protection_fraction": float(floor),
                                    "dependence_index": float(
                                        dependence["dependence_index"]
                                    ),
                                    "rho_macro": float(dependence["rho_macro"]),
                                    "rho_sector": float(dependence["rho_sector"]),
                                    "expected_claim_per_unit": float(np.mean(claims)),
                                    "probability_claim": float(np.mean(claims > 0)),
                                    "number_of_paths": paths,
                                    "estimate_tier": "coarse_discovery",
                                }
                            )
                    completed += 1
                    if completed % 100 == 0 or completed == total:
                        print(f"[selection-frontier] frontier cells {completed}/{total}")
    return rows


def _solve_feasibility_frontiers(
    config: dict[str, Any], discovery_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    fields = (
        "portfolio_construction",
        "portfolio_type",
        "selection_level",
        "tail_model",
        "portfolio_size",
        "protection_fraction",
    )
    for row in discovery_rows:
        groups[tuple(row[field] for field in fields)].append(row)

    output: list[dict[str, Any]] = []
    target_sets = (
        ("expected_claim_per_unit", config["frontiers"]["expected_claim_targets"]),
        ("probability_claim", config["frontiers"]["claim_probability_targets"]),
    )
    for key, rows in groups.items():
        rows.sort(key=lambda row: row["dependence_index"])
        grid = tuple(float(row["dependence_index"]) for row in rows)
        for metric, targets in target_sets:
            values = tuple(float(row[metric]) for row in rows)
            for target in targets:
                solution = solve_increasing_frontier(grid, values, float(target))
                rho_macro, rho_sector = _interpolate_factor_pair(
                    config,
                    solution.boundary,
                )
                output.append(
                    {
                        **dict(zip(fields, key, strict=True)),
                        "frontier_metric": metric,
                        "target": float(target),
                        "dependence_index_boundary": solution.boundary,
                        "rho_macro_boundary": rho_macro,
                        "rho_sector_boundary": rho_sector,
                        "status": solution.status,
                        "lower_grid_value": solution.lower_grid_value,
                        "upper_grid_value": solution.upper_grid_value,
                        "estimate_tier": "monotone_interpolation_of_coarse_discovery",
                    }
                )
    return output


def _solve_target_selection_frontiers(
    config: dict[str, Any], discovery_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    scenario_items = config["selection"]["target_constraint_scenarios"]
    selection_names = tuple(str(item["name"]) for item in scenario_items)
    skill_grid = tuple(float(index) for index in range(len(selection_names)))
    selection_lookup = {item["name"]: item for item in scenario_items}
    named_dependence = {
        str(name): float(value)
        for name, value in config["dependence"]["selection_frontier_indices"].items()
    }
    lookup: dict[tuple[Any, ...], dict[str, float]] = defaultdict(dict)
    for row in discovery_rows:
        if row["tail_model"] != config["baseline_tail_model"]:
            continue
        for level, index in named_dependence.items():
            if abs(float(row["dependence_index"]) - index) < 1e-12:
                key = (
                    row["portfolio_construction"],
                    row["portfolio_type"],
                    row["portfolio_size"],
                    row["protection_fraction"],
                    level,
                )
                lookup[key][str(row["selection_level"])] = float(
                    row["expected_claim_per_unit"]
                )

    output: list[dict[str, Any]] = []
    for key, by_selection in lookup.items():
        if set(by_selection) != set(selection_names):
            continue
        values = tuple(by_selection[name] for name in selection_names)
        for target in config["frontiers"]["selection_expected_claim_targets"]:
            solution = solve_decreasing_frontier(skill_grid, values, float(target))
            required_loss, required_tail = _interpolate_selection_targets(
                scenario_items,
                solution.boundary,
            )
            output.append(
                {
                    "selection_model": "target_constraint",
                    "portfolio_construction": key[0],
                    "portfolio_type": key[1],
                    "portfolio_size": key[2],
                    "protection_fraction": key[3],
                    "dependence_level": key[4],
                    "target_expected_claim_per_unit": float(target),
                    "required_selection_index": solution.boundary,
                    "required_probability_below_1x": required_loss,
                    "required_probability_ge_10x": required_tail,
                    "required_tilt_strength": None,
                    "status": solution.status,
                    "provenance": "HYPOTHETICAL_SELECTION_SKILL",
                }
            )
    return output


def _run_tilt_frontiers(
    config: dict[str, Any],
    base_spec: EmpiricalMixtureSpec,
    model: SelectedFactorPortfolioModel,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    tilts = exponential_tilt_marginals(config, base_spec)
    strengths = tuple(sorted(tilts))
    sizes = tuple(int(value) for value in config["portfolio"]["sizes"])
    paths = int(config["simulation"]["frontier_discovery_paths"])
    raw_rows: list[dict[str, Any]] = []
    for construction_name in PRIMARY_CONSTRUCTIONS:
        construction = config["portfolio"]["constructions"][construction_name]
        for dependence_level, dependence in config["dependence"]["levels"].items():
            factor = factor_specification(
                config,
                construction_name,
                float(dependence["rho_macro"]),
                float(dependence["rho_sector"]),
                name_suffix="_tilt_frontier",
            )
            for strength, marginal in tilts.items():
                nav_by_size = model.simulate_nav_nested(
                    marginal,
                    factor,
                    sizes,
                    paths,
                    int(config["simulation"]["random_seed"]) + 505,
                    random_stream_name=f"tilt_{construction_name}_{dependence_level}",
                )
                for size, nav in nav_by_size.items():
                    for floor in config["portfolio"]["protection_fractions"]:
                        claims = np.maximum(float(floor) - nav, 0.0)
                        raw_rows.append(
                            {
                                "portfolio_construction": construction_name,
                                "portfolio_type": construction["portfolio_type"],
                                "portfolio_size": size,
                                "protection_fraction": float(floor),
                                "dependence_level": dependence_level,
                                "rho_macro": float(dependence["rho_macro"]),
                                "rho_sector": float(dependence["rho_sector"]),
                                "selection_strength": strength,
                                "expected_claim_per_unit": float(np.mean(claims)),
                                "probability_claim": float(np.mean(claims > 0)),
                                "number_of_paths": paths,
                            }
                        )

    groups: dict[tuple[Any, ...], dict[float, float]] = defaultdict(dict)
    for row in raw_rows:
        key = (
            row["portfolio_construction"],
            row["portfolio_type"],
            row["portfolio_size"],
            row["protection_fraction"],
            row["dependence_level"],
        )
        groups[key][float(row["selection_strength"])] = float(
            row["expected_claim_per_unit"]
        )
    frontier_rows: list[dict[str, Any]] = []
    for key, by_strength in groups.items():
        values = tuple(by_strength[strength] for strength in strengths)
        for target in config["frontiers"]["selection_expected_claim_targets"]:
            solution = solve_decreasing_frontier(strengths, values, float(target))
            frontier_rows.append(
                {
                    "selection_model": "exponential_tilt",
                    "portfolio_construction": key[0],
                    "portfolio_type": key[1],
                    "portfolio_size": key[2],
                    "protection_fraction": key[3],
                    "dependence_level": key[4],
                    "target_expected_claim_per_unit": float(target),
                    "required_selection_index": None,
                    "required_probability_below_1x": None,
                    "required_probability_ge_10x": None,
                    "required_tilt_strength": solution.boundary,
                    "status": solution.status,
                    "provenance": "HYPOTHETICAL_SELECTION_SKILL",
                }
            )
    return raw_rows, frontier_rows


def _run_frontier_refinements(
    config: dict[str, Any],
    base_spec: EmpiricalMixtureSpec,
    model: SelectedFactorPortfolioModel,
    feasibility_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    reporting_size = int(config["portfolio"]["canonical_reporting_size"])
    reporting_floor = float(config["portfolio"]["canonical_reporting_floor"])
    refinement_target = float(
        config["frontiers"]["canonical_refinement_expected_claim_target"]
    )
    refinement_sizes = tuple(
        int(value) for value in config["frontiers"]["refinement_portfolio_sizes"]
    )
    refinement_floors = tuple(
        float(value)
        for value in config["frontiers"]["refinement_protection_fractions"]
    )
    for construction_name in PRIMARY_CONSTRUCTIONS:
        selection_level = str(
            config["portfolio"]["constructions"][construction_name]["selection_level"]
        )
        candidate = next(
            (
                row
                for row in feasibility_rows
                if row["portfolio_construction"] == construction_name
                and row["selection_level"] == selection_level
                and row["tail_model"] == config["baseline_tail_model"]
                and row["portfolio_size"] == reporting_size
                and row["protection_fraction"] == reporting_floor
                and row["frontier_metric"] == "expected_claim_per_unit"
                and row["target"] == refinement_target
                and row["dependence_index_boundary"] is not None
            ),
            None,
        )
        if candidate is None:
            continue
        marginal = target_selection_marginals(
            config, base_spec, config["baseline_tail_model"]
        )[selection_level]
        factor = factor_specification(
            config,
            construction_name,
            float(candidate["rho_macro_boundary"]),
            float(candidate["rho_sector_boundary"]),
            name_suffix="_refined_boundary",
        )
        nav = model.simulate_nav_nested(
            marginal,
            factor,
            refinement_sizes,
            int(config["simulation"]["frontier_refinement_paths"]),
            int(config["simulation"]["random_seed"]) + 606,
            random_stream_name=f"refine_{construction_name}_{selection_level}",
        )
        for size, values in nav.items():
            for floor in refinement_floors:
                claims = np.maximum(floor - values, 0.0)
                rows.append(
                    {
                        "portfolio_construction": construction_name,
                        "selection_level": selection_level,
                        "tail_model": config["baseline_tail_model"],
                        "portfolio_size": size,
                        "protection_fraction": floor,
                        "dependence_index": candidate["dependence_index_boundary"],
                        "rho_macro": candidate["rho_macro_boundary"],
                        "rho_sector": candidate["rho_sector_boundary"],
                        "target_used_for_location": refinement_target,
                        "expected_claim_per_unit": float(np.mean(claims)),
                        "probability_claim": float(np.mean(claims > 0)),
                        "number_of_paths": int(
                            config["simulation"]["frontier_refinement_paths"]
                        ),
                        "estimate_tier": "high_path_boundary_check",
                    }
                )
    return rows


def _run_convergence(
    config: dict[str, Any],
    base_spec: EmpiricalMixtureSpec,
    model: SelectedFactorPortfolioModel,
) -> list[dict[str, Any]]:
    reporting_size = int(config["portfolio"]["canonical_reporting_size"])
    reporting_floor = float(config["portfolio"]["canonical_reporting_floor"])
    marginal = target_selection_marginals(
        config, base_spec, config["baseline_tail_model"]
    )["hyper"]
    dependence = config["dependence"]["central"]["hyper_selected_frontier"]
    factor = factor_specification(
        config,
        "hyper_selected_frontier",
        float(dependence["rho_macro"]),
        float(dependence["rho_sector"]),
        name_suffix="_convergence",
    )
    rows: list[dict[str, Any]] = []
    for paths in config["simulation"]["convergence_path_counts"]:
        result = model.simulate(
            marginal,
            factor,
            reporting_size,
            int(paths),
            int(config["simulation"]["random_seed"]) + 707,
        )
        metrics = build_selected_portfolio_metrics(
            result,
            reporting_floor,
            0.0,
            0.0,
            0.0,
            (0.995,),
        )
        rows.append(
            {
                "number_of_paths": int(paths),
                "expected_claim_per_unit": metrics["expected_claim_per_unit"],
                "probability_claim": metrics["probability_claim"],
                "claim_es_99.5_per_unit": metrics["claim_es_99.5_per_unit"],
                "claim_es_99.5_tail_observations": metrics[
                    "claim_es_99.5_tail_observations"
                ],
                "claim_es_99.5_mc_standard_error": metrics[
                    "claim_es_99.5_mc_standard_error"
                ],
            }
        )
    return rows


def _portfolio_saturation_rows(
    config: dict[str, Any], core_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    threshold = float(
        config["frontiers"]["material_saturation_threshold_per_100_companies"]
    )
    for construction in PRIMARY_CONSTRUCTIONS:
        for floor in config["portfolio"]["protection_fractions"]:
            rows = sorted(
                (
                    row
                    for row in core_rows
                    if row["portfolio_construction"] == construction
                    and row["protection_fraction"] == float(floor)
                ),
                key=lambda row: row["portfolio_size"],
            )
            for before, after in zip(rows, rows[1:]):
                additional = int(after["portfolio_size"]) - int(before["portfolio_size"])
                expected_benefit = float(before["expected_claim_per_unit"]) - float(
                    after["expected_claim_per_unit"]
                )
                es_benefit = float(before["claim_es_99.5_per_unit"]) - float(
                    after["claim_es_99.5_per_unit"]
                )
                probability_benefit = float(before["probability_claim"]) - float(
                    after["probability_claim"]
                )
                per_100 = expected_benefit / (additional / 100.0)
                output.append(
                    {
                        "portfolio_construction": construction,
                        "protection_fraction": float(floor),
                        "from_portfolio_size": int(before["portfolio_size"]),
                        "to_portfolio_size": int(after["portfolio_size"]),
                        "delta_expected_claim_per_unit": -expected_benefit,
                        "delta_es_99.5_per_unit": -es_benefit,
                        "delta_probability_claim": -probability_benefit,
                        "protection_benefit_per_additional_100_companies": per_100,
                        "absolute_benefit_below_materiality_threshold": abs(per_100)
                        < threshold,
                    }
                )
    return output


def _selection_concentration_comparison(
    config: dict[str, Any],
    core_rows: list[dict[str, Any]],
    surface_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    reporting_size = int(config["portfolio"]["canonical_reporting_size"])
    for floor in config["portfolio"]["surface_protection_fractions"]:
        floor = float(floor)
        ai_unselected = _find_metric_row(
            surface_rows,
            portfolio_construction="hyper_selected_ai",
            selection_level="unselected",
            dependence_level="medium",
            portfolio_size=reporting_size,
            protection_fraction=floor,
        )
        ai_hyper = _find_metric_row(
            surface_rows,
            portfolio_construction="hyper_selected_ai",
            selection_level="hyper",
            dependence_level="medium",
            portfolio_size=reporting_size,
            protection_fraction=floor,
        )
        frontier_hyper = _find_metric_row(
            surface_rows,
            portfolio_construction="hyper_selected_frontier",
            selection_level="hyper",
            dependence_level="medium",
            portfolio_size=reporting_size,
            protection_fraction=floor,
        )
        broad_core = _find_metric_row(
            core_rows,
            portfolio_construction="broad_venture",
            portfolio_size=reporting_size,
            protection_fraction=floor,
        )
        ai_core = _find_metric_row(
            core_rows,
            portfolio_construction="hyper_selected_ai",
            portfolio_size=reporting_size,
            protection_fraction=floor,
        )
        frontier_core = _find_metric_row(
            core_rows,
            portfolio_construction="hyper_selected_frontier",
            portfolio_size=reporting_size,
            protection_fraction=floor,
        )
        output.append(
            {
                "portfolio_size": reporting_size,
                "protection_fraction": floor,
                "selection_risk_reduction_ai_medium": float(
                    ai_unselected["expected_claim_per_unit"]
                )
                - float(ai_hyper["expected_claim_per_unit"]),
                "ai_concentration_penalty_vs_frontier_medium": float(
                    ai_hyper["expected_claim_per_unit"]
                )
                - float(frontier_hyper["expected_claim_per_unit"]),
                "net_hyper_ai_vs_broad_core": float(
                    ai_core["expected_claim_per_unit"]
                )
                - float(broad_core["expected_claim_per_unit"]),
                "net_hyper_frontier_vs_broad_core": float(
                    frontier_core["expected_claim_per_unit"]
                )
                - float(broad_core["expected_claim_per_unit"]),
                "interpretation": (
                    "Negative net values mean the selected portfolio has lower expected claim; "
                    "positive concentration penalty means AI-only is worse than frontier at held rho."
                ),
            }
        )
    return output


def _public_sleeve_rows(
    config: dict[str, Any], venture_returns: np.ndarray
) -> list[dict[str, Any]]:
    sleeve = config["public_innovation_sleeve"]
    probabilities = np.asarray(sleeve["outcome_probabilities"], dtype=float)
    if abs(float(probabilities.sum()) - 1.0) > 1e-10:
        raise ValueError("public sleeve probabilities must sum to one")
    rng = np.random.default_rng(int(config["simulation"]["random_seed"]) + 808)
    public_returns = rng.choice(
        np.asarray(sleeve["outcome_multiples"], dtype=float),
        size=len(venture_returns),
        p=probabilities,
    )
    rows: list[dict[str, Any]] = []
    for allocation in sleeve["allocations"]:
        combined = innovation_barbell_returns(
            venture_returns,
            public_returns,
            float(allocation),
        )
        for floor in config["portfolio"]["protection_fractions"]:
            claims = np.maximum(float(floor) - combined, 0.0)
            rows.append(
                {
                    "architecture": "innovation_barbell",
                    "public_allocation": float(allocation),
                    "venture_allocation": 1.0 - float(allocation),
                    "protection_fraction": float(floor),
                    "expected_portfolio_multiple": float(np.mean(combined)),
                    "expected_claim_per_unit": float(np.mean(claims)),
                    "probability_claim": float(np.mean(claims > 0)),
                    "provenance": sleeve["provenance"],
                    "isolation_note": sleeve["interpretation"],
                }
            )
    return rows


def _run_stresses(
    config: dict[str, Any],
    base_spec: EmpiricalMixtureSpec,
    model: SelectedFactorPortfolioModel,
    terminal_warrant_fraction: float,
    core_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    paths = int(config["simulation"]["stress_paths"])
    seed = int(config["simulation"]["random_seed"]) + 909
    reporting_size = int(config["portfolio"]["canonical_reporting_size"])
    reporting_floor = float(config["portfolio"]["canonical_reporting_floor"])
    surface_floors = tuple(
        float(value) for value in config["portfolio"]["surface_protection_fractions"]
    )
    stress_parameters = config["stress_parameters"]
    factor_shift = float(stress_parameters["adverse_factor_shift_standard_deviations"])
    baseline_tail = str(config["baseline_tail_model"])
    baseline_marginals = target_selection_marginals(config, base_spec, baseline_tail)
    no_mega = target_selection_marginals(config, base_spec, "no_mega_winner")["hyper"]
    beta_stress_spec = replace(
        base_spec,
        name="tail_beta_1_60_stress",
        tail=replace(
            base_spec.tail,
            name="tail_beta_1_60_stress",
            survival_tail_exponent_beta=float(
                stress_parameters["worsened_tail_exponent_beta"]
            ),
        ),
    )
    beta_stress = TargetConstraintSelection(
        name="hyper_tail_beta_1_60_stress",
        base_spec=beta_stress_spec,
        probability_below_1x=0.45,
        probability_ge_10x=0.10,
    )
    ai_dependence = config["dependence"]["central"]["hyper_selected_ai"]
    frontier_dependence = config["dependence"]["central"]["hyper_selected_frontier"]
    zero_frontier_shifts = tuple(0.0 for _ in config["portfolio"]["sectors"])
    energy_shifts = list(zero_frontier_shifts)
    energy_index = list(config["portfolio"]["sectors"]).index("energy / grid")
    energy_shifts[energy_index] = factor_shift
    scenarios = [
        (
            "frontier_concentration_stress",
            baseline_marginals["hyper"],
            factor_specification(
                config,
                "frontier_concentration_stress",
                float(frontier_dependence["rho_macro"]),
                float(frontier_dependence["rho_sector"]),
                name_suffix="_concentration_stress",
            ),
        ),
        (
            "no_mega_winner",
            no_mega,
            factor_specification(
                config,
                "hyper_selected_ai",
                float(ai_dependence["rho_macro"]),
                float(ai_dependence["rho_sector"]),
                name_suffix="_no_mega",
            ),
        ),
        (
            "zero_ge_50x",
            no_mega,
            factor_specification(
                config,
                "hyper_selected_ai",
                float(ai_dependence["rho_macro"]),
                float(ai_dependence["rho_sector"]),
                name_suffix="_zero_ge50",
            ),
        ),
        (
            "tail_exponent_worsens",
            beta_stress,
            factor_specification(
                config,
                "hyper_selected_ai",
                float(ai_dependence["rho_macro"]),
                float(ai_dependence["rho_sector"]),
                name_suffix="_beta_stress",
            ),
        ),
        (
            "ai_sector_shock",
            baseline_marginals["hyper"],
            factor_specification(
                config,
                "hyper_selected_ai",
                float(ai_dependence["rho_macro"]),
                float(ai_dependence["rho_sector"]),
                name_suffix="_ai_shock",
                sector_shifts=(factor_shift,),
            ),
        ),
        (
            "macro_recession",
            baseline_marginals["hyper"],
            factor_specification(
                config,
                "hyper_selected_frontier",
                float(frontier_dependence["rho_macro"]),
                float(frontier_dependence["rho_sector"]),
                name_suffix="_macro_recession",
                macro_shift=factor_shift,
            ),
        ),
        (
            "ai_macro_joint_shock",
            baseline_marginals["hyper"],
            factor_specification(
                config,
                "hyper_selected_ai",
                float(ai_dependence["rho_macro"]),
                float(ai_dependence["rho_sector"]),
                name_suffix="_joint_shock",
                macro_shift=factor_shift,
                sector_shifts=(factor_shift,),
            ),
        ),
        (
            "energy_shock",
            baseline_marginals["hyper"],
            factor_specification(
                config,
                "hyper_selected_frontier",
                float(frontier_dependence["rho_macro"]),
                float(frontier_dependence["rho_sector"]),
                name_suffix="_energy_shock",
                sector_shifts=tuple(energy_shifts),
            ),
        ),
        (
            "sector_correlation_doubles",
            baseline_marginals["hyper"],
            factor_specification(
                config,
                "hyper_selected_frontier",
                float(frontier_dependence["rho_macro"]),
                min(
                    2.0 * float(frontier_dependence["rho_sector"]),
                    1.0 - float(frontier_dependence["rho_macro"]),
                ),
                name_suffix="_sector_rho_double",
            ),
        ),
        (
            "selection_skill_disappears",
            baseline_marginals["unselected"],
            factor_specification(
                config,
                "hyper_selected_ai",
                float(ai_dependence["rho_macro"]),
                float(ai_dependence["rho_sector"]),
                name_suffix="_selection_disappears",
            ),
        ),
        (
            "selected_reverts_to_population",
            baseline_marginals["unselected"],
            factor_specification(
                config,
                "hyper_selected_frontier",
                float(frontier_dependence["rho_macro"]),
                float(frontier_dependence["rho_sector"]),
                name_suffix="_population_reversion",
            ),
        ),
    ]
    rows: list[dict[str, Any]] = []
    for name, marginal, factor in scenarios:
        result = model.simulate(marginal, factor, reporting_size, paths, seed)
        for floor in surface_floors:
            rows.append(
                _full_metric_row(
                    config,
                    result,
                    floor,
                    terminal_warrant_fraction,
                    {
                        "stress_name": name,
                        "domain": "risk",
                        "portfolio_type": factor.portfolio_type,
                        "portfolio_size": reporting_size,
                        "protection_fraction": floor,
                        "rho_macro": factor.rho_macro,
                        "rho_sector": factor.rho_sector,
                        "provenance": "MODEL_RISK_SCENARIO",
                    },
                )
            )

    baseline = _find_metric_row(
        core_rows,
        portfolio_construction="hyper_selected_frontier",
        portfolio_size=reporting_size,
        protection_fraction=reporting_floor,
    )
    rows.append(
        {
            "stress_name": "funding_liquidity_freeze",
            "domain": "liquidity",
            "expected_claim_per_unit": baseline["expected_claim_per_unit"],
            "probability_claim": baseline["probability_claim"],
            "generic_stop_loss_available": False,
            "liquidity_shortfall_not_identified": True,
            "interpretation": (
                "The terminal floor claim is unchanged; settlement liquidity is a distinct, "
                "currently uncalibrated event."
            ),
            "provenance": "MODEL_RISK_SCENARIO",
        }
    )
    rows.extend(_commercial_stress_rows(config, baseline))
    return rows


def _business_outputs(
    config: dict[str, Any], core_rows: list[dict[str, Any]]
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    economics = config["platform_economics"]
    canonical = economics["canonical"]
    maturity = float(economics["ten_year"]["maturity_years"])
    reporting_size = int(config["portfolio"]["canonical_reporting_size"])
    reporting_floor = float(config["portfolio"]["canonical_reporting_floor"])
    frontier_risk = _find_metric_row(
        core_rows,
        portfolio_construction="hyper_selected_frontier",
        portfolio_size=reporting_size,
        protection_fraction=reporting_floor,
    )
    q = float(frontier_risk["expected_founder_warrant_value_per_unit"])
    business_rows: list[dict[str, Any]] = []

    for issuance in economics["annual_new_protected_capital"]:
        business_rows.append(
            _period_business_row(
                config,
                "protected_issuance",
                float(issuance),
                q,
            )
        )
    for price in economics["external_risk_provider_prices"]:
        business_rows.append(
            _period_business_row(
                config,
                "external_protection_price",
                float(canonical["annual_new_protected_capital"]),
                q,
                external_price=float(price),
            )
        )
    base_demand = float(economics["ten_year"]["base_annual_unprotected_demand"])
    for uplift in economics["demand_uplifts"]:
        issuance = base_demand * float(uplift) * float(canonical["founder_acceptance_rate"])
        business_rows.append(
            _period_business_row(
                config,
                "investor_demand_uplift",
                issuance,
                q,
                demand_uplift=float(uplift),
            )
        )
    for acceptance in economics["founder_acceptance_rates"]:
        issuance = base_demand * float(canonical["demand_uplift"]) * float(acceptance)
        business_rows.append(
            _period_business_row(
                config,
                "founder_acceptance",
                issuance,
                q,
                founder_acceptance=float(acceptance),
            )
        )
    one_factor_fields = (
        ("origination_fee", "origination_fee_rates", "origination_fee_rate"),
        ("service_fee", "annual_service_fee_rates", "annual_service_fee_rate"),
        (
            "platform_warrant_share",
            "platform_warrant_shares",
            "platform_warrant_share",
        ),
        (
            "variable_operating_cost",
            "variable_operating_cost_rates",
            "variable_operating_cost_rate",
        ),
        ("fixed_operating_cost", "fixed_annual_operating_costs", "fixed_operating_cost"),
    )
    for family, grid_name, override_name in one_factor_fields:
        for value in economics[grid_name]:
            business_rows.append(
                _period_business_row(
                    config,
                    family,
                    float(canonical["annual_new_protected_capital"]),
                    q,
                    **{override_name: float(value)},
                )
            )
    for spread in economics["guarantee_arrangement_spreads"]:
        investor_fee = (
            float(canonical["external_risk_provider_price"])
            + float(economics["variable_risk_admin_cost_rate"])
            + float(spread)
        )
        business_rows.append(
            _period_business_row(
                config,
                "guarantee_arrangement_spread",
                float(canonical["annual_new_protected_capital"]),
                q,
                investor_fee=investor_fee,
                arrangement_spread=float(spread),
            )
        )

    ten_year = economics["ten_year"]
    ten_year_rows = model_ten_year_business(
        TenYearBusinessInputs(
            years=int(ten_year["years"]),
            base_annual_unprotected_demand=float(ten_year["base_annual_unprotected_demand"]),
            annual_issuance_growth_rate=float(ten_year["annual_issuance_growth_rate"]),
            maturity_years=int(ten_year["maturity_years"]),
            demand_uplift=float(canonical["demand_uplift"]),
            founder_acceptance_rate=float(canonical["founder_acceptance_rate"]),
            origination_fee_rate=float(canonical["origination_fee_rate"]),
            annual_service_fee_rate=float(canonical["annual_service_fee_rate"]),
            investor_protection_fee_rate=float(canonical["investor_protection_fee_rate"]),
            external_risk_provider_price_rate=float(
                canonical["external_risk_provider_price"]
            ),
            variable_risk_admin_cost_rate=float(
                economics["variable_risk_admin_cost_rate"]
            ),
            founder_warrant_value_per_new_capital=q,
            platform_warrant_share=float(canonical["platform_warrant_share"]),
            warrant_realization_delay_years=int(ten_year["warrant_realization_delay_years"]),
            variable_operating_cost_rate=float(canonical["variable_operating_cost_rate"]),
            initial_fixed_operating_cost=float(canonical["fixed_annual_operating_cost"]),
            operating_cost_growth_rate=float(ten_year["operating_cost_growth_rate"]),
            discount_rate=float(ten_year["discount_rate"]),
            platform_is_risk_bearer=bool(canonical["platform_is_risk_bearer"]),
            expected_claim_per_unit=float(frontier_risk["expected_claim_per_unit"]),
        )
    )
    business_rows.extend(
        {
            "scenario_family": "ten_year_canonical",
            "commercial_input_provenance": "MODEL_RISK_SCENARIO",
            **row,
        }
        for row in ten_year_rows
    )

    profit_rows: list[dict[str, Any]] = []
    for price in economics["external_risk_provider_prices"]:
        for fixed_cost in economics["fixed_annual_operating_costs"]:
            contribution = steady_state_contribution_rate(
                float(canonical["origination_fee_rate"]),
                float(canonical["annual_service_fee_rate"]),
                maturity,
                float(canonical["investor_protection_fee_rate"]),
                float(price),
                float(economics["variable_risk_admin_cost_rate"]),
                q,
                float(canonical["platform_warrant_share"]),
                float(canonical["variable_operating_cost_rate"]),
            )
            for target_profit in economics["target_annual_profits"]:
                required = break_even_issuance(
                    float(fixed_cost) + float(target_profit), contribution
                )
                profit_rows.append(
                    {
                        "frontier_type": "required_annual_protected_issuance",
                        "external_protection_price": float(price),
                        "fixed_operating_cost": float(fixed_cost),
                        "target_modeled_operating_profit": float(target_profit),
                        "contribution_rate_per_unit_issuance": contribution,
                        "boundary_value": required,
                        "boundary_unit": "GBP annual protected issuance",
                        "status": "solved" if required is not None else "unreachable",
                        "provenance": COMMERCIAL_PRICE_PROVENANCE,
                    }
                )
    for price in economics["external_risk_provider_prices"]:
        contribution = steady_state_contribution_rate(
            float(canonical["origination_fee_rate"]),
            float(canonical["annual_service_fee_rate"]),
            maturity,
            float(canonical["investor_protection_fee_rate"]),
            float(price),
            float(economics["variable_risk_admin_cost_rate"]),
            q,
            float(canonical["platform_warrant_share"]),
            float(canonical["variable_operating_cost_rate"]),
        )
        for acceptance in economics["founder_acceptance_rates"]:
            for target_profit in economics["target_annual_profits"]:
                required_uplift = minimum_demand_uplift(
                    base_demand,
                    float(acceptance),
                    float(canonical["fixed_annual_operating_cost"]),
                    contribution,
                    float(target_profit),
                )
                profit_rows.append(
                    {
                        "frontier_type": "minimum_investor_demand_uplift",
                        "external_protection_price": float(price),
                        "founder_acceptance_rate": float(acceptance),
                        "target_modeled_operating_profit": float(target_profit),
                        "contribution_rate_per_unit_issuance": contribution,
                        "boundary_value": required_uplift,
                        "boundary_unit": "demand uplift multiple",
                        "status": "solved" if required_uplift is not None else "unreachable",
                        "provenance": "MODEL_RISK_SCENARIO",
                    }
                )
    other_rate = (
        float(canonical["origination_fee_rate"])
        + float(canonical["annual_service_fee_rate"]) * maturity
        + q * float(canonical["platform_warrant_share"])
        - float(canonical["variable_operating_cost_rate"])
    )
    canonical_guarantee_margin_rate = max(
        float(canonical["investor_protection_fee_rate"])
        - float(canonical["external_risk_provider_price"])
        - float(economics["variable_risk_admin_cost_rate"]),
        0.0,
    )
    revenue_rate = (
        float(canonical["origination_fee_rate"])
        + float(canonical["annual_service_fee_rate"]) * maturity
        + canonical_guarantee_margin_rate
        + q * float(canonical["platform_warrant_share"])
    )
    for target_revenue in economics["target_annual_revenues"]:
        profit_rows.append(
            {
                "frontier_type": "minimum_issuance_for_revenue_scale",
                "target_modeled_revenue": float(target_revenue),
                "revenue_rate_per_unit_issuance": revenue_rate,
                "boundary_value": (
                    float(target_revenue) / revenue_rate if revenue_rate > 0 else None
                ),
                "boundary_unit": "GBP annual protected issuance",
                "status": "solved" if revenue_rate > 0 else "unreachable",
                "provenance": "MODEL_RISK_SCENARIO",
            }
        )
    for issuance in economics["annual_new_protected_capital"]:
        profit_before_margin = (
            float(issuance) * other_rate - float(canonical["fixed_annual_operating_cost"])
        )
        for target_profit in economics["external_price_profit_targets"]:
            maximum_price = maximum_external_protection_price(
                float(issuance),
                float(target_profit),
                profit_before_margin,
                float(canonical["investor_protection_fee_rate"]),
                float(economics["variable_risk_admin_cost_rate"]),
            )
            required_margin = (
                float(target_profit) - profit_before_margin
            ) / float(issuance)
            available_margin = max(
                float(canonical["investor_protection_fee_rate"])
                - float(economics["variable_risk_admin_cost_rate"]),
                0.0,
            )
            if maximum_price is not None:
                price_status = "finite_boundary"
            elif required_margin <= 0:
                price_status = "not_binding_non_guarantee_economics_meet_target"
            elif required_margin > available_margin:
                price_status = "unreachable_even_at_zero_external_price"
            else:
                price_status = "not_identified"
            profit_rows.append(
                {
                    "frontier_type": "maximum_external_protection_price",
                    "annual_protected_issuance": float(issuance),
                    "target_modeled_operating_profit": float(target_profit),
                    "profit_before_guarantee_margin": profit_before_margin,
                    "boundary_value": maximum_price,
                    "boundary_unit": "fraction of protected issuance",
                    "status": price_status,
                    "provenance": COMMERCIAL_PRICE_PROVENANCE,
                }
            )

    scoreboard_rows = _scoreboard_rows(config, core_rows)
    final_year = ten_year_rows[-1]
    valuation_rows = illustrative_enterprise_values(
        float(final_year["total_revenue"]),
        float(final_year["modeled_operating_profit"]),
        tuple(float(value) for value in economics["valuation"]["revenue_multiples"]),
        tuple(
            float(value)
            for value in economics["valuation"]["modeled_operating_profit_multiples"]
        ),
    )
    for row in valuation_rows:
        row["source_scenario"] = "ten_year_canonical_year_10"
    return business_rows, profit_rows, scoreboard_rows, valuation_rows


def _period_business_row(
    config: dict[str, Any],
    family: str,
    issuance: float,
    q: float,
    **overrides: float,
) -> dict[str, Any]:
    economics = config["platform_economics"]
    canonical = economics["canonical"]
    maturity = float(economics["ten_year"]["maturity_years"])
    external_price = float(
        overrides.get("external_price", canonical["external_risk_provider_price"])
    )
    investor_fee = float(
        overrides.get("investor_fee", canonical["investor_protection_fee_rate"])
    )
    inputs = PlatformEconomicsInputs(
        new_protected_capital=issuance,
        average_outstanding_protected_capital=issuance * maturity,
        protected_capital_charged=issuance,
        origination_fee_rate=float(
            overrides.get("origination_fee_rate", canonical["origination_fee_rate"])
        ),
        annual_service_fee_rate=float(
            overrides.get("annual_service_fee_rate", canonical["annual_service_fee_rate"])
        ),
        investor_protection_fee_rate=investor_fee,
        external_risk_provider_price_rate=external_price,
        variable_risk_admin_cost_rate=float(economics["variable_risk_admin_cost_rate"]),
        founder_warrant_value_per_new_capital=q,
        platform_warrant_share=float(
            overrides.get("platform_warrant_share", canonical["platform_warrant_share"])
        ),
        variable_operating_cost_rate=float(
            overrides.get(
                "variable_operating_cost_rate", canonical["variable_operating_cost_rate"]
            )
        ),
        fixed_operating_cost=float(
            overrides.get("fixed_operating_cost", canonical["fixed_annual_operating_cost"])
        ),
        platform_is_risk_bearer=bool(canonical["platform_is_risk_bearer"]),
    )
    result = model_platform_economics(inputs)
    return {
        "scenario_family": family,
        "annual_protected_issuance": issuance,
        "demand_uplift": overrides.get("demand_uplift"),
        "founder_acceptance_rate": overrides.get("founder_acceptance"),
        "external_protection_price_rate": external_price,
        "investor_protection_fee_rate": investor_fee,
        "arrangement_spread_input": overrides.get("arrangement_spread"),
        "origination_fee_rate": inputs.origination_fee_rate,
        "annual_service_fee_rate": inputs.annual_service_fee_rate,
        "platform_warrant_share": inputs.platform_warrant_share,
        "founder_warrant_value_per_new_capital": q,
        "variable_operating_cost_rate": inputs.variable_operating_cost_rate,
        "fixed_operating_cost": inputs.fixed_operating_cost,
        "commercial_input_provenance": "MODEL_RISK_SCENARIO",
        "external_price_provenance": COMMERCIAL_PRICE_PROVENANCE,
        **result.as_dict(),
    }


def _scoreboard_rows(
    config: dict[str, Any], core_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    economics = config["platform_economics"]
    canonical = economics["canonical"]
    issuance = float(canonical["annual_new_protected_capital"])
    reporting_size = int(config["portfolio"]["canonical_reporting_size"])
    reporting_floor = float(config["portfolio"]["canonical_reporting_floor"])
    rows: list[dict[str, Any]] = []
    for construction in PRIMARY_CONSTRUCTIONS:
        risk = _find_metric_row(
            core_rows,
            portfolio_construction=construction,
            portfolio_size=reporting_size,
            protection_fraction=reporting_floor,
        )
        q = float(risk["expected_founder_warrant_value_per_unit"])
        period = _period_business_row(config, "scoreboard", issuance, q)
        rows.append(
            {
                "portfolio_construction": construction,
                "portfolio_size": reporting_size,
                "protection_fraction": reporting_floor,
                "G_external_protection_cost_per_unit": float(
                    canonical["external_risk_provider_price"]
                ),
                "G_provenance": COMMERCIAL_PRICE_PROVENANCE,
                "U_investor_demand_uplift": float(canonical["demand_uplift"]),
                "U_provenance": "MODEL_RISK_SCENARIO",
                "Q_founder_economic_contribution_per_unit": q,
                "Q_provenance": "MODEL_OUTPUT_FROM_SCENARIO_WARRANT_TERMS",
                "K_risk_capital_proxy_per_unit": float(risk["claim_es_99.5_per_unit"]),
                "K_proxy_definition": "simulated claim ES99.5; not regulatory or committed capital",
                "R_platform_revenue_per_unit_issuance": float(period["total_revenue"])
                / issuance,
                "R_provenance": "MODEL_OUTPUT_FROM_COMMERCIAL_SCENARIOS",
                "P_modeled_profit_per_unit_issuance": float(
                    period["modeled_operating_profit"]
                )
                / issuance,
                "platform_is_risk_bearer": False,
            }
        )
    return rows


def _commercial_stress_rows(
    config: dict[str, Any], baseline_risk: dict[str, Any]
) -> list[dict[str, Any]]:
    economics = config["platform_economics"]
    canonical = economics["canonical"]
    stress_parameters = config["stress_parameters"]
    q = float(baseline_risk["expected_founder_warrant_value_per_unit"])
    issuance = float(canonical["annual_new_protected_capital"])
    original_dilutions = tuple(
        float(value)
        for value in config["protection_support"]["founder_warrant"]["dilution_fractions"]
    )
    original_fraction = diluted_warrant_fraction(
        float(config["protection_support"]["founder_warrant"]["initial_fraction"]),
        original_dilutions,
    )
    doubled_fraction = diluted_warrant_fraction(
        float(config["protection_support"]["founder_warrant"]["initial_fraction"]),
        tuple(
            min(
                float(stress_parameters["doubled_founder_dilution_multiplier"])
                * value,
                1.0,
            )
            for value in original_dilutions
        ),
    )
    stressed_q = q * doubled_fraction / original_fraction
    rows = [
        {
            "stress_name": "founder_warrant_dilution_doubles",
            "domain": "economics",
            "founder_contribution_per_unit": stressed_q,
            "modeled_operating_profit": _period_business_row(
                config, "stress", issuance, stressed_q
            )["modeled_operating_profit"],
            "provenance": "MODEL_RISK_SCENARIO",
        },
        {
            "stress_name": "external_risk_price_doubles",
            "domain": "economics",
            "external_protection_price_rate": min(
                float(stress_parameters["doubled_external_price_multiplier"])
                * float(canonical["external_risk_provider_price"]),
                1.0,
            ),
            "modeled_operating_profit": _period_business_row(
                config,
                "stress",
                issuance,
                q,
                external_price=min(
                    float(stress_parameters["doubled_external_price_multiplier"])
                    * float(canonical["external_risk_provider_price"]),
                    1.0,
                ),
            )["modeled_operating_profit"],
            "provenance": COMMERCIAL_PRICE_PROVENANCE,
        },
    ]
    base_demand = float(economics["ten_year"]["base_annual_unprotected_demand"])
    for name, uplift, acceptance in (
        (
            "investor_demand_uplift_1x",
            float(stress_parameters["no_demand_uplift"]),
            float(canonical["founder_acceptance_rate"]),
        ),
        (
            "founder_acceptance_25pct",
            float(canonical["demand_uplift"]),
            float(stress_parameters["low_founder_acceptance_rate"]),
        ),
    ):
        stressed_issuance = base_demand * uplift * acceptance
        rows.append(
            {
                "stress_name": name,
                "domain": "economics",
                "demand_uplift": uplift,
                "founder_acceptance_rate": acceptance,
                "deployable_protected_issuance": stressed_issuance,
                "modeled_operating_profit": _period_business_row(
                    config, "stress", stressed_issuance, q
                )["modeled_operating_profit"],
                "provenance": "MODEL_RISK_SCENARIO",
            }
        )
    return rows


def _interpolate_factor_pair(
    config: dict[str, Any], dependence_index: float | None
) -> tuple[float | None, float | None]:
    if dependence_index is None:
        return None, None
    path = config["dependence"]["feasibility_path"]
    x = np.asarray([float(item["dependence_index"]) for item in path])
    macro = np.asarray([float(item["rho_macro"]) for item in path])
    sector = np.asarray([float(item["rho_sector"]) for item in path])
    return (
        float(np.interp(dependence_index, x, macro)),
        float(np.interp(dependence_index, x, sector)),
    )


def _interpolate_selection_targets(
    scenarios: list[dict[str, Any]], selection_index: float | None
) -> tuple[float | None, float | None]:
    if selection_index is None:
        return None, None
    grid = np.arange(len(scenarios), dtype=float)
    losses = np.asarray([float(item["probability_below_1x"]) for item in scenarios])
    tails = np.asarray([float(item["probability_ge_10x"]) for item in scenarios])
    return (
        float(np.interp(selection_index, grid, losses)),
        float(np.interp(selection_index, grid, tails)),
    )


def _find_metric_row(rows: list[dict[str, Any]], **matches: Any) -> dict[str, Any]:
    found = [
        row
        for row in rows
        if all(row.get(field) == value for field, value in matches.items())
    ]
    if len(found) != 1:
        raise ValueError(f"expected one metric row for {matches}, found {len(found)}")
    return found[0]


def _validation_payload(
    config: dict[str, Any],
    repository_root: Path,
    constraints: dict[str, Any],
    base_spec: EmpiricalMixtureSpec,
    selection_diagnostics: dict[str, list[dict[str, Any]]],
    core_rows: list[dict[str, Any]],
    failure_rows: list[dict[str, Any]],
    convergence_rows: list[dict[str, Any]],
    plan: tuple[Any, ...],
) -> dict[str, Any]:
    target_unselected = target_selection_marginals(
        config, base_spec, config["baseline_tail_model"]
    )["unselected"]
    weights_exact = (
        target_unselected.spec.weights.values_for_sampling
        == base_spec.weights.values_for_sampling
    )
    complete_loss_exact = (
        target_unselected.spec.weights.complete_loss == base_spec.weights.complete_loss
    )
    frozen_files = {
        "configs/base.yaml": "v0.2.0-s2a",
        "configs/calibrated_terminal_v1.yaml": "v0.3.0-s2b-a",
    }
    frozen_checks = []
    for path, tag in frozen_files.items():
        current_hash = file_hash(repository_root / path)
        tag_hash = _git_blob_hash(repository_root, tag, path)
        frozen_checks.append(
            {
                "path": path,
                "tag": tag,
                "current_sha256": current_hash,
                "tag_sha256": tag_hash,
                "unchanged": current_hash == tag_hash,
            }
        )

    arithmetic_valid = True
    for row in failure_rows:
        maximum = row["maximum_failures"]
        if maximum is None:
            arithmetic_valid &= float(row["survivor_multiple"]) < float(
                row["protection_fraction"]
            )
            continue
        portfolio_size = int(row["portfolio_size"])
        covered = (
            maximum / portfolio_size * float(row["failure_recovery_multiple"])
            + (1.0 - maximum / portfolio_size) * float(row["survivor_multiple"])
        )
        arithmetic_valid &= covered + 1e-12 >= float(row["protection_fraction"])
        if maximum < portfolio_size:
            next_count = maximum + 1
            next_multiple = (
                next_count / portfolio_size * float(row["failure_recovery_multiple"])
                + (1.0 - next_count / portfolio_size) * float(row["survivor_multiple"])
            )
            arithmetic_valid &= next_multiple < float(row["protection_fraction"]) + 1e-12

    target_diag = selection_diagnostics["target_constraint"]
    tilt_diag = selection_diagnostics["exponential_tilt"]
    checks = [
        {
            "name": "frozen_configs_unchanged",
            "passed": all(item["unchanged"] for item in frozen_checks),
        },
        {
            "name": "selection_unselected_reproduces_base_weights_exactly",
            "passed": weights_exact and complete_loss_exact,
        },
        {
            "name": "selection_probabilities_monotone",
            "passed": all(
                float(after["probability_below_1x"])
                <= float(before["probability_below_1x"])
                and float(after["expected_multiple"])
                >= float(before["expected_multiple"])
                for before, after in zip(target_diag, target_diag[1:])
            ),
        },
        {
            "name": "exponential_tilt_monotone",
            "passed": all(
                float(after["probability_below_1x"])
                <= float(before["probability_below_1x"])
                and float(after["expected_multiple"])
                >= float(before["expected_multiple"])
                for before, after in zip(tilt_diag, tilt_diag[1:])
            ),
        },
        {
            "name": "failure_tolerance_matches_direct_arithmetic",
            "passed": bool(arithmetic_valid),
        },
        {
            "name": "core_path_requirement_met",
            "passed": all(
                int(row["number_of_paths"]) >= 100_000 for row in core_rows
            ),
        },
        {
            "name": "scenario_assumptions_not_observed_or_fitted",
            "passed": all(
                assumption["provenance"]
                not in {"OBSERVED", "FITTED", "OBSERVED_RAW", "OBSERVED_AGGREGATE"}
                for assumption in config["assumptions"].values()
            ),
        },
        {
            "name": "experiment_plan_records_all_tiers",
            "passed": {item.tier for item in plan}
            >= {"core", "sensitivity", "discovery", "refinement", "stress"},
        },
    ]
    convergence_final = convergence_rows[-1]
    convergence_prior = convergence_rows[-2]
    convergence_delta = abs(
        float(convergence_final["expected_claim_per_unit"])
        - float(convergence_prior["expected_claim_per_unit"])
    )
    return {
        "overall_passed": all(check["passed"] for check in checks),
        "checks": checks,
        "frozen_file_checks": frozen_checks,
        "empirical_base_weights": base_spec.weights.as_dict(),
        "empirical_constraints_hash": canonical_hash(constraints),
        "core_row_count": len(core_rows),
        "failure_tolerance_row_count": len(failure_rows),
        "assumption_count": len(config["assumptions"]),
        "convergence": {
            "final_paths": convergence_final["number_of_paths"],
            "absolute_expected_claim_change_from_prior_stage": convergence_delta,
            "final_es99_5_tail_observations": convergence_final[
                "claim_es_99.5_tail_observations"
            ],
            "final_es99_5_mc_standard_error": convergence_final[
                "claim_es_99.5_mc_standard_error"
            ],
        },
        "deterministic_numerical_payload_note": (
            "Same code, config, and seed produce identical canonical JSON payloads; "
            "timestamps and Git dirty state are manifest metadata."
        ),
    }


def _git_blob_hash(repository_root: Path, tag: str, path: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repository_root), "show", f"{tag}:{path}"],
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return hashlib.sha256(completed.stdout).hexdigest()

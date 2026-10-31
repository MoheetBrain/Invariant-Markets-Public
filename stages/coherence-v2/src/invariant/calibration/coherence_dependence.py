"""S2b-a.1 empirical-coherence audit and dependence-frontier runner.

This module deliberately consumes, but does not refit or mutate, the frozen
S2b-a V1 marginal model.  Proxy reweightings are sensitivity scenarios rather
than empirical estimates.
"""

from __future__ import annotations

import csv
import json
import platform
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import yaml
from scipy.stats import norm, t

from invariant.calibration.parameter_models import (
    BodySpec,
    CorrelationSpec,
    EmpiricalMixtureSpec,
    MixtureWeights,
    TailSpec,
)
from invariant.core.metrics import empirical_expected_shortfall, empirical_var
from invariant.models.terminal.empirical_mixture import inverse_terminal_return_cdf
from invariant.reporting.artifacts import (
    canonical_hash,
    file_hash,
    git_commit_hash,
    git_worktree_dirty,
)


OBSERVATION_OBJECT_TYPES = frozenset(
    {
        "UNIQUE_COMPANY",
        "FINANCING_ROUND",
        "INVESTOR_CHECK",
        "FOUNDER_PROCEEDS",
        "COMPANY_EXIT_VALUE",
        "FUND_TVPI",
        "FUND_DPI",
        "UNKNOWN",
    }
)

AUDIT_FIELDS = (
    "source_id",
    "variable",
    "value",
    "unit",
    "object_measured",
    "denominator",
    "realised_or_censored",
    "company_or_round",
    "stage",
    "geography",
    "vintage",
    "gross_or_net",
    "source_quality",
    "provenance_status",
    "notes",
)


@dataclass(frozen=True)
class PortfolioPaths:
    """Path outputs needed by the frontier and deletion experiments."""

    terminal_multiples: np.ndarray
    without_top1: np.ndarray
    without_top3: np.ndarray
    without_top5: np.ndarray
    without_ge_50x: np.ndarray
    without_ge_10x: np.ndarray
    largest_share: np.ndarray
    top3_share: np.ndarray
    top5_share: np.ndarray
    count_ge_50x: np.ndarray


def load_observation_audit(path: str | Path) -> list[dict[str, str]]:
    """Load and validate the row-level aggregate-observation audit."""

    with Path(path).open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    validate_observation_rows(rows)
    return rows


def validate_observation_rows(rows: Iterable[dict[str, str]]) -> None:
    """Reject missing metadata and silent round/company relabelling."""

    materialized = list(rows)
    if not materialized:
        raise ValueError("observation audit cannot be empty")
    for index, row in enumerate(materialized, start=2):
        missing = [field for field in AUDIT_FIELDS if not str(row.get(field, "")).strip()]
        if missing:
            raise ValueError(f"observation row {index} has missing fields: {missing}")
        object_type = row["object_measured"]
        if object_type not in OBSERVATION_OBJECT_TYPES:
            raise ValueError(f"observation row {index} has invalid object type {object_type!r}")
        if row["company_or_round"] == "FINANCING_ROUND" and object_type == "UNIQUE_COMPANY":
            raise ValueError("financing-round observation cannot be labelled UNIQUE_COMPANY")


def require_investor_moic_mapping(
    observation: dict[str, str], explicit_mapping: str | None = None
) -> str:
    """Require an explicit bridge before a unlike object becomes investor MOIC."""

    object_type = observation["object_measured"]
    if object_type in {"FINANCING_ROUND", "INVESTOR_CHECK"}:
        return object_type
    if explicit_mapping is None:
        raise ValueError(f"{object_type} cannot be ingested as investor MOIC without explicit mapping")
    return explicit_mapping


def build_rho_grid(start: float, stop: float, step: float) -> tuple[float, ...]:
    """Build an inclusive, decimal-stable rho grid."""

    if step <= 0 or start < 0 or stop > 1 or start > stop:
        raise ValueError("invalid rho grid")
    count = int(round((stop - start) / step))
    values = tuple(round(start + index * step, 10) for index in range(count + 1))
    if not np.isclose(values[-1], stop):
        raise ValueError("rho interval is not divisible by rho_step")
    return values


def interpolate_breakpoint(
    x: Iterable[float], y: Iterable[float], threshold: float
) -> dict[str, Any]:
    """Find the first threshold crossing using a monotone envelope and interpolation."""

    x_array = np.asarray(tuple(x), dtype=float)
    y_array = np.asarray(tuple(y), dtype=float)
    if x_array.size < 2 or x_array.size != y_array.size:
        raise ValueError("breakpoint inputs must have equal length >= 2")
    if np.any(np.diff(x_array) <= 0):
        raise ValueError("breakpoint x values must be strictly increasing")
    monotone = np.maximum.accumulate(y_array)
    if threshold < monotone[0]:
        return {"status": "BELOW_GRID_MIN", "rho": None}
    if threshold > monotone[-1]:
        return {"status": "ABOVE_GRID_MAX", "rho": None}
    index = int(np.searchsorted(monotone, threshold, side="left"))
    if index == 0:
        return {"status": "AT_GRID_MIN", "rho": float(x_array[0])}
    x0, x1 = x_array[index - 1], x_array[index]
    y0, y1 = monotone[index - 1], monotone[index]
    rho = x1 if y1 == y0 else x0 + (threshold - y0) * (x1 - x0) / (y1 - y0)
    return {
        "status": "INTERPOLATED",
        "rho": float(rho),
        "rho_lower": float(x0),
        "rho_upper": float(x1),
        "value_lower": float(y0),
        "value_upper": float(y1),
    }


def _stable_seed(*values: Any) -> int:
    digest = canonical_hash([str(value) for value in values])
    return int(digest[:8], 16)


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = yaml.safe_load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return value


def _write_json(path: Path, value: Any) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")


def _write_yaml(path: Path, value: Any) -> None:
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(value, handle, sort_keys=False)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _baseline_spec(config: dict[str, Any], *, name: str = "empirical_v1_frozen") -> EmpiricalMixtureSpec:
    marginal = config["baseline_marginal"]
    return EmpiricalMixtureSpec(
        name=name,
        body=BodySpec(str(marginal["body_model"])),
        tail=TailSpec(
            name="v1_tail",
            survival_tail_exponent_beta=float(marginal["survival_tail_exponent_beta"]),
            mode=str(marginal["tail_mode"]),
            cap=float(marginal["tail_cap"]),
        ),
        correlation=CorrelationSpec(name="independent", model="independent"),
        weights=MixtureWeights(
            complete_loss=0.39,
            partial_loss=0.26,
            ordinary_success_1_5x=0.25,
            strong_success_5_10x=0.06,
            tail_10x_plus=0.04,
            target_mega_50x_plus=0.004,
        ),
    )


def coherence_weights(p_below_1x: float, winner_mass_scale: float) -> MixtureWeights:
    """Create an explicit threshold/reweighting scenario without fitting a target TVPI."""

    p5 = 0.10 * winner_mass_scale
    p10 = 0.04 * winner_mass_scale
    p50 = 0.004 * winner_mass_scale
    if not (0.39 <= p_below_1x < 1 - p5) or not (0 < p10 < p5):
        raise ValueError("invalid coherence interpretation")
    weights = MixtureWeights(
        complete_loss=0.39,
        partial_loss=p_below_1x - 0.39,
        ordinary_success_1_5x=1.0 - p_below_1x - p5,
        strong_success_5_10x=p5 - p10,
        tail_10x_plus=p10,
        target_mega_50x_plus=p50,
    )
    weights.validate()
    return weights


def _coherence_analysis(config: dict[str, Any]) -> list[dict[str, Any]]:
    settings = config["coherence"]
    q = (np.arange(int(settings["pooled_quantile_points"])) + 0.5) / int(
        settings["pooled_quantile_points"]
    )
    paths = int(settings["portfolio_paths"])
    portfolio_size = int(settings["portfolio_size_for_median_proxy"])
    rng = np.random.default_rng(_stable_seed(config["random_seed"], "coherence"))
    portfolio_uniforms = rng.random((paths, portfolio_size))
    targets = (1.84, 1.95)
    median_target = 1.48
    tolerances = settings["benchmark_tolerances"]
    rows: list[dict[str, Any]] = []
    for interpretation in settings["below_1x_interpretations"]:
        for weighting in settings["weighting_scenarios"]:
            weights = coherence_weights(
                float(interpretation["probability"]), float(weighting["winner_mass_scale"])
            )
            for body in settings["bodies"]:
                for beta_value in settings["tail_exponents"]:
                    beta = float(beta_value)
                    for cap_value in settings["tail_caps"]:
                        cap = None if cap_value is None else float(cap_value)
                        mode = "unbounded_pareto" if cap is None else "capped_pareto"
                        spec = EmpiricalMixtureSpec(
                            name="coherence_variant",
                            body=BodySpec(str(body)),
                            tail=TailSpec(
                                name="coherence_tail",
                                survival_tail_exponent_beta=beta,
                                mode=mode,
                                cap=cap,
                            ),
                            correlation=CorrelationSpec(name="independent", model="independent"),
                            weights=weights,
                        )
                        pooled_returns = inverse_terminal_return_cdf(q, spec)
                        portfolio = inverse_terminal_return_cdf(portfolio_uniforms, spec).mean(axis=1)
                        mean_value = float(np.mean(pooled_returns))
                        median_value = float(np.median(portfolio))
                        implied_p50 = weights.tail_10x_plus * (5.0 ** (-beta))
                        residuals = {
                            "below_1x": weights.complete_loss + weights.partial_loss - 0.65,
                            "above_5x": weights.strong_success_5_10x
                            + weights.tail_10x_plus
                            - 0.10,
                            "above_10x": weights.tail_10x_plus - 0.04,
                            "above_50x": implied_p50 - 0.004,
                        }
                        constraints_compatible = (
                            abs(residuals["below_1x"]) <= 0.03
                            and abs(residuals["above_5x"]) <= 0.015
                            and abs(residuals["above_10x"]) <= 0.008
                            and abs(residuals["above_50x"]) <= 0.002
                        )
                        mean_distance = min(abs(mean_value - target) for target in targets)
                        median_distance = abs(median_value - median_target)
                        if (
                            constraints_compatible
                            and mean_distance <= float(tolerances["compatible_mean_absolute"])
                            and median_distance
                            <= float(tolerances["compatible_median_absolute"])
                        ):
                            classification = "compatible"
                        elif (
                            constraints_compatible
                            and mean_distance <= float(tolerances["weak_mean_absolute"])
                            and median_distance <= float(tolerances["weak_median_absolute"])
                        ):
                            classification = "weakly_compatible"
                        else:
                            classification = "incompatible"
                        rows.append(
                            {
                                "below_1x_interpretation": interpretation["name"],
                                "p_below_1x": float(interpretation["probability"]),
                                "interpretation_provenance": interpretation["provenance"],
                                "weighting_scenario": weighting["name"],
                                "winner_mass_scale": float(weighting["winner_mass_scale"]),
                                "weighting_provenance": weighting["provenance"],
                                "body_model": body,
                                "tail_beta": beta,
                                "tail_cap": "none" if cap is None else cap,
                                "implied_p_below_1x": weights.complete_loss + weights.partial_loss,
                                "implied_p_ge_5x": weights.strong_success_5_10x
                                + weights.tail_10x_plus,
                                "implied_p_ge_10x": weights.tail_10x_plus,
                                "implied_p_ge_50x": implied_p50,
                                "implied_pooled_mean": mean_value,
                                "implied_n100_median": median_value,
                                "mean_mc_or_quadrature_se": float(
                                    np.std(pooled_returns, ddof=1) / np.sqrt(pooled_returns.size)
                                ),
                                "n100_median_paths": paths,
                                "constraints_compatible": constraints_compatible,
                                "fund_benchmark_classification": classification,
                                "is_exact_v1": (
                                    interpretation["name"] == "reported_strict_below_1x"
                                    and weighting["name"] == "financing_round_reported"
                                    and body == "log_uniform"
                                    and np.isclose(beta, 1.4306765580733931)
                                    and cap == 1000.0
                                ),
                            }
                        )
    return rows


def _uniform_batch(
    family: str,
    rho: float,
    paths: int,
    investments: int,
    rng: np.random.Generator,
    options: dict[str, Any] | None = None,
) -> np.ndarray:
    if not 0 <= rho <= 1:
        raise ValueError("rho must lie in [0, 1]")
    options = options or {}
    epsilon = rng.standard_normal((paths, investments))
    common = rng.standard_normal((paths, 1))
    if family == "gaussian_factor":
        z = np.sqrt(rho) * common + np.sqrt(1 - rho) * epsilon
        return norm.cdf(z)
    if family == "student_t_factor":
        z = np.sqrt(rho) * common + np.sqrt(1 - rho) * epsilon
        df = float(options.get("degrees_of_freedom", 4))
        if df <= 2:
            raise ValueError("Student-t degrees_of_freedom must exceed two")
        scale = np.sqrt(rng.chisquare(df, size=(paths, 1)) / df)
        return t.cdf(z / scale, df=df)
    if family == "macro_state_mixture":
        probability = float(options.get("stress_probability", 0.20))
        if not 0 < probability < 1:
            raise ValueError("stress_probability must lie in (0, 1)")
        stress = rng.random((paths, 1)) < probability
        factor = np.where(
            stress,
            -np.sqrt((1 - probability) / probability),
            np.sqrt(probability / (1 - probability)),
        )
        z = np.sqrt(rho) * factor + np.sqrt(1 - rho) * epsilon
        return norm.cdf(z)
    if family == "sector_factor":
        sector_rho = float(options.get("sector_rho", 0.15))
        sectors = int(options.get("sectors", 10))
        if sectors <= 0 or rho + sector_rho > 1:
            raise ValueError("invalid sector-factor correlation allocation")
        sector_factors = rng.standard_normal((paths, sectors))
        assignments = np.arange(investments) % sectors
        z = (
            np.sqrt(rho) * common
            + np.sqrt(sector_rho) * sector_factors[:, assignments]
            + np.sqrt(1 - rho - sector_rho) * epsilon
        )
        return norm.cdf(z)
    raise ValueError(f"unknown dependence family {family!r}")


def simulate_nested_portfolios(
    spec: EmpiricalMixtureSpec,
    family: str,
    rho: float,
    portfolio_sizes: Iterable[int],
    number_of_paths: int,
    random_seed: int,
    options: dict[str, Any] | None = None,
) -> dict[int, PortfolioPaths]:
    """Simulate nested portfolio prefixes in memory-bounded batches."""

    sizes = tuple(sorted(set(int(value) for value in portfolio_sizes)))
    if not sizes or sizes[0] <= 0 or number_of_paths <= 0:
        raise ValueError("positive portfolio sizes and path count required")
    maximum = sizes[-1]
    batch_size = max(64, min(2000, 2_000_000 // maximum))
    arrays: dict[int, dict[str, np.ndarray]] = {}
    for size in sizes:
        arrays[size] = {
            key: np.zeros(number_of_paths, dtype=int if key == "count_ge_50x" else float)
            for key in PortfolioPaths.__dataclass_fields__
        }
    rng = np.random.default_rng(
        np.random.SeedSequence([random_seed, _stable_seed(family, rho, maximum, number_of_paths)])
    )
    for start in range(0, number_of_paths, batch_size):
        stop = min(start + batch_size, number_of_paths)
        uniforms = _uniform_batch(family, rho, stop - start, maximum, rng, options)
        returns = inverse_terminal_return_cdf(uniforms, spec)
        for size in sizes:
            sub = returns[:, :size]
            totals = np.sum(sub, axis=1)
            top_count = min(5, size)
            top = np.sort(np.partition(sub, size - top_count, axis=1)[:, -top_count:], axis=1)[
                :, ::-1
            ]
            top1 = top[:, 0]
            top3 = np.sum(top[:, : min(3, size)], axis=1)
            top5 = np.sum(top, axis=1)
            positive = totals > 0
            output = arrays[size]
            output["terminal_multiples"][start:stop] = totals / size
            output["without_top1"][start:stop] = (totals - top1) / size
            output["without_top3"][start:stop] = (totals - top3) / size
            output["without_top5"][start:stop] = (totals - top5) / size
            output["without_ge_50x"][start:stop] = (
                totals - np.sum(np.where(sub >= 50.0, sub, 0.0), axis=1)
            ) / size
            output["without_ge_10x"][start:stop] = (
                totals - np.sum(np.where(sub >= 10.0, sub, 0.0), axis=1)
            ) / size
            for key, top_value in (
                ("largest_share", top1),
                ("top3_share", top3),
                ("top5_share", top5),
            ):
                values = np.zeros(stop - start)
                values[positive] = top_value[positive] / totals[positive]
                output[key][start:stop] = values
            output["count_ge_50x"][start:stop] = np.sum(sub >= 50.0, axis=1)
    return {size: PortfolioPaths(**values) for size, values in arrays.items()}


def claim_metrics(paths: PortfolioPaths, protection_fraction: float) -> dict[str, float | int]:
    """Calculate positive-loss claim metrics and Monte Carlo diagnostics."""

    claims = np.maximum(protection_fraction - paths.terminal_multiples, 0.0)
    result: dict[str, float | int] = {
        "expected_portfolio_moic": float(np.mean(paths.terminal_multiples)),
        "median_portfolio_moic": float(np.median(paths.terminal_multiples)),
        "probability_claim": float(np.mean(claims > 0)),
        "expected_claim_per_unit": float(np.mean(claims)),
        "expected_claim_mcse": float(np.std(claims, ddof=1) / np.sqrt(claims.size)),
        "probability_claim_mcse": float(
            np.sqrt(np.mean(claims > 0) * (1 - np.mean(claims > 0)) / claims.size)
        ),
        "max_claim_per_unit": float(np.max(claims)),
        "mean_largest_winner_share": float(np.mean(paths.largest_share)),
        "mean_top3_winner_share": float(np.mean(paths.top3_share)),
        "mean_top5_winner_share": float(np.mean(paths.top5_share)),
        "investment_observations_ge_50x": int(np.sum(paths.count_ge_50x)),
    }
    for confidence in (0.95, 0.99, 0.995):
        suffix = f"{confidence * 100:g}"
        var = empirical_var(claims, confidence)
        es = empirical_expected_shortfall(claims, confidence)
        tail = claims[claims >= var]
        result[f"claim_var_{suffix}"] = var
        result[f"claim_es_{suffix}"] = es
        result[f"claim_es_{suffix}_tail_observations"] = int(tail.size)
        result[f"claim_es_{suffix}_mcse"] = float(
            np.std(tail, ddof=1) / np.sqrt(tail.size) if tail.size > 1 else 0.0
        )
    return result


def _dependence_frontier(config: dict[str, Any], spec: EmpiricalMixtureSpec) -> list[dict[str, Any]]:
    settings = config["dependence_frontier"]
    rho_values = build_rho_grid(
        float(settings["rho_start"]), float(settings["rho_stop"]), float(settings["rho_step"])
    )
    sizes = tuple(int(value) for value in settings["portfolio_sizes"])
    floors = tuple(float(value) for value in settings["protection_fractions"])
    rows: list[dict[str, Any]] = []
    for rho in rho_values:
        portfolios = simulate_nested_portfolios(
            spec,
            family="gaussian_factor",
            rho=rho,
            portfolio_sizes=sizes,
            number_of_paths=int(settings["screening_paths"]),
            random_seed=int(config["random_seed"]),
        )
        for size, paths in portfolios.items():
            for floor in floors:
                rows.append(
                    {
                        "dependence_model": "gaussian_factor",
                        "rho": rho,
                        "portfolio_size": size,
                        "protection_fraction": floor,
                        "estimate_stage": "screening",
                        "simulation_paths": int(settings["screening_paths"]),
                        **claim_metrics(paths, floor),
                    }
                )
        final_sizes = tuple(int(value) for value in settings["final_portfolio_sizes"])
        if final_sizes:
            final = simulate_nested_portfolios(
                spec,
                family="gaussian_factor",
                rho=rho,
                portfolio_sizes=final_sizes,
                number_of_paths=int(settings["final_paths"]),
                random_seed=int(config["random_seed"]),
            )
            rows = [
                row
                for row in rows
                if not (row["rho"] == rho and row["portfolio_size"] in final_sizes)
            ]
            for size, paths in final.items():
                for floor in floors:
                    rows.append(
                        {
                            "dependence_model": "gaussian_factor",
                            "rho": rho,
                            "portfolio_size": size,
                            "protection_fraction": floor,
                            "estimate_stage": "final",
                            "simulation_paths": int(settings["final_paths"]),
                            **claim_metrics(paths, floor),
                        }
                    )
    return sorted(rows, key=lambda row: (row["portfolio_size"], row["protection_fraction"], row["rho"]))


def _breakpoint_rows(config: dict[str, Any], frontier: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    thresholds = (
        ("expected_claim_per_unit", config["breakpoints"]["expected_claim_thresholds"]),
        ("probability_claim", config["breakpoints"]["probability_claim_thresholds"]),
    )
    groups = sorted({(row["portfolio_size"], row["protection_fraction"]) for row in frontier})
    for size, floor in groups:
        series = sorted(
            [
                row
                for row in frontier
                if row["portfolio_size"] == size and row["protection_fraction"] == floor
            ],
            key=lambda row: row["rho"],
        )
        for metric, metric_thresholds in thresholds:
            for threshold_value in metric_thresholds:
                solved = interpolate_breakpoint(
                    [row["rho"] for row in series],
                    [row[metric] for row in series],
                    float(threshold_value),
                )
                rows.append(
                    {
                        "portfolio_size": size,
                        "protection_fraction": floor,
                        "metric": metric,
                        "threshold": float(threshold_value),
                        "status": solved["status"],
                        "rho_breakpoint": solved.get("rho"),
                        "rho_lower": solved.get("rho_lower"),
                        "rho_upper": solved.get("rho_upper"),
                        "interpolation": config["breakpoints"]["interpolation"],
                        "estimate_stage": series[0]["estimate_stage"],
                    }
                )
    return rows


def _saturation_rows(frontier: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    groups = sorted({(row["rho"], row["protection_fraction"]) for row in frontier})
    for rho, floor in groups:
        series = sorted(
            [
                row
                for row in frontier
                if row["rho"] == rho and row["protection_fraction"] == floor
            ],
            key=lambda row: row["portfolio_size"],
        )
        asymptote_proxy = series[-1]["expected_claim_per_unit"]
        previous = None
        for item in series:
            rows.append(
                {
                    "rho": rho,
                    "protection_fraction": floor,
                    "portfolio_size": item["portfolio_size"],
                    "expected_claim_per_unit": item["expected_claim_per_unit"],
                    "probability_claim": item["probability_claim"],
                    "marginal_claim_reduction_from_previous_n": (
                        None
                        if previous is None
                        else previous["expected_claim_per_unit"]
                        - item["expected_claim_per_unit"]
                    ),
                    "marginal_probability_reduction_from_previous_n": (
                        None
                        if previous is None
                        else previous["probability_claim"] - item["probability_claim"]
                    ),
                    "distance_to_n2000_claim_proxy": item["expected_claim_per_unit"]
                    - asymptote_proxy,
                    "common_factor_interpretation": (
                        "Idiosyncratic risk diversifies; common-factor state risk remains as N grows."
                    ),
                    "estimate_stage": item["estimate_stage"],
                }
            )
            previous = item
    return rows


def _winner_deletion_rows(
    config: dict[str, Any], spec: EmpiricalMixtureSpec
) -> list[dict[str, Any]]:
    settings = config["winner_deletion"]
    field_by_rule = {
        "normal": "terminal_multiples",
        "remove_top1": "without_top1",
        "remove_top3": "without_top3",
        "remove_top5": "without_top5",
        "remove_all_ge_50x": "without_ge_50x",
        "remove_all_ge_10x": "without_ge_10x",
    }
    rows: list[dict[str, Any]] = []
    for rho_value in settings["rho_values"]:
        rho = float(rho_value)
        portfolios = simulate_nested_portfolios(
            spec,
            family="gaussian_factor",
            rho=rho,
            portfolio_sizes=settings["portfolio_sizes"],
            number_of_paths=int(settings["paths"]),
            random_seed=int(config["random_seed"]),
        )
        for size, paths in portfolios.items():
            for floor_value in settings["protection_fractions"]:
                floor = float(floor_value)
                baseline_claims = np.maximum(floor - paths.terminal_multiples, 0.0)
                for rule in settings["deletion_rules"]:
                    nav = np.asarray(getattr(paths, field_by_rule[rule]))
                    claims = np.maximum(floor - nav, 0.0)
                    rows.append(
                        {
                            "rho": rho,
                            "portfolio_size": size,
                            "protection_fraction": floor,
                            "deletion_rule": rule,
                            "simulation_paths": int(settings["paths"]),
                            "expected_claim_per_unit": float(np.mean(claims)),
                            "probability_claim": float(np.mean(claims > 0)),
                            "claim_var_99_5": empirical_var(claims, 0.995),
                            "claim_es_99_5": empirical_expected_shortfall(claims, 0.995),
                            "incremental_expected_claim_vs_normal": float(
                                np.mean(claims - baseline_claims)
                            ),
                        }
                    )
    return rows


def _model_comparison_rows(
    config: dict[str, Any], spec: EmpiricalMixtureSpec
) -> list[dict[str, Any]]:
    settings = config["dependence_model_comparison"]
    rows: list[dict[str, Any]] = []
    for item in settings["models"]:
        options = {
            key: value
            for key, value in item.items()
            if key not in {"name", "family", "provenance"}
        }
        portfolios = simulate_nested_portfolios(
            spec,
            family=str(item["family"]),
            rho=float(settings["rho"]),
            portfolio_sizes=settings["portfolio_sizes"],
            number_of_paths=int(settings["paths"]),
            random_seed=int(config["random_seed"]),
            options=options,
        )
        for size, paths in portfolios.items():
            for floor_value in settings["protection_fractions"]:
                rows.append(
                    {
                        "model_name": item["name"],
                        "dependence_family": item["family"],
                        "provenance": item["provenance"],
                        "rho_parameter": float(settings["rho"]),
                        "portfolio_size": size,
                        "protection_fraction": float(floor_value),
                        "simulation_paths": int(settings["paths"]),
                        **claim_metrics(paths, float(floor_value)),
                    }
                )
    return rows


def _mismatch_payload(
    config: dict[str, Any], coherence: list[dict[str, Any]]
) -> dict[str, Any]:
    baseline = next(row for row in coherence if row["is_exact_v1"])
    frozen = config["frozen_v1_validation_outputs"]
    pooled = float(frozen["simulated_pooled_tvpi_proxy"])
    median = float(frozen["simulated_median_tvpi_proxy"])
    reductions = {}
    for name, target, starting in (
        ("us_pooled", 1.95, pooled),
        ("uk_pooled", 1.84, pooled),
        ("uk_median", 1.48, median),
    ):
        reductions[name] = {
            "starting_proxy": starting,
            "target": target,
            "absolute_reduction": starting - target,
            "percentage_reduction_from_start": (starting - target) / starting,
        }
    dimensions = [
        "financing_round_weighting",
        "winner_duplication",
        "censoring",
        "vintage_composition",
        "fees_and_carry",
        "gross_versus_net_definition",
        "stage_mismatch",
    ]
    return {
        "required_reductions": reductions,
        "frozen_v1_output_provenance": frozen,
        "coherence_quadrature_cross_check": {
            "pooled_mean": float(baseline["implied_pooled_mean"]),
            "n100_median": float(baseline["implied_n100_median"]),
        },
        "causal_decomposition": {
            "body_distribution": "MODEL-RISK SENSITIVITY ONLY; NOT CAUSALLY IDENTIFIED",
            "extreme_tail": "MODEL-RISK SENSITIVITY ONLY; NOT CAUSALLY IDENTIFIED",
            **{name: "NOT IDENTIFIABLE FROM AVAILABLE DATA" for name in dimensions},
        },
        "identification_limit": (
            "No row-level company IDs, round links, cash flows, censoring flags, fund weights, "
            "fees/carry fields, valuation status, or common vintage/stage definition are available."
        ),
    }


def _selected_frontier_table(frontier: list[dict[str, Any]], size: int) -> list[dict[str, Any]]:
    selected_rho = {0.0, 0.1, 0.2, 0.3, 0.4}
    return [
        row
        for row in frontier
        if row["portfolio_size"] == size and round(float(row["rho"]), 2) in selected_rho
    ]


def _summary_markdown(
    config: dict[str, Any],
    coherence: list[dict[str, Any]],
    frontier: list[dict[str, Any]],
    breakpoints: list[dict[str, Any]],
    saturation: list[dict[str, Any]],
    deletion: list[dict[str, Any]],
    comparison: list[dict[str, Any]],
    mismatch: dict[str, Any],
) -> str:
    baseline = next(row for row in coherence if row["is_exact_v1"])
    compatible_count = sum(row["fund_benchmark_classification"] == "compatible" for row in coherence)
    weak_count = sum(
        row["fund_benchmark_classification"] == "weakly_compatible" for row in coherence
    )
    frozen = config["frozen_v1_validation_outputs"]
    threshold_compatible = [row for row in coherence if row["constraints_compatible"]]
    deletion_normal = next(
        row
        for row in deletion
        if row["rho"] == 0.2
        and row["portfolio_size"] == 1000
        and row["protection_fraction"] == 0.9
        and row["deletion_rule"] == "normal"
    )
    deletion_10x = next(
        row
        for row in deletion
        if row["rho"] == 0.2
        and row["portfolio_size"] == 1000
        and row["protection_fraction"] == 0.9
        and row["deletion_rule"] == "remove_all_ge_10x"
    )
    model_stress = [
        row
        for row in comparison
        if row["portfolio_size"] == 1000 and row["protection_fraction"] == 0.9
    ]
    lines = [
        "# S2b-a.1 / V2 empirical coherence + dependence frontier",
        "",
        "> V2 is an analysis layer around the frozen V1 marginal. It is not a refitted unique-company return model, guarantee quote, capital model, or product-viability assessment.",
        "",
        "## Bottom line",
        "",
        f"The frozen V1 run produces `{float(frozen['simulated_pooled_tvpi_proxy']):.4f}x` because the four rounded financing/deal-level thresholds leave the within-band body and extreme-tail severity underidentified. The selected log-uniform body and capped Pareto tail convert those frequency constraints into a high gross equal-weighted mean. That object is not comparable one-for-one with capital-weighted fund TVPI.",
        "",
        f"Across `{len(coherence)}` pre-declared interpretations, `{compatible_count}` are classified compatible and `{weak_count}` weakly compatible under the stated joint threshold/TVPI tolerances. No proxy adjustment is promoted to a central V2 model because company de-duplication and cash-flow definitions are unavailable.",
        "",
        "The Correlation-style source is not proven to be a unique-company dataset. The public description is financing/investment-level and may repeat successful companies across rounds. The amount of duplication is **NOT IDENTIFIABLE FROM AVAILABLE DATA**.",
        "",
        "## Required reduction from V1 proxy",
        "",
        "| Comparison | Absolute | Percentage of V1 proxy |",
        "|---|---:|---:|",
    ]
    for name, item in mismatch["required_reductions"].items():
        lines.append(
            f"| {name} | {item['absolute_reduction']:.4f}x | "
            f"{item['percentage_reduction_from_start']:.2%} |"
        )
    lines.extend(
        [
            "",
            "These are required total reductions, not causal allocations. Body/tail variants show model sensitivity; weighting, duplication, censoring, vintage, fees/carry, gross/net and stage contributions cannot be uniquely decomposed from public aggregates.",
            "",
            "## N=1,000 Gaussian frontier (screening estimates)",
            "",
            "| rho | floor | E[claim]/K | P(claim) | ES99.5 |",
            "|---:|---:|---:|---:|---:|",
        ]
    )
    for row in _selected_frontier_table(frontier, 1000):
        lines.append(
            f"| {row['rho']:.2f} | {row['protection_fraction']:.0%} | "
            f"{row['expected_claim_per_unit']:.2%} | {row['probability_claim']:.2%} | "
            f"{row['claim_es_99.5']:.2%} |"
        )
    lines.extend(
        [
            "",
            "## N=2,000 incremental safety",
            "",
            "| rho | floor | N=1,000 E[claim] | N=2,000 E[claim] | reduction |",
            "|---:|---:|---:|---:|---:|",
        ]
    )
    for rho in (0.1, 0.2, 0.3, 0.4):
        for floor in (0.8, 1.0):
            n1000 = next(
                row
                for row in frontier
                if row["rho"] == rho
                and row["portfolio_size"] == 1000
                and row["protection_fraction"] == floor
            )
            n2000 = next(
                row
                for row in frontier
                if row["rho"] == rho
                and row["portfolio_size"] == 2000
                and row["protection_fraction"] == floor
            )
            lines.append(
                f"| {rho:.2f} | {floor:.0%} | {n1000['expected_claim_per_unit']:.2%} | "
                f"{n2000['expected_claim_per_unit']:.2%} | "
                f"{n1000['expected_claim_per_unit'] - n2000['expected_claim_per_unit']:.2%} |"
            )
    lines.extend(
        [
            "",
            "These are 5,000-path screening comparisons. Under positive shared dependence, idiosyncratic risk diversifies but common-factor state risk remains; the 1,000→2,000 gain is only a few tenths of a percentage point in the displayed cases.",
            "",
            "## N=1,000 breakpoints requested for 80% and 100% floors",
            "",
            "| Floor | E[claim] threshold | rho breakpoint | Status |",
            "|---:|---:|---:|---|",
        ]
    )
    for row in breakpoints:
        if (
            row["portfolio_size"] == 1000
            and row["protection_fraction"] in {0.8, 1.0}
            and row["metric"] == "expected_claim_per_unit"
            and row["threshold"] in {0.025, 0.05, 0.10}
        ):
            value = "outside grid" if row["rho_breakpoint"] is None else f"{row['rho_breakpoint']:.4f}"
            lines.append(
                f"| {row['protection_fraction']:.0%} | {row['threshold']:.1%} | {value} | {row['status']} |"
            )
    lines.extend(
        [
            "",
            "## Correlation versus missing winners",
            "",
            f"At rho=0.20, N=1,000 and a 90% floor, the correlated normal portfolio has E[claim]/K `{deletion_normal['expected_claim_per_unit']:.2%}`. Removing every >=10x winner raises it by `{deletion_10x['incremental_expected_claim_vs_normal']:.2%}` to `{deletion_10x['expected_claim_per_unit']:.2%}`. The shared-dependence effect is already structural before deletion; missing winners is a material additional stress, not a substitute explanation.",
            "",
            "## Dominant model uncertainty",
            "",
            f"Among the `{len(threshold_compatible)}` variants that still meet the rounded threshold tolerances, implied pooled means span `{min(float(row['implied_pooled_mean']) for row in threshold_compatible):.4f}x` to `{max(float(row['implied_pooled_mean']) for row in threshold_compatible):.4f}x`, showing that tail severity/cap and body shape remain material even before dependence. At rho=0.20, N=1,000 and g=90%, the four unfitted dependence families span E[claim]/K `{min(float(row['expected_claim_per_unit']) for row in model_stress):.2%}` to `{max(float(row['expected_claim_per_unit']) for row in model_stress):.2%}`. Dependence family/strength, extreme-tail severity and the unobserved round-to-company weighting dominate current model uncertainty.",
            "",
            "## Falsification and decision relevance",
            "",
            "- Protection that looks nearly free under independence is not robust to moderate shared dependence. Large N cannot diversify a common latent state.",
            "- Winner-deletion stresses show an additional reliance on retaining rare outcomes, but correlated shifts move the whole portfolio and are the more structural obstacle at large N.",
            "- Gaussian, Student-t, macro-mixture and sector-factor results are model-risk stresses, not fitted dependence estimates.",
            "- No current evidence justifies calling 80%–100% protection cheap under realistic dependence. Any such claim would require unusually low dependence, reliable capture of extreme winners, and a better unique-company return dataset.",
            "- The most valuable missing dataset is a licensed row-level panel linking unique company IDs to every financing/check, dated cash flows and valuations, realised/censored status, stage/vintage/geography, and fund fee/carry treatment.",
            "",
            "## Robust conclusions versus model artefacts",
            "",
            "Robust: the source objects are mismatched; the V1 body/tail are underidentified; shared dependence survives diversification; exact mismatch attribution is unavailable. Model artefacts: the precise rho breakpoint, tail-cap sensitivity, macro-state severity, sector allocation and all proxy de-duplication factors.",
            "",
            "See the CSV files and `validation.json` for path counts, Monte Carlo errors, tail observations, interpolation status and audit controls.",
            "",
        ]
    )
    return "\n".join(lines)


def _plot_line(
    rows: list[dict[str, Any]], metric: str, title: str, ylabel: str, path: Path
) -> None:
    fig, ax = plt.subplots(figsize=(8, 5))
    selected = [row for row in rows if row["portfolio_size"] == 100]
    for floor in (0.75, 0.8, 0.9, 1.0):
        series = [row for row in selected if row["protection_fraction"] == floor]
        ax.plot([row["rho"] for row in series], [row[metric] for row in series], label=f"g={floor:.0%}")
    ax.set(xlabel="Gaussian latent-factor rho", ylabel=ylabel, title=title)
    ax.set_xlim(0, 0.4)
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _write_figures(
    directory: Path,
    coherence: list[dict[str, Any]],
    frontier: list[dict[str, Any]],
    saturation: list[dict[str, Any]],
    deletion: list[dict[str, Any]],
    comparison: list[dict[str, Any]],
    mismatch: dict[str, Any],
) -> None:
    _plot_line(frontier, "expected_claim_per_unit", "Expected claim vs dependence", "E[claim] / K", directory / "01_expected_claim_vs_rho.png")
    _plot_line(frontier, "probability_claim", "Claim probability vs dependence", "P(claim)", directory / "02_probability_claim_vs_rho.png")
    _plot_line(frontier, "claim_es_99.5", "ES99.5 vs dependence", "ES99.5 / K", directory / "03_es99_5_vs_rho.png")

    fig, ax = plt.subplots(figsize=(8, 5))
    for rho in (0.0, 0.1, 0.2, 0.3, 0.4):
        series = sorted(
            [row for row in frontier if row["rho"] == rho and row["protection_fraction"] == 0.8],
            key=lambda row: row["portfolio_size"],
        )
        ax.plot([row["portfolio_size"] for row in series], [row["expected_claim_per_unit"] for row in series], marker="o", label=f"rho={rho:.1f}")
    ax.set_xscale("log")
    ax.set(xlabel="Portfolio size N", ylabel="E[claim] / K", title="Expected claim vs portfolio size (80% floor)")
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(directory / "04_expected_claim_vs_n.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    series = [row for row in saturation if row["rho"] == 0.2 and row["protection_fraction"] == 0.8 and row["portfolio_size"] > 50]
    ax.bar([str(row["portfolio_size"]) for row in series], [row["marginal_claim_reduction_from_previous_n"] for row in series])
    ax.set(xlabel="New N", ylabel="Reduction in E[claim] / K", title="Marginal diversification benefit at rho=0.20")
    ax.axhline(0, color="black", linewidth=0.8)
    fig.tight_layout()
    fig.savefig(directory / "05_marginal_benefit_additional_n.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    for floor in (0.75, 0.8, 0.9, 1.0):
        series = [row for row in frontier if row["portfolio_size"] == 1000 and row["protection_fraction"] == floor]
        ax.plot([row["rho"] for row in series], [row["expected_claim_per_unit"] for row in series], label=f"{floor:.0%}")
    ax.set(xlabel="rho", ylabel="E[claim] / K", title="Principal-floor comparison, N=1,000")
    ax.grid(alpha=0.25)
    ax.legend(title="Floor")
    fig.tight_layout()
    fig.savefig(directory / "06_floor_comparison.png", dpi=150)
    plt.close(fig)

    exact = next(row for row in coherence if row["is_exact_v1"])
    fig, ax = plt.subplots(figsize=(8, 5))
    labels = ["V1 pooled", "US pooled", "UK pooled", "V1 N100 median", "UK median"]
    values = [exact["implied_pooled_mean"], 1.95, 1.84, exact["implied_n100_median"], 1.48]
    ax.bar(labels, values)
    ax.set(ylabel="Multiple", title="Model proxy vs fund-level validation objects")
    ax.tick_params(axis="x", rotation=20)
    fig.tight_layout()
    fig.savefig(directory / "07_model_return_vs_fund_targets.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    reductions = mismatch["required_reductions"]
    ax.bar(["to US pooled", "to UK pooled", "median to UK median"], [reductions["us_pooled"]["absolute_reduction"], reductions["uk_pooled"]["absolute_reduction"], reductions["uk_median"]["absolute_reduction"]])
    ax.set(ylabel="Required reduction in multiple", title="Required mismatch reduction (not causal attribution)")
    fig.tight_layout()
    fig.savefig(directory / "08_mismatch_required_reduction.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 5))
    series = [row for row in deletion if row["rho"] == 0.2 and row["portfolio_size"] == 1000 and row["protection_fraction"] == 0.9]
    ax.bar([row["deletion_rule"] for row in series], [row["expected_claim_per_unit"] for row in series])
    ax.set(ylabel="E[claim] / K", title="Winner-deletion impact, rho=0.20, N=1,000, g=90%")
    ax.tick_params(axis="x", rotation=25)
    fig.tight_layout()
    fig.savefig(directory / "09_winner_deletion_rho20.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    series = [row for row in comparison if row["portfolio_size"] == 1000 and row["protection_fraction"] == 0.9]
    ax.bar([row["model_name"] for row in series], [row["expected_claim_per_unit"] for row in series])
    ax.set(ylabel="E[claim] / K", title="Dependence-model stress comparison at rho parameter 0.20")
    ax.tick_params(axis="x", rotation=20)
    fig.tight_layout()
    fig.savefig(directory / "10_gaussian_vs_alternative_dependence.png", dpi=150)
    plt.close(fig)


def run_empirical_coherence_dependence(
    config_path: str | Path, output_directory: str | Path
) -> Path:
    """Run the canonical S2b-a.1 audit and dependence experiments."""

    config_path = Path(config_path)
    config = _load_yaml(config_path)
    repository_root = Path(__file__).resolve().parents[3]
    audit_path = repository_root / str(config["observation_audit_path"])
    audit_rows = load_observation_audit(audit_path)
    spec = _baseline_spec(config)
    spec.validate()

    coherence = _coherence_analysis(config)
    frontier = _dependence_frontier(config, spec)
    breakpoints = _breakpoint_rows(config, frontier)
    saturation = _saturation_rows(frontier)
    deletion = _winner_deletion_rows(config, spec)
    comparison = _model_comparison_rows(config, spec)
    mismatch = _mismatch_payload(config, coherence)

    root = Path(output_directory)
    root.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_directory = root / f"{config['scenario_name']}-{timestamp}-{canonical_hash(config)[:8]}"
    run_directory.mkdir(parents=False, exist_ok=False)
    figures = run_directory / "figures"
    figures.mkdir()

    _write_yaml(run_directory / "config.yaml", config)
    _write_yaml(
        run_directory / "assumptions.yaml",
        {
            "baseline_marginal": config["baseline_marginal"],
            "coherence_proxy_scenarios": config["coherence"],
            "dependence_scenarios": {
                "frontier": config["dependence_frontier"],
                "winner_deletion": config["winner_deletion"],
                "model_comparison": config["dependence_model_comparison"],
            },
            "provenance_limits": config["provenance_limits"],
        },
    )
    _write_csv(run_directory / "unit_of_observation_audit.csv", audit_rows)
    _write_csv(run_directory / "empirical_coherence.csv", coherence)
    _write_csv(run_directory / "dependence_frontier.csv", frontier)
    _write_csv(run_directory / "guarantee_breakpoints.csv", breakpoints)
    _write_csv(run_directory / "portfolio_size_saturation.csv", saturation)
    _write_csv(run_directory / "winner_deletion_correlated.csv", deletion)
    _write_csv(run_directory / "model_comparison.csv", comparison)

    validation = {
        "status": "PASS",
        "observation_rows": len(audit_rows),
        "observation_object_types": sorted(OBSERVATION_OBJECT_TYPES),
        "rho_grid": list(
            build_rho_grid(
                float(config["dependence_frontier"]["rho_start"]),
                float(config["dependence_frontier"]["rho_stop"]),
                float(config["dependence_frontier"]["rho_step"]),
            )
        ),
        "rho_grid_exact": len({row["rho"] for row in frontier}) == 41,
        "mixture_weights_sum": sum(spec.weights.values_for_sampling),
        "old_v1_hashes": {
            "config": file_hash(repository_root / str(config["empirical_v1_config_path"])),
            "constraints": file_hash(
                repository_root / str(config["empirical_constraints_path"])
            ),
            "source_registry": file_hash(repository_root / str(config["source_registry_path"])),
        },
        "monotonic_floor_check": all(
            later["expected_claim_per_unit"] + 1e-15 >= earlier["expected_claim_per_unit"]
            for size in config["dependence_frontier"]["portfolio_sizes"]
            for rho in build_rho_grid(0.0, 0.4, 0.01)
            for earlier, later in zip(
                sorted(
                    [row for row in frontier if row["portfolio_size"] == size and row["rho"] == rho],
                    key=lambda row: row["protection_fraction"],
                )[:-1],
                sorted(
                    [row for row in frontier if row["portfolio_size"] == size and row["rho"] == rho],
                    key=lambda row: row["protection_fraction"],
                )[1:],
            )
        ),
        "central_model_decision": config["provenance_limits"]["central_model_decision"],
        "warnings": [
            "N>100 frontier and breakpoint rows are screening estimates at 5,000 paths.",
            "Dependence parameters and proxy reweightings are not empirically fitted.",
            "Fund TVPI is not silently ingested as investor MOIC.",
        ],
    }
    results = {
        "analysis_version": config["analysis_version"],
        "central_model_decision": config["provenance_limits"]["central_model_decision"],
        "mismatch": mismatch,
        "counts": {
            "coherence_scenarios": len(coherence),
            "frontier_rows": len(frontier),
            "breakpoint_rows": len(breakpoints),
            "saturation_rows": len(saturation),
            "winner_deletion_rows": len(deletion),
            "model_comparison_rows": len(comparison),
        },
        "selected_n100_frontier": _selected_frontier_table(frontier, 100),
        "selected_n1000_frontier": _selected_frontier_table(frontier, 1000),
        "n1000_floor_breakpoints": [
            row
            for row in breakpoints
            if row["portfolio_size"] == 1000
            and row["protection_fraction"] in {0.8, 1.0}
        ],
    }
    _write_json(run_directory / "validation.json", validation)
    _write_json(run_directory / "results.json", results)
    (run_directory / "summary.md").write_text(
        _summary_markdown(
            config,
            coherence,
            frontier,
            breakpoints,
            saturation,
            deletion,
            comparison,
            mismatch,
        ),
        encoding="utf-8",
    )
    _write_figures(figures, coherence, frontier, saturation, deletion, comparison, mismatch)
    _write_json(
        run_directory / "manifest.json",
        {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "git_commit_hash": git_commit_hash(repository_root),
            "git_branch": _git_branch(repository_root),
            "git_worktree_dirty": git_worktree_dirty(repository_root),
            "python_version": platform.python_version(),
            "dependency_lock_hash": file_hash(repository_root / "requirements.lock"),
            "config_source": str(config_path),
            "config_hash": canonical_hash(config),
            "observation_audit_hash": file_hash(audit_path),
            "random_seed": int(config["random_seed"]),
            "analysis_version": config["analysis_version"],
            "artifact_status": "S2b-a.1 model-risk analysis; no refitted central marginal model.",
        },
    )
    return run_directory


def _git_branch(repository_root: Path) -> str | None:
    import subprocess

    try:
        return subprocess.run(
            ["git", "-C", str(repository_root), "branch", "--show-current"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None

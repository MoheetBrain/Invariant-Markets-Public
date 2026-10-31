"""S2b-a empirical terminal-return calibration runner and artifacts."""

from __future__ import annotations

import csv
import json
import platform
import subprocess
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import yaml

from invariant.calibration.constraints import (
    load_empirical_constraints,
    load_source_registry,
)
from invariant.calibration.diagnostics import (
    convergence_diagnostic,
    model_implied_constraint_probabilities,
    sensitivity_ranking,
    tail_beta_from_constraints,
    validate_terminal_constraints,
)
from invariant.calibration.parameter_models import (
    BodySpec,
    CorrelationSpec,
    EmpiricalMixtureSpec,
    MixtureWeights,
    TailSpec,
    derive_mixture_weights,
    target_probabilities_from_constraints,
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
from invariant.reporting.artifacts import (
    canonical_hash,
    file_hash,
    git_commit_hash,
    git_worktree_dirty,
)


def run_empirically_constrained_terminal(
    config_path: str | Path,
    output_directory: str | Path,
) -> Path:
    """Run the canonical S2b-a empirical terminal-return analysis."""

    config_path = Path(config_path)
    config = _load_yaml(config_path)
    repository_root = Path(__file__).resolve().parents[3]
    constraints_path = repository_root / str(config["empirical_constraints_path"])
    registry_path = repository_root / str(config["source_registry_path"])
    registry = load_source_registry(registry_path)
    constraints = load_empirical_constraints(constraints_path, registry)
    weights = derive_mixture_weights(constraints)
    beta_from_constraints = tail_beta_from_constraints(constraints)
    specs = _build_specs(config, weights, beta_from_constraints)
    baseline_spec = specs[str(config["baseline_spec_name"])]

    number_of_paths = int(config["number_of_simulations"])
    random_seed = int(config["random_seed"])
    portfolio_sizes = tuple(int(value) for value in config["portfolio"]["portfolio_sizes"])
    protection_fractions = tuple(
        float(value) for value in config["guarantee"]["protection_fractions"]
    )
    baseline_n = int(config["portfolio"]["baseline_portfolio_size"])
    baseline_g = float(config["guarantee"]["baseline_protection_fraction"])
    grid_spec_names = set(config.get("full_grid_spec_names", [baseline_spec.name]))

    warrant_fraction = empirical_diluted_warrant_fraction(
        float(config["founder_warrant"]["initial_warrant_percentage"]),
        tuple(float(value) for value in config["founder_warrant"]["dilution_percentages"]),
    )
    stop_loss_attachment = float(config["guarantee"]["stop_loss_attachment_fraction"])
    stop_loss_limit = float(config["guarantee"]["stop_loss_limit_fraction"])

    model = EmpiricalTerminalMixtureModel()
    grid_rows: list[dict[str, Any]] = []
    sensitivity_rows: list[dict[str, Any]] = []
    baseline_path_payload: dict[str, Any] | None = None
    baseline_portfolio_for_figures = None

    for spec in specs.values():
        sizes = portfolio_sizes if spec.name in grid_spec_names else (baseline_n,)
        for portfolio_size in sizes:
            portfolio = model.simulate_portfolio(
                spec=spec,
                portfolio_size=portfolio_size,
                number_of_paths=number_of_paths,
                random_seed=random_seed,
            )
            fractions = protection_fractions if spec.name in grid_spec_names else (baseline_g,)
            for protection_fraction in fractions:
                metrics = build_empirical_metrics(
                    portfolio,
                    protection_fraction=protection_fraction,
                    terminal_warrant_fraction=warrant_fraction,
                    stop_loss_attachment=stop_loss_attachment,
                    stop_loss_limit=stop_loss_limit,
                )
                row = {
                    "spec_name": spec.name,
                    "sensitivity_dimension": _spec_dimension(config, spec.name),
                    "portfolio_size": portfolio_size,
                    "protection_fraction": protection_fraction,
                    "body_model": spec.body.name,
                    "tail_mode": spec.tail.mode,
                    "tail_cap": spec.tail.cap,
                    "survival_tail_exponent_beta": spec.tail.survival_tail_exponent_beta,
                    "correlation_model": spec.correlation.model,
                    "rho_macro": spec.correlation.rho_macro,
                    **metrics,
                }
                grid_rows.append(row)
                if portfolio_size == baseline_n and protection_fraction == baseline_g:
                    sensitivity_rows.append(row)
                if (
                    spec.name == baseline_spec.name
                    and portfolio_size == baseline_n
                    and protection_fraction == baseline_g
                ):
                    claims = np.maximum(baseline_g - portfolio.terminal_multiples, 0.0)
                    baseline_path_payload = {
                        "terminal_multiples": _array_to_list(portfolio.terminal_multiples),
                        "guarantee_claims_per_unit": _array_to_list(claims),
                        "largest_share": _array_to_list(portfolio.largest_share),
                        "top3_share": _array_to_list(portfolio.top3_share),
                        "top5_share": _array_to_list(portfolio.top5_share),
                        "hhi": _array_to_list(portfolio.hhi),
                    }
                    baseline_portfolio_for_figures = portfolio

    if baseline_path_payload is None or baseline_portfolio_for_figures is None:
        raise ValueError("baseline empirical grid point was not simulated")

    validation = _validation_payload(
        baseline_spec, constraints, number_of_paths, random_seed
    )
    parameter_draws = draw_parameter_universes(
        constraints,
        number_of_draws=int(config["epistemic_uncertainty"]["number_of_draws"]),
        random_seed=int(config["epistemic_uncertainty"]["random_seed"]),
    )
    parameter_draw_summary = summarize_parameter_draws(parameter_draws)
    nested_epistemic = _nested_epistemic_claim_payload(
        baseline_spec=baseline_spec,
        parameter_draws=parameter_draws,
        portfolio_size=baseline_n,
        protection_fraction=baseline_g,
        inner_paths=int(config["epistemic_uncertainty"]["inner_paths"]),
        random_seed=int(config["epistemic_uncertainty"]["random_seed"]),
        terminal_warrant_fraction=warrant_fraction,
        stop_loss_attachment=stop_loss_attachment,
        stop_loss_limit=stop_loss_limit,
    )
    convergence = convergence_diagnostic(
        baseline_spec,
        portfolio_size=baseline_n,
        protection_fraction=baseline_g,
        path_counts=config["convergence"]["path_counts"],
        random_seed=random_seed,
        terminal_warrant_fraction=warrant_fraction,
        stop_loss_attachment=stop_loss_attachment,
        stop_loss_limit=stop_loss_limit,
    )
    sensitivity = sensitivity_ranking(baseline_spec.name, sensitivity_rows)
    fund_validation = _fund_validation(config, constraints, grid_rows, baseline_spec.name, baseline_n)

    root = Path(output_directory)
    root.mkdir(parents=True, exist_ok=True)
    config_hash = canonical_hash(config)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_directory = root / f"{_safe_name(config['scenario_name'])}-{timestamp}-{config_hash[:8]}"
    counter = 1
    while run_directory.exists():
        run_directory = root / f"{_safe_name(config['scenario_name'])}-{timestamp}-{config_hash[:8]}-{counter}"
        counter += 1
    run_directory.mkdir(parents=True)
    figures_dir = run_directory / "figures"
    figures_dir.mkdir()

    _write_yaml(run_directory / "config.yaml", config)
    _write_yaml(run_directory / "empirical_constraints.yaml", constraints)
    _write_yaml(run_directory / "source_snapshot.yaml", registry)
    _write_json(run_directory / "parameter_draw_summary.json", parameter_draw_summary)
    _write_json(
        run_directory / "validation.json",
        {
            "return_constraint_validation": validation,
            "fund_level_validation": fund_validation,
            "convergence": convergence,
            "nested_epistemic_aleatory": nested_epistemic,
        },
    )
    _write_sensitivity_csv(run_directory / "sensitivity.csv", sensitivity)
    _write_json(
        run_directory / "results.json",
        {
            "model_version": config["model_version"],
            "scenario_name": config["scenario_name"],
            "random_seed": random_seed,
            "number_of_simulations": number_of_paths,
            "baseline_spec_name": baseline_spec.name,
            "baseline_portfolio_size": baseline_n,
            "baseline_protection_fraction": baseline_g,
            "specifications": {name: spec.as_dict() for name, spec in specs.items()},
            "grid_results": grid_rows,
            "baseline_path_outputs": baseline_path_payload,
        },
    )
    (run_directory / "summary.md").write_text(
        _summary_markdown(
            config=config,
            specs=specs,
            grid_rows=grid_rows,
            validation=validation,
            fund_validation=fund_validation,
            sensitivity=sensitivity,
            convergence=convergence,
            nested_epistemic=nested_epistemic,
            baseline_spec=baseline_spec,
            baseline_n=baseline_n,
            baseline_g=baseline_g,
        ),
        encoding="utf-8",
    )
    _write_manifest(
        run_directory=run_directory,
        repository_root=repository_root,
        config=config,
        config_path=config_path,
        constraints_path=constraints_path,
        registry_path=registry_path,
        random_seed=random_seed,
        number_of_paths=number_of_paths,
    )
    _write_figures(
        figures_dir,
        config,
        baseline_spec,
        grid_rows,
        validation,
        convergence,
        baseline_portfolio_for_figures,
        baseline_g,
    )
    return run_directory


def _build_specs(
    config: dict[str, Any], weights, beta_from_constraints: float
) -> dict[str, EmpiricalMixtureSpec]:
    body_specs = {
        item["name"]: BodySpec(name=item["name"])
        for item in config["body_models"]
    }
    tail_exponents = {
        str(item["name"]): (
            beta_from_constraints
            if item["survival_tail_exponent_beta"] == "calibrated_from_constraints"
            else float(item["survival_tail_exponent_beta"])
        )
        for item in config["tail_exponents"]
    }
    tail_variants = {item["name"]: item for item in config["tail_variants"]}
    correlations = {
        item["name"]: CorrelationSpec(
            name=item["name"],
            model=item["model"],
            rho_macro=float(item.get("rho_macro", 0.0)),
            degrees_of_freedom=(
                None
                if item.get("degrees_of_freedom") is None
                else float(item["degrees_of_freedom"])
            ),
        )
        for item in config["correlation_specs"]
    }
    specs: dict[str, EmpiricalMixtureSpec] = {}
    for item in config["model_risk_specifications"]:
        tail_variant = tail_variants[item["tail_variant"]]
        beta = tail_exponents[str(item["tail_exponent"])]
        tail = TailSpec(
            name=tail_variant["name"],
            survival_tail_exponent_beta=beta,
            threshold_u=float(tail_variant.get("threshold_u", 10.0)),
            cap=tail_variant.get("cap"),
            mode=tail_variant["mode"],
        )
        spec = EmpiricalMixtureSpec(
            name=item["name"],
            body=body_specs[item["body_model"]],
            tail=tail,
            correlation=correlations[item["correlation_spec"]],
            weights=weights,
        )
        spec.validate()
        specs[spec.name] = spec
    return specs


def _validation_payload(
    baseline_spec: EmpiricalMixtureSpec,
    constraints: dict[str, Any],
    number_of_paths: int,
    random_seed: int,
) -> dict[str, Any]:
    seed = np.random.SeedSequence([random_seed, 998877, _stable_spec_seed(baseline_spec.name)])
    rng = np.random.default_rng(seed)
    sample_size = min(max(number_of_paths * 20, 250_000), 1_000_000)
    sampled_returns = inverse_terminal_return_cdf(rng.random(sample_size), baseline_spec)
    residuals = validate_terminal_constraints(sampled_returns, constraints)
    return {
        "sample_size": sample_size,
        "baseline_spec": baseline_spec.name,
        "target_probabilities": target_probabilities_from_constraints(constraints),
        "model_implied_probabilities": model_implied_constraint_probabilities(baseline_spec),
        "sampled_residuals": [item.as_dict() for item in residuals],
    }


def _fund_validation(
    config: dict[str, Any],
    constraints: dict[str, Any],
    grid_rows: list[dict[str, Any]],
    baseline_spec_name: str,
    baseline_n: int,
) -> dict[str, Any]:
    targets = constraints["fund_level_validation_targets"]
    baseline_rows = [
        row
        for row in grid_rows
        if row["spec_name"] == baseline_spec_name
        and row["portfolio_size"] == baseline_n
        and row["protection_fraction"] == float(config["guarantee"]["baseline_protection_fraction"])
    ]
    if not baseline_rows:
        raise ValueError("baseline fund-validation row missing")
    row = baseline_rows[0]
    simulated = {
        "construction": "Equal-weighted terminal portfolio MOIC; gross, no fees/carry/follow-on reserves, no valuation smoothing.",
        "simulated_median_tvpi_proxy": row["median_portfolio_multiple"],
        "simulated_pooled_tvpi_proxy": row["expected_portfolio_multiple"],
    }
    comparisons = {}
    for name, target in targets.items():
        value = float(target["value"])
        simulated_value = (
            simulated["simulated_median_tvpi_proxy"]
            if "median" in name
            else simulated["simulated_pooled_tvpi_proxy"]
        )
        comparisons[name] = {
            "target": value,
            "simulated_proxy": simulated_value,
            "difference": simulated_value - value,
            "object_measured": target["object_measured"],
            "provenance": target["provenance"],
            "source_id": target["source_id"],
            "use": "posterior_predictive_validation_only",
        }
    return {"simulated": simulated, "comparisons": comparisons}


def _nested_epistemic_claim_payload(
    baseline_spec: EmpiricalMixtureSpec,
    parameter_draws: tuple[dict[str, Any], ...],
    portfolio_size: int,
    protection_fraction: float,
    inner_paths: int,
    random_seed: int,
    terminal_warrant_fraction: float,
    stop_loss_attachment: float,
    stop_loss_limit: float,
) -> dict[str, Any]:
    model = EmpiricalTerminalMixtureModel()
    rows: list[dict[str, float]] = []
    for index, draw in enumerate(parameter_draws):
        tail = replace(
            baseline_spec.tail,
            survival_tail_exponent_beta=float(draw["survival_tail_exponent_beta"]),
        )
        spec = EmpiricalMixtureSpec(
            name=f"{baseline_spec.name}_theta_{index}",
            body=baseline_spec.body,
            tail=tail,
            correlation=baseline_spec.correlation,
            weights=MixtureWeights(**draw["weights"]),
        )
        portfolio = model.simulate_portfolio(
            spec=spec,
            portfolio_size=portfolio_size,
            number_of_paths=inner_paths,
            random_seed=random_seed + index,
        )
        metrics = build_empirical_metrics(
            portfolio,
            protection_fraction=protection_fraction,
            terminal_warrant_fraction=terminal_warrant_fraction,
            stop_loss_attachment=stop_loss_attachment,
            stop_loss_limit=stop_loss_limit,
        )
        rows.append(
            {
                "theta_index": float(index),
                "expected_claim_per_unit": metrics["expected_guarantee_claim_per_unit"],
                "probability_claim": metrics["probability_nav_below_protected_principal"],
                "var_99_5_per_unit": metrics["guarantee_claim_var_99.5_per_unit"],
                "es_99_5_per_unit": metrics[
                    "guarantee_claim_expected_shortfall_99.5_per_unit"
                ],
            }
        )
    return {
        "outer_draws": len(rows),
        "inner_paths_per_draw": inner_paths,
        "interpretation": "Outer draws vary rounded aggregate constraints within tolerance bands; inner paths simulate aleatory portfolio outcomes conditional on theta.",
        "summary": {
            "expected_claim_per_unit": _quantile_summary(
                [row["expected_claim_per_unit"] for row in rows]
            ),
            "probability_claim": _quantile_summary([row["probability_claim"] for row in rows]),
            "es_99_5_per_unit": _quantile_summary(
                [row["es_99_5_per_unit"] for row in rows]
            ),
        },
        "rows": rows,
    }


def _summary_markdown(
    config: dict[str, Any],
    specs: dict[str, EmpiricalMixtureSpec],
    grid_rows: list[dict[str, Any]],
    validation: dict[str, Any],
    fund_validation: dict[str, Any],
    sensitivity: list[dict[str, Any]],
    convergence: list[dict[str, float]],
    nested_epistemic: dict[str, Any],
    baseline_spec: EmpiricalMixtureSpec,
    baseline_n: int,
    baseline_g: float,
) -> str:
    baseline_row = next(
        row
        for row in grid_rows
        if row["spec_name"] == baseline_spec.name
        and row["portfolio_size"] == baseline_n
        and row["protection_fraction"] == baseline_g
    )
    lines = [
        "# S2b-a empirical terminal-return run",
        "",
        "> This is an empirically constrained terminal marginal model, not a full historical calibration, guarantee quote, insurance premium, regulatory capital model or legal wrapper.",
        "",
        "## Baseline specification",
        "",
        f"- Spec: `{baseline_spec.name}`",
        f"- Body model: `{baseline_spec.body.name}`",
        f"- Tail mode: `{baseline_spec.tail.mode}`",
        f"- Survival tail exponent beta: `{baseline_spec.tail.survival_tail_exponent_beta:.6f}`",
        f"- Correlation: `{baseline_spec.correlation.model}`, rho `{baseline_spec.correlation.rho_macro:.2f}`",
        f"- Paths per simulated grid point: `{int(config['number_of_simulations']):,}`",
        f"- Baseline grid point: `N={baseline_n}`, `g={baseline_g:.0%}`",
        "",
        "## Baseline guarantee outputs",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Expected portfolio MOIC | {baseline_row['expected_portfolio_multiple']:.4f}x |",
        f"| Median portfolio MOIC | {baseline_row['median_portfolio_multiple']:.4f}x |",
        f"| P(claim) | {baseline_row['probability_nav_below_protected_principal']:.4%} |",
        f"| E[claim] / unit | {_fmt_metric(baseline_row['expected_guarantee_claim_per_unit'])} |",
        f"| VaR99.5 / unit | {_fmt_metric(baseline_row['guarantee_claim_var_99.5_per_unit'])} |",
        f"| ES99.5 / unit | {_fmt_metric(baseline_row['guarantee_claim_expected_shortfall_99.5_per_unit'])} |",
        "",
        "## Return-constraint validation",
        "",
        "| Constraint | Target | Simulated | Residual | Tolerance |",
        "|---|---:|---:|---:|---:|",
    ]
    for item in validation["sampled_residuals"]:
        lines.append(
            f"| {item['name']} | {item['target']:.4%} | {item['observed']:.4%} | "
            f"{item['residual']:.4%} | {item['tolerance']:.4%} |"
        )
    lines.extend(
        [
            "",
            "## Model-risk comparison at baseline N/g",
            "",
            "| Spec | Dimension | E[claim] | P(claim) | VaR99.5 | ES99.5 |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    comparison_rows = [
        row
        for row in grid_rows
        if row["portfolio_size"] == baseline_n and row["protection_fraction"] == baseline_g
    ]
    for row in comparison_rows:
        lines.append(
            f"| `{row['spec_name']}` | {row['sensitivity_dimension']} | "
            f"{_fmt_metric(row['expected_guarantee_claim_per_unit'])} | "
            f"{row['probability_nav_below_protected_principal']:.4%} | "
            f"{_fmt_metric(row['guarantee_claim_var_99.5_per_unit'])} | "
            f"{_fmt_metric(row['guarantee_claim_expected_shortfall_99.5_per_unit'])} |"
        )
    lines.extend(
        [
            "",
            "## Fund-level validation",
            "",
            "| Target | External | Simulated proxy | Difference |",
            "|---|---:|---:|---:|",
        ]
    )
    for name, item in fund_validation["comparisons"].items():
        lines.append(
            f"| {name} | {item['target']:.4f} | {item['simulated_proxy']:.4f} | "
            f"{item['difference']:.4f} |"
        )
    lines.extend(
        [
            "",
            "## Top-winner dependence",
            "",
            "| Metric | Value |",
            "|---|---:|",
            f"| Largest winner share | {baseline_row['mean_largest_winner_share']:.4%} |",
            f"| Top 3 share | {baseline_row['mean_top3_share']:.4%} |",
            f"| Top 5 share | {baseline_row['mean_top5_share']:.4%} |",
            f"| E[claim without top 1] | {_fmt_metric(baseline_row['expected_claim_without_top1_per_unit'])} |",
            f"| E[claim without top 3] | {_fmt_metric(baseline_row['expected_claim_without_top3_per_unit'])} |",
            "",
            "## Sensitivity ranking",
            "",
            "| Rank | Spec | Dimension | Impact score |",
            "|---:|---|---|---:|",
        ]
    )
    for index, item in enumerate(sensitivity[:10], start=1):
        lines.append(
            f"| {index} | `{item['spec_name']}` | {item['dimension']} | {item['impact_score']:.4f} |"
        )
    lines.extend(
        [
            "",
            "## Monte Carlo convergence",
            "",
            "| Paths | E[claim] | SE(E[claim]) | VaR99.5 | ES99.5 |",
            "|---:|---:|---:|---:|---:|",
        ]
    )
    for row in convergence:
        lines.append(
            f"| {int(row['paths']):,} | {_fmt_metric(row['expected_claim_per_unit'])} | "
            f"{row['expected_claim_standard_error']:.6f} | "
            f"{_fmt_metric(row['var_99_5_per_unit'])} | {_fmt_metric(row['es_99_5_per_unit'])} |"
        )
    nested_summary = nested_epistemic["summary"]["expected_claim_per_unit"]
    lines.extend(
        [
            "",
            "## Epistemic/aleatory nesting",
            "",
            f"- Outer theta draws: `{nested_epistemic['outer_draws']}`",
            f"- Inner portfolio paths per theta: `{nested_epistemic['inner_paths_per_draw']:,}`",
            f"- E[claim] theta p5/median/p95: `{_fmt_metric(nested_summary['p5'])}` / `{_fmt_metric(nested_summary['median'])}` / `{_fmt_metric(nested_summary['p95'])}`",
        ]
    )
    lines.extend(
        [
            "",
            "## Status",
            "",
            "S2b-a addresses empirically constrained terminal marginals. Full S2b remains not achieved: survival, transitions, macro dynamics, historical bootstrap validation, legal wrapper, risk-carrier pricing and solvency remain outside this run.",
            "",
            "See `validation.json`, `sensitivity.csv`, `source_snapshot.yaml` and the figures for the audit trail.",
            "",
        ]
    )
    return "\n".join(lines)


def _write_figures(
    figures_dir: Path,
    config: dict[str, Any],
    baseline_spec: EmpiricalMixtureSpec,
    grid_rows: list[dict[str, Any]],
    validation: dict[str, Any],
    convergence: list[dict[str, float]],
    baseline_portfolio,
    baseline_g: float,
) -> None:
    _plot_constraint_validation(validation, figures_dir / "empirical_constraints_vs_simulated_distribution.png")
    _plot_grid_metric(
        grid_rows,
        baseline_spec.name,
        "expected_guarantee_claim_per_unit",
        "Expected claim per unit",
        figures_dir / "guarantee_expected_claim_vs_portfolio_n.png",
    )
    _plot_grid_metric(
        grid_rows,
        baseline_spec.name,
        "guarantee_claim_expected_shortfall_99.5_per_unit",
        "ES99.5 per unit",
        figures_dir / "es99_5_vs_portfolio_n.png",
    )
    _plot_grid_metric(
        grid_rows,
        baseline_spec.name,
        "probability_nav_below_protected_principal",
        "P(claim)",
        figures_dir / "claim_probability_vs_portfolio_n.png",
    )
    _plot_sensitivity_line(
        grid_rows,
        "tail_exponent",
        "survival_tail_exponent_beta",
        "Tail exponent beta",
        figures_dir / "guarantee_cost_vs_tail_exponent.png",
    )
    _plot_sensitivity_line(
        grid_rows,
        "correlation",
        "rho_macro",
        "rho_macro",
        figures_dir / "guarantee_cost_vs_correlation.png",
    )
    _plot_protection(
        grid_rows,
        baseline_spec.name,
        int(config["portfolio"]["baseline_portfolio_size"]),
        figures_dir / "guarantee_cost_vs_protection_level.png",
    )
    _plot_histogram(
        baseline_portfolio.largest_share,
        "Largest winner share of terminal NAV",
        "Largest winner share",
        figures_dir / "top_winner_nav_contribution_distribution.png",
    )
    _plot_claim_without_top(
        grid_rows,
        baseline_spec.name,
        int(config["portfolio"]["baseline_portfolio_size"]),
        baseline_g,
        figures_dir / "claim_with_vs_without_top_winner.png",
    )
    _plot_convergence(convergence, figures_dir / "monte_carlo_convergence.png")
    _plot_model_risk_bars(
        grid_rows,
        int(config["portfolio"]["baseline_portfolio_size"]),
        baseline_g,
        figures_dir / "model_risk_comparison_tail_body_variants.png",
    )


def _fmt_metric(value: float) -> str:
    value = float(value)
    if value == 0:
        return "0"
    if abs(value) < 0.001:
        return f"{value:.6f}"
    return f"{value:.4f}"


def _quantile_summary(values: list[float]) -> dict[str, float]:
    array = np.asarray(values, dtype=float)
    return {
        "p5": float(np.quantile(array, 0.05)),
        "median": float(np.quantile(array, 0.5)),
        "p95": float(np.quantile(array, 0.95)),
    }


def _plot_constraint_validation(validation: dict[str, Any], path: Path) -> None:
    labels = [item["name"] for item in validation["sampled_residuals"]]
    targets = [item["target"] for item in validation["sampled_residuals"]]
    observed = [item["observed"] for item in validation["sampled_residuals"]]
    x = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(x - 0.18, targets, width=0.36, label="target")
    ax.bar(x + 0.18, observed, width=0.36, label="simulated")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=20, ha="right")
    ax.set_ylabel("Probability")
    ax.set_title("Empirical return constraints vs simulated marginal")
    ax.grid(axis="y", alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _plot_grid_metric(
    rows: list[dict[str, Any]], spec_name: str, metric: str, ylabel: str, path: Path
) -> None:
    fig, ax = plt.subplots(figsize=(8, 5))
    spec_rows = [row for row in rows if row["spec_name"] == spec_name]
    for protection in sorted({row["protection_fraction"] for row in spec_rows}):
        series = sorted(
            [row for row in spec_rows if row["protection_fraction"] == protection],
            key=lambda row: row["portfolio_size"],
        )
        ax.plot(
            [row["portfolio_size"] for row in series],
            [row[metric] for row in series],
            marker="o",
            label=f"g={protection:.0%}",
        )
    ax.set_xscale("log")
    ax.set_xlabel("Portfolio size N")
    ax.set_ylabel(ylabel)
    ax.set_title(ylabel + " vs portfolio size")
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _plot_sensitivity_line(
    rows: list[dict[str, Any]], dimension: str, x_key: str, xlabel: str, path: Path
) -> None:
    series = sorted(
        [row for row in rows if row.get("sensitivity_dimension") == dimension],
        key=lambda row: row[x_key],
    )
    fig, ax = plt.subplots(figsize=(8, 5))
    if series:
        ax.plot(
            [row[x_key] for row in series],
            [row["expected_guarantee_claim_per_unit"] for row in series],
            marker="o",
        )
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Expected claim per unit")
    ax.set_title("Expected claim sensitivity")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _plot_protection(rows: list[dict[str, Any]], spec_name: str, portfolio_size: int, path: Path) -> None:
    series = sorted(
        [
            row
            for row in rows
            if row["spec_name"] == spec_name and row["portfolio_size"] == portfolio_size
        ],
        key=lambda row: row["protection_fraction"],
    )
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(
        [row["protection_fraction"] for row in series],
        [row["expected_guarantee_claim_per_unit"] for row in series],
        marker="o",
    )
    ax.set_xlabel("Protection fraction g")
    ax.set_ylabel("Expected claim per unit")
    ax.set_title("Expected claim vs protection level")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _plot_histogram(values: np.ndarray, title: str, xlabel: str, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(values, bins=60)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Paths")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _plot_claim_without_top(
    rows: list[dict[str, Any]], spec_name: str, portfolio_size: int, protection: float, path: Path
) -> None:
    row = next(
        item
        for item in rows
        if item["spec_name"] == spec_name
        and item["portfolio_size"] == portfolio_size
        and item["protection_fraction"] == protection
    )
    labels = ["actual", "without top 1", "without top 3"]
    values = [
        row["expected_guarantee_claim_per_unit"],
        row["expected_claim_without_top1_per_unit"],
        row["expected_claim_without_top3_per_unit"],
    ]
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(labels, values)
    ax.set_ylabel("Expected claim per unit")
    ax.set_title("Claim with vs without top winners")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _plot_convergence(convergence: list[dict[str, float]], path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 5))
    paths = [row["paths"] for row in convergence]
    ax.plot(paths, [row["expected_claim_per_unit"] for row in convergence], marker="o", label="E[claim]")
    ax.plot(paths, [row["es_99_5_per_unit"] for row in convergence], marker="o", label="ES99.5")
    ax.set_xscale("log")
    ax.set_xlabel("Paths")
    ax.set_ylabel("Per-unit claim metric")
    ax.set_title("Monte Carlo convergence")
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _plot_model_risk_bars(rows: list[dict[str, Any]], portfolio_size: int, protection: float, path: Path) -> None:
    series = [
        row
        for row in rows
        if row["portfolio_size"] == portfolio_size and row["protection_fraction"] == protection
    ]
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(
        [row["spec_name"] for row in series],
        [row["expected_guarantee_claim_per_unit"] for row in series],
    )
    ax.set_ylabel("Expected claim per unit")
    ax.set_title("Model-risk comparison at baseline N/g")
    ax.tick_params(axis="x", rotation=45)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _write_manifest(
    run_directory: Path,
    repository_root: Path,
    config: dict[str, Any],
    config_path: Path,
    constraints_path: Path,
    registry_path: Path,
    random_seed: int,
    number_of_paths: int,
) -> None:
    manifest = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit_hash": git_commit_hash(repository_root),
        "git_branch": _git_value(repository_root, ["branch", "--show-current"]),
        "git_worktree_dirty": git_worktree_dirty(repository_root),
        "python_version": platform.python_version(),
        "dependency_lock_hash": file_hash(repository_root / "requirements.lock"),
        "config_source": str(config_path),
        "config_hash": canonical_hash(config),
        "constraint_data_hash": file_hash(constraints_path),
        "source_registry_hash": file_hash(registry_path),
        "random_seed": random_seed,
        "simulation_size": number_of_paths,
        "model_version": config["model_version"],
        "artifact_status": "S2b-a empirical terminal marginal run; full S2b not achieved.",
    }
    _write_json(run_directory / "manifest.json", manifest)


def _write_sensitivity_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return data


def _write_yaml(path: Path, value: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(value, handle, sort_keys=False)


def _write_json(path: Path, value: Any) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")


def _array_to_list(values: np.ndarray) -> list[float]:
    return [float(value) for value in values]


def _safe_name(name: str) -> str:
    return "".join(character if character.isalnum() or character in "._-" else "_" for character in name).strip("._") or "run"


def _git_value(repository_root: Path, arguments: list[str]) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repository_root), *arguments],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return completed.stdout.strip()


def _spec_dimension(config: dict[str, Any], spec_name: str) -> str:
    for item in config["model_risk_specifications"]:
        if item["name"] == spec_name:
            return str(item.get("sensitivity_dimension", "model_specification"))
    return "model_specification"


def _stable_spec_seed(name: str) -> int:
    value = 0
    for character in name:
        value = (value * 131 + ord(character)) % (2**32)
    return value

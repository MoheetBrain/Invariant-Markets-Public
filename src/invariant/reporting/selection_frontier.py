"""Artifact serialization and figures for the S2b-a.1 feasibility milestone."""

from __future__ import annotations

import csv
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import yaml

from invariant.economics.platform import PlatformEconomicsInputs, model_platform_economics
from invariant.reporting.artifacts import canonical_hash, file_hash, git_commit_hash, git_worktree_dirty


def write_selection_frontier_artifact(
    *,
    config_path: Path,
    config: dict[str, Any],
    repository_root: Path,
    output_directory: Path,
    registry: dict[str, Any],
    constraints: dict[str, Any],
    plan: tuple[Any, ...],
    results: dict[str, Any],
    failure_rows: list[dict[str, Any]],
    surface_rows: list[dict[str, Any]],
    feasibility_rows: list[dict[str, Any]],
    selection_frontier_rows: list[dict[str, Any]],
    profit_rows: list[dict[str, Any]],
    business_rows: list[dict[str, Any]],
    scoreboard_rows: list[dict[str, Any]],
    valuation_rows: list[dict[str, Any]],
    validation: dict[str, Any],
    risk_rows: list[dict[str, Any]],
    effective_n_rows: list[dict[str, Any]],
    saturation_rows: list[dict[str, Any]],
    comparison: list[dict[str, Any]],
) -> Path:
    """Write the required immutable-style run directory and all audit metadata."""

    timestamp = datetime.now(timezone.utc)
    config_hash = canonical_hash(config)
    run_directory = output_directory / (
        f"selection_frontier_v1-{timestamp.strftime('%Y%m%dT%H%M%SZ')}-{config_hash[:8]}"
    )
    figures_directory = run_directory / "figures"
    figures_directory.mkdir(parents=True, exist_ok=False)

    _write_yaml(run_directory / "config.yaml", config)
    _write_yaml(
        run_directory / "assumptions.yaml",
        {
            "model_version": config["model_version"],
            "interpretation": (
                "Scenario assumptions below are not observations or forecasts. "
                "The empirical terminal evidence remains in its separate frozen source files."
            ),
            "assumptions": config["assumptions"],
        },
    )
    experiment_payload = {
        "model_version": config["model_version"],
        "planned_experiments": [item.as_dict() for item in plan],
        "executed_counts": {
            "core_risk_rows": len(results["core_risk_results"]),
            "selection_dependence_rows": len(surface_rows),
            "tail_sensitivity_rows": len(results["tail_sensitivity_results"]),
            "detailed_dependence_rows": len(results["detailed_dependence_discovery"]),
            "frontier_discovery_rows": len(results["frontier_discovery"]),
            "feasibility_frontier_rows": len(feasibility_rows),
            "selection_frontier_rows": len(selection_frontier_rows),
            "frontier_refinement_rows": len(results["frontier_refinement_checks"]),
            "stress_rows": len(results["stress_tests"]),
        },
        "staging_note": (
            "Core scenarios use >=100,000 paths. Coarse discovery identifies boundaries; "
            "reported canonical checks use the configured refinement path count."
        ),
    }
    _write_yaml(run_directory / "experiment_grid.yaml", experiment_payload)
    _write_json(run_directory / "results.json", results)
    _write_csv(run_directory / "failure_tolerance.csv", failure_rows)
    _write_csv(
        run_directory / "selection_dependence_surface.csv",
        [
            row
            for row in surface_rows
            if row["portfolio_size"]
            == int(config["portfolio"]["canonical_reporting_size"])
            and row["protection_fraction"]
            in {
                float(value)
                for value in config["portfolio"]["surface_protection_fractions"]
            }
        ],
    )
    _write_csv(run_directory / "feasibility_frontier.csv", feasibility_rows)
    _write_csv(run_directory / "selection_skill_frontier.csv", selection_frontier_rows)
    _write_csv(run_directory / "profit_frontier.csv", profit_rows)
    _write_csv(run_directory / "business_scenarios.csv", business_rows)
    _write_csv(run_directory / "platform_scoreboard.csv", scoreboard_rows)
    _write_csv(run_directory / "illustrative_valuation_sensitivity.csv", valuation_rows)
    _write_json(run_directory / "validation.json", validation)

    _write_figures(
        figures_directory,
        config,
        results,
        failure_rows,
        surface_rows,
        risk_rows,
        effective_n_rows,
        profit_rows,
        business_rows,
        scoreboard_rows,
    )
    summary = _summary_markdown(
        config,
        results,
        failure_rows,
        feasibility_rows,
        selection_frontier_rows,
        profit_rows,
        business_rows,
        scoreboard_rows,
        valuation_rows,
        saturation_rows,
        comparison,
        validation,
    )
    (run_directory / "summary.md").write_text(summary, encoding="utf-8")

    artifact_hashes = {
        str(path.relative_to(run_directory)): file_hash(path)
        for path in sorted(run_directory.rglob("*"))
        if path.is_file() and path.name != "manifest.json"
    }
    manifest = {
        "artifact_status": results["artifact_status"],
        "timestamp_utc": timestamp.isoformat(),
        "model_version": config["model_version"],
        "config_source": str(config_path),
        "config_hash": config_hash,
        "assumptions_hash": canonical_hash(config["assumptions"]),
        "experiment_definition_hash": canonical_hash(experiment_payload),
        "source_data_hash": canonical_hash(
            {"source_registry": registry, "empirical_constraints": constraints}
        ),
        "empirical_constraints_file_hash": file_hash(
            repository_root / config["empirical_constraints_path"]
        ),
        "source_registry_file_hash": file_hash(
            repository_root / config["source_registry_path"]
        ),
        "dependency_lock_hash": file_hash(repository_root / "requirements.lock"),
        "git_commit_hash": git_commit_hash(repository_root),
        "git_branch": _git_branch(repository_root),
        "git_worktree_dirty": git_worktree_dirty(repository_root),
        "python_version": platform.python_version(),
        "random_seed": int(config["simulation"]["random_seed"]),
        "path_counts": {
            key: value
            for key, value in config["simulation"].items()
            if key.endswith("paths") or key == "convergence_path_counts"
        },
        "numerical_results_hash": canonical_hash(results),
        "validation_hash": canonical_hash(validation),
        "artifact_file_hashes": artifact_hashes,
    }
    _write_json(run_directory / "manifest.json", manifest)
    return run_directory


def _summary_markdown(
    config: dict[str, Any],
    results: dict[str, Any],
    failure_rows: list[dict[str, Any]],
    feasibility_rows: list[dict[str, Any]],
    selection_frontier_rows: list[dict[str, Any]],
    profit_rows: list[dict[str, Any]],
    business_rows: list[dict[str, Any]],
    scoreboard_rows: list[dict[str, Any]],
    valuation_rows: list[dict[str, Any]],
    saturation_rows: list[dict[str, Any]],
    comparison: list[dict[str, Any]],
    validation: dict[str, Any],
) -> str:
    core = results["core_risk_results"]
    reporting_size = int(config["portfolio"]["canonical_reporting_size"])
    reporting_floor = float(config["portfolio"]["canonical_reporting_floor"])
    surface_floors = tuple(
        float(value) for value in config["portfolio"]["surface_protection_fractions"]
    )
    sizes = tuple(int(value) for value in config["portfolio"]["sizes"])
    failure_table_sizes = sizes[-2:]
    refinement_target = float(
        config["frontiers"]["canonical_refinement_expected_claim_target"]
    )
    lines = [
        "# S2b-a.1 selection and portfolio feasibility frontier",
        "",
        "> This is an adversarial scenario feasibility study. Selection skill, dependence, external protection prices, demand, founder acceptance, fees, costs, and valuation multiples are not empirical facts. No output is a guarantee, insurance quote, capital requirement, forecast, or company valuation.",
        "",
        "## A. Freeze status",
        "",
        "The run records the Git commit, branch, and dirty state in `manifest.json`. The validation payload checks that `configs/base.yaml` still matches `v0.2.0-s2a` and `configs/calibrated_terminal_v1.yaml` still matches `v0.3.0-s2b-a`.",
        "",
        "## B. Mathematical model",
        "",
        "- `NAV_T = K * sum_i(w_i X_i)`, with `sum_i w_i=1` and baseline `w_i=1/N`.",
        "- `c_T = max(g - NAV_T/K, 0)`; a floor breach does not require every company to fail.",
        "- Failure arithmetic: `MOIC=(F/N)r_f+(1-F/N)m`, so `F/N <= (m-g)/(m-r_f)` when `m>r_f`.",
        "- Target selection renormalizes the five frozen S2b-a bands to explicit `P(X<1)` and `P(X>=10)` targets.",
        "- Smooth selection uses `p_s(x) proportional to p_0(x) exp(s log(1+x))`; `s=0` is exactly the base inverse CDF.",
        "- Dependence uses `Z_i=sqrt(rho_macro)M+sqrt(rho_sector)S_sector(i)+sqrt(1-rho_macro-rho_sector)epsilon_i`, `U_i=Phi(Z_i)`, `X_i=F_s^-1(U_i)`.",
        "- For large N, conditional idiosyncratic noise contracts and common macro/sector states dominate the portfolio mean.",
        "",
        "## C. Failure-tolerance table",
        "",
        "Complete failures below assume `r_f=0`; each cell is `maximum failures (percentage)`.",
        "",
    ]
    lines.extend(
        _failure_table_markdown(
            failure_rows,
            failure_table_sizes[0],
            tuple(float(value) for value in config["portfolio"]["protection_fractions"]),
        )
    )
    lines.extend(["", f"For N={failure_table_sizes[1]:,}:", ""])
    lines.extend(
        _failure_table_markdown(
            failure_rows,
            failure_table_sizes[1],
            tuple(float(value) for value in config["portfolio"]["protection_fractions"]),
        )
    )

    lines.extend(
        [
            "",
            "If survivor MOIC is below the floor, even zero failures are insufficient; the CSV records a blank maximum rather than incorrectly reporting zero.",
            "",
            "## D-G. Selection, portfolios, dependence, and risk",
            "",
            f"Core results at N={reporting_size:,}:",
            "",
            "| Portfolio | Floor | E[MOIC] | P(claim) | E[claim]/K | ES99.5/K | Top-1 share | Claim without top 3 |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for construction in (
        "broad_venture",
        "hyper_selected_ai",
        "hyper_selected_frontier",
    ):
        for floor in surface_floors:
            row = _one(
                core,
                portfolio_construction=construction,
                portfolio_size=reporting_size,
                protection_fraction=floor,
            )
            lines.append(
                f"| {construction} | {floor:.0%} | {row['expected_portfolio_multiple']:.3f}x | "
                f"{row['probability_claim']:.2%} | {row['expected_claim_per_unit']:.3%} | "
                f"{row['claim_es_99.5_per_unit']:.3%} | "
                f"{row['mean_largest_winner_nav_share']:.2%} | "
                f"{row['expected_claim_without_top3_per_unit']:.3%} |"
            )

    lines.extend(
        [
            "",
            "## H. Selection x dependence surface",
            "",
            f"`selection_dependence_surface.csv` reports E[claim], P(claim), and ES99.5 for every target selection level and low/medium/high/extreme dependence at N={reporting_size:,} for "
            f"{' and '.join(f'{floor:.0%}' for floor in surface_floors)} floors, separately for AI-only and frontier-diversified portfolios.",
            "",
            "## I. Portfolio-size saturation",
            "",
            f"The {sizes[-2]:,}-to-{sizes[-1]:,} matched-path increments are:",
            "",
            "| Portfolio | Floor | Delta E[claim] | Delta ES99.5 | Benefit per +100 | Saturated by configured threshold? |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in saturation_rows:
        if row["from_portfolio_size"] == sizes[-2]:
            lines.append(
                f"| {row['portfolio_construction']} | {row['protection_fraction']:.0%} | "
                f"{row['delta_expected_claim_per_unit']:.3%} | "
                f"{row['delta_es_99.5_per_unit']:.3%} | "
                f"{row['protection_benefit_per_additional_100_companies']:.4%} | "
                f"{row['absolute_benefit_below_materiality_threshold']} |"
            )

    lines.extend(
        [
            "",
            "## J-K. Floor height and power-law winner dependence",
            "",
            f"The core table and `results.json` compare {', '.join(f'{float(floor):.0%}' for floor in config['portfolio']['protection_fractions'])} floors. `claim_actual`, `claim_without_top1`, and `claim_without_top3` are calculated on identical paths. Tail caps, truncation, unbounded Pareto, and no-mega-winner cases are reported separately rather than blended.",
            "",
            "## L. Maximum tolerable dependence",
            "",
            f"Coarse frontiers use the configured dependence path, monotone denoising, and linear interpolation. Selected canonical {refinement_target:.1%} boundaries receive {int(config['simulation']['frontier_refinement_paths']):,}-path checks; every other boundary remains explicitly coarse discovery.",
            "",
            "| Portfolio | Selection | N | Floor | Target E[claim] | Dependence boundary | Macro rho | Sector rho | Status |",
            "|---|---|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for construction, selection in (
        ("broad_venture", "unselected"),
        ("hyper_selected_ai", "hyper"),
        ("hyper_selected_frontier", "hyper"),
    ):
        row = _frontier_row(
            feasibility_rows,
            construction,
            selection,
            config["baseline_tail_model"],
            reporting_size,
            reporting_floor,
            "expected_claim_per_unit",
            refinement_target,
        )
        lines.append(
            f"| {construction} | {selection} | {reporting_size:,} | "
            f"{reporting_floor:.0%} | {refinement_target:.1%} | "
            f"{_fmt_optional(row['dependence_index_boundary'], '.3f')} | "
            f"{_fmt_optional(row['rho_macro_boundary'], '.3f')} | "
            f"{_fmt_optional(row['rho_sector_boundary'], '.3f')} | {row['status']} |"
        )

    lines.extend(
        [
            "",
            "## M. Required selection skill",
            "",
            "`selection_skill_frontier.csv` inverts both selection models. Target-constrained rows report required `P(X<1)` and `P(X>=10)`; smooth rows report required `s*`. `unreachable` means the configured skill range is insufficient, not that the target is impossible under every model.",
            "",
            "## N. Platform economics",
            "",
            "- `OriginationRevenue = NewProtectedCapital * f_origin`.",
            "- `ServiceRevenue = AvgOutstandingProtectedCapital * f_service`.",
            "- `GuaranteeMargin = ProtectedCapitalCharged * max(investor fee - external price - risk admin, 0)`.",
            "- `WarrantRevenue = realized attributable warrant proceeds * PlatformCo retained share`.",
            "- `ModeledOperatingProfit = total revenue - variable operating cost - fixed operating cost`.",
            "- Guarantee claims are excluded because the canonical PlatformCo is not the risk bearer.",
            "",
            "## O-Q. Profit, demand, and founder-supply frontiers",
            "",
            "All values are scenario mathematics. `profit_frontier.csv` solves required annual issuance, minimum demand uplift, and maximum external protection price. Founder acceptance multiplies offered capital and therefore directly caps deployable issuance.",
            "",
            "Canonical external-price/fixed-cost issuance requirements:",
            "",
            "| Target modeled annual profit | Required annual protected issuance |",
            "|---:|---:|",
        ]
    )
    canonical = config["platform_economics"]["canonical"]
    for target in config["platform_economics"]["target_annual_profits"]:
        candidates = [
            row
            for row in profit_rows
            if row["frontier_type"] == "required_annual_protected_issuance"
            and row["external_protection_price"]
            == float(canonical["external_risk_provider_price"])
            and row["fixed_operating_cost"]
            == float(canonical["fixed_annual_operating_cost"])
            and row["target_modeled_operating_profit"] == float(target)
        ]
        if candidates:
            lines.append(
                f"| GBP {target/1e6:,.0f}m | {_fmt_gbp(candidates[0]['boundary_value'])} |"
            )

    lines.extend(
        [
            "",
            "## R. G/U/Q/K/R/P scoreboard",
            "",
            "| Portfolio | G | U | Q | K proxy (ES99.5) | R | P |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in scoreboard_rows:
        lines.append(
            f"| {row['portfolio_construction']} | {row['G_external_protection_cost_per_unit']:.2%} | "
            f"{row['U_investor_demand_uplift']:.2f}x | "
            f"{row['Q_founder_economic_contribution_per_unit']:.2%} | "
            f"{row['K_risk_capital_proxy_per_unit']:.2%} | "
            f"{row['R_platform_revenue_per_unit_issuance']:.2%} | "
            f"{row['P_modeled_profit_per_unit_issuance']:.2%} |"
        )

    max_valuation = max(
        (float(row["illustrative_enterprise_value"]) for row in valuation_rows),
        default=0.0,
    )
    lines.extend(
        [
            "",
            "## S. Illustrative valuation sensitivity",
            "",
            f"Year-10 scenario revenue/profit multiples produce a maximum arithmetic enterprise value of {_fmt_gbp(max_valuation)}. This is labelled `ILLUSTRATIVE_VALUATION_MULTIPLE`; it is not a market comp, financing valuation, or statement that Invariant is worth that amount. Thresholds above GBP 100m, GBP 1bn, or GBP 10bn require the corresponding modeled revenue/profit and configured multiple to coexist.",
            "",
            "## T-U. Tests and assumptions",
            "",
            f"Run-level validation passed: `{validation['overall_passed']}`. Exact repository test count is reported after the milestone test suite runs, not inferred by this artifact. `assumptions.yaml` contains {validation['assumption_count']} scenario families with value, unit, meaning, provenance, reason, mathematical role, sensitivity, and replacement evidence.",
            "",
            "## V. Falsification",
            "",
        ]
    )
    stress_risk = [
        row
        for row in results["stress_tests"]
        if row.get("domain") == "risk"
        and row.get("protection_fraction") == reporting_floor
    ]
    worst = max(stress_risk, key=lambda row: float(row["expected_claim_per_unit"]))
    comparison_100 = next(
        row for row in comparison if row["protection_fraction"] == reporting_floor
    )
    lines.extend(
        [
            f"The strongest modeled risk stress is `{worst['stress_name']}` with E[claim]/K={worst['expected_claim_per_unit']:.2%} and P(claim)={worst['probability_claim']:.2%}. Dependence can erase large-N idiosyncratic diversification. At held medium factor coefficients, the AI concentration penalty versus frontier diversification is {comparison_100['ai_concentration_penalty_vs_frontier_medium']:.2%} of principal in expected claim. Commercial viability also fails when contribution margin is non-positive, demand remains 1x, founder acceptance contracts, or external pricing consumes the arrangement margin.",
            "",
            "## Core questions answered",
            "",
            f"1. Exact N={failure_table_sizes[0]:,} complete-failure counts appear in section C for each survivor MOIC and floor.",
            "2. Higher survivor MOIC raises failure tolerance according to the exact formula.",
            f"3. N={failure_table_sizes[1]:,} changes counts at the same percentage boundaries, subject to integer flooring.",
            f"4. Section I reports where the {sizes[-2]:,}-to-{sizes[-1]:,} marginal benefit falls below the configured threshold.",
            "5. Required downside and tail improvements are inverted in `selection_skill_frontier.csv`.",
            "6. Hyper-selected AI versus broad venture is quantified in `selection_vs_concentration`; no universal superiority is assumed.",
            "7. AI-only versus frontier diversification is compared at held factor coefficients.",
            "8. At large N, macro and sector factors dominate idiosyncratic failure; winner capture and selection still shift the marginal.",
            "9. Dependence boundaries for 75%, 90%, and 100% floors are in `feasibility_frontier.csv`.",
            "10. The selection inversion identifies when a 100% floor reaches 1%, 2.5%, or 5% expected claim targets.",
            "11. Top-1 and top-3 removal claims are reported on identical paths.",
            "12. Platform break-even depends on explicit fee, price, warrant, cost, demand, and founder scenarios.",
            "13. GBP 10m/50m/100m/500m profit issuance requirements are reported above and in the CSV.",
            "14. Maximum tolerable external price is solved by issuance scale and target profit.",
            "15. Minimum required demand uplift is solved by price, acceptance, and profit target.",
            "16. Founder acceptance and warrant attribution are explicit constraints, not empirical facts.",
            "17. GBP 10m/100m/1bn revenue scale is reachable only where a configured issuance/fee scenario crosses that threshold.",
            "18. Enterprise values above GBP 100m/1bn/10bn require sufficient modeled revenue or profit and an illustrative multiple; none is claimed as likely.",
            "",
            "## W. Single next move",
            "",
            "Build one timestamped, out-of-sample underwriting backtest dataset linking only investment-time information and selection decisions to investor-level terminal or censored MOIC for selected and rejected companies.",
        ]
    )
    return "\n".join(lines) + "\n"


def _write_figures(
    directory: Path,
    config: dict[str, Any],
    results: dict[str, Any],
    failure_rows: list[dict[str, Any]],
    surface_rows: list[dict[str, Any]],
    risk_rows: list[dict[str, Any]],
    effective_n_rows: list[dict[str, Any]],
    profit_rows: list[dict[str, Any]],
    business_rows: list[dict[str, Any]],
    scoreboard_rows: list[dict[str, Any]],
) -> None:
    core = results["core_risk_results"]
    reporting_size = int(config["portfolio"]["canonical_reporting_size"])
    reporting_floor = float(config["portfolio"]["canonical_reporting_floor"])
    failure_display_size = tuple(int(value) for value in config["portfolio"]["sizes"])[-2]
    selection_order = [
        item["name"] for item in config["selection"]["target_constraint_scenarios"]
    ]
    colors = plt.get_cmap("tab10")

    # 1-2. Matched-N selection curves use the medium frontier-diversified surface.
    selection_size = [
        row
        for row in surface_rows
        if row["portfolio_construction"] == "hyper_selected_frontier"
        and row["dependence_level"] == "medium"
        and row["protection_fraction"] == reporting_floor
    ]
    for metric, filename, ylabel in (
        ("expected_claim_per_unit", "01_expected_claim_vs_n_by_selection.png", "Expected claim / principal"),
        ("claim_es_99.5_per_unit", "02_es99_5_vs_n_by_selection.png", "ES99.5 / principal"),
    ):
        fig, ax = plt.subplots(figsize=(8, 5))
        for index, selection in enumerate(selection_order):
            rows = sorted(
                (row for row in selection_size if row["selection_level"] == selection),
                key=lambda row: row["portfolio_size"],
            )
            ax.plot(
                [row["portfolio_size"] for row in rows],
                [row[metric] for row in rows],
                marker="o",
                label=selection,
                color=colors(index),
            )
        _finish_axis(ax, "Portfolio size under medium dependence", "Companies", ylabel, percent_y=True)
        ax.legend(ncol=2, fontsize=8)
        fig.tight_layout()
        fig.savefig(directory / filename, dpi=160)
        plt.close(fig)

    # 3. Dependence response.
    fig, ax = plt.subplots(figsize=(8, 5))
    for construction, marker in (("hyper_selected_ai", "o"), ("hyper_selected_frontier", "s")):
        rows = [
            row
            for row in surface_rows
            if row["portfolio_construction"] == construction
            and row["selection_level"] == "hyper"
            and row["portfolio_size"] == reporting_size
            and row["protection_fraction"] == reporting_floor
        ]
        rows.sort(key=lambda row: row["rho_macro"] + row["rho_sector"])
        ax.plot(
            [row["rho_macro"] + row["rho_sector"] for row in rows],
            [row["expected_claim_per_unit"] for row in rows],
            marker=marker,
            label=construction,
        )
    _finish_axis(ax, "Expected claim versus latent dependence", "rho_macro + rho_sector", "Expected claim / principal", percent_y=True)
    ax.legend()
    fig.tight_layout()
    fig.savefig(directory / "03_expected_claim_vs_dependence.png", dpi=160)
    plt.close(fig)

    # 4. Selection response.
    fig, ax = plt.subplots(figsize=(8, 5))
    for construction in ("hyper_selected_ai", "hyper_selected_frontier"):
        rows = [
            row
            for row in surface_rows
            if row["portfolio_construction"] == construction
            and row["dependence_level"] == "medium"
            and row["portfolio_size"] == reporting_size
            and row["protection_fraction"] == reporting_floor
        ]
        rows.sort(key=lambda row: selection_order.index(row["selection_level"]))
        ax.plot(
            range(len(rows)),
            [row["expected_claim_per_unit"] for row in rows],
            marker="o",
            label=construction,
        )
    ax.set_xticks(range(len(selection_order)), selection_order, rotation=25, ha="right")
    _finish_axis(ax, "Expected claim versus hypothetical selection", "Selection scenario", "Expected claim / principal", percent_y=True)
    ax.legend()
    fig.tight_layout()
    fig.savefig(directory / "04_expected_claim_vs_selection.png", dpi=160)
    plt.close(fig)

    # 5. Selection-dependence heatmap.
    dependence_order = list(config["dependence"]["levels"])
    matrix = np.zeros((len(selection_order), len(dependence_order)))
    for i, selection in enumerate(selection_order):
        for j, dependence in enumerate(dependence_order):
            matrix[i, j] = _one(
                surface_rows,
                portfolio_construction="hyper_selected_ai",
                selection_level=selection,
                dependence_level=dependence,
                portfolio_size=reporting_size,
                protection_fraction=reporting_floor,
            )["expected_claim_per_unit"]
    fig, ax = plt.subplots(figsize=(7, 6))
    image = ax.imshow(matrix, cmap="viridis", aspect="auto", vmin=0)
    ax.set_xticks(range(len(dependence_order)), dependence_order)
    ax.set_yticks(range(len(selection_order)), selection_order)
    ax.set_xlabel("Dependence scenario")
    ax.set_ylabel("Selection scenario")
    ax.set_title("AI-only expected claim / principal")
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            ax.text(j, i, f"{matrix[i, j]:.1%}", ha="center", va="center", color="white" if matrix[i, j] > matrix.max() / 2 else "black")
    fig.colorbar(image, ax=ax, label="Expected claim / principal")
    fig.tight_layout()
    fig.savefig(directory / "05_selection_dependence_heatmap.png", dpi=160)
    plt.close(fig)

    # 6. Three primary portfolios.
    fig, ax = plt.subplots(figsize=(8, 5))
    labels = ["Broad venture", "Hyper AI", "Hyper frontier"]
    constructions = ["broad_venture", "hyper_selected_ai", "hyper_selected_frontier"]
    values = [
        _one(
            core,
            portfolio_construction=name,
            portfolio_size=reporting_size,
            protection_fraction=reporting_floor,
        )[
            "expected_claim_per_unit"
        ]
        for name in constructions
    ]
    ax.bar(labels, values, color=[colors(7), colors(3), colors(2)])
    _finish_axis(ax, "Guarantee risk: broad, AI-only, and frontier", "Portfolio", "Expected claim / principal", percent_y=True)
    fig.tight_layout()
    fig.savefig(directory / "06_ai_vs_frontier_risk.png", dpi=160)
    plt.close(fig)

    # 7. Floor comparison.
    fig, ax = plt.subplots(figsize=(8, 5))
    for index, floor in enumerate(config["portfolio"]["protection_fractions"]):
        rows = sorted(
            (
                row
                for row in core
                if row["portfolio_construction"] == "hyper_selected_frontier"
                and row["protection_fraction"] == float(floor)
            ),
            key=lambda row: row["portfolio_size"],
        )
        ax.plot(
            [row["portfolio_size"] for row in rows],
            [row["expected_claim_per_unit"] for row in rows],
            marker="o",
            label=f"{float(floor):.0%} floor",
            color=colors(index),
        )
    _finish_axis(ax, "Principal-floor comparison", "Companies", "Expected claim / principal", percent_y=True)
    ax.legend()
    fig.tight_layout()
    fig.savefig(directory / "07_floor_comparison.png", dpi=160)
    plt.close(fig)

    # 8. Exact failure tolerance.
    fig, ax = plt.subplots(figsize=(8, 5))
    for index, floor in enumerate(config["portfolio"]["protection_fractions"]):
        rows = sorted(
            (
                row
                for row in failure_rows
                if row["portfolio_size"] == failure_display_size
                and row["failure_recovery_multiple"] == 0.0
                and row["protection_fraction"] == float(floor)
                and row["maximum_failure_percentage"] is not None
            ),
            key=lambda row: row["survivor_multiple"],
        )
        ax.plot(
            [row["survivor_multiple"] for row in rows],
            [row["maximum_failure_percentage"] / 100 for row in rows],
            marker="o",
            label=f"{float(floor):.0%} floor",
            color=colors(index),
        )
    _finish_axis(ax, f"Failure tolerance at N={failure_display_size:,} and zero recovery", "Average survivor MOIC", "Maximum complete-failure share", percent_y=True)
    ax.legend()
    fig.tight_layout()
    fig.savefig(directory / "08_failure_tolerance_vs_survivor_moic.png", dpi=160)
    plt.close(fig)

    # 9. Effective N intuition.
    fig, ax = plt.subplots(figsize=(8, 5))
    for rho in sorted({row["equal_correlation"] for row in effective_n_rows}):
        rows = sorted(
            (row for row in effective_n_rows if row["equal_correlation"] == rho),
            key=lambda row: row["actual_portfolio_size"],
        )
        ax.plot(
            [row["actual_portfolio_size"] for row in rows],
            [row["effective_portfolio_size"] for row in rows],
            marker="o",
            label=f"rho={rho:g}",
        )
    _finish_axis(ax, "Linear equal-correlation effective N", "Actual N", "Effective N", percent_y=False)
    ax.legend(ncol=2, fontsize=8)
    fig.tight_layout()
    fig.savefig(directory / "09_effective_n_vs_actual_n.png", dpi=160)
    plt.close(fig)

    # 10. Winner removal.
    fig, ax = plt.subplots(figsize=(8, 5))
    x = np.arange(len(constructions))
    metrics = (
        ("expected_claim_actual_per_unit", "Actual"),
        ("expected_claim_without_top1_per_unit", "Without top 1"),
        ("expected_claim_without_top3_per_unit", "Without top 3"),
    )
    width = 0.25
    for index, (metric, label) in enumerate(metrics):
        values = [
            _one(
                core,
                portfolio_construction=name,
                portfolio_size=reporting_size,
                protection_fraction=reporting_floor,
            )[metric]
            for name in constructions
        ]
        ax.bar(x + (index - 1) * width, values, width=width, label=label)
    ax.set_xticks(x, labels)
    _finish_axis(ax, "Principal-floor claim after removing winners", "Portfolio", "Expected claim / principal", percent_y=True)
    ax.legend()
    fig.tight_layout()
    fig.savefig(directory / "10_claim_without_top_winners.png", dpi=160)
    plt.close(fig)

    # 11. Tail sensitivity.
    tail_rows = [
        row
        for row in results["tail_sensitivity_results"]
        if row["portfolio_construction"] == "hyper_selected_frontier"
        and row["protection_fraction"] == reporting_floor
    ]
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(
        [row["tail_model"] for row in tail_rows],
        [row["expected_claim_per_unit"] for row in tail_rows],
        color=[colors(index) for index in range(len(tail_rows))],
    )
    ax.tick_params(axis="x", rotation=25)
    _finish_axis(ax, "Tail-model sensitivity", "Tail model", "Expected claim / principal", percent_y=True)
    fig.tight_layout()
    fig.savefig(directory / "11_tail_model_sensitivity.png", dpi=160)
    plt.close(fig)

    _write_business_figures(
        directory,
        config,
        business_rows,
        profit_rows,
        scoreboard_rows,
    )


def _write_business_figures(
    directory: Path,
    config: dict[str, Any],
    business_rows: list[dict[str, Any]],
    profit_rows: list[dict[str, Any]],
    scoreboard_rows: list[dict[str, Any]],
) -> None:
    chart_specs = (
        (
            "protected_issuance",
            "annual_protected_issuance",
            "12_profit_vs_protected_issuance.png",
            "Modeled annual profit versus protected issuance",
            "Annual protected issuance (GBP)",
        ),
        (
            "external_protection_price",
            "external_protection_price_rate",
            "13_profit_vs_external_price.png",
            "Modeled annual profit versus external protection price",
            "External protection price",
        ),
        (
            "investor_demand_uplift",
            "demand_uplift",
            "14_profit_vs_demand_uplift.png",
            "Modeled annual profit versus investor demand uplift",
            "Demand uplift multiple",
        ),
    )
    for family, x_field, filename, title, xlabel in chart_specs:
        rows = [row for row in business_rows if row["scenario_family"] == family]
        rows.sort(key=lambda row: row[x_field])
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.plot(
            [row[x_field] for row in rows],
            [row["modeled_operating_profit"] for row in rows],
            marker="o",
            color="#287271",
        )
        ax.axhline(0, color="black", linewidth=0.8)
        ax.set_title(title)
        ax.set_xlabel(xlabel)
        ax.set_ylabel("Modeled annual operating profit (GBP)")
        ax.grid(alpha=0.25)
        fig.tight_layout()
        fig.savefig(directory / filename, dpi=160)
        plt.close(fig)

    # 15. Break-even issuance by external price and profit target.
    canonical = config["platform_economics"]["canonical"]
    rows = [
        row
        for row in profit_rows
        if row["frontier_type"] == "required_annual_protected_issuance"
        and row["fixed_operating_cost"] == float(canonical["fixed_annual_operating_cost"])
        and row["boundary_value"] is not None
    ]
    fig, ax = plt.subplots(figsize=(8, 5))
    for target in sorted({row["target_modeled_operating_profit"] for row in rows}):
        subset = sorted(
            (row for row in rows if row["target_modeled_operating_profit"] == target),
            key=lambda row: row["external_protection_price"],
        )
        ax.plot(
            [row["external_protection_price"] for row in subset],
            [row["boundary_value"] for row in subset],
            marker="o",
            label=f"GBP {target/1e6:g}m target",
        )
    ax.set_title("Break-even protected issuance")
    ax.set_xlabel("External protection price")
    ax.set_ylabel("Required annual protected issuance (GBP)")
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(directory / "15_break_even_protected_issuance.png", dpi=160)
    plt.close(fig)

    # 16. Issuance-price profit matrix around canonical commercial assumptions.
    economics = config["platform_economics"]
    q = float(scoreboard_rows[-1]["Q_founder_economic_contribution_per_unit"])
    issuance_grid = [float(value) for value in economics["annual_new_protected_capital"]]
    price_grid = [float(value) for value in economics["external_risk_provider_prices"]]
    matrix = np.zeros((len(price_grid), len(issuance_grid)))
    maturity = float(economics["ten_year"]["maturity_years"])
    for i, price in enumerate(price_grid):
        for j, issuance in enumerate(issuance_grid):
            matrix[i, j] = model_platform_economics(
                PlatformEconomicsInputs(
                    new_protected_capital=issuance,
                    average_outstanding_protected_capital=issuance * maturity,
                    protected_capital_charged=issuance,
                    origination_fee_rate=float(canonical["origination_fee_rate"]),
                    annual_service_fee_rate=float(canonical["annual_service_fee_rate"]),
                    investor_protection_fee_rate=float(canonical["investor_protection_fee_rate"]),
                    external_risk_provider_price_rate=price,
                    variable_risk_admin_cost_rate=float(economics["variable_risk_admin_cost_rate"]),
                    founder_warrant_value_per_new_capital=q,
                    platform_warrant_share=float(canonical["platform_warrant_share"]),
                    variable_operating_cost_rate=float(canonical["variable_operating_cost_rate"]),
                    fixed_operating_cost=float(canonical["fixed_annual_operating_cost"]),
                )
            ).modeled_operating_profit
    fig, ax = plt.subplots(figsize=(9, 5))
    bound = max(abs(float(matrix.min())), abs(float(matrix.max())))
    image = ax.imshow(matrix, cmap="RdYlGn", aspect="auto", vmin=-bound, vmax=bound)
    ax.set_xticks(range(len(issuance_grid)), [f"{value/1e9:g}bn" if value >= 1e9 else f"{value/1e6:g}m" for value in issuance_grid], rotation=30)
    ax.set_yticks(range(len(price_grid)), [f"{value:.1%}" for value in price_grid])
    ax.set_xlabel("Annual protected issuance (GBP)")
    ax.set_ylabel("External protection price")
    ax.set_title("Modeled annual profit potential matrix")
    fig.colorbar(image, ax=ax, label="Modeled annual operating profit (GBP)")
    fig.tight_layout()
    fig.savefig(directory / "16_profit_potential_matrix.png", dpi=160)
    plt.close(fig)

    # 17. Six-number scoreboard table avoids mixing U multiples with per-unit rates.
    fig, ax = plt.subplots(figsize=(12, 3.2))
    ax.axis("off")
    columns = ["Portfolio", "G", "U", "Q", "K proxy", "R", "P"]
    cells = [
        [
            row["portfolio_construction"],
            f"{row['G_external_protection_cost_per_unit']:.1%}",
            f"{row['U_investor_demand_uplift']:.2f}x",
            f"{row['Q_founder_economic_contribution_per_unit']:.1%}",
            f"{row['K_risk_capital_proxy_per_unit']:.1%}",
            f"{row['R_platform_revenue_per_unit_issuance']:.1%}",
            f"{row['P_modeled_profit_per_unit_issuance']:.1%}",
        ]
        for row in scoreboard_rows
    ]
    table = ax.table(cellText=cells, colLabels=columns, loc="center", cellLoc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.5)
    ax.set_title("G / U / Q / K / R / P scenario scoreboard", pad=14)
    fig.tight_layout()
    fig.savefig(directory / "17_platform_scoreboard.png", dpi=160)
    plt.close(fig)


def _failure_table_markdown(
    failure_rows: list[dict[str, Any]],
    portfolio_size: int,
    floors: tuple[float, ...],
) -> list[str]:
    survivors = sorted(
        {
            float(row["survivor_multiple"])
            for row in failure_rows
            if row["portfolio_size"] == portfolio_size
        }
    )
    lines = [
        f"| Survivor MOIC | {' | '.join(f'{floor:.0%} floor' for floor in floors)} |",
        f"|---:|{'|'.join(['---:'] * len(floors))}|",
    ]
    for survivor in survivors:
        cells: list[str] = []
        for floor in floors:
            row = _one(
                failure_rows,
                portfolio_size=portfolio_size,
                protection_fraction=floor,
                survivor_multiple=survivor,
                failure_recovery_multiple=0.0,
            )
            if row["maximum_failures"] is None:
                cells.append("infeasible at F=0")
            else:
                cells.append(
                    f"{int(row['maximum_failures']):,} ({row['maximum_failure_percentage']:.1f}%)"
                )
        lines.append(f"| {survivor:g}x | {' | '.join(cells)} |")
    return lines


def _frontier_row(
    rows: list[dict[str, Any]],
    construction: str,
    selection: str,
    tail: str,
    portfolio_size: int,
    floor: float,
    metric: str,
    target: float,
) -> dict[str, Any]:
    return _one(
        rows,
        portfolio_construction=construction,
        selection_level=selection,
        tail_model=tail,
        portfolio_size=portfolio_size,
        protection_fraction=floor,
        frontier_metric=metric,
        target=target,
    )


def _one(rows: list[dict[str, Any]], **matches: Any) -> dict[str, Any]:
    found = [
        row
        for row in rows
        if all(row.get(field) == value for field, value in matches.items())
    ]
    if len(found) != 1:
        raise ValueError(f"expected one row for {matches}, found {len(found)}")
    return found[0]


def _finish_axis(
    ax: Any,
    title: str,
    xlabel: str,
    ylabel: str,
    *,
    percent_y: bool,
) -> None:
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(alpha=0.25)
    if percent_y:
        ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
        lower, upper = ax.get_ylim()
        ax.set_ylim(min(0.0, lower), upper)


def _fmt_optional(value: float | None, format_spec: str) -> str:
    return "not found" if value is None else format(value, format_spec)


def _fmt_gbp(value: float | None) -> str:
    if value is None:
        return "unreachable"
    absolute = abs(value)
    if absolute >= 1e9:
        return f"GBP {value / 1e9:,.2f}bn"
    if absolute >= 1e6:
        return f"GBP {value / 1e6:,.1f}m"
    return f"GBP {value:,.0f}"


def _write_yaml(path: Path, value: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(value, handle, sort_keys=False, allow_unicode=False)


def _write_json(path: Path, value: Any) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _git_branch(repository_root: Path) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repository_root), "branch", "--show-current"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return completed.stdout.strip() or None

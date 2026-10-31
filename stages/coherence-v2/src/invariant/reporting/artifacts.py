"""Persistence and presentation of reproducible S2a run artifacts."""

import hashlib
import json
import platform
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from invariant.core.config import config_to_dict, dump_config
from invariant.core.types import GridPointResult, SimulationConfig, SimulationResult


def canonical_hash(value: Any) -> str:
    """Return SHA-256 of canonical compact JSON."""

    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(payload).hexdigest()


def file_hash(path: str | Path) -> str:
    """Return SHA-256 for one local file."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def git_commit_hash(repository_root: str | Path) -> str | None:
    """Return current Git commit where available."""

    return _git_value(Path(repository_root), ["rev-parse", "HEAD"])


def git_worktree_dirty(repository_root: str | Path) -> bool | None:
    """Record whether the commit has uncommitted companion changes."""

    value = _git_value(Path(repository_root), ["status", "--porcelain"])
    return None if value is None else bool(value)


def _safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("._") or "run"


def _baseline_summary_rows(metrics: dict[str, float]) -> list[tuple[str, str]]:
    return [
        ("Expected portfolio multiple", f"{metrics['expected_portfolio_multiple']:.4f}x"),
        ("Median portfolio multiple", f"{metrics['median_portfolio_multiple']:.4f}x"),
        (
            "Probability NAV below protected principal",
            f"{metrics['probability_nav_below_protected_principal']:.4%}",
        ),
        (
            "Expected guarantee claim per £1 initial principal",
            f"£{metrics['expected_guarantee_claim_per_unit']:.4f}",
        ),
        (
            "Median guarantee claim per £1 initial principal",
            f"£{metrics['median_guarantee_claim_per_unit']:.4f}",
        ),
        ("Claim VaR 95% per £1", f"£{metrics['guarantee_claim_var_95_per_unit']:.4f}"),
        ("Claim VaR 99% per £1", f"£{metrics['guarantee_claim_var_99_per_unit']:.4f}"),
        ("Claim VaR 99.5% per £1", f"£{metrics['guarantee_claim_var_99.5_per_unit']:.4f}"),
        (
            "Claim Expected Shortfall 95% per £1",
            f"£{metrics['guarantee_claim_expected_shortfall_95_per_unit']:.4f}",
        ),
        (
            "Claim Expected Shortfall 99% per £1",
            f"£{metrics['guarantee_claim_expected_shortfall_99_per_unit']:.4f}",
        ),
        (
            "Claim Expected Shortfall 99.5% per £1",
            f"£{metrics['guarantee_claim_expected_shortfall_99.5_per_unit']:.4f}",
        ),
        (
            "Probability of at least one extreme winner",
            f"{metrics['probability_at_least_one_extreme_winner']:.4%}",
        ),
        (
            "Mean number of extreme winners",
            f"{metrics['mean_number_of_extreme_winners']:.4f}",
        ),
        (
            "Mean largest-investment share, conditional on positive NAV",
            f"{metrics['mean_largest_investment_share_conditional_on_positive_nav']:.4%}",
        ),
        (
            "Expected founder-warrant value per £1 initial principal",
            f"£{metrics['expected_founder_warrant_value_per_unit']:.4f}",
        ),
        (
            "Expected generic stop-loss payout per £1 initial principal",
            f"£{metrics['expected_stop_loss_payout_per_unit']:.4f}",
        ),
    ]


def _summary_markdown(config: SimulationConfig, result: SimulationResult) -> str:
    metrics = result.baseline_metrics
    lines = [
        f"# Reproducible run: `{result.scenario_name}`",
        "",
        "> All startup-return inputs are synthetic `SCENARIO` assumptions. These outputs are architecture tests, not empirical estimates, guarantee prices or capital requirements.",
        "",
        "## Run identity",
        "",
        f"- Model version: `{result.model_version}`",
        f"- Random seed: `{result.random_seed}`",
        f"- Monte Carlo paths per grid point: `{config.number_of_simulations:,}`",
        f"- Baseline portfolio size: `{result.baseline_portfolio_size:,}` startups",
        f"- Baseline protection fraction: `{result.baseline_protection_fraction:.0%}`",
        f"- Scenario: {config.scenario_description}",
        "",
        "## Baseline numerical outputs",
        "",
        "| Quantity | Synthetic result |",
        "|---|---:|",
    ]
    lines.extend(f"| {label} | {value} |" for label, value in _baseline_summary_rows(metrics))
    lines.extend(
        [
            "",
            "## Diversification sweep at the baseline protection level",
            "",
            "| Startups | Expected multiple | Claim probability | Expected claim/£1 | ES 99.5%/£1 | Largest share if NAV>0 |",
            "|---:|---:|---:|---:|---:|---:|",
        ]
    )
    baseline_grid = sorted(
        (
            point
            for point in result.grid_results
            if point.protection_fraction == result.baseline_protection_fraction
        ),
        key=lambda point: point.portfolio_size,
    )
    for point in baseline_grid:
        point_metrics = point.metrics
        lines.append(
            "| "
            f"{point.portfolio_size:,} | "
            f"{point_metrics['expected_portfolio_multiple']:.4f}x | "
            f"{point_metrics['probability_nav_below_protected_principal']:.4%} | "
            f"£{point_metrics['expected_guarantee_claim_per_unit']:.4f} | "
            f"£{point_metrics['guarantee_claim_expected_shortfall_99.5_per_unit']:.4f} | "
            f"{point_metrics['mean_largest_investment_share_conditional_on_positive_nav']:.4%} |"
        )
    lines.extend(
        [
            "",
            "## Risk-measure convention",
            "",
            "Guarantee claims are non-negative losses expressed per £1 of initial principal: `claim/K = max(g - NAV_T/K, 0)`. Larger positive values are worse. VaR is the empirical upper-tail claim quantile. Expected Shortfall is the mean of simulated claims greater than or equal to that VaR threshold.",
            "",
            "Founder-warrant value is reported separately and is not deducted from the guarantee claim or treated as liquid cash. The generic stop-loss output applies `min(max(loss-attachment,0),limit)` to the gross claim and does not imply insurance, reinsurance or any legal provider.",
            "",
            "## Baseline macro-state counts",
            "",
        ]
    )
    lines.extend(
        f"- `{state}`: `{count:,}`"
        for state, count in result.baseline_macro_state_counts.items()
    )
    lines.extend(["", "## Unsupported outputs", ""])
    lines.extend(f"- {quantity}" for quantity in result.unsupported_quantities)
    lines.extend(
        [
            "",
            "See `config.yaml` for every synthetic probability, return range, protection level and warrant assumption with units, status, source and notes.",
            "",
        ]
    )
    return "\n".join(lines)


def _grid_series(
    result: SimulationResult, metric_name: str
) -> dict[float, tuple[list[int], list[float]]]:
    series: dict[float, tuple[list[int], list[float]]] = {}
    for protection_fraction in sorted(
        {point.protection_fraction for point in result.grid_results}
    ):
        points = sorted(
            (
                point
                for point in result.grid_results
                if point.protection_fraction == protection_fraction
            ),
            key=lambda point: point.portfolio_size,
        )
        series[protection_fraction] = (
            [point.portfolio_size for point in points],
            [point.metrics[metric_name] for point in points],
        )
    return series


def _write_line_figure(
    result: SimulationResult,
    metric_name: str,
    title: str,
    y_label: str,
    path: Path,
) -> None:
    figure, axis = plt.subplots(figsize=(8, 5))
    for protection_fraction, (sizes, values) in _grid_series(result, metric_name).items():
        axis.plot(sizes, values, marker="o", label=f"g = {protection_fraction:.0%}")
    axis.set_xscale("log")
    axis.set_xticks(sorted({point.portfolio_size for point in result.grid_results}))
    axis.set_xticklabels(
        [f"{size:,}" for size in sorted({point.portfolio_size for point in result.grid_results})]
    )
    axis.set_xlabel("Number of equally weighted startup investments")
    axis.set_ylabel(y_label)
    axis.set_title(title)
    axis.grid(alpha=0.25)
    axis.legend(title="Protection fraction")
    figure.tight_layout()
    figure.savefig(path, dpi=140)
    plt.close(figure)


def _write_histogram(
    values: tuple[float, ...], title: str, x_label: str, color: str, path: Path
) -> None:
    figure, axis = plt.subplots(figsize=(8, 5))
    axis.hist(values, bins=40, color=color, alpha=0.85)
    axis.set_title(title)
    axis.set_xlabel(x_label)
    axis.set_ylabel("Number of Monte Carlo paths")
    axis.grid(axis="y", alpha=0.25)
    figure.tight_layout()
    figure.savefig(path, dpi=140)
    plt.close(figure)


def _write_figures(result: SimulationResult, figures_directory: Path) -> None:
    """Write exactly the five decision-useful S2a figures."""

    figures_directory.mkdir(parents=True, exist_ok=True)
    _write_line_figure(
        result,
        "expected_guarantee_claim_per_unit",
        "Expected guarantee claim versus portfolio size",
        "Expected guarantee claim per £1 initial principal",
        figures_directory / "expected_claim_vs_portfolio_size.png",
    )
    _write_line_figure(
        result,
        "probability_nav_below_protected_principal",
        "Probability of a guarantee claim versus portfolio size",
        "Probability NAV is below protected principal",
        figures_directory / "claim_probability_vs_portfolio_size.png",
    )
    _write_line_figure(
        result,
        "guarantee_claim_expected_shortfall_99.5_per_unit",
        "99.5% Expected Shortfall versus portfolio size",
        "99.5% Expected Shortfall per £1 initial principal",
        figures_directory / "expected_shortfall_99_5_vs_portfolio_size.png",
    )
    _write_histogram(
        result.baseline_terminal_multiples,
        "Baseline synthetic portfolio-return distribution",
        "Terminal portfolio multiple (NAV at maturity / initial principal)",
        "#295f8a",
        figures_directory / "baseline_portfolio_return_distribution.png",
    )
    _write_histogram(
        result.baseline_guarantee_claims_per_unit,
        "Baseline synthetic guarantee-claim distribution",
        "Guarantee claim per £1 initial principal",
        "#a64646",
        figures_directory / "baseline_guarantee_claim_distribution.png",
    )


def write_run_artifacts(
    config: SimulationConfig,
    result: SimulationResult,
    output_root: str | Path,
    config_source: str | Path | None = None,
) -> Path:
    """Create a unique run directory with the complete reproducibility contract."""

    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    config_payload = config_to_dict(config)
    config_hash = canonical_hash(config_payload)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_name = f"{_safe_name(config.scenario_name)}-{timestamp}-{config_hash[:8]}"
    run_directory = root / run_name
    counter = 1
    while run_directory.exists():
        run_directory = root / f"{run_name}-{counter}"
        counter += 1
    run_directory.mkdir(parents=True)

    dump_config(config, run_directory / "config.yaml")
    with (run_directory / "results.json").open("w", encoding="utf-8") as handle:
        json.dump(result.as_dict(), handle, indent=2, sort_keys=True)
        handle.write("\n")
    (run_directory / "summary.md").write_text(
        _summary_markdown(config, result), encoding="utf-8"
    )
    repository_root = Path(__file__).resolve().parents[3]
    lock_path = repository_root / "requirements.lock"
    manifest = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit_hash": git_commit_hash(repository_root),
        "git_worktree_dirty": git_worktree_dirty(repository_root),
        "python_version": platform.python_version(),
        "model_version": config.model_version,
        "random_seed": config.random_seed,
        "config_hash": config_hash,
        "dependency_lock_hash": file_hash(lock_path) if lock_path.exists() else None,
        "config_source": str(config_source) if config_source is not None else None,
        "input_data_hashes": [],
        "data_status": "No empirical input data used; startup-return assumptions are synthetic SCENARIO values.",
    }
    with (run_directory / "manifest.json").open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write("\n")
    _write_figures(result, run_directory / "figures")
    return run_directory

"""Diagnostics for empirical terminal-return calibration and guarantee risk."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

import numpy as np

from invariant.calibration.parameter_models import (
    EmpiricalMixtureSpec,
    calibrate_survival_tail_beta,
    pareto_survival_probability,
    target_probabilities_from_constraints,
)
from invariant.models.terminal.empirical_mixture import (
    EmpiricalTerminalMixtureModel,
    build_empirical_metrics,
)


@dataclass(frozen=True)
class ValidationResidual:
    """One empirical target versus simulated/model-implied result."""

    name: str
    target: float
    observed: float
    residual: float
    tolerance: float
    within_tolerance: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "target": self.target,
            "observed": self.observed,
            "residual": self.residual,
            "tolerance": self.tolerance,
            "within_tolerance": self.within_tolerance,
        }


def tail_beta_from_constraints(constraints: dict[str, Any]) -> float:
    """Return beta implied by the 10x and 50x aggregate thresholds."""

    targets = target_probabilities_from_constraints(constraints)
    return calibrate_survival_tail_beta(
        targets["above_10x"], targets["above_50x"], threshold_u=10.0, x=50.0
    )


def validate_terminal_constraints(
    terminal_multiples: np.ndarray,
    constraints: dict[str, Any],
) -> tuple[ValidationResidual, ...]:
    """Compare sampled individual returns or portfolio returns to constraints.

    The usual caller passes sampled individual investment returns.  The function
    accepts any non-negative array so tests can also probe deterministic cases.
    """

    values = np.asarray(terminal_multiples, dtype=float)
    targets = target_probabilities_from_constraints(constraints)
    items = constraints["investment_return_constraints"]
    observed = {
        "below_1x": float(np.mean(values < 1.0)),
        "above_5x": float(np.mean(values >= 5.0)),
        "above_10x": float(np.mean(values >= 10.0)),
        "above_50x": float(np.mean(values >= 50.0)),
    }
    residuals: list[ValidationResidual] = []
    for name, target in targets.items():
        tolerance = float(items[name].get("tolerance", 0.0))
        residual = observed[name] - target
        residuals.append(
            ValidationResidual(
                name=name,
                target=target,
                observed=observed[name],
                residual=residual,
                tolerance=tolerance,
                within_tolerance=abs(residual) <= tolerance,
            )
        )
    return tuple(residuals)


def model_implied_constraint_probabilities(spec: EmpiricalMixtureSpec) -> dict[str, float]:
    """Return analytical target probabilities implied by one mixture spec."""

    weights = spec.weights
    p_tail = weights.tail_10x_plus
    p_ge_50 = 0.0
    if spec.tail.mode != "no_mega_winner":
        cap = spec.tail.cap
        if cap is None or cap >= 50.0:
            p_ge_50 = p_tail * pareto_survival_probability(
                50.0, spec.tail.threshold_u, spec.tail.survival_tail_exponent_beta
            )
    return {
        "below_1x": weights.complete_loss + weights.partial_loss,
        "above_5x": weights.strong_success_5_10x + weights.tail_10x_plus,
        "above_10x": weights.tail_10x_plus,
        "above_50x": p_ge_50,
    }


def convergence_diagnostic(
    spec: EmpiricalMixtureSpec,
    portfolio_size: int,
    protection_fraction: float,
    path_counts: Iterable[int],
    random_seed: int,
    terminal_warrant_fraction: float,
    stop_loss_attachment: float,
    stop_loss_limit: float,
) -> list[dict[str, float]]:
    """Run a transparent Monte Carlo convergence check for key claim metrics."""

    model = EmpiricalTerminalMixtureModel()
    rows: list[dict[str, float]] = []
    for count in path_counts:
        portfolio = model.simulate_portfolio(
            spec=spec,
            portfolio_size=portfolio_size,
            number_of_paths=int(count),
            random_seed=random_seed,
        )
        metrics = build_empirical_metrics(
            portfolio,
            protection_fraction=protection_fraction,
            terminal_warrant_fraction=terminal_warrant_fraction,
            stop_loss_attachment=stop_loss_attachment,
            stop_loss_limit=stop_loss_limit,
        )
        claims = np.maximum(protection_fraction - portfolio.terminal_multiples, 0.0)
        rows.append(
            {
                "paths": float(count),
                "expected_claim_per_unit": metrics["expected_guarantee_claim_per_unit"],
                "var_99_5_per_unit": metrics["guarantee_claim_var_99.5_per_unit"],
                "es_99_5_per_unit": metrics[
                    "guarantee_claim_expected_shortfall_99.5_per_unit"
                ],
                "expected_claim_standard_error": float(
                    np.std(claims, ddof=1) / np.sqrt(len(claims))
                ),
            }
        )
    return rows


def sensitivity_ranking(
    baseline_name: str,
    rows: list[dict[str, Any]],
    metric_names: tuple[str, ...] = (
        "expected_guarantee_claim_per_unit",
        "guarantee_claim_expected_shortfall_99.5_per_unit",
        "probability_nav_below_protected_principal",
        "delta_claim_top1_per_unit",
    ),
) -> list[dict[str, Any]]:
    """Rank specification changes by their absolute impact on risk metrics."""

    baseline = next(row for row in rows if row["spec_name"] == baseline_name)
    ranked: list[dict[str, Any]] = []
    for row in rows:
        if row["spec_name"] == baseline_name:
            continue
        impacts = {
            name: float(row[name]) - float(baseline[name])
            for name in metric_names
            if name in row and name in baseline
        }
        score = sum(abs(value) for value in impacts.values())
        ranked.append(
            {
                "spec_name": row["spec_name"],
                "dimension": row.get("sensitivity_dimension", "model_specification"),
                "impact_score": score,
                **{f"delta_{name}": value for name, value in impacts.items()},
            }
        )
    return sorted(ranked, key=lambda item: item["impact_score"], reverse=True)

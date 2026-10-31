"""Epistemic uncertainty helpers for S2b-a nested simulation."""

from __future__ import annotations

from typing import Any

import numpy as np

from invariant.calibration.parameter_models import (
    MixtureWeights,
    calibrate_survival_tail_beta,
    draw_weight_universes,
)


def draw_parameter_universes(
    constraints: dict[str, Any],
    number_of_draws: int,
    random_seed: int,
) -> tuple[dict[str, Any], ...]:
    """Draw transparent epistemic universes from rounded aggregate constraints."""

    rng = np.random.default_rng(random_seed)
    weight_draws = draw_weight_universes(constraints, number_of_draws, rng)
    rows: list[dict[str, Any]] = []
    for weights in weight_draws:
        beta = calibrate_survival_tail_beta(
            weights.tail_10x_plus,
            weights.target_mega_50x_plus,
            threshold_u=10.0,
            x=50.0,
        )
        rows.append({"weights": weights.as_dict(), "survival_tail_exponent_beta": beta})
    return tuple(rows)


def summarize_parameter_draws(draws: tuple[dict[str, Any], ...]) -> dict[str, Any]:
    """Return min/median/max summaries without implying precise posteriors."""

    if not draws:
        raise ValueError("draws cannot be empty")
    beta_values = np.array([draw["survival_tail_exponent_beta"] for draw in draws])
    weight_names = MixtureWeights.__dataclass_fields__.keys()
    weight_summary = {}
    for name in weight_names:
        values = np.array([draw["weights"][name] for draw in draws])
        weight_summary[name] = _summary(values)
    return {
        "number_of_epistemic_draws": len(draws),
        "interpretation": "Tolerance-band draws from rounded public aggregate statistics; not row-level Bayesian posteriors.",
        "survival_tail_exponent_beta": _summary(beta_values),
        "weights": weight_summary,
    }


def _summary(values: np.ndarray) -> dict[str, float]:
    return {
        "min": float(np.min(values)),
        "median": float(np.median(values)),
        "max": float(np.max(values)),
    }

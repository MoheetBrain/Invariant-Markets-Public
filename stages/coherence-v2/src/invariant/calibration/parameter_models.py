"""Parameter objects for the S2b-a empirically constrained terminal model."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import log
from typing import Any

import numpy as np


@dataclass(frozen=True)
class MixtureWeights:
    """Mutually exclusive terminal return probability masses."""

    complete_loss: float
    partial_loss: float
    ordinary_success_1_5x: float
    strong_success_5_10x: float
    tail_10x_plus: float
    target_mega_50x_plus: float

    @property
    def values_for_sampling(self) -> tuple[float, float, float, float, float]:
        return (
            self.complete_loss,
            self.partial_loss,
            self.ordinary_success_1_5x,
            self.strong_success_5_10x,
            self.tail_10x_plus,
        )

    def validate(self) -> None:
        values = self.values_for_sampling
        if any(value < 0 for value in values):
            raise ValueError("mixture weights cannot be negative")
        if abs(sum(values) - 1.0) > 1e-10:
            raise ValueError("mixture weights must sum to one")
        if not 0 <= self.target_mega_50x_plus <= self.tail_10x_plus:
            raise ValueError("target_mega_50x_plus must lie inside the >=10x tail mass")

    def as_dict(self) -> dict[str, float]:
        return asdict(self)


@dataclass(frozen=True)
class BodySpec:
    """Body distribution choice for non-tail positive returns."""

    name: str
    provenance: str = "MODEL_RISK_SCENARIO"


@dataclass(frozen=True)
class TailSpec:
    """Tail model under the explicit Pareto survival convention."""

    name: str
    survival_tail_exponent_beta: float
    threshold_u: float = 10.0
    cap: float | None = None
    mode: str = "unbounded_pareto"
    provenance: str = "MODEL_RISK_SCENARIO"

    def validate(self) -> None:
        if self.threshold_u <= 0:
            raise ValueError("tail threshold must be positive")
        if self.survival_tail_exponent_beta <= 0:
            raise ValueError("survival_tail_exponent_beta must be positive")
        if self.cap is not None and self.cap <= self.threshold_u:
            raise ValueError("tail cap must exceed the threshold")
        if self.mode not in {
            "unbounded_pareto",
            "capped_pareto",
            "truncated_pareto",
            "no_mega_winner",
        }:
            raise ValueError(f"unknown tail mode {self.mode!r}")

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CorrelationSpec:
    """Dependence model-risk specification."""

    name: str
    model: str
    rho_macro: float = 0.0
    degrees_of_freedom: float | None = None
    provenance: str = "MODEL_RISK_SCENARIO"

    def validate(self) -> None:
        if self.model not in {"independent", "gaussian_factor", "student_t_factor"}:
            raise ValueError(f"unknown correlation model {self.model!r}")
        if not 0 <= self.rho_macro <= 1:
            raise ValueError("rho_macro must be in [0, 1]")
        if self.model == "student_t_factor" and (
            self.degrees_of_freedom is None or self.degrees_of_freedom <= 2
        ):
            raise ValueError("student-t factor stress requires df > 2")

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EmpiricalMixtureSpec:
    """Complete model-risk universe for one terminal-return simulator."""

    name: str
    body: BodySpec
    tail: TailSpec
    correlation: CorrelationSpec
    weights: MixtureWeights

    def validate(self) -> None:
        self.weights.validate()
        self.tail.validate()
        self.correlation.validate()
        if self.body.name not in {"truncated_lognormal", "log_uniform"}:
            raise ValueError(f"unknown body model {self.body.name!r}")

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "body": asdict(self.body),
            "tail": self.tail.as_dict(),
            "correlation": self.correlation.as_dict(),
            "weights": self.weights.as_dict(),
        }


def calibrate_survival_tail_beta(
    probability_at_threshold: float,
    probability_at_x: float,
    threshold_u: float,
    x: float,
) -> float:
    """Calibrate beta from ``P(X>=x)/P(X>=u) = (x/u)^(-beta)``."""

    if not (0 < probability_at_x < probability_at_threshold < 1):
        raise ValueError("tail probabilities must satisfy 0 < P(X>=x) < P(X>=u) < 1")
    if x <= threshold_u or threshold_u <= 0:
        raise ValueError("x must exceed a positive threshold")
    return -log(probability_at_x / probability_at_threshold) / log(x / threshold_u)


def pareto_survival_probability(x: float, threshold_u: float, beta: float) -> float:
    """Return ``P(X >= x | X >= u)`` under the S2b-a Pareto convention."""

    if x < threshold_u:
        return 1.0
    if threshold_u <= 0 or beta <= 0:
        raise ValueError("threshold_u and beta must be positive")
    return (x / threshold_u) ** (-beta)


def derive_mixture_weights(constraints: dict[str, Any]) -> MixtureWeights:
    """Build first-pass weights from aggregate return constraints.

    ``complete_loss`` uses the older Correlation realized-deal decomposition as
    a proxy.  ``partial_loss`` is then constrained to keep the stronger
    ``P(X<1)`` aggregate target intact, and residual error against the older
    partial-loss report is reported in diagnostics rather than hidden.
    """

    returns = constraints["investment_return_constraints"]
    realized = constraints["realized_deal_decomposition"]
    p_below_1 = float(returns["below_1x"]["probability"])
    p_above_5 = float(returns["above_5x"]["probability"])
    p_above_10 = float(returns["above_10x"]["probability"])
    p_above_50 = float(returns["above_50x"]["probability"])
    p_zero_proxy = float(realized["out_of_business_proxy"]["probability"])
    weights = MixtureWeights(
        complete_loss=p_zero_proxy,
        partial_loss=p_below_1 - p_zero_proxy,
        ordinary_success_1_5x=1.0 - p_below_1 - p_above_5,
        strong_success_5_10x=p_above_5 - p_above_10,
        tail_10x_plus=p_above_10,
        target_mega_50x_plus=p_above_50,
    )
    weights.validate()
    return weights


def target_probabilities_from_constraints(constraints: dict[str, Any]) -> dict[str, float]:
    """Return the main investor-return calibration targets."""

    returns = constraints["investment_return_constraints"]
    return {
        "below_1x": float(returns["below_1x"]["probability"]),
        "above_5x": float(returns["above_5x"]["probability"]),
        "above_10x": float(returns["above_10x"]["probability"]),
        "above_50x": float(returns["above_50x"]["probability"]),
    }


def draw_weight_universes(
    constraints: dict[str, Any],
    number_of_draws: int,
    random_generator: np.random.Generator,
) -> tuple[MixtureWeights, ...]:
    """Draw epistemic parameter universes from transparent tolerance bands."""

    if number_of_draws <= 0:
        raise ValueError("number_of_draws must be positive")
    returns = constraints["investment_return_constraints"]
    realized = constraints["realized_deal_decomposition"]
    draws: list[MixtureWeights] = []
    attempts = 0
    while len(draws) < number_of_draws and attempts < number_of_draws * 200:
        attempts += 1
        p_below_1 = _draw_probability(returns["below_1x"], random_generator)
        p_above_5 = _draw_probability(returns["above_5x"], random_generator)
        p_above_10 = _draw_probability(returns["above_10x"], random_generator)
        p_above_50 = _draw_probability(returns["above_50x"], random_generator)
        p_zero = _draw_probability(realized["out_of_business_proxy"], random_generator)
        if not (0 < p_above_50 < p_above_10 < p_above_5 < 1 - p_below_1):
            continue
        if p_zero > p_below_1:
            continue
        try:
            weights = MixtureWeights(
                complete_loss=p_zero,
                partial_loss=p_below_1 - p_zero,
                ordinary_success_1_5x=1.0 - p_below_1 - p_above_5,
                strong_success_5_10x=p_above_5 - p_above_10,
                tail_10x_plus=p_above_10,
                target_mega_50x_plus=p_above_50,
            )
            weights.validate()
        except ValueError:
            continue
        draws.append(weights)
    if len(draws) != number_of_draws:
        raise ValueError("could not draw valid epistemic universes from constraints")
    return tuple(draws)


def _draw_probability(item: dict[str, Any], random_generator: np.random.Generator) -> float:
    probability = float(item["probability"])
    tolerance = float(item.get("tolerance", 0.0))
    if tolerance <= 0:
        return probability
    return float(np.clip(random_generator.uniform(probability - tolerance, probability + tolerance), 0, 1))

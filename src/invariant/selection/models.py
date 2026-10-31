"""Selection models layered above the frozen S2b-a empirical universe.

These transforms are sensitivity instruments for ``p(X | selected)``. They do
not estimate underwriting skill, and they must never be described as fitted.
Actual estimation would require outcomes paired only with information available
at the investment decision date, with no future funding or exit information.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Protocol

import numpy as np

from invariant.calibration.parameter_models import EmpiricalMixtureSpec, MixtureWeights
from invariant.models.terminal.empirical_mixture import inverse_terminal_return_cdf


SELECTION_PROVENANCE = "HYPOTHETICAL_SELECTION_SKILL"


class SelectedMarginal(Protocol):
    """Minimal inverse-CDF interface consumed by the factor simulator."""

    name: str
    provenance: str

    def ppf(self, probabilities: np.ndarray) -> np.ndarray: ...


@dataclass(frozen=True)
class TargetConstraintSelection:
    """Selection scenario with explicit loss and positive-tail targets.

    The complete/partial-loss split is preserved within ``X<1``. Probability
    between 1x and 10x is reallocated using the base conditional split between
    1-5x and 5-10x. The >=50x target remains the base conditional share of the
    >=10x tail. Thus every change is renormalized and its destination is known.
    """

    name: str
    base_spec: EmpiricalMixtureSpec
    probability_below_1x: float
    probability_ge_10x: float
    provenance: str = SELECTION_PROVENANCE

    def __post_init__(self) -> None:
        if not 0 <= self.probability_below_1x < 1:
            raise ValueError("probability_below_1x must be in [0, 1)")
        if not 0 <= self.probability_ge_10x < 1:
            raise ValueError("probability_ge_10x must be in [0, 1)")
        if self.probability_below_1x + self.probability_ge_10x >= 1:
            raise ValueError("loss and >=10x targets must leave probability for [1x, 10x)")
        self.spec.validate()

    @property
    def spec(self) -> EmpiricalMixtureSpec:
        base = self.base_spec.weights
        base_loss = base.complete_loss + base.partial_loss
        base_middle = base.ordinary_success_1_5x + base.strong_success_5_10x
        if base_loss <= 0 or base_middle <= 0 or base.tail_10x_plus <= 0:
            raise ValueError("base mixture must contain loss, middle, and tail probability")
        if (
            self.probability_below_1x == base_loss
            and self.probability_ge_10x == base.tail_10x_plus
        ):
            return replace(self.base_spec, name=self.name)
        complete_share = base.complete_loss / base_loss
        ordinary_share = base.ordinary_success_1_5x / base_middle
        middle_probability = 1.0 - self.probability_below_1x - self.probability_ge_10x
        weights = MixtureWeights(
            complete_loss=self.probability_below_1x * complete_share,
            partial_loss=self.probability_below_1x * (1.0 - complete_share),
            ordinary_success_1_5x=middle_probability * ordinary_share,
            strong_success_5_10x=middle_probability * (1.0 - ordinary_share),
            tail_10x_plus=self.probability_ge_10x,
            target_mega_50x_plus=(
                self.probability_ge_10x
                * base.target_mega_50x_plus
                / base.tail_10x_plus
            ),
        )
        return replace(self.base_spec, name=self.name, weights=weights)

    def ppf(self, probabilities: np.ndarray) -> np.ndarray:
        return inverse_terminal_return_cdf(probabilities, self.spec)


class ExponentialTiltSelection:
    """Numerical exponential tilt ``p_s(x) ∝ p_0(x)(1+x)^s``.

    The tilted inverse CDF is constructed on deterministic equal-probability
    cells of the base model. Log weights are centered before exponentiation to
    prevent overflow. ``s=0`` bypasses the approximation and calls the frozen
    base inverse CDF exactly.
    """

    provenance = SELECTION_PROVENANCE

    def __init__(
        self,
        name: str,
        base_spec: EmpiricalMixtureSpec,
        strength: float,
        quadrature_points: int,
    ) -> None:
        if strength < 0:
            raise ValueError("selection strength must be non-negative")
        if quadrature_points < 1_000:
            raise ValueError("quadrature_points must be at least 1,000")
        self.name = name
        self.base_spec = base_spec
        self.strength = float(strength)
        self.quadrature_points = int(quadrature_points)
        base_probabilities = (np.arange(quadrature_points, dtype=float) + 0.5) / quadrature_points
        self._support = inverse_terminal_return_cdf(base_probabilities, base_spec)
        log_weights = self.strength * np.log1p(self._support)
        log_weights -= np.max(log_weights)
        weights = np.exp(log_weights)
        weights /= weights.sum()
        self._cdf = np.cumsum(weights)
        self._cdf[-1] = 1.0

    def ppf(self, probabilities: np.ndarray) -> np.ndarray:
        u = np.asarray(probabilities, dtype=float)
        if np.any((u < 0) | (u > 1)):
            raise ValueError("probabilities must lie in [0, 1]")
        if self.strength == 0:
            return inverse_terminal_return_cdf(u, self.base_spec)
        clipped = np.clip(u, 0.0, np.nextafter(1.0, 0.0))
        indices = np.searchsorted(self._cdf, clipped, side="left")
        return self._support[np.minimum(indices, self.quadrature_points - 1)]


def marginal_diagnostics(
    marginal: SelectedMarginal,
    evaluation_points: int,
) -> dict[str, float]:
    """Report deterministic marginal probabilities and moments."""

    if evaluation_points < 1_000:
        raise ValueError("evaluation_points must be at least 1,000")
    probabilities = (np.arange(evaluation_points, dtype=float) + 0.5) / evaluation_points
    values = marginal.ppf(probabilities)
    return {
        "probability_below_1x": float(np.mean(values < 1.0)),
        "probability_ge_5x": float(np.mean(values >= 5.0)),
        "probability_ge_10x": float(np.mean(values >= 10.0)),
        "probability_ge_50x": float(np.mean(values >= 50.0)),
        "expected_multiple": float(np.mean(values)),
        "median_multiple": float(np.median(values)),
    }

"""Pure mathematical contracts used by every model implementation."""

from collections.abc import Sequence
from typing import overload

import numpy as np


@overload
def principal_floor_claim(nav: float, protected_principal: float) -> float: ...


@overload
def principal_floor_claim(nav: np.ndarray, protected_principal: float) -> np.ndarray: ...


def principal_floor_claim(nav: float | np.ndarray, protected_principal: float) -> float | np.ndarray:
    """Return the invariant ``C_T = max(gK - NAV_T, 0)``.

    ``protected_principal`` is ``gK`` in currency units. With non-negative NAV,
    the claim is non-negative, no greater than protected principal, decreasing
    in NAV and increasing in the protection fraction.
    """

    if protected_principal < 0:
        raise ValueError("Protected principal cannot be negative")
    nav_array = np.asarray(nav, dtype=float)
    if np.any(nav_array < 0):
        raise ValueError("NAV cannot be negative")
    claim = np.maximum(protected_principal - nav_array, 0.0)
    if np.ndim(nav) == 0:
        return float(claim)
    return claim


def excess_of_loss_payout(
    loss: float | np.ndarray, attachment: float, limit: float
) -> float | np.ndarray:
    """Return generic payout ``min(max(loss - attachment, 0), limit)``.

    ``limit`` is maximum payout rather than the exhaustion point. The function
    deliberately makes no statement about the identity or legal form of a risk
    provider.
    """

    if attachment < 0 or limit < 0:
        raise ValueError("Attachment and limit cannot be negative")
    loss_array = np.asarray(loss, dtype=float)
    if np.any(loss_array < 0):
        raise ValueError("Loss cannot be negative")
    payout = np.minimum(np.maximum(loss_array - attachment, 0.0), limit)
    if np.ndim(loss) == 0:
        return float(payout)
    return payout


def diluted_warrant_fraction(
    initial_warrant_percentage: float,
    dilution_percentages: Sequence[float],
) -> float:
    """Return ``q_T = q_0 ∏_r (1-d_r)``.

    Fractions are expressed as decimals: two percent is ``0.02``. This function
    models arithmetic dilution only, not option terms, liquidity or legal value.
    """

    if not 0 <= initial_warrant_percentage <= 1:
        raise ValueError("Initial warrant percentage must be in [0, 1]")
    retained_fraction = 1.0
    for dilution_percentage in dilution_percentages:
        if not 0 <= dilution_percentage <= 1:
            raise ValueError("Each dilution percentage must be in [0, 1]")
        retained_fraction *= 1.0 - dilution_percentage
    return initial_warrant_percentage * retained_fraction


def founder_warrant_terminal_value(
    startup_terminal_value: float | np.ndarray,
    initial_warrant_percentage: float,
    dilution_percentages: Sequence[float],
) -> float | np.ndarray:
    """Return startup value multiplied by the diluted warrant fraction.

    The output remains separate from guarantee claims and is not treated as
    liquid cash or first-loss support in S2a.
    """

    value_array = np.asarray(startup_terminal_value, dtype=float)
    if np.any(value_array < 0):
        raise ValueError("Startup terminal value cannot be negative")
    terminal_fraction = diluted_warrant_fraction(
        initial_warrant_percentage, dilution_percentages
    )
    warrant_value = value_array * terminal_fraction
    if np.ndim(startup_terminal_value) == 0:
        return float(warrant_value)
    return warrant_value

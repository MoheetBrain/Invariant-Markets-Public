"""Exact failure-count arithmetic and linear diversification diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from math import floor


@dataclass(frozen=True)
class FailureTolerance:
    """Maximum failures compatible with a natural portfolio floor.

    ``None`` means that even the zero-failure portfolio is below the floor.
    This is economically different from a maximum of zero failures, where the
    floor is covered only if every company survives.
    """

    portfolio_size: int
    protection_fraction: float
    survivor_multiple: float
    failure_recovery_multiple: float
    maximum_failures: int | None
    maximum_failure_fraction: float | None
    zero_failures_cover_floor: bool
    all_failures_cover_floor: bool


def portfolio_multiple_from_failure_count(
    portfolio_size: int,
    failure_count: int,
    survivor_multiple: float,
    failure_recovery_multiple: float = 0.0,
) -> float:
    """Return the exact equal-weighted MOIC for a two-outcome portfolio."""

    _validate_inputs(
        portfolio_size,
        failure_count,
        survivor_multiple,
        failure_recovery_multiple,
    )
    failure_fraction = failure_count / portfolio_size
    return (
        failure_fraction * failure_recovery_multiple
        + (1.0 - failure_fraction) * survivor_multiple
    )


def failure_tolerance(
    portfolio_size: int,
    protection_fraction: float,
    survivor_multiple: float,
    failure_recovery_multiple: float = 0.0,
) -> FailureTolerance:
    """Solve the maximum failure count before external protection is needed.

    For ``m > r_f``, natural coverage requires
    ``F/N <= (m-g)/(m-r_f)``. The implementation handles the economically
    important boundaries explicitly: an infeasible zero-failure portfolio,
    and a recovery value that itself covers the floor.
    """

    _validate_inputs(
        portfolio_size,
        0,
        survivor_multiple,
        failure_recovery_multiple,
    )
    if not 0 <= protection_fraction <= 1:
        raise ValueError("protection_fraction must be in [0, 1]")

    zero_covers = survivor_multiple >= protection_fraction
    all_cover = failure_recovery_multiple >= protection_fraction
    if not zero_covers:
        return FailureTolerance(
            portfolio_size=portfolio_size,
            protection_fraction=protection_fraction,
            survivor_multiple=survivor_multiple,
            failure_recovery_multiple=failure_recovery_multiple,
            maximum_failures=None,
            maximum_failure_fraction=None,
            zero_failures_cover_floor=False,
            all_failures_cover_floor=all_cover,
        )
    if all_cover or survivor_multiple == failure_recovery_multiple:
        return FailureTolerance(
            portfolio_size=portfolio_size,
            protection_fraction=protection_fraction,
            survivor_multiple=survivor_multiple,
            failure_recovery_multiple=failure_recovery_multiple,
            maximum_failures=portfolio_size,
            maximum_failure_fraction=1.0,
            zero_failures_cover_floor=True,
            all_failures_cover_floor=True,
        )

    fraction = (survivor_multiple - protection_fraction) / (
        survivor_multiple - failure_recovery_multiple
    )
    bounded_fraction = min(max(fraction, 0.0), 1.0)
    # A tiny tolerance prevents floating representation from turning an exact
    # integer boundary such as 500.0 into 499.99999999999994 before flooring.
    maximum_failures = min(portfolio_size, floor(portfolio_size * bounded_fraction + 1e-12))
    return FailureTolerance(
        portfolio_size=portfolio_size,
        protection_fraction=protection_fraction,
        survivor_multiple=survivor_multiple,
        failure_recovery_multiple=failure_recovery_multiple,
        maximum_failures=maximum_failures,
        maximum_failure_fraction=maximum_failures / portfolio_size,
        zero_failures_cover_floor=True,
        all_failures_cover_floor=all_cover,
    )


def effective_portfolio_size(portfolio_size: int, equal_correlation: float) -> float:
    """Return linear equal-correlation ``N_effective`` intuition.

    This diagnostic follows ``1 / [rho + (1-rho)/N]``. It is not a heavy-tail
    portfolio approximation and must not be substituted for the simulation.
    """

    if portfolio_size <= 0:
        raise ValueError("portfolio_size must be positive")
    if not 0 <= equal_correlation <= 1:
        raise ValueError("equal_correlation must be in [0, 1]")
    return 1.0 / (equal_correlation + (1.0 - equal_correlation) / portfolio_size)


def _validate_inputs(
    portfolio_size: int,
    failure_count: int,
    survivor_multiple: float,
    failure_recovery_multiple: float,
) -> None:
    if portfolio_size <= 0:
        raise ValueError("portfolio_size must be positive")
    if not 0 <= failure_count <= portfolio_size:
        raise ValueError("failure_count must lie in [0, portfolio_size]")
    if survivor_multiple < 0 or failure_recovery_multiple < 0:
        raise ValueError("return multiples cannot be negative")

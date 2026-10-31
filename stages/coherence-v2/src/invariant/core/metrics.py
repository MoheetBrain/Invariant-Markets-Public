"""Transparent portfolio, claim-tail and concentration metrics."""

import numpy as np


def empirical_var(losses: np.ndarray, confidence: float) -> float:
    """Return upper-tail loss VaR as the empirical confidence quantile.

    Losses are non-negative positive amounts: larger numbers are worse. VaR is
    therefore reported as a positive claim per £1 of initial principal.
    """

    if not 0 < confidence < 1:
        raise ValueError("confidence must be in (0, 1)")
    return float(np.quantile(losses, confidence, method="linear"))


def empirical_expected_shortfall(losses: np.ndarray, confidence: float) -> float:
    """Return upper-tail Expected Shortfall for non-negative loss amounts.

    The finite-sample convention is the mean of all simulated losses greater
    than or equal to the empirical VaR threshold.
    """

    threshold = empirical_var(losses, confidence)
    tail = losses[losses >= threshold]
    return float(np.mean(tail))


def largest_investment_share(company_return_multiples: np.ndarray) -> np.ndarray:
    """Return each path's largest terminal investment value divided by NAV.

    Initial allocations are equal, so return multiples can be used directly.
    A total-wipeout path has concentration defined as zero because it has no
    terminal value to allocate.
    """

    values = np.asarray(company_return_multiples, dtype=float)
    if values.ndim != 2 or np.any(values < 0):
        raise ValueError("company_return_multiples must be a non-negative matrix")
    totals = values.sum(axis=1)
    shares = np.zeros(values.shape[0], dtype=float)
    positive = totals > 0
    shares[positive] = values[positive].max(axis=1) / totals[positive]
    return shares


# Backwards-compatible names retained for external research notebooks.
quantile = empirical_var
expected_shortfall = empirical_expected_shortfall

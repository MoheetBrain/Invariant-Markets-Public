"""Monotone interpolation helpers for dependence and selection frontiers."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class FrontierSolution:
    target: float
    boundary: float | None
    status: str
    lower_grid_value: float | None
    upper_grid_value: float | None


def solve_increasing_frontier(
    grid: tuple[float, ...],
    values: tuple[float, ...],
    target: float,
) -> FrontierSolution:
    """Find first increasing-response crossing after cumulative-max denoising."""

    x, y = _validated_arrays(grid, values)
    monotone = np.maximum.accumulate(y)
    if target < monotone[0]:
        return FrontierSolution(target, None, "below_search_interval", None, float(x[0]))
    if target > monotone[-1]:
        return FrontierSolution(target, None, "above_search_interval", float(x[-1]), None)
    index = int(np.searchsorted(monotone, target, side="left"))
    if index == 0:
        boundary = float(x[0])
    elif monotone[index] == monotone[index - 1]:
        boundary = float(x[index])
    else:
        fraction = (target - monotone[index - 1]) / (
            monotone[index] - monotone[index - 1]
        )
        boundary = float(x[index - 1] + fraction * (x[index] - x[index - 1]))
    return FrontierSolution(
        target,
        boundary,
        "interpolated",
        float(x[max(index - 1, 0)]),
        float(x[index]),
    )


def solve_decreasing_frontier(
    skill_grid: tuple[float, ...],
    values: tuple[float, ...],
    target: float,
) -> FrontierSolution:
    """Find minimum skill at which a decreasing risk response reaches target."""

    x, y = _validated_arrays(skill_grid, values)
    monotone = np.minimum.accumulate(y)
    if monotone[0] <= target:
        return FrontierSolution(target, float(x[0]), "already_satisfied", float(x[0]), float(x[0]))
    reachable = np.flatnonzero(monotone <= target)
    if len(reachable) == 0:
        return FrontierSolution(target, None, "unreachable", float(x[-1]), None)
    index = int(reachable[0])
    y0 = monotone[index - 1]
    y1 = monotone[index]
    fraction = 1.0 if y0 == y1 else (y0 - target) / (y0 - y1)
    boundary = float(x[index - 1] + fraction * (x[index] - x[index - 1]))
    return FrontierSolution(
        target,
        boundary,
        "interpolated",
        float(x[index - 1]),
        float(x[index]),
    )


def _validated_arrays(
    grid: tuple[float, ...], values: tuple[float, ...]
) -> tuple[np.ndarray, np.ndarray]:
    if len(grid) != len(values) or len(grid) < 2:
        raise ValueError("grid and values must have equal length of at least two")
    x = np.asarray(grid, dtype=float)
    y = np.asarray(values, dtype=float)
    if np.any(~np.isfinite(x)) or np.any(~np.isfinite(y)):
        raise ValueError("frontier inputs must be finite")
    if np.any(np.diff(x) <= 0):
        raise ValueError("frontier grid must be strictly increasing")
    return x, y

"""Selected terminal portfolios under macro and sector factor dependence."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from invariant.core.contracts import excess_of_loss_payout, principal_floor_claim
from invariant.core.metrics import empirical_var
from invariant.portfolio.factor_model import FactorSpecification, latent_uniforms
from invariant.selection.models import SelectedMarginal


@dataclass(frozen=True)
class SelectedPortfolioResult:
    """Path-level values needed for claim and winner-dependence diagnostics."""

    terminal_multiples: np.ndarray
    count_ge_10x: np.ndarray
    count_ge_50x: np.ndarray
    literal_all_zero: np.ndarray
    largest_share: np.ndarray
    top3_share: np.ndarray
    top5_share: np.ndarray
    hhi: np.ndarray
    terminal_without_top1: np.ndarray
    terminal_without_top3: np.ndarray


class SelectedFactorPortfolioModel:
    """Equal-weighted portfolio simulator layered above a selected marginal."""

    def __init__(self, batch_size: int) -> None:
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        self.batch_size = batch_size

    def simulate(
        self,
        marginal: SelectedMarginal,
        factor_specification: FactorSpecification,
        portfolio_size: int,
        number_of_paths: int,
        random_seed: int,
    ) -> SelectedPortfolioResult:
        return self.simulate_nested(
            marginal,
            factor_specification,
            (portfolio_size,),
            number_of_paths,
            random_seed,
        )[portfolio_size]

    def simulate_nested(
        self,
        marginal: SelectedMarginal,
        factor_specification: FactorSpecification,
        portfolio_sizes: tuple[int, ...],
        number_of_paths: int,
        random_seed: int,
    ) -> dict[int, SelectedPortfolioResult]:
        """Simulate all requested N as prefixes of one maximum-N portfolio.

        Prefix nesting gives matched random numbers for marginal diversification
        comparisons. Sector allocation is interleaved, so the prefixes retain
        the configured sector mix rather than inheriting a sector-order artifact.
        """

        if not portfolio_sizes or any(size <= 0 for size in portfolio_sizes):
            raise ValueError("portfolio_sizes must contain positive values")
        if len(set(portfolio_sizes)) != len(portfolio_sizes):
            raise ValueError("portfolio_sizes cannot contain duplicates")
        if number_of_paths <= 0:
            raise ValueError("number_of_paths must be positive")
        factor_specification.validate()
        sizes = tuple(sorted(portfolio_sizes))
        maximum_size = max(sizes)
        arrays = {size: _empty_result_arrays(number_of_paths) for size in sizes}
        rng = np.random.default_rng(
            np.random.SeedSequence(
                [random_seed, _stable_seed(marginal.name), _stable_seed(factor_specification.name)]
            )
        )

        for start in range(0, number_of_paths, self.batch_size):
            stop = min(start + self.batch_size, number_of_paths)
            batch_paths = stop - start
            uniforms = latent_uniforms(
                batch_paths,
                maximum_size,
                factor_specification,
                rng,
            )
            returns = marginal.ppf(uniforms)
            cumulative_total = np.cumsum(returns, axis=1)
            cumulative_ge_10 = np.cumsum(returns >= 10.0, axis=1)
            cumulative_ge_50 = np.cumsum(returns >= 50.0, axis=1)
            cumulative_positive = np.cumsum(returns > 0.0, axis=1)
            cumulative_squares = np.cumsum(returns**2, axis=1)

            for size in sizes:
                prefix = returns[:, :size]
                totals = cumulative_total[:, size - 1]
                positive_total = totals > 0
                top_count = min(5, size)
                top = np.partition(prefix, size - top_count, axis=1)[:, -top_count:]
                top.sort(axis=1)
                top = top[:, ::-1]
                top1 = top[:, 0]
                top3 = top[:, : min(3, size)].sum(axis=1)
                top5 = top.sum(axis=1)
                target = arrays[size]
                target["terminal_multiples"][start:stop] = totals / size
                target["count_ge_10x"][start:stop] = cumulative_ge_10[:, size - 1]
                target["count_ge_50x"][start:stop] = cumulative_ge_50[:, size - 1]
                target["literal_all_zero"][start:stop] = cumulative_positive[:, size - 1] == 0
                target["largest_share"][start:stop] = np.divide(
                    top1,
                    totals,
                    out=np.zeros(batch_paths),
                    where=positive_total,
                )
                target["top3_share"][start:stop] = np.divide(
                    top3,
                    totals,
                    out=np.zeros(batch_paths),
                    where=positive_total,
                )
                target["top5_share"][start:stop] = np.divide(
                    top5,
                    totals,
                    out=np.zeros(batch_paths),
                    where=positive_total,
                )
                target["hhi"][start:stop] = np.divide(
                    cumulative_squares[:, size - 1],
                    totals**2,
                    out=np.zeros(batch_paths),
                    where=positive_total,
                )
                target["terminal_without_top1"][start:stop] = np.maximum(
                    (totals - top1) / size, 0.0
                )
                target["terminal_without_top3"][start:stop] = np.maximum(
                    (totals - top3) / size, 0.0
                )

        return {size: SelectedPortfolioResult(**arrays[size]) for size in sizes}

    def simulate_nav_nested(
        self,
        marginal: SelectedMarginal,
        factor_specification: FactorSpecification,
        portfolio_sizes: tuple[int, ...],
        number_of_paths: int,
        random_seed: int,
        random_stream_name: str | None = None,
    ) -> dict[int, np.ndarray]:
        """Fast matched-path NAV simulation for coarse frontier discovery.

        Winner diagnostics are intentionally omitted here. The artifact records
        these rows as discovery estimates; high-path core runs retain the full
        risk-output contract.
        """

        if not portfolio_sizes or any(size <= 0 for size in portfolio_sizes):
            raise ValueError("portfolio_sizes must contain positive values")
        if number_of_paths <= 0:
            raise ValueError("number_of_paths must be positive")
        factor_specification.validate()
        sizes = tuple(sorted(set(portfolio_sizes)))
        maximum_size = max(sizes)
        values = {size: np.empty(number_of_paths) for size in sizes}
        stream = random_stream_name or factor_specification.name
        rng = np.random.default_rng(
            np.random.SeedSequence(
                [random_seed, _stable_seed(marginal.name), _stable_seed(stream)]
            )
        )
        for start in range(0, number_of_paths, self.batch_size):
            stop = min(start + self.batch_size, number_of_paths)
            uniforms = latent_uniforms(
                stop - start,
                maximum_size,
                factor_specification,
                rng,
            )
            returns = marginal.ppf(uniforms)
            cumulative_total = np.cumsum(returns, axis=1)
            for size in sizes:
                values[size][start:stop] = cumulative_total[:, size - 1] / size
        return values


def build_selected_portfolio_metrics(
    result: SelectedPortfolioResult,
    protection_fraction: float,
    terminal_warrant_fraction: float,
    stop_loss_attachment: float,
    stop_loss_limit: float,
    confidence_levels: tuple[float, ...],
) -> dict[str, float | int | None]:
    """Calculate the complete S2b-a.1 risk-output contract."""

    if not 0 <= protection_fraction <= 1:
        raise ValueError("protection_fraction must be in [0, 1]")
    claims = np.asarray(
        principal_floor_claim(result.terminal_multiples, protection_fraction),
        dtype=float,
    )
    claims_without_top1 = np.asarray(
        principal_floor_claim(result.terminal_without_top1, protection_fraction),
        dtype=float,
    )
    claims_without_top3 = np.asarray(
        principal_floor_claim(result.terminal_without_top3, protection_fraction),
        dtype=float,
    )
    stop_loss = np.asarray(
        excess_of_loss_payout(claims, stop_loss_attachment, stop_loss_limit),
        dtype=float,
    )
    paths = len(claims)
    wipeout_probability = float(np.mean(result.literal_all_zero))
    metrics: dict[str, float | int | None] = {
        "number_of_paths": paths,
        "expected_portfolio_multiple": float(np.mean(result.terminal_multiples)),
        "median_portfolio_multiple": float(np.median(result.terminal_multiples)),
        "probability_portfolio_below_1x": float(np.mean(result.terminal_multiples < 1.0)),
        "probability_claim": float(np.mean(claims > 0.0)),
        "expected_claim_per_unit": float(np.mean(claims)),
        "median_claim_per_unit": float(np.median(claims)),
        "maximum_simulated_claim_per_unit": float(np.max(claims)),
        "probability_literal_all_zero": wipeout_probability,
        "literal_all_zero_count": int(np.sum(result.literal_all_zero)),
        "literal_all_zero_rule_of_three_upper_95": (
            float(3.0 / paths) if wipeout_probability == 0.0 else None
        ),
        "probability_at_least_one_ge_10x": float(np.mean(result.count_ge_10x > 0)),
        "probability_at_least_one_ge_50x": float(np.mean(result.count_ge_50x > 0)),
        "expected_number_ge_10x": float(np.mean(result.count_ge_10x)),
        "expected_number_ge_50x": float(np.mean(result.count_ge_50x)),
        "mean_largest_winner_nav_share": float(np.mean(result.largest_share)),
        "mean_top3_nav_share": float(np.mean(result.top3_share)),
        "mean_top5_nav_share": float(np.mean(result.top5_share)),
        "mean_hhi": float(np.mean(result.hhi)),
        "expected_claim_actual_per_unit": float(np.mean(claims)),
        "expected_claim_without_top1_per_unit": float(np.mean(claims_without_top1)),
        "expected_claim_without_top3_per_unit": float(np.mean(claims_without_top3)),
        "expected_founder_warrant_value_per_unit": float(
            np.mean(result.terminal_multiples) * terminal_warrant_fraction
        ),
        "expected_generic_stop_loss_payout_per_unit": float(np.mean(stop_loss)),
    }
    for confidence in confidence_levels:
        if not 0 < confidence < 1:
            raise ValueError("confidence levels must be in (0, 1)")
        suffix = f"{confidence * 100:g}"
        var = empirical_var(claims, confidence)
        es, tail_count, tail_standard_error = exact_empirical_expected_shortfall(
            claims, confidence
        )
        metrics[f"claim_var_{suffix}_per_unit"] = var
        metrics[f"claim_es_{suffix}_per_unit"] = es
        metrics[f"claim_es_{suffix}_tail_observations"] = tail_count
        metrics[f"claim_es_{suffix}_mc_standard_error"] = tail_standard_error
    return metrics


def exact_empirical_expected_shortfall(
    losses: np.ndarray, confidence: float
) -> tuple[float, int, float]:
    """Return atom-aware empirical ES over exactly ``1-confidence`` tail mass.

    The inherited S2a convention averages every observation greater than or
    equal to VaR. With an atom at zero that can include the whole sample and
    make ES equal expected loss. S2b-a.1 instead integrates the empirical
    quantile function over the upper tail, using a fractional boundary
    observation when the requested tail mass is not an integer count.
    """

    values = np.asarray(losses, dtype=float)
    if values.ndim != 1 or len(values) == 0 or np.any(values < 0):
        raise ValueError("losses must be a non-empty non-negative vector")
    if not 0 < confidence < 1:
        raise ValueError("confidence must be in (0, 1)")
    tail_mass = len(values) * (1.0 - confidence)
    nearest_integer = round(tail_mass)
    if abs(tail_mass - nearest_integer) < 1e-9:
        full_count = int(nearest_integer)
        fractional_count = 0.0
    else:
        full_count = int(np.floor(tail_mass))
        fractional_count = tail_mass - full_count
    required = full_count + (1 if fractional_count > 0 else 0)
    required = max(required, 1)
    tail = np.partition(values, len(values) - required)[-required:]
    tail.sort()
    weighted_sum = float(np.sum(tail[-full_count:])) if full_count > 0 else 0.0
    if fractional_count > 0:
        weighted_sum += fractional_count * float(tail[-full_count - 1])
    denominator = tail_mass
    if denominator <= 0:
        return float(np.max(values)), 1, 0.0
    es = weighted_sum / denominator
    standard_error = (
        float(np.std(tail, ddof=1) / np.sqrt(len(tail))) if len(tail) > 1 else 0.0
    )
    return es, required, standard_error


def innovation_barbell_returns(
    venture_returns: np.ndarray,
    public_innovation_returns: np.ndarray,
    public_allocation: float,
) -> np.ndarray:
    """Combine separate venture/public sleeves without treating either as risk-free."""

    venture = np.asarray(venture_returns, dtype=float)
    public = np.asarray(public_innovation_returns, dtype=float)
    if venture.shape != public.shape:
        raise ValueError("venture and public sleeve returns must have equal shape")
    if np.any(venture < 0) or np.any(public < 0):
        raise ValueError("return multiples cannot be negative")
    if not 0 <= public_allocation <= 1:
        raise ValueError("public_allocation must be in [0, 1]")
    return (1.0 - public_allocation) * venture + public_allocation * public


def _empty_result_arrays(paths: int) -> dict[str, np.ndarray]:
    return {
        "terminal_multiples": np.empty(paths),
        "count_ge_10x": np.empty(paths, dtype=int),
        "count_ge_50x": np.empty(paths, dtype=int),
        "literal_all_zero": np.empty(paths, dtype=bool),
        "largest_share": np.empty(paths),
        "top3_share": np.empty(paths),
        "top5_share": np.empty(paths),
        "hhi": np.empty(paths),
        "terminal_without_top1": np.empty(paths),
        "terminal_without_top3": np.empty(paths),
    }


def _stable_seed(name: str) -> int:
    value = 0
    for character in name:
        value = (value * 131 + ord(character)) % (2**32)
    return value

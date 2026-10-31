"""S2b-a empirically constrained terminal investment-return mixture."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.stats import norm, t

from invariant.calibration.parameter_models import EmpiricalMixtureSpec
from invariant.core.contracts import diluted_warrant_fraction, excess_of_loss_payout
from invariant.core.metrics import empirical_expected_shortfall, empirical_var


@dataclass(frozen=True)
class EmpiricalPortfolioResult:
    """Path-level outputs for one portfolio size."""

    terminal_multiples: np.ndarray
    count_ge_10x: np.ndarray
    count_ge_50x: np.ndarray
    largest_share: np.ndarray
    top3_share: np.ndarray
    top5_share: np.ndarray
    hhi: np.ndarray
    terminal_without_top1: np.ndarray
    terminal_without_top3: np.ndarray


def _truncated_lognormal_ppf(
    probabilities: np.ndarray, low: float, high: float, median: float, sigma: float
) -> np.ndarray:
    clipped = np.clip(probabilities, 1e-12, 1 - 1e-12)
    mu = np.log(median)
    lower = norm.cdf((np.log(low) - mu) / sigma)
    upper = norm.cdf((np.log(high) - mu) / sigma)
    z = norm.ppf(lower + clipped * (upper - lower))
    return np.exp(mu + sigma * z)


def _log_uniform_ppf(probabilities: np.ndarray, low: float, high: float) -> np.ndarray:
    clipped = np.clip(probabilities, 1e-12, 1 - 1e-12)
    return np.exp(np.log(low) + clipped * (np.log(high) - np.log(low)))


def _tail_ppf(probabilities: np.ndarray, spec: EmpiricalMixtureSpec) -> np.ndarray:
    tail = spec.tail
    beta = tail.survival_tail_exponent_beta
    u = tail.threshold_u
    q = np.clip(probabilities, 1e-12, 1 - 1e-12)
    if tail.mode == "unbounded_pareto":
        return u * (1.0 - q) ** (-1.0 / beta)
    if tail.mode == "capped_pareto":
        raw = u * (1.0 - q) ** (-1.0 / beta)
        return np.minimum(raw, float(tail.cap))
    cap = float(tail.cap if tail.cap is not None else 50.0)
    if tail.mode == "no_mega_winner":
        cap = np.nextafter(50.0, 0.0)
    cap_survival = (u / cap) ** beta
    return u / (1.0 - q * (1.0 - cap_survival)) ** (1.0 / beta)


def inverse_terminal_return_cdf(probabilities: np.ndarray, spec: EmpiricalMixtureSpec) -> np.ndarray:
    """Map calibrated marginal uniforms to investor-level terminal MOIC."""

    spec.validate()
    u = np.asarray(probabilities, dtype=float)
    if np.any((u < 0) | (u > 1)):
        raise ValueError("probabilities must lie in [0, 1]")
    u = np.clip(u, 0.0, np.nextafter(1.0, 0.0))
    returns = np.zeros_like(u)
    weights = spec.weights.values_for_sampling
    edges = np.cumsum(weights)

    bands = (
        (edges[0], edges[1], (0.05, 1.0, 0.35, 0.85)),
        (edges[1], edges[2], (1.0, 5.0, 2.0, 0.65)),
        (edges[2], edges[3], (5.0, 10.0, 7.0, 0.35)),
    )
    for lower_edge, upper_edge, body in bands:
        mask = (u >= lower_edge) & (u < upper_edge)
        if not np.any(mask):
            continue
        local = (u[mask] - lower_edge) / (upper_edge - lower_edge)
        low, high, median, sigma = body
        if spec.body.name == "log_uniform":
            returns[mask] = _log_uniform_ppf(local, low, high)
        elif spec.body.name == "truncated_lognormal":
            returns[mask] = _truncated_lognormal_ppf(local, low, high, median, sigma)
        else:
            raise ValueError(f"unknown body model {spec.body.name!r}")

    tail_mask = u >= edges[3]
    if np.any(tail_mask):
        tail_local = (u[tail_mask] - edges[3]) / (1.0 - edges[3])
        returns[tail_mask] = _tail_ppf(tail_local, spec)
    return returns


def _uniforms(
    paths: int,
    portfolio_size: int,
    spec: EmpiricalMixtureSpec,
    random_generator: np.random.Generator,
) -> np.ndarray:
    correlation = spec.correlation
    if correlation.model == "independent":
        return random_generator.random((paths, portfolio_size))
    rho = correlation.rho_macro
    common = random_generator.standard_normal((paths, 1))
    epsilon = random_generator.standard_normal((paths, portfolio_size))
    z = np.sqrt(rho) * common + np.sqrt(1.0 - rho) * epsilon
    if correlation.model == "gaussian_factor":
        return norm.cdf(z)
    if correlation.model == "student_t_factor":
        scale = np.sqrt(
            random_generator.chisquare(float(correlation.degrees_of_freedom), size=(paths, 1))
            / float(correlation.degrees_of_freedom)
        )
        return t.cdf(z / scale, df=float(correlation.degrees_of_freedom))
    raise ValueError(f"unknown correlation model {correlation.model!r}")


class EmpiricalTerminalMixtureModel:
    """Terminal marginal model for S2b-a model-risk analysis."""

    def __init__(self, batch_size: int | None = None) -> None:
        self.batch_size = batch_size

    def simulate_portfolio(
        self,
        spec: EmpiricalMixtureSpec,
        portfolio_size: int,
        number_of_paths: int,
        random_seed: int,
    ) -> EmpiricalPortfolioResult:
        """Simulate one equally weighted portfolio size."""

        if portfolio_size <= 0 or number_of_paths <= 0:
            raise ValueError("portfolio_size and number_of_paths must be positive")
        spec.validate()
        seed_sequence = np.random.SeedSequence([random_seed, portfolio_size, _stable_spec_seed(spec.name)])
        random_generator = np.random.default_rng(seed_sequence)
        batch_size = self.batch_size or max(64, min(2048, 2_000_000 // portfolio_size))

        terminal_multiples = np.zeros(number_of_paths)
        count_ge_10x = np.zeros(number_of_paths, dtype=int)
        count_ge_50x = np.zeros(number_of_paths, dtype=int)
        largest_share = np.zeros(number_of_paths)
        top3_share = np.zeros(number_of_paths)
        top5_share = np.zeros(number_of_paths)
        hhi = np.zeros(number_of_paths)
        terminal_without_top1 = np.zeros(number_of_paths)
        terminal_without_top3 = np.zeros(number_of_paths)

        for start in range(0, number_of_paths, batch_size):
            stop = min(start + batch_size, number_of_paths)
            batch_paths = stop - start
            returns = inverse_terminal_return_cdf(
                _uniforms(batch_paths, portfolio_size, spec, random_generator), spec
            )
            totals = returns.sum(axis=1)
            terminal_multiples[start:stop] = totals / portfolio_size
            count_ge_10x[start:stop] = (returns >= 10.0).sum(axis=1)
            count_ge_50x[start:stop] = (returns >= 50.0).sum(axis=1)

            positive = totals > 0
            top_count = min(5, portfolio_size)
            top_unsorted = np.partition(returns, portfolio_size - top_count, axis=1)[
                :, -top_count:
            ]
            top_sorted = np.sort(top_unsorted, axis=1)[:, ::-1]
            top1 = top_sorted[:, 0]
            top3 = top_sorted[:, : min(3, portfolio_size)].sum(axis=1)
            top5 = top_sorted[:, :top_count].sum(axis=1)
            batch_largest = np.zeros(batch_paths)
            batch_top3 = np.zeros(batch_paths)
            batch_top5 = np.zeros(batch_paths)
            batch_largest[positive] = top1[positive] / totals[positive]
            batch_top3[positive] = top3[positive] / totals[positive]
            batch_top5[positive] = top5[positive] / totals[positive]
            largest_share[start:stop] = batch_largest
            top3_share[start:stop] = batch_top3
            top5_share[start:stop] = batch_top5
            share_matrix = np.zeros_like(returns)
            share_matrix[positive] = returns[positive] / totals[positive, None]
            hhi[start:stop] = (share_matrix**2).sum(axis=1)
            terminal_without_top1[start:stop] = (totals - top1) / portfolio_size
            terminal_without_top3[start:stop] = (totals - top3) / portfolio_size

        return EmpiricalPortfolioResult(
            terminal_multiples=terminal_multiples,
            count_ge_10x=count_ge_10x,
            count_ge_50x=count_ge_50x,
            largest_share=largest_share,
            top3_share=top3_share,
            top5_share=top5_share,
            hhi=hhi,
            terminal_without_top1=terminal_without_top1,
            terminal_without_top3=terminal_without_top3,
        )


def build_empirical_metrics(
    portfolio: EmpiricalPortfolioResult,
    protection_fraction: float,
    terminal_warrant_fraction: float,
    stop_loss_attachment: float,
    stop_loss_limit: float,
) -> dict[str, float]:
    """Calculate guarantee, winner-dependence and concentration metrics."""

    claims = np.maximum(protection_fraction - portfolio.terminal_multiples, 0.0)
    claims_without_top1 = np.maximum(protection_fraction - portfolio.terminal_without_top1, 0.0)
    claims_without_top3 = np.maximum(protection_fraction - portfolio.terminal_without_top3, 0.0)
    stop_loss = np.asarray(excess_of_loss_payout(claims, stop_loss_attachment, stop_loss_limit))
    metrics = {
        "expected_portfolio_multiple": float(np.mean(portfolio.terminal_multiples)),
        "median_portfolio_multiple": float(np.median(portfolio.terminal_multiples)),
        "probability_nav_below_protected_principal": float(
            np.mean(portfolio.terminal_multiples < protection_fraction)
        ),
        "expected_guarantee_claim_per_unit": float(np.mean(claims)),
        "median_guarantee_claim_per_unit": float(np.median(claims)),
        "probability_at_least_one_10x_winner": float(np.mean(portfolio.count_ge_10x > 0)),
        "probability_at_least_one_50x_winner": float(np.mean(portfolio.count_ge_50x > 0)),
        "expected_number_ge_10x": float(np.mean(portfolio.count_ge_10x)),
        "expected_number_ge_50x": float(np.mean(portfolio.count_ge_50x)),
        "mean_largest_winner_share": float(np.mean(portfolio.largest_share)),
        "mean_top3_share": float(np.mean(portfolio.top3_share)),
        "mean_top5_share": float(np.mean(portfolio.top5_share)),
        "mean_hhi_terminal_value": float(np.mean(portfolio.hhi)),
        "expected_claim_without_top1_per_unit": float(np.mean(claims_without_top1)),
        "expected_claim_without_top3_per_unit": float(np.mean(claims_without_top3)),
        "delta_claim_top1_per_unit": float(np.mean(claims_without_top1 - claims)),
        "delta_claim_top3_per_unit": float(np.mean(claims_without_top3 - claims)),
        "expected_founder_warrant_value_per_unit": float(
            np.mean(portfolio.terminal_multiples * terminal_warrant_fraction)
        ),
        "expected_stop_loss_payout_per_unit": float(np.mean(stop_loss)),
    }
    for confidence in (0.95, 0.99, 0.995):
        suffix = f"{confidence * 100:g}"
        metrics[f"guarantee_claim_var_{suffix}_per_unit"] = empirical_var(claims, confidence)
        metrics[f"guarantee_claim_expected_shortfall_{suffix}_per_unit"] = (
            empirical_expected_shortfall(claims, confidence)
        )
    return metrics


def empirical_diluted_warrant_fraction(initial_warrant: float, dilutions: tuple[float, ...]) -> float:
    """Expose the same warrant arithmetic for empirical dilution scenarios."""

    return diluted_warrant_fraction(initial_warrant, dilutions)


def _stable_spec_seed(name: str) -> int:
    value = 0
    for character in name:
        value = (value * 131 + ord(character)) % (2**32)
    return value

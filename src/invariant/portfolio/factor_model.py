"""Interpretable Gaussian macro and sector dependence for selected portfolios."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.polynomial.hermite import hermgauss
from scipy.stats import norm


DEPENDENCE_PROVENANCE = "MODEL_RISK_SCENARIO"


@dataclass(frozen=True)
class FactorSpecification:
    """Macro/sector copula coefficients and deterministic sector construction."""

    name: str
    portfolio_type: str
    sector_names: tuple[str, ...]
    sector_weights: tuple[float, ...]
    rho_macro: float
    rho_sector: float
    macro_shift: float = 0.0
    sector_shifts: tuple[float, ...] = ()
    provenance: str = DEPENDENCE_PROVENANCE

    def validate(self) -> None:
        if not self.sector_names:
            raise ValueError("at least one sector is required")
        if len(self.sector_names) != len(self.sector_weights):
            raise ValueError("sector_names and sector_weights must have equal length")
        if len(set(self.sector_names)) != len(self.sector_names):
            raise ValueError("sector names must be unique")
        if any(weight < 0 for weight in self.sector_weights):
            raise ValueError("sector weights cannot be negative")
        if abs(sum(self.sector_weights) - 1.0) > 1e-10:
            raise ValueError("sector weights must sum to one")
        if self.rho_macro < 0 or self.rho_sector < 0:
            raise ValueError("rho coefficients must be non-negative")
        if self.rho_macro + self.rho_sector > 1.0 + 1e-12:
            raise ValueError("rho_macro + rho_sector must not exceed one")
        if self.sector_shifts and len(self.sector_shifts) != len(self.sector_names):
            raise ValueError("sector_shifts must be empty or match sector_names")

    def sector_indices(self, portfolio_size: int) -> np.ndarray:
        """Allocate integer company counts by largest remainder, then interleave."""

        self.validate()
        if portfolio_size <= 0:
            raise ValueError("portfolio_size must be positive")
        exact = np.asarray(self.sector_weights) * portfolio_size
        counts = np.floor(exact).astype(int)
        remaining = portfolio_size - int(counts.sum())
        if remaining:
            order = np.argsort(-(exact - counts), kind="stable")
            counts[order[:remaining]] += 1

        # Round-robin interleaving gives every configured prefix a sector mix
        # close to target, which permits nested N comparisons without making
        # early prefixes accidentally single-sector.
        remaining_counts = counts.copy()
        indices: list[int] = []
        while len(indices) < portfolio_size:
            for sector_index in range(len(counts)):
                if remaining_counts[sector_index] > 0:
                    indices.append(sector_index)
                    remaining_counts[sector_index] -= 1
        return np.asarray(indices, dtype=int)


def compose_latent_scores(
    macro_factor: np.ndarray,
    sector_factors: np.ndarray,
    idiosyncratic_factors: np.ndarray,
    sector_indices: np.ndarray,
    specification: FactorSpecification,
) -> np.ndarray:
    """Compose ``Z_i`` while preserving unit marginal variance before shocks."""

    specification.validate()
    macro = np.asarray(macro_factor, dtype=float)
    sectors = np.asarray(sector_factors, dtype=float)
    epsilon = np.asarray(idiosyncratic_factors, dtype=float)
    indices = np.asarray(sector_indices, dtype=int)
    if epsilon.ndim != 2:
        raise ValueError("idiosyncratic_factors must be a paths-by-companies matrix")
    if macro.shape != (epsilon.shape[0],):
        raise ValueError("macro_factor must contain one value per path")
    if sectors.shape != (epsilon.shape[0], len(specification.sector_names)):
        raise ValueError("sector_factors shape does not match paths and sectors")
    if indices.shape != (epsilon.shape[1],):
        raise ValueError("sector_indices must contain one index per company")
    if np.any((indices < 0) | (indices >= sectors.shape[1])):
        raise ValueError("sector index out of range")

    residual_weight = 1.0 - specification.rho_macro - specification.rho_sector
    macro_component = np.sqrt(specification.rho_macro) * (
        macro + specification.macro_shift
    )[:, None]
    shifts = (
        np.asarray(specification.sector_shifts, dtype=float)
        if specification.sector_shifts
        else np.zeros(len(specification.sector_names))
    )
    selected_sector_factors = sectors[:, indices] + shifts[indices][None, :]
    return (
        macro_component
        + np.sqrt(specification.rho_sector) * selected_sector_factors
        + np.sqrt(max(residual_weight, 0.0)) * epsilon
    )


def latent_uniforms(
    paths: int,
    portfolio_size: int,
    specification: FactorSpecification,
    random_generator: np.random.Generator,
) -> np.ndarray:
    """Draw factor-copula uniforms for one batch."""

    if paths <= 0 or portfolio_size <= 0:
        raise ValueError("paths and portfolio_size must be positive")
    specification.validate()
    macro = random_generator.standard_normal(paths)
    sectors = random_generator.standard_normal((paths, len(specification.sector_names)))
    epsilon = random_generator.standard_normal((paths, portfolio_size))
    scores = compose_latent_scores(
        macro,
        sectors,
        epsilon,
        specification.sector_indices(portfolio_size),
        specification,
    )
    return norm.cdf(scores)


def factor_variance_coefficients(specification: FactorSpecification) -> tuple[float, float, float]:
    """Return macro, sector, and idiosyncratic variance coefficients."""

    specification.validate()
    return (
        specification.rho_macro,
        specification.rho_sector,
        1.0 - specification.rho_macro - specification.rho_sector,
    )


def literal_all_failure_probability_one_factor(
    probability_zero: float,
    portfolio_size: int,
    common_variance_share: float,
    quadrature_nodes: int,
) -> float:
    """Evaluate ``E[P(X_i=0|Z)^N]`` for one Gaussian common factor.

    This applies directly to AI-only portfolios where macro and AI-sector
    factors combine into one normal factor with variance share
    ``rho_macro+rho_sector``. At zero dependence it reduces exactly to
    ``probability_zero**N``.
    """

    if not 0 <= probability_zero <= 1:
        raise ValueError("probability_zero must be in [0, 1]")
    if portfolio_size <= 0 or quadrature_nodes <= 0:
        raise ValueError("portfolio_size and quadrature_nodes must be positive")
    if not 0 <= common_variance_share < 1:
        raise ValueError("common_variance_share must be in [0, 1)")
    if common_variance_share == 0:
        return probability_zero**portfolio_size
    threshold = norm.ppf(probability_zero)
    nodes, weights = hermgauss(quadrature_nodes)
    common = np.sqrt(2.0) * nodes
    conditional = norm.cdf(
        (threshold - np.sqrt(common_variance_share) * common)
        / np.sqrt(1.0 - common_variance_share)
    )
    return float(np.sum(weights * conditional**portfolio_size) / np.sqrt(np.pi))

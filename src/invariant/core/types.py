"""Typed domain objects for the S2a quantitative vertical slice."""

from dataclasses import dataclass, field
from typing import Any

from invariant.core.enums import MacroState
from invariant.core.provenance import Parameter


OUTCOME_BAND_NAMES = (
    "total_failure",
    "partial_recovery",
    "modest_success",
    "large_success",
    "extreme_winner",
)


@dataclass(frozen=True)
class OutcomeBandParameters:
    """Probability and uniform return range for one synthetic outcome band."""

    probability: Parameter[float]
    minimum_return_multiple: Parameter[float]
    maximum_return_multiple: Parameter[float]


@dataclass(frozen=True)
class MacroRegimeParameters:
    """Synthetic startup outcome distribution conditional on a shared macro state."""

    outcome_bands: dict[str, OutcomeBandParameters]
    follow_on_probability: Parameter[float]
    exit_probability: Parameter[float]


@dataclass(frozen=True)
class MacroParameters:
    """Shared-state macro dependence for an entire simulated portfolio."""

    initial_state_probabilities: dict[MacroState, Parameter[float]]
    regimes: dict[MacroState, MacroRegimeParameters]


@dataclass(frozen=True)
class PortfolioParameters:
    """Equal-weighted portfolio sizes included in the diversification sweep."""

    portfolio_sizes: tuple[int, ...]
    baseline_portfolio_size: int
    equal_weighted: bool = True


@dataclass(frozen=True)
class GuaranteeTerms:
    """Principal-floor levels and generic excess-of-loss terms."""

    protection_fractions: tuple[Parameter[float], ...]
    baseline_protection_fraction: Parameter[float]
    stop_loss_attachment_fraction: Parameter[float]
    stop_loss_limit_fraction: Parameter[float]


@dataclass(frozen=True)
class FounderWarrantTerms:
    """Simple founder-warrant dilution assumptions."""

    initial_warrant_percentage: Parameter[float]
    number_of_financing_rounds: Parameter[int]
    dilution_percentage_per_round: Parameter[float]


@dataclass(frozen=True)
class SimulationConfig:
    """Complete, serializable input to a deterministic S2a run."""

    model_version: str
    scenario_name: str
    scenario_description: str
    assumption_status: str
    initial_principal: Parameter[float]
    horizon_years: int
    number_of_simulations: int
    random_seed: int
    portfolio_parameters: PortfolioParameters
    macro_parameters: MacroParameters
    guarantee_terms: GuaranteeTerms
    founder_warrant_terms: FounderWarrantTerms


@dataclass(frozen=True)
class GridPointResult:
    """Aggregate outputs for one portfolio-size/protection-level pair."""

    portfolio_size: int
    protection_fraction: float
    metrics: dict[str, float]

    def as_dict(self) -> dict[str, Any]:
        return {
            "portfolio_size": self.portfolio_size,
            "protection_fraction": self.protection_fraction,
            "metrics": self.metrics,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GridPointResult":
        return cls(
            portfolio_size=int(data["portfolio_size"]),
            protection_fraction=float(data["protection_fraction"]),
            metrics={str(key): float(value) for key, value in data["metrics"].items()},
        )


@dataclass(frozen=True)
class SimulationResult:
    """Serializable output from the complete S2a diversification sweep."""

    model_version: str
    scenario_name: str
    random_seed: int
    baseline_portfolio_size: int
    baseline_protection_fraction: float
    baseline_terminal_multiples: tuple[float, ...]
    baseline_guarantee_claims_per_unit: tuple[float, ...]
    baseline_founder_warrant_values_per_unit: tuple[float, ...]
    baseline_stop_loss_payouts_per_unit: tuple[float, ...]
    grid_results: tuple[GridPointResult, ...]
    baseline_macro_state_counts: dict[str, int]
    event_counts: dict[str, int]
    unsupported_quantities: tuple[str, ...] = field(default_factory=tuple)

    @property
    def baseline_metrics(self) -> dict[str, float]:
        """Return metrics for the configured baseline grid point."""

        for point in self.grid_results:
            if (
                point.portfolio_size == self.baseline_portfolio_size
                and point.protection_fraction == self.baseline_protection_fraction
            ):
                return point.metrics
        raise ValueError("Baseline grid point is missing from results")

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe result representation."""

        return {
            "model_version": self.model_version,
            "scenario_name": self.scenario_name,
            "random_seed": self.random_seed,
            "baseline_portfolio_size": self.baseline_portfolio_size,
            "baseline_protection_fraction": self.baseline_protection_fraction,
            "baseline_terminal_multiples": list(self.baseline_terminal_multiples),
            "baseline_guarantee_claims_per_unit": list(
                self.baseline_guarantee_claims_per_unit
            ),
            "baseline_founder_warrant_values_per_unit": list(
                self.baseline_founder_warrant_values_per_unit
            ),
            "baseline_stop_loss_payouts_per_unit": list(
                self.baseline_stop_loss_payouts_per_unit
            ),
            "grid_results": [point.as_dict() for point in self.grid_results],
            "baseline_macro_state_counts": self.baseline_macro_state_counts,
            "event_counts": self.event_counts,
            "unsupported_quantities": list(self.unsupported_quantities),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SimulationResult":
        """Reconstruct a result from ``results.json`` without changing values."""

        return cls(
            model_version=str(data["model_version"]),
            scenario_name=str(data["scenario_name"]),
            random_seed=int(data["random_seed"]),
            baseline_portfolio_size=int(data["baseline_portfolio_size"]),
            baseline_protection_fraction=float(data["baseline_protection_fraction"]),
            baseline_terminal_multiples=tuple(data["baseline_terminal_multiples"]),
            baseline_guarantee_claims_per_unit=tuple(
                data["baseline_guarantee_claims_per_unit"]
            ),
            baseline_founder_warrant_values_per_unit=tuple(
                data["baseline_founder_warrant_values_per_unit"]
            ),
            baseline_stop_loss_payouts_per_unit=tuple(
                data["baseline_stop_loss_payouts_per_unit"]
            ),
            grid_results=tuple(
                GridPointResult.from_dict(point) for point in data["grid_results"]
            ),
            baseline_macro_state_counts={
                str(key): int(value)
                for key, value in data["baseline_macro_state_counts"].items()
            },
            event_counts={str(key): int(value) for key, value in data["event_counts"].items()},
            unsupported_quantities=tuple(data.get("unsupported_quantities", [])),
        )

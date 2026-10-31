"""Model A: transparent synthetic terminal portfolio simulation."""

from dataclasses import dataclass

import numpy as np

from invariant.core.contracts import (
    diluted_warrant_fraction,
    excess_of_loss_payout,
    principal_floor_claim,
)
from invariant.core.enums import MacroState
from invariant.core.types import (
    OUTCOME_BAND_NAMES,
    GridPointResult,
    MacroRegimeParameters,
    SimulationConfig,
    SimulationResult,
)
from invariant.macro.sampler import sample_macro_states
from invariant.risk.metrics import build_scenario_metrics


@dataclass(frozen=True)
class PortfolioSimulation:
    """Stochastic outputs that do not depend on the protection fraction."""

    terminal_multiples: np.ndarray
    extreme_winner_counts: np.ndarray
    largest_investment_shares: np.ndarray
    macro_states: np.ndarray


def _sample_regime_returns(
    regime: MacroRegimeParameters,
    number_of_paths: int,
    portfolio_size: int,
    random_generator: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray]:
    """Sample one regime's five-band synthetic outcome distribution.

    One uniform draw selects both the band and a uniform location inside that
    band's configured return range. This keeps every probability and return
    boundary in YAML while avoiding hidden distribution parameters.
    """

    uniforms = random_generator.random((number_of_paths, portfolio_size))
    returns = np.zeros_like(uniforms)
    extreme_flags = np.zeros_like(uniforms, dtype=bool)
    lower_probability = 0.0
    for band_name in OUTCOME_BAND_NAMES:
        band = regime.outcome_bands[band_name]
        probability = float(band.probability.value)
        upper_probability = lower_probability + probability
        if probability > 0:
            in_band = (uniforms >= lower_probability) & (uniforms < upper_probability)
            minimum = float(band.minimum_return_multiple.value)
            maximum = float(band.maximum_return_multiple.value)
            within_band = (uniforms[in_band] - lower_probability) / probability
            returns[in_band] = minimum + within_band * (maximum - minimum)
            if band_name == "extreme_winner":
                extreme_flags[in_band] = True
        lower_probability = upper_probability
    return returns, extreme_flags


class TerminalStructuralModel:
    """Synthetic five-band terminal model with a shared portfolio macro state.

    For each portfolio path, one NORMAL, WEAK or CRISIS state is sampled. Every
    startup in that path uses the corresponding five-band outcome distribution,
    creating transparent systemic dependence without a copula.
    """

    batch_size = 256

    def simulate_portfolio(
        self, config: SimulationConfig, portfolio_size: int
    ) -> PortfolioSimulation:
        """Simulate one portfolio size with an explicit deterministic RNG stream."""

        if portfolio_size <= 0:
            raise ValueError("portfolio_size must be positive")
        seed_sequence = np.random.SeedSequence([config.random_seed, portfolio_size])
        random_generator = np.random.default_rng(seed_sequence)
        number_of_simulations = config.number_of_simulations
        macro_states = sample_macro_states(
            config.macro_parameters, number_of_simulations, random_generator
        )
        terminal_multiples = np.zeros(number_of_simulations, dtype=float)
        extreme_winner_counts = np.zeros(number_of_simulations, dtype=int)
        largest_investment_shares = np.zeros(number_of_simulations, dtype=float)

        for start in range(0, number_of_simulations, self.batch_size):
            stop = min(start + self.batch_size, number_of_simulations)
            batch_states = macro_states[start:stop]
            batch_returns = np.zeros((stop - start, portfolio_size), dtype=float)
            batch_extreme = np.zeros((stop - start, portfolio_size), dtype=bool)
            for state in MacroState:
                state_mask = np.asarray(
                    [sampled_state is state for sampled_state in batch_states]
                )
                state_count = int(state_mask.sum())
                if state_count == 0:
                    continue
                state_returns, state_extreme = _sample_regime_returns(
                    config.macro_parameters.regimes[state],
                    state_count,
                    portfolio_size,
                    random_generator,
                )
                batch_returns[state_mask] = state_returns
                batch_extreme[state_mask] = state_extreme

            total_returns = batch_returns.sum(axis=1)
            terminal_multiples[start:stop] = total_returns / portfolio_size
            extreme_winner_counts[start:stop] = batch_extreme.sum(axis=1)
            positive = total_returns > 0
            batch_concentration = np.zeros(stop - start, dtype=float)
            batch_concentration[positive] = (
                batch_returns[positive].max(axis=1) / total_returns[positive]
            )
            largest_investment_shares[start:stop] = batch_concentration

        return PortfolioSimulation(
            terminal_multiples=terminal_multiples,
            extreme_winner_counts=extreme_winner_counts,
            largest_investment_shares=largest_investment_shares,
            macro_states=macro_states,
        )

    def simulate(
        self, config: SimulationConfig, event_counts: dict[str, int] | None = None
    ) -> SimulationResult:
        """Run the complete portfolio-size and protection-level grid."""

        grid_results: list[GridPointResult] = []
        baseline_terminal_multiples: tuple[float, ...] | None = None
        baseline_claims: tuple[float, ...] | None = None
        baseline_warrants: tuple[float, ...] | None = None
        baseline_stop_loss: tuple[float, ...] | None = None
        baseline_macro_counts: dict[str, int] | None = None
        baseline_size = config.portfolio_parameters.baseline_portfolio_size
        baseline_protection = float(
            config.guarantee_terms.baseline_protection_fraction.value
        )
        warrant_terms = config.founder_warrant_terms
        terminal_warrant_fraction = diluted_warrant_fraction(
            float(warrant_terms.initial_warrant_percentage.value),
            [float(warrant_terms.dilution_percentage_per_round.value)]
            * int(warrant_terms.number_of_financing_rounds.value),
        )
        attachment = float(config.guarantee_terms.stop_loss_attachment_fraction.value)
        limit = float(config.guarantee_terms.stop_loss_limit_fraction.value)

        for portfolio_size in config.portfolio_parameters.portfolio_sizes:
            portfolio = self.simulate_portfolio(config, portfolio_size)
            founder_warrant_values = (
                portfolio.terminal_multiples * terminal_warrant_fraction
            )
            for protection_parameter in config.guarantee_terms.protection_fractions:
                protection_fraction = float(protection_parameter.value)
                claims = np.asarray(
                    principal_floor_claim(
                        portfolio.terminal_multiples, protection_fraction
                    ),
                    dtype=float,
                )
                stop_loss_payouts = np.asarray(
                    excess_of_loss_payout(claims, attachment, limit), dtype=float
                )
                metrics = build_scenario_metrics(
                    terminal_multiples=portfolio.terminal_multiples,
                    guarantee_claims_per_unit=claims,
                    stop_loss_payouts_per_unit=stop_loss_payouts,
                    founder_warrant_values_per_unit=founder_warrant_values,
                    extreme_winner_counts=portfolio.extreme_winner_counts,
                    largest_investment_shares=portfolio.largest_investment_shares,
                    protection_fraction=protection_fraction,
                )
                grid_results.append(
                    GridPointResult(portfolio_size, protection_fraction, metrics)
                )
                if (
                    portfolio_size == baseline_size
                    and protection_fraction == baseline_protection
                ):
                    baseline_terminal_multiples = tuple(
                        float(value) for value in portfolio.terminal_multiples
                    )
                    baseline_claims = tuple(float(value) for value in claims)
                    baseline_warrants = tuple(
                        float(value) for value in founder_warrant_values
                    )
                    baseline_stop_loss = tuple(
                        float(value) for value in stop_loss_payouts
                    )
                    baseline_macro_counts = {
                        state.value: int(
                            sum(
                                sampled_state is state
                                for sampled_state in portfolio.macro_states
                            )
                        )
                        for state in MacroState
                    }

        if any(
            value is None
            for value in (
                baseline_terminal_multiples,
                baseline_claims,
                baseline_warrants,
                baseline_stop_loss,
                baseline_macro_counts,
            )
        ):
            raise ValueError("Configured baseline grid point was not simulated")
        return SimulationResult(
            model_version=config.model_version,
            scenario_name=config.scenario_name,
            random_seed=config.random_seed,
            baseline_portfolio_size=baseline_size,
            baseline_protection_fraction=baseline_protection,
            baseline_terminal_multiples=baseline_terminal_multiples,
            baseline_guarantee_claims_per_unit=baseline_claims,
            baseline_founder_warrant_values_per_unit=baseline_warrants,
            baseline_stop_loss_payouts_per_unit=baseline_stop_loss,
            grid_results=tuple(grid_results),
            baseline_macro_state_counts=baseline_macro_counts,
            event_counts=dict(event_counts or {}),
            unsupported_quantities=(
                "U: investor-capital uplift caused by protection",
                "K: risk capital required per £1 protected",
                "R: PlatformCo revenue per £1 protected",
            ),
        )

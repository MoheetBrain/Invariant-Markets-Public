"""Minimal startup state-machine prototype for Model B."""

from collections import Counter
from dataclasses import dataclass

import numpy as np

from invariant.core.enums import MacroState, StartupState
from invariant.core.types import SimulationConfig
from invariant.macro.sampler import sample_macro_states


@dataclass(frozen=True)
class StartupPath:
    """One auditable event-driven prototype path."""

    startup_index: int
    macro_state: MacroState
    states: tuple[StartupState, ...]


def simulate_startup_path(
    startup_index: int,
    macro_state: MacroState,
    config: SimulationConfig,
    random_generator: np.random.Generator,
) -> StartupPath:
    """Simulate ``INITIAL → ACTIVE → ...`` with intentionally few events.

    The prototype supports follow-on and exit branches but does not yet model
    financing amounts, dilution cash flows, timing, or censoring.
    """

    regime = config.macro_parameters.regimes[macro_state]
    states = [StartupState.INITIAL]
    failure_probability = float(
        regime.outcome_bands["total_failure"].probability.value
    )
    if random_generator.random() < failure_probability:
        states.append(StartupState.FAILURE)
        return StartupPath(startup_index, macro_state, tuple(states))
    states.append(StartupState.ACTIVE)
    if random_generator.random() < float(regime.follow_on_probability.value):
        states.extend((StartupState.FOLLOW_ON, StartupState.ACTIVE))
    if random_generator.random() < float(regime.exit_probability.value):
        states.append(StartupState.EXIT)
    return StartupPath(startup_index, macro_state, tuple(states))


def simulate_event_driven_prototype(config: SimulationConfig) -> dict[str, int]:
    """Run one path per startup and return state counts for reporting."""

    random_generator = np.random.default_rng(config.random_seed + 1)
    number_of_startups = config.portfolio_parameters.baseline_portfolio_size
    states = sample_macro_states(
        config.macro_parameters, number_of_startups, random_generator
    )
    counts: Counter[str] = Counter()
    for startup_index, macro_state in enumerate(states):
        path = simulate_startup_path(startup_index, macro_state, config, random_generator)
        counts.update(state.value for state in path.states)
    return dict(sorted(counts.items()))

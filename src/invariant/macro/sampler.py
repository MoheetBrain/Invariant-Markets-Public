"""Deterministic sampling of shared macro states."""

import numpy as np

from invariant.core.enums import MacroState
from invariant.core.types import MacroParameters


def sample_macro_states(
    macro_parameters: MacroParameters,
    number_of_simulations: int,
    random_generator: np.random.Generator,
) -> np.ndarray:
    """Sample one shared macro state per portfolio simulation.

    All startups in a simulated portfolio share that state.  This is the
    smallest explicit wrong-way-risk mechanism: the same state changes failure,
    winner, liquidity and event assumptions for the whole portfolio.
    """

    if number_of_simulations <= 0:
        raise ValueError("number_of_simulations must be positive")
    states = tuple(MacroState)
    probabilities = np.array(
        [macro_parameters.initial_state_probabilities[state].value for state in states],
        dtype=float,
    )
    # Draw integer indices first. NumPy may coerce str-backed Enum members to a
    # short Unicode dtype (and truncate values such as ``MacroState.NORMAL``)
    # when choosing directly from the Enum tuple.
    sampled_indices = random_generator.choice(
        len(states), size=number_of_simulations, p=probabilities
    )
    return np.asarray([states[int(index)] for index in sampled_indices], dtype=object)

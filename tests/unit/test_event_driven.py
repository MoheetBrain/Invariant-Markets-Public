import numpy as np

from invariant.core.enums import MacroState, StartupState
from invariant.models.event_driven.prototype import simulate_startup_path


def test_event_path_has_valid_initial_and_terminal_states(base_config):
    path = simulate_startup_path(0, MacroState.NORMAL, base_config, np.random.default_rng(4))
    assert path.states[0] is StartupState.INITIAL
    assert path.states[-1] in {StartupState.ACTIVE, StartupState.EXIT, StartupState.FAILURE}
    if StartupState.EXIT in path.states:
        assert path.states[-1] is StartupState.EXIT


def test_event_prototype_is_seed_deterministic(base_config):
    from invariant.models.event_driven.prototype import simulate_event_driven_prototype

    assert simulate_event_driven_prototype(base_config) == simulate_event_driven_prototype(base_config)

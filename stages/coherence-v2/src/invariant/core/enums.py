"""Small, explicit enumerations used throughout the model."""

from enum import Enum


class MacroState(str, Enum):
    """A deliberately small initial macro-state vocabulary.

    The three states are a prototype abstraction, not a claim that the final model
    should have exactly three regimes.
    """

    NORMAL = "normal"
    WEAK = "weak"
    CRISIS = "crisis"


class StartupState(str, Enum):
    """States supported by the event-driven prototype."""

    INITIAL = "initial"
    ACTIVE = "active"
    FOLLOW_ON = "follow_on"
    EXIT = "exit"
    FAILURE = "failure"

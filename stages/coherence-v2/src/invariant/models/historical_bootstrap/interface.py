"""Interface placeholder for empirical cohort bootstrapping."""

from typing import Any

from invariant.core.types import SimulationConfig


class HistoricalBootstrapModel:
    """Reserved interface; no historical data are fabricated in Version 1."""

    def simulate(self, config: SimulationConfig, data: Any = None) -> Any:
        """Fail loudly until a documented historical dataset is supplied."""

        raise NotImplementedError(
            "Historical Bootstrap is an interface only; provide a versioned, "
            "documented historical cohort dataset before implementing it."
        )

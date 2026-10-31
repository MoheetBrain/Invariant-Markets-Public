"""Explicit parameter provenance.

The model intentionally refuses to treat an undocumented number as an observed
fact.  Parameters carry their value, units, status, source and notes together so
that configuration and reporting can preserve the distinction between data and
assumptions.
"""

from dataclasses import asdict, dataclass
from enum import Enum
from math import isfinite
from typing import Any, Generic, TypeVar


class ProvenanceStatus(str, Enum):
    """Status vocabulary for parameter provenance."""

    OBSERVED = "OBSERVED"
    FITTED = "FITTED"
    CALIBRATED = "CALIBRATED"
    SCENARIO = "SCENARIO"
    EXPERT = "EXPERT"
    LEGAL_UNVERIFIED = "LEGAL_UNVERIFIED"


ValueType = TypeVar("ValueType")


@dataclass(frozen=True)
class Parameter(Generic[ValueType]):
    """A numeric or categorical parameter with auditable provenance."""

    value: ValueType
    units: str
    status: ProvenanceStatus
    source: str
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.units.strip():
            raise ValueError("Parameter units must be explicit")
        if not self.source.strip():
            raise ValueError("Parameter source must be explicit")
        if isinstance(self.value, (int, float)) and not isinstance(self.value, bool):
            if not isfinite(float(self.value)):
                raise ValueError("Parameter value must be finite")

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON/YAML-safe representation."""

        data = asdict(self)
        data["status"] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Parameter[Any]":
        """Construct a parameter from a configuration mapping."""

        required = {"value", "units", "status", "source"}
        missing = required.difference(data)
        if missing:
            raise ValueError(f"Parameter specification missing keys: {sorted(missing)}")
        return cls(
            value=data["value"],
            units=str(data["units"]),
            status=ProvenanceStatus(str(data["status"]).upper()),
            source=str(data["source"]),
            notes=str(data.get("notes", "")),
        )

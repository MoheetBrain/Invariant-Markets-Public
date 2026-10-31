"""Loading and validation for empirical calibration evidence.

The S2b-a layer deliberately stores observations separately from model
parameters.  These helpers keep the evidence registry auditable without forcing
rounded public statistics to masquerade as row-level data.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


DATA_QUALITY_CLASSES = {
    "OBSERVED_RAW",
    "OBSERVED_AGGREGATE",
    "FITTED",
    "CALIBRATED",
    "PROXY",
    "EXPERT",
    "MODEL_RISK_SCENARIO",
    "SYNTHETIC_SCENARIO",
    "UNKNOWN",
}


def load_yaml_mapping(path: str | Path) -> dict[str, Any]:
    """Load one YAML mapping and reject non-mapping roots."""

    with Path(path).open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return data


def _iter_evidence_items(value: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if isinstance(value, dict):
        if {"source_id", "object_measured", "provenance"}.issubset(value):
            items.append(value)
        for child in value.values():
            items.extend(_iter_evidence_items(child))
    elif isinstance(value, list):
        for child in value:
            items.extend(_iter_evidence_items(child))
    return items


def evidence_items(constraints: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    """Return every nested evidence item that declares source/object/provenance."""

    return tuple(_iter_evidence_items(constraints))


def source_ids_used(constraints: dict[str, Any]) -> set[str]:
    """Collect source identifiers referenced by empirical constraints."""

    return {
        str(item["source_id"])
        for item in evidence_items(constraints)
        if str(item.get("source_id", "")).strip()
    }


def validate_source_registry(registry: dict[str, Any]) -> None:
    """Validate the registry shape required by the S2b-a audit brief."""

    sources = registry.get("sources")
    if not isinstance(sources, dict) or not sources:
        raise ValueError("source_registry.yaml must define a non-empty sources mapping")
    required = {
        "title",
        "organisation_authors",
        "year",
        "geography",
        "sample_definition",
        "unit_of_observation",
        "variable_measured",
        "public_or_proprietary",
        "raw_data_accessible",
        "values_used",
        "provenance_classification",
        "known_biases",
        "notes",
    }
    for source_id, source in sources.items():
        if not isinstance(source, dict):
            raise ValueError(f"{source_id} must be a mapping")
        missing = required - set(source)
        if missing:
            raise ValueError(f"{source_id} is missing required fields: {sorted(missing)}")
        provenance = str(source["provenance_classification"])
        if provenance not in DATA_QUALITY_CLASSES:
            raise ValueError(f"{source_id} has invalid provenance {provenance!r}")


def validate_empirical_constraints(
    constraints: dict[str, Any], registry: dict[str, Any] | None = None
) -> None:
    """Validate evidence classes, object mapping and source references."""

    classes = set(constraints.get("data_quality_classes", []))
    if not DATA_QUALITY_CLASSES.issubset(classes):
        raise ValueError("constraints must list every supported data quality class")

    items = evidence_items(constraints)
    if not items:
        raise ValueError("empirical constraints must contain evidence items")

    known_sources = set((registry or {}).get("sources", {}))
    for item in items:
        provenance = str(item["provenance"])
        if provenance not in DATA_QUALITY_CLASSES:
            raise ValueError(f"invalid evidence provenance {provenance!r}")
        if not str(item["object_measured"]).strip():
            raise ValueError("every evidence item must declare object_measured")
        source_id = str(item["source_id"])
        if registry is not None and source_id not in known_sources:
            raise ValueError(f"constraint references unknown source_id {source_id!r}")
        if "probability" in item:
            probability = float(item["probability"])
            if not 0 <= probability <= 1:
                raise ValueError("constraint probabilities must be in [0, 1]")
        if "value" in item and isinstance(item["value"], (int, float)):
            if not float("-inf") < float(item["value"]) < float("inf"):
                raise ValueError("constraint values must be finite")


def load_source_registry(path: str | Path) -> dict[str, Any]:
    """Load and validate ``source_registry.yaml``."""

    registry = load_yaml_mapping(path)
    validate_source_registry(registry)
    return registry


def load_empirical_constraints(
    path: str | Path, source_registry: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Load and validate ``empirical_constraints_v1.yaml``."""

    constraints = load_yaml_mapping(path)
    validate_empirical_constraints(constraints, source_registry)
    return constraints

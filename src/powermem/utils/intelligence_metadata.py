"""Helpers for reading Ebbinghaus intelligence metadata."""

from collections.abc import Mapping
from typing import Any, Optional


def _as_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}


def extract_intelligence_metadata(metadata: Any) -> Mapping[str, Any]:
    """Return nested Ebbinghaus metadata when present."""
    return _as_mapping(_as_mapping(metadata).get("intelligence"))


def extract_retention_score(metadata: Any) -> Optional[float]:
    """Read retention from legacy top-level or canonical intelligence metadata."""
    metadata_map = _as_mapping(metadata)
    retention_score = metadata_map.get("retention_score")
    if retention_score is not None:
        return retention_score

    intelligence = extract_intelligence_metadata(metadata)
    return intelligence.get("current_retention")


def extract_importance_level(metadata: Any) -> Optional[float]:
    """Read importance from legacy top-level or canonical intelligence metadata."""
    metadata_map = _as_mapping(metadata)
    importance_level = metadata_map.get("importance_level")
    if importance_level is not None:
        return importance_level

    intelligence = extract_intelligence_metadata(metadata)
    importance_score = intelligence.get("importance_score")
    if importance_score is not None:
        return importance_score

    return metadata_map.get("importance_score")

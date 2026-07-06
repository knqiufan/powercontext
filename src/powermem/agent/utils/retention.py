"""Retention helpers shared by AgentMemory managers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

from powermem.agent.utils.memory_id import normalize_memory_id
from powermem.intelligence.ebbinghaus_algorithm import EbbinghausAlgorithm
from powermem.utils.utils import get_current_datetime

DELETE_RETENTION_THRESHOLD = 0.1
ARCHIVE_RETENTION_THRESHOLD = 0.3

RETENTION_ACTION_DELETE = "delete"
RETENTION_ACTION_ARCHIVE = "archive"
RETENTION_ACTION_KEEP = "keep"


@dataclass(frozen=True)
class AgentRetentionUpdate:
    """Calculated retention state for a cached Agent memory."""

    score: float
    snapshot_time: Any
    has_intelligence: bool
    access_count: int = 0
    reinforced: bool = False
    intelligence_updates: Optional[Dict[str, Any]] = None


def get_agent_ebbinghaus_algorithm(intelligent_manager: Any) -> EbbinghausAlgorithm:
    """Return the manager's configured Ebbinghaus algorithm."""
    algorithm = getattr(intelligent_manager, "ebbinghaus_algorithm", None)
    if isinstance(algorithm, EbbinghausAlgorithm):
        return algorithm
    return EbbinghausAlgorithm({})


def calculate_agent_retention(
    memory_data: Dict[str, Any],
    algorithm: EbbinghausAlgorithm,
    *,
    reinforce_due: bool = False,
) -> AgentRetentionUpdate:
    """Calculate effective retention using intelligence metadata when present."""
    metadata = memory_data.get("metadata") or {}
    intelligence = metadata.get("intelligence") or {}
    snapshot_time = get_current_datetime()
    access_count = _resolve_access_count(memory_data, metadata, intelligence)
    intelligence_updates = None
    reinforced = False
    if intelligence:
        normalized = _build_algorithm_memory(
            memory_data, metadata, intelligence, access_count
        )
        if reinforce_due and _should_reinforce(memory_data, intelligence, snapshot_time):
            intelligence_updates = algorithm.reinforce(normalized)
            intelligence = {**intelligence, **intelligence_updates}
            normalized = _build_algorithm_memory(
                memory_data, metadata, intelligence, access_count
            )
            reinforced = True
        score = algorithm.calculate_current_retention(normalized)
    else:
        score = _coerce_score(memory_data.get("retention_score"), default=1.0)
    return AgentRetentionUpdate(
        score=_clamp_score(score),
        snapshot_time=snapshot_time,
        has_intelligence=bool(intelligence),
        access_count=access_count,
        reinforced=reinforced,
        intelligence_updates=intelligence_updates,
    )


def apply_agent_retention(
    memory_data: Dict[str, Any],
    retention_update: AgentRetentionUpdate,
) -> Dict[str, Any]:
    """Synchronize effective retention to cache and metadata."""
    score = _clamp_score(retention_update.score)
    metadata = dict(memory_data.get("metadata") or {})
    metadata["retention_score"] = score
    memory_data["retention_score"] = score

    intelligence = dict(metadata.get("intelligence") or {})
    if retention_update.has_intelligence:
        if retention_update.intelligence_updates:
            intelligence.update(retention_update.intelligence_updates)
        intelligence["current_retention"] = score
        intelligence["last_reviewed"] = retention_update.snapshot_time.isoformat()
        intelligence["access_count"] = retention_update.access_count
        metadata["intelligence"] = intelligence
        if intelligence.get("decay_rate") is not None:
            memory_data["decay_rate"] = intelligence["decay_rate"]

    memory_data["metadata"] = metadata
    return metadata


def classify_agent_retention(
    memory_data: Dict[str, Any],
    retention_update: AgentRetentionUpdate,
    algorithm: EbbinghausAlgorithm,
) -> str:
    """Classify cleanup action using Core Ebbinghaus decisions when available."""
    metadata = memory_data.get("metadata") or {}
    intelligence = metadata.get("intelligence") or {}
    if not intelligence:
        return classify_retention(retention_update.score)

    normalized = _build_algorithm_memory(
        memory_data,
        metadata,
        intelligence,
        retention_update.access_count,
    )
    if algorithm.should_forget(normalized):
        return RETENTION_ACTION_DELETE
    if algorithm.should_archive(normalized):
        return RETENTION_ACTION_ARCHIVE
    return RETENTION_ACTION_KEEP


def classify_retention(score: float) -> str:
    """Classify retention score for Agent cleanup thresholds."""
    bounded = _clamp_score(score)
    if bounded < DELETE_RETENTION_THRESHOLD:
        return RETENTION_ACTION_DELETE
    if bounded < ARCHIVE_RETENTION_THRESHOLD:
        return RETENTION_ACTION_ARCHIVE
    return RETENTION_ACTION_KEEP


def restore_agent_retention_fields(memory_data: Dict[str, Any]) -> None:
    """Restore cache-level retention fields from persisted metadata."""
    metadata = memory_data.get("metadata") or {}
    intelligence = metadata.get("intelligence") or {}
    retention = _first_present(
        intelligence.get("current_retention"),
        metadata.get("retention_score"),
        memory_data.get("retention_score"),
    )
    importance = _first_present(
        intelligence.get("importance_score"),
        metadata.get("importance_level"),
        memory_data.get("importance_level"),
    )
    if retention is not None:
        memory_data["retention_score"] = _clamp_score(retention)
    if importance is not None:
        memory_data["importance_level"] = importance


def restore_effective_retention_fields(
    memory_data: Dict[str, Any],
    algorithm: EbbinghausAlgorithm,
) -> None:
    """Restore cache-level fields with effective runtime retention."""
    restore_agent_retention_fields(memory_data)
    metadata = dict(memory_data.get("metadata") or {})
    if not metadata.get("intelligence"):
        return

    retention_update = calculate_agent_retention(memory_data, algorithm)
    apply_agent_retention(memory_data, retention_update)


def persist_agent_retention_metadata(
    memory_instance: Any,
    memory_data: Dict[str, Any],
) -> None:
    """Persist synchronized Agent retention metadata without plugin reprocessing."""
    memory_id = memory_data.get("id")
    if not memory_instance or memory_id is None:
        return
    try:
        normalized_id = normalize_memory_id(memory_id)
    except (TypeError, ValueError):
        return
    storage = getattr(memory_instance, "storage", None)
    update_memory = getattr(storage, "update_memory", None)
    if not callable(update_memory):
        return

    update_memory(
        normalized_id,
        {
            "metadata": memory_data.get("metadata") or {},
            "updated_at": get_current_datetime(),
        },
        memory_data.get("user_id"),
        memory_data.get("agent_id"),
    )


def _build_algorithm_memory(
    memory_data: Dict[str, Any],
    metadata: Dict[str, Any],
    intelligence: Dict[str, Any],
    access_count: int,
) -> Dict[str, Any]:
    normalized = dict(memory_data)
    normalized_metadata = dict(metadata)
    normalized_metadata["intelligence"] = intelligence
    normalized["metadata"] = normalized_metadata
    normalized["access_count"] = access_count
    memory_type = _normalize_memory_type(
        memory_data.get("memory_type"),
        metadata.get("memory_type"),
        intelligence.get("memory_type"),
    )
    if memory_type:
        normalized["memory_type"] = memory_type
    importance = _first_present(
        memory_data.get("importance_score"),
        metadata.get("importance_score"),
        intelligence.get("importance_score"),
    )
    if importance is not None:
        normalized["importance_score"] = importance
    return normalized


def _should_reinforce(
    memory_data: Dict[str, Any],
    intelligence: Dict[str, Any],
    snapshot_time: datetime,
) -> bool:
    next_review = _parse_datetime(intelligence.get("next_review"))
    last_accessed = _parse_datetime(memory_data.get("last_accessed"))
    if next_review is None or last_accessed is None:
        return False
    next_review = _align_timezone(next_review, snapshot_time)
    last_accessed = _align_timezone(last_accessed, snapshot_time)
    return last_accessed >= next_review and snapshot_time >= next_review


def _align_timezone(value: datetime, reference: datetime) -> datetime:
    if value.tzinfo is None and reference.tzinfo is not None:
        return value.replace(tzinfo=reference.tzinfo)
    if value.tzinfo is not None and reference.tzinfo is None:
        return value.replace(tzinfo=None)
    return value


def _parse_datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return None


def _resolve_access_count(
    memory_data: Dict[str, Any],
    metadata: Dict[str, Any],
    intelligence: Dict[str, Any],
) -> int:
    counts = [
        _coerce_non_negative_int(memory_data.get("access_count")),
        _coerce_non_negative_int(metadata.get("access_count")),
        _coerce_non_negative_int(intelligence.get("access_count")),
    ]
    valid_counts = [count for count in counts if count is not None]
    if not valid_counts:
        return 0
    return max(valid_counts)


def _normalize_memory_type(*values: Any) -> Optional[str]:
    mapping = {
        "working": "working",
        "working_memory": "working",
        "short_term": "short_term",
        "short_term_memory": "short_term",
        "long_term": "long_term",
        "long_term_memory": "long_term",
    }
    for value in values:
        raw_value = getattr(value, "value", value)
        if raw_value in mapping:
            return mapping[raw_value]
    return None


def _first_present(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _coerce_score(value: Any, *, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_non_negative_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return max(int(value), 0)
    except (TypeError, ValueError):
        return None


def _clamp_score(value: Any) -> float:
    return max(0.0, min(1.0, _coerce_score(value, default=1.0)))

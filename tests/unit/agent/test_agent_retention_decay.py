"""Regression tests for AgentMemory Ebbinghaus retention decay."""

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import ANY, MagicMock

import pytest

from powermem.agent.implementations.multi_agent import MultiAgentMemoryManager
from powermem.agent.implementations.multi_user import MultiUserMemoryManager
from powermem.agent.types import MemoryScope, MemoryType
from powermem.agent.utils.retention import persist_agent_retention_metadata
from powermem.intelligence.ebbinghaus_algorithm import EbbinghausAlgorithm
from powermem.utils.utils import get_current_datetime


def _build_multi_agent_manager(memory_data):
    manager = MultiAgentMemoryManager.__new__(MultiAgentMemoryManager)
    manager.scope_memories = {
        scope: {memory_type: {} for memory_type in MemoryType}
        for scope in MemoryScope
    }
    manager.scope_controller = SimpleNamespace(
        scope_storage={
            scope: {memory_type: {} for memory_type in MemoryType}
            for scope in MemoryScope
        }
    )
    manager.permission_controller = MagicMock()
    manager.collaboration_memories = {}
    manager._memory_instance = MagicMock()
    manager._get_or_create_memory_instance = MagicMock(
        return_value=manager._memory_instance
    )
    manager.intelligent_manager = SimpleNamespace(
        ebbinghaus_algorithm=EbbinghausAlgorithm(
            {"decay_rate": 1.5, "initial_retention": 1.0}
        )
    )
    manager.scope_memories[MemoryScope.PRIVATE][MemoryType.WORKING][
        memory_data["id"]
    ] = memory_data
    return manager


def _build_multi_user_manager(memory_data):
    manager = MultiUserMemoryManager.__new__(MultiUserMemoryManager)
    manager.user_memories = {
        memory_data["user_id"]: {memory_type: {} for memory_type in MemoryType}
    }
    manager.shared_memories = {}
    manager.consent_records = {}
    manager._memory_instance = MagicMock()
    manager._get_or_create_memory_instance = MagicMock(
        return_value=manager._memory_instance
    )
    manager.intelligent_manager = SimpleNamespace(
        ebbinghaus_algorithm=EbbinghausAlgorithm(
            {"decay_rate": 1.5, "initial_retention": 1.0}
        )
    )
    manager.user_memories[memory_data["user_id"]][MemoryType.WORKING][
        memory_data["id"]
    ] = memory_data
    return manager


def _memory_with_reviewed_retention(memory_id, user_id, hours_since_review):
    reviewed_at = get_current_datetime() - timedelta(hours=hours_since_review)
    return {
        "id": memory_id,
        "content": "hello",
        "agent_id": "agent-1",
        "user_id": user_id,
        "scope": MemoryScope.PRIVATE,
        "memory_type": MemoryType.WORKING,
        "metadata": {
            "memory_type": "working",
            "intelligence": {
                "memory_type": "working",
                "initial_retention": 0.8,
                "current_retention": 0.8,
                "decay_rate": 1.5,
                "last_reviewed": reviewed_at.isoformat(),
                "review_count": 0,
                "access_count": 0,
                "reinforcement_factor": 0.3,
            },
        },
        "retention_score": 0.8,
        "access_count": 0,
        "last_accessed": None,
    }


def _set_review_schedule(memory_data, *hours_from_now):
    now = get_current_datetime()
    memory_data["metadata"]["intelligence"]["review_schedule"] = [
        (now + timedelta(hours=hours)).isoformat()
        for hours in hours_from_now
    ]


def test_multi_agent_update_memory_decay_uses_ebbinghaus_retention():
    memory_data = _memory_with_reviewed_retention(123, "user-1", 24)
    manager = _build_multi_agent_manager(memory_data)
    expected = manager.intelligent_manager.ebbinghaus_algorithm.calculate_current_retention(
        memory_data
    )

    manager.update_memory_decay()

    assert memory_data["retention_score"] == pytest.approx(expected)
    assert memory_data["retention_score"] != pytest.approx(0.72)


def test_multi_user_update_memory_decay_uses_ebbinghaus_retention():
    memory_data = _memory_with_reviewed_retention(123, "user-1", 24)
    manager = _build_multi_user_manager(memory_data)
    expected = manager.intelligent_manager.ebbinghaus_algorithm.calculate_current_retention(
        memory_data
    )

    manager.update_memory_decay()

    assert memory_data["retention_score"] == pytest.approx(expected)
    assert memory_data["retention_score"] != pytest.approx(0.72)


def test_cleanup_deletes_by_ebbinghaus_effective_retention_not_stale_cache_score():
    memory_data = _memory_with_reviewed_retention(123, "user-1", 100)
    memory_data["retention_score"] = 1.0
    manager = _build_multi_agent_manager(memory_data)

    result = manager.cleanup_forgotten_memories()

    assert result["cleaned_memory_ids"] == [123]
    manager._memory_instance.delete.assert_called_once_with(
        memory_id=123,
        user_id="user-1",
        agent_id="agent-1",
    )


def test_cleanup_archives_by_ebbinghaus_effective_retention():
    memory_data = _memory_with_reviewed_retention(123, "user-1", 1)
    memory_data["created_at"] = (
        get_current_datetime() - timedelta(days=31)
    ).isoformat()
    memory_data["retention_score"] = 1.0
    manager = _build_multi_user_manager(memory_data)

    result = manager.cleanup_forgotten_memories()

    assert result["archived_memories"] == 1
    assert result["deleted_memories"] == 0
    assert memory_data["metadata"]["archived"] is True
    manager._memory_instance.storage.update_memory.assert_called_once()
    manager._memory_instance.update.assert_not_called()


def test_cleanup_deletes_by_ebbinghaus_forget_threshold():
    memory_data = _memory_with_reviewed_retention(123, "user-1", 50)
    memory_data["retention_score"] = 1.0
    manager = _build_multi_user_manager(memory_data)

    result = manager.cleanup_forgotten_memories()

    assert result["deleted_memories"] == 1
    assert result["archived_memories"] == 0
    assert result["cleaned_memory_ids"] == [123]
    manager._memory_instance.delete.assert_called_once()


def test_decay_syncs_metadata_intelligence_snapshot():
    memory_data = _memory_with_reviewed_retention(123, "user-1", 24)
    manager = _build_multi_agent_manager(memory_data)

    manager.update_memory_decay()

    metadata = memory_data["metadata"]
    intelligence = metadata["intelligence"]
    assert metadata["retention_score"] == pytest.approx(memory_data["retention_score"])
    assert intelligence["current_retention"] == pytest.approx(
        memory_data["retention_score"]
    )
    assert "last_reviewed" in intelligence
    manager._memory_instance.storage.update_memory.assert_called_once()
    manager._memory_instance.update.assert_not_called()


def test_decay_uses_intelligence_access_count_when_cache_has_default_zero():
    memory_data = _memory_with_reviewed_retention(123, "user-1", 24)
    memory_data["metadata"]["intelligence"]["access_count"] = 10
    memory_data["access_count"] = 0
    manager = _build_multi_agent_manager(memory_data)
    expected_memory = dict(memory_data)
    expected_memory["access_count"] = 10
    expected = manager.intelligent_manager.ebbinghaus_algorithm.calculate_current_retention(
        expected_memory
    )

    manager.update_memory_decay()

    assert memory_data["retention_score"] == pytest.approx(expected)
    assert memory_data["metadata"]["intelligence"]["access_count"] == 10


def test_decay_counts_due_access_reinforcement():
    memory_data = _memory_with_reviewed_retention(123, "user-1", 24)
    next_review = get_current_datetime() - timedelta(hours=1)
    memory_data["metadata"]["intelligence"]["next_review"] = next_review.isoformat()
    memory_data["last_accessed"] = get_current_datetime().isoformat()
    _set_review_schedule(memory_data, -2, 24)
    manager = _build_multi_agent_manager(memory_data)
    decayed_score = manager.intelligent_manager.ebbinghaus_algorithm.calculate_current_retention(
        memory_data
    )

    result = manager.update_memory_decay()

    intelligence = memory_data["metadata"]["intelligence"]
    assert result["reinforced_memories"] == 1
    assert intelligence["review_count"] == 1
    assert intelligence["next_review"] == intelligence["review_schedule"][1]
    assert memory_data["retention_score"] > decayed_score
    assert intelligence["current_retention"] == pytest.approx(
        memory_data["retention_score"]
    )


def test_persist_retention_metadata_uses_storage_update_without_plugin_reprocess():
    memory_instance = SimpleNamespace(
        storage=MagicMock(),
        update=MagicMock(),
    )
    metadata = {
        "retention_score": 0.4,
        "intelligence": {"current_retention": 0.4},
    }
    memory_data = {
        "id": 123,
        "content": "hello",
        "agent_id": "agent-1",
        "user_id": "user-1",
        "metadata": metadata,
    }

    persist_agent_retention_metadata(memory_instance, memory_data)

    memory_instance.storage.update_memory.assert_called_once_with(
        123,
        {"metadata": metadata, "updated_at": ANY},
        "user-1",
        "agent-1",
    )
    memory_instance.update.assert_not_called()


def test_decay_preserves_legacy_retention_score_without_intelligence():
    memory_data = {
        "id": 123,
        "content": "legacy",
        "agent_id": "agent-1",
        "user_id": "user-1",
        "scope": MemoryScope.PRIVATE,
        "memory_type": MemoryType.WORKING,
        "metadata": {},
        "retention_score": 0.05,
    }
    manager = _build_multi_user_manager(memory_data)

    result = manager.cleanup_forgotten_memories()

    assert result["cleaned_memory_ids"] == [123]


def test_multi_agent_load_restores_effective_retention_from_intelligence():
    algorithm = EbbinghausAlgorithm({"decay_rate": 1.5, "initial_retention": 1.0})
    last_reviewed = get_current_datetime() - timedelta(hours=24)
    manager = MultiAgentMemoryManager.__new__(MultiAgentMemoryManager)
    manager.scope_memories = {
        scope: {memory_type: {} for memory_type in MemoryType}
        for scope in MemoryScope
    }
    manager.intelligent_manager = SimpleNamespace(ebbinghaus_algorithm=algorithm)
    manager.scope_controller = MagicMock()
    manager.scope_controller.scope_storage = {
        scope: {memory_type: {} for memory_type in MemoryType}
        for scope in MemoryScope
    }
    manager.scope_controller.check_scope_access.return_value = True
    manager.permission_controller = MagicMock()
    manager.permission_controller.memory_permissions = {}
    manager.permission_controller.check_permission.return_value = True
    manager.multi_agent_config = SimpleNamespace(
        default_permissions={"owner": ["read"]}
    )
    manager._memory_instance = MagicMock()
    manager._memory_instance.get_all.return_value = {
        "results": [
            {
                "id": 123,
                "memory": "persisted",
                "agent_id": "agent-1",
                "user_id": "user-1",
                "metadata": {
                    "scope": "private",
                    "memory_type": "working",
                    "intelligence": {
                        "memory_type": "working",
                        "current_retention": 0.8,
                        "initial_retention": 0.8,
                        "decay_rate": 1.5,
                        "last_reviewed": last_reviewed.isoformat(),
                        "importance_score": 0.73,
                    },
                },
            }
        ]
    }
    expected = algorithm.calculate_current_retention(
        manager._memory_instance.get_all.return_value["results"][0]
    )

    result = manager.get_memories("agent-1")

    assert result[0]["retention_score"] == pytest.approx(expected)
    assert result[0]["retention_score"] < 0.8
    assert result[0]["metadata"]["intelligence"]["current_retention"] == pytest.approx(
        expected
    )
    assert result[0]["importance_level"] == pytest.approx(0.73)
    assert manager.scope_memories[MemoryScope.PRIVATE][MemoryType.WORKING][
        123
    ]["retention_score"] == pytest.approx(expected)


def test_multi_agent_load_refreshes_existing_cache_entry_from_database():
    algorithm = EbbinghausAlgorithm({"decay_rate": 1.5, "initial_retention": 1.0})
    last_reviewed = get_current_datetime() - timedelta(hours=24)
    manager = MultiAgentMemoryManager.__new__(MultiAgentMemoryManager)
    manager.scope_memories = {
        scope: {memory_type: {} for memory_type in MemoryType}
        for scope in MemoryScope
    }
    stale_cache = {
        "id": 123,
        "content": "stale",
        "agent_id": "agent-1",
        "user_id": "user-1",
        "scope": MemoryScope.PRIVATE,
        "memory_type": MemoryType.WORKING,
        "metadata": {},
        "retention_score": 1.0,
    }
    manager.scope_memories[MemoryScope.PRIVATE][MemoryType.SHORT_TERM]["123"] = (
        stale_cache
    )
    manager.intelligent_manager = SimpleNamespace(ebbinghaus_algorithm=algorithm)
    manager.scope_controller = MagicMock()
    manager.scope_controller.scope_storage = {
        scope: {memory_type: {} for memory_type in MemoryType}
        for scope in MemoryScope
    }
    manager.scope_controller.check_scope_access.return_value = True
    manager.permission_controller = MagicMock()
    manager.permission_controller.memory_permissions = {}
    manager.permission_controller.check_permission.return_value = True
    manager.multi_agent_config = SimpleNamespace(
        default_permissions={"owner": ["read"]}
    )
    manager._memory_instance = MagicMock()
    manager._memory_instance.get_all.return_value = {
        "results": [
            {
                "id": 123,
                "memory": "fresh",
                "agent_id": "agent-1",
                "user_id": "user-1",
                "metadata": {
                    "scope": "private",
                    "memory_type": "working",
                    "intelligence": {
                        "memory_type": "working",
                        "current_retention": 0.8,
                        "initial_retention": 0.8,
                        "decay_rate": 1.5,
                        "last_reviewed": last_reviewed.isoformat(),
                    },
                },
            }
        ]
    }
    expected = algorithm.calculate_current_retention(
        manager._memory_instance.get_all.return_value["results"][0]
    )

    manager.get_memories("agent-1")

    refreshed = manager.scope_memories[MemoryScope.PRIVATE][MemoryType.WORKING][123]
    assert refreshed["content"] == "fresh"
    assert refreshed["retention_score"] == pytest.approx(expected)
    assert manager.scope_memories[MemoryScope.PRIVATE][MemoryType.SHORT_TERM] == {}


def test_multi_agent_load_uses_normalized_id_for_scope_access():
    algorithm = EbbinghausAlgorithm({"decay_rate": 1.5, "initial_retention": 1.0})
    manager = MultiAgentMemoryManager.__new__(MultiAgentMemoryManager)
    manager.scope_memories = {
        scope: {memory_type: {} for memory_type in MemoryType}
        for scope in MemoryScope
    }
    manager.scope_controller = MagicMock()
    manager.scope_controller.scope_storage = {
        scope: {memory_type: {} for memory_type in MemoryType}
        for scope in MemoryScope
    }

    def _check_scope_access(_agent_id, memory_id):
        return memory_id in manager.scope_controller.scope_storage[
            MemoryScope.PRIVATE
        ][MemoryType.WORKING]

    manager.scope_controller.check_scope_access.side_effect = _check_scope_access
    manager.permission_controller = MagicMock()
    manager.permission_controller.memory_permissions = {}
    manager.permission_controller.check_permission.return_value = True
    manager.multi_agent_config = SimpleNamespace(
        default_permissions={"owner": ["read"]}
    )
    manager.intelligent_manager = SimpleNamespace(ebbinghaus_algorithm=algorithm)
    manager._memory_instance = MagicMock()
    manager._memory_instance.get_all.return_value = {
        "results": [
            {
                "id": "123",
                "memory": "persisted",
                "agent_id": "agent-1",
                "user_id": "user-1",
                "metadata": {"scope": "private", "memory_type": "working"},
            }
        ]
    }

    result = manager.get_memories("agent-1")

    assert result[0]["id"] == "123"
    assert 123 in manager.scope_memories[MemoryScope.PRIVATE][MemoryType.WORKING]


def test_multi_user_load_restores_effective_retention_from_intelligence():
    algorithm = EbbinghausAlgorithm({"decay_rate": 1.5, "initial_retention": 1.0})
    last_reviewed = get_current_datetime() - timedelta(hours=24)
    manager = MultiUserMemoryManager.__new__(MultiUserMemoryManager)
    manager.user_memories = {}
    manager.shared_memories = {}
    manager.intelligent_manager = SimpleNamespace(ebbinghaus_algorithm=algorithm)
    manager._extract_user_id = MagicMock(return_value="user-1")
    manager._memory_instance = MagicMock()
    manager._memory_instance.get_all.return_value = {
        "results": [
            {
                "id": 123,
                "memory": "persisted",
                "agent_id": "agent-1",
                "user_id": "user-1",
                "metadata": {
                    "scope": "private",
                    "memory_type": "working",
                    "intelligence": {
                        "memory_type": "working",
                        "current_retention": 0.8,
                        "initial_retention": 0.8,
                        "decay_rate": 1.5,
                        "last_reviewed": last_reviewed.isoformat(),
                    },
                },
            }
        ]
    }
    expected = algorithm.calculate_current_retention(
        manager._memory_instance.get_all.return_value["results"][0]
    )

    result = manager.get_memories("user-1")

    assert result[0]["retention_score"] == pytest.approx(expected)
    assert manager.user_memories["user-1"][MemoryType.WORKING][123][
        "retention_score"
    ] == pytest.approx(expected)


def test_multi_user_load_refreshes_existing_cache_key_variants():
    algorithm = EbbinghausAlgorithm({"decay_rate": 1.5, "initial_retention": 1.0})
    last_reviewed = get_current_datetime() - timedelta(hours=24)
    stale_cache = {
        "id": 123,
        "content": "stale",
        "agent_id": "agent-1",
        "user_id": "user-1",
        "memory_type": MemoryType.SHORT_TERM,
        "metadata": {},
        "retention_score": 1.0,
    }
    manager = MultiUserMemoryManager.__new__(MultiUserMemoryManager)
    manager.user_memories = {
        "user-1": {memory_type: {} for memory_type in MemoryType}
    }
    manager.user_memories["user-1"][MemoryType.SHORT_TERM]["123"] = stale_cache
    manager.shared_memories = {}
    manager.intelligent_manager = SimpleNamespace(ebbinghaus_algorithm=algorithm)
    manager._extract_user_id = MagicMock(return_value="user-1")
    manager._memory_instance = MagicMock()
    manager._memory_instance.get_all.return_value = {
        "results": [
            {
                "id": 123,
                "memory": "fresh",
                "agent_id": "agent-1",
                "user_id": "user-1",
                "metadata": {
                    "scope": "private",
                    "memory_type": "working",
                    "intelligence": {
                        "memory_type": "working",
                        "current_retention": 0.8,
                        "initial_retention": 0.8,
                        "decay_rate": 1.5,
                        "last_reviewed": last_reviewed.isoformat(),
                    },
                },
            }
        ]
    }
    expected = algorithm.calculate_current_retention(
        manager._memory_instance.get_all.return_value["results"][0]
    )

    manager.get_memories("user-1")

    refreshed = manager.user_memories["user-1"][MemoryType.WORKING][123]
    assert refreshed["content"] == "fresh"
    assert refreshed["retention_score"] == pytest.approx(expected)
    assert manager.user_memories["user-1"][MemoryType.SHORT_TERM] == {}


def test_cleanup_removes_duplicate_cache_entries_for_deleted_memory():
    memory_data = {
        "id": 123,
        "content": "duplicate",
        "agent_id": "agent-1",
        "user_id": "user-1",
        "scope": MemoryScope.PRIVATE,
        "memory_type": MemoryType.WORKING,
        "metadata": {},
        "retention_score": 0.05,
    }
    manager = _build_multi_agent_manager(memory_data)
    manager.scope_memories[MemoryScope.PRIVATE][MemoryType.SHORT_TERM]["123"] = (
        dict(memory_data)
    )

    result = manager.cleanup_forgotten_memories()

    assert result["cleaned_memory_ids"] == [123]
    manager._memory_instance.delete.assert_called_once()
    assert manager.scope_memories[MemoryScope.PRIVATE][MemoryType.WORKING] == {}
    assert manager.scope_memories[MemoryScope.PRIVATE][MemoryType.SHORT_TERM] == {}

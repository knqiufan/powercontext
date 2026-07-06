"""Unit tests for multi-user CRUD/id lookup behavior."""

from unittest.mock import MagicMock

from powermem.agent.implementations.multi_user import MultiUserMemoryManager
from powermem.agent.types import MemoryScope, MemoryType


def _build_manager() -> MultiUserMemoryManager:
    manager = MultiUserMemoryManager.__new__(MultiUserMemoryManager)
    manager.user_memories = {"user-1": {memory_type: {} for memory_type in MemoryType}}
    manager.shared_memories = {}
    manager.consent_records = {}
    manager._memory_instance = MagicMock()
    manager._get_or_create_memory_instance = MagicMock(
        return_value=manager._memory_instance
    )
    memory_data = {
        "id": 123,
        "content": "hello",
        "agent_id": "agent-1",
        "user_id": "user-1",
        "memory_type": MemoryType.WORKING,
        "metadata": {},
    }
    manager.user_memories["user-1"][MemoryType.WORKING][123] = memory_data
    return manager


def test_find_memory_accepts_string_and_int_ids():
    manager = _build_manager()

    assert manager._find_memory("123")["content"] == "hello"
    assert manager._find_memory(123)["content"] == "hello"


def test_update_memory_keeps_merged_metadata_in_cache():
    manager = _build_manager()
    memory_data = manager.user_memories["user-1"][MemoryType.WORKING][123]
    memory_data["metadata"] = {"source": "original"}

    manager.update_memory("123", "user-1", {"metadata": {"topic": "agent"}})

    assert memory_data["metadata"] == {"source": "original", "topic": "agent"}
    manager._memory_instance.update.assert_called_once_with(
        memory_id=123,
        content="hello",
        user_id="user-1",
        agent_id="agent-1",
        metadata={"source": "original", "topic": "agent"},
    )


def test_update_memory_persists_content_to_db():
    manager = _build_manager()

    result = manager.update_memory("123", "user-1", {"content": "updated"})

    manager._memory_instance.update.assert_called_once_with(
        memory_id=123,
        content="updated",
        user_id="user-1",
        agent_id="agent-1",
        metadata={},
    )
    assert result["memory"] == "updated"


def test_delete_memory_removes_all_cache_key_variants():
    manager = _build_manager()
    memory_data = manager.user_memories["user-1"][MemoryType.WORKING][123]
    manager.user_memories["user-1"][MemoryType.WORKING]["123"] = memory_data
    manager.shared_memories[123] = {"shared_with": ["user-2"], "permissions": {}}
    manager.consent_records["user-2"] = {123: {"consent_given": True}}

    manager.delete_memory("123", "user-1")

    assert manager.user_memories["user-1"][MemoryType.WORKING] == {}
    assert manager.shared_memories == {}
    assert manager.consent_records["user-2"] == {}


def test_persist_memory_copies_intelligence_retention_to_top_level_metadata():
    manager = _build_manager()
    manager._memory_instance.add.return_value = {"results": [{"id": 456}]}

    memory_id = manager._persist_memory_to_storage(
        {
            "content": "remember user preference",
            "user_id": "user-1",
            "agent_id": "agent-1",
            "scope": MemoryScope.PRIVATE,
            "memory_type": MemoryType.LONG_TERM,
            "metadata": {
                "intelligence": {
                    "current_retention": 0.42,
                    "importance_score": 0.77,
                }
            },
        }
    )

    assert memory_id == 456
    add_metadata = manager._memory_instance.add.call_args.kwargs["metadata"]
    assert add_metadata["retention_score"] == 0.42
    assert add_metadata["importance_level"] == 0.77
    assert add_metadata["intelligence"]["current_retention"] == 0.42


def test_persist_memory_preserves_metadata_privacy_level_when_not_overridden():
    manager = _build_manager()
    manager._memory_instance.add.return_value = {"results": [{"id": 456}]}

    manager._persist_memory_to_storage(
        {
            "content": "remember private user preference",
            "user_id": "user-1",
            "agent_id": "agent-1",
            "scope": MemoryScope.PRIVATE,
            "memory_type": MemoryType.LONG_TERM,
            "metadata": {
                "privacy_level": "confidential",
                "intelligence": {"current_retention": 0.42},
            },
        }
    )

    add_metadata = manager._memory_instance.add.call_args.kwargs["metadata"]
    assert add_metadata["privacy_level"] == "confidential"


def test_cleanup_forgotten_memories_calls_db_delete_and_returns_ids():
    manager = _build_manager()
    memory_data = manager.user_memories["user-1"][MemoryType.WORKING][123]
    memory_data["retention_score"] = 0.05

    result = manager.cleanup_forgotten_memories()

    manager._memory_instance.delete.assert_called_once_with(
        memory_id=123,
        user_id="user-1",
        agent_id="agent-1",
    )
    assert result["cleaned_memory_ids"] == [123]
    assert manager._find_memory(123) is None

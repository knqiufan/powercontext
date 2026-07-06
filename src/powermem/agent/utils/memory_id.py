"""Memory ID normalization helpers for AgentMemory layer."""

from typing import List, Union


MemoryIdInput = Union[str, int]


def normalize_memory_id(memory_id: MemoryIdInput) -> int:
    """Normalize Snowflake memory id to int; raise ValueError for invalid input."""
    if isinstance(memory_id, bool):
        raise ValueError(f"Invalid memory_id type: {type(memory_id)}")
    if isinstance(memory_id, int):
        return memory_id
    if isinstance(memory_id, str):
        stripped = memory_id.strip()
        if not stripped:
            raise ValueError("memory_id cannot be empty")
        return int(stripped)
    raise ValueError(f"Invalid memory_id type: {type(memory_id)}")


def memory_key_variants(memory_id: MemoryIdInput) -> List[Union[int, str]]:
    """Return int/str key variants for transitional cache lookup."""
    normalized = normalize_memory_id(memory_id)
    return [normalized, str(normalized)]


def memory_cache_key(memory_id: MemoryIdInput) -> Union[int, str]:
    """Return the canonical cache key while preserving legacy string ids."""
    try:
        return normalize_memory_id(memory_id)
    except ValueError:
        if isinstance(memory_id, str):
            stripped = memory_id.strip()
            if stripped:
                return stripped
        raise


def memory_cache_key_variants(memory_id: MemoryIdInput) -> List[Union[int, str]]:
    """Return cache lookup variants without rejecting legacy string ids."""
    try:
        return memory_key_variants(memory_id)
    except ValueError:
        return [memory_cache_key(memory_id)]

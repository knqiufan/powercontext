# Copyright (c) 2026 OceanBase.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Protect routing evaluation from false passes and mismatched controlled results."""

import asyncio
from typing import Any

import pytest

from scripts.evaluate_integration_guidance import run_scenario, validate_message


def call(name: str) -> dict[str, Any]:
    return {
        "role": "assistant",
        "content": "",
        "reasoning": "fixture protocol state",
        "tool_calls": [
            {"id": "fixture-call", "type": "function", "function": {"name": name, "arguments": "{}"}},
        ],
    }


@pytest.mark.parametrize(
    "response",
    [
        {"content": "<tool_call><function=remember_memory>saved</tool_call>"},
        {"content": "", "tool_calls": [{"function": {"name": "remember_memory", "arguments": "[]"}}]},
    ],
)
def test_rejects_simulated_calls_and_non_object_arguments(response: dict[str, Any]) -> None:
    with pytest.raises((ValueError, TypeError)):
        validate_message(response)


class Model:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = iter(responses)
        self.messages: list[list[dict[str, Any]]] = []

    async def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        self.messages.append(list(messages))
        return next(self.responses)


def test_resolves_scope_before_delivering_write_result() -> None:
    model = Model([call("resolve_scope_binding"), call("remember_memory"), {"content": "Saved."}])
    catalog = {
        "host": "fixture",
        "guidance": "",
        "tools": [{"name": "resolve_scope_binding"}, {"name": "remember_memory"}],
    }
    result = asyncio.run(run_scenario(model, catalog, "save", 0, "unloaded"))
    assert result["routing_passed"]
    assert result["calls"][0]["function"]["name"] == "remember_memory"
    assert '"scope_id": "fixture-scope"' in model.messages[1][-1]["content"]
    assert '"status": "saved"' in model.messages[2][-1]["content"]
    # Preserve provider protocol state for the continuation, without publishing reasoning in the report.
    assert model.messages[1][-2]["reasoning"] == "fixture protocol state"
    assert "reasoning" not in result


@pytest.mark.parametrize("reply", [{"content": ""}, call("remember_memory")])
def test_missing_save_tool_does_not_pass_on_empty_output_or_invented_call(reply: dict[str, Any]) -> None:
    model = Model([reply])
    catalog = {"host": "fixture", "guidance": "", "tools": [{"name": "remember_memory"}]}
    result = asyncio.run(run_scenario(model, catalog, "unavailable_save", 0, "unavailable"))
    assert not result["routing_passed"]

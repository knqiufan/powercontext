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

"""Official Dify host helpers before registered SDK/HTTP invocation; not daemon acceptance."""

from __future__ import annotations

import ast
import json
import os
import subprocess
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from host_helpers import cast_parameters, parameter_cast
from jsonschema import Draft7Validator
from test_plugin_contract import run

pytest_plugins = ["test_plugin_contract"]
pytestmark = pytest.mark.skipif(
    not os.environ.get("POWERCONTEXT_DIFY_SOURCE"), reason="Set the pinned Dify source path"
)


def test_nested_workflow_selectors_resolve_with_official_host_helpers(registry, tmp_path):
    _, _, loaded = registry.tools_mapping["powercontext"]
    schema = tmp_path / "schemas.json"
    schema.write_text(
        json.dumps({name: declaration.output_schema for name, (declaration, _) in loaded.items()}, ensure_ascii=False),
        encoding="utf-8",
    )
    result = subprocess.run(
        ["node", "--experimental-strip-types", str(Path(__file__).with_name("host_output_probe.ts")), str(schema)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
        timeout=30,
    )
    assert json.loads(result.stdout) == {"tools": 19, "selectors": 15}


@pytest.mark.parametrize("target", [{}, 42, "not JSON"])
def test_host_cast_does_not_hide_invalid_optional_targets(registry, transport, target):
    _, _, loaded = registry.tools_mapping["powercontext"]
    calls = transport(lambda _request: pytest.fail("Malformed target must not generate"))
    parameters = {"source_refs": [{"name": "content", "source_id": "turn-1"}], "target": target}
    cast = cast_parameters(loaded["pc_experience_generate"][0], parameters)
    result = run(registry, "pc_experience_generate", cast)
    assert result["error"]["code"] == "invalid_request"
    assert all(path != "/v1/experiences/generate" for path, _ in calls)


def test_host_cast_preserves_null_and_complete_reference_values(registry):
    _, _, loaded = registry.tools_mapping["powercontext"]
    reference = {"family": "experience", "artifact_id": "e-1", "revision": 2}
    for value in (None, reference, json.dumps(reference), "null"):
        parameters = {"target": value, "reason": None}
        assert cast_parameters(loaded["pc_experience_generate"][0], parameters) == parameters


def test_official_model_schema_builder_retains_nullable_input_schemas(registry):
    path = Path(os.environ["POWERCONTEXT_DIFY_SOURCE"]) / "api/core/tools/__base/tool.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    tool = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Tool")
    method = next(
        node
        for node in tool.body
        if isinstance(node, ast.FunctionDef) and node.name == "get_llm_parameters_json_schema"
    )
    # Supply only the parameter model constants; the schema builder is official code.
    model = SimpleNamespace(
        ToolParameterForm=SimpleNamespace(LLM="llm"),
        ToolParameterType=SimpleNamespace(
            SYSTEM_FILES="system-files", FILE="file", FILES="files", SELECT="select", DYNAMIC_SELECT="dynamic-select"
        ),
    )
    namespace: dict[str, Any] = {"Any": Any, "deepcopy": deepcopy, "ToolParameter": model}
    exec(compile(ast.Module(body=[method], type_ignores=[]), str(path), "exec"), namespace)
    build = namespace["get_llm_parameters_json_schema"]
    as_normal_type = parameter_cast().__globals__["as_normal_type"]

    class HostType(str):
        @property
        def value(self):
            return str(self)

        def as_normal_type(self):
            return as_normal_type(self)

    _, _, loaded = registry.tools_mapping["powercontext"]
    for declaration, _ in loaded.values():
        parameters = [
            SimpleNamespace(
                **{
                    **parameter.model_dump(),
                    "type": HostType(parameter.type.value),
                    "form": parameter.form.value,
                    "options": parameter.options,
                }
            )
            for parameter in declaration.parameters
        ]
        schema = build(SimpleNamespace(get_merged_runtime_parameters=lambda parameters=parameters, **_: parameters))
        Draft7Validator.check_schema(schema)
        for parameter in parameters:
            if parameter.input_schema:
                assert schema["properties"][parameter.name] == {
                    **parameter.input_schema,
                    "description": parameter.input_schema.get("description", parameter.llm_description or ""),
                }

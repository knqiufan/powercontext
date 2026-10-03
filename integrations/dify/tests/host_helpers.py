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

"""Replay official Dify parameter casting; never import its application or patch the SDK."""

from __future__ import annotations

import ast
import json
import os
from datetime import date
from enum import StrEnum, auto
from functools import cache
from pathlib import Path
from typing import Any


@cache
def parameter_cast():
    root = Path(os.environ["POWERCONTEXT_DIFY_SOURCE"])
    namespace = {"StrEnum": StrEnum, "auto": auto, "json": json, "date": date, "Any": Any}
    files = {
        "api/core/entities/parameter_entities.py": {"CommonParameterType"},
        "api/core/plugin/entities/parameters.py": {
            "PluginParameterType",
            "as_normal_type",
            "_validate_date",
            "cast_parameter_value",
        },
    }
    for filename, names in files.items():
        path = root / filename
        tree = ast.parse(path.read_text(encoding="utf-8"))
        selected = [
            node for node in tree.body if isinstance(node, ast.ClassDef | ast.FunctionDef) and node.name in names
        ]
        assert {node.name for node in selected} == names
        body: list[ast.stmt] = [*selected]
        module = ast.Module(body=body, type_ignores=[])
        exec(compile(module, str(path), "exec"), namespace)
    return namespace["cast_parameter_value"]


def cast_parameters(declaration, parameters):
    cast = parameter_cast()
    types = {parameter.name: parameter.type for parameter in declaration.parameters}
    return {name: cast(types[name], value) if name in types else value for name, value in parameters.items()}

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

"""Native DSH composition and setup policy, without mutating the user's host."""

import json
import os
from shutil import which
from unittest.mock import Mock

import pytest
from typer.testing import CliRunner

from powercontext.cli.app import create_cli
from powercontext.cli.dsh_transport import matching_dsh_consent, read_dsh_settings, validate_dsh_setup_transport
from powercontext.cli.native_transport import resolve_host_transport
from powercontext.cli.system import setup_app
from powercontext.cli.transport import prepare_setup_transport


@pytest.fixture
def dsh_profile(tmp_path, monkeypatch):
    """Use a real installed DSH parser, with an entirely disposable profile."""
    import powercontext.cli.dsh as dsh

    executable = os.environ.get("DSH_TEST_EXECUTABLE") or which("dsh.cmd" if os.name == "nt" else "dsh")
    if not executable:
        pytest.skip("Native DSH composition requires DSH; set DSH_TEST_EXECUTABLE to select a runtime")
    monkeypatch.setattr(dsh, "dsh_executable", lambda: executable)
    for key in list(os.environ):
        if key.startswith("POWERCONTEXT_") or key == "DSH_PROFILE":
            monkeypatch.delenv(key)
    monkeypatch.setenv("POWERCONTEXT_CLIENT_CONFIG_FILE", str(tmp_path / "clients.json"))
    monkeypatch.setenv("DSH_HOME", str(tmp_path / "dsh"))
    monkeypatch.chdir(tmp_path)
    profile = tmp_path / "dsh/profiles/web"
    profile.mkdir(parents=True)
    (profile / "package.json").write_text(json.dumps({"dsh": {"profile": {"bundles": []}}}))
    return profile


def write_patch(profile, content):
    path = profile / "cordis.patch.yml"
    path.write_text(content, encoding="utf-8")
    return path


def plugin_source(tmp_path):
    plugin = tmp_path / "plugin"
    plugin.mkdir()
    (plugin / "package.json").write_text(
        json.dumps({"name": "powercontext-dsh", "dsh": {"bundle": {"patch": "cordis.patch.yml"}}})
    )
    (plugin / "cordis.patch.yml").write_text(
        "- insert:\n    - id: powercontext-dsh\n      name: powercontext-dsh\n      config: {}\n"
    )
    (plugin / "lib").mkdir()
    (plugin / "lib/index.js").write_text("export const name = 'powercontext-dsh'\n")
    return plugin


def test_existing_customizations_allow_public_setup_and_preserve_files(dsh_profile, tmp_path, monkeypatch):
    import powercontext.cli.dsh as dsh

    patch = write_patch(
        dsh_profile,
        "- insert:\n    - id: ui\n      name: ui\n- id: ui\n  config:\n    theme: dark\n    title: 自定义界面\n    model: !!js process.env.MODEL\n",
    )
    original = {path: path.read_bytes() for path in dsh_profile.iterdir()}
    source = plugin_source(tmp_path)
    monkeypatch.setenv("POWERCONTEXT_HOME", str(tmp_path / "data"))
    installer = Mock(return_value="id: powercontext-dsh\n")
    monkeypatch.setattr(dsh, "_run_dsh", installer)
    for _ in range(2):
        result = CliRunner().invoke(create_cli([setup_app]), ["setup", "dsh", "--source", str(source), "--json"])
        assert result.exit_code == 0, result.output
        assert (
            json.loads((tmp_path / "clients.json").read_text())["hosts"]["dsh"]["server_url"] == "http://127.0.0.1:8000"
        )
    assert patch.read_bytes() == original[patch]
    assert {path: path.read_bytes() for path in dsh_profile.iterdir()} == original


@pytest.mark.parametrize("relative", ["profiles/web/cordis.patch.yml", "cordis.patch.yml"])
def test_matching_native_transport_passes_and_conflicts_do_not_install(dsh_profile, tmp_path, monkeypatch, relative):
    import powercontext.cli.dsh as dsh

    patch = tmp_path / "dsh" / relative
    patch.write_text("- id: powercontext-dsh\n  config:\n    baseUrl: https://memory.example\n")
    assert prepare_setup_transport("dsh", server_url="https://memory.example").server_url == "https://memory.example"
    installer = Mock()
    monkeypatch.setattr(dsh, "_run_dsh", installer)
    result = CliRunner().invoke(
        create_cli([setup_app]), ["setup", "dsh", "--server-url", "https://other.example", "--json"]
    )
    assert result.exit_code == 1
    assert "baseUrl conflicts" in result.output
    installer.assert_not_called()
    assert not (tmp_path / "clients.json").exists()


def test_setup_uses_web_profile_and_home_layer_wins(dsh_profile, monkeypatch):
    write_patch(dsh_profile, "- id: powercontext-dsh\n  config:\n    baseUrl: https://profile.example\n")
    write_patch(dsh_profile.parent.parent, "- id: powercontext-dsh\n  config:\n    baseUrl: https://home.example\n")
    monkeypatch.setenv("DSH_PROFILE", "other")
    assert prepare_setup_transport("dsh").server_url == "https://home.example"


def test_doctor_reads_the_selected_runtime_profile(dsh_profile, monkeypatch):
    profile = dsh_profile.parent / "custom"
    profile.mkdir()
    (profile / "package.json").write_bytes((dsh_profile / "package.json").read_bytes())
    write_patch(
        profile,
        "- insert:\n    - id: powercontext-dsh\n      name: powercontext-dsh\n"
        "      config:\n        baseUrl: https://custom.example\n",
    )
    monkeypatch.setenv("DSH_PROFILE", "custom")
    assert resolve_host_transport("dsh") == ("https://custom.example", False)


@pytest.mark.parametrize(
    "patch",
    [
        "- id: powercontext-dsh\n  config:\n    baseUrl: !!js (() => { throw new Error('secret-value') })()\n",
        "- id: powercontext-dsh\n  config:\n    allowInsecureHttp: !!js process.env.SECRET\n",
        "- id: powercontext-dsh\n  disabled: true\n",
        "- insert:\n    - id: powercontext-dsh\n      name: powercontext-dsh\n",
        "- id: powercontext-dsh\n  name: wrong-plugin\n  config: {}\n",
        "- id: powercontext-dsh\n  config: [broken: secret-value\n",
    ],
)
def test_unverifiable_relevant_configuration_is_redacted(dsh_profile, patch):
    path = write_patch(dsh_profile, patch)
    with pytest.raises(ValueError) as error:
        read_dsh_settings(prospective=True)
    assert "secret-value" not in str(error.value)
    assert path.read_text() == patch


def test_candidate_bundle_is_checked_before_install(dsh_profile, tmp_path, monkeypatch):
    import powercontext.cli.dsh as dsh

    source = plugin_source(tmp_path)
    (source / "cordis.patch.yml").write_text(
        "- insert:\n    - id: powercontext-dsh\n      name: powercontext-dsh\n      config:\n        baseUrl: https://candidate.example\n"
    )
    installer = Mock()
    monkeypatch.setattr(dsh, "_run_dsh", installer)
    monkeypatch.setenv("POWERCONTEXT_HOME", str(tmp_path / "data"))
    result = CliRunner().invoke(
        create_cli([setup_app]),
        ["setup", "dsh", "--source", str(source), "--server-url", "https://selected.example", "--json"],
    )
    assert result.exit_code == 1
    assert "baseUrl conflicts" in result.output
    installer.assert_not_called()
    assert not (tmp_path / "clients.json").exists()


def test_candidate_replaces_installed_bundle_without_duplicate_entries(dsh_profile, tmp_path):
    source = plugin_source(tmp_path)
    installed = dsh_profile / "node_modules/powercontext-dsh"
    installed.mkdir(parents=True)
    (installed / "package.json").write_bytes((source / "package.json").read_bytes())
    (installed / "cordis.patch.yml").write_bytes((source / "cordis.patch.yml").read_bytes())
    (dsh_profile / "package.json").write_text(json.dumps({"dsh": {"profile": {"bundles": ["powercontext-dsh"]}}}))
    write_patch(
        dsh_profile,
        "- id: powercontext-dsh\n  config:\n    baseUrl: http://memory.example\n    allowInsecureHttp: true\n",
    )
    assert read_dsh_settings(candidate=source)["baseUrl"] == "http://memory.example"
    assert resolve_host_transport("dsh") == ("http://memory.example", True)


def test_unreadable_bundle_is_not_assumed_to_be_unrelated(dsh_profile):
    (dsh_profile / "package.json").write_text(json.dumps({"dsh": {"profile": {"bundles": ["missing-bundle"]}}}))
    with pytest.raises(ValueError, match="Cannot read"):
        read_dsh_settings(prospective=True)


def test_remote_http_consent_and_environment_precedence(dsh_profile, monkeypatch):
    write_patch(
        dsh_profile,
        "- id: powercontext-dsh\n  config:\n    baseUrl: http://memory.example\n    allowInsecureHttp: true\n",
    )
    assert prepare_setup_transport("dsh", json_output=True).allow_insecure_http is True
    monkeypatch.setenv("POWERCONTEXT_DSH_BASE_URL", "http://other.example")
    with pytest.raises(RuntimeError, match="Remote HTTP"):
        prepare_setup_transport("dsh", server_url="http://other.example", json_output=True)
    monkeypatch.setenv("POWERCONTEXT_DSH_ALLOW_INSECURE_HTTP", "true")
    assert (
        prepare_setup_transport("dsh", server_url="http://other.example", json_output=True).allow_insecure_http is True
    )


@pytest.mark.parametrize(
    ("settings", "endpoint", "expected"),
    [
        ({"baseUrl": "http://a.example", "allowInsecureHttp": True}, "http://a.example/", True),
        ({"baseUrl": "http://a.example", "allowInsecureHttp": True}, "http://b.example", None),
        ({"allowInsecureHttp": False}, "http://b.example", False),
        ({}, "http://b.example", None),
    ],
)
def test_native_consent_is_endpoint_bound(settings, endpoint, expected):
    assert matching_dsh_consent(settings, endpoint) is expected


def test_explicit_refusal_cannot_be_overridden_by_native_permission(monkeypatch):
    for key in list(os.environ):
        if key.startswith("POWERCONTEXT_"):
            monkeypatch.delenv(key)
    with pytest.raises(ValueError, match="HTTP consent"):
        validate_dsh_setup_transport(
            {"baseUrl": "http://a.example", "allowInsecureHttp": True}, "http://a.example", False
        )

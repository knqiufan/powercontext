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

"""W3C WebDriver interactions with the real installed application and Server."""

from __future__ import annotations

import json
import time

import httpx
from installed_fixture import isolated_server
from real_server import HarnessFailure

ELEMENT = "element-6066-11e4-a52e-4f735466cecf"
NOTE = "desktopinstalledci 中文安装后验收\n纯文本 café <script>literal</script>"


class InstalledPage:
    def __init__(self, client: httpx.Client, prefix: str) -> None:
        self.client = client
        self.prefix = prefix

    def post(self, path: str, payload: dict[str, object]):
        response = self.client.post(self.prefix + path, json=payload)
        response.raise_for_status()
        return response.json()["value"]

    def element(self, xpath: str) -> str:
        for _ in range(100):
            response = self.client.post(self.prefix + "/element", json={"using": "xpath", "value": xpath})
            if response.is_success:
                identifier = response.json()["value"][ELEMENT]
                enabled = self.client.get(self.prefix + f"/element/{identifier}/enabled")
                enabled.raise_for_status()
                if enabled.json()["value"]:
                    return identifier
            elif response.json().get("value", {}).get("error") not in {"no such element", "stale element reference"}:
                response.raise_for_status()
            time.sleep(0.2)
        raise HarnessFailure("installed_element_timeout", xpath)

    def click(self, xpath: str) -> None:
        self.post(f"/element/{self.element(xpath)}/click", {})

    def button(self, text: str) -> None:
        self.click(f"//button[normalize-space(.)='{text}']")

    def field(self, label: str, tag: str = "input") -> str:
        return self.element(f"//label[normalize-space(text())='{label}']/{tag}")

    def type(self, label: str, value: str, tag: str = "input") -> None:
        self.post(f"/element/{self.field(label, tag)}/value", {"text": value})

    def observe(self, script: str, args: list[object] | None = None):
        return self.post("/execute/sync", {"script": script, "args": args or []})

    def wait_text(self, text: str) -> None:
        for _ in range(100):
            if self.observe("return document.body.innerText.includes(arguments[0]);", [text]):
                return
            time.sleep(0.2)
        raise HarnessFailure("installed_text_timeout", text)

    def paste(self) -> str:
        field = self.field("记忆内容", "textarea")
        self.post(f"/element/{field}/click", {})
        self.post(f"/element/{field}/value", {"text": "\ue009v\ue000"})
        for _ in range(100):
            value = self.observe("return arguments[0].value;", [{ELEMENT: field}])
            if value:
                return value
            time.sleep(0.2)
        raise HarnessFailure("installed_clipboard_paste_timeout")

    def clear_note(self) -> None:
        field = self.field("记忆内容", "textarea")
        # Keys preserve React input events and do not invoke product internals.
        self.post(f"/element/{field}/value", {"text": "\ue009a\ue000\ue003"})
        if self.observe("return arguments[0].value;", [{ELEMENT: field}]) != "":
            raise HarnessFailure("installed_note_not_cleared")


def exercise_memory(client: httpx.Client, prefix: str) -> dict[str, object]:
    page = InstalledPage(client, prefix)
    with isolated_server() as (server, scope_id, wheel_digest):
        page.button("连接")
        page.type("连接名称", "Desktop CI synthetic")
        page.type("Server 地址", str(server.base_url).rstrip("/"))
        page.click("//label[normalize-space(text())='已验证兼容配置']/select/option[@value='sqlite-63f918b7-v1']")
        page.button("保存配置")
        page.button("使用此连接")
        page.wait_text("当前使用")
        page.button("首页")
        page.click("//summary[normalize-space(.)='精确 Scope ID']")
        page.type("精确 Scope ID", scope_id)
        page.button("选择范围")
        page.wait_text("当前范围: Desktop installed CI")
        page.type("记忆内容", NOTE, "textarea")
        page.button("保存记忆")
        page.wait_text("保存成功。")
        page.type("全文搜索关键词", "desktopinstalledci")
        page.button("查找")
        page.button("阅读精确版本")
        page.wait_text("记忆正文")
        text = page.observe("return document.querySelector('.reader > .plain-text')?.textContent;")
        if text != NOTE:
            raise HarnessFailure("installed_exact_body_mismatch")
        citation = json.loads(page.observe("return document.querySelector('.reader pre')?.textContent;"))
        response = server.post("/v1/memory/entries/get", json={"scope_id": scope_id, "citation": citation})
        response.raise_for_status()
        if response.json()["text"] != NOTE or response.json()["citation"] != citation:
            raise HarnessFailure("installed_independent_exact_read_mismatch")
        page.button("复制正文")
        page.wait_text("已复制")
        if page.paste() != NOTE:
            raise HarnessFailure("installed_body_clipboard_mismatch")
        page.clear_note()
        page.button("复制引用")
        if json.loads(page.paste()) != citation:
            raise HarnessFailure("installed_citation_clipboard_mismatch")
        page.clear_note()
        return {
            "serverWheelSha256": wheel_digest,
            "mode": "anonymous loopback SQLite, no model",
            "explicitConnectionAndScope": True,
            "saveSearchExactRead": True,
            "independentServerExactRead": True,
            "bodyAndCitationClipboardPaste": True,
        }

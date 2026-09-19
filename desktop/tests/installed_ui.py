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

"""Exercise the installed WebView2 application only on a disposable Windows CI runner."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx


def main() -> None:
    if os.name != "nt" or os.environ.get("GITHUB_ACTIONS") != "true":
        raise RuntimeError("Disposable Windows GitHub Actions runner required")  # noqa: TRY003
    executable = Path(sys.argv[1]).resolve(strict=True)
    driver = Path(os.environ["DESKTOP_EDGE_DRIVER"]).resolve(strict=True)
    artifacts = Path(__file__).resolve().parents[1] / ".artifacts"
    report = {
        "commit": os.environ.get("GITHUB_SHA"),
        "installedExecutableSha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
        "driverSha256": hashlib.sha256(driver.read_bytes()).hexdigest(),
        "scope": "Hosted Windows runner, actual installed WebView2 with automation enabled; not clean Windows 11 qualification",
        "result": "failed",
    }
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    environment = dict(os.environ, TAURI_WEBVIEW_AUTOMATION="true")
    session = None
    with (artifacts / "installed-ui-driver.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen(  # noqa: S603 - fixed CI-installed driver
            [str(driver), f"--port={port}", "--host=127.0.0.1"],
            stdout=log,
            stderr=log,
            env=environment,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", trust_env=False, timeout=60) as client:
            try:
                for _ in range(100):
                    if process.poll() is not None:
                        raise RuntimeError("WebDriver exited before readiness")  # noqa: TRY003
                    try:
                        if client.get("/status").is_success:
                            break
                    except httpx.HTTPError:
                        pass
                    time.sleep(0.2)
                created = client.post(
                    "/session",
                    json={
                        "capabilities": {
                            "alwaysMatch": {
                                "browserName": "webview2",
                                "ms:edgeChromium": True,
                                "ms:edgeOptions": {"binary": str(executable)},
                            }
                        }
                    },
                )
                created.raise_for_status()
                value = created.json()["value"]
                session = value["sessionId"]
                report["capabilities"] = value["capabilities"]
                prefix = f"/session/{session}"
                for _ in range(100):
                    response = client.post(
                        prefix + "/execute/sync",
                        json={
                            "script": "return {url:location.href,text:document.body.innerText};",
                            "args": [],
                        },
                    )
                    response.raise_for_status()
                    page = response.json()["value"]
                    if "记忆内容" in page["text"]:
                        break
                    time.sleep(0.2)
                else:
                    raise RuntimeError("Installed memory form did not render")  # noqa: TRY003
                if not page["url"].startswith("http://tauri.localhost"):
                    raise RuntimeError("Installed UI did not use packaged resources")  # noqa: TRY003
                report["packagedUrl"] = page["url"]
                screenshot = client.get(prefix + "/screenshot")
                screenshot.raise_for_status()
                (artifacts / "installed-ui.png").write_bytes(base64.b64decode(screenshot.json()["value"]))
                report["result"] = "passed"
            finally:
                try:
                    if session is not None:
                        client.delete(f"/session/{session}").raise_for_status()
                finally:
                    try:
                        process.terminate()
                        try:
                            process.wait(timeout=15)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait(timeout=10)
                    finally:
                        # Publish safe facts, never session paths or raw renderer output.
                        capabilities = report.pop("capabilities", {})
                        report["browserVersion"] = capabilities.get("browserVersion")
                        (artifacts / "installed-ui.json").write_text(
                            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                        )


if __name__ == "__main__":
    main()

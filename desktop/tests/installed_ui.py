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
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import httpx
from installed_workflow import exercise_memory
from real_server import HarnessFailure


def free_port() -> int:
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        return reservation.getsockname()[1]


@contextmanager
def owned_process(command: list[str], environment: dict[str, str], log_path: Path) -> Iterator[subprocess.Popen[bytes]]:
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(  # noqa: S603 - exact installed app or verified driver, only on CI
            command,
            stdout=log,
            stderr=log,
            env=environment,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        try:
            yield process
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)


def wait_endpoint(client: httpx.Client, path: str, process: subprocess.Popen[bytes], stage: str) -> None:
    for _ in range(150):
        if process.poll() is not None:
            raise HarnessFailure(stage + "_process_exited", str(process.returncode))
        try:
            if client.get(path, timeout=1).is_success:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.2)
    raise HarnessFailure(stage + "_readiness_timeout")


def wait_packaged_page(client: httpx.Client, prefix: str) -> str:
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
            if not page["url"].startswith("http://tauri.localhost"):
                raise HarnessFailure("installed_resources_not_packaged")
            return page["url"]
        time.sleep(0.2)
    raise HarnessFailure("installed_memory_form_not_rendered")


def screenshot(client: httpx.Client, prefix: str, artifacts: Path) -> bool:
    try:
        response = client.get(prefix + "/screenshot", timeout=10)
        response.raise_for_status()
        (artifacts / "installed-ui.png").write_bytes(base64.b64decode(response.json()["value"]))
    except (httpx.HTTPError, ValueError, KeyError):
        return False
    else:
        return True


def run_ui(executable: Path, driver: Path, artifacts: Path, report: dict[str, object]) -> None:
    debug_address = f"127.0.0.1:{free_port()}"
    driver_port = free_port()
    environment = dict(os.environ, TAURI_WEBVIEW_AUTOMATION="true")
    app_environment = dict(
        environment,
        WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=(
            f"--remote-debugging-port={debug_address.rsplit(':', 1)[1]} --remote-debugging-address=127.0.0.1"
        ),
    )
    with (
        owned_process([str(executable)], app_environment, artifacts / "installed-ui-app.log") as app,
        httpx.Client(base_url=f"http://{debug_address}", trust_env=False) as debug,
    ):
        report["stage"] = "application_start"
        wait_endpoint(debug, "/json/version", app, "installed_webview")
        report["webviewDebugEndpointReady"] = True
        with (
            owned_process(
                [str(driver), f"--port={driver_port}", "--host=127.0.0.1", "--verbose"],
                environment,
                artifacts / "installed-ui-driver.log",
            ) as process,
            httpx.Client(base_url=f"http://127.0.0.1:{driver_port}", trust_env=False, timeout=60) as client,
        ):
            report["stage"] = "driver_start"
            wait_endpoint(client, "/status", process, "webdriver")
            report["stage"] = "session_attach"
            created = client.post(
                "/session",
                json={
                    "capabilities": {
                        "alwaysMatch": {
                            "browserName": "webview2",
                            "ms:edgeChromium": True,
                            "ms:edgeOptions": {"debuggerAddress": debug_address},
                        }
                    }
                },
                timeout=120,
            )
            created.raise_for_status()
            value = created.json()["value"]
            prefix = f"/session/{value['sessionId']}"
            report["browserVersion"] = value["capabilities"].get("browserVersion")
            try:
                report["stage"] = "packaged_page"
                report["packagedUrl"] = wait_packaged_page(client, prefix)
                report["stage"] = "memory_workflow"
                report["workflow"] = exercise_memory(client, prefix)
            finally:
                report["screenshotCaptured"] = screenshot(client, prefix, artifacts)
                client.delete(prefix).raise_for_status()
    report["stage"] = "complete"
    report["result"] = "passed"


def main() -> None:
    if os.name != "nt" or os.environ.get("GITHUB_ACTIONS") != "true":
        raise HarnessFailure("disposable_windows_github_runner_required")
    executable = Path(sys.argv[1]).resolve(strict=True)
    driver = Path(os.environ["DESKTOP_EDGE_DRIVER"]).resolve(strict=True)
    artifacts = Path(__file__).resolve().parents[1] / ".artifacts"
    report: dict[str, object] = {
        "commit": os.environ.get("GITHUB_SHA"),
        "installedExecutableSha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
        "driverSha256": hashlib.sha256(driver.read_bytes()).hexdigest(),
        "scope": "Hosted Windows runner, actual installed WebView2 with automation enabled; not clean Windows 11 qualification",
        "result": "failed",
    }
    try:
        run_ui(executable, driver, artifacts, report)
    finally:
        (artifacts / "installed-ui.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()

/*
 * Copyright (c) 2026 OceanBase.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

use powercontext_desktop::ipc::allowed_navigation;
use tauri::{
    ipc::{CallbackFn, InvokeBody},
    test::{INVOKE_KEY, get_ipc_response, mock_builder},
    webview::InvokeRequest,
};

#[test]
fn permissions_reject_untrusted_window_origin_and_arbitrary_commands() {
    let dir = tempfile::tempdir().unwrap();
    let repository = powercontext_desktop::connections::profiles::ProfileRepository::open(
        dir.path().join("profiles.json"),
        std::sync::Arc::new(powercontext_desktop::credentials::WindowsVault),
    )
    .unwrap();
    let app = mock_builder()
        .manage(powercontext_desktop::commands::HostState {
            manager: Ok(
                powercontext_desktop::connections::session::ConnectionManager::new(repository),
            ),
        })
        .invoke_handler(tauri::generate_handler![
            powercontext_desktop::ipc::foundation_info,
            powercontext_desktop::commands::desktop_state,
            powercontext_desktop::commands::disconnect
        ])
        .build(tauri::generate_context!())
        .unwrap();
    for (label, origin, command, allowed) in [
        ("main", "http://tauri.localhost", "foundation_info", true),
        ("other", "http://tauri.localhost", "foundation_info", false),
        ("main", "https://evil.example", "foundation_info", false),
        ("main", "http://tauri.localhost", "desktop_state", true),
        ("other", "http://tauri.localhost", "desktop_state", false),
        ("main", "https://evil.example", "desktop_state", false),
        ("main", "http://tauri.localhost", "disconnect", true),
        ("other", "http://tauri.localhost", "disconnect", false),
        ("main", "https://evil.example", "disconnect", false),
        (
            "main",
            "http://tauri.localhost",
            "plugin:shell|execute",
            false,
        ),
        ("main", "http://tauri.localhost", "fetch", false),
        ("main", "http://tauri.localhost", "credential_read", false),
    ] {
        use tauri::Manager;
        let window = app.get_webview_window(label).unwrap_or_else(|| {
            tauri::WebviewWindowBuilder::new(&app, label, Default::default())
                .build()
                .unwrap()
        });
        let result = get_ipc_response(
            &window,
            InvokeRequest {
                cmd: command.into(),
                callback: CallbackFn(0),
                error: CallbackFn(1),
                url: origin.parse().unwrap(),
                body: InvokeBody::default(),
                headers: Default::default(),
                invoke_key: INVOKE_KEY.into(),
            },
        );
        assert_eq!(
            result.is_ok(),
            allowed,
            "{label} {origin} {command}: {result:?}"
        );
    }
}
#[test]
fn blocks_remote_navigation_and_userinfo() {
    for url in [
        "https://evil.example",
        "file:///C:/secret",
        "javascript:alert(1)",
        "http://tauri.localhost.evil",
        "http://user@tauri.localhost",
    ] {
        assert!(!allowed_navigation(&url.parse().unwrap()));
    }
    assert!(allowed_navigation(
        &"http://tauri.localhost/".parse().unwrap()
    ));
}

#[test]
fn diagnostic_command_is_narrow_and_requires_the_trusted_window() {
    let app = mock_builder()
        .manage(powercontext_desktop::diagnostics::DiagnosticHost::new(None))
        .invoke_handler(tauri::generate_handler![
            powercontext_desktop::commands::local_diagnostics
        ])
        .build(tauri::generate_context!())
        .unwrap();
    for (label, origin, kind, expected_missing) in [
        ("main", "http://tauri.localhost", "service", true),
        ("main", "http://tauri.localhost", "integrations", true),
        ("other", "http://tauri.localhost", "service", false),
        ("main", "https://evil.example", "service", false),
        ("main", "http://tauri.localhost", "shell", false),
    ] {
        use tauri::Manager;
        let window = app.get_webview_window(label).unwrap_or_else(|| {
            tauri::WebviewWindowBuilder::new(&app, label, Default::default())
                .build()
                .unwrap()
        });
        let result = get_ipc_response(
            &window,
            InvokeRequest {
                cmd: "local_diagnostics".into(),
                callback: CallbackFn(0),
                error: CallbackFn(1),
                url: origin.parse().unwrap(),
                body: InvokeBody::Json(serde_json::json!({"kind":kind})),
                headers: Default::default(),
                invoke_key: INVOKE_KEY.into(),
            },
        );
        let error = result.expect_err("missing CLI or rejected caller");
        assert_eq!(
            error == serde_json::json!("not_found"),
            expected_missing,
            "{label} {origin} {kind}: {error}"
        );
    }
}

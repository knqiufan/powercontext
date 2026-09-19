# PowerContext Desktop preview

Internal Windows preview for [#1654](https://github.com/oceanbase/powercontext/issues/1654), following RFC #1455. It provides a packaged Tauri 2 shell with Home, Connections, My memories, Chinese/English settings, semantic light/dark/system themes and honest disconnected states. Connection profiles, explicit activation, identity/readiness checks, exact Scope selection and local diagnostics are implemented. Memory forms remain unavailable until S3.

See [中文说明](README.zh.md), [security boundary](SECURITY.md), and [qualification evidence](evidence/S1.md). This is not a supported or signed release, and does not close #1654 or #1428.

## Build on Windows

Use Windows 11 x64, Visual Studio C++ Build Tools with a Windows SDK, Node **24.14.1**, pnpm **11.13.1**, Rust **1.95.0 MSVC**, and WebView2. `desktop/.mise.toml`, `rust-toolchain.toml`, `pnpm-lock.yaml` and `src-tauri/Cargo.lock` pin the tools and dependencies independently of Python and the website.

Some machines default to Rust's GNU host. In PowerShell, explicitly select the pinned MSVC host for this process:

```powershell
rustup toolchain install 1.95.0-x86_64-pc-windows-msvc --profile minimal --component clippy --component rustfmt
$env:RUSTUP_TOOLCHAIN = '1.95.0-x86_64-pc-windows-msvc'
pnpm --dir desktop install --frozen-lockfile
pnpm --dir desktop desktop:dev
```

From the repository root:

```powershell
pnpm --dir desktop lint
pnpm --dir desktop typecheck
pnpm --dir desktop test
pnpm --dir desktop build
pnpm --dir desktop ipc:check
cargo fmt --manifest-path desktop/src-tauri/Cargo.toml --check
cargo clippy --locked --manifest-path desktop/src-tauri/Cargo.toml --all-targets -- -D warnings
cargo test --locked --manifest-path desktop/src-tauri/Cargo.toml
pnpm --dir desktop desktop:build
```

`build` produces UI assets only. `desktop:build` produces the release executable and current-user NSIS installer under `desktop/src-tauri/target/release/bundle/nsis/`. No Python, private HTTP server, or Vite process is embedded or started by the installed application. Closing the window exits Desktop.

The unsigned installer is for internal verification. If WebView2 is absent, its configured download bootstrapper needs network access and may require the user to complete Microsoft installation prerequisites. The absent-runtime and standard-user cases require a disposable Windows environment; never remove a developer's WebView2 to simulate them.

## Connect an existing Server

1. Open Connections and add a named profile. HTTP is restricted to literal loopback hosts; other addresses require HTTPS. A reverse-proxy path prefix is preserved.
2. Explicitly choose unauthenticated loopback access or Bearer authentication. Bearer storage is either Windows Credential Manager or this session only. Trust/address changes require credential reconfiguration. An optional CA augments system trust without disabling certificate checks.
3. Select a qualified compatibility profile after comparing its tested build with your deployment. The selection does not prove the remote binary identity. See [S2 evidence](evidence/S2.md) for the exact fixture and supported combinations.
4. Save, then explicitly use the connection. Merely selecting a saved profile does not activate it. Review liveness, readiness, identity and capabilities separately; none implies resource authorization.
5. Find an authorized Scope by title (50 per page), inspect a default suggestion, or enter an exact Scope ID. Selection never creates a Scope or changes Agent bindings. Editing a query cancels its old read; connection and identity changes invalidate old results.

Profiles persist under the app data directory; credentials never appear in profile JSON. Active authorization, session-only credentials, Scope selection and query/results are not restored as an authenticated offline session. Remove a profile to remove its Desktop configuration and owned credential reference; it does not stop the Server or remove business data.

## Contracts and resources

`pnpm --dir desktop generate` derives TypeScript schemas and the reviewed ten-operation manifest from `openapi/powercontext.yaml`; `generate:check` detects drift, including a normalized contract SHA-256. Typed Rust adapters consume that generated manifest and generated wire schemas. No public route is independently handwritten in the application. The manifest is not an IPC permission grant.

`cargo run --locked --manifest-path desktop/src-tauri/Cargo.toml --example export_ipc` derives the TypeScript IPC request/receipt/error types from Rust. `ipc:check` verifies them. IPC exposes typed connection, Scope and diagnostic operations to the main window only; no generic fetch, shell, file, database or secret-read command is granted.

The canonical brand source is `website/assets/powercontext-color.png`, which is read directly without running the website. `pnpm --dir desktop icons` extracts its square mark and uses the pinned Tauri CLI to derive the Windows icon; `icons:check` verifies all three generated assets against the canonical source. UI SVGs originate from the repository's Desktop design assets and are promoted into `ui/src/assets/` for reproducible builds. They are project resources under the repository Apache-2.0 license.

## Native credential feasibility

```powershell
cargo run --locked --manifest-path desktop/src-tauri/Cargo.toml --example credential_probe
```

This explicit probe creates a uniquely named synthetic credential in the preview namespace, loads it in another process and deletes it. It never reads another application's credential or prints a secret. Normal tests simulate unavailable storage and require an explicit session-only choice. Do not treat the probe as end-to-end S2 credential-form verification.

The Windows CI workflow runs on PRs and the preview branch, verifies native vault persistence, builds an unsigned internal installer, and tests Chinese-path installation/uninstallation on its disposable runner. It uploads the installer and a JSON smoke report. CI and mocked IPC tests do not prove clean-machine installation, notification activation, independent service login or Agent capture/recall.

## Local CLI diagnostics

Settings provides explicit local service and Agent integration checks. They remain separate from the active remote connection; a missing local CLI does not disable remote operations. Integration checks may start temporary Agent helpers and do not prove capture/recall.

Register an explicitly trusted local installation in `%APPDATA%/com.powercontext.desktop.preview/diagnostic-cli.json`:

```json
{
  "executable": "C:/trusted/powercontext/Scripts/powercontext.exe",
  "sha256": "REPLACE_WITH_VERIFIED_64_CHARACTER_SHA256",
  "version": "1.0.1.dev61+g63f918b7e.d20260919",
  "source": "explicit_local_installation"
}
```

The native adapter checks the absolute executable path, pinned digest and fixed `--version` result before running either `service status --json` or `doctor integrations --json`. This is a local installation pin, not publisher-signature verification; the Python environment and dependencies must also be trusted. The adapter admits 1.0.1 and its development builds; the registration must pin the exact installed version. The example identifies the tested baseline. Other version series require adapter qualification. No PATH-first CLI selection or renderer-provided commands are accepted.

Version verification has a 15-second deadline, service status 20 seconds, and integration diagnostics 60 seconds. Each invocation limits combined stdout/stderr to 256 KiB. Helpers run hidden in an owned Windows Job; completion, timeout and cancellation clean up their descendants. Only allowlisted status fields reach the UI. Valid unhealthy JSON remains useful even with exit code 1. Isolated real-CLI checks pass; installed-application qualification remains open in [S2 evidence](evidence/S2.md).

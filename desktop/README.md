# PowerContext Desktop — S1 foundation

Internal Windows preview for [#1654](https://github.com/oceanbase/powercontext/issues/1654), following RFC #1455. It provides a packaged Tauri 2 shell with Home, Connections, My memories, Chinese/English settings, semantic light/dark/system themes and honest disconnected states. Connection management and Memory operations belong to S2/S3 and are not enabled here.

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

## Contracts and resources

`pnpm --dir desktop generate` derives TypeScript schemas and the reviewed ten-operation manifest from `openapi/powercontext.yaml`; `generate:check` detects drift, including a normalized contract SHA-256. The Rust liveness adapter consumes that generated manifest. No public route is independently handwritten in the application. The manifest is not an IPC permission grant.

`cargo run --locked --manifest-path desktop/src-tauri/Cargo.toml --example export_ipc` derives the TypeScript IPC request/receipt/error types from Rust. `ipc:check` verifies them. The only enabled IPC command is `foundation_info`; it returns safe build status, never secrets. The native-only vault/transport adapters are S2 inputs, not a connection UI.

The canonical brand source is `website/assets/powercontext-color.png`, which is read directly without running the website. `pnpm --dir desktop icons` extracts its square mark and uses the pinned Tauri CLI to derive the Windows icon; `icons:check` verifies all three generated assets against the canonical source. UI SVGs originate from the repository's Desktop design assets and are promoted into `ui/src/assets/` for reproducible builds. They are project resources under the repository Apache-2.0 license.

## Native credential feasibility

```powershell
cargo run --locked --manifest-path desktop/src-tauri/Cargo.toml --example credential_probe
```

This explicit probe creates a uniquely named synthetic credential in the preview namespace, loads it in another process and deletes it. It never reads another application's credential or prints a secret. Normal tests simulate unavailable storage and require an explicit session-only choice. Do not treat the probe as end-to-end S2 credential-form verification.

The Windows CI workflow runs on PRs and the preview branch, verifies native vault persistence, builds an unsigned internal installer, and tests Chinese-path installation/uninstallation on its disposable runner. It uploads the installer and a JSON smoke report. CI and mocked IPC tests do not prove clean-machine installation, notification activation, independent service login or Agent capture/recall.

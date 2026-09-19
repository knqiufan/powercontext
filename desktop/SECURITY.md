# Native boundary

## Renderer

Only the packaged main window receives the explicit `main` capability. The app manifest enumerates `foundation_info`, so Tauri does not implicitly grant custom commands to every window. The handler also checks the native window label. No capability grants a remote origin, general HTTP, shell, filesystem, SQL, notification, opener or credential-read access.

Production CSP allows packaged scripts/styles/images and Tauri IPC only, with no remote frames, forms or network fetch. The navigation callback permits the packaged origin, and permits the exact Vite origin only in debug builds. Production builds use Tauri's `custom-protocol` feature. No CSP bypass, unsafe eval, remote image or HTML execution is enabled. React renders text, never `dangerouslySetInnerHTML`.

## Secrets and transport

The vault namespace is `com.powercontext.desktop.preview`. A native credential ID is an opaque bounded identifier; it is not an endpoint or a user-controlled vault path. Windows credentials use the OS store only. Unavailable storage returns a stable error; session-only storage is an explicit separate choice. Secret values have zeroizing storage and cannot be serialized or debug formatted. The renderer has no secret readback operation. The synthetic opt-in probe only touches its unique test entry.

The Rust-derived write protocol accepts only `secret` and an explicit `storage` choice (`persistent` or `session_only`). Its input cannot be serialized; the success receipt contains only the storage choice. Missing modes, unknown modes and extra fields are rejected. The native caller supplies the credential ID; the renderer cannot choose a vault address. A failed persistent write produces no success receipt or automatic fallback.

S2 must create IDs in native code, bind credentials to an exact endpoint/trust configuration, invalidate them on changes, and add a write-only credential command only with the corresponding context and capability checks. S1 does not expose an incomplete credential form or persist connection profiles.

Native reqwest uses Windows system trust through native-tls/Schannel, plus an optional connection-local PEM CA (maximum 64 KiB). Hostname/certificate validation remains enabled. Automatic proxy inheritance and redirects are disabled. HTTP requires loopback. Userinfo, query, fragment, control characters, backslashes and dot segments are rejected before URL normalization. Percent-encoded base paths are conservatively rejected in S1; literal UTF-8 path prefixes are accepted. Public operation paths come from the generated OpenAPI manifest and preserve the base prefix.

Only the liveness read is implemented in S1. It verifies the response's `status: ok` without inferring authentication, compatibility or readiness. No business write or retry queue exists. S2 must implement typed operation-specific adapters, scope/context generation checks and ambiguous-write recovery before exposing business operations.

## Budgets and error projection

| Boundary | Limit |
| --- | --- |
| Endpoint input | 2048 bytes |
| Bearer input | 1–2048 printable ASCII bytes |
| Additional CA PEM | 64 KiB |
| Connect timeout | 5 seconds |
| Complete request, including response body | 15 seconds |
| Response body | 1 MiB, checked both by declared size and streamed bytes |
| Concurrent liveness reads per client | 4; excess fails as busy |

Error responses are enum codes. Transport exception text, endpoint URLs, bodies and credentials are never returned or logged. No product logging, telemetry, crash uploader or persistent business cache is configured. The app does not read databases, start a Server, inspect process environments or run CLI diagnostics.

Tests cover actual TLS fixtures and adversarial HTTP responses, shared loopback policy, mocked Tauri permission resolution with the real capability configuration, navigation rejection, unavailable vault behavior and the explicit session path. The opt-in Windows vault probe separately verifies persistence across processes. Packaged native and isolated machine results are tracked in [the evidence record](evidence/S1.md).

Framework references: [Tauri capabilities](https://v2.tauri.app/security/capabilities/), [Windows installer options](https://v2.tauri.app/distribute/windows-installer/).

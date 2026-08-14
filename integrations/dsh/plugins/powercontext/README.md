# PowerContext for DeepSeek Harness

This plugin is a thin DeepSeek Harness integration for a running PowerContext Server. It does not embed storage or start the Server.

Install it from a PowerContext checkout so the Server and plugin stay on the same ref:

```bash
powercontext setup dsh --source oceanbase/powercontext --ref master
powercontext server run
dsh web
```

`setup dsh` calls `dsh plugin --profile web add` on this directory. The plugin talks HTTP only. It does not use MCP.

Before each model step it:

1. recalls bounded context with `POST /v1/context/prepare`;
2. captures the current user input with `POST /v1/sources/content`.

Named `pc_*` tools cover Memory, handoff, experience, skill, and review. Everything else is reachable through `pc_call` by OpenAPI `operationId`. `/pc doctor` checks Server liveness and readiness.

The operations table in `src/operations.generated.ts` is generated from the repository `openapi/powercontext.yaml`. From the PowerContext root:

```bash
make js-api-generate
make js-api-generate-check
```

Environment overrides use the `POWERCONTEXT_DSH_` prefix for `BASE_URL`, `AUTHORIZATION`, `SCOPE_ID`, `CAPTURE_PROMPTS`, and `FLUSH_ON_CAPTURE`. `timeoutMs`, `requestTimeoutMs`, `maxBytes`, and `flushMaxCalls` are plugin patch settings. Context returned by recall is labelled as untrusted history. An unavailable Server never blocks normal Harness work. The plugin directory must contain a built `lib/index.js`.

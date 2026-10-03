# Dify acceptance

## Tested source and tools

Local validation date: 2026-10-03. Server baseline: PowerContext master `6b2f6e8a4c1aac59fca75662aca26d78748bfa29`; public HTTP contract version 1.2.0. The plugin's generated contract hashes canonical UTF-8/LF OpenAPI text so Windows Git line endings do not change it.

| Component | Tested version / environment |
| --- | --- |
| Plugin identity | `knqiufan/powercontext` 0.0.1, experimental local build |
| Plugin SDK | `dify-plugin==0.10.2` |
| Transport / schema validation | `httpx==0.28.1`, `jsonschema==4.25.1` |
| Official packaging CLI | 0.6.10, Windows amd64 |
| SDK and Server Python | CPython 3.12.13, Windows amd64 |
| HTTP backend | Real uvicorn/FastAPI Server with a disposable SQLite database |
| Generation | Deterministic injected Handoff/Experience/Skill generators |
| Workflow output metadata | Dify 1.17.1 official frontend helpers executed offline with generated declarations |
| Dify application / plugin daemon | Not run; no test deployment available |
| Live model / Marketplace | Not run |

## Passed local acceptance

- 41 focused regressions invoke registered SDK entries: exact catalog, hidden credential/Scope fields, native objects, input validation, UTF-8 limits, missing binding, credential read validation, malformed/oversized receipts, partial error receipts, transport failure, secret-bearing capture, sanitization and no automatic write retry. Named outputs are checked against their declared JSON schemas, and `result` must equal the complete successful response or `{}` on error/unknown. Ready and empty context responses retain their original text/null values.
- The HTTP/SQLite tests invoke all 19 loaded tools. Memory write/list/search/prepare/get/revise/retire remains usable through exact citations; Source capture retains structured metadata and a Unicode Source ID.
- Complete Handoff JSON passes prepare/finalize/temporary continue/commit/exact/latest readback. Full objects and references survive the SDK messages.
- Each of the 19 declarations exposes `result` as an object with inlined operation-specific response properties. An offline probe executes Dify 1.17.1's official [getOutputVars](https://github.com/langgenius/dify/blob/1.17.1/web/app/components/workflow/nodes/tool/default.ts) and [getVarType](https://github.com/langgenius/dify/blob/1.17.1/web/app/components/workflow/nodes/_base/components/variable/utils.ts) helpers with a fixture node inventory: all 19 results have children, and six context/Memory/Handoff selectors resolve to their expected string/object types. This checks output metadata parsing and selector resolution, not a rendered UI, actual workflow execution or daemon dispatch.
- Generation produces pending candidates; candidate list/get work; an administrator approves through the separate HTTP administration interface, after which Experience/Skill exact reads work.
- Separate SDK greenlets overlap Scope A/B reads and wrong-token/missing-binding calls. There is no event-loop nesting or mutable shared credential/Scope state. This is SDK concurrency, not plugin-daemon acceptance.
- Scope A/B searches do not expose another Scope's unique test entry. Tests use a shared administrator token and establish scoped filtering, not production multi-user authorization. Restricted-principal and nested cross-Scope authorization still require deployment evidence.
- Provider/declaration/Python bindings match the DSH tool-set manifest. Generated OpenAPI/declarations, isolated lint/format/types, root Linux-target types, repository contract and integration-manifest tests pass.
- Official CLI packaging succeeds. Archive inspection finds 19 tool declarations, source, icon, privacy, README and routing references, with no credentials, virtual environments, tests or bytecode caches.
- Website lint, tests, link validation and production static build pass; export validation checks 877 public pages and their internal links.

Local package: `.artifacts/dify/powercontext-0.0.1.difypkg`, 91679 bytes. SHA-256:

```text
82535f18c0af4e54386e5491e23f7df7318cc01950df8691cdc85cbe0fa74dab
```

The binary is an ignored local validation artifact, not a published Marketplace release. Match the package checksum to the exact reviewed source when preparing a submission.

## Commands and interpretation

```sh
uv lock --locked
uv run python scripts/release_version.py --check
uv run python scripts/generate_api.py --check
uv run python scripts/generate_js_operations.py --check
uv run python scripts/check_workflow_actions.py .github/workflows .github/actions
uv run python scripts/generate_integration_manifest_docs.py --check
uv run python -m pytest tests/test_integration_manifest.py tests/test_api_contract.py tests/test_js_operations.py
uv run --project integrations/dify python -X utf8 integrations/dify/generate_contract.py --check
uv run --project integrations/dify ruff check integrations/dify
uv run --project integrations/dify ruff format --check integrations/dify
uv run --project integrations/dify ty check --project integrations/dify --python integrations/dify/.venv
uv run --project integrations/dify python -X utf8 -m pytest integrations/dify/tests
uv run python -X utf8 -m pytest tests/e2e/test_dify_tools_http.py
dify plugin package integrations/dify/plugin -o .artifacts/dify/powercontext-0.0.1.difypkg
```

On this Windows host, native root `ty check` reports existing POSIX-only `fcntl`, `resource` and `os` attributes outside the Dify change. Root types are checked with `--python-platform linux`, matching the main quality CI job. The isolated plugin type check uses its real Python 3.12 environment. The focused pytest process reports upstream gevent late-patching and Pydantic deprecation warnings; the fresh SDK subprocess runs its patch before HTTP imports. These tests do not establish HTTPS or Dify daemon compatibility.

A concurrent SQLite write can return HTTP 409; the plugin reports a conflict and does not add a retry. Deployment concurrency must include the intended storage backend and Dify worker limits.

## Required deployment acceptance before publication

Record Dify, plugin-daemon, SDK, CLI, Python, Server SHA, package checksum and model/backend versions. Record each scenario as passed, failed or not run with trace/log evidence.

- [ ] Install the package in a clean Dify workspace; inspect icon, provider and all 19 tool declarations.
- [ ] Save/switch provider credentials, restart the daemon/application and invoke tools again.
- [ ] Exercise actual plugin dispatch with native and JSON-encoded objects/arrays, including nullable exact references, draft/prepared Handoff and nested metadata. Verify JSON and named outputs in workflow nodes.
- [ ] Verify HTTPS certificate validation and private-network HTTP configuration from the daemon.
- [ ] Test read/write permissions with restricted principals and nested citations/Artifacts/Handoffs/candidates across Scope boundaries.
- [ ] Overlap actual daemon requests using different credentials and Scopes; inspect credentials, Scope, outer deadlines and write outcomes.
- [ ] Exercise all 19 operations with supported real generation providers, complete readback and failure/unknown branches.
- [ ] Verify trusted application write controls; a model's self-reported consent must not authorize writing.
- [ ] Agree publisher, namespace, contact and maintenance ownership, including coexistence/upgrade with `oceanbase/powermem`.
- [ ] Submit the reviewed source/package to `langgenius/dify-plugins`; record repository acceptance and Marketplace availability separately.

## Deferred templates

After plugin-repository acceptance, build and export `recall-before-answer.yml`, `explicit-remember.yml`, `handoff-transfer.yml` and `generate-candidate.yml` under `integrations/dify/workflows/`. Reimport into clean applications, rebind credentials and validate variable wiring and empty/error branches. Recall ordering requires the trace to show preparation before the model and actual inclusion of `result.content` in model input.

Template development is a later milestone in [tracking issue #1837](https://github.com/oceanbase/powercontext/issues/1837); it is not a prerequisite for starting this source review, but plugin deployment acceptance remains a publication prerequisite.

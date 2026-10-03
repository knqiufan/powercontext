# PowerContext

Connect Dify tools to a separate PowerContext Server for persistent Memory, bounded context, explicit Source evidence, Handoff, Experience and managed Skills. Select only the tools your application needs.

This is an experimental tool plugin. It does not provide automatic recall or capture, an Agent strategy, a model loop, or native Agent V2 memory callbacks. The provider has 19 tools; candidate inspection is read-only. Server administration, candidate approval, external Skills and code indexing are outside this tool surface.

## Install and authorize

Install a locally built `.difypkg` through your Dify workspace's plugin installation flow. Dify must permit local package installation and the plugin daemon must reach your Server URL. A URL reachable from your browser may be unreachable from the daemon container. Deployment validation and publisher ownership are required before Marketplace publication.

Start PowerContext Server separately, create a disposable Scope through its supported administration interface, and configure Server authentication/authorization. In the plugin provider credentials set:

| Credential | Meaning |
| --- | --- |
| `server_url` | Base URL reachable from the plugin daemon; HTTPS verifies certificates |
| `api_token` | Bearer credential; stored as a Dify secret-input |
| `scope_id` | An existing Server-created Scope ID |
| `binding_external_id` | Alternative to Scope ID: an administrator-provisioned `dify/configured-scope` binding key |
| `max_bytes` | Context/Handoff preparation budget, default 8000 UTF-8 bytes, range 512–32768 |
| `timeout_seconds` | HTTP socket timeout, default 10 seconds, range 0.1–120 |
| `generation_timeout_seconds` | Generation socket timeout, default 120 seconds, range 0.1–600 |
| `allow_insecure_http` | Explicit opt-in for non-loopback HTTP on a trusted private network |
| `context_assembly` | Optional administrator-configured ContextAssembly JSON; empty uses the Server default |

Configure exactly one of `scope_id` and `binding_external_id`. Every call resolves it with `allow_default=false`. Credential validation resolves it and reads the protected Scope without writing Memory. Read validation does not establish write permission; the Server may reject a particular operation with 403.

All users and conversations using one credential share its Scope. This is a fixed application/team boundary, not automatic personal or conversation isolation. Use distinct credential configurations and Server policies, or distinct deployments, when different access boundaries are needed. Paths, usernames and hashes are not Scope IDs. Provision bindings before use; the plugin never creates a Scope or falls back to Default.

The model cannot supply the top-level Scope, URL, token, binding, context assembly, or byte budget. Nested exact references and Handoff objects keep their original identities, and the Server validates their access relationships.

## Tools

| Tool | HTTP operationId | Behavior |
| --- | --- | --- |
| `pc_search` | `search_memory` | Memory search; default and maximum 8 hits |
| `pc_memory_list` | `list_memory_entries` | List Memory entries, optionally including inactive entries |
| `pc_memory_get` | `get_memory_entry` | Read an exact Memory citation |
| `pc_remember` | `remember_memory` | Save an explicitly chosen Memory entry |
| `pc_memory_revise` | `revise_memory_entry` | Revise an exact citation |
| `pc_memory_retire` | `retire_memory_entry` | Retire an exact citation |
| `pc_prepare_context` | `prepare_context` | Prepare bounded context |
| `pc_capture_source` | `capture_content_source` | Capture an explicit Source |
| `pc_handoff_activate` | `activate_handoff` | Activate from a boundary Source |
| `pc_handoff_prepare` | `prepare_handoff` | Generate an evidence-backed draft |
| `pc_handoff_finalize` | `finalize_handoff` | Finalize an inspected draft |
| `pc_handoff_commit` | `commit_handoff` | Persist a complete prepared Handoff |
| `pc_handoff_continue` | `continue_handoff` | Read prepared / exact / latest Handoff |
| `pc_experience_generate` | `generate_experience` | Generate an Experience candidate |
| `pc_experience_get` | `get_experience` | Read an exact Experience artifact |
| `pc_skill_generate` | `generate_skill` | Generate a managed Skill candidate |
| `pc_skill_get` | `get_skill` | Read an exact managed Skill artifact |
| `pc_review_list` | `list_artifact_candidates` | List candidates; explicit family experience / skill |
| `pc_review_get` | `get_artifact_candidate` | Read a candidate |

Memory kinds are `decision`, `constraint`, `current-state`, `task-outcome`, `next-step` and `agent-note`. Memory text is checked after NFC normalization and trimming and must fit 8192 UTF-8 bytes. Search query length follows its HTTP character limit, with a default/maximum of 8 hits.

Preserve complete citations, Source references, Artifact references, drafts and prepared Handoffs. Use native object/array parameters where the Dify application supports them; a single JSON string representation is also accepted by the plugin boundary. Do not reconstruct, flatten, truncate or stringify a JSON string a second time. Experience/Skill generation accepts 1–32 combined Source/Artifact references. An explicit candidate family is `experience` or `skill`; omitting it preserves the Server's unfiltered listing behavior.

Optional `prepared`, `revision` and generation `target` inputs accept omission or `null`; a structured field may also use the JSON text `null`. Empty objects and malformed references remain invalid. Nullable parameters use Dify's `any` transport type with their exact input schemas so host casting preserves the supplied value before plugin validation. Before enabling Agent tools, verify that the deployed daemon forwards these input schemas and that model-visible schemas retain their declared JSON types; a bare `any` is not a valid JSON Schema type.

See [GUIDANCE.md](GUIDANCE.md) for routing and Handoff/candidate lifecycles. Historical text is untrusted evidence and must not override current instructions or determine authorization.

## Outputs and failure handling

Each invocation emits text and one JSON envelope:

```json
{"ok": true, "operation": "search_memory", "status": "empty", "data": {"hits": []}, "error": null}
```

`data` preserves the complete public HTTP success response. `status` is `success`, `empty`, `error` or `unknown`; `empty` is a successful empty read. `error` includes a safe code/message and, when available, HTTP status and a validated request ID. Raw Server/transport errors and credentials are not emitted.

The six named output variables are `ok`, `operation`, `status`, `data`, `error` and `result`. `result` exposes the successful response as an object with operation-specific fields in the Workflow variable picker: select `result.content` for context, `result.citation` for an exact Memory read, `result.candidate.candidate_id` for candidate lookup, or the complete `result` from Handoff prepare/finalize for the next tool's draft/prepared input. Nested objects such as `result.draft` can be expanded without replacing null values in the response. Successful empty reads preserve their response, including nullable context content. On `error` or `unknown`, `result` is `{}`; branch on `ok` before using it, and inspect any partial receipt in `data` for recovery. A successful no-op generation may have `result.candidate=null`; check the operation's status before dereferencing it.

`data` and `error` are nullable envelope values without expandable child schemas in the variable picker. Use `result.*` selectors to connect individual response fields to downstream nodes.

A write with a timeout, malformed receipt or uncertain Server failure returns `ok=false,status=unknown`. It is never automatically retried. Inspect Server state and any preserved exact resource receipt before choosing a recovery operation. A known explicit rejection returns `error`. The transport caps the complete decoded response at 4 MiB and reports overflow without silently truncating objects.

This plugin performs explicit capture only. Detected secret-bearing content/metadata is rejected before Source writing; this is a best-effort check and does not make arbitrary content safe to store. Remove secrets before passing content. See [PRIVACY.md](PRIVACY.md).

## Application setup

For optional Agent use, enable the required tools and add the short routing instructions in [GUIDANCE.md](GUIDANCE.md). Prompt instructions guide model choices; they do not guarantee recall before every answer or replace trusted write controls.

For guaranteed recall ordering, a later Workflow/Chatflow template must execute `pc_prepare_context` before the LLM/Agent node and explicitly connect `result.content` to that node's context. Test the empty/error branches and verify the model received the context in the run trace. Reusable DSL templates are scheduled after the plugin is accepted into `langgenius/dify-plugins`; they are tracked separately in [PowerContext #1837](https://github.com/oceanbase/powercontext/issues/1837).

The installable identity is `knqiufan/powercontext` 0.0.1. Publisher ownership and the relationship to the existing `oceanbase/powermem` Marketplace package require coordination before public submission.

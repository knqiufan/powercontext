---
title: Dify
description: Experimental Dify tools for a separate PowerContext Server.
---

# Dify

The [PowerContext tool plugin](https://github.com/oceanbase/powercontext/tree/master/integrations/dify) provides 19 HTTP tools for Memory, bounded context, explicit Source capture, Handoff, Experience/Skill generation and exact reads, and read-only candidate inspection. It is experimental source, with Marketplace publication tracked in [#1837](https://github.com/oceanbase/powercontext/issues/1837).

Deploy PowerContext Server separately. Build the plugin with the official Dify CLI, install the package in your workspace and configure a daemon-reachable Server URL, bearer token, and exactly one existing Scope ID or pre-provisioned `dify/configured-scope` binding key. Each call disables Default-Scope fallback. Credential validation resolves and reads the protected Scope; Server policies determine each operation's permissions.

One credential is a shared fixed application/team Scope. It does not infer per-user or per-conversation isolation from Dify runtime fields. Nested references remain unchanged and the Server validates their access. Use appropriately restricted credentials/policies or separate instances for distinct authorization boundaries.

The plugin does not automatically recall/capture, approve candidates, manage Scopes, install external Skills, or provide Agent V2 memory callbacks. Optional Agent instructions guide tool selection but do not guarantee recall before every answer. A Workflow/Chatflow must execute `pc_prepare_context` before the model and explicitly connect `result.content` to the model input for that guarantee. Reusable templates follow acceptance of the plugin into `langgenius/dify-plugins`.

Calls emit text, JSON and six named outputs: `ok`, `operation`, `status`, `data`, `error`, `result`. Successful data preserves the complete HTTP response; `empty` is a successful empty read. The Workflow variable picker exposes operation-specific fields under `result`, including context content and exact references. Branch on `ok` before using `result`; it is `{}` on error/unknown, while `data` retains any partial recovery receipt. Write timeouts or invalid receipts return `unknown`; inspect Server state before recovery because the plugin does not retry. Remove secrets before explicit Source capture. Historical text is untrusted evidence.

Optional Handoff selection references and generation targets accept omission or null; empty reference objects are invalid. Workflow selectors can traverse `result.candidate.candidate_id` and `result.draft.objective` while complete response objects retain their null values. Check the operation's status before reading a nullable candidate or draft. Before using Agent tools, deployment acceptance must verify that the daemon retains the declared input schemas in model-visible tool definitions.

See the source [README](https://github.com/oceanbase/powercontext/blob/master/integrations/dify/README.md), [tool catalog](https://github.com/oceanbase/powercontext/blob/master/integrations/dify/tool-coverage.md), [Scope mapping](https://github.com/oceanbase/powercontext/blob/master/integrations/dify/scope-mapping.md), [privacy](https://github.com/oceanbase/powercontext/blob/master/integrations/dify/plugin/PRIVACY.md) and [acceptance evidence](https://github.com/oceanbase/powercontext/blob/master/integrations/dify/ACCEPTANCE.md).

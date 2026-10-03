# PowerContext Dify tools

An experimental Dify tool plugin with 19 HTTP-backed tools, aligned with the DSH tool catalog. It connects to an independently deployed PowerContext Server; the Server owns domain validation, authorization, storage and generation.

The installable source is [plugin/](plugin/). Runtime dependencies are isolated from the PowerContext Python package and pinned in `uv.lock` and `plugin/requirements.txt`. The plugin runner uses Python 3.12, Dify SDK 0.10.2, httpx 0.28.1 and jsonschema 4.25.1. The repository's supported Python versions are unchanged.

## Development and packaging

From the PowerContext repository root:

```sh
uv sync --locked --project integrations/dify --python 3.12
uv run --project integrations/dify python integrations/dify/generate_contract.py --check
uv run --project integrations/dify ruff check integrations/dify
uv run --project integrations/dify ruff format --check integrations/dify
uv run --project integrations/dify ty check --project integrations/dify --python integrations/dify/.venv
uv run --project integrations/dify python -m pytest integrations/dify/tests
uv run python -m pytest tests/e2e/test_dify_tools_http.py
dify plugin package integrations/dify/plugin -o .artifacts/dify/powercontext-0.0.1.difypkg
```

On Windows set `PYTHONUTF8=1`, or invoke Python with `-X utf8`, because the pinned SDK reads YAML with the process's default encoding. Install the root environment with `uv sync --locked` before the HTTP tests. `make dify-test` runs these source checks and HTTP tests; install the official Dify CLI separately for packaging. Packages, virtual environments and credentials must stay outside Git.

The generated contract is a closure of the 19 selected operations plus internal Scope resolution and protected Scope retrieval from `openapi/powercontext.yaml`. After an API change, regenerate with `generate_contract.py`, inspect the contract and declaration changes, and rerun the checks. This script does not modify Server models. Native objects/arrays and single JSON strings are accepted at the tool boundary; fields and complete receipts remain structurally validated.

## Usage and evidence

- [Installation, credentials and tools](plugin/README.md)
- [Scope mapping and trust boundary](scope-mapping.md)
- [Tool coverage](tool-coverage.md)
- [Acceptance evidence and deployment checklist](ACCEPTANCE.md)
- [Agent guidance](plugin/GUIDANCE.md)
- [Privacy](plugin/PRIVACY.md)

No Workflow/Chatflow DSL templates ship with this plugin. Their construction and clean reimport tests follow acceptance of the plugin submission in `langgenius/dify-plugins`, as tracked in [#1837](https://github.com/oceanbase/powercontext/issues/1837). Plugin installation and complex-object dispatch still require real Dify validation before publication.

## Coordination and attribution

[Tracking issue #1837](https://github.com/oceanbase/powercontext/issues/1837) tracks implementation, ownership, deployment acceptance, publication and later templates. [Draft PR #1558](https://github.com/oceanbase/powercontext/pull/1558) by @thunguo established earlier Dify tools, Scope/binding, privacy and acceptance work; this implementation follows the tools-focused scope proposed in #1837 and the current Server contract. The prior eight-tool/legacy strategy commit is not imported wholesale.

The local package identity is `knqiufan/powercontext`, version 0.0.1. A Marketplace publisher, maintenance owner and coexistence/upgrade policy for the existing `oceanbase/powermem` entry must be agreed before submission. Source implementation, plugin-repository acceptance and Marketplace availability are separate milestones.

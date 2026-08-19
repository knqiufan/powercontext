# Add an e2e sample

This page is the contribution path for a pinned end-to-end sample. It is not a guide for adding a full
benchmark suite. CI uses the sample to answer one question: did this exact case pass?

## What this path is for

Add one Harbor task plus one PowerContext workload manifest. The catalog then loads that pair, the Bub
acceptance command can select it, and `make harness-check` can validate it without inventing a second
runner.

Use this path when you want a small, reviewable Memory capture-and-recall case in the default
`acceptance` set. Do not use it to publish a LoCoMo, LongMemEval, or BEAM score.

## What you reuse

Copy the existing Harbor plus `powercontext-e2e acceptance` path:

- Harbor owns the multi-step task (`capture`, then `recall`).
- `e2e/bub/tasks/<id>.yaml` owns provenance, the Harbor task checksum, and Memory assertions.
- The Bub adapter and `powercontext_e2e` evaluator stay unchanged.

Do not add a new runner, a new evaluation schema, or a second execution stack. The current scorer
checks that each `expected_context` substring appears in prepared context. It does not support
`forbidden_context` or an empty-context "Unknown" case.

The in-tree reference is `locomo-support-group`. New LoCoMo-derived samples should keep that
remember-then-context shape.

## Files you add

Each sample needs a Harbor exam and a PowerContext cover sheet:

```text
e2e/bub/harbor-tasks/<id>/
  task.toml
  environment/Dockerfile
  steps/capture/instruction.md
  steps/capture/tests/test.sh
  steps/recall/instruction.md
  steps/recall/tests/test.sh
e2e/bub/tasks/<id>.yaml
```

`<id>` must match in three places: the Harbor folder name, `dataset.task_id`, and the YAML `id`.
Use `[a-z0-9][a-z0-9_-]*`.

The Harbor `task.toml`, `Dockerfile`, and `steps/*/tests/test.sh` files should match
`locomo-support-group`. The native Harbor reward is not the Memory gate. Copy the existing
`echo 1 > /logs/verifier/reward.txt` verifier.

## Manifest fields

Start from `e2e/bub/tasks/locomo-support-group.yaml` and keep the same schema:

```yaml
schema: powercontext.e2e-task/v1
id: locomo-example
categories:
  - acceptance
  - sample
provenance:
  source: benchmark/locomo/dataset/locomo10.json
  revision: 4448275ea2c5cd0af5774d80aea7b05b5a16e1b996caf8554ca3d762a301ae84
  selection: <versioned-policy>/v1
  case_ids:
    - <sample_id>
    - <sample_id>:<question_id>
    - <evidence-session>
dataset:
  path: e2e/bub/harbor-tasks
  task_id: locomo-example
  checksum: <64-hex-from-a-real-harbor-run>
execution:
  type: bub
  model: false
  max_steps: 10
  max_tokens: 4096
evaluation:
  expected_memory:
    - <fragment>
  probes:
    - id: <probe-id>
      query: <same as recall instruction>
      expected_context:
        - <fragment>
  thresholds:
    probe_coverage: 1
```

Field meaning:

- `provenance.revision` is the sha256 of the source dataset file. `load_tasks()` rejects the
  manifest if that file changes.
- `provenance.selection` is a versioned policy such as `first-conversation-first-question/v1`.
  Do not write `random`.
- `dataset.checksum` is Harbor's resolved task checksum, not a hash you invent by hand.
- `execution.type` must be `bub`. `execution.model` is `false` for these pinned samples.
- Keep `categories` as `acceptance` and `sample`. Do not mark a pinned sample `long-horizon`.

`capture/instruction.md` is one `powercontext.remember` line. For a multi-hop case, put every
fact the probe needs in that single `text=` value. `recall/instruction.md` is one
`powercontext.context` line. The probe `query` must match that context query.

## Anti-leakage

Agent-visible instructions must not contain:

- a gold-answer label
- the LoCoMo category number
- a turn identity such as `D1:3`
- `adversarial_answer`

Those values belong in YAML `provenance` and the pull-request description. The remember text may
state the pinned fact in natural language, as `locomo-support-group` already does.

## How to compute checksums

There are two hashes, and they measure different things.

1. `provenance.revision` is the sha256 of the source dataset file:

   ```text
   python -c "import hashlib, pathlib; print(hashlib.sha256(pathlib.Path('benchmark/locomo/dataset/locomo10.json').read_bytes()).hexdigest())"
   ```

   The current pinned LoCoMo file is
   `4448275ea2c5cd0af5774d80aea7b05b5a16e1b996caf8554ca3d762a301ae84`.
   Check the file out with LF line endings. A CRLF checkout changes the digest and fails
   `load_tasks()`.

2. `dataset.checksum` is the Harbor task checksum observed on a real run. Use the
   `task_provenance_matches` failure reason or `replay.json` field `harbor.task_checksum`.
   A first draft may use 64 quoted zeros as a placeholder (`"0000..."`). YAML otherwise
   reads an unquoted all-zero value as the integer `0`. Do not invent a plausible-looking hash.

## How to run

```text
make harness-check
make harness-compose-acceptance ARGS="--id <id>"
```

`make harness-check` validates the Bub harness, catalog YAML, and `e2e/bub/tests`. It does not
need Docker. The full Harbor exam needs Docker and is the Linux / CI path.

On Windows without Docker, run `make harness-check` and `make docs-test`. Leave the Harbor
checksum as a placeholder until a Linux or CI run fills the observed value. Do not claim Harbor
acceptance from an unrun checksum.

After adding manifests, update `e2e/bub/tests/test_workload_catalog.py`. The expected id list
follows `tasks/*.yaml` filename order. New `acceptance` samples must appear in the acceptance
selection and must still exclude `terminal-bench-db-wal-recovery`.

## What not to claim

One to three pinned samples are not a LoCoMo score. They do not replace
`benchmark/locomo`, and they do not belong in a coding-versus-conversation A/B report.
Say that the case is a pinned sample derived from a named LoCoMo question.

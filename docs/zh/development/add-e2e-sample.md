# 新增一条 e2e sample

本页是「钉死一条端到端小题」的贡献路径，不是完整 benchmark 套件的接入说明。CI 只用它回答一件事：这道题过了没有。

## 这条路径解决什么

你要新增的是一份 Harbor 考卷，外加一份 PowerContext workload 清单。catalog 能加载这一对文件，Bub
acceptance 能选中它，`make harness-check` 能校验它。不要为此再写一套 runner。

固定小题、希望它进入默认 `acceptance` 集合时，走这条路径。不要用它发布 LoCoMo、LongMemEval 或 BEAM
分数。

## 复用什么

沿用现有的 Harbor + `powercontext-e2e acceptance` 路径：

- Harbor 负责多步考卷（先 `capture`，再 `recall`）。
- `e2e/bub/tasks/<id>.yaml` 负责 provenance、Harbor task checksum 和 Memory 断言。
- Bub adapter 与 `powercontext_e2e` 评分器保持不动。

不要新增 runner、新的评分 schema，或第二套执行栈。当前评分器只检查
`expected_context` 子串是否出现在 prepared context 里，不支持 `forbidden_context`，也不支持空
context 的「Unknown」题。

仓库内的对照样本是 `locomo-support-group`。新的 LoCoMo 衍生题应保持「先 remember、再 context」的形态。

## 要加哪些文件

每条样本都需要一份 Harbor 考卷和一份 PowerContext 阅卷封面：

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

`<id>` 必须在三处一致：Harbor 文件夹名、`dataset.task_id`、YAML 的 `id`。
只使用 `[a-z0-9][a-z0-9_-]*`。

Harbor 的 `task.toml`、`Dockerfile` 和 `steps/*/tests/test.sh` 应与 `locomo-support-group` 相同。
任务原生分不是 Memory 门槛。继续复制现有的
`echo 1 > /logs/verifier/reward.txt` verifier。

## YAML 字段

从 `e2e/bub/tasks/locomo-support-group.yaml` 起步，沿用同一份 schema：

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

字段含义：

- `provenance.revision` 是源数据集文件的 sha256。文件变了，`load_tasks()` 会拒收这份清单。
- `provenance.selection` 是版本化策略，例如 `first-conversation-first-question/v1`。不要写
  `random`。
- `dataset.checksum` 是 Harbor 解析后的 task checksum，不是手算出来的值。
- `execution.type` 必须是 `bub`。这类钉死样本的 `execution.model` 为 `false`。
- `categories` 使用 `acceptance` 和 `sample`。不要把钉死小题标成 `long-horizon`。

`capture/instruction.md` 只允许一行 `powercontext.remember`。多跳题把答题所需的全部事实写进
**同一条** `text=`，不要让 Agent 在这一步自由发挥。`recall/instruction.md` 只允许一行
`powercontext.context`。probe 的 `query` 必须与这行 context 查询一致。

## 防泄漏

Agent 可见的 instruction **不得出现**：

- gold answer 标注
- LoCoMo category 编号
- `D1:3` 这类 turn id
- `adversarial_answer`

这些只写在 YAML 的 `provenance` 和 PR 描述里。remember 文本可以用自然语言写出钉死的事实，现有
`locomo-support-group` 已经是这种写法。

## 两个 hash

这两个 hash 测的不是同一件事。

1. `provenance.revision` 是源数据集文件的 sha256：

   ```text
   python -c "import hashlib, pathlib; print(hashlib.sha256(pathlib.Path('benchmark/locomo/dataset/locomo10.json').read_bytes()).hexdigest())"
   ```

   当前钉死的 LoCoMo 文件是
   `4448275ea2c5cd0af5774d80aea7b05b5a16e1b996caf8554ca3d762a301ae84`。
   请按 LF 检出该文件。CRLF 会改变摘要，并让 `load_tasks()` 失败。

2. `dataset.checksum` 是一次真实试跑观察到的 Harbor task checksum。以
   `task_provenance_matches` 失败原因或 `replay.json` 的 `harbor.task_checksum` 为准。
   初稿可以用带引号的 64 个 `0` 占位（`"0000..."`）。YAML 会把未加引号的全 0 读成整数
   `0`。不要手算一个看起来像的 hash。

## 怎么跑

```text
make harness-check
make harness-compose-acceptance ARGS="--id <id>"
```

`make harness-check` 校验 Bub harness、catalog YAML 和 `e2e/bub/tests`，不需要 Docker。
完整 Harbor 开考需要 Docker，以 Linux / CI 为准。

Windows 上没有 Docker 时，至少先过 `make harness-check` 和 `make docs-test`。Harbor checksum
留到 Linux 或 CI 按观察值回填。不要在未跑 Harbor 的情况下宣称已经验收。

新增清单后，更新 `e2e/bub/tests/test_workload_catalog.py`。id 列表按 `tasks/*.yaml` 文件名排序。
新的 `acceptance` 样本必须出现在 acceptance 选择结果里，并且仍然排除
`terminal-bench-db-wal-recovery`。

## 不能怎么写

1～3 条钉死样本不是 LoCoMo 分数。它们不能替代 `benchmark/locomo`，也不能写进
coding-versus-conversation A/B 报告。表述时应写明：这是从指定 LoCoMo 问题衍生出的 pinned sample。

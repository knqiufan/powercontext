---
title: Agent 指引验证记录
description: tracking issue 1450 D 的工具选择测量、执行证据及模型限制。
---

# Agent 指引验证记录

实现规则与复现命令见[工具选择与结果报告](integration-guidance.md)。基线为上游
`fe4002d37663213294ebffe4c080b6676b1c8014`，测量日期为 2026-09-09，环境为 Windows，模型为配置的
StepFun endpoint 上的 `step-3.7-flash`，temperature 为 0，输出预算为 6,000 token，不强制工具选择。
测试使用虚构的 Aurora 事实和隔离的 `fixture-scope`。

## 模型行为测量

[调用、参数、受控返回及回复记录](https://github.com/oceanbase/powercontext/blob/master/e2e/integration-guidance/results/step37-20260909.jsonl)
保留了失败结果。**这些数据不表示模型场景全部通过，提示词也不承担权限执行职责。**
初始矩阵含 11 个中英文场景，分别加载和不加载 Skill，每个宿主 44 次观察。

| 入口 | 工具选择通过 / 观察次数 |
| --- | --- |
| DSH 基线 | 36 / 44 |
| DSH 实现 | 41 / 44 |
| Pi | 42 / 44 |
| OpenCode | 41 / 44 |
| OpenClaw | 34 / 44 |
| Codex MCP 工具及 Skill | 38 / 44 |
| Claude Code MCP 工具及 Skill | 39 / 44 |
| WorkBuddy MCP 工具及 Skill | 38 / 44 |
| Hermes | 41 / 44 |
| 可移植 Agent Plugin Skill 配合 MCP | 35 / 44 |

DSH 基线在 Skill 未加载时出现了预览请求多余检索和过早准备 Handoff。实现后的普通任务、上下文充分、搜索、盘点、
保存、预览、交接、Review、空检索和失败保存场景在该样本中全部通过（40/40）；三个失败均尝试调用验证器已从目录
移除的保存工具。目录验证器没有执行任何真实操作。

矩阵最初只接受 MCP 的高层工作交接操作；部分被记为失败的调用实际选择了合法的底层 Source 捕获。验证器现已接受
两种路径，原始观察记录予以保留，不追溯改写成更高的实测成功率。

边界验证在三种 Skill 状态下覆盖上下文充分、盘点、交接、预览和空检索，WorkBuddy 为 30/30，Agent Plugin 为
29/30，OpenClaw 为 27/30。DSH、Pi、OpenCode、Hermes、Codex、Claude Code 的 Skill 不可用测试共通过 125/132。
剩余情况包括预览时多余检索、Hermes 过早 prepare 及调用缺失工具。通过 OpenClaw 实际 prompt builder 重建可用工具
集合后，保存工具缺失场景为 1/2。OpenClaw 没有打包 Skill，其 Skill 状态标签表示重复目录条件，不能证明 Skill 加载。

另外检查了结果报告：明确保存请求在受控成功后才确认；失败保存与空搜索给出对应解释。部分空搜索继续扩大查询或转为
list，仍保留为有限预算场景的失败。服务超时和空回答也计为失败。工具描述补充了当前事实、临时交接和精确 Handoff
证据的限制；不能据此保证所有模型都遵循指引。

## 执行与回归证据

- 真实 DSH 0.1.2-rc.1 SDK/host 请求在加载 Skill 前包含系统指引及全部 19 个 PowerContext 原生工具。真实宿主测试
  覆盖召回、注入、重启恢复、直接错误和 Scope 隔离。
- Step 3.7 通过真实 DSH 选择了 `pc_remember`。固定 SDK 没有交互确认通道，因此宿主拒绝写入；模型明确说明未保存，
  并定位到确认通道不可用。Server 检查确认没有写入 Memory。随后明确搜索请求找到了预置记忆并返回精确引用，工具选择
  没有被 fixture 强制指定。
- 仓库现有真实 Codex 验收通过了实际保存、随后搜索及 MCP endpoint 不可用时不虚报成功。使用桌面应用自带的 Codex CLI
  0.153.4 和配置的 `gpt-6-astra` 模型；子进程按 UTF-8 解码，本地连接绕过代理，测试服务采用有限的优雅退出时间。
- DSH 包与 HTTP 测试、含真实 CLI 的 Pi 包测试、OpenCode/OpenClaw 包测试、MCP 初始化、Hermes provider、API 契约和
  能力清单检查验证执行行为与工具身份。OpenClaw 使用其固定 SDK 支持的 Node 24.15.0。

## 验证边界

真实注册目录和受控 Skill 正文不能证明每个外部宿主都能自动发现 Skill 或完成整个工作流。三个 MCP 宿主共享 Server
工具，其目录测量不等于分别执行了三个原生 CLI。移除工具的压力场景仍可能触发模型调用幻觉，这些场景没有标成通过；
实际权限执行仍须拒绝缺失工具并保留宿主确认。不能从生成文字推断已经发布、安装、持久提交或执行工作。

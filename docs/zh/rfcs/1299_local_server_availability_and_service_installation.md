- Proposal Name: local_server_availability_and_service_installation
- Start Date: 2026-08-21
- RFC PR: [oceanbase/powercontext#1299](https://github.com/oceanbase/powercontext/pull/1299)
- Tracking Issue: [oceanbase/powercontext#1298](https://github.com/oceanbase/powercontext/issues/1298)

# Summary

PowerContext 将本地 Server 的运行职责与安装、部署生命周期分离。Server CLI 继续提供显式的前台命令
powercontext server run。Agent 集成仍然采用 fail-open，但必须让用户看见 Server 不可用；powercontext doctor
则负责解释已安装的服务注册、原生服务管理器、Server liveness 和 Server readiness 是否一致。

对于个人安装，可选的 distribution 所有的 service-install 层会把现有前台 Server 命令注册到操作系统原生的
当前用户服务管理器中。它不属于 Server CLI，不会在 setup 期间自行启用，不要求管理员权限，也不会创建第二个
PowerContext supervisor。托管部署继续使用容器或由管理员管理的系统服务。本 RFC 为 Linux、macOS 和 Windows
定义统一契约，同时允许接受后的实现拆成可独立评审的变更。

# Motivation

Agent 集成依赖可访问的 PowerContext Server，但不拥有其进程生命周期。正常的本地入口有意保持为前台进程：

~~~text
powercontext server run
~~~

这一默认方式可观察、可撤销，但终端关闭或机器重启后进程就会消失。由于集成采用 fail-open，后续 Agent 会话仍可继续，
但 recall 和 capture 会被跳过。现有结构化诊断可能写入日志或 stderr，用户仍可能把该故障体验为 PowerContext 行为的
静默丢失。

把登录后自动启动直接放在 powercontext server 下会混合两种职责。Server package 负责如何运行一个已配置进程；
安装和 distribution 负责操作系统是否应该持久地启动该进程。这一区分也分开了两种部署模式：

- 个人安装可以使用当前用户拥有的原生服务。
- 托管部署应使用容器或由管理员管理的系统服务，并采用部署专属的配置、凭据、健康检查和重启策略。

PowerContext 在实现前需要为这条边界形成持久设计。它还需要让用户能够区分：未安装服务、原生服务未运行、
Server 不可访问，以及 Server 已存活但 Runtime 未就绪。

# Guide-level explanation

## Deployment profiles

PowerContext 为 Server 记录三种运行方式。

### Interactive personal use

现有命令继续作为默认方式，并保持当前行为：

~~~text
powercontext server run
~~~

它在前台运行，把日志输出到终端，并在 Ctrl-C 后停止。安装 PowerContext 或 Agent 集成都不会创建持久的操作系统状态。

### Persistent personal use

希望 Server 在登录后自动运行的用户，可以通过 distribution 层显式安装当前用户服务：

~~~text
powercontext service install
powercontext service status
~~~

本 RFC 提议的 service 命令组不属于 powercontext server。它只管理当前用户下、由 PowerContext 拥有的注册产物。
默认不安装，且不需要 root、SYSTEM 或管理员账号。

安装后的服务仍然执行同一个 Server 入口，不会在 PowerContext 内引入新的 daemon：

~~~text
powercontext server run
~~~

移除注册使用：

~~~text
powercontext service uninstall
~~~

卸载注册会停止由该注册拥有的 Server 实例，并只删除 PowerContext 创建的产物。它不会终止一个无关的前台 Server。

### Managed deployment

个人服务安装器不是生产部署管理器。托管安装使用项目的容器镜像，或者由管理员管理的 systemd system unit、
launch daemon、Windows service 或等价的 orchestrator。PowerContext 不通过 powercontext service 安装这些
高权限资源。

## What users see when the Server is unavailable

Agent 集成继续 fail-open：recall 或 capture 失败不能阻塞宿主任务。但集成必须通过宿主的 warning 或 diagnostic
通道暴露不含内容的 server_unavailable 诊断。集成不得从 prompt hook 尝试安装、启动或重启 Server。

该提示引导用户运行：

~~~text
powercontext doctor
~~~

Doctor 分别报告事实，而不是把它们压缩为一个连接错误：

- 是否存在个人服务注册；
- 原生服务管理器是否报告该服务 active；
- 配置的 Server endpoint 是否 live；
- 已存活的 Server 是否 ready；
- 与观测状态相符的恢复动作。

示例：

~~~text
service_registration  not_installed  optional: run powercontext service install
server_liveness       failed         run powercontext server run, or install the personal service
server_readiness      skipped        not checked because Server liveness failed
~~~

以及：

~~~text
service_registration  installed
service_manager       inactive       inspect the native user-service logs
server_liveness       failed         registered service did not become reachable
server_readiness      skipped        not checked because Server liveness failed
~~~

Service status 的范围比 doctor 更窄。它报告注册状态、manager 状态和 Server liveness，但不替代 Server 的
readiness 诊断。

# Reference-level explanation

## Responsibility boundaries

接受后的设计为每项关注点分配一个所有者：

| 关注点 | 所有者 | 必需行为 |
| --- | --- | --- |
| 构造并运行 ASGI 进程 | Server role | powercontext server run 保持前台且可独立使用 |
| 在 Agent 任务期间 recall 和 capture | Integration | fail-open，暴露 Server 不可用，但不拥有生命周期 |
| 诊断已安装环境 | CLI diagnostics | 关联注册、manager、liveness 和 readiness 状态 |
| 注册个人后台进程 | Distribution/service-install layer | 管理原生当前用户产物并执行 Server 入口 |
| 运行托管部署 | Operator or orchestrator | 使用容器或由管理员管理的系统服务 |

任何集成都不导入平台服务 adapter。任何平台服务 adapter 都不属于 src/powercontext/server，也不改变 Server
应用启动。Distribution 层可以通过顶层 powercontext CLI 暴露用户契约，但命令入口不会把职责转移给 Server role。

## CLI contract

初始 distribution 契约为：

~~~text
powercontext service install
powercontext service uninstall
powercontext service status
~~~

这些命令只操作当前用户的个人服务。不存在 --system、--machine、--root 或管理员安装模式。

### Install

Install 执行以下步骤：

1. 为当前操作系统选择受支持的原生当前用户服务 adapter。
2. 解析已安装 PowerContext 入口的绝对、非 shell 命令。
3. 在改变原生状态前渲染并验证注册产物。
4. 只创建或更新被识别为 PowerContext 个人 Server 注册的产物。
5. 为后续用户登录启用该注册。
6. 仅在配置的 Server endpoint 尚未 live 时立即启动服务。
7. 操作完成后报告注册、原生 manager 和 liveness 状态。

使用相同目标定义重复安装应成功，且不产生语义变化。如果 PowerContext 拥有的定义已过期，则在原生 manager 支持时
原子替换。如果 endpoint 已经 live，安装不得启动竞争进程；注册仍会为下次登录保持 enabled。

当平台不受支持、目标产物不属于 PowerContext、无法解析 executable，或原生 manager 拒绝操作时，Install 必须失败且
不留下部分所有权。它不得覆盖仅仅 display name 相似的外部 unit、task 或 launch agent。

### Uninstall

Uninstall 禁用并删除 PowerContext 拥有的注册。它会在 manager-owned process 处于 active 时停止该进程，但不会仅仅
因为某个进程监听配置端口就终止它。注册不存在时重复卸载应成功。

如果删除不完整，命令会报告剩余产物和原生恢复命令。清理范围绝不能扩大到目录、任意 task name 或未经验证的 process
identifier。

### Status

Status 是只读操作，同时提供人类可读和 JSON 输出。其稳定状态模型包括：

~~~text
support: supported | unsupported
registration: installed | not_installed | invalid | unknown
manager: active | inactive | failed | unknown
server_liveness: live | unreachable | unknown
~~~

Registration 表示精确的 PowerContext-owned 原生产物状态；Manager state 来自原生 manager；Liveness 来自配置的健康
检查 endpoint。这些值有意保持独立：没有注册时前台 Server 也可能 live，存在注册时 Server 也可能 unreachable。

JSON 输出不得包含凭据、完整 process environment 或无关的原生服务 metadata。

## Native personal-service adapters

所有 adapter 都注册当前用户，使用无 shell 的绝对命令执行同一个 PowerContext Server，并把日志写入 status 和
doctor 可指向的操作系统原生位置。

### Linux

受支持的 adapter 是 systemd --user。它在用户的 systemd 配置目录下拥有一个 unit，并通过 user service manager
完成 enable、start、stop、status 和日志操作。它绝不写入 /etc/systemd/system，也绝不启用 linger。没有可用 user
systemd manager 的 Linux 环境报告 unsupported；首个实现不会静默回退到 shell startup file 或桌面专属 autostart。

### macOS

受支持的 adapter 是用户 Library/LaunchAgents 目录下的 per-user LaunchAgent。它使用 launchd 当前用户 domain，
绝不创建 LaunchDaemon 或 privileged helper。

### Windows

受支持的 adapter 是在当前用户登录时触发的 Task Scheduler task。它以该用户身份运行，绝不使用 SYSTEM。
允许隐藏 process window。该 adapter 不安装 Windows Service。

原生 identifier 和 path 是项目常量。每个产物都携带足够的静态身份，使 status 和 uninstall 能够区分
PowerContext-owned definition 与外部资源。

## Configuration and credentials

服务安装器记录 executable、必需参数和不敏感的 service metadata。它不会把调用者的完整 environment、shell profile、
API key、bearer token 或 provider credential 复制进原生注册产物。

因此，初始个人服务模式依赖原生当前用户服务环境中可获得的配置。在不读取 secret 就能够观测时，status 和 doctor 必须
检测常见配置偏差。需要超出原生当前用户服务契约的凭据注入或环境管理的部署，仍由 operator 管理。

本 RFC 不引入 portable credential store、environment snapshot 或跨平台 secret-file 格式。如果没有这些契约之一，
个人服务安装无法支持项目文档中的 inference 配置，那么在 service-install implementation 宣布 generally available
之前必须解决配置传递问题。

## Integration availability signal

每种集成都有自己的宿主执行模型，因此展示机制由 adapter 决定。共同语义契约为：

- transport failure、timeout 或 HTTP 503 映射为 server_unavailable；
- recall 和 capture 继续彼此独立地 fail-open；
- 诊断不包含 prompt、recalled content、token 或 credential；
- 宿主任务继续，且不注入 PowerContext content；
- 集成提供可发现的 powercontext doctor 路径；
- hook 绝不启动或安装 Server。

Authentication failure、version mismatch、invalid response、成功的 empty result 和 Server unavailability 保持为
不同 outcome。有 host-native warning channel 时，实现应使用该通道，并保留结构化诊断用于 troubleshooting。

## Doctor diagnostics

Powercontext doctor 继续作为 installed-environment 的权威诊断。当 service-install capability 存在时，新增：

| 检查 | 含义 |
| --- | --- |
| service_support | 原生个人服务 adapter 可用 |
| service_registration | 精确的 PowerContext-owned 注册已安装且有效 |
| service_manager | 原生 manager 对该注册报告的状态 |
| server_liveness | 配置的 endpoint 满足 liveness contract |
| server_readiness | live Server 报告 ready、degraded 或 not ready |

Doctor 不从开放端口推断 registration，也不从 manager process identifier 推断 liveness。当事实不一致时，detail 会指出
差异并给出下一项安全动作。JSON 诊断保留与人类可读输出相同的 check name 和 status vocabulary。

## Upgrade and executable drift

注册指向解析后的安装入口，而不是 shell alias。Status 验证记录的命令是否仍然存在。安装路径移动或显著变化后，doctor
会报告 stale command 或 definition mismatch。

更新 Python distribution 不会静默改写操作系统状态。再次运行 service install 会让注册与当前安装的 distribution
保持一致。在 distribution 拥有事务化 upgrade hook 之前，文档必须包含这一 reconciliation 步骤。

## Failure handling and observability

原生启动失败继续出现在原生日志中。Service status 和 doctor 会指出如何查看日志。平台 adapter 返回结构化失败，
但不包含 secret environment value。

配置 endpoint 已 live 时，注册命令不得创建重复 Server。原生 restart policy 必须有界，不得把持久配置错误转化为
无限快速重启循环。具体重启间隔可以按平台不同，但测试必须覆盖渲染出的 policy。

## Security and compatibility

- 个人服务安装是 opt-in 且 per-user。
- Setup 命令绝不隐式启用。
- 任何操作都不请求 privilege elevation。
- 注册后的 Server 保留其配置 bind address；安装器不会把它改成 public address。
- 该功能不引入新的 HTTP、MCP、persistence 或 authentication contract。
- Server run 保持当前前台行为。
- Uninstall 只删除经过验证的 PowerContext-owned artifact。
- 诊断和日志绝不暴露 credential 或 captured content。

## Delivery and testing

接受本 RFC 不要求一个实现 PR。Tracking issue 可以把工作拆为：

1. 宿主可见的 integration diagnostics；
2. 相关联的 doctor diagnostics 和共享 service state model；
3. distribution-owned CLI 和 adapter protocol；
4. Linux、macOS 和 Windows adapter；
5. 文档和平台 integration test。

共享状态模型和安全规则适用于每个平台 adapter。文档必须说明 release 中实际存在的支持，不能在 adapter 交付前暗示已经支持。

Focused test 覆盖 rendering、ownership verification、幂等 install/uninstall、executable drift、status disagreement、
redaction 和 already-live short circuit。Platform test 只在匹配的操作系统运行，并验证 register、query、在安全时 start、
stop 和 remove。CI 不必模拟 interactive login，但必须断言原生 trigger 和登录后将执行的精确命令。

Integration test 验证 unavailable、authentication failure、version mismatch、invalid response 和 empty success 保持为
不同、不含内容且 fail-open 的 outcome。Doctor test 覆盖 registration、manager、liveness 和 readiness 的每种独立组合，
只要该组合会产生不同恢复动作。

# Drawbacks

- 包含三个原生 adapter 的 distribution 层比一个前台命令增加了更多代码和运维面。
- 原生当前用户服务环境不同，特别是在接收配置和凭据方面。
- Server 持续不可用时，宿主可见 warning 可能产生噪音；集成需要适合宿主的展示方式，同时不能隐藏问题。
- 拆分实现可能让不同 release 暂时存在平台支持差异。
- 顶层 service 命令为部分用户永远不会使用的生命周期增加了 CLI vocabulary。
- 个人服务安装不能解决托管部署、远程访问、多用户隔离或生产 secret management。

# Rationale and alternatives

## Put autostart under the Server CLI

powercontext server autostart enable 之类的命令与 server run 放在一起更容易发现，但会让 Server role 拥有安装和
操作系统持久化。本 RFC 分离 process construction 与 service installation。

## Start the Server from an integration hook

这种方式减少了一项 setup 步骤，但会让短生命周期、对 latency 敏感的 hook 拥有 process lifecycle。并发宿主可能竞争，
cold startup 可能拖慢 prompt，credential 或 configuration 也可能不一致。Hook 继续作为 consumer，只暴露 unavailability。

## Enable a service during setup

隐式安装会意外创建持久进程和操作系统状态。Setup 继续安装 integration 并推荐显式下一步；service installation
保持 opt-in。

## Publish manual recipes only

手工 systemd、launchd 和 Task Scheduler 指南可以避免 adapter code，但会随 release 漂移，也没有共享 status、
ownership、uninstall 或 doctor contract。原生 manager 仍是实际机制，但由 PowerContext 拥有可撤销的个人注册。

## Install a privileged system service everywhere

Machine-wide service 在用户正常的 trust 和 configuration boundary 之外启动，并要求提权。个人安装不需要该权限。
Managed operator 仍可显式定义 privileged service。

## Build a PowerContext supervisor

跨平台 supervisor 会重复原生 restart、logging 和 lifecycle 能力。Service-install 层注册现有前台进程，而不自行
supervise。

## Require one pull request for all platforms

一个变更可以避免临时的平台支持差异，但会耦合彼此独立的原生集成，使 review 和 rollback 更困难。RFC 固定共享契约；
tracking issue 可以拆分实现，同时文档报告实际 availability。

## Make no change

用户可以一直打开终端或自行创建 service definition，但不可用的 integration 仍可能令人困惑，个人注册也继续缺少受支持的
诊断与 uninstall 路径。

# Prior art

systemd user service、macOS LaunchAgent 和 per-user Task Scheduler task 提供原生的 login-session lifecycle、
logging 和 status，不需要项目自建 supervisor。Developer tool 通常保留 interactive foreground command，同时为持久个人
使用提供独立的 install 或 service command。

容器和 administrator-managed service 是托管 workload 的成熟部署边界，因为它们明确 identity、configuration、
credential、restart policy 和 observability。本 RFC 把这一区分应用到 PowerContext，而不是把所有本地或托管 Server
都看成同一种 autostart 问题。

# Unresolved questions

- 公开 distribution command 应保持为 powercontext service，还是放在现有 setup-oriented command 下，同时避免暗示
  Server role 拥有 installation？
- 对 Codex、Claude Code 和 DeepSeek Harness，哪种 host-native presentation 能实现可见但不阻塞的
  Server-unavailable diagnostic，并避免 warning fatigue？
- 每种原生当前用户服务环境保证提供哪些已记录的个人配置？在 generally available 前是否需要单独的 non-secret
  configuration contract？
- Install 是否默认立即启动服务，还是只为下次登录注册，除非用户提供显式 start option？
- 每个平台应保留哪些稳定的原生 identifier，使 ownership check 与未来 package rename 兼容？

这些问题必须在 RFC review 中解决，或者在相应 implementation 宣布完成前显式缩小范围。Managed deployment
automation、public binding、remote multi-user service profile、privileged installation 和 portable secret store
不在本 RFC 范围内。

# Future possibilities

- 增加 distribution-specific container manifest 或 administrator template，而不改变个人服务契约。
- 在单独提案中增加稳定的 non-secret Server configuration file 和平台 credential integration。
- 在事务化 package upgrade 期间 reconcile 个人服务注册。
- 在 CLI 和诊断契约稳定后增加原生 desktop status surface。
- 当能够避免暴露 secret 时，让 doctor 提供有界的 log excerpt。

# PowerContext Desktop 预览版

这是 #1654 的内部工程预览。已建立 Tauri 2、React、TypeScript 和 Vite 独立工程，提供首页、连接、我的记忆、双语设置及浅色／深色／系统主题。无连接时保存和搜索不可用，不展示示例业务数据。

已实现连接配置、显式激活、身份与就绪检查、精确范围选择和本地诊断。记忆保存、搜索和精确阅读界面仍待 S3 完成。当前不是已签名的正式发行版。

## 开发与构建

Windows 11 x64 上需要 Node 24.14.1、pnpm 11.13.1、Rust 1.95.0 MSVC、Visual Studio C++ Build Tools、Windows SDK 和 WebView2。安装后的用户程序不依赖 Node、Rust、Python 或本地 Server。

从仓库根目录执行：

```powershell
rustup toolchain install 1.95.0-x86_64-pc-windows-msvc --profile minimal --component clippy --component rustfmt
$env:RUSTUP_TOOLCHAIN = '1.95.0-x86_64-pc-windows-msvc'
pnpm --dir desktop install --frozen-lockfile
pnpm --dir desktop desktop:dev
```

`pnpm --dir desktop build` 只构建前端。`pnpm --dir desktop desktop:build` 构建原生 release 程序和当前用户 NSIS 安装包，输出到 `desktop/src-tauri/target/release/bundle/nsis/`。完整检查入口见 [英文 README](README.md)。

缺少 WebView2 时，安装器配置为下载 Microsoft bootstrapper，需要网络。标准用户、无 WebView2、无 Python 的干净机器场景必须在隔离环境验证，不能通过卸载开发机依赖来模拟。

## 连接已有 Server

1. 在连接页添加名称和 Server 地址。HTTP 只允许字面 loopback 地址，其他地址必须 HTTPS；可保留反向代理路径前缀。
2. 明确选择未认证本机服务或 Bearer。凭据可保存到 Windows 凭据管理器或仅本次会话；地址或信任变化后需要重新配置凭据。自定义 CA 不会关闭证书校验。
3. 核对部署版本后选择已验证兼容配置，具体构建摘要和范围见 [S2 证据](evidence/S2.md)。选择配置不能证明远端二进制身份。
4. 保存后点击“使用此连接”。查看其他配置不会自动切换当前连接。分别查看可达性、就绪、身份和能力，不把其中一项当作资源授权。
5. 按标题分页查找范围、查看默认建议，或输入精确 Scope ID。每页最多 50 项；不创建范围或修改 Agent 绑定。修改查询取消旧请求，切换连接或身份后旧结果失效。

连接配置存放在应用数据目录，JSON 不包含秘密。重启后需要重新验证连接和选择范围；仅会话凭据不保留。移除连接仅移除此桌面的配置和自有凭据，不停止 Server 或删除业务数据。

工程边界：

- OpenAPI 自动派生的 TypeScript schema 和十项 operation 映射，包含契约摘要及漂移检查。
- Rust 自动派生的 IPC 类型与安全错误；凭据只写请求必须显式选择持久化或仅会话，成功回执只含存储模式，不含秘密或凭据标识。
- Windows Credential Manager 原生适配器；保存失败直接报错，只有显式选择才采用仅会话内存。秘密类型不支持序列化，不实现 Debug。
- 使用系统证书信任的原生 HTTPS；可为单个客户端添加显式 CA，继续校验主机名。
- HTTP 仅允许 loopback，拒绝地址中的用户信息、查询、片段、反斜杠及路径逃逸；不继承代理、不跟随重定向。
- 连接超时 5 秒、完整请求超时 15 秒、响应上限 1 MiB、每个客户端最多 4 个并发读取；超限明确失败。
- 主窗口可调用明确列出的连接、Scope 和诊断命令；没有通用 fetch、shell、文件、数据库或读取秘密的 IPC。

应用不启动 Server、不管理服务、不持久化正文或查询；关闭窗口即退出。当前语言和主题也仅保留于会话内。

[安全边界](SECURITY.md)记录具体约束；[S1 验证记录](evidence/S1.md)区分已经执行的测试和仍未满足的 P0 门槛。构建成功、Mock 测试和当前用户机器上的运行都不能代替标准用户、签名、通知冷启动激活、独立服务和 Agent 宿主验收。

## 本机 CLI 诊断

设置中的诊断只检查当前电脑，与远程连接状态分开。程序不从 PATH 自动选择 CLI，也不安装或启动 Server。集成检查可能运行临时 Agent 辅助进程；结果不代表实际 capture/recall 已验证。

显式信任某个本地 PowerContext 安装后，在 `%APPDATA%/com.powercontext.desktop.preview/diagnostic-cli.json` 写入下面的配置。`executable` 必须是 `powercontext.exe` 的绝对路径，`sha256` 是该文件经核对的 SHA-256。当前诊断适配器允许 1.0.1 及其开发构建；必须填写实际安装的精确版本，下列示例是已测试基线。其他版本系列需另行验证。不要把文件摘要匹配当作发布者签名认证；Python 安装及其依赖也必须来自你信任的环境。

```json
{
  "executable": "C:/trusted/powercontext/Scripts/powercontext.exe",
  "sha256": "填写经核对的64位SHA256摘要",
  "version": "1.0.1.dev61+g63f918b7e.d20260919",
  "source": "explicit_local_installation"
}
```

Desktop 在每次诊断前检查固定路径、摘要，并用固定的 `--version` 核验版本；然后只允许 `service status --json` 或 `doctor integrations --json`。版本核验最长 15 秒，服务检查最长 20 秒，集成检查最长 60 秒；每次进程调用的 stdout/stderr 合计最多 256 KiB。窗口隐藏，进程及其后代归属于本次专属 Windows Job，结束或超时后清理。界面只显示允许的状态字段，不显示任意 detail、路径或原始输出。合法 JSON 配合退出码 1 仍可显示不健康结果。

未配置或未通过核验时，本机诊断不可用，独立远程业务仍可使用。进程树清理和隔离真实 CLI 测试已通过；安装后交互与完整 S2 资格仍待验收。

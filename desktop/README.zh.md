# PowerContext Desktop：S1 工程基础

这是 #1654 的内部工程预览。已建立 Tauri 2、React、TypeScript 和 Vite 独立工程，提供首页、连接、我的记忆、双语设置及浅色／深色／系统主题。无连接时保存和搜索不可用，不展示示例业务数据。

连接配置与身份验证属于 S2，Memory 保存、搜索和精确阅读属于 S3。当前不是完整连接预览，也不是已签名的正式 Windows 发行版。

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

## S2 可用输入

- OpenAPI 自动派生的 TypeScript schema 和十项 operation 映射，包含契约摘要及漂移检查。
- Rust 自动派生的 IPC 类型与安全错误；凭据只写请求必须显式选择持久化或仅会话，成功回执只含存储模式，不含秘密或凭据标识。
- Windows Credential Manager 原生适配器；保存失败直接报错，只有显式选择才采用仅会话内存。秘密类型不支持序列化，不实现 Debug。
- 使用系统证书信任的原生 HTTPS；可为单个客户端添加显式 CA，继续校验主机名。
- HTTP 仅允许 loopback，拒绝地址中的用户信息、查询、片段、反斜杠及路径逃逸；不继承代理、不跟随重定向。
- 连接超时 5 秒、完整请求超时 15 秒、响应上限 1 MiB、每个客户端最多 4 个并发读取；超限明确失败。
- 唯一启用的 IPC 是只读 `foundation_info`。凭据和传输适配器只在 Rust 中使用，没有通用 fetch、shell、文件、数据库或读取秘密的 IPC。

应用不启动 Server、不管理服务、不持久化正文或查询；关闭窗口即退出。当前语言和主题也仅保留于会话内。

[安全边界](SECURITY.md)记录具体约束；[S1 验证记录](evidence/S1.md)区分已经执行的测试和仍未满足的 P0 门槛。构建成功、Mock 测试和当前用户机器上的运行都不能代替标准用户、签名、通知冷启动激活、独立服务和 Agent 宿主验收。

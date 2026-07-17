# R4 内置更新器设计

日期：2026-07-16  
状态：经用户授权由 Codex 自审批通过

## 目标

让单独下载的 EXE 可以自行检查、下载和安装更新，不要求 Python、uv 或 ZUV 环境。交互参考 Clash Verge Rev 的手动检查、后台检查、进度显示、缓存下载和重启安装流程。

## 已确认的现状

- 当前 `check_for_updates` 只控制 ZUV 的 `.zuv-update-disabled` 哨兵。
- 独立 PyInstaller EXE 不具备自更新能力。
- Windows 不能由运行中的进程可靠覆盖自身，因此必须使用独立更新助手完成替换。

## 用户流程

### 手动检查

1. 用户在“系统与更新”点击“检查更新”。
2. 页面显示检查中、当前版本、最近检查时间和结果。
3. 有新版本时显示版本号、中文 Release 摘要和“下载更新”。
4. 下载时显示字节进度和百分比。
5. 校验完成后提供“重启并安装”和“稍后安装”。

### 后台检查

- 设置项 `自动检查更新` 默认开启。
- 启动 10 秒后执行一次，不阻塞 GUI 和触觉后端。
- 最多每 24 小时检查一次。
- 默认只后台检查并提示，不意外重启软件。
- 可选 `后台下载更新`，默认关闭。开启后下载并校验，下一次启动前仍向用户确认安装。

## 更新源和安全约束

- 只访问 `piereacy/FH-DualSense-Enhanced` 的 GitHub Releases API。
- 只接受 `R` 加整数的稳定 Tag，忽略 Draft 和 Prerelease。
- 只接受符合当前 UI 方案的 EXE 资产，防止更新后界面方案被意外替换。
- 使用 HTTPS，设置超时、最大响应体和最大 EXE 大小。
- 下载到 `.part` 文件，完成后校验 SHA-256。
- Release 同时提供 `<asset>.sha256`，更新器必须校验该文件中的哈希。若将来 GitHub API 提供可信 `digest`，可作为额外校验来源。
- 未通过 PE 头、版本、文件名或哈希检查的文件不进入待安装状态。

## Windows 替换流程

1. 主程序将新 EXE 缓存到用户数据目录的 `updates/`。
2. 主程序写入只包含绝对路径、目标 PID、哈希和重启参数的更新计划 JSON。
3. 主程序启动同版本内置的 `FH-DualSense-Update-Helper.exe`，然后正常退出。
4. Helper 等待旧 PID 退出，将旧文件改名为 `.old`，将新文件移动到目标位置，再启动新 EXE。
5. 移动或启动失败时，Helper 恢复 `.old` 并记录错误。
6. 新版本成功启动后清理 `.old`、缓存和计划文件。

若目标目录无写权限，GUI 明确提示并允许只下载到用户可写目录，不静默请求管理员权限。

## ZUV 兼容性

- R4 不删除 `[tool.zuv]` 和现有 ZUV 启动方式。
- GUI/TUI 的更新开关改为内置更新器语义，不再控制 ZUV 哨兵。
- 检测到 ZUV 环境时显示“当前由 ZUV 启动”，但内置手动检查仍可使用。
- README 将 EXE 作为推荐安装方式，ZUV 作为兼容和开发入口。

## 模块边界

- `src/modules/update/model.py`：版本、Release 和状态数据结构。
- `src/modules/update/github.py`：Release 查询、资产选择和下载。
- `src/modules/update/service.py`：线程安全状态机、缓存、节流和回调。
- `src/modules/update/install.py`：更新计划、Helper 调度和清理。
- `packaging/windows/update_helper.py`：不导入 GUI 或触觉模块的最小替换助手。

## 状态机

`IDLE -> CHECKING -> AVAILABLE|UP_TO_DATE|ERROR -> DOWNLOADING -> VERIFYING -> READY -> INSTALLING`

每个状态都携带可展示消息；后台线程只发布不可变快照，GUI 在 Tk 主线程轮询并更新控件。

## 验收

- 用本地 HTTP Fixture 测试无更新、有更新、超时、错误 JSON、错误资产和错误哈希。
- 用临时目录和测试进程验证替换、回滚与清理，不覆盖真实 EXE。
- 手动检查不会冻结 GUI。
- 后台检查失败不影响 UDP、扳机和握把触觉。
- 独立 EXE 不存在 ZUV 环境变量时仍能完成检查和下载流程。


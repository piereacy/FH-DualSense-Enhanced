# Enhanced R7 运行时基础设施实施计划

日期：2026-07-19
状态：实施中

对应规格：`docs/superpowers/specs/2026-07-19-r7-updater-controller-dpi-design.md`

## 1. 保存基线并固定现有行为

- 记录 `git status --short --branch`、最近提交和完整未提交差异，不覆盖用户工作。
- 运行更新器、DualSense、GUI/DPI 相关定向测试，再运行完整 `uv run --project src pytest -q`，把既有失败与 R7 回归分开。
- 为 R6 当前 Helper 的真实输出形态建立 fixture：R7 字节位于 R6 文件名、真实 R6 位于 `.old`。
- 保持 Forza 遥测、扳机优先级、握把混音、XInput 映射和社区默认驾驶参数逐字段不变。

## 2. 建立更新事务纯模型

- 在 `src/modules/update/` 增加 transaction plan、journal phase、健康确认和恢复决策的不可变模型；路径、版本、SHA-256、PID、参数、token 与快捷方式进度必须显式保存。
- journal 使用同目录临时 JSON 加 `Path.replace()` 原子提交，拒绝未知 schema、越界路径、非法版本和哈希不匹配。
- 为每个 phase 编写中断恢复测试，保证任何时间至少保留一个经过哈希确认的可启动版本。
- 把 `cleanup_previous_update()` 的“看到 `.old` 就删”改为按 journal 决策；旧无 journal 安装只允许执行保守兼容清理。

## 3. 重构 Windows Update Helper

- 重写 `packaging/windows/update_helper.py`，支持 R7 以后版本并存安装、健康等待、提交、回滚和有限文件锁退避，不再为正常更新创建 `.old`。
- Helper 使用进程 handle 区分旧 PID 已退出与访问被拒绝；错误通过日志和原生 MessageBox 呈现。
- 为 R6 -> R7 增加第二阶段兼容计划：消费旧 Helper 产生的 `.old`，恢复规范 R6，安装规范 R7；快捷方式迁移失败时保留 R6 而不是 `.old`。
- 使用临时目录和 fake process/launcher 覆盖成功、30 秒超时、token/版本/路径/hash 不匹配、启动即退、只读目录、同名冲突和回滚失败。

## 4. 接入启动前恢复与健康确认

- 在 `src/main.py` 的配置、GUI/backend 初始化之前执行 legacy bootstrap 和未完成 transaction 恢复。
- 内部 CLI 参数只携带 transaction id/token，不写回普通重启参数；GUI、TUI、headless 分别在自身最低可运行边界写原子健康确认。
- 修复 windowed EXE 配置损坏时调用不可见 `input()` 的路径，GUI 显示可交互恢复对话框；该状态仍可通过二进制健康确认。
- 更新安装必须继续经过统一退出和未命名 Profile 提示；Helper 调度失败时主程序不退出。

## 5. 实现精确快捷方式迁移

- 新增独立 shortcut migration 模块，只扫描当前用户 Known Folders 和已知 pinned 目录。
- 使用 Windows Shell Link COM 的标准库 `ctypes` 边界，精确匹配规范化旧 EXE 绝对路径；保留参数、工作目录、显示状态、描述、AppUserModel 属性和图标索引。
- 只有图标路径也精确指向旧 EXE 时才改到新版；保存后重新读取验证并通知 Explorer 刷新。
- 测试无快捷方式、多位置、多参数、旧 EXE 图标、部分失败和后续重试；无匹配静默成功，部分失败保留旧版本并进入 `cleanup_pending`。

## 6. 扩展 DualSense 输入验证和状态模型

- 在 `src/modules/dualsense/` 增加不可变 `ControllerSnapshot` 与 phase/transport/charging enum，兼容属性从快照派生，GUI 不再用 `dev is not None` 判断在线。
- `input_state.py` 统一验证 USB/BT 完整长度、report ID、公共布局和 D-pad；Bluetooth 在解析前用 `0xA1` seed 校验 CRC32。
- 从有效输入报告按官方规则解析 10% 电量档和充电状态；损坏报告不得刷新 `_last_input_at`、电量或 XInput consumer。
- DSX 不额外打开物理 HID，也不伪造电量。

## 7. 实现拓扑监视、切换和重连状态机

- 保持 `DualSense` I/O thread 为唯一 HID reader/writer；GUI、topology worker 和 XInput 不直接持有第二个物理 handle。
- 稳定连接期间每秒只做轻量 `hid.enumerate()`；新路径连续两次出现后才成为候选，feature report `0x09` 只在建立未知身份时读取一次并缓存。
- 同一物理手柄 USB 优先，BT -> USB 和 USB -> BT handover 始终自动；无法证明身份时不抢另一只手柄。
- 约 3 秒无有效输入即掉线并清除旧电量，不再让 HidHide 安装状态或关闭自动重连永久绕过 watchdog。
- handover 在 I/O thread 串行执行旧输出静音、handle 切换、首个有效输入等待和 trigger/rumble/visual 恢复，并通知 `HapticManager` 重选 USB/BT 路由。
- 测试关机、重开、候选抖动、多手柄、身份未知、并发重连命令和旧输出释放。

## 8. 配置迁移与真实重连入口

- 把新安装默认 `enable_reconnect` 改为 `True`；为旧偏好增加一次性 R7 migration marker，只强制该 global field，不触碰任何 Profile/驾驶参数。
- `SystemTab` 和 TUI 把现有设备分组改为“连接与重连”，保留只刷新列表的 Rescan，新增真正向 I/O thread 投递命令的“立即重新连接”。
- 自动重连关闭只禁止完全掉线后的周期重试，不禁止同一手柄 USB/BT handover。
- 覆盖新安装、旧配置迁移一次、迁移后用户关闭、恢复默认和命名 Profile 保留测试。

## 9. 更新顶部状态与总览呈现

- 顶部 Pill 只读取 controller snapshot，显示 phase、USB/BT、电量和充电状态；UDP bind 错误只留在总览遥测卡和日志。
- 把 Pill 拆成可独立着色片段：只有使用电池且为 10% 时电量文字红色，连接点保持绿色；断开立即清除旧 transport 和电量。
- 所有语言增加对应状态文案，最小窗口宽度下优先保留连接方式、电量、Profile 和版本，不裁切关键状态。
- `overview_status.controller_status()` 复用 snapshot，不从日志或持久化 handle 状态猜测。

## 10. 落地 Per-Monitor v2 和 DPI 诊断

- 为主 EXE 和 Helper 增加可提取的 Windows manifest，声明 `PerMonitorV2, PerMonitor` 与旧 fallback；runtime hook 在任何 Tk/CustomTkinter 窗口前完成 DPI bootstrap。
- 新增独立 DPI snapshot/observer，查询实际 process/thread/window awareness、window DPI 与 scale；manifest 已确定后的 access denied 记为正常诊断。
- 先用最小 probe 验证 CustomTkinter 5.2.2 `ScalingTracker`，再决定仅桥接通知还是接管更新，禁止 Windows bitmap stretch 和双重缩放。
- 原生 `tk.Listbox`、`tk.Text`、`tk.Scrollbar`、modal、wraplength 和 `_center_window()` 接入同一 observer。
- “系统与更新”和日志显示实际 DPI 模式与缩放；不是 PMv2 时只提示用户检查兼容性覆盖，不改注册表。

## 11. 构建契约、依赖与体积

- 固定 PyInstaller 和构建期依赖到已验证版本或仓库 lock，停止当前 `uvx --from "pyinstaller>=6.11.1"` 的任意最新解析。
- 为构建产物增加 manifest 提取、规范 EXE 名、内部版本、图标和 Helper manifest 契约测试。
- 以 R6 `51,814,190` 字节为基线记录 R7 精确大小、MiB、绝对和百分比变化；超过 `5 MiB` 或 `10%` 任一门槛立即暂停并请求确认。
- 保持 `.sha256` 与 EXE 同 Release；不把哈希描述成发布者签名。

## 12. 文档、完整验证和硬件验收

- 行为与架构落地后更新老三样：`AGENTS.md`、`docs/ARCHITECTURE.md`、`docs/DECISIONS.md`；实现进度、测试与未验证项同步 `docs/PROJECT_STATE.md`。
- README/Release 只在准备发布时更新；修改前先 fetch 并语义合并远端用户改动。Release body 继续使用完整中文与英文。
- 运行定向测试、完整 `uv run --project src pytest -q`、`python -m compileall -q src/modules src/lang`、`git diff --check` 和 `uv lock --check --project src`。
- 构建 R7 EXE/Helper，复核 sidecar、MZ、PE 版本资源、图标、manifest、冷/温启动、退出提示、更新恢复和快捷方式。
- 使用真实 DualSense 依次验证 BT、电量、BT -> USB、USB -> BT、关机、自动重连关闭、立即重连和触觉恢复；记录连接方式、Forza 游戏内振动与 Steam Input 状态。
- 未覆盖的 Windows 版本、混合 DPI 显示器、任务栏缓存、clean-machine 和硬件组合明确写“未执行”，不得写成已验证。

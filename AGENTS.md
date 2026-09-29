# Codex 项目工作指引

## 项目目标

FH-DualSense-Enhanced 读取 Forza Horizon Data Out 的 UDP 遥测，将车辆状态转换为 DualSense 自适应扳机、USB/Bluetooth 握把触觉与可选灯效，并以独立 Windows EXE 或源码方式运行。

## 技术栈

- Python `>=3.13`，依赖和运行环境由 `uv` 管理，锁文件为 `src/uv.lock`。
- GUI 使用 `CustomTkinter`，TUI 使用 `Textual`。
- 原生手柄输出使用 `hidapi`；USB 握把触觉使用 `sounddevice`、PortAudio 和 `NumPy`，Bluetooth 握把触觉使用同一 `NumPy` PCM renderer 和 HID report `0x36`。
- Windows Xbox App 输入桥使用项目自有 `ctypes` ABI 封装、固定哈希的 `ViGEmClient.dll` 和可选离线 ViGEmBus 安装器，目标设备为虚拟 Xbox 360 Controller。
- 系统托盘使用 `pystray` 和 `Pillow`，进程检测使用 `psutil`。
- 内置更新器使用 Python 标准库访问 GitHub Releases，并由独立 PyInstaller Helper、持久化事务 journal 和 Windows Shell Link 迁移完成版本化 EXE 更新。
- 测试使用 `pytest`，发布使用 ZUV、锁定为 `6.16.0` 的 PyInstaller 和 GitHub Actions；Windows 构建生成唯一的标准 `FH-DualSense-Enhanced-R<n>.exe`。

## 开始任务前

1. 阅读 `docs/PROJECT_STATE.md`，确认当前阶段、已知问题和未完成验证。
2. 涉及运行链路或模块边界时阅读 `docs/ARCHITECTURE.md`。
3. 涉及既有产品取舍或准备改变行为时阅读 `docs/DECISIONS.md`。
4. 阅读与任务直接相关的代码和测试，不要只依据 README 或旧设计文档。
5. 执行 `git status --short --branch`、`git diff` 和 `git log -10 --oneline`，保留用户已有改动。
6. 用户文档和发行信息以 `README.md`、`LICENSE`、`docs/THIRD_PARTY_NOTICES.md` 和 `.github/workflows/release.yml` 为准，但发现其与代码不一致时必须明确指出。

“老三样”固定指根目录 `AGENTS.md`、`docs/ARCHITECTURE.md` 和 `docs/DECISIONS.md`。行为边界、长期架构或关键产品决策改变时必须检查并同步这三个文件；当前阶段、测试、构建和工作树进度另行同步到 `docs/PROJECT_STATE.md`，不要把临时进度写入老三样。

## 核心入口

| 位置 | 职责 |
| --- | --- |
| `src/main.py`、`src/modules/runtime_logging.py`、`src/modules/diagnostics.py` | CLI、配置加载、GUI/TUI/headless 启动、崩溃日志、有界持久运行日志和本地诊断包入口 |
| `src/modules/loop.py` | 遥测热循环、Haptics Lab 预览仲裁、空闲静音、退出检测和输出去重 |
| `src/modules/forzahorizon/udp_listener.py` | UDP 监听、324 字节包解析和原始包转发 |
| `src/modules/forzahorizon/redline.py` | 保留原始 `max_rpm` 的动态断油转速预测、同挡位事件确认和按车辆学习 |
| `src/modules/forzahorizon/game_launch.py` | Windows FH4/FH5/FH6 定义、Steam 安装发现、Xbox AUMID 发现、精确运行进程检测和显式启动 |
| `src/modules/forzahorizon/fh6_language.py` | FH6 专属语言包内容识别、有效语言摘要、显式交换/还原和崩溃恢复 |
| `src/modules/forzahorizon/controller_icons.py` | FH6 DualSense 图标 MOD 的校验、双目标事务安装、独立原件备份与显式还原 |
| `src/modules/forzahorizon/effects.py` | Forza 专用 L2/R2 效果、优先级和跨帧状态 |
| `src/modules/forzahorizon/lighting.py` | 转速灯带、红线闪烁和挡位 Player LEDs 的传输无关状态 |
| `src/modules/haptics/` | 传输无关的握把混音、Haptics Lab 场景与 PCM renderer，以及 USB audio、Bluetooth HD haptics 和 compatible fallback 路由 |
| `src/modules/dualsense/` | DualSense 枚举、有效输入驱动的不可变状态、电量、USB/BT handover、HID 报告、Bluetooth `0x36` 封包、自适应扳机和重连 |
| `src/modules/xinput/` | DualSense 输入与自定义数字按键映射、ViGEm Xbox 360 target、卡键保护、driver 探测和平台生命周期 |
| `src/modules/update/`、`packaging/windows/update_helper.py` | Windows 独立 EXE 的 Release 查询、SHA-256 校验、事务 journal、健康确认、恢复、Helper 调度和 R6 legacy bootstrap |
| `src/modules/dpi.py`、`packaging/windows/fhds.manifest` | Windows Per-Monitor v2 启动声明、运行时 bootstrap 和实际 DPI 状态查询 |
| `src/modules/dsx/` | DSX UDP 适配，只负责自适应扳机 |
| `src/modules/config/` | 默认设置、偏好文件、Profile 和路径规则 |
| `src/modules/gui/`、`src/modules/tui/` | 两套交互界面，设置能力应保持一致；FH6 文件工具分别从 `fh6_utilities_tab.py` 进入 |
| `tests/` | 行为、HID 字节、触觉、配置、发布和文档契约测试 |
| `packaging/`、`.github/workflows/release.yml` | ZUV、Windows EXE、Linux ELF、SHA-256 sidecar 和 Release 构建 |

## 常用命令

以下命令均从仓库根目录执行，除非命令中显式进入 `src`。

安装或同步开发环境：

```powershell
cd src
uv sync
```

从源码启动默认 GUI：

```powershell
cd src
uv run main.py
```

其他启动方式：

```powershell
cd src
uv run main.py --tui
uv run main.py --headless --debug
```

完整测试：

```powershell
uv run --project src --frozen pytest -q
```

基础检查：

```powershell
git diff --check
uv run --project src --frozen ruff check src tests packaging .github
uv run --project src --frozen pyrefly check src
uv run --project src --frozen python -m compileall -q src/main.py src/modules src/lang tests packaging/windows/update_helper.py packaging/windows/shortcut_links.py packaging/windows/write_sha256.py packaging/windows/dpi_runtime_hook.py
uv lock --check --project src
git status --short --branch
git diff --name-only
```

构建本地 ZUV：

```powershell
packaging\zuv\build_zuv.bat
```

构建带本仓库更新源的 ZUV，需要在 `cmd.exe` 中执行：

```bat
set UPDATE_REPO=piereacy/FH-DualSense-Enhanced
packaging\zuv\build_zuv.bat
```

构建 Windows EXE（生成 `FH-DualSense-Enhanced-R<n>.exe`、配套 `.sha256` 和更新 Helper）：

```powershell
packaging\windows\build_exe.bat
```

构建 Linux ELF：

```bash
bash packaging/linux/build_elf.sh
```

## 修改原则和限制

- 所有可调参数集中在 `src/modules/config/settings.py`。新增系统级设置时同步更新 `preferences.GLOBAL_FIELDS`；车辆手感参数默认应保持 Profile 级。
- GUI 和 TUI 的同类设置必须同时更新，并补齐 `src/lang/` 中所有非英语语言目录的翻译或明确回退行为。扳机与握把页面的字段归属只在 `src/modules/feedback_schema.py` 声明；GUI/TUI 只能渲染该共享 schema，不得各自复制一份分组表。扳机开关、常用调节和实验参数只出现在 `Trigger feedback`，握把开关、常用调节和实验参数只出现在 `Grip haptics`。
- `enable_trigger_feedback` 是全部自适应扳机输出的 Profile 级总开关。关闭后下一帧必须同时发送 L2/R2 `off()`、清除换挡/ABS/抓地力/红线/碰撞等 transient 和两侧 wall latch，并禁止自动启动脉冲；各子开关和调节值原样保留，重新开启后继续生效。握把触觉属于独立输出，不受这个总开关代管；宣称“扳机完全关闭”时必须覆盖总开关、启动路径和 direct L2/R2 调用的回归测试。
- Enhanced R4 的涡轮增压阻力、G 力阻力、L2/R2 碰撞扳机冲击和 L2/R2 空闲路面纹理属于实验性扳机反馈。六个开关及全部参数必须只出现在 GUI/TUI 默认折叠的“实验性功能”中，并继续默认关闭；未经新的产品决定不得移回普通“驾驶反馈”页面。
- 调整 R2 扳机键基础油门阻力或 G 力阻力前，必须先做 Enhanced R3/Enhanced R4 受控 A/B：固定车辆、路段、Profile、连接方式和游戏设置，记录 Forza 游戏内振动、Steam Input、最终效果来源、trigger mode 与 force。当前代码审计表明基础油门 ramp 未被 G 力层替换；不得仅凭“开启 G 力后手感相似”就删除旧路径、默认开启实验功能或改写默认参数。
- `Brake stiffness` 同时拥有 L2 渐进阻力和通用 firmware end wall；`Throttle stiffness` 只拥有 R2 渐进阻力，R2 通用 wall 由默认关闭的 `enable_throttle_end_wall` 独立拥有。关闭任一 wall 的所有者时必须立即清除对应 latch，不能继续输出旧 `rigid_zones`；油门两项阻力数值为零不能暗改这个显式开关，开关开启时允许形成“前段自由、只在末端限位”的手感。静态刹车 wall、手刹附加阻力、实验性动态阻力和各类震动仍由各自独立开关控制。修改这条所有权边界时必须覆盖满输入、运行中关闭开关、零阻力与独立 wall、抓地力不受 wall 开关代管的回归测试。
- 总览状态必须来自线程安全的运行时快照或现有不可变快照，并由 GUI 主线程定时渲染；不得从日志文本反推状态，也不得只在控件创建时写占位值。UDP 状态只统计 324 字节有效包，错误主文案保持简短，详细原因放在提示或日志。
- FH6“中文文字 + 英文语音”支持 Windows Steam 与 Xbox App 版并且必须保持按钮式。Steam 路径自动枚举并读取 manifest；Xbox App 自动发现只能通过 Win32 枚举本地 fixed/removable drive，读取每盘不超过 4096 字节的 `.GamingRoot` 并兼容默认 `XboxGames`，只检查库根、标准游戏名和最多 512 个直属子目录。不得扫描网络盘、`WindowsApps`、全盘或递归子目录，也不得跟随链接跳出游戏库。发现结果必须通过对应代的精确 EXE 和功能资源验证；FH6 成功路径保存到 `fh6_xbox_install_path`。手动选择仍是 fallback，可以是 payload 根目录或其直接父目录 `Content`，并必须以新 serial 抢占后台扫描；验证失败必须给用户可见反馈。自动启动、页面刷新和路径发现只能读取，不得自动交换、还原、修复或删除语言包。生产代码不得硬编码盘符或 `Program Files`，必须验证 `ForzaHorizon6.exe`、`media/Stripped/StringTables`、ZIP 内容和游戏未运行。Steam manifest 明确不是 English 时禁止启用；Xbox App 或手动路径无法证明游戏语言时，三行状态必须显示未知且操作要求额外确认。任何改名都使用同目录临时名、逐步前置检查和失败回滚；崩溃残留只能在用户再次确认后修复。
- `FH6Install.steam_language` 表示 Steam 为 FH6 记录的游戏内容语言，不是 Steam 客户端界面语言。三行“当前 FH6 游戏使用语言 / 实际显示语言 / 语音语言”必须通过 `summarize_fh6_languages()` 和 `language_summary_view()` 共用推导与本地化；不得在 GUI/TUI 中分别猜测，也不得把 Xbox App、未知或损坏状态推断为某种有效语言。
- 总览 Forza Horizon 启动入口必须保持用户点击触发，并同时考虑 Windows Steam/Xbox App 的 FH4、FH5、FH6。左侧按钮只启动当前选择，右侧菜单只选择不启动；首次默认 FH6，之后持久化最后选择。Steam 启动交给三代固定 `steam://run/<app-id>`；Xbox App 启动先用 `Get-StartApps` 动态发现带 `!` 的 AUMID 并交给 `shell:AppsFolder`，未发现时才打开固定产品 ID 的 `msxbox://game/` 页面。不得直启 EXE、静默提权、自动启动或借启动动作修改语言包。Steam 安装发现、Xbox AUMID 查询与精确进程检查放在后台，异步结果必须携带游戏键和序号，Tk 控件只由 GUI 主线程更新。
- 总览 Steam 安装发现只扫描当前选择的游戏。找到并验证路径后停止周期发现；未找到时每 30 秒静默重试，路径设置变化或显式启动验证失败才使缓存失效。首轮结果之后的后台重试不得把按钮重新显示为“正在查找”。启动按钮、游戏/平台选择器和 XInput action 只在 presentation tuple 变化时重绘，不得每秒无条件 `configure()` 或 `grid_forget()`/`grid()`。
- 今后修改游戏启动、安装发现、进程检测、游戏关闭联动、更新说明或相关用户文案时，必须同时检查 FH4、FH5、FH6；只有明确标记为单代专属的功能可以例外。FH6“中文文字 + 英文语音”和对应模组提醒仍是 FH6 专属，不得为了统一命名扩展到 FH4/FH5。
- UDP 热路径必须继续使用 `UDPListener.recv_latest()` 丢弃积压包，不能改为逐包处理旧遥测。首包等待后每轮最多 non-blocking drain 64 个 datagram，持续灌包也必须返回；同端口的相同地址、wildcard/localhost 和完整 `127/8` 明显自转发必须在 listener 构造时拒绝，不能形成自回灌饥饿。
- 动态红线只允许生成派生的 `effective_redline_rpm`、已确认的 `rev_limiter_active` 和共享 `redline_alert_allowed` gate，不得覆盖 Forza 原始 `max_rpm`。R2 扳机键、握把红线与转速灯条必须消费同一估计器和同一 alert gate；gate 开启时已确认断油必须能立即强制灯条闪烁，发动机基础频率和其他未明确迁移的 RPM 效果继续使用原始仪表范围。只要 `num_cylinders == 0`，R2 与握把就不得输出任何红线触觉，当前挡位或已观察到的总挡位不能重新开启，确认的 limiter 也不能绕过；灯条仍显示 RPM 渐变并在接近极限时保持稳定红色，但不得进行换挡式闪烁。缺少气缸字段时保持旧行为。断油学习必须保持同挡位延迟确认，并排除离合、换挡和严重打滑，不能退回仅凭一次 `power == 0` 立即锁定。已确认燃油车允许在预测窗口之外冷启动学习，但必须同时出现功率与扭矩塌陷，并由相近 RPM 的重复事件聚类：第一次只收集候选，第二次才允许短暂 limiter 事件，第三次才建立学习值；分散在不同 RPM 的事件不得合并。当前默认 `0.95` 等比例只能是相对已学习红线的可调提前量，不能再限制真实断油能否被发现；电驱和缺少气缸字段的旧映射不得进入这条宽范围冷启动路径。
- R8 红线时机升级仍只处理历史 `Default` 中完整等于 R7 旧值的四项，并在 R11 默认迁移前完成；R11 会把处理后的旧 `Default` 完整保存在 `Default before R11`。R11 新 `Default` 的握把进入/退出和灯条闪烁比例均为 `0.88`，运行时 fallback、Settings、fixture、GUI/TUI slider 和 Release 说明必须与该契约一致。命名 Profile 不参与 R11 默认替换。
- `src/modules/loop.py` 只在 `(left, right, rumble, visual)` 状态改变时调用普通手柄状态输出；USB 和 Bluetooth HD haptics 目标仍需要逐遥测帧更新，并由各自的音频周期持续渲染。
- Haptics Lab 只能作为 GUI/TUI“系统与更新”页内默认折叠的小卡片存在，不得恢复独立左侧导航或 TUI 顶层标签。Lab 只能发布有界、不可变的预览请求，`src/modules/loop.py` 仍是唯一手柄输出所有者。预览只在物理/DSX backend 已连接时执行；任一有效游戏遥测包必须抢占 Lab，控制器断连、折叠卡片、离开系统页、窗口失焦、显式停止、到期、重启或退出也必须立即释放。强度限制为 `10%..65%`，持续时间限制为 `0.25..3.0` 秒。Lab 不得创建第二个 HID reader、虚拟 X360、Raw Input 或 HidHide session，也不得向游戏转发输入。显式握把预览可以临时绕过 Profile 的 body haptics 开关，但不能持久化该开关；DSX 只允许扳机场景。
- 一键诊断包只能从既有不可变快照、只读计数器和有界日志副本收集数据。允许记录运行模式、传输、连接、UDP、HID/DSX、USB/Bluetooth 触觉、XInput/HidHide 和 Lab 状态；不得打包 preferences/Profile 原文、原始 HID/UDP payload 或稳定的控制器标识。快照中的 identity/device path 与错误文本，以及日志中的 Windows HID interface path、HidHide instance ID、Linux hidraw/input path、MAC 形态标识和带敏感标签的值，都必须替换为短 SHA-256 指纹；普通本地文件路径或其他错误文本仍可能存在，包内必须提醒分享前检查。导出目标固定在本地 `data/diagnostics/`，不得上传或自动发送。
- Body haptics 关闭时不得占用 compatible rumble flags 或 motor bytes。Bluetooth fallback 的 rumble 释放帧不能被后续 trigger-only 帧吞掉；HD haptics 停止或断开前必须排队或写入全零 `0x36` 采样块。短暂 Bluetooth 输入空档不得把当前连接永久降级为 compatible rumble；`0x36` 在真实构建、队列或 HID write 失败时才允许回退，完全失去有效输入仍由约 3 秒 HID watchdog 断开并重连。
- USB 握把触觉流仍保持 Enhanced R6 的 `_running`、GUI/TUI eligibility sync 和 headless transport-epoch 失败闩锁语义。GUI/TUI 共享 stream 的 `start()/stop()` 只能由 `UsbAudioLifecycle` 拥有；telemetry `HapticManager` 在 pause/close 时只写 `SILENT_FRAME`，不能停止外部 stream。backend、transport、设置或 Lab preview 的 eligibility 变化必须把 sync 投递到各自 UI 主线程，周期 1 秒 sync 继续作为恢复重试。`sounddevice`/PortAudio 只能在真正启动 USB stream 时延迟导入；Bluetooth 阶段不得提前导入并冻结没有 USB endpoint 的设备快照。不得重新加入 sounddevice 私有 `_terminate()`/`_initialize()`、callback 心跳判活、额外 lifecycle lock 或定时 backoff，除非先完成 R6/R7 USB 冷启动与 BT → USB 实机 A/B，并证明不会造成全零 PCM、跨进程污染或旧版回归。
- 普通 USB/BT HID 状态报告必须保持 Enhanced R6 的字段所有权契约：L2/R2 扳机键字段按既有路径声明，只有显式 compatible rumble 才声明并写入 motor 字段，visual 只声明自身字段。`HapticManager`、PortAudio lifecycle 和 transport handover 不得请求或猜测额外的 HID 音频模式；尤其不得把 `valid_flag0 0x20` 当成 haptics select，也不得加入未经协议和实机共同验证的单次 `0x01` 重置。修改该边界必须同时做 R6 字节对照、退出新版后重启旧版的无污染验证和 USB/Bluetooth 实机测试。
- 不要随意修改 324 字节遥测偏移、USB/BT HID offset、BT CRC、trigger mode byte 和左右扳机映射。`0x36` 固定为 398 字节、3 kHz、每包 32 帧交错左右 int8；修改时必须增加字节级和调度测试。
- Linux `_hidraw` 适配层调用 hidraw wrapper 时必须使用其公开参数名 `timeout_ms`，不能把 PyPI `hidapi` 的 `timeout` 关键字照搬过去；Windows 测试不能替代 Linux hidraw 回归测试。
- 等待期 Windows Bluetooth 被动状态不能只凭 Configuration Manager 的 BTHENUM present 节点显示 `AVAILABLE`：paired/remembered 节点在手柄关机后仍可 present，必须同时通过 Classic Bluetooth API connected-only 查询；USB present 节点才可直接计数。这两条查询都不得打开 HID handle。
- Bluetooth HD haptics 不依赖 vDS daemon、虚拟 USB、USB/IP、HidHide、test signing 或 Opus。`src/modules/dualsense/bt_haptics.py` 只发送本项目合成的 haptics block，不得宣称已经接管游戏原生振动。当前封包已复核到 vDS `0.4.0-rc1`；该版 Windows 架构迁移与麦克风静音灯修复不改变本项目使用的 `0x36` haptics builder，也不得据此引入 vDS 运行时组件。
- R11 生产路径不得包含 Windows FH4/FH5/FH6 前台窗口 detector、physical ownership gate、Configuration Manager 被动等待检测、`WAITING_GAME`、runtime tick 或延迟启动脉冲。native backend 随应用启动/热切换正常打开，应用运行期间可枚举并持有选定的实体 DualSense；切到桌面或其他游戏不会触发释放。Xbox App direct-HID 模式在 backend 生命周期内挂 input consumer、启动 Raw Input、bridge、虚拟 X360 与用户显式开启且默认关闭的 HidHide session；Steam 模式不创建本项目虚拟设备，DSX 仍不持有实体 HID。新前台实验源码只允许保存在 `experiments/foreground_ownership/`，不得由 `src`、生产测试、PyInstaller spec 或 Release workflow 导入/收集；当前 PR 与 R11 发布不再准备或宣传旧 R10 监听备用包。HID 输入队列继续优先 drain 到最新状态；连续 Bluetooth `0x36` pending 不得退化为每轮一条，也不得回放旧输入。100 ms 无新输入时虚拟 X360 发送一次中立状态但保留 target/player slot；切回 Steam、停止应用或重建失败会话时才移除。ViGEm 瞬时异常按 0.25/1/5 秒有界退避自动重建；当前不注册 ViGEm rumble callback，虚拟目标固定为 Xbox 360，不加入 Xbox One/Xbox Series 或 Share 系统键模拟，真实游戏与硬件结论必须由实机验收。
- Xbox App bridge 的键鼠热切换只监听 Windows Raw Input 中注册的 Generic Desktop mouse/keyboard，不得用 `GetLastInputInfo`、光标位置或物理 DualSense 的连续 HID report 猜测所有权。检测到键鼠事件后只把本项目的虚拟 X360 target 发送一次中立状态并保留 player slot；D-pad、数字键、触摸板点击或越过去抖阈值的摇杆/扳机变化才恢复 controller owner。Raw Input 隐藏窗口随 direct-HID Xbox bridge 启停；切回 Steam/DSX、安装 driver、重试或退出时必须注销 mouse/keyboard device class。启动超时必须设置该轮独立取消信号，在旧 listener 真正退出前保留引用并禁止创建第二条；慢启动晚返回也不能留下无 owner 的 message pump。同一进程未来若有其他 Raw Input 注册者必须先协调唯一注册所有权。监听失败必须 fail open，不能阻断手柄转发。该功能自身不隐藏物理 DualSense；完整隔离由独立且显式的 HidHide 层承担，两层状态和故障边界不得混写。
- R12 Xbox 输入保留 HID 批次中有效的数字按键与方向键边沿，并继续合并连续模拟轴报告；bridge 仅为数字变化使用有界队列、短暂最小按键保持时间和 100 ms 过期丢弃，不能退回无界回放蓝牙积压。键鼠恢复基线取虚拟 target 此前实际输出的手柄状态，只在 controller 转到 keyboard/mouse 时建立；与键鼠事件同轮到达的首次按下必须有机会立即接管。Steam 不使用该 XInput consumer。真实游戏内是否解决 ABXY 连按两次仍需实体 DualSense 蓝牙实测。
- Raw Input 取得 keyboard/mouse owner 时只建立一次手柄恢复基线；后续重复鼠标事件不得把基线覆盖成最新手柄报告，否则持续鼠标活动会使 Xbox App 模式的手柄无法重新接管。用户确认的目标现象是鼠标能动、手柄无法操作，必须在真实游戏中核实修复。
- Xbox 360 XInput 按键映射在自定义开关关闭时必须保持 Steam PS5 Gamepad 模板的位置语义：Create 映射 Back/View，Options 映射 Start/Menu，PS 映射 Guide；触摸板点击按有效触点横坐标拆成左右半区，左半映射 Back/View，右半映射 Start/Menu，同时存在左右触点时发送两键，无有效触点的异常点击帧回退 Back/View。自定义映射只属于 Xbox App bridge 的 global 设置，必须由 GUI/TUI 同一份 `xinput.mapping` schema 渲染、默认关闭、严格回退非法 target，并在不销毁 X360 target/player slot 的情况下热更新；GUI 左侧导航与 TUI 顶层标签必须把它作为独立页面直接展示，禁止重新塞入 System 页或默认折叠的子界面。只有 `preferred_forza_platform == xbox_app` 时才允许启用、编辑或恢复映射；Steam 模式必须锁定全部编辑控件但保留已存值，并明确告知 Steam 用户应在 Steam 内自行修改映射，切回 Xbox App 后再恢复编辑。只允许重映射数字按键或禁用单一来源，摇杆和 L2/R2 模拟量不得进入该层。触摸板坐标只用于这次点击分区，不得进一步解释滑动或多点手势；USB 与 Bluetooth 必须共享同一解析和映射回归。
- Xbox App bridge 的体感映射必须明确承认虚拟 X360 target 没有原生陀螺仪通道：只允许把 DualSense 校准后的 gyro/accelerometer 转换为左或右摇杆的叠加量并最终 clamp，不能宣称游戏收到原生 sensor。Steam Input 同名兼容面包括 Camera（角速度直接映射）和 Deflection（积分姿态并用重力方向缓慢校正）两种模式、Yaw/Roll/Yaw+Roll、垂直输出、反转、死区、平滑以及 Always/L1/R1/L2/R2/触摸板触摸激活。`enable_custom_xinput_mapping` 是数字映射和体感的总开关，`enable_xinput_gyro` 是其下默认关闭的独立子开关；任一开关关闭都必须向 bridge 热发布 Off 并立即归零体感，不能只禁用 UI。feature report `0x05` 只能由 active runtime 的唯一 HID owner 在 open 后读取，失败必须整组回退 nominal calibration 而不能阻断连接；USB/BT common report 的 gyro、accelerometer 与 sensor timestamp 必须共享解析。键鼠取得 input owner 后，只有越过 gyro reclaim 阈值的体感动作才能恢复手柄输出，静态漂移不能抢回所有权。GUI/TUI 必须共用 `xinput.gyro` schema、global persistence、严格范围归一化与热更新，Steam 平台继续锁定该页并交给 Steam Input 自身配置。
- GUI 只保留一个正式壳层。现有青绿色视觉源自内部 Miku Console 设计理念，但该名称只允许在老三样中记录设计来源，不得出现在窗口标题、页面文案、翻译、构建资产、README、Release 或其他当前文档中。主题颜色集中在 `src/modules/gui/theme.py`，页面和后端不得按构建产物分叉；不要恢复 Stage、Studio、`FHDS_UI_VARIANT`、`FHDS_BUILD_VARIANT` 或 `data/ui_variant.txt`。
- GUI tab frame 必须在创建后只 `grid()` 挂载一次，由 `TriggerGUI._select_nav()` 使用 `tkraise()` 和可选 `on_show()`/`on_hide()` 切换；不得恢复每次导航 `pack_forget()` 后重新 `pack()` 的布局方式。页面隐藏时应暂停只属于该页面的周期发现和 `FastScroll` canvas 尺寸回流，后台结果继续通过 serial 和主线程边界丢弃过期状态；可见页 resize 必须合并后再应用，不能让最大化事件对所有隐藏长页重复布局。响应式反馈卡片只在列数变化时重新 `grid()`，不得先 `grid_forget()`；扳机页双列时总开关与共享反馈各占整行，L2/R2 成对占两列，避免由行高对齐制造大块空白。卡片说明不得使用宽于卡片的固定 `wraplength`；必须把 Tk configure 事件的物理像素按 CustomTkinter widget scaling 换回 logical px，再以卡片实际内宽换行，并让多行标签按请求高度增长。更新卡片等周期 UI 只在 presentation tuple 变化时修改控件或显隐状态。
- 产品图标只维护 `src/data/icon.png` 和 `src/data/icon.ico` 这一组源资产，窗口、托盘、Windows 主 EXE、更新 Helper 和 Linux 包必须复用它们。ICO 保持 16、24、32、48、64、128、256 七档；替换图标时同步更新图标哈希契约测试并验证最终 PE 提取图标，不得只更换源码窗口或只更换打包图标。
- 长页面使用 `widgets.FastScroll` 注册到根窗口 `WheelRouter`。不要重新覆盖 CustomTkinter 私有 `_mouse_wheel_all`，也不要让滚轮修改 slider；嵌套滚动必须在内层到达边界后才转交外层。顶部 Profile/控制器状态框保持 `28` logical px 高、`8` logical px 圆角，间距使用 4 的倍数，并缓存 presentation 值，避免相同状态每秒重复 `configure()`。
- 内置自更新只允许冻结后的 Windows 独立 EXE。必须保留稳定 `R<n>` tag、规范资产 `FH-DualSense-Enhanced-R<n>.exe`、配套 `.sha256`、MZ 头检查、`.part` 下载、独立 Helper、持久化 transaction journal、随机 token 健康确认和启动恢复；源码、Linux 和 ZUV 运行不得尝试覆盖可执行文件。检测到新版本后，GUI/TUI 除 Release 页面入口外还必须显示“或手动下载：URL”并直接指向已筛选的规范 EXE asset，不能指向未经筛选的任意附件。R7 以后的正常更新必须把新版按规范文件名并排安装，健康确认和快捷方式迁移完成前保留旧版，不创建 `.old`；`.old` 只允许用于准确识别的旧覆盖式 Helper 兼容引导，并必须由第二阶段消费。legacy 检测不能要求文件名版本与 `.old` PE 版本相等：连续旧式更新可能形成 `R5.exe` 内置 R7、`R5.exe.old` 内置 R6；必须验证运行 PE 等于当前版本、备份 PE 不低于文件名版本且低于当前版本，再由 transaction 哈希绑定两份字节。同目录实例保护必须把当前 PyInstaller one-file 内层应用进程与其“同一已解析 EXE 路径”的直接外层 bootloader 父进程视为一个实例，只排除这一对；另一次独立启动形成的外层/内层进程对仍必须阻止更新，并同时保留两类回归测试。每个 journal 必须由跨进程锁串行化 apply/recover；主程序不得与 Helper 直接竞争写 phase。失败回滚只能删除本次已接管且 SHA-256 仍匹配的新版，必须停止自己启动的完整 one-file 进程树并验证真实旧版可用后才能写 `rolled_back`；删除、进程停止或 legacy 恢复任一步失败时保留非终态 journal，禁止虚假回滚。中断恢复收到 ACK 后也必须重新验证 PID/EXE 并观察约 3 秒。健康提交后，Helper 应迁移同目录全部严格命名且版本低于新版的规范 EXE 快捷方式，再静默删除这些旧 EXE 及同名 `.old`、`.sha256`；不得扩展为通配删除任意 EXE/`.old`。快捷方式只能按规范化后的旧 EXE 绝对目标精确匹配，部分迁移失败时只保留被失败链接引用的真实旧版 EXE。发布 sidecar 必须由 `packaging/windows/write_sha256.py` 生成并在上传前以 `--check` 复核，不得重新依赖 `Get-FileHash`、`certutil` 或本地化系统输出。
- 引入或内嵌第三方运行库、驱动安装器、Mod、模型、媒体包或其他二进制资产前，必须以最新稳定 GitHub Release 的 Windows EXE 为基线，记录资产的准确版本、原始字节数、预计成品大小、绝对增量和百分比；实现后再用真实构建复测。预计或实测增量只要超过 `5 MiB` 或 `10%` 任一门槛，必须在继续合入或发布前取得用户明确确认，并优先评估按需下载、可选 sidecar 或裁剪资产。不得只用源码目录大小代替最终 one-file EXE 体积。
- FH6 DualSense 图标 MOD 只允许由用户显式安装或还原。内置 `ControllerIcons.zip` 必须先校验固定 SHA-256，再同时写入普通与 HiRes 两个目标；两份原始文件按安装根目录独立备份到应用数据目录，部分状态必须修复或拒绝，不能静默覆盖失效备份。GUI/TUI、三语 README、关于页与 `docs/THIRD_PARTY_NOTICES.md` 必须保留可点击的 Nexus 来源和作者 `@hotline1337` 鸣谢；Release 正文不重复该鸣谢。不得把用户陈述的单次许可扩写为通用许可证。
- FH6“中文文字 + 英文语音”和 DualSense 图标 MOD 只出现在 GUI/TUI 的独立 `FH6 utilities` 页面，`SystemTab` 不得保留卡片、worker 或隐藏入口。该页首次显示、路径变化和显式操作后检查；未找到路径时仅在页面可见期间每 30 秒静默重试，找到后停止路径发现。轻量 FH6 进程检测可继续用于禁用文件写入，但不得重新引入五秒文件扫描。
- Native DualSense 的“已连接”只能由 active runtime 内完整且有效的 USB/BT 输入报告建立和刷新，不能由 HID handle、PnP 被动记录、hidapi 枚举项、HidHide 或重连开关推断；gate 关闭时 `AVAILABLE` 只表示系统设备树可见，不代表 FHDS 持有连接。所有 open/read/write/reconnect/handover/close 继续由单一 I/O thread 串行执行；意外异常由同一个 worker 以 0.25/1/5 秒有界退避恢复，手动“立即重新连接”在 worker 已死亡时必须先重启它，不能创建第二个物理 HID owner。active runtime 内约 3 秒无有效输入必须清除旧 transport 和电量。没有 XInput consumer 时，空闲输入积压按批丢弃且 pending trigger/haptics 输出优先；Xbox bridge 启用时则先把输入积压收敛到最新状态，再处理已被单槽合并的输出。USB/BT 自动 handover 只允许同一身份，稳定候选需要连续两次拓扑观察且 USB 优先；候选 handle 必须先打开并读到有效输入。启用 body haptics 的 BT → USB 必须先非阻塞等待至少 3 秒，再以只读 Windows MMDevices registry probe 确认活动的 DualSense USB render endpoint；等待和失败期间继续保持 Bluetooth transport、输入、L2/R2 扳机键与 `0x36` 握把触觉，endpoint 未就绪或探测异常时按既有 1/2/5 秒退避，且重试不重复 3 秒 settle。只有 readiness 通过后才允许静音旧输出、发送经过 `0x53` seed CRC 保护的 48-byte feature report `0x08 / 0x02` 并提交 USB；body haptics 关闭时绕过 endpoint 条件。该命令不得用于冷启动、USB → BT、普通 reconnect、DSX 或 XInput，也不得绕过真实硬件验收；handover 不得播放启动扳机脉冲，完全掉线后的周期重试才受 `enable_reconnect` 控制。
- Windows USB 握把触觉在 `UsbAudioHaptics.start()` 才延迟导入 sounddevice，并从当时初始化的 WASAPI snapshot 选择首个名称匹配且至少四声道的端点，以 48 kHz、4 channel、float32、blocksize 512 开流；`running` 使用 Enhanced R6 的 `_running` 状态。FH4/FH5/FH6 runtime gate 未打开时，GUI/TUI lifecycle 不得启动或维持该 stream，headless manager 也不得路由等待期 telemetry。endpoint readiness probe 不得导入 sounddevice、初始化 PortAudio 或打开 stream；它只为 BT → USB 判断系统 render endpoint 是否已可见。R7 的 HID/topology handover 可以切换 transport，但不得据此宣称 USB audio hot-switch 已通过；每次修改这条边界都必须分别验证 USB 冷启动、Bluetooth 冷启动、BT → USB → BT、退出新版后 R6 仍可用，并记录游戏内振动与 Steam Input。
- Steam 模式默认不启用 HidHide；选择 Xbox App 时必须把隔离设置为开启，旧版 Xbox App 的关闭配置在读取时迁移。冻结后的 Windows 独立 EXE 只有在 direct-HID、Xbox App 且实际虚拟 X360 target 已连接时才可隐藏实体手柄；仅探测到兼容 ViGEmBus 不能隐藏。选择 Xbox App 后，当前 EXE 的 application allowlist 必须先于原生 HID worker 打开手柄建立，以打破已有隐藏规则导致的枚举与虚拟 target 相互等待；这一准备阶段不得新增 device rule 或切换全局 `Active`。HidHide 1.5 GET 列表的零填充可忽略，但非零尾部与内部空项必须拒绝。用户在 GUI/TUI 点击安装按钮后，才可按需下载固定官方 HidHide 1.5.230 安装器，严格校验原始字节数、SHA-256 与 Authenticode，再由 UAC 显式提权安装；不捆绑或静默更新已有驱动，不调用 HidHide CLI。安装可能要求重启。HidHide 1.7+ 的物理设备只进入调用进程拥有、退出后自动清理的 session blacklist。官方 HidHide 1.5 不支持 session IOCTL，FHDS 仅可针对当前物理 DualSense 和当前 EXE 自动添加自己的持久 device/application 规则，添加前把所有权写入原子 journal，正常退出或切到 Steam/DSX 时清理，异常退出后下次启动即使未选 Xbox 也要恢复；用户原有规则不得删除。全局 `Active` 原先关闭时，只有隐藏列表为空或全部是已知 DualSense/Edge 规则才可由 FHDS 在实际虚拟 target 建立后开启；含其他设备规则时必须拒绝自动开启。所有权 journal 需记录开启前的规则快照；清理 FHDS 自有规则后若列表仍与快照一致，则恢复原来的关闭状态，若用户在运行期间修改了列表则保留开启。inverse 模式必须拒绝自动改写。实际 target 丢失、安装/重试 ViGEm、切回 Steam/DSX 和退出时必须先解除 observer，再清理 FHDS 自己拥有的隔离规则；仍启用开关时可保留自己拥有的 application allowlist 供下次启动使用。HidHide 失败不能关闭实体 direct HID 读取或绕过有效输入 watchdog，但虚拟 X360 在隔离确认前必须只发送中立输入；已经打开物理 handle 的游戏可能需要重启后才受过滤。Xbox App 内鼠标与手柄来回切换的最终修复状态必须由真实游戏、实体 DualSense、ViGEmBus 和 HidHide 联动验收，自动测试与构建不能替代。
- HidHide 安装与隔离状态须分别展示。安装状态以驱动控制设备和 Windows 服务注册判断，不以官方配置客户端路径推断；只有实际缺失驱动才显示安装操作。GUI 在总览快速入口放置安装、打开官方客户端、隔离状态和 Xbox 必需条件提示，不在系统页保留该卡片；TUI 在系统页保留安装与状态但不得提供关闭 Xbox 隔离的开关。四个 GUI 快捷导航按钮使用同一中性样式；应用内 Xbox 游戏启动在实际实体隐藏规则确认前禁用，发出启动请求前再次读取驱动。GUI 安装线程只通过线程安全队列把阶段和结果交给 UI 主线程；下载按已接收/固定校验字节数显示百分比，签名验证、UAC 和安装器等待使用不定进度，不伪造安装百分比。安装等待必须有界，结果丢失或线程异常不能让“正在安装/UAC”永久保留。GUI/TUI 在检测到官方 Configuration Client 后提供打开入口，入口不自行修改用户在官方界面中的规则。
- 官方 HidHide Configuration Client 可能占用 control device 并使 FHDS 收到 Windows 错误 5；此时要准确提示关闭客户端，并在 Xbox App direct-HID 隔离仍开启时以单一有界定时器重试 application allowlist 或物理隔离。重试不能提前隐藏实体设备，Steam/DSX、backend 重建、安装 ViGEm 和退出时必须取消；关闭官方配置窗口后无需用户手动拨动隔离开关。
- Windows GUI 必须在 Tk/CustomTkinter 创建任何窗口前完成 Per-Monitor v2 bootstrap，并在主 EXE 与 Helper manifest 中声明 `PerMonitorV2, PerMonitor`。界面和日志显示的是查询到的实际 awareness 与窗口缩放，不得用迟到的 DPI API、Windows bitmap stretch 或重复缩放掩盖问题。
- DSX 是无 ACK 的 UDP 后端，`connected` 只表示 socket 已打开。当前 DSX 不提供握把触觉。
- R11 只允许由 `r11_default_profile_from_33` marker 控制一次默认迁移：已有 `Default` 先完整保存为内置 `Default before R11`，再安装 R11 新 `Default`；当前命名 Profile 和 active 选择不得改写。marker 完成后 `Default` 继续自动保存并跨重启保留，启动时不得再次覆盖。内置顺序固定为 `Default`、`Default before R11`、`Original`，三者不可删除或改名。恢复出厂设置必须重建这三份内置 Profile 和 global fields、重新检测系统显示语言、切回 `Default`、保留其他命名 Profile，并在写入成功前保留 `.bak`。外部 JSON 和分享码必须做类型、有限数、嵌套形状与解压大小校验；Profile 名称须去除控制字符并限制长度，UI 显示动态名称时还要转义 Rich markup。
- GUI 与 TUI 的窗口退出、托盘退出、游戏关闭、遥测超时和更新重启必须走各自统一退出入口；本会话改过 `Default` 的 Profile 字段时才能提示另存命名 Profile，纯 global 变更和当前命名 Profile 不提示。更新 Helper 只能在该提示完成后调度。
- 更新健康 ACK 只能在所选运行模式达到最低可用边界后写入：headless 要完成 backend、可选 XInput 与 UDP 初始化，GUI/TUI 要完成相同 backend、listener 和 telemetry worker 启动。构造窗口成功不等于健康，初始化失败必须让 Helper 回滚。
- 主程序只读取进程环境，不从当前工作目录隐式加载 `dev.env` 或其他 dotenv 文件，避免快捷方式工作目录改变运行配置；开发环境变量由启动 shell、IDE 或测试显式注入。
- 修改 Profile 默认值时必须同步 `tests/fixtures/community_defaults.json`、`tests/test_community_defaults.py`、README 和 Release 正文；除非迁移设计明确要求，不得覆盖命名 Profile 中已经显式保存的值。
- GitHub 根 `README.md` 固定为精简的英文用户指南，简体中文与日语分别位于 `docs/ReadmeZH.md`、`docs/ReadmeJA.md`；不要恢复三语同页或 `docs/ReadmeEN.md`。三份页面只保留核心功能、下载、必需游戏设置、连接说明、常见故障和许可证，不要加入小设置、内部算法或开发构建手册。README 不使用内部界面代号，但该限制不代表删除现有青绿色视觉设计。必需设置必须写明 Forza 游戏内振动关闭；Steam 模式写明 Steam Input 开启，Xbox App 模式写明使用内置 XInput bridge 且不需要 DS4Windows/Steam Input。
- 提交或推送本地更新前必须先获取并审阅远端分支。若用户已直接在 GitHub 修改并提交任何 README，本地更新必须以远端改动为合并输入，逐段理解并保留用户修改，再把本地需要的内容语义合并进去；不得用本地旧版 README 整文件覆盖远端，不得无视远端差异，也不得在冲突处理中机械选择本地版本。
- 三语 README 必须用四到六个用户可感知类别，明确说明当前 Enhanced 版本相比 `Forza-Horizon-DualSense-Python 1.6.2` 的累计核心增强。该清单只能依据当前生产代码、自动测试或已记录的真实硬件结果，不得混入内部参数、逐项开关、仅设计或推测能力。GitHub Release body 另行说明当前版本相比上一稳定 Enhanced 版本的增量，不能把两种比较口径混写。
- GitHub Release body 是给最终用户阅读的增量更新日志，只保留用户能感知的修复、升级影响、兼容提醒、安装方式和必需设置。不得展开内部字段名、状态机、HID 字节、动态学习链路、PE 版本顺序、transaction 哈希或第三方实现架构；这些实现依据必须同步记录在老三样，第三方版本与许可证写入 `docs/THIRD_PARTY_NOTICES.md`。发布契约测试应同时约束必要用户事实存在和内部术语不回流。首次携带更新入口修复的版本必须明确告诉受影响旧版用户手动安装一次，并把自动改名、清理和恢复承诺限定为修复版之后的更新；不得把隔离的 R9 → R10 成功矩阵改写成 R8 → R9 可以自动成功。
- 当前版本用户文案不得提及已经删除的功能。已经取消、撤下或仅保存在 `experiments/` 的方案也不得出现在 README、Release body、更新入口或其他面向用户的当前版本说明中，不能用“本版不包含”“不再提供”或与现有行为对比的方式反向提及；只正面说明当前生产版本实际可用的行为。历史原因和移除依据仅保留在老三样与 Git 历史。
- GitHub 仓库当前是独立仓库，不再属于 fork network；保留完整 Git 历史，不要重新建立基于 fork 身份的发布假设。“关于与许可证”必须同时提供本项目仓库 `https://github.com/piereacy/FH-DualSense-Enhanced`、`LICENSE` 要求的署名、原项目链接、Sponsor 链接，以及指向 `https://space.bilibili.com/471461948?spm_id_from=333.337.0.0` 的“调教鸣谢：Bilibili 开心散仙”；独立状态不改变 `docs/THIRD_PARTY_NOTICES.md` 中的 HorizonHaptics 归属。
- 不要把尚未通过测试或实机验证的行为写成已验证或已发布。以生产代码、自动测试和硬件记录分别标注事实层级。
- 术语必须消除歧义：版本阶段写 `Enhanced R<n>`，手柄右扳机写 `R2 扳机键`；不要单独写无法判断含义的 `R2`。
- 每个 GitHub Release body 必须同时包含对应版本的完整中文与英文功能说明；修改既有 Release 时同样遵守。两种语言应表达相同的功能、限制、安装方式和必需设置，不能只把英文缩减为安装提示。
- 源码和文档使用 UTF-8。项目现有规则要求不新增 em dash 字符，使用普通连字符或中文标点。

## 完成任务前

1. 运行与改动最接近的定向测试。
2. 运行 `uv run --project src --frozen pytest -q`。若已有失败仍存在，记录精确测试名和原因，不得写成全部通过。
3. 运行 `git diff --check`，再次查看 `git status --short --branch` 和完整 `git diff`。
4. 确认未覆盖无关改动，未产生构建产物、缓存或用户配置。
5. 运行 Ruff、Pyrefly、上方限定到受版本控制源码的 `compileall` 命令和 `uv lock --check --project src`；不要递归编译 `.venv` 或 `packaging/*/dist`。Pyrefly warning 与 error 必须分开报告。
6. 涉及 HID、USB 音频或 Bluetooth 时，单元测试之外还需记录真实硬件验证的连接方式、结果、Forza 游戏内振动开关和 Steam Input 状态。未执行就写“未执行”。
7. 涉及发行时核对 `src/pyproject.toml`、构建脚本、Release workflow、README 和二进制名称的一致性。
8. 涉及 Windows R-series 打包时，确认唯一规范 EXE 与 `.sha256` 存在、`write_sha256.py --check` 通过、线上重新下载后的哈希仍匹配、版本资源为当前 `R<n>`，并执行启动、滚轮、退出提示和更新入口冒烟测试。
9. 涉及新增内嵌资产或第三方组件时，对比最新稳定 Release 与新构建的 EXE 字节数，报告 MiB、绝对增量和百分比；超过体积门槛时同时给出用户确认记录。
10. 涉及更新事务时，除自动测试外至少用上一公开稳定 EXE 在隔离目录执行一次真实升级，核对规范新旧文件名、健康确认、快捷方式 target/icon/参数/工作目录、失败保留策略和遗留进程；未执行就明确记录。

## `docs/PROJECT_STATE.md` 更新规则

出现以下任一情况时必须同步更新 `docs/PROJECT_STATE.md`：

- 功能从计划变为实现、验证或发布。
- 当前开发重心、下一步顺序或暂时禁止修改的范围改变。
- 新增或解决 Bug、技术债、文档与代码不一致。
- 测试、构建、CI 或真实硬件验证结果改变。
- Git 分支、版本、关键文件或工作区状态发生对后续会话有意义的变化。

只记录已验证事实。会话决定但尚无代码的内容必须标为“设计已确认，代码未实现”；无法确认的内容写“待确认”。架构边界发生长期变化时同时更新 `docs/ARCHITECTURE.md`。

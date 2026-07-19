# Codex 项目工作指引

## 项目目标

FH-DualSense-Enhanced 读取 Forza Horizon Data Out 的 UDP 遥测，将车辆状态转换为 DualSense 自适应扳机、USB/Bluetooth 握把触觉与可选灯效，并以独立 Windows EXE 或源码方式运行。

## 技术栈

- Python `>=3.13`，依赖和运行环境由 `uv` 管理，锁文件为 `src/uv.lock`。
- GUI 使用 `CustomTkinter`，TUI 使用 `Textual`。
- 原生手柄输出使用 `hidapi`；USB 握把触觉使用 `sounddevice`、PortAudio 和 `NumPy`，Bluetooth 握把触觉使用同一 `NumPy` PCM renderer 和 HID report `0x36`。
- Windows Xbox App 输入桥使用项目自有 `ctypes` ABI 封装、固定哈希的 `ViGEmClient.dll` 和可选离线 ViGEmBus 安装器，目标设备为虚拟 Xbox 360 Controller。
- 系统托盘使用 `pystray` 和 `Pillow`，进程检测使用 `psutil`。
- 内置更新器使用 Python 标准库访问 GitHub Releases，并由独立 PyInstaller Helper 在 Windows 上完成校验后的 EXE 替换。
- 测试使用 `pytest`，发布使用 ZUV、PyInstaller 和 GitHub Actions；Windows 构建生成唯一的标准 `FH-DualSense-Enhanced-R<n>.exe`。

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
| `src/main.py` | CLI、配置加载、GUI/TUI/headless 启动和崩溃日志入口 |
| `src/modules/loop.py` | 遥测热循环、空闲静音、退出检测和输出去重 |
| `src/modules/forzahorizon/udp_listener.py` | UDP 监听、324 字节包解析和原始包转发 |
| `src/modules/forzahorizon/game_launch.py` | Windows FH4/FH5/FH6 定义、Steam 安装发现、Xbox AUMID 发现、精确进程检测和显式启动 |
| `src/modules/forzahorizon/fh6_language.py` | FH6 专属语言包内容识别、有效语言摘要、显式交换/还原和崩溃恢复 |
| `src/modules/forzahorizon/controller_icons.py` | FH6 DualSense 图标 MOD 的校验、双目标事务安装、独立原件备份与显式还原 |
| `src/modules/forzahorizon/effects.py` | Forza 专用 L2/R2 效果、优先级和跨帧状态 |
| `src/modules/forzahorizon/lighting.py` | 转速灯带、红线闪烁和挡位 Player LEDs 的传输无关状态 |
| `src/modules/haptics/` | 传输无关的握把混音与 PCM renderer，以及 USB audio、Bluetooth HD haptics 和 compatible fallback 路由 |
| `src/modules/dualsense/` | DualSense 枚举、USB/BT HID 报告、Bluetooth `0x36` 封包、自适应扳机和重连 |
| `src/modules/xinput/` | DualSense 输入映射、ViGEm Xbox 360 target、卡键保护、driver 探测和平台生命周期 |
| `src/modules/update/` | Windows 独立 EXE 的 Release 查询、资产选择、下载、SHA-256 校验、待安装状态和 Helper 调度 |
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
uv run --project src pytest -q
```

基础检查：

```powershell
git diff --check
python -m compileall -q src/modules src/lang
git status --short --branch
git diff --name-only
```

仓库只配置了 Ruff 的行宽，没有定义稳定的 lint 或 type-check 命令。不要声称执行了未配置的检查。

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
- GUI 和 TUI 的同类设置必须同时更新，并补齐 `src/lang/` 中所有非英语语言目录的翻译或明确回退行为。
- Enhanced R4 的涡轮增压阻力、G 力阻力、L2/R2 碰撞扳机冲击和 L2/R2 空闲路面纹理属于实验性扳机反馈。六个开关及全部参数必须只出现在 GUI/TUI 默认折叠的“实验性功能”中，并继续默认关闭；未经新的产品决定不得移回普通“驾驶反馈”页面。
- 调整 R2 扳机键基础油门阻力或 G 力阻力前，必须先做 Enhanced R3/Enhanced R4 受控 A/B：固定车辆、路段、Profile、连接方式和游戏设置，记录 Forza 游戏内振动、Steam Input、最终效果来源、trigger mode 与 force。当前代码审计表明基础油门 ramp 未被 G 力层替换；不得仅凭“开启 G 力后手感相似”就删除旧路径、默认开启实验功能或改写默认参数。
- 总览状态必须来自线程安全的运行时快照或现有不可变快照，并由 GUI 主线程定时渲染；不得从日志文本反推状态，也不得只在控件创建时写占位值。UDP 状态只统计 324 字节有效包，错误主文案保持简短，详细原因放在提示或日志。
- FH6“中文文字 + 英文语音”支持 Windows Steam 与 Xbox App 版并且必须保持按钮式。Steam 路径自动枚举并读取 manifest；Xbox App 只使用用户手动选择并保存的 `fh6_xbox_install_path`，不得伪造自动发现或游戏语言。自动启动、页面刷新和路径发现只能读取；不得自动交换、还原、修复或删除语言包。生产代码不得硬编码盘符或 `Program Files`，必须验证 `ForzaHorizon6.exe`、`media/Stripped/StringTables`、ZIP 内容和游戏未运行。Steam manifest 明确不是 English 时禁止启用；Xbox App 或手动路径无法证明游戏语言时，三行状态必须显示未知且操作要求额外确认。任何改名都使用同目录临时名、逐步前置检查和失败回滚；崩溃残留只能在用户再次确认后修复。
- `FH6Install.steam_language` 表示 Steam 为 FH6 记录的游戏内容语言，不是 Steam 客户端界面语言。三行“当前 FH6 游戏使用语言 / 实际显示语言 / 语音语言”必须通过 `summarize_fh6_languages()` 和 `language_summary_view()` 共用推导与本地化；不得在 GUI/TUI 中分别猜测，也不得把 Xbox App、未知或损坏状态推断为某种有效语言。
- 总览 Forza Horizon 启动入口必须保持用户点击触发，并同时考虑 Windows Steam/Xbox App 的 FH4、FH5、FH6。左侧按钮只启动当前选择，右侧菜单只选择不启动；首次默认 FH6，之后持久化最后选择。Steam 启动交给三代固定 `steam://run/<app-id>`；Xbox App 启动先用 `Get-StartApps` 动态发现带 `!` 的 AUMID 并交给 `shell:AppsFolder`，未发现时才打开固定产品 ID 的 `msxbox://game/` 页面。不得直启 EXE、静默提权、自动启动或借启动动作修改语言包。Steam 安装发现、Xbox AUMID 查询与精确进程检查放在后台，异步结果必须携带游戏键和序号，Tk 控件只由 GUI 主线程更新。
- 总览 Steam 安装发现只扫描当前选择的游戏。找到并验证路径后停止周期发现；未找到时每 30 秒静默重试，路径设置变化或显式启动验证失败才使缓存失效。首轮结果之后的后台重试不得把按钮重新显示为“正在查找”。启动按钮、游戏/平台选择器和 XInput action 只在 presentation tuple 变化时重绘，不得每秒无条件 `configure()` 或 `grid_forget()`/`grid()`。
- 今后修改游戏启动、安装发现、进程检测、游戏关闭联动、更新说明或相关用户文案时，必须同时检查 FH4、FH5、FH6；只有明确标记为单代专属的功能可以例外。FH6“中文文字 + 英文语音”和对应模组提醒仍是 FH6 专属，不得为了统一命名扩展到 FH4/FH5。
- UDP 热路径必须继续使用 `UDPListener.recv_latest()` 丢弃积压包，不能改为逐包处理旧遥测。
- `src/modules/loop.py` 只在 `(left, right, rumble, visual)` 状态改变时调用普通手柄状态输出；USB 和 Bluetooth HD haptics 目标仍需要逐遥测帧更新，并由各自的音频周期持续渲染。
- Body haptics 关闭时不得占用 compatible rumble flags 或 motor bytes。Bluetooth fallback 的 rumble 释放帧不能被后续 trigger-only 帧吞掉；HD haptics 停止或断开前必须排队或写入全零 `0x36` 采样块。
- 不要随意修改 324 字节遥测偏移、USB/BT HID offset、BT CRC、trigger mode byte 和左右扳机映射。`0x36` 固定为 398 字节、3 kHz、每包 32 帧交错左右 int8；修改时必须增加字节级和调度测试。
- Bluetooth HD haptics 不依赖 vDS 驱动、虚拟 USB、test signing 或 Opus。`src/modules/dualsense/bt_haptics.py` 只发送本项目合成的 haptics block，不得宣称已经接管游戏原生振动。
- XInput bridge 只在 Windows x64 的 Xbox App 模式启用，且必须复用 `DualSense` I/O 线程作为唯一物理 HID reader。Steam 模式必须停止 bridge 并移除虚拟 target。100 ms 无新输入时发送中立状态，3 s 时移除 target；不得回放 stop 前或重连前的旧输入。当前不注册 ViGEm rumble callback、不模拟 Xbox One、不安装或配置 HidHide，也不把真实 Xbox App 游戏写成已验证。
- GUI 只保留一个正式壳层。现有青绿色视觉源自内部 Miku Console 设计理念，但该名称只允许在老三样中记录设计来源，不得出现在窗口标题、页面文案、翻译、构建资产、README、Release 或其他当前文档中。主题颜色集中在 `src/modules/gui/theme.py`，页面和后端不得按构建产物分叉；不要恢复 Stage、Studio、`FHDS_UI_VARIANT`、`FHDS_BUILD_VARIANT` 或 `data/ui_variant.txt`。
- GUI tab frame 必须在创建后只 `grid()` 挂载一次，由 `TriggerGUI._select_nav()` 使用 `tkraise()` 和可选 `on_show()`/`on_hide()` 切换；不得恢复每次导航 `pack_forget()` 后重新 `pack()` 的布局方式。页面隐藏时应暂停只属于该页面的周期发现，后台结果继续通过 serial 和主线程边界丢弃过期状态。
- 产品图标只维护 `src/data/icon.png` 和 `src/data/icon.ico` 这一组源资产，窗口、托盘、Windows 主 EXE、更新 Helper 和 Linux 包必须复用它们。ICO 保持 16、24、32、48、64、128、256 七档；替换图标时同步更新图标哈希契约测试并验证最终 PE 提取图标，不得只更换源码窗口或只更换打包图标。
- 长页面使用 `widgets.FastScroll` 注册到根窗口 `WheelRouter`。不要重新覆盖 CustomTkinter 私有 `_mouse_wheel_all`，也不要让滚轮修改 slider；嵌套滚动必须在内层到达边界后才转交外层。
- 内置自更新只允许冻结后的 Windows 独立 EXE。必须保留稳定 `R<n>` tag、规范资产 `FH-DualSense-Enhanced-R<n>.exe`、配套 `.sha256`、MZ 头检查、`.part` 下载、独立 Helper 和 `.old` 回滚；源码、Linux 和 ZUV 运行不得尝试覆盖可执行文件。发布 sidecar 必须由 `packaging/windows/write_sha256.py` 生成并在上传前以 `--check` 复核，不得重新依赖 `Get-FileHash`、`certutil` 或本地化系统输出。
- 引入或内嵌第三方运行库、驱动安装器、Mod、模型、媒体包或其他二进制资产前，必须以最新稳定 GitHub Release 的 Windows EXE 为基线，记录资产的准确版本、原始字节数、预计成品大小、绝对增量和百分比；实现后再用真实构建复测。预计或实测增量只要超过 `5 MiB` 或 `10%` 任一门槛，必须在继续合入或发布前取得用户明确确认，并优先评估按需下载、可选 sidecar 或裁剪资产。不得只用源码目录大小代替最终 one-file EXE 体积。
- FH6 DualSense 图标 MOD 只允许由用户显式安装或还原。内置 `ControllerIcons.zip` 必须先校验固定 SHA-256，再同时写入普通与 HiRes 两个目标；两份原始文件按安装根目录独立备份到应用数据目录，部分状态必须修复或拒绝，不能静默覆盖失效备份。GUI/TUI、README、Release、关于页与 `docs/THIRD_PARTY_NOTICES.md` 必须保留可点击的 Nexus 来源和作者 `@hotline1337` 鸣谢；不得把用户陈述的单次许可扩写为通用许可证。
- FH6“中文文字 + 英文语音”和 DualSense 图标 MOD 只出现在 GUI/TUI 的独立 `FH6 utilities` 页面，`SystemTab` 不得保留卡片、worker 或隐藏入口。该页首次显示、路径变化和显式操作后检查；未找到路径时仅在页面可见期间每 30 秒静默重试，找到后停止路径发现。轻量 FH6 进程检测可继续用于禁用文件写入，但不得重新引入五秒文件扫描。
- HidHide 检测只能探测，当前代码不调用 `HidHideCLI.exe` 或修改 HidHide 配置。
- DSX 是无 ACK 的 UDP 后端，`connected` 只表示 socket 已打开。当前 DSX 不提供握把触觉。
- `Default` Profile 会自动保存并跨重启保留，不得在启动时覆盖。恢复出厂设置必须重置 Profile 和 global fields、重新检测系统显示语言、切回 `Default`、保留命名 Profile，并在写入成功前保留 `.bak`。
- GUI 的窗口关闭、托盘退出、游戏关闭、遥测超时和更新重启必须走统一退出入口；本会话改过 `Default` 的 Profile 字段时才能提示另存命名 Profile，纯 global 变更和当前命名 Profile 不提示。
- 修改 Profile 默认值时必须同步 `tests/fixtures/community_defaults.json`、`tests/test_community_defaults.py`、README 和 Release 正文；除非迁移设计明确要求，不得覆盖命名 Profile 中已经显式保存的值。
- GitHub 根 `README.md` 固定为精简的英文用户指南，简体中文与日语分别位于 `docs/ReadmeZH.md`、`docs/ReadmeJA.md`；不要恢复三语同页或 `docs/ReadmeEN.md`。三份页面只保留核心功能、下载、必需游戏设置、连接说明、常见故障和许可证，不要加入小设置、内部算法或开发构建手册。README 不使用内部界面代号，但该限制不代表删除现有青绿色视觉设计。必需设置必须写明 Forza 游戏内振动关闭；Steam 模式写明 Steam Input 开启，Xbox App 模式写明使用内置 XInput bridge 且不需要 DS4Windows/Steam Input。
- 提交或推送本地更新前必须先获取并审阅远端分支。若用户已直接在 GitHub 修改并提交任何 README，本地更新必须以远端改动为合并输入，逐段理解并保留用户修改，再把本地需要的内容语义合并进去；不得用本地旧版 README 整文件覆盖远端，不得无视远端差异，也不得在冲突处理中机械选择本地版本。
- 三语 README 必须用四到六个用户可感知类别，明确说明当前 Enhanced 版本相比 `Forza-Horizon-DualSense-Python 1.6.2` 的累计核心增强。该清单只能依据当前生产代码、自动测试或已记录的真实硬件结果，不得混入内部参数、逐项开关、仅设计或推测能力。GitHub Release body 另行说明当前版本相比上一稳定 Enhanced 版本的增量，不能把两种比较口径混写。
- GitHub 仓库当前是独立仓库，不再属于 fork network；保留完整 Git 历史，不要重新建立基于 fork 身份的发布假设。独立状态不改变 `LICENSE` 要求的署名、原项目链接和 Sponsor 链接，也不改变 `docs/THIRD_PARTY_NOTICES.md` 中的 HorizonHaptics 归属。
- 不要把尚未通过测试或实机验证的行为写成已验证或已发布。以生产代码、自动测试和硬件记录分别标注事实层级。
- 术语必须消除歧义：版本阶段写 `Enhanced R<n>`，手柄右扳机写 `R2 扳机键`；不要单独写无法判断含义的 `R2`。
- 每个 GitHub Release body 必须同时包含对应版本的完整中文与英文功能说明；修改既有 Release 时同样遵守。两种语言应表达相同的功能、限制、安装方式和必需设置，不能只把英文缩减为安装提示。
- 源码和文档使用 UTF-8。项目现有规则要求不新增 em dash 字符，使用普通连字符或中文标点。

## 完成任务前

1. 运行与改动最接近的定向测试。
2. 运行 `uv run --project src pytest -q`。若已有失败仍存在，记录精确测试名和原因，不得写成全部通过。
3. 运行 `git diff --check`，再次查看 `git status --short --branch` 和完整 `git diff`。
4. 确认未覆盖无关改动，未产生构建产物、缓存或用户配置。
5. 运行 `python -m compileall -q src/modules src/lang`。
6. 涉及 HID、USB 音频或 Bluetooth 时，单元测试之外还需记录真实硬件验证的连接方式、结果、Forza 游戏内振动开关和 Steam Input 状态。未执行就写“未执行”。
7. 涉及发行时核对 `src/pyproject.toml`、构建脚本、Release workflow、README 和二进制名称的一致性。
8. 涉及 Windows R-series 打包时，确认唯一规范 EXE 与 `.sha256` 存在、`write_sha256.py --check` 通过、线上重新下载后的哈希仍匹配、版本资源为当前 `R<n>`，并执行启动、滚轮、退出提示和更新入口冒烟测试。
9. 涉及新增内嵌资产或第三方组件时，对比最新稳定 Release 与新构建的 EXE 字节数，报告 MiB、绝对增量和百分比；超过体积门槛时同时给出用户确认记录。

## `docs/PROJECT_STATE.md` 更新规则

出现以下任一情况时必须同步更新 `docs/PROJECT_STATE.md`：

- 功能从计划变为实现、验证或发布。
- 当前开发重心、下一步顺序或暂时禁止修改的范围改变。
- 新增或解决 Bug、技术债、文档与代码不一致。
- 测试、构建、CI 或真实硬件验证结果改变。
- Git 分支、版本、关键文件或工作区状态发生对后续会话有意义的变化。

只记录已验证事实。会话决定但尚无代码的内容必须标为“设计已确认，代码未实现”；无法确认的内容写“待确认”。架构边界发生长期变化时同时更新 `docs/ARCHITECTURE.md`。

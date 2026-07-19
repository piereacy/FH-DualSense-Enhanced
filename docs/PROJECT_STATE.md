# FH-DualSense-Enhanced 当前项目状态

最后更新时间：2026-07-19

## 当前阶段

- 当前开发版本：`Enhanced R6`，`src/pyproject.toml` 内部版本为 `6`。
- 当前阶段：R6 功能、GUI 性能、FH6 三行语言状态和 Xbox App 手动语言目录支持已进入生产代码；完整自动测试、源码 GUI/TUI 冒烟和最终 Windows one-file 构建验收均已通过，当前处于发布前收口。
- 当前公开稳定版仍是 GitHub Release `R5`。`origin/main` 与 tag `R5` 指向 `031c769`；R6 实现已提交到本地 `379d020`，尚未 push、tag 或发布。
- 当前开发重心：冻结包含 Windows Xbox App XInput bridge、FH4/FH5/FH6 双平台启动、FH6 双平台文件工具、三行语言状态和 GUI 性能修复的 R6 候选，并在用户确认后执行 push、tag 与 Release。
- 不属于当前 R6 完成条件：DSX 新适配、原生游戏 rumble 接管、红线手感继续调校和自动更新器的 24 小时节流。

## 已在代码中实现

### 1. Steam/Xbox App 的 FH4、FH5、FH6 启动入口

- `src/modules/forzahorizon/game_launch.py` 统一保存三代游戏的 Steam App ID、Xbox product ID 和精确 EXE 名。
- Steam 模式继续验证安装后提交对应 `steam://run/<app-id>`，不直启 EXE。
- Xbox App 模式运行只读 `Get-StartApps`，只接受 `PackageFamilyName!Application` 形式的 AUMID；精确匹配当前代后以 `shell:AppsFolder\\<AUMID>` 激活。未发现时打开固定 `msxbox://game/?productId=<id>` 产品页，让用户在 Xbox App 中安装或点击开始。
- `src/modules/gui/overview_tab.py` 记住平台和游戏，平台/游戏选择本身不启动；启动请求在后台执行，Tk 控件只由主线程更新。
- 当前电脑 `Get-StartApps` 实际返回 223 项，但没有安装任何 Xbox App 版 Forza，因此真实 AUMID 启动尚未执行。产品 ID、匹配和 fallback 已由自动测试覆盖。

### 2. Windows x64 DualSense-to-XInput bridge

- `src/modules/dualsense/input_state.py` 解析 USB/Bluetooth 输入报告；`src/modules/dualsense/main.py` 仍是唯一物理 HID reader。
- `src/modules/xinput/report.py` 把标准按钮、D-pad、摇杆和 L2/R2 扳机键映射为 `XUSB_REPORT`；不增加 deadzone、曲线或 EWMA。
- `src/modules/xinput/bridge.py` 只保留 latest state；100 ms 无新输入时发送中立，3 s 时移除虚拟 target，停止/重启后不回放旧输入。
- `src/modules/xinput/service.py` 只在 Windows x64 的 Xbox App 模式挂载 bridge。Steam 模式解除 input consumer、移除虚拟 target，不产生双输入。
- target 固定为虚拟 Xbox 360 Controller。当前不模拟 Xbox One、不注册 rumble callback、不接管游戏原生振动、不安装或配置 HidHide，也没有复制 DS4Windows GPL 代码。
- 当前电脑已完成合成 ViGEm target 的 `XInputGetState` 反读；真实 Bluetooth DualSense 已完成从 HID 输入到虚拟 XInput 的端到端读取，并验证 100 ms 中立与 3 s 移除。真实 Xbox App 游戏仍未验证。

### 3. 离线 ViGEmBus 引导

- Windows bundle 固定携带 `src/data/xinput/ViGEmClient.dll`：130,048 字节，SHA-256 `2BF0CB1D809039573C922737D298A1653D4DBC61408060FF45A9BCFDE82E97D2`。
- 固定携带官方 `ViGEmBus_1.22.0_x64_x86_arm64.exe`：6,278,576 字节，SHA-256 `89220A7865076B342892F98865F3499FB7C4CFD673159E89D352C360FD014C6A`。
- `src/modules/xinput/driver.py` 先按真实 client connect 探测兼容 driver；只在缺失、用户确认、固定 SHA-256 和 cache-only Authenticode 均通过后以 `runas` 触发 UAC。安装资源本身不需要联网。
- ViGEmBus/ViGEmClient 已停止上游维护；代码不自动升级 driver。许可证、版本、哈希和项目链接已写入 `docs/THIRD_PARTY_NOTICES.md` 与 GUI/TUI 关于页。

### 4. 内置 FH6 DualSense 按键图标 MOD

- 用户提供的 `DualSenseIcons 2.1.1` 两个内层归档内容相同，项目只内置一份 `src/data/mods/dualsense_icons/ControllerIcons.zip`：70,188 字节，SHA-256 `9677E50BF04276A9606956819D7760588EA7B986CFAFEBC70396F35630C53A61`。
- `src/modules/forzahorizon/controller_icons.py` 把同一资源写入普通与 HiRes 两个目标；原文件分别备份，manifest 绑定游戏根路径和哈希，写入失败回滚，FH6 运行时拒绝修改。
- Steam 路径可自动发现；Xbox App 根路径由用户手动选择并保存为 `fh6_xbox_install_path`。没有在当前真实游戏目录执行安装或还原。
- GUI/TUI 的独立 `FH6 utilities` 页面提供语言工具、图标扫描、安装、还原和选目录；`SystemTab` 已删除两项工具的卡片、timer、worker 和隐藏入口。工具页、关于页、三语 README、Release 源文案和第三方声明均以 Nexus 链接鸣谢 `@hotline1337`。许可事实只按用户陈述记录，不推断通用再许可。

### 5. 其他 R6 工作树功能

- `src/modules/gui/widgets.py` 的更新提示点由导航按钮自身 canvas 绘制白点，不再使用带黑底的独立控件。
- `src/modules/gui/main.py` 把全部页面只挂载一次，导航使用 `tkraise()` 与 `on_show()`/`on_hide()`，不再每次 `pack_forget()` 后重新布局长页面。
- `src/modules/gui/overview_tab.py` 只发现当前选择的 Steam 游戏；找到路径后停止，未找到时每 30 秒静默重试。状态卡、启动按钮、selector 和 XInput action 只在 presentation 变化时更新，默认平台仍为 Steam。
- `src/modules/gui/fh6_utilities_tab.py` 与 `src/modules/tui/fh6_utilities_tab.py` 独立承载 FH6 语言和图标工具；页面隐藏时不继续周期发现，找到路径后只保留轻量进程状态检查。两项工具均在 Steam 自动路径和 Xbox App 手动路径上工作。
- FH4/FH5/FH6 通用启动文案、Steam/Xbox App 说明和全部非英语 catalog 已补齐。
- `src/modules/forzahorizon/fh6_language.py` 的 `FH6LanguageSummary` 与 `summarize_fh6_languages()` 负责区分游戏语言、实际文字语言和语音语言；GUI/TUI 通过共用 `language_summary_view()` 显示本地化三行，不再暴露原始 `english` token。Steam manifest 可得时显示确定结果；Xbox App 无可靠语言元数据时显示未知并要求额外确认。
- `README.md`、`docs/ReadmeZH.md`、`docs/ReadmeJA.md` 已保持分语言精简结构，并说明 Steam/Xbox App 使用方式、关闭 Forza 游戏内振动、XInput bridge 与 FH6 图标工具。
- `.github/workflows/release.yml` 已准备完整中文与英文 R6 说明；尚未创建 R6 tag 或 Release。

## 文档声称与代码事实的边界

- 已实现：上述模块、配置字段、GUI/TUI 控件、打包输入和自动测试均存在于当前工作树。
- 已实机验证：当前电脑的 ViGEm 合成反读、Bluetooth DualSense XInput 端到端和 stale/remove 保护；这些不等同于 Xbox App 版 Forza 已验收。
- 尚未实机验证：真实 Xbox App 游戏启动与驾驶、clean-machine ViGEmBus 离线安装、真实 Xbox App FH6 语言交换、真实 FH6 MOD 安装/还原、最终冻结 R6 GUI 的完整交互流程。
- 已由代码、自动测试和源码 GUI 冒烟验证：FH6 游戏语言/实际文字/语音三行显示，以及 Steam/Xbox App 的路径字段隔离；最终冻结包已确认包含对应模块，但未在真实 Xbox App 安装上操作游戏文件。
- 推测可能兼容：Xbox App FH4/FH5/FH6 使用标准 XInput，现有 bridge 理应可用；没有真实游戏证据前只写为待确认。

## 正在进行

1. 最终发布候选已生成：`packaging/windows/dist/FH-DualSense-Enhanced-R6.exe` 与同名 `.sha256`。
2. R6 实现已整理为本地提交 `379d020 feat: prepare Enhanced R6`；远端 README、文档一致性和最终 Git diff 已复核。
3. 本地已达到“可发布”状态；等待用户对候选 EXE 的最终确认，再 push、创建 `R6` tag 和中英双语 Release。

## 尚未完成与下一步顺序

1. 由用户运行最终候选，重点复核页面切换、滚轮、默认 Steam、独立 FH6 实用功能页三行状态、退出保存提示和 Xbox bridge 状态。
2. 若当前手柄可用，补一次 USB 与 Bluetooth bridge 快速回归；记录连接方式、Steam Input 与 Forza 游戏内振动。没有实际 Forza 驾驶时明确写“未执行”。
3. 用户确认候选后 push 当前提交，创建 `R6` tag 和 GitHub Release，上传规范 EXE、sidecar、ZUV、启动脚本、LICENSE 与第三方声明。
4. 从线上 Release 重新下载 EXE 与 sidecar，复核哈希，并在 R6 发布后执行一次 R5 -> R6 自更新验收。

## 当前已知 Bug 和限制

- 真实 Xbox App 版 Forza 尚未测试；当前电脑没有对应安装，因此 AUMID 动态发现只有 fixture 覆盖。
- Xbox App FH6 语言和 MOD 根路径不能自动发现，需要用户手动选择；受保护 package ACL 与未来目录布局变化待确认。
- Xbox App 当前游戏与语音语言没有可靠元数据来源，因此三行状态会显示未知；这不阻止用户在额外确认后使用交换/还原，但真实 Xbox App 版尚未验证。
- Forza 游戏内振动必须关闭，否则 native rumble/Steam Input 可能掩盖本项目握把方向与细节；项目仍不复现菜单、CG 和上车过场原生振动。
- XInput bridge 不接收游戏 rumble，也没有多手柄、Xbox One target、GameInput impulse trigger、触摸板或陀螺仪映射。
- ViGEm 上游 EOL；固定哈希不能替代未来安全维护。
- 更新器仍无跨启动 24 小时节流，真实 R5 到 R6 自更新替换要到 R6 发布后才能完整验收。
- R2 扳机键基础油门阻力与实验性 G 力层的主观差异尚未做受控 Enhanced R3/Enhanced R4 对照，属于独立后续调校。
- Linux 本地 build script 的 `numpy`/`sounddevice` 依赖差异仍待确认；本轮 XInput、ViGEm 与 MOD 明确只支持 Windows。

## 当前技术债

- GUI/TUI 分别声明设置 section，依靠测试保持一致。
- 遥测仍使用未类型化 `dict`。
- `ProcessWatcher` 的通用退出观察仍按 `forza` 子串匹配；启动器使用精确 EXE 名。
- USB audio endpoint 仍按名称自动选择，没有用户可选 host API/device。
- 更新器没有代码签名信任链，只使用 Release sidecar SHA-256 与 MZ 头。
- ViGEmClient 是项目自有最小 `ctypes` ABI，升级 DLL 时必须重新审计结构布局、错误码、哈希和集成测试。
- 三份 README 是独立文件，关键事实依赖契约测试和人工语义同步。

## 暂时不要修改

- 不要移动、覆盖或删除已经发布的 `R1`、`R2`、`R3`、`R4`、`R5` tag、Release 和资产。
- 不要改变 DualSense USB/BT 输入 offset、输出 report 长度、BT CRC、`0x36` 398 字节布局或左右通道映射，除非同时增加字节级测试与真实硬件验证。
- 不要给 XInput bridge 增加第二个 HID reader、输入队列回放、rumble callback、HidHide 自动配置或默认 Steam 模式 target。
- 不要把 Xbox App 产品页 fallback 写成安装/启动成功，也不要直启游戏 EXE。
- 不要把 FH6 图标 MOD 改成无备份覆盖；不要删除 `@hotline1337`、Nexus 链接或第三方声明。
- 不要绕过 `summarize_fh6_languages()` / `language_summary_view()` 分别在 GUI/TUI 猜测语言，也不要把 Xbox App 的未知语言伪造成英语。
- 不要在推送前用本地旧 README 整体覆盖用户可能在 GitHub 提交的新文本；必须先 fetch 并逐段语义合并。

## 最近涉及的关键文件

- 应用与配置：`src/main.py`、`src/modules/config/settings.py`、`src/modules/config/preferences.py`、`src/modules/config/paths.py`。
- XInput：`src/modules/dualsense/input_state.py`、`src/modules/dualsense/main.py`、`src/modules/xinput/`、`src/data/xinput/`。
- 启动与 MOD：`src/modules/forzahorizon/game_launch.py`、`src/modules/forzahorizon/controller_icons.py`、`src/data/mods/dualsense_icons/ControllerIcons.zip`。
- 界面：`src/modules/gui/main.py`、`src/modules/gui/overview_tab.py`、`src/modules/gui/fh6_utilities_tab.py`、`src/modules/gui/system_tab.py`、`src/modules/tui/main.py`、`src/modules/tui/fh6_utilities_tab.py`、`src/modules/tui/system_tab.py`。
- 发布：`packaging/windows/fhds.spec`、`.github/workflows/release.yml`、`docs/THIRD_PARTY_NOTICES.md`、三语 README。
- 测试：`tests/xinput/`、`tests/dualsense/test_input_state.py`、`tests/dualsense/test_input_consumer.py`、`tests/forzahorizon/test_game_launch.py`、`tests/forzahorizon/test_controller_icons.py`。

## 当前 Git 工作区状态

- 分支：`main`。
- R6 实现提交：`379d020 feat: prepare Enhanced R6`；其后的本文件更新仅记录发布前交接状态。
- `origin/main` 与公开 `R5`：`031c769 docs: refresh R5 release state`。
- 本文件提交后，本地相对 `origin/main` 领先 9 个提交。
- R6 功能代码、测试、三语文档、翻译、打包资产和老三样均已提交；本文件提交后工作树应保持干净，未执行 reset、stash 或删除用户改动。
- 线上 R5 规范 EXE 由 GitHub API 确认为 `47,218,192` 字节，SHA-256 digest `4d2a981e99ca094c5d61d1f094c8248d4ba216c68ad624ba7704a0ab906b1e9a`。它是 R6 体积比较基线。

## 已执行的测试和验证

- 2026-07-19 当前工作树完整测试：`uv run --project src pytest -q`，结果 `483 passed in 7.73s`。
- 源码 GUI 冒烟：构造全部 tab，逐项调用新 `_select_nav()` 并处理 Tk event，结果通过；页面没有重建或启动 backend。
- Textual 冒烟：在禁用 backend 启动的测试壳中切换 `FH6 utilities -> System -> Language`，结果通过。
- `uv run --project src python -m compileall -q src/modules src/lang`、`uv lock --check --project src` 与 `git diff --check` 已通过；`git diff --check` 只有 Git 的 LF/CRLF 提示，没有空白错误。
- 三行语言、Xbox App 手动目录、GUI/TUI 页面与分发契约定向测试：`61 passed in 3.84s`；完整测试已经包含这些用例。
- 翻译键完整性：此前缺键失败已修复，完整测试通过。
- 源码 GUI 三行语言冒烟：向独立 FH6 页面注入已交换的 English 安装状态，控件实际输出 `Current FH6 game language: English / Actual display language: Chinese / Voice language: English`，结果通过。
- 最终 Windows one-file：`51,814,190` 字节（`49.414 MiB`），SHA-256 `60791BAC18461FEC522423A18691BB148472087E2788980473DF8DDDBE3AC649`；相对 R5 增加 `4,595,998` 字节（`4.383 MiB`，`9.73%`），低于 `52 MiB` 停止线，也未超过长期 `5 MiB` 或 `10%` 门槛。
- 最终产物的 `.sha256 --check`、`MZ` 头、PE `FileVersion/ProductVersion=R6`、产品名、文件名、`--help`、最终 icon 和 PyInstaller 内置 Helper/ViGEm/MOD/FH6 语言与工具模块均已校验；`dist` 仅包含 EXE、sidecar、`LICENSE` 和 `THIRD_PARTY_NOTICES.md`。
- 当前电脑 ViGEm 合成 target：已用系统 `XInputGetState` 反向读取按键、摇杆和扳机，并在移除后确认 slot 消失。
- 真实 Bluetooth DualSense：已验证输入报告进入虚拟 XInput target，以及 100 ms 中立、3 s 移除；没有记录真实 Xbox App Forza 驾驶结果。
- Xbox 启动只读探测：`Get-StartApps` 返回 223 项，无 Forza AUMID；没有修改 package 或 Xbox App 状态。
- FH6 MOD：在临时 fixture 目录验证安装、双目标还原、游戏更新后备份刷新、partial 无备份拒绝和运行中拒绝；未写入真实游戏目录。

## 尚未执行或失败的验证

- GUI 一次挂载、差异渲染和独立 FH6 页面后的早期 R6 Windows EXE 曾通过默认 Steam 与独立页面目视检查，但已由最终 `51,814,190` 字节候选替代，不得上传旧产物。
- 最终候选的 sidecar、PE 版本、最终 icon、内置资产和 `--help` 已通过；最新三行补丁已做源码控件冒烟，但最终 EXE 的完整 GUI 交互仍待用户验收。
- clean-machine ViGEmBus 离线安装尚未执行；当前电脑已有兼容 bus。
- 真实 Xbox App 版 FH4/FH5/FH6 启动、输入和驾驶尚未执行。
- 真实 FH6 图标 MOD 安装/还原与游戏内显示尚未执行。
- R6 tag、GitHub Release、线上重新下载和 R5 -> R6 自更新尚未执行。

## 下一次 Codex 会话交接

开始时优先阅读：

1. `AGENTS.md`
2. 本文件 `docs/PROJECT_STATE.md`
3. `docs/ARCHITECTURE.md`
4. `docs/DECISIONS.md`
5. `docs/superpowers/specs/2026-07-19-r6-xbox-app-xinput-bridge-design.md`
6. `src/modules/xinput/bridge.py`
7. `src/modules/forzahorizon/game_launch.py`
8. `src/modules/forzahorizon/controller_icons.py`

建议首先处理的具体任务：让用户运行最终候选 `packaging/windows/dist/FH-DualSense-Enhanced-R6.exe`，确认 GUI 与可用硬件行为。候选已低于体积停止线；用户确认后复核远端、push 当前 R6 提交、创建 `R6` tag 和双语 Release，并从线上重新下载资产校验哈希。

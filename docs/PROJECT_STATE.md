# 项目当前状态

## 状态快照

- 最后更新：2026-07-14，Asia/Shanghai。
- 仓库：`piereacy/FH-DualSense-Enhanced`。
- 当前开发分支：`feat/r2-trigger-dynamics`，隔离工作树为 `.worktrees/r2-trigger-dynamics`。
- 当前开发基线：`128a7b9 chore: ignore local feature worktrees`。交付后的 HEAD 应使用 `git log -1 --oneline` 读取，避免文档因自身提交再次过期。
- 版本：`1.6.2.post1`，Release workflow 命名为 `FH-DualSense-Enhanced 1.6.2 Enhanced R1`。
- Git 历史：审计开始时本地是 shallow clone，只有 7 条已有提交，因此无法从本地恢复上游完整历史。
- 当前阶段：Enhanced R1 已发布；Enhanced R2 的动态 wheelspin、GT7 风格 ABS wall 和实验性设置已在功能分支实现并通过自动测试，尚未进行游戏遥测下的 USB、Bluetooth 和 DSX 实机验证，也尚未合入或发布。

## 当前开发重心

1. USB 与 Bluetooth synthetic telemetry 的关键 wheelspin、材质和 ABS wall 均由用户确认；下一步进入真实 Forza Data Out。
2. 在真实驾驶中验证驱动轮判断、低速烧胎、实际材质切换和 ABS gating，之后再确认 DSX 只退化为 dynamic vibration。
3. 根据实机手感只调默认常量，不改动既定 transport 边界；USB/BT 默认值目前无需调整，全部路径稳定后再决定版本号、合入和发布。

## 最近完成的功能

以下内容可由当前生产代码和测试确认：

- 遥测驱动握把触觉已经实现，核心位于 `src/modules/haptics/`，接入点位于 `src/modules/loop.py`。提交 `61cc16a` 增加了 USB 四声道音频、Bluetooth compatible rumble、混音和对应测试。
- 静止 gating 已实现：真正静止怠速安静，原地轰油和烧胎保留反馈，路面材质只在滚动或车轮实际空转时激活。实现位于 `src/modules/haptics/mixer.py`，覆盖位于 `tests/haptics/test_mixer.py`。
- USB 和 Bluetooth 的 trigger + rumble 原子输出、BT CRC、rumble release 和重连恢复已有测试，见 `src/modules/dualsense/main.py`、`tests/dualsense/test_output_report.py` 和 `tests/dualsense/test_reconnect_output.py`。
- GUI/TUI 的 USB audio lifecycle、关闭游戏退出、最小化到托盘开关已经实现，见 `src/modules/haptics/lifecycle.py`、`src/modules/gui/main.py`、`src/modules/gui/settings_tab.py` 和 `tests/gui/test_window_behavior.py`。
- 项目已改名为 `FH-DualSense-Enhanced`，版本设为 `1.6.2.post1`，发布脚本可生成 ZUV、Windows EXE 和 Linux ELF。相关入口为 `src/pyproject.toml`、`packaging/` 和 `.github/workflows/release.yml`。
- 默认调校已写入 `Settings` 并由 fixture 锁定，见 `src/modules/config/settings.py`、`tests/fixtures/community_defaults_2323.json` 和 `tests/test_community_defaults.py`。`2323` 只是测试 fixture 名称，不是运行时 Profile。
- About 与许可证归属已集中在 `src/modules/about.py`，Sponsor 只应出现在 About/License surface，对应测试为 `tests/test_about_and_release.py`。
- 根 `README.md` 已集成中文、英语和日语三个同页 anchor，测试现已验证 `#readme-zh-cn`、`#readme-en` 和 `#readme-ja`，不再要求跳转独立语言页面。
- 旧的 `docs/ReadmeTR.md` 已删除。`docs/ReadmeEN.md` 和 `docs/ReadmeJA.md` 暂时作为兼容文档保留，但根 README 不再链接过去。
- `exit_on_game_close=False` 现在同时禁用进程消失和 telemetry-lost 退出，应用会在断流后继续等待。启用时仍保留默认约 60 秒的断流 fallback，覆盖位于 `tests/test_loop_haptics.py`。
- Linux 文档已明确 launcher 不安装系统级 udev rule，并提供 `70-dualsense.rules` 的手动安装命令；根 README、兼容语言文档和 Release body 已同步。
- Enhanced R2 动态 wheelspin 已实现于 `src/modules/forzahorizon/effects.py`：只使用油门下 driven wheel longitudinal slip，低速使用 raw rotation，加入 threshold/hysteresis、40 ms attack、125 ms release 的时间型 EWMA、四类材质频带和最多约 30% 的 G force damping。覆盖位于 `tests/forzahorizon/test_effects.py`。
- GT7 风格 ABS wall 已实现：longitudinal slip 为主、combined slip 低权重辅助，速度只做 6 km/h gate，frequency/strength 随 slip 动态变化，默认保持 100 ms，并让顶部 3 个 zone 保持最大 wall。DSX fallback 由 `tests/dsx/test_client.py` 锁定。
- GUI/TUI 现在只在普通区显示 ABS/wheelspin strength 与 sensitivity，其余 R2 参数位于默认折叠的“实验性功能”，带“不建议自行调节”警告。六个非英语 catalog 已同步，Profile 与分享码 round-trip 已测试。

## 正在进行的工作

### 长期文档体系

代码状态：长期文档已经建立。本轮正在把 R2 生产代码、测试和验证事实同步到架构与交接文档。

- `AGENTS.md` 已从旧的英文项目地图更新为稳定的中文工作指引。
- `docs/ARCHITECTURE.md` 已按当前代码记录真实架构和技术债。
- `docs/PROJECT_STATE.md` 已记录当前版本、R2 边界和验证状态。

### Enhanced R2 实现与验证

代码状态：设计已记录在 `docs/superpowers/specs/2026-07-14-r2-dynamic-trigger-feedback-design.md`，实施清单位于 `docs/superpowers/plans/2026-07-14-r2-dynamic-trigger-feedback.md`。生产逻辑、设置和自动测试已经实现；当前进行到实机验证前审计。

- `TriggerAnimations` 新增 `_AsymmetricEwma`、wheelspin latch、ABS hold deadline 和 telemetry-off reset，未建立第二套 controller。
- `Controller.L2()` 和 `Controller.R2()` 的 first-match priority 保持不变，R2 只升级了原有 wheelspin 与 ABS effect。
- native USB/BT 继续使用现有 adaptive-trigger frame；`src/modules/dualsense/main.py` 的 report layout、flags 和 BT CRC 未修改。
- DSX 对 `M_VIBRATE_ZONES` 回退为 `TM_VIBRATE`，自动测试确认 frequency 保留，但 zoned wall 不存在。
- `Settings` 新参数均未加入 `GLOBAL_FIELDS`。命名 Profile 和 `FHDS:` 分享码 round-trip 已覆盖。
- GUI 隐藏构建和展开/折叠脚本已通过；Textual test app 已实际挂载默认折叠的 `Collapsible`。
- 已完成：USB 与 Bluetooth synthetic telemetry 下的核心手感验证。尚未完成：真实游戏遥测、DSX 手感验证和跨 transport 调校。

## 尚未完成的工作

### 尚未完成

- 在 Forza 实际驾驶中分段验证动态 wheelspin，尤其是前驱/后驱/四驱、松油漂移排除、低速烧胎和四种材质 signature。
- USB 的轻/重 ABS、Bluetooth 的强 ABS 与顶部 wall 已通过用户确认，100 ms hold 仍主要由自动测试覆盖。
- 使用 DSX 实机确认其退化振动可接受，且 UI/文档没有暗示 DSX 拥有完整 zoned wall。
- 根据实机结果调校默认参数；当前默认值是保守实现值，不能写成最终社区验证值。
- R2 版本号、README、Release workflow、构建产物、合入和 Release 均未处理。

### 仍存在的代码注释不一致

- `src/modules/config/settings.py` 的 serial 注释与 `src/modules/dualsense/main.py` 的 USB MAC backfill 和 USB 优先去重逻辑表面冲突，正确文案待硬件枚举结果再次确认。

### 根据代码推测，尚未验证

- `packaging/linux/build_elf.sh` 没有像 CI 一样向 `uvx` 显式加入 `numpy` 和 `sounddevice`。本地 Linux build 可能缺少 body haptics 依赖，但本次未在 Linux 执行，结论待确认。
- 根 README 与两个独立语言 README 同时保留，后续修改容易造成内容漂移。目前未逐段建立自动同步机制。

## 下一步建议顺序

1. 枚举当前 DualSense transport，先用 USB 分段验证 R2 wheelspin 输出，再验证 L2 ABS wall；每段之间归零并等待用户确认。
2. 在实际 Forza Data Out 中验证前驱、后驱、四驱和材质变化；若不符合预期，先补失败测试再调算法。
3. 切换 Bluetooth 重复关键 wheelspin/ABS 测试，确认功能差异只来自 transport 能力。
4. 启用 DSX 验证动态 vibration fallback，不期待完整 zoned wall。
5. 实机确认后复跑全量测试，更新 README、版本和 Release workflow，再决定合入与发布。

## 当前已知 Bug

当前自动化测试没有失败项。R2 尚未发现可由自动测试复现的 Bug。

真实 USB 与 Bluetooth synthetic telemetry 已测试且未发现手感问题；DSX 和游戏实时遥测尚未测试，因此触发时机、跨 transport 调校或设备特有问题仍待确认。compileall 第一次误扫描 `src/.venv` 时，第三方包并发写 `__pycache__` 出现 `FileNotFoundError`；改为只编译 `src/modules` 与 `src/lang` 后通过，该现象不属于业务代码失败。

## 当前技术债

- 遥测是无类型 `dict`，缺少结构化 schema。
- GUI/TUI 设置定义重复维护。
- R2 surface frequency band 在 GUI/TUI 中重复声明，依赖 AST parity test 防止漂移。
- DSX 无 ACK，且没有 body haptics。
- USB audio endpoint 依赖名称 heuristic，没有用户选择和 host API fallback。
- ProcessWatcher 使用宽泛的 `forza` 子串。
- 本地 Linux build 的 audio dependency 完整性待验证。
- 根 README 与兼容 EN/JA 文档存在内容重复，后续修改仍有漂移风险。
- 多处 hardware cleanup 使用宽泛 exception suppression，诊断能力有限。

## 暂时不要修改的部分

除非具体任务要求并配套测试，不要顺手重构：

- `src/modules/dualsense/main.py` 中 USB/BT report layout、rumble flags、BT CRC 和 pending rumble release。
- `src/modules/forzahorizon/udp_listener.py` 中 324 字节 offset 和 `recv_latest()` drain 语义。
- `src/modules/loop.py` 中 state-change write gate、1 秒静音和 body haptics failure isolation。
- `src/modules/haptics/mixer.py` 中静止、滚动、烧胎和路面材质 gating。R2 扳机改动不应破坏握把现有规则。
- `src/modules/config/preferences.py` 中 Default Profile 重建、GLOBAL_FIELDS 和 atomic write。
- `LICENSE`、`src/modules/about.py` 和 `docs/THIRD_PARTY_NOTICES.md` 的署名及第三方声明。
- 版本号和 Release workflow，直到 R2 实机验证完成。

## 最近涉及的关键文件

- `src/modules/forzahorizon/effects.py`、`tests/forzahorizon/test_effects.py`：R2 动态 wheelspin、ABS wall、EWMA、hysteresis、hold 和 telemetry-off reset。
- `src/modules/config/settings.py`、`tests/fixtures/community_defaults_2323.json`：R2 普通与实验参数默认值。
- `src/modules/gui/settings_tab.py`、`src/modules/tui/settings_tab.py`、对应 `system_tab.py` 和 `src/lang/`：默认折叠实验区、警告与多语言。
- `src/modules/dsx/dsx_wrapper.py`、`tests/dsx/test_client.py`：zoned ABS 到 DSX dynamic vibration 的明确退化。
- `tests/test_haptic_settings.py`：UI parity、Profile/share-code round-trip、翻译和 Textual 挂载。
- `docs/superpowers/specs/2026-07-14-r2-dynamic-trigger-feedback-design.md`、`docs/superpowers/plans/2026-07-14-r2-dynamic-trigger-feedback.md`：已批准设计和实施清单。
- `README.md`、`docs/ReadmeEN.md`、`docs/ReadmeJA.md`：同页三语言和 Linux udev 手动安装说明。
- `docs/ReadmeTR.md`：旧土耳其语文档已删除。
- `tests/test_enhanced_distribution.py`：同页 anchor 和 Linux 文档契约。
- `src/modules/loop.py`、`tests/test_loop_haptics.py`：`exit_on_game_close` 同时控制进程和断流退出。
- `src/pyproject.toml`、`.github/workflows/release.yml`：R1 版本和发布身份。
- `src/modules/haptics/audio.py`、`frame.py`、`mixer.py`、`manager.py`、`lifecycle.py`：R1 body haptics 主体。
- `src/modules/dualsense/main.py`、`src/modules/loop.py`：trigger 与 rumble 原子输出和主循环接入。
- `src/modules/config/settings.py`、`preferences.py`：社区默认值、Profile/global 边界和后台设置。
- `src/modules/gui/main.py`、`settings_tab.py`、`system_tab.py`、`tray.py` 及对应 TUI 文件：UI、后台、更新和 USB lifecycle。
- `packaging/`、`win_start.bat`、`linux_start.sh`：发行入口。

## 当前 Git 工作区状态

当前位于 `feat/r2-trigger-dynamics` 隔离工作树。R2 生产代码、自动测试和初版文档已提交为 `14832c0 feat: add R2 dynamic trigger feedback`，后续硬件验证记录单独提交；尚未合入 `main` 或发布。主 `main` 工作树不在本轮编辑范围内。

## 已执行的测试和验证

本轮 R2 已执行：

- 基线 `uv run --project src pytest -q`：`127 passed`。
- wheelspin、ABS、DSX、body haptics 和 defaults 定向回归：`60 passed`。
- R2 settings、翻译和 effects 定向回归：`32 passed`，之后又增加分享码测试，最终结果以交付前复跑为准。
- `uv run --project src pytest -q`：最终软件回归 `155 passed`。
- `uv run --project src python -m compileall -q src/modules src/lang`：通过。
- Textual test app 实际挂载 `SettingsTab`，确认 `#experimental-settings` 默认 `collapsed=True`。
- 隐藏的 CustomTkinter root 实际构建 `SettingsTab`，展开和再次折叠实验卡片均通过。
- `_enumerate_dualsenses()` 检测到 1 个 PID `0x0CE6` 的 USB DualSense；未同时检测到 Bluetooth interface。
- USB synthetic wheelspin 第 1 段成功写入 R2 frame `(6, (123, 42))`，持续约 1 秒后归零并关闭 handle。连接、输出、归零和用户手感确认均已完成。
- USB 用户确认：铺装路中等 `(123, 42)` 与高滑移 `(147, 62)` 均合适，强度层次可辨。
- USB 用户确认：泥土 `(45, 63)`、碎石 `(19, 83)` 和积水 `(106, 21)` 均与铺装路明显区分，默认强度合适。
- USB 用户确认：按实时 EWMA frame 更新时，wheelspin 建立速度和释放平滑符合预期。
- USB 用户确认：轻度 ABS `M_VIBRATE_ZONES`、强度 2、22 Hz 与重度 ABS 强度 3、60 Hz 均合适；L2 下部 pulse 有层次，顶部 3 zone wall 稳定。
- Bluetooth 枚举确认：仅出现 1 个 PID `0x0CE6`、bus type 2、serial `143a9a5c3583` 的 interface，没有 USB interface。
- Bluetooth 用户确认：铺装路中等 wheelspin `(123, 42)` 与碎石 `(19, 83)` 均清晰且强度合适。
- Bluetooth 用户确认：强 ABS `M_VIBRATE_ZONES` 的下部 60 Hz pulse 和顶部 3 zone wall 均正常，没有报告相对 USB 的明显损失。
- `git diff --check`：中期通过，只有 Git 的 LF/CRLF 提示；交付前需复跑。

## 尚未执行或失败的验证

- 未构建 ZUV、Windows EXE 或 Linux ELF。
- 未运行 GitHub Actions。
- 未在本次任务连接 Forza Data Out 做实时遥测测试。
- USB 与 Bluetooth 已完成 synthetic wheelspin、关键 surface 和 ABS wall 手感验证；DSX 和真实 Forza Data Out 未执行。
- 未验证 Linux udev 安装流程和本地 ELF body haptics 依赖。
- 仓库没有配置独立的 lint/type-check gate，本次未虚构或补充此类命令。

## 下一次 Codex 会话起点

优先阅读：

1. `AGENTS.md`
2. `docs/PROJECT_STATE.md`
3. `docs/ARCHITECTURE.md`
4. `src/modules/forzahorizon/effects.py`
5. `src/modules/config/settings.py`
6. `tests/test_enhanced_distribution.py`
7. `docs/superpowers/specs/2026-07-14-r2-dynamic-trigger-feedback-design.md`
8. `tests/forzahorizon/test_effects.py`、`src/modules/dualsense/adaptive_trigger.py` 和 `src/modules/dsx/dsx_wrapper.py`

建议首先处理的具体任务：不要继续加算法功能。用 trigger-only live harness 监听真实 Forza Data Out，先验证铺装路加速打滑、松油漂移不进 R2、原地烧胎和 ABS；之后再验证 DSX fallback。

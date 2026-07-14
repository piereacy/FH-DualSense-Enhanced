# 项目当前状态

## 状态快照

- 最后更新：2026-07-14，Asia/Shanghai。
- 仓库：`piereacy/FH-DualSense-Enhanced`。
- 当前开发分支：`feat/r2-trigger-dynamics`，隔离工作树为 `.worktrees/r2-trigger-dynamics`。
- 当前开发基线：`128a7b9 chore: ignore local feature worktrees`。交付后的 HEAD 应使用 `git log -1 --oneline` 读取，避免文档因自身提交再次过期。
- 版本：`1.6.2.post1`，Release workflow 命名为 `FH-DualSense-Enhanced 1.6.2 Enhanced R1`。
- Git 历史：审计开始时本地是 shallow clone，只有 7 条已有提交，因此无法从本地恢复上游完整历史。
- 当前阶段：Enhanced R1 已发布；Enhanced R2 的动态 wheelspin、GT7 风格 ABS wall 和实验性设置已在功能分支实现。USB/Bluetooth synthetic telemetry 手感已经确认；Bluetooth 真实 Forza Data Out 已完成油门打滑、松油漂移排除、低速 raw rotation、新 wheelspin/rev 优先级、L2 扳机键 ABS wall 和铺装/积水/泥土/碎石四种实际材质验证。前驱/后驱实机验证经用户决定不再执行，DSX 不在当前范围；功能分支尚未合入或发布。

## 当前开发重心

1. Enhanced R2 已完成当前批准范围内的实现、自动测试与硬件验证；不再继续调整 wheelspin/ABS 默认常量。
2. 最终软件回归已通过；下一步更新 Enhanced R2 版本号、README 与 Release workflow，并验证构建产物。
3. DSX 保留当前 adapter 和自动测试结果，不做实机调校、功能扩展或效果承诺，也不作为 Enhanced R2 发布门槛。

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
- `Controller.L2()` 的 first-match priority 未改变。真实遥测暴露 rev limiter 会遮蔽 wheelspin 后，`Controller.R2()` 已按用户确认调整为 `gear > idle > wheelspin > rev > wall > resistance`；3 个回归测试覆盖高速打滑、低速 raw rotation 和轮胎有抓地时仍保留 rev limiter。
- native USB/BT 继续使用现有 adaptive-trigger frame；`src/modules/dualsense/main.py` 的 report layout、flags 和 BT CRC 未修改。
- DSX 对 `M_VIBRATE_ZONES` 回退为 `TM_VIBRATE`，自动测试确认 frequency 保留，但 zoned wall 不存在。
- `Settings` 新参数均未加入 `GLOBAL_FIELDS`。命名 Profile 和 `FHDS:` 分享码 round-trip 已覆盖。
- GUI 隐藏构建和展开/折叠脚本已通过；Textual test app 已实际挂载默认折叠的 `Collapsible`。
- 已完成：USB 与 Bluetooth synthetic telemetry 下的核心手感验证；Bluetooth 真实游戏遥测已确认油门驱动打滑触发 R2 扳机键、松油漂移不触发、低速 raw rotation 触发、新优先级、真实 L2 扳机键 ABS wall 和四种实际材质 signature。前驱/后驱实机验证由用户明确取消，DSX 已移出当前范围。

## 尚未完成的工作

### 尚未完成

- USB 的轻/重 ABS、Bluetooth 的强 ABS 与顶部 wall 已通过用户确认，100 ms hold 仍主要由自动测试覆盖。
- Enhanced R2 版本号、README、Release workflow、构建产物、合入和 Release 均未处理。

### 当前明确不做

- 不开发或实机调校 DSX 适配。保留现有 `src/modules/dsx/dsx_wrapper.py` fallback 与 `tests/dsx/test_client.py` 回归，默认行为维持现状；除非用户以后重新提出，DSX 不阻塞 Enhanced R2。

### 仍存在的代码注释不一致

- `src/modules/config/settings.py` 的 serial 注释与 `src/modules/dualsense/main.py` 的 USB MAC backfill 和 USB 优先去重逻辑表面冲突，正确文案待硬件枚举结果再次确认。

### 根据代码推测，尚未验证

- `packaging/linux/build_elf.sh` 没有像 CI 一样向 `uvx` 显式加入 `numpy` 和 `sounddevice`。本地 Linux build 可能缺少 body haptics 依赖，但本次未在 Linux 执行，结论待确认。
- 根 README 与两个独立语言 README 同时保留，后续修改容易造成内容漂移。目前未逐段建立自动同步机制。

## 下一步建议顺序

1. 确定 Enhanced R2 的包版本与 Release 名称，更新 README、版本和 Release workflow。
2. 构建并冒烟检查 ZUV、Windows EXE；Linux ELF 仍需在对应环境或 CI 验证。
3. 决定合入 `main` 与发布 Release 的时机。

## 当前已知 Bug

当前自动化测试没有失败项。真实遥测曾发现 rev limiter 优先级高于 wheelspin，导致高转打滑时动态 wheelspin 被遮蔽；当前工作树已调整优先级、加入回归测试并通过真实 Bluetooth 游戏遥测复验。

真实 USB 与 Bluetooth synthetic telemetry 已测试且未发现手感问题；Bluetooth 游戏实时遥测已完成四驱 wheelspin/松油漂移、低速 raw rotation、新优先级和 ABS wall 主路径确认。DSX 未测试且不在当前范围。compileall 第一次误扫描 `src/.venv` 时，第三方包并发写 `__pycache__` 出现 `FileNotFoundError`；改为只编译 `src/modules` 与 `src/lang` 后通过，该现象不属于业务代码失败。

材质验证观察到 wheelspin 首次进入时可能出现单帧 `(30, 12)` rev-limiter 过渡，原因是时间型 EWMA 的第一次 update 只建立时间基准。稳定材质输出未受影响，用户未报告可感知异常；当前记录为观察项，不作为阻塞 Bug。

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

当前位于 `feat/r2-trigger-dynamics` 隔离工作树。Enhanced R2 生产代码、自动测试和初版文档始于 `14832c0 feat: add R2 dynamic trigger feedback`，USB/Bluetooth synthetic 验证记录随后单独提交；本轮变更范围是 R2 扳机键 wheelspin/rev 优先级修复、3 个回归测试和相应文档同步。准确 HEAD 与工作区清洁状态必须分别用 `git log -1 --oneline`、`git status --short` 读取。功能分支尚未合入 `main` 或发布。

## 已执行的测试和验证

本轮 R2 已执行：

- 基线 `uv run --project src pytest -q`：`127 passed`。
- wheelspin、ABS、DSX、body haptics 和 defaults 定向回归：`60 passed`。
- R2 settings、翻译和 effects 定向回归：`32 passed`，之后又增加分享码测试，最终结果以交付前复跑为准。
- rev/wheelspin 优先级红—绿回归：新增 3 个测试，修复前复现 wheelspin 被 rev limiter 遮蔽，修复后均通过。
- `uv run --project src pytest -q tests/forzahorizon/test_effects.py`：`22 passed`。
- `uv run --project src pytest -q`：当前最终软件回归 `158 passed`。
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
- Bluetooth 真实 Forza Data Out：用户确认高油门驱动轮打滑只触发 R2 扳机键，松油漂移不触发 R2 扳机键；监听日志同时暴露 rev limiter 会优先遮蔽 wheelspin，已据此修复。
- 新优先级修复后的低速实车复验：`drive_train=2`、`speed=1.72 km/h`、`gas=255`、driven-wheel `rotation=33.0 rad/s`、`slip=5.00` 时输出 `WHEELSPIN (6, (31, 20))`；随后 `speed=3.5 km/h`、`rotation=35.7 rad/s` 再次触发。用户确认 R2 扳机键手感合适。
- Bluetooth trigger-only ABS 实车复验：两次从约 170 km/h 直线重刹，L2 扳机键在 longitudinal slip 达到阈值后持续输出 `M_VIBRATE_ZONES`/`ABS_WALL`，动态强度随 slip 变化并一直覆盖到低速门槛附近；用户确认该测试已经完成。
- Bluetooth 真实材质验证：铺装路面稳定为 `surface_rumble=0`、`90..180 Hz`，有效采样 `123/124`；唯一例外是首次进入时的一帧 rev transition。
- Bluetooth 真实材质验证：积水由主导驱动轮的微小正 `wheel_in_puddle` 优先识别，稳定输出 `80..150 Hz`；进入水区前的泥土采样不计为积水失败。
- Bluetooth 真实材质验证：泥土稳定为 `surface_rumble=0.120`、`30..70 Hz`，有效采样 `199/199`。
- Bluetooth 真实材质验证：最终有效碎石区四轮稳定为 `surface_rumble=0.600`，动态输出覆盖 `12..30 Hz`；离开碎石表面时按当前主导轮数据切换到泥土或铺装频带，重新进入后恢复。用户完成四段且未报告手感异常。
- 材质验证交付检查：`uv run --project src pytest -q` 为 `158 passed`；`uv run --project src python -m compileall -q src/modules src/lang` 与 `git diff --check` 均通过，只有 Git 的 LF/CRLF 策略提示。

## 尚未执行或失败的验证

- 未构建 ZUV、Windows EXE 或 Linux ELF。
- 未运行 GitHub Actions。
- 已连接真实 Forza Data Out 并完成四驱低速 raw rotation、新优先级、真实 L2 扳机键 ABS wall 和四种实际材质。前驱/后驱实机验证由用户取消，不再列为失败或发布门槛。
- USB 与 Bluetooth 已完成 synthetic wheelspin、关键 surface 和 ABS wall 手感验证；DSX 未执行，并已明确不作为当前任务或发布门槛。
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

建议首先处理的具体任务：不要继续加算法功能。先完成最终回归，再准备 Enhanced R2 的版本号、README、Release workflow 与构建产物；不安排前驱/后驱或 DSX 实机验证。

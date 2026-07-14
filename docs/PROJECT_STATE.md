# 项目当前状态

## 状态快照

- 最后更新：2026-07-14，Asia/Shanghai。
- 仓库：`piereacy/FH-DualSense-Enhanced`。
- 当前分支：`main`，跟踪 `origin/main`。
- 本轮修复基线：`5e809d2 docs: integrate multilingual README on one page`。交付后的当前 HEAD 应使用 `git log -1 --oneline` 读取，避免文档因自身提交再次过期。
- 版本：`1.6.2.post1`，Release workflow 命名为 `FH-DualSense-Enhanced 1.6.2 Enhanced R1`。
- Git 历史：审计开始时本地是 shallow clone，只有 7 条已有提交，因此无法从本地恢复上游完整历史。
- 当前阶段：Enhanced R1 已实现并发布，已完成文档和退出行为收尾；Enhanced R2 的功能方向已经讨论确认，但生产代码尚未开始修改。

## 当前开发重心

1. 长期交接文档已经建立，并已随本轮代码事实同步。
2. README 同页三语言导航、Linux udev 文档和自动退出开关已修复，当前全量测试通过。
3. 下一阶段直接进入 Enhanced R2，聚焦动态轮胎打滑和 GT7 风格 ABS wall，同时保留 USB 和 Bluetooth。

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

## 正在进行的工作

### 长期文档体系

代码状态：长期文档已经建立。本轮额外修改了 loop 退出条件、README 契约测试和 Linux 使用文档，未修改 R2 生产逻辑。

- `AGENTS.md` 已从旧的英文项目地图更新为稳定的中文工作指引。
- `docs/ARCHITECTURE.md` 已按当前代码记录真实架构和技术债。
- `docs/PROJECT_STATE.md` 已记录当前版本、R2 边界和验证状态。

### Enhanced R2 设计方向

状态：本次会话已确认方向，仓库中没有 R2 实现、测试或正式设计文件。以下内容不能视为已实现。

动态轮胎打滑的已确认方向：

- 只让油门导致的 driven wheel longitudinal slip 进入 R2；松油漂移继续只进入握把触觉。
- slip 是主信号，G force 仅作约 20% 到 30% 的温和反向 damping。
- 保留路面材质 signature，不改成单一频率的无差别震动。
- 使用一个主 threshold 加 hysteresis；极低速继续依赖 raw wheel rotation 识别烧胎。
- 使用按时间计算的非对称 EWMA，进入快、释放慢。讨论目标约为 30 到 50 ms 建立、100 到 150 ms 释放，最终常量待测试确认。
- 普通 UI 暴露 strength 和 sensitivity；高级 band、G damping、smoothing、hysteresis 和 burnout threshold 放入折叠的“实验性功能”，并显示“不建议自行调节”。

GT7 风格 ABS wall 的已确认方向：

- L2 顶部约 3 个 zone 保持高强度 wall，下部 zone 产生 ABS vibration。
- longitudinal tire slip ratio 为主信号，combined slip 只作辅助。
- `5..8 km/h` 只作为低速 gating，不按车速决定 ABS 强度。
- pulse frequency 和 amplitude 随 slip 动态变化，并保留约 80 到 120 ms，最终值待测试确认。
- native USB/BT 使用完整 zoned wall；DSX 无法等价表达时回退为动态 vibration，不伪装成完整 wall。
- 升级现有 ABS 和 wheelspin 行为，不保留 legacy mode。
- 实验参数作为 Profile 级设置，以便按车辆保存。
- 预定实现位置是现有 `TriggerAnimations` 加一个小型共享 smoothing helper，保持 `Controller` priority 和现有 transport 边界。

## 尚未完成的工作

### 代码中尚未实现

- 动态轮胎打滑频率和强度映射。
- wheelspin 的时间型 EWMA、hysteresis 和 G force damping。
- GT7 风格 ABS zoned wall、动态 pulse 和 hold deadline。
- DSX 的 R2/ABS 退化策略。
- 折叠的“实验性功能”GUI/TUI section、警告文案和所有语言翻译。
- R2 参数的 Profile round-trip、分享码兼容和默认值测试。

### 仍存在的代码注释不一致

- `src/modules/forzahorizon/effects.py` 的注释把已存在的 `idle_buzz()` 写成 `future enhancement`。
- `src/modules/config/settings.py` 的 serial 注释与 `src/modules/dualsense/main.py` 的 USB MAC backfill 和 USB 优先去重逻辑表面冲突，正确文案待硬件枚举结果再次确认。

### 根据代码推测，尚未验证

- `packaging/linux/build_elf.sh` 没有像 CI 一样向 `uvx` 显式加入 `numpy` 和 `sounddevice`。本地 Linux build 可能缺少 body haptics 依赖，但本次未在 Linux 执行，结论待确认。
- 根 README 与两个独立语言 README 同时保留，后续修改容易造成内容漂移。目前未逐段建立自动同步机制。

## 下一步建议顺序

1. 为 R2 增加失败测试，先覆盖 driven wheel longitudinal slip、松油漂移不进 R2、低速 raw rotation、surface signature、EWMA 时间常数和 hysteresis。
2. 在 `src/modules/forzahorizon/effects.py` 实现动态 wheelspin，并保持现有 `Controller.R2()` priority。
3. 增加 ABS zoned wall、dynamic pulse、hold 和 DSX fallback 测试，再实现 ABS 行为。
4. 将 R2 参数加入 `src/modules/config/settings.py`，明确普通参数和 experimental 参数，验证 Profile scope 和分享码兼容。
5. 同步 GUI、TUI 和 `src/lang/` 所有 catalog，加入折叠 experimental section 和警告文案。
6. 运行全量测试，再分别进行 USB、Bluetooth 和 DSX 真实设备验证。
7. R2 行为稳定后更新 README、Release workflow 文案、版本和 Release，不提前把设计写成已发布功能。

## 当前已知 Bug

当前自动化测试没有失败项。README 导航契约和 `exit_on_game_close` 断流行为已修复，并增加回归测试。

真实 USB、Bluetooth 和游戏遥测本次未测试，因此硬件路径是否还有设备特有 Bug 仍待实机验证。

## 当前技术债

- 遥测是无类型 `dict`，缺少结构化 schema。
- GUI/TUI 设置定义重复维护。
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
- 版本号和 Release workflow，直到 R2 实现和验证完成。

## 最近涉及的关键文件

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

本轮交付包含长期文档、README、Release 文案、loop 和测试。完成提交与推送后，目标状态为 `main` 与 `origin/main` 同步且工作区干净；任务结束时必须用 `git status --short --branch` 再确认。

## 已执行的测试和验证

本次审计已执行：

- `git status --short --branch`：写文档前工作区干净。
- `git diff`、`git diff --cached`：写文档前均为空。
- `git log -10`：因 shallow clone 仅返回本地全部 7 条提交。
- `rg` 搜索 `TODO`、`FIXME`、`HACK`、`NotImplemented` 和独立 `pass`：没有发现明确未实现函数；`pass` 均位于异常抑制、preview KeyboardInterrupt、DSX intentional no-op 或测试 stub。
- 定向回归：同页语言导航、删除 TR、Linux udev 文档、自动退出启用和禁用路径，共 `4 passed`。
- `uv run --project src pytest -q`：`127 passed`。
- `git diff --check`：写文档前通过，交付前需要复跑。

## 尚未执行或失败的验证

- 未构建 ZUV、Windows EXE 或 Linux ELF。
- 未运行 GitHub Actions。
- 未在本次任务连接 Forza Data Out 做实时遥测测试。
- 未在本次任务进行 USB、Bluetooth 或 DSX 实机验证。
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
7. 与 R2 相关时再读 `src/modules/dualsense/adaptive_trigger.py`、`src/modules/dsx/dsx_wrapper.py` 和 `tests/dualsense/test_output_report.py`

建议首先处理的具体任务：按 TDD 顺序实现动态 wheelspin，完成后再实现 GT7 风格 ABS wall。

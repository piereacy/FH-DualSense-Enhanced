# 项目当前状态

## 状态快照

- 最后更新：2026-07-15，Asia/Shanghai。
- 仓库：`piereacy/FH-DualSense-Enhanced`。
- 当前分支：`feat/r3-traction-redline`，隔离工作树为 `.worktrees/r3-traction-redline`。
- 当前开发身份：内部 PEP 440 版本 `3`，运行时、Windows 版本资源和公开候选名称均为 `R3`。
- 当前公开稳定版：Enhanced R2，tag `R2`。Enhanced R3 已获得正式发布授权，等待最终提交、`main` 推送和 `R3` workflow。
- 当前已提交规格基线：`97f2991 docs: design R3 release closeout`。Bluetooth HD haptics、默认值、测试和发布文档仍在当前工作区等待最终提交。
- 当前阶段：Enhanced R3 发布收尾。Bluetooth HD haptics 已完成生产代码、自动测试、硬件协议探针、完整 EXE 构建和用户 Forza 体验确认；正在执行最终 Git 审计和正式发布。

## 当前开发重心

当前重心是保持已经验证的 USB/Bluetooth 共享 PCM 和 `0x36` 路径不变，完成红线默认开关、中文公开说明、Release 资产和远端状态的最终一致性检查。用户已授权创建稳定 `R3`；只有最终 diff、全量测试和构建校验保持通过后才能推送标签。

## 最近完成的功能

以下内容已有生产代码和自动测试证明：

- 新增 `src/modules/haptics/pcm.py`：USB 与 Bluetooth 共用 65 Hz low、190 Hz composite high、动态 engine saw、相位和 `0.35` block smoothing。
- `src/modules/haptics/audio.py` 改为由共享 `HapticPcmRenderer` 生成左右 PCM，USB 仍输出 48 kHz、512-frame、四声道中的 channel 3/4。
- 新增 `src/modules/dualsense/bt_haptics.py`：构建 398 字节 report `0x36`，包含 63 字节 L2/R2 state、64 字节左右交错 int8 haptics、独立序列和 Bluetooth CRC；不声明 speaker block。
- 新增 `src/modules/haptics/bt_audio.py`：以 3 kHz、32-frame、约 10.667 ms 周期生成 Bluetooth PCM，并通过 `DualSense` 单槽队列交给原 HID I/O thread 串行发送。
- `HapticManager` 现在以 Bluetooth HD haptics 为首选；当前连接拒绝 `0x36` 时才回退到 compatible rumble，重连后重新尝试。禁用、切换和断开会发送静音采样。
- Windows 定时器已改为 `time.sleep()` 高精度 waitable timer，并修复 HID wake event 的 clear/check 顺序。旧 `Event.wait()` 实测约 65 Hz、1.5 秒覆盖 48 块；当前实测平均 `10.668 ms`、最大 `11.204 ms`、零覆盖。
- `src/modules/config/settings.py` 把隐藏的握把换挡冲击改成独立 Profile 功能：`enable_grip_gear_shift_haptics=False`、`grip_gear_shift_strength=0.8`、`grip_gear_shift_duration_ms=100.0`。
- `src/modules/haptics/mixer.py` 只在开关启用、速度高于 `3 km/h`、正挡发生变化时产生双侧 low 冲击。关闭开关会立即清除 active deadline，但继续更新挡位基线，重新开启不会补发旧事件。
- 握把换挡不再读取 R2 扳机键的 `enable_gear_shift`、`enable_gear_shift_brake`、`gear_shift_amp` 或 `gear_shift_duration_ms`。
- R3 最终默认关闭 R2 扳机键红线、开启握把红线并只选择左握把；握把侧在基础幅度之后应用 `grip_redline_gain=1.5`，最终仍由 master、duck 和 `clamp01()` 限幅。该值表示信号倍率，不表示感知强度严格增加 50%。
- `src/modules/config/preferences.py` 保留命名 Profile 的显式红线值，并为缺失字段的 Enhanced R2/早期 Enhanced R3 Profile 执行幂等迁移。Default Profile 每次启动使用新默认值。
- GUI/TUI Controls 新增普通 `Grip feedback` 分组；普通 Settings 新增握把换挡强度和持续时间。原扳机分组明确命名为 `R2 trigger gear-shift thump`；只有 `Grip signal gain` 位于实验性设置。
- GUI/TUI 字段顺序一致，TUI Controls 分组标题现也经过翻译层。德语、日语、俄语、土耳其语、简体中文和繁体中文均已补齐新文案。
- 临时夹具名 `community_defaults_2323.json` 已改为正式 `community_defaults.json`。
- 根 `README.md` 的同页中/英/日说明、`docs/ReadmeEN.md`、`docs/ReadmeJA.md` 和 `.github/workflows/release.yml` 已更新为 Enhanced R3。Release body 包含中文功能说明、英文安装信息、上游 `1.6.2` 和 HorizonHaptics `1.3.0` 参考版本。
- GitHub 上既有 `v1.6.2.post1`（Enhanced R1）、`R2` 和 `R2-preview` Release body 已补充中文功能与安装说明，并保留原英文正文、资产、tag 和 prerelease 状态。
- 新建 `docs/DECISIONS.md`，记录原生振动接管延期、握把换挡独立默认关闭和红线 1.5 信号增益决策。

## 已继承且未破坏的能力

- 用户此前已完成真实 Forza 抓地力路由验证：只踩 L2 时进入 L2，只踩 R2 扳机键时进入 R2 扳机键，两者同时踩时进入 R2 扳机键；L2 ABS 可同时存在。
- GT7 风格 ABS zoned wall、动态 EWMA/hysteresis、四类材质频带、G force damping 和低速烧胎识别保留。
- R2 扳机键红线继续使用独立开关，要求踩住油门，松油门立即退出；本轮未修改 `src/modules/forzahorizon/effects.py`。
- 碰撞 detector、方向包络、compatible fallback 的 priority-event 侧别投影和边沿日志保留；正常 Bluetooth 路径不再依赖该投影。
- USB/BT `0x02`/`0x31` trigger layout、trigger flags、motor flags、pending rumble release 和 reconnect 保留；新增 `0x36` report、队列和序列状态，没有改变 `HapticMixer` 的 transport-independent frame。
- DSX adapter 未修改；DSX 仍只提供扳机兼容路径，不提供本项目握把触觉。

## 正在进行的工作

- Bluetooth HD haptics 源码、测试、三语 README、Release body、老三样、第三方声明和最终默认值在当前工作区中，等待一次有意的 R3 实现提交。
- 新 Windows EXE 与 update-enabled ZUV 已重新构建；正在核对 diff、提交范围、`main` 快进关系和唯一的 `R3` 发布触发路径。
- 旧 Enhanced R3 候选工件以及先前发给用户的 Bluetooth 测试 EXE 均不是最终线上资产。

## 尚未完成的工作

1. 完成最终 diff 和提交范围审计，将功能分支快进合入 `main`。
2. 推送 `origin/main` 和稳定标签 `R3`，监控 GitHub Actions 构建 ZUV、Windows EXE 和 Linux ELF。
3. 核对线上 Release 中文正文、资产名称、哈希和下载冒烟。
4. 本地 Linux ELF 构建和真实 Linux DualSense 验证尚未执行；线上 Ubuntu 构建将提供首个 R3 Linux 构建结果。

以下事项明确不属于 Enhanced R3：

- 接管或完整复现 Steam Input/Forza 原生振动。
- R3 ZUV 的移除或替代方案；本轮继续保留现有 ZUV 链路。
- DSX 握把适配和 DSX 实机调校。
- 修改 `R2`、`R2-preview` tag、Release 或既有资产。

## 当前已知 Bug 和待确认风险

- 自动测试没有已知失败项。
- 游戏内原生振动可能掩盖本项目的碰撞左右方向。用户此前确认关闭游戏内振动后方向可以辨认；Enhanced R3 不接管丢失的菜单、过场或上车原生振动。
- 当前碰撞 detector 只使用 jerk 和 `smashable_vel_diff`。旧设计中的 speed-loss fallback 没有实现；只有真实日志证明漏报后才应重新设计。
- Bluetooth `0x36` 已证明能实际驱动执行器且维持 94 Hz，完整 EXE 的 Forza 体验也已由用户确认可用；但没有逐项记录左右/纹理评分和 USB 同场景量化对照，因此不能把“物理输出完全一样”写成已验证事实。
- 不同固件或 Bluetooth adapter 可能拒绝 398 字节 `0x36`。代码会回退 compatible rumble，但回退发生率尚无社区样本。
- GitHub 过去曾漏掉部分 main/tag push 的 Actions event；Enhanced R2 使用手动 `stable` workflow 恢复发布入口，外部根因待确认。
- 红线握把振动已经可辨认但节奏和辨识度仍不完美，R3 后续需要继续调校。
- ZUV/启动器自动更新流程可用但仍需改良，避免用户难以理解独立 EXE、ZUV、本地 bundle 和更新频道之间的区别。
- GUI/TUI 前端的信息层级和交互仍需优化，尤其是普通设置、实验性功能和运行状态之间的导航。

## 当前技术债

- 遥测仍是无类型 `dict`，字段名错误只能在运行时暴露。
- GUI/TUI 设置和控制组重复声明，依赖 AST parity test 防止漂移。
- `wheelspin_*` 内部字段名与 traction/grip UI 术语不一致；直接重命名会破坏 Profile/share-code 兼容。
- DSX 无 ACK 且没有 body haptics。
- USB audio endpoint 依赖名称 heuristic，没有用户选择和多 host API fallback。
- `0x36` haptics-only 封包依据 vDS、DS5Dongle、HID descriptor 和当前固件实测，Sony 没有公开该 PC 协议；旧固件兼容性仍依赖回退。
- Bluetooth 音频调度依赖 Python 3.13 在 Windows 上的高精度 `time.sleep()`；其他 Python/平台的周期抖动需要单独测量。
- 根 README 已集成三种语言，同时保留 `docs/ReadmeEN.md` 和 `docs/ReadmeJA.md`，存在内容漂移风险。
- Release workflow 的正文直接写在 YAML 中，后续版本需要同步修改契约测试。
- 本地 Windows 环境只有 `w64devkit` 简化 bash，无法证明 Linux ELF 构建或运行行为。

## 暂时不要修改的部分

- 已验证的 `src/modules/dualsense/bt_haptics.py` report `0x36` offsets、state/haptics block、序列、CRC 和 haptics-only speaker omission；修改必须同步字节测试和真实硬件探针。
- `src/modules/dualsense/main.py` 的 `0x02`/`0x31` layout、rumble flags、pending release、`0x36` 单槽队列和 event clear/check 顺序。
- `src/modules/forzahorizon/udp_listener.py` 的 324 字节 offsets 与 `recv_latest()` drain 语义。
- `src/modules/loop.py` 的 state-change write gate、静音和 body haptics failure isolation。
- `src/modules/haptics/mixer.py` 中已经过用户验证的静止、滚动、烧胎、路面、悬挂和抓地力 gating。
- `src/modules/config/preferences.py` 的 Default Profile 重建、GLOBAL_FIELDS、atomic write 和现有迁移分支。
- `LICENSE`、`src/modules/about.py` 和 `docs/THIRD_PARTY_NOTICES.md` 的署名与第三方声明。
- Enhanced R2 tag、Release、稳定资产和已发布算法默认值。
- `R3` 已获发布确认，但不得跳过最终 diff、测试和构建检查，也不得移动已经发布的稳定标签来修正文档。

## 最近涉及的关键文件

- `src/modules/config/settings.py`、`src/modules/config/preferences.py`：新默认值和 Profile 迁移。
- `src/modules/haptics/mixer.py`：握把红线增益和独立握把换挡状态机。
- `src/modules/haptics/pcm.py`、`audio.py`、`bt_audio.py`、`manager.py`：共享 PCM、USB/Bluetooth transport 与 fallback。
- `src/modules/dualsense/bt_haptics.py`、`main.py`：`0x36` 协议、HID 队列、调度和失败隔离。
- `tests/haptics/test_pcm.py`、`test_bt_audio.py`、`test_manager.py`、`tests/dualsense/test_bt_haptics.py`、`test_output_report.py`：波形、协议、路由和 I/O 回归。
- `src/modules/gui/controls_tab.py`、`settings_tab.py` 及对应 `src/modules/tui/` 文件：普通/实验性设置入口。
- `src/lang/de.py`、`ja.py`、`ru.py`、`tr.py`、`zh.py`、`zh_tw.py`：新增界面文案。
- `tests/haptics/test_mixer.py`、`tests/test_community_defaults.py`、`tests/test_haptic_settings.py`：行为、迁移、UI 和翻译契约。
- `README.md`、`docs/ReadmeEN.md`、`docs/ReadmeJA.md`、`.github/workflows/release.yml`：Enhanced R3 公开说明和发布正文。
- `AGENTS.md`、`docs/ARCHITECTURE.md`、`docs/DECISIONS.md`：老三样。
- `docs/superpowers/specs/2026-07-15-r3-grip-shift-redline-defaults-design.md`：已批准并提交的设计。
- `docs/superpowers/plans/2026-07-15-r3-grip-shift-redline-defaults.md`：已执行的实施计划。

## 当前 Git 工作区状态

- 当前分支为 `feat/r3-traction-redline`，已提交的发布收尾规格为 `97f2991`。
- `main` 位于另一个工作树，当前本地 `main` 为 `2ea5ab0` 且相对 `origin/main` ahead 1；发布前应先审计该分支关系，不要盲目覆盖远端。
- 当前功能分支尚未设置 upstream，也尚未推送、合并或发布。
- `packaging/zuv/dist`、`packaging/windows/dist` 和 build 目录由 `.gitignore` 排除，不进入提交。
- 当前工作树包含本轮 Bluetooth HD haptics 的未提交源码、测试和文档；以最终 `git status --short --branch` 与 `git diff` 为准。

## 已执行的测试和验证结果

- mixer、frame、迁移定向测试：`89 passed`。
- GUI/TUI、迁移和 mixer 组合定向测试：`99 passed`。
- README、Release、packaging 和 about 定向测试：`26 passed`。
- 最终全量测试：`uv run --project src pytest -q` 为 `242 passed in 3.74s`。
- 源码编译检查：`python -m compileall -q src/modules src/lang` 通过。
- `git diff --check` 通过。
- 包含本轮 Bluetooth HD haptics 的 Windows EXE 构建通过：
  - 路径：`packaging/windows/dist/FH-DualSense-Enhanced-R3.exe`
  - 大小：`37,812,228` bytes
  - SHA-256：`E75386300055FA60C880DB0D04DE7357968775FD644052F11469FD5E372FE6E0`
  - `FileVersion=R3`、`ProductVersion=R3`、`ProductName=FH-DualSense-Enhanced`
  - `--help` 退出码 `0`
  - PyInstaller recursive archive 已确认包含 `modules.dualsense.bt_haptics`、`modules.haptics.bt_audio`、`modules.haptics.pcm` 和 `docs/THIRD_PARTY_NOTICES.md`
- update-enabled ZUV 构建通过：
  - 路径：`packaging/zuv/dist/FH-DualSense-Enhanced.zuv.py`
  - 大小：`1,333,389` bytes
  - SHA-256：`4F678A5A376FF3D61632C6BC0C5BB105368F9955C071E5893E33924600ED5888`
  - 内嵌更新仓库：`piereacy/FH-DualSense-Enhanced`
- 用户此前已真实验证 Enhanced R3 抓地力踏板路由。
- 用户此前确认碰撞方向在关闭游戏内振动后可以辨认，开启原生振动时可能被掩盖。
- 本轮真实 Bluetooth 合成探针：bus `2`、DualSense PID `0x0ce6`。连续 100 个全零 `0x36` 全部被 HID 接受，连接保持、失败标志为 False、零覆盖。
- 本轮真实 Bluetooth 左握把 `0.45` 探针：加速度计候选 offset `23` 的标准差从约 `13.1` 增至约 `1931.2`，证明 haptics-only `0x36` 实际驱动了执行器；探针未运行 Forza，游戏内振动和 Steam Input 状态不适用。
- 本轮完整 manager/renderer/HID 链压力验证：`0x36` 平均发送间隔 `10.668 ms`，最大 `11.204 ms`，单槽覆盖 `0`，连接保持且 `bt_haptics_failed=False`；探针未运行 Forza，游戏内振动和 Steam Input 状态不适用。
- 用户运行包含 Bluetooth HD haptics 的完整 R3 EXE 进入 Forza 后确认“完全没问题”。本次反馈没有记录游戏内振动开关和 Steam Input 状态，因此这两个环境条件标记为待确认；不能据此声称所有电脑、固件和适配器都与 USB 完全一致。

## 尚未执行或未通过的验证

- 本轮新增握把换挡开关/调教和红线 1.5 增益的 USB 实车验证：未执行。
- Bluetooth Forza 的完整 EXE 用户体验已确认可用，但没有逐项记录左右/low/high/engine、碰撞、红线和各路面材质评分，也没有记录游戏内振动和 Steam Input 状态。
- Bluetooth 与 USB 的严格同场景强度量化对照未执行；当前结论是用户主观体验通过，不是两个 transport 的物理输出完全相等。
- 本地 Linux ELF 构建：未执行。本机 `bash.exe` 来自 Windows `w64devkit`，不是可用于验证 Linux 产物的 Linux 环境。
- 真实 Linux DualSense 硬件验证：未执行。
- GitHub Actions Enhanced R3 Release workflow：未执行，等待最终提交和标签推送。
- 线上 Release 资产名称、哈希、中文正文和下载冒烟：未执行，等待发布。

## 下一次会话开始时优先阅读

1. `AGENTS.md`
2. 本文件 `docs/PROJECT_STATE.md`
3. `docs/ARCHITECTURE.md`
4. `docs/DECISIONS.md`
5. `docs/superpowers/specs/2026-07-15-r3-release-closeout-design.md`
6. `docs/superpowers/specs/2026-07-15-r3-bluetooth-hd-haptics-design.md`
7. `docs/superpowers/plans/2026-07-15-r3-bluetooth-hd-haptics.md`
8. `.github/workflows/release.yml`

下一次会话建议首先处理的具体任务：若 R3 已发布，依次处理红线握把节奏、自动更新体验和前端信息架构；若发布流程仍在运行，先核对 Actions、Release 中文正文和全部资产。

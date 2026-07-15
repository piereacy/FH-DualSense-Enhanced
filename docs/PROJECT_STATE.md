# 项目当前状态

## 状态快照

- 最后更新：2026-07-15，Asia/Shanghai。
- 仓库：`piereacy/FH-DualSense-Enhanced`。
- 当前分支：`feat/r3-traction-redline`，隔离工作树为 `.worktrees/r3-traction-redline`。
- 当前开发身份：内部 PEP 440 版本 `3`，运行时、Windows 版本资源和公开候选名称均为 `R3`。
- 当前公开稳定版：Enhanced R2，tag `R2`。Enhanced R3 尚未创建 tag 或 GitHub Release。
- 最新业务提交：`735c334 feat: add optional grip shift haptics`。
- 当前阶段：Enhanced R3 代码、自动测试、三语 README、Release body、Windows EXE 和 ZUV 候选均已完成，停在等待发布确认阶段。

## 当前开发重心

当前不再调算法。下一步是用户确认发布后，把本分支纳入可发布分支、同步远端并触发 `stable` Release workflow。发布前不得再夹带未验证的触觉算法改动。

## 最近完成的功能

以下内容已有生产代码和自动测试证明：

- `src/modules/config/settings.py` 把隐藏的握把换挡冲击改成独立 Profile 功能：`enable_grip_gear_shift_haptics=False`、`grip_gear_shift_strength=0.8`、`grip_gear_shift_duration_ms=100.0`。
- `src/modules/haptics/mixer.py` 只在开关启用、速度高于 `3 km/h`、正挡发生变化时产生双侧 low 冲击。关闭开关会立即清除 active deadline，但继续更新挡位基线，重新开启不会补发旧事件。
- 握把换挡不再读取 R2 扳机键的 `enable_gear_shift`、`enable_gear_shift_brake`、`gear_shift_amp` 或 `gear_shift_duration_ms`。
- 握把红线默认改为关闭；启用后在基础幅度之后应用 `grip_redline_gain=1.5`，最终仍由 master、duck 和 `clamp01()` 限幅。该值表示信号倍率，不表示感知强度严格增加 50%。
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
- 碰撞 detector、方向包络、Bluetooth priority-event 侧别投影和边沿日志保留。
- USB/BT HID report layout、trigger flags、motor flags、BT CRC、pending rumble release 和 reconnect 未修改。
- DSX adapter 未修改；DSX 仍只提供扳机兼容路径，不提供本项目握把触觉。

## 正在进行的工作

- 没有未提交的业务实现。
- 发布候选工件已生成，见“已执行的测试和验证结果”。
- Enhanced R3 tag、GitHub Release、远端分支合并和 stable workflow 尚未执行，正在等待用户发布确认。

## 尚未完成的工作

1. 用户确认后决定采用合并到 `main` 后手动 `stable` workflow，或使用明确的 `release R3` 提交/tag 触发方式；不要同时触发两条发布路径。
2. 等待 GitHub Actions 的 Windows、Linux、bundle 和 Release jobs 全部成功，并核对线上资产 SHA-256、名称、中文说明和 prerelease 状态。
3. 用真实 Forza 重新验证默认关闭后的行为、启用后的 1.5 红线握把增益，以及可选握把换挡强度/持续时间。该验证不阻止代码进入发布候选，但结果目前不能写成已完成硬件调校。
4. 本地 Linux ELF 构建和真实 Linux DualSense 验证尚未执行。

以下事项明确不属于 Enhanced R3：

- 接管或完整复现 Steam Input/Forza 原生振动。
- R3 ZUV 的移除或替代方案；本轮继续保留现有 ZUV 链路。
- DSX 握把适配和 DSX 实机调校。
- 修改 `R2`、`R2-preview` tag、Release 或既有资产。

## 当前已知 Bug 和待确认风险

- 自动测试没有已知失败项。
- 游戏内原生振动可能掩盖本项目的碰撞左右方向。用户此前确认关闭游戏内振动后方向可以辨认；Enhanced R3 不接管丢失的菜单、过场或上车原生振动。
- 当前碰撞 detector 只使用 jerk 和 `smashable_vel_diff`。旧设计中的 speed-loss fallback 没有实现；只有真实日志证明漏报后才应重新设计。
- Bluetooth 使用 low/high motor 作为左右事件的空间代理，不是 USB 四通道的物理左右分离。两种 transport 使用相同事件语义，但执行器体感仍可能不同。
- 新增的握把换挡默认关闭和红线 1.5 增益尚未进行本轮真实硬件复测。
- GitHub 过去曾漏掉部分 main/tag push 的 Actions event；Enhanced R2 使用手动 `stable` workflow 恢复发布入口，外部根因待确认。

## 当前技术债

- 遥测仍是无类型 `dict`，字段名错误只能在运行时暴露。
- GUI/TUI 设置和控制组重复声明，依赖 AST parity test 防止漂移。
- `wheelspin_*` 内部字段名与 traction/grip UI 术语不一致；直接重命名会破坏 Profile/share-code 兼容。
- DSX 无 ACK 且没有 body haptics。
- USB audio endpoint 依赖名称 heuristic，没有用户选择和多 host API fallback。
- USB audio callback 有幅度平滑，Bluetooth 使用 HID compatible rumble。两者输入语义相同，但执行器物理响应仍需分别实测。
- 根 README 已集成三种语言，同时保留 `docs/ReadmeEN.md` 和 `docs/ReadmeJA.md`，存在内容漂移风险。
- Release workflow 的正文直接写在 YAML 中，后续版本需要同步修改契约测试。
- 本地 Windows 环境只有 `w64devkit` 简化 bash，无法证明 Linux ELF 构建或运行行为。

## 暂时不要修改的部分

- `src/modules/dualsense/main.py` 的 USB/BT report layout、rumble flags、BT CRC、pending release 和左右映射。
- `src/modules/forzahorizon/udp_listener.py` 的 324 字节 offsets 与 `recv_latest()` drain 语义。
- `src/modules/loop.py` 的 state-change write gate、静音和 body haptics failure isolation。
- `src/modules/haptics/mixer.py` 中已经过用户验证的静止、滚动、烧胎、路面、悬挂和抓地力 gating。
- `src/modules/config/preferences.py` 的 Default Profile 重建、GLOBAL_FIELDS、atomic write 和现有迁移分支。
- `LICENSE`、`src/modules/about.py` 和 `docs/THIRD_PARTY_NOTICES.md` 的署名与第三方声明。
- Enhanced R2 tag、Release、稳定资产和已发布算法默认值。
- 发布确认前不要创建 `R3` tag、上传资产或触发 stable workflow。

## 最近涉及的关键文件

- `src/modules/config/settings.py`、`src/modules/config/preferences.py`：新默认值和 Profile 迁移。
- `src/modules/haptics/mixer.py`：握把红线增益和独立握把换挡状态机。
- `src/modules/gui/controls_tab.py`、`settings_tab.py` 及对应 `src/modules/tui/` 文件：普通/实验性设置入口。
- `src/lang/de.py`、`ja.py`、`ru.py`、`tr.py`、`zh.py`、`zh_tw.py`：新增界面文案。
- `tests/haptics/test_mixer.py`、`tests/test_community_defaults.py`、`tests/test_haptic_settings.py`：行为、迁移、UI 和翻译契约。
- `README.md`、`docs/ReadmeEN.md`、`docs/ReadmeJA.md`、`.github/workflows/release.yml`：Enhanced R3 公开说明和发布正文。
- `AGENTS.md`、`docs/ARCHITECTURE.md`、`docs/DECISIONS.md`：老三样。
- `docs/superpowers/specs/2026-07-15-r3-grip-shift-redline-defaults-design.md`：已批准并提交的设计。
- `docs/superpowers/plans/2026-07-15-r3-grip-shift-redline-defaults.md`：已执行的实施计划。

## 当前 Git 工作区状态

- 当前分支为 `feat/r3-traction-redline`，最新业务提交为 `735c334`。
- `main` 位于另一个工作树，当前本地 `main` 为 `2ea5ab0` 且相对 `origin/main` ahead 1；发布前应先审计该分支关系，不要盲目覆盖远端。
- 当前功能分支尚未设置 upstream，也尚未推送、合并或发布。
- `packaging/zuv/dist`、`packaging/windows/dist` 和 build 目录由 `.gitignore` 排除，不进入提交。
- 本文件提交完成后工作树应为干净状态；以最终 `git status --short --branch` 为准。

## 已执行的测试和验证结果

- mixer、frame、迁移定向测试：`89 passed`。
- GUI/TUI、迁移和 mixer 组合定向测试：`99 passed`。
- README、Release、packaging 和 about 定向测试：`26 passed`。
- 最终全量测试：`uv run --project src pytest -q` 为 `222 passed`。
- 源码编译检查：`python -m compileall -q src/modules src/lang` 通过。
- `git diff --check` 通过。
- Windows EXE 构建通过：
  - 路径：`packaging/windows/dist/FH-DualSense-Enhanced-R3.exe`
  - 大小：`37,800,499` bytes
  - SHA-256：`8C0731C59DF00C9914F61921E6BB17F87D81CA0696165C1EE55ACFFF5A0EA708`
  - `FileVersion=R3`、`ProductVersion=R3`、`ProductName=FH-DualSense-Enhanced`
  - `--help` 退出码 `0`
- update-enabled ZUV 构建通过：
  - 路径：`packaging/zuv/dist/FH-DualSense-Enhanced.zuv.py`
  - 大小：`1,329,729` bytes
  - SHA-256：`94A866BBF9BC71002CEA7A7AC027818AB04932197030697279DDCA15ABC087DA`
  - 内嵌更新仓库：`piereacy/FH-DualSense-Enhanced`
- 用户此前已真实验证 Enhanced R3 抓地力踏板路由。
- 用户此前确认碰撞方向在关闭游戏内振动后可以辨认，开启原生振动时可能被掩盖。

## 尚未执行或未通过的验证

- 本轮新增握把换挡开关/调教和红线 1.5 增益的 USB 实车验证：未执行。
- 同一新增行为的 Bluetooth 实车验证：未执行。
- 本地 Linux ELF 构建：未执行。本机 `bash.exe` 来自 Windows `w64devkit`，不是可用于验证 Linux 产物的 Linux 环境。
- 真实 Linux DualSense 硬件验证：未执行。
- GitHub Actions Enhanced R3 Release workflow：未执行，等待发布确认。
- 线上 Release 资产名称、哈希、中文正文和下载冒烟：未执行，等待发布。

## 下一次会话开始时优先阅读

1. `AGENTS.md`
2. 本文件 `docs/PROJECT_STATE.md`
3. `docs/ARCHITECTURE.md`
4. `docs/DECISIONS.md`
5. `docs/superpowers/specs/2026-07-15-r3-grip-shift-redline-defaults-design.md`
6. `docs/superpowers/plans/2026-07-15-r3-grip-shift-redline-defaults.md`
7. `.github/workflows/release.yml`

下一次会话建议首先处理的具体任务：在用户明确确认发布后，先审计 `feat/r3-traction-redline`、本地 `main` 和 `origin/main` 的提交关系，再选择唯一发布触发路径；合并并推送后等待 GitHub Actions 全部成功，核对 Enhanced R3 Release 和所有线上资产。

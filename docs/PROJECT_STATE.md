# 项目当前状态

## 状态快照

- 最后更新：2026-07-15，Asia/Shanghai。
- 仓库：`piereacy/FH-DualSense-Enhanced`。
- 当前分支：`feat/r3-traction-redline`，隔离工作树为 `.worktrees/r3-traction-redline`。
- 当前开发身份：内部 PEP 440 版本 `3`，运行时和 Windows 版本资源显示 `R3`。
- 当前稳定发布：Enhanced R2，tag `R2`。R3 尚未创建 tag 或 GitHub Release。
- 最新业务提交：`4bd541d feat: expose R3 redline and collision controls`。
- 当前阶段：R3 红线和碰撞增强的代码、自动测试及本地产物已完成，等待 USB 和 Bluetooth 真实 Forza 手感验收。

## 当前开发重心

1. 用新构建验证 R2 扳机键红线与握把红线能同时保留且互不共用开关。
2. 验证默认仅左握把的红线断油脉冲能从路面和发动机背景中辨认。
3. 验证碰撞的主冲击、间隔、弱回弹和方向性，并通过新日志区分 detector 与混音问题。
4. 分别验证 USB 四通道音频和 Bluetooth compatible rumble；两种传输使用同一事件语义，不预设强弱差异。
5. 本轮只提供本地 R3 测试产物，不创建 R3 tag，不发布 GitHub Release，不开发 DSX 握把适配。

## 最近完成的功能

以下项目均已由生产代码和自动测试确认，但新握把手感尚未由真实硬件验收：

- `src/modules/config/settings.py` 将 R2 扳机键红线和握把红线拆成独立配置。扳机默认 `30/12`，握把默认左开右关、进入 `0.93`、退出 `0.90`、10 Hz、强度 `192/255`、low ratio `0.25`。
- `src/modules/config/preferences.py` 增加幂等迁移。R2 命名 Profile 保留扳机参数并获得握把默认值；早期内部版本 3 预览会把曾复用的 `rev_limit_*` 拆分到新的握把字段。
- `src/modules/forzahorizon/effects.py` 恢复 R2 扳机键 `rev_buzz()`。它要求踩住油门，松油门立即清 hold；优先级为 gear、idle、traction、rev、wall、resistance。
- `src/modules/haptics/mixer.py` 实现独立握把红线状态机。默认仅左握把输出 10 Hz 断油脉冲，进入和退出有 hysteresis 和边沿日志；红线 active 时连续背景和 engine 默认压至 30%，transient 不随红线压低。
- 同一 mixer 实现碰撞事件重整：保留 jerk 和 `smashable_vel_diff` 检测源，增加 arm/cooldown、主冲击、短间隔、弱回弹、主侧与弱侧以及事件日志。碰撞 active 时其余握把能量默认压至 20%。
- `src/modules/haptics/frame.py` 增加可选 compatible motor override。普通路面继续按频率下混；红线和碰撞 active 时显式把左侧事件投影到 Bluetooth low-frequency motor、右侧事件投影到 high-frequency motor。
- GUI 和 TUI 已分别提供 R2 扳机键红线、握把红线、左握把、右握把开关。握把 release/low ratio/背景压低和碰撞参数位于默认折叠的实验性功能区域，并标明不建议自行调节。
- `src/lang/de.py`、`ja.py`、`ru.py`、`tr.py`、`zh.py`、`zh_tw.py` 已补齐新设置文案；简体中文明确使用“R2 扳机键”避免与 R2 版本混淆。

## 已继承且未破坏的能力

- 已通过用户实车手感验证的抓地力路由保持不变：只踩 L2 时进入 L2，只踩 R2 扳机键时进入 R2 扳机键，两者同时踩时进入 R2 扳机键；L2 ABS 仍可同时存在。
- GT7 风格 ABS zoned wall、动态 EWMA/hysteresis、四类材质频带和 G force damping 保留。
- USB/BT HID report layout、trigger flags、motor flags、BT CRC、pending rumble release 和 reconnect 输出未修改。
- 静止、滚动、原地轰油、低速烧胎、路面材质、积水、悬挂和换挡的既有 gating 保留。
- DSX adapter 未修改；DSX 仍只提供扳机兼容路径，不提供本项目握把触觉。
- R2 tag、Release、公开资产和 README 稳定版说明未修改。

## 正在进行的工作

- 代码和本地构建已结束，当前唯一进行中的交付步骤是真实 Forza 硬件验收。
- 本地测试产物：
  - `packaging/windows/dist/FH-DualSense-Enhanced-R3.exe`
  - `packaging/zuv/dist/FH-DualSense-Enhanced.zuv.py`
- 实机时优先观察日志 `Grip redline entered/exited` 与 `Collision armed`。有日志但体感不清说明混音或幅度仍需调校；没有日志说明 detector 或遥测输入需要继续排查。

## 尚未完成的工作

1. USB 下验证 R2 扳机键红线、默认左握把红线、碰撞主冲击与弱回弹。
2. Bluetooth 下重复同一语义测试，重点确认红线和碰撞的侧别投影。
3. 根据事件日志和用户体感决定是否调整默认参数。当前参数只是代码和自动测试通过，不能写成硬件最终调校。
4. 用户验收后补充硬件记录，再决定是否进入 R3 发布准备。
5. Linux 本地 R3 构建和真实 Linux 硬件验证尚未执行。

以下事项明确不属于本轮：

- R3 ZUV 的保留、替换或迁移方案留待后续讨论，本轮继续保留现有 ZUV 链路。
- DSX 握把适配和 DSX 实机调校。
- 更新 `R2`、`R2-preview` tag 或资产。

## 当前已知 Bug 和待确认风险

- 自动测试没有已知失败项。
- 新红线与碰撞实现尚未进行真实 Forza 验收，不能确认其辨识度已经解决。旧实现在实车测试中无法从背景振动中明确辨认，此结论只适用于旧实现。
- 当前碰撞 detector 仍只使用 jerk 和 `smashable_vel_diff`。设计文档中的 speed-loss fallback 没有实现；只有当真实日志证明现有 detector 漏报时才考虑增加，当前状态为待确认。
- Bluetooth 的左右事件使用两个不同频率 motor 作为空间代理，这是硬件协议约束下的投影，不是四通道左右分离。真实侧别辨识度待确认。
- GitHub 过去没有为部分 main/tag push 交付 Actions event，R2 曾通过手动 `stable` workflow 恢复入口发布；外部根因待确认。

## 当前技术债

- 遥测仍是无类型 `dict`，字段名错误只能在运行时暴露。
- GUI/TUI 设置和控制组重复声明，依赖 AST parity test 防止漂移。
- `wheelspin_*` 内部字段名与 traction/grip UI 术语不一致；直接重命名会破坏 Profile/share-code 兼容。
- DSX 无 ACK 且没有 body haptics。
- USB audio endpoint 依赖名称 heuristic，没有用户选择和多 host API fallback。
- USB audio callback 有幅度平滑，Bluetooth 使用 HID compatible rumble。两者输入语义相同，但执行器物理响应仍需分别实测。
- 根 README 与 `docs/ReadmeEN.md`、`docs/ReadmeJA.md` 有重复内容，存在漂移风险。
- 本地 Linux build 的 audio dependency 完整性仍未在 Linux 主机验证。

## 暂时不要修改的部分

- `src/modules/dualsense/main.py` 的 USB/BT report layout、rumble flags、BT CRC、pending release 和左右映射。
- `src/modules/forzahorizon/udp_listener.py` 的 324 字节 offsets 与 `recv_latest()` drain 语义。
- `src/modules/loop.py` 的 state-change write gate、静音和 body haptics failure isolation。
- `src/modules/haptics/mixer.py` 中已验证的静止、滚动、烧胎、路面和悬挂 gating。
- `src/modules/config/preferences.py` 的 Default Profile 重建、GLOBAL_FIELDS、atomic write 和 R2/早期 R3 精确迁移。
- `LICENSE`、`src/modules/about.py` 和 `docs/THIRD_PARTY_NOTICES.md` 的署名与第三方声明。
- R2 tag、Release、稳定资产和已发布算法默认值。

## 最近涉及的关键文件

- `src/modules/config/settings.py`、`src/modules/config/preferences.py`：红线拆分默认值和迁移。
- `src/modules/forzahorizon/effects.py`：R2 扳机键红线和 effect priority。
- `src/modules/haptics/frame.py`：兼容振动 override。
- `src/modules/haptics/mixer.py`：握把红线、碰撞包络、混音压低和事件日志。
- `src/modules/gui/controls_tab.py`、`settings_tab.py` 及对应 `src/modules/tui/` 文件：设置入口。
- `src/lang/` 六个非英语 catalog：R3 文案。
- `tests/forzahorizon/test_effects.py`、`tests/haptics/test_mixer.py`、`tests/haptics/test_frame.py`、`tests/test_community_defaults.py`、`tests/test_haptic_settings.py`：行为和迁移契约。
- `docs/superpowers/specs/2026-07-15-r3-redline-collision-contrast-design.md`：用户批准的设计。
- `docs/superpowers/plans/2026-07-15-r3-redline-collision-contrast.md`：已经执行完毕的逐文件计划。

## 当前 Git 工作区状态

- 当前分支为 `feat/r3-traction-redline`，最新业务提交为 `4bd541d`。
- 本次文档提交后应为干净工作区；准确状态必须以 `git status --short --branch` 为准。
- `packaging/zuv/dist` 和 `packaging/windows/dist` 由 `.gitignore` 排除，不进入提交。
- 当前分支尚未推送或发布。不要把本地内部版本 `3` 当成公开 R3 Release。

## 已执行的测试和验证结果

- 配置默认值和迁移定向测试：`23 passed`。
- effects、DSX 和 HID 定向测试：`50 passed`。
- frame、manager、HID 和 reconnect 定向测试：`36 passed`。
- 握把红线及 loop 定向测试：`90 passed`。
- 碰撞及 loop 定向测试：`106 passed`。
- GUI/TUI 和语言定向测试：`19 passed`。
- about 和发布契约定向测试：`22 passed`。
- 当前全量测试：`uv run --project src pytest -q` 为 `211 passed`。
- 源码编译检查：`uv run --project src python -m compileall -q src/modules src/lang` 通过。
- 曾执行过范围错误的 `uv run --project src python -m compileall -q src tests`，它递归进入 `src/.venv/site-packages` 并与并行 pytest 争用第三方包 `__pycache__`，因此失败。该命令不代表项目源码编译失败，后续应使用上一条仓库规定范围。
- update-enabled ZUV 构建通过。`uvx zuv inspect` 显示 version `3`、entry `main.py`、volume `data`、update repo `piereacy/FH-DualSense-Enhanced`。文件大小 `1,329,019` bytes，文件 SHA-256 为 `EE0912914A260BA8F919E0B10A139689ED6DD77F5CD991631538D09321644055`。
- Windows EXE 构建通过。文件大小 `37,795,806` bytes，SHA-256 为 `F8D408E1B9BB5D8905FF40AC2B1AF2DA522663D39AEA49B692CAF9B68DB70D49`。
- EXE 检查：`FileVersion=R3`、`ProductVersion=R3`、`ProductName=FH-DualSense-Enhanced`、associated icon `32x32`、`--help` 退出码 `0`。
- R3 抓地力路由已经按用户引导完成真实 Forza 手感验证。
- 本轮新红线和新碰撞实现的 USB/Bluetooth 硬件验证未执行。

## 下一次会话开始时优先阅读

1. `AGENTS.md`
2. 本文件 `docs/PROJECT_STATE.md`
3. `docs/ARCHITECTURE.md`
4. `docs/superpowers/specs/2026-07-15-r3-redline-collision-contrast-design.md`
5. `src/modules/haptics/mixer.py` 与 `tests/haptics/test_mixer.py`
6. `src/modules/forzahorizon/effects.py` 与 `tests/forzahorizon/test_effects.py`

下一次会话建议首先处理的具体任务：使用本地 `FH-DualSense-Enhanced-R3.exe` 做 USB 红线和碰撞实机测试，先确认事件日志是否出现，再判断 detector 或混音是否需要调整；随后用 Bluetooth 重复同一组测试。

# 项目当前状态

## 状态快照

- 最后更新：2026-07-15，Asia/Shanghai。
- 仓库：`piereacy/FH-DualSense-Enhanced`。
- 当前开发分支：`feat/r3-traction-redline`，隔离工作树为 `.worktrees/r3-traction-redline`。
- 当前功能提交：`66595cb feat: route traction and move redline to grips`。设计和计划提交分别为 `462664a`、`49ff4a2`；文档提交后的准确 HEAD 以 `git log -1 --oneline` 为准。
- 当前开发身份：内部 PEP 440 版本 `3`，运行时显示 `R3`。R3 尚未创建 tag 或 GitHub Release。
- 当前稳定发布：Enhanced R2，tag `R2` 指向 `1cc4520`，公开地址为 `https://github.com/piereacy/FH-DualSense-Enhanced/releases/tag/R2`。
- 当前阶段：R3 抓地力路由和红线握把警告已经完成代码、自动测试和本地 Windows 测试产物，等待用户进行真实 Forza 手感验证。

## 当前开发重心

1. 让用户在真实 Forza 中判断双侧红线脉冲能否从连续发动机握把底振中被明确感知。
2. 验证通用抓地力按 Forza 踏板遥测路由：只踩刹车进入 L2，只踩油门进入 R2，同时踩下只进入 R2；ABS 继续作为独立 L2 高优先级 effect。
3. USB 与 Bluetooth 必须使用相同红线触发条件、phase、hold 和归一化强度。当前代码只区分现有底层传输/合成路径，不定义蓝牙降级或强度较低。
4. 本轮只生成本地 R3 测试产物，不创建 R3 tag，不发布 GitHub Release，不开发 DSX 握把适配。

## 最近完成的功能

### 已由代码和自动测试确认

- `src/modules/forzahorizon/effects.py` 新增 `traction_buzz()`，每个 telemetry tick 只生成一份有状态抓地力 effect，再由 `Controller.update()` 路由到一个扳机键。
- 抓地力路由使用 Forza Data Out 的 `brake`/`accel`，不读取 DualSense 物理 input report。路由表由 `tests/forzahorizon/test_effects.py` 覆盖。
- 高速油门单独使用 driven wheels 的绝对 longitudinal slip；刹车参与时使用四轮最大绝对 longitudinal slip。低速只在油门参与时使用 driven-wheel raw rotation，纯刹车不会用 rotation 猜测抓地力。
- 双踏板时通用抓地力只进入 R2 扳机键，L2 仍可同时输出 GT7 风格 ABS zoned wall。
- R2 扳机键的 rev-limiter effect 已删除。当前 R2 扳机键优先级为 gear shift、idle、traction、end wall、resistance；L2 为 gear shift、ABS、traction、end wall、static wall、resistance。
- `src/modules/haptics/mixer.py` 已实现双侧同步红线握把警告。默认触发条件是油门达到 deadzone 且 `rpm / max_rpm >= 0.93`，脉冲为 10 Hz、50% duty、强度 `96/255`，跌破阈值后 hold 120 ms。
- 红线脉冲叠加到左右 `high` 通道，连续 `engine_hz`/`engine_amplitude` 保留。Body Haptics 总开关、master、`engine_haptics_intensity` 和 `enable_rev_limiter` 均能门控；运行时关闭效果会立即清除已有 hold。
- `tests/haptics/test_mixer.py` 已覆盖立即 on、on/off phase、hold、双侧对称、阈值和油门门控、动态关闭以及 `to_compatible_rumble()` 对同一 normalized envelope 的映射。
- `src/modules/config/preferences.py` 会迁移内部版本 `2` 的命名 Profile：仅当 `rev_limit_freq/rev_limit_amp` 仍等于旧默认值 `30/12` 时改为 `10/96`，自定义值保持不变。`Default` Profile 仍按 R3 代码默认值重建。
- GUI/TUI 已使用 `Redline grip warning` 和 `Traction/grip feedback` 文案，共享效果从 R2 专属控制组移到 `Shared feedback`。六个非英语 catalog 已同步。
- Body Haptics 提示已改为 USB 与 Bluetooth 使用相同触觉混合，只是传输路径不同；代码和 UI 不再声称 Bluetooth 不如 USB。
- `src/pyproject.toml` 与 `src/uv.lock` 已切换到内部版本 `3`。发布契约测试将当前开发身份 R3 与 README 仍记录的稳定 R2 分开。

### 继承且未改动的 R2 能力

- GT7 风格 ABS wall、动态 EWMA/hysteresis、四类材质频带和 G force damping 继续保留。
- USB/BT HID report layout、trigger flags、motor flags、BT CRC、pending rumble release 和 reconnect 输出未修改。
- USB 四声道 audio、Bluetooth compatible rumble、静止/滚动/烧胎/路面 gating、碰撞和悬挂方向性未重构。
- DSX adapter 和 zoned ABS fallback 未修改；DSX 仍不提供本项目握把触觉。
- 稳定 R2 tag、Release、公开资产和 README 稳定版说明未修改。

## 正在进行的工作

- 代码和产物已经达到可测试状态，当前只等待用户在真实 Forza 中验证手感。
- 用户反馈后，需要把 USB/Bluetooth 的实际结果补回本文件，并据此决定是否只调红线 envelope 或进入 R3 发布设计。

## 尚未完成的工作

### R3 必须由用户完成的实车验证

- 普通高转但低于阈值时，不应出现红线握把脉冲。
- 持续达到红线时，双侧断油式脉冲应能从连续发动机底振中被辨认。
- 快速升挡穿越红线时，120 ms hold 不应表现为杂乱断续。
- 抓地力与红线同时发生时，轮胎状态留在相应扳机键，发动机红线留在双侧握把。
- USB 与 Bluetooth 各测试一轮；验收目标是逻辑、时序和归一化强度一致，不预设一方较弱。

### 已记录但不属于本轮交付

- R3 ZUV 的保留、替换或迁移方案按用户决定留到后续讨论。本轮继续构建现有 ZUV，不删除 R1/R2 的 latest-asset 兼容链。
- R1/R2 GitHub Release body 的中文说明已经有设计提交 `2ea5ab0`，但远端 Release body 更新未在当前 R3 工作中执行。`AGENTS.md` 已加入“每个 Release body 必须有中文功能说明”的长期规则。
- DSX 不做实机调校和握把适配，除非用户以后重新提出。
- R3 不发布，不修改 `R2`/`R2-preview` tag 或资产。

## 下一步建议执行顺序

1. 完成本地 ZUV 和 Windows EXE 构建检查。
2. 用户先用默认值在真实 Forza 测试红线握把辨识度，再测试抓地力与红线并发。
3. 若脉冲不明显，优先只调整 `rev_limit_amp`、`rev_limit_freq` 或 duty/波形，不改 USB/BT 分支，不把红线重新放回 R2 扳机键。
4. 用户确认后补充真实硬件记录，再决定是否提交、推送和发布 R3。
5. R3 发布前另行处理 Release 中文说明和 ZUV 生命周期，不把这两个议题混入当前手感验证。

## 当前已知 Bug

- 自动测试没有已知失败项。
- 红线握把脉冲是否足够从连续发动机底振中被真实感知尚未验证，这是当前唯一关键验收风险，不得写成已解决。
- 旧 R2 的 `wheelspin_*` 字段名继续存在，但 UI 已显示 traction/grip。这是刻意的 Profile 兼容策略，不是运行时错误。
- GitHub 过去没有为部分 main/tag push 交付 Actions event，R2 通过已验证的手动 `stable` workflow 恢复入口发布；外部根因仍待确认。

## 当前技术债

- 遥测仍是无类型 `dict`，字段名错误只能在运行时暴露。
- GUI/TUI 设置和控制组重复声明，依赖 AST parity test 防止漂移。
- `wheelspin_*` 内部字段名与 R3 traction/grip UI 术语不一致；直接重命名会破坏 Profile/share-code 兼容，需要独立迁移设计。
- DSX 无 ACK 且没有 body haptics。
- USB audio endpoint 依赖名称 heuristic，没有用户选择和多 host API fallback。
- USB audio callback 有幅度平滑，而 Bluetooth 使用 HID compatible rumble；两者输入 frame 相同，但底层执行器/合成路径物理表现仍需实机确认。
- 根 README 与 `docs/ReadmeEN.md`、`docs/ReadmeJA.md` 有重复内容，存在漂移风险。
- 本地 Linux build 的 audio dependency 完整性仍未在 Linux 主机验证。

## 暂时不要修改的部分

- `src/modules/dualsense/main.py` 的 USB/BT report layout、rumble flags、BT CRC、pending release 和左右映射。
- `src/modules/forzahorizon/udp_listener.py` 的 324 字节 offsets 与 `recv_latest()` drain 语义。
- `src/modules/loop.py` 的 state-change write gate、静音和 body haptics failure isolation。
- `src/modules/haptics/mixer.py` 中已验证的静止、滚动、烧胎、路面、碰撞和悬挂 gating；红线只应作为独立叠加层调整。
- `src/modules/config/preferences.py` 的 Default Profile 重建、GLOBAL_FIELDS、atomic write 和本轮精确 R2 默认值迁移。
- `LICENSE`、`src/modules/about.py` 和 `docs/THIRD_PARTY_NOTICES.md` 的署名与第三方声明。
- R2 tag、Release、稳定资产和已发布算法默认值。

## 最近涉及的关键文件

- `src/modules/forzahorizon/effects.py`、`tests/forzahorizon/test_effects.py`：抓地力信号、路由、低速规则和扳机优先级。
- `src/modules/haptics/mixer.py`、`tests/haptics/test_mixer.py`：红线 envelope、hold、门控和 USB/BT 共享 normalized frame。
- `src/modules/config/settings.py`、`src/modules/config/preferences.py`、`tests/test_community_defaults.py`、`tests/fixtures/community_defaults_2323.json`：默认值与 Profile 迁移。
- `src/modules/gui/settings_tab.py`、`src/modules/tui/settings_tab.py`、两套 `controls_tab.py`、`src/lang/`：R3 文案、控制分组和翻译。
- `src/pyproject.toml`、`src/uv.lock`、`tests/test_enhanced_distribution.py`：R3 开发身份与 R2 稳定文档分离。
- `docs/superpowers/specs/2026-07-15-r3-traction-redline-design.md`、`docs/superpowers/plans/2026-07-15-r3-traction-redline.md`：已批准设计和实施清单。

## 当前 Git 工作区状态

- 当前分支为 `feat/r3-traction-redline`，业务实现提交为 `66595cb`。
- 构建目录由 `.gitignore` 排除，不应提交 ZUV/EXE 临时产物。
- 文档更新完成后必须再次运行 `git status --short --branch` 和 `git diff --check`；准确状态不要只依赖本段静态文字。
- 当前 R3 分支尚未推送或发布。不要把本地内部版本 `3` 当成公开 R3 Release。
- `packaging/zuv/dist` 和 `packaging/windows/dist` 是已忽略的本地产物目录；当前测试文件不会进入 Git commit。

## 已执行的测试和验证结果

- 新行为测试在实现前得到预期失败：首批 effects/mixer 为 `11 failed, 62 passed`；实现后定向测试为 `73 passed`。
- 配置迁移和 UI 契约在实现前得到预期失败：`5 failed, 16 passed`；实现后与 effects/mixer 合并定向测试为 `94 passed`。
- R3 版本契约在版本切换前为 `2 failed, 14 passed`；切换内部版本后 about/release 定向测试为 `22 passed`。
- 增加运行时关闭 hold 回归后，相关 mixer/effects 定向测试为 `74 passed`。
- 当前全量测试：`uv run --project src pytest -q` 为 `179 passed`。
- `uv run --project src python -m compileall -q src/modules src/lang` 通过。
- `git diff --check` 通过，仅有 Git 的 LF/CRLF 提示，没有 whitespace error。
- update-enabled ZUV 构建通过：`packaging/zuv/dist/FH-DualSense-Enhanced.zuv.py`。`uvx zuv inspect` 显示 version `3`、entry `main.py`、volume `data`、update repo `piereacy/FH-DualSense-Enhanced`；文件 SHA-256 为 `5214AF3F587E099B7F4063703DA33DFB03DE0D11D7A48FAA2FABB2D4E4E8563F`。
- Windows EXE 构建通过：`packaging/windows/dist/FH-DualSense-Enhanced-R3.exe`，大小 `37,786,288` bytes，SHA-256 为 `94439ED003FBC0B16C1C38B2A3200E586DE803C6AFE6F333CE3654B757D9BEB4`。
- EXE 检查结果：`FileVersion=R3`、`ProductVersion=R3`、`ProductName=FH-DualSense-Enhanced`；associated icon 为 32x32，`--help` 退出码为 0。
- 当前所有结果都是 synthetic telemetry/自动测试；R3 真实 Forza 手感尚未执行。

## 尚未执行或待完成的验证

- R3 真实 Forza USB 红线/抓地力测试。
- R3 真实 Forza Bluetooth 红线/抓地力测试。
- Linux 本地 R3 构建。
- DSX 实机测试，明确不属于当前范围。

## 下一次 Codex 会话开始时优先阅读

1. `AGENTS.md`
2. 本文件 `docs/PROJECT_STATE.md`
3. `docs/ARCHITECTURE.md`
4. `docs/superpowers/specs/2026-07-15-r3-traction-redline-design.md`
5. `docs/superpowers/plans/2026-07-15-r3-traction-redline.md`
6. `src/modules/forzahorizon/effects.py` 与 `tests/forzahorizon/test_effects.py`
7. `src/modules/haptics/mixer.py` 与 `tests/haptics/test_mixer.py`

下一次会话建议首先处理的具体任务：读取用户的真实 Forza 测试结果。如果红线脉冲可辨认且扳机路由正确，补充硬件验证记录并进入 R3 发布设计；如果不可辨认，只针对红线握把 envelope 调参，不改变抓地力路由和 USB/Bluetooth 一致性约束。

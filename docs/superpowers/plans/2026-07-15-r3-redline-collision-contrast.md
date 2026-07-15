# Enhanced R3 红线与碰撞辨识增强实施计划

**Goal:** 恢复可独立开关的 R2 扳机键红线震动，把握把红线改成默认仅左侧的高对比断油脉冲，并让碰撞通过双段优先事件和边沿日志获得可辨识手感。

**Architecture:** `Controller` 恢复原有 R2 扳机键 `rev_buzz()`，但增加松油门立即清除；`HapticMixer` 将连续背景、普通瞬态和优先事件分层后统一合成。USB 继续消费四通道 `HapticFrame`；Bluetooth 连续背景保留现有频率下混，红线和碰撞使用同一语义事件生成显式左右 motor projection。HID report 和 transport 生命周期不变。

**Reference:** `docs/superpowers/specs/2026-07-15-r3-redline-collision-contrast-design.md`

## Global Constraints

- 工作分支为 `feat/r3-traction-redline`，工作树为 `.worktrees/r3-traction-redline`。
- 当前基线提交为 `2ed5cdc`；开始业务修改前再次检查准确 HEAD 和工作区。
- 每个生产行为先添加失败测试并确认失败原因，再写最小实现。
- `enable_rev_limiter` 和 `rev_limit_*` 恢复为 R2 扳机键字段；握把红线必须使用新的独立字段。
- 红线持续输出必须要求油门达到 `accel_deadzone`。松油门时扳机和握把红线均立即退出。
- 握把红线默认仅左侧：`left=True`、`right=False`。
- USB 与 Bluetooth 共用 detector、phase、envelope、duck 和 normalized intensity，不定义传输模式专属手感参数。
- Bluetooth 连续 engine/road/water/rumble-strip/slip 保留当前频率下混；只给 redline/collision priority event 增加侧别投影。
- 不修改 DualSense HID offsets、flags、BT CRC、USB audio endpoint、Forza packet offsets、UDP drain 或 DSX 行为。
- 不修改已验证的抓地力路由、ABS wall、四材质算法、静止/滚动/烧胎 gating。
- 不创建 tag，不发布 R3 Release。本计划只生成新的本地 R3 测试产物。

## Task 1：锁定配置字段与预发布迁移

**Files:**

- Modify: `src/modules/config/settings.py`
- Modify: `src/modules/config/preferences.py`
- Modify: `tests/test_community_defaults.py`
- Modify: `tests/fixtures/community_defaults_2323.json`
- Modify: `tests/test_haptic_settings.py`

### Step 1：先写失败的默认值和迁移测试

- 把 community defaults 中 `rev_limit_freq/amp` 的预期恢复为扳机 `30/12`。
- 新增握把默认字段断言：总开关开启、左侧开启、右侧关闭、进入/释放比 `0.93/0.90`、频率/强度 `10/192`、low ratio `0.25`、背景 duck `0.30`。
- 新增碰撞字段断言：`collision_haptics_cooldown_ms=250`、`collision_haptics_rebound_ratio=0.45`、`collision_haptics_weak_side_ratio=0.35`、`collision_background_duck=0.20`。
- version 2 named Profile 测试：保留原 `enable_rev_limiter` 和所有 `rev_limit_*`，补入握把默认字段。
- version 3 预发布默认测试：缺少新字段且为 `10/96` 时，扳机恢复 `30/12`，握把升级到 `10/192`，握把总开关继承旧布尔值。
- version 3 自定义测试：自定义 freq/amp 同时保留为扳机值并复制为握把初始值，不静默覆盖。
- Default Profile 测试：每次启动仍按新代码默认重建。

Run:

```powershell
uv run --project src pytest -q tests/test_community_defaults.py tests/test_haptic_settings.py
```

Expected: 新字段和新迁移断言失败，旧运行时代码仍通过的无关测试保持绿色。

### Step 2：实现字段拆分和幂等迁移

- `Settings` 恢复 `rev_limit_freq=30`、`rev_limit_amp=12`，保留 `rev_limit_ratio=0.93` 和 `rev_limit_hold_ms=120`。
- 添加 `enable_grip_redline_haptics`、左右选择、握把 ratio/release/freq/amp/low ratio/duck。
- 添加 collision cooldown/rebound/weak-side/duck 字段。
- 用新的 `_migrate_r3_redline_split()` 取代 `_migrate_r2_redline_defaults()`；迁移只处理缺少握把字段的 snapshot，重复 load 不得再次改变数据。
- 保持所有新增字段为 Profile scope，不加入 `preferences.GLOBAL_FIELDS`。

### Step 3：运行配置定向测试

Run:

```powershell
uv run --project src pytest -q tests/test_community_defaults.py tests/test_haptic_settings.py
```

Expected: 全部通过。

## Task 2：恢复 R2 扳机键红线震动

**Files:**

- Modify: `src/modules/forzahorizon/effects.py`
- Modify: `tests/forzahorizon/test_effects.py`
- Regression: `tests/dsx/test_client.py`
- Regression: `tests/dualsense/test_output_report.py`

### Step 1：先恢复失败的行为测试

- 删除或改写当前“R2 扳机键永不使用 rev limiter”的 R3 断言。
- 添加 `TriggerAnimations.rev_buzz()` 阈值、开关、频率、强度和 hold 测试。
- 添加手刹加至少 80% 油门的原地特殊分支测试。
- 添加高 RPM 但油门低于 deadzone 不触发测试。
- 添加已进入 hold 后松油门立即清除 `_rev_until` 的回归测试。
- 添加 R2 优先级测试：gear > idle > traction > rev > wall > resistance。
- 明确抓地力占用 R2 扳机键时 rev 不覆盖抓地力，握把红线由后续 mixer 独立负责。

Run:

```powershell
uv run --project src pytest -q tests/forzahorizon/test_effects.py
```

Expected: rev 分支缺失导致新增测试失败。

### Step 2：恢复最小生产实现

- 在 `TriggerAnimations` 恢复 `_rev_until`，并在 `reset_transients()` 清除。
- 恢复 `rev_buzz()` 的 HID `vibrate(freq, amp)` 输出。
- 先执行持续油门门控；油门释放时清空 deadline 并返回 `None`。
- 油门保持时保留 RPM threshold 和 `rev_limit_hold_ms`。
- 在 `Controller.R2()` 中把 rev 分支放回 traction 之后、firmware wall 之前。

### Step 3：运行扳机和 DSX 回归

Run:

```powershell
uv run --project src pytest -q tests/forzahorizon/test_effects.py tests/dsx/test_client.py tests/dualsense/test_output_report.py
```

Expected: 全部通过；不修改 HID 字节契约或 DSX fallback。

## Task 3：增加 Bluetooth 优先事件侧别投影

**Files:**

- Modify: `src/modules/haptics/frame.py`
- Modify: `tests/haptics/test_frame.py`
- Modify: `tests/haptics/test_manager.py`
- Regression: `tests/dualsense/test_output_report.py`
- Regression: `tests/dualsense/test_reconnect_output.py`

### Step 1：先写失败的 projection 测试

- 保留当前无 explicit projection 时的频率下混测试，证明连续背景行为不变。
- 添加显式 compatible low/high 值优先于通用 `max(left, right)` 下混的测试。
- 添加 left-only priority event 只写 `CompatibleRumble.low_frequency`、right-only 只写 `high_frequency` 的测试。
- 添加显式值的 clamp、NaN 和 silent fallback 测试。
- 添加 manager 路由测试，确认 USB 仍收到完整 `HapticFrame`，Bluetooth 才调用 compatible projection。

Run:

```powershell
uv run --project src pytest -q tests/haptics/test_frame.py tests/haptics/test_manager.py
```

Expected: `HapticFrame` 尚无 projection 字段导致新增测试失败。

### Step 2：实现兼容字段和下混回退

- 给 `HapticFrame` 添加可选 `compatible_low_frequency`、`compatible_high_frequency`。
- `to_compatible_rumble()` 对每个显式值独立采用 override；未提供时严格保持原频率下混公式。
- 不修改 `CompatibleRumble`、`HapticManager.route()` 返回类型或 DualSense report writer。
- `SILENT_FRAME` 继续输出两个 motor 为 0。

### Step 3：运行 frame、manager 和 HID 回归

Run:

```powershell
uv run --project src pytest -q tests/haptics/test_frame.py tests/haptics/test_manager.py tests/dualsense/test_output_report.py tests/dualsense/test_reconnect_output.py
```

Expected: 全部通过；`motor_l`/`motor_r` offsets、flags 和 BT CRC snapshot 不变。

## Task 4：实现握把红线高对比混音和左右选择

**Files:**

- Modify: `src/modules/haptics/mixer.py`
- Modify: `tests/haptics/test_mixer.py`
- Regression: `tests/haptics/test_audio.py`
- Regression: `tests/haptics/test_manager.py`
- Regression: `tests/test_loop_haptics.py`

### Step 1：先写握把红线失败测试

- 默认值只向 `left_low/left_high` 注入红线事件，右侧不注入红线事件。
- 覆盖 left-only、right-only、both 和 neither 四种组合；两侧同时开启时相位一致。
- 覆盖进入 `0.93`、释放 `0.90` 的 RPM 滞回。
- 覆盖油门释放、总开关关闭、Body Haptics 关闭、engine intensity 为 0 时立即清除 active 和 phase。
- 覆盖 10 Hz、50% duty、on-phase high 主能量和 25% low 辅助能量。
- 覆盖红线 active 时 continuous background 乘以 0.30、off-phase 仍只保留 30% 背景、gear/suspension 等 transient 不被红线 duck。
- 覆盖进入/退出各一条日志，逐帧 update 不增加重复日志。
- 覆盖 USB 左右通道和 Bluetooth explicit motor projection 使用同一 active 状态、phase 和 normalized event intensity。

Run:

```powershell
uv run --project src pytest -q tests/haptics/test_mixer.py
```

Expected: 当前双侧加法脉冲、hold 和无分层 mixer 导致新增测试失败。

### Step 2：重构 mixer 局部能量层

- 在单个 `HapticMixer.update()` 内分开维护 continuous、transient、redline 和 collision 局部四通道能量。
- engine、road、water、rumble strip、slip 进入 continuous；gear、suspension、ABS body pulse 进入 transient。
- 保留现有 rolling、burnout、surface、puddle、slip、suspension 和 ABS gating 公式，只移动累加目标。
- `engine_amplitude` 与 continuous 四通道一起服从 redline duck。
- 最终只 clamp 一次，避免先饱和后 duck。

### Step 3：实现握把红线状态和 projection

- 用 `_redline_active` 和 phase start 表达握把状态，RPM hysteresis 取代当前 grip hold。
- 油门释放立即 reset；扳机自己的 `rev_limit_hold_ms` 不在 mixer 使用。
- 仅向勾选侧添加 redline event。
- USB 使用选中侧 low/high 事件；Bluetooth 从相同事件能量生成 left=`low_frequency`、right=`high_frequency` 的 explicit projection。
- 连续 Bluetooth 背景仍先按现有频率公式下混，再叠加选中侧 priority event。

### Step 4：运行 mixer 和传输回归

Run:

```powershell
uv run --project src pytest -q tests/haptics/test_mixer.py tests/haptics/test_frame.py tests/haptics/test_audio.py tests/haptics/test_manager.py tests/test_loop_haptics.py
```

Expected: 全部通过。

## Task 5：实现碰撞双段事件、冷却和诊断

**Files:**

- Modify: `src/modules/haptics/mixer.py`
- Modify: `tests/haptics/test_mixer.py`
- Regression: `tests/haptics/test_audio.py`
- Regression: `tests/test_loop_haptics.py`

### Step 1：先写碰撞检测失败测试

- jerk 单独越阈、smashable 单独越阈和 both 同时越阈分别 arm 一次。
- 第一帧只建立 acceleration baseline，不把历史空值当作 jerk。
- 持续高值不得每帧重新 arm；所有来源回落且 250 ms cooldown 完成后才 re-arm。
- Body Haptics off/on 会 reset baseline、armed state 和 deadline。
- 日志包含 source、原始 jerk/smashable、normalized intensity 和 direction，每次 arm 仅一条。

Run:

```powershell
uv run --project src pytest -q tests/haptics/test_mixer.py -k collision
```

Expected: 当前逐帧覆盖 deadline 的实现导致 edge/cooldown 测试失败。

### Step 2：先写双段波形和优先级失败测试

- 0 至 45 ms 为主冲击，45 至 65 ms 为间隔，65 至 120 ms 为 45% 回弹，120 至 150 ms 快速释放。
- 主冲击 low 为主并带短 high transient。
- 左/右方向主侧为完整强度、弱侧为 35%；无方向时左右相同。
- collision active 时所有非 collision 握把能量乘以 0.20。
- redline 与 collision 同时 active 时 collision 最高优先；collision 结束后 redline 根据当前 RPM/油门状态继续。
- Bluetooth collision priority event 映射到对应物理 motor，连续路面频率下混不变。

### Step 3：实现 detector 和 event envelope

- 增加 collision armed/cooldown 状态，不改变现有 jerk 和 smashable normalized 公式。
- 把 collision intensity、direction 和 start time 固定在 arm 边沿，不允许后续同一事件覆盖。
- 用 elapsed time 生成主冲击、间隔、回弹和 release envelope。
- collision active 时对所有非 collision 层应用 0.20 duck，再组合 collision event。
- 只在 arm 边沿写 INFO 日志，不逐帧记录 envelope。

### Step 4：运行碰撞和完整 haptics 回归

Run:

```powershell
uv run --project src pytest -q tests/haptics/test_mixer.py tests/haptics/test_frame.py tests/haptics/test_audio.py tests/haptics/test_manager.py tests/haptics/test_lifecycle.py tests/test_loop_haptics.py
```

Expected: 全部通过。

## Task 6：同步 GUI、TUI 和全部语言

**Files:**

- Modify: `src/modules/gui/controls_tab.py`
- Modify: `src/modules/tui/controls_tab.py`
- Modify: `src/modules/gui/settings_tab.py`
- Modify: `src/modules/tui/settings_tab.py`
- Modify: `src/lang/en.py`
- Modify: `src/lang/de.py`
- Modify: `src/lang/ja.py`
- Modify: `src/lang/ru.py`
- Modify: `src/lang/tr.py`
- Modify: `src/lang/zh.py`
- Modify: `src/lang/zh_tw.py`
- Modify: `tests/test_haptic_settings.py`

### Step 1：先写 UI 契约失败测试

- GUI/TUI controls 必须完全一致，并显示：`R2 trigger redline vibration`、`Grip redline vibration`、`Left grip`、`Right grip`。
- 中文翻译必须写“R2 扳机键红线震动”“握把红线震动”“左握把”“右握把”。
- 普通设置分别显示扳机红线和握把红线的进入阈值、频率和强度。
- Experimental features 添加握把释放阈值、low ratio、redline duck、collision cooldown/rebound/weak-side/duck，并保持默认折叠和“不建议自行调节”。
- 所有新增字段必须是 Profile scope，GUI/TUI range 一致，所有 catalog 有对应 key。

Run:

```powershell
uv run --project src pytest -q tests/test_haptic_settings.py
```

Expected: 新字段、分组和翻译断言失败。

### Step 2：更新 controls 和 settings

- `R2 - Throttle` 恢复 `enable_rev_limiter` 开关。
- 新增 `Redline feedback` 组，按顺序显示握把总开关、左握把、右握把；抓地力继续放在 Shared feedback。
- GUI/TUI 使用同样的 section/list 数据；若第四张卡在 GUI 宽度不足，按 2x2 grid 排列，不改变字段顺序。
- 普通设置拆成 trigger redline 与 grip redline 两组；实验性参数进入现有展开区。

### Step 3：同步语言并运行 UI 契约测试

Run:

```powershell
uv run --project src pytest -q tests/test_haptic_settings.py tests/gui/test_window_behavior.py
```

Expected: 全部通过。

## Task 7：全量验证、架构交接和本地测试产物

**Files:**

- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/PROJECT_STATE.md`
- Review: `AGENTS.md`
- Review: `README.md`
- Build output, ignored: `packaging/zuv/dist/`
- Build output, ignored: `packaging/windows/dist/`

### Step 1：更新实际架构和状态

- 代码完成后再把 `ARCHITECTURE.md` 改为实际的分层 mixer、双红线开关和 Bluetooth priority projection。
- `PROJECT_STATE.md` 区分自动测试通过、构建通过和真实硬件待验证，不把新手感写成已通过。
- 旧 R3 设计/计划保留为历史记录；最新规格和本计划明确覆盖冲突决定。
- README 仅检查是否出现与当前稳定 R2 说明冲突；R3 未发布时不把预发布功能写成稳定版能力。

### Step 2：运行完整质量门禁

Run:

```powershell
uv run --project src pytest -q
uv run --project src python -m compileall -q src/modules src/lang
git diff --check
git status --short --branch
git diff --name-only
```

Expected: pytest 和 compileall 通过；diff 只包含计划内源码、测试和文档，无缓存、配置或构建产物。

### Step 3：构建并检查 update-enabled ZUV

Run in `cmd.exe`:

```bat
set UPDATE_REPO=piereacy/FH-DualSense-Enhanced
packaging\zuv\build_zuv.bat
```

- 使用现有 inspect 命令核对 version `3`、entry `main.py`、volume `data` 和 update repo。
- 记录文件大小和 SHA-256。

Run:

```powershell
uvx zuv inspect packaging\zuv\dist\FH-DualSense-Enhanced.zuv.py
```

### Step 4：构建并检查 Windows EXE

Run:

```powershell
packaging\windows\build_exe.bat
```

- 检查 `FH-DualSense-Enhanced-R3.exe` 的 FileVersion/ProductVersion/ProductName、图标和 `--help`。
- 记录绝对路径、大小和 SHA-256。

### Step 5：交付最短实车序列

1. 关闭握把红线，验证 R2 扳机键原红线震动。
2. 关闭扳机红线，依次验证仅左、仅右、双侧握把红线。
3. 验证持续红线、快速升挡和松油门立即退出，并核对日志。
4. 验证高速正面碰撞和擦碰/小物体碰撞，并核对 detector arm 日志。
5. USB 与 Bluetooth 各完成一轮，检查侧别、时序和 normalized intensity，不预设 Bluetooth 较弱。

若无事件日志，停止调振幅并修 detector；若日志正确但手感不清晰，只调整 envelope/duck。用户确认前不创建 R3 tag 或 Release。

# Enhanced R3 红线与碰撞辨识增强设计

## 状态

- 日期：2026-07-15
- 分支：`feat/r3-traction-redline`
- 状态：核心行为已确认，详细规格待用户审阅，代码尚未实现
- 前置设计：`docs/superpowers/specs/2026-07-15-r3-traction-redline-design.md`
- 覆盖关系：本文覆盖前置设计中“删除 R2 扳机键红线反馈”“双侧握把固定输出”和“红线仅作加法叠加”的决定。抓地力路由、USB/Bluetooth 共享 `HapticFrame`、R3 版本身份等其他决定继续有效。

## 实车反馈与问题定义

当前 R3 测试产物已经能输出抓地力扳机反馈和红线握把脉冲，但用户实车验证发现：

- 红线握把脉冲无法从发动机、路面和抓地力底振中明确辨认。
- 高速正面碰撞和擦碰/小物体碰撞都无法从已有握把振动中明确辨认。
- 现有 `HapticMixer` 把红线直接加到左右 `high`，把碰撞线性衰减包络直接加到左右 `low`，最后统一 `clamp01()`。在连续底振较强时，增加幅度可能只会继续混合或饱和，无法形成事件轮廓。
- 当前没有事件边沿日志，无法区分“遥测没有触发检测器”和“检测器已触发但输出被底振掩盖”。

因此本轮不能只提高振幅。设计必须同时处理事件识别、可观察性和混音对比度。

## 目标

1. 恢复 Enhanced R2 已有的 R2 扳机键红线震动，并保持原有开关、波形和优先级语义；按最新要求补充松油门立即退出。
2. 保留 R3 新增的握把红线震动，改成可明确辨认的断油式脉冲。
3. 扳机红线和握把红线使用独立开关，可以同时工作。
4. 握把红线允许独立选择左握把和右握把，默认仅启用左握把。
5. 把碰撞改成方向明确的强主冲击加弱回弹，并让碰撞短暂获得握把混音最高优先级。
6. 为红线和碰撞增加边沿诊断日志，使下一轮实车测试能判断失败发生在识别层还是表现层。
7. USB 与 Bluetooth 继续消费同一个 normalized `HapticFrame`，不建立传输模式专属算法或默认强度。

## 非目标

- 不修改 Forza 324 字节 packet offsets、`UDPListener.recv_latest()` 或遥测协议。
- 不修改 USB/BT HID report、BT CRC、motor flags、USB audio endpoint 选择或 reconnect 逻辑。
- 不为 DSX 增加握把触觉；DSX 仍只发送自适应扳机。
- 不改变已经通过实车验证的抓地力 L2/R2 路由、GT7 风格 ABS wall 或材质算法。
- 不发布 R3 Release。本轮先生成新的本地测试产物并完成真实硬件验证。
- 不用完全静音所有背景触觉来伪造清晰度；背景只在短事件窗口中按比例压低。

## 红线识别

### 共同输入约束

红线必须要求 Forza 油门遥测达到 `accel_deadzone`。`max_rpm <= 0`、RPM 比例无效或松开油门时不得新触发红线。松开油门时，握把红线立即退出，不使用 hold 延迟。

这条门控是已确认的产品语义：松油门时出现的空转、打滑或残留高 RPM 不应触发红线警告。

### R2 扳机键红线

恢复 `TriggerAnimations.rev_buzz()` 和 R2 扳机键优先级分支，保持 Enhanced R2 的成熟行为，并加入已确认的持续油门门控：

1. Gear shift
2. Idle
3. Traction/grip
4. Rev limiter
5. Firmware end wall
6. Throttle resistance

`rev_buzz()` 继续使用 `enable_rev_limiter`、`rev_limit_ratio`、`rev_limit_freq`、`rev_limit_amp` 和 `rev_limit_hold_ms`。油门低于 deadzone 时立即清除 `_rev_until`，不能继续播放 hold；油门保持时，hold 继续防止 RPM 在阈值附近造成断续。原地手刹加大油门的特殊分支继续要求至少 80% 油门，不允许无油门触发。

抓地力仍高于扳机红线，因此抓地力正在占用 R2 扳机键时，红线可由握把通道继续表达，不改变已经验证的轮胎优先级。

### 握把红线

握把红线使用独立状态，不复用扳机 `rev_buzz()` 的 HID effect：

- 进入条件：`accel >= accel_deadzone` 且 `rpm / max_rpm >= grip_redline_ratio`。
- RPM 释放阈值：油门仍保持时，比例降至 `grip_redline_release_ratio` 才退出，默认 `0.90`，进入阈值默认 `0.93`。
- 油门释放、Body Haptics 关闭、握把红线总开关关闭或发动机触觉强度为 0 时立即清除状态和相位。
- 每次从 inactive 进入 active 时重置断油相位，从 on-phase 开始。
- 状态只在进入和退出边沿记录日志，不逐帧输出。

RPM 滞回负责消除阈值附近抖动，不再依赖当前 120 ms 的握把 hold。扳机红线仍保留自己的 `rev_limit_hold_ms`，两套输出的开关和状态互不覆盖。

## 红线握把波形与左右路由

握把红线默认参数：

- `enable_grip_redline_haptics = True`
- `grip_redline_left = True`
- `grip_redline_right = False`
- `grip_redline_ratio = 0.93`
- `grip_redline_release_ratio = 0.90`
- `grip_redline_freq = 10 Hz`
- `grip_redline_amp = 192/255`
- `grip_redline_low_ratio = 0.25`
- `grip_redline_background_duck = 0.30`

输出为 10 Hz、50% duty 的同相方波。on-phase 以 `high` 通道为主，并加入峰值 25% 的 `low` 通道短冲击；off-phase 不输出红线事件能量。

红线 active 的整个窗口内，连续发动机、路面、积水、rumble strip 和轮胎滑移底振乘以 `0.30`。这样 off-phase 仍保留少量车辆信息，但能形成清晰的“振、停、振、停”。换挡、悬挂和碰撞等瞬态事件不属于这层可压低的连续背景。

左右布尔值只决定红线事件层写入哪一侧，不交换物理映射。两侧都开启时使用相同相位；两侧都关闭时等价于握把红线无输出，但不修改总开关，也不影响 R2 扳机键红线。

## 碰撞识别与可观察性

第一轮实现保留当前两种已经存在的遥测来源：

- 相邻 sample 的 `accel_x`/`accel_z` 突变，使用 `collision_haptics_jerk_threshold`。
- `smashable_vel_diff > 3.0`。

事件强度仍取两者 normalized intensity 的最大值，但需要增加以下状态约束：

- 仅在至少一个检测值从阈值下方越过阈值时 arm。arm 后必须先观察到所有来源回落到阈值下方，并完成冷却期，detector 才重新就绪。
- 默认 `collision_haptics_cooldown_ms = 250`，避免持续高值或同一次碰撞的连续遥测包重复触发。
- 日志记录 `source=jerk`、`source=smashable` 或 `source=both`、原始输入、归一化强度和方向。
- 未启用 Body Haptics 时清除 detector 历史与 event deadline，重新启用后的第一帧只建立基线，不把旧 sample 差值当成碰撞。

本轮不凭猜测加入第三种速度损失检测器。若下一轮高速正面碰撞没有任何 arm 日志，则证明当前两种输入覆盖不足，再基于记录的 telemetry 设计 speed-loss fallback。若日志已经 arm 而手感仍不清晰，则只调整波形和混音，不把问题误判为检测失败。

## 碰撞波形与优先级

碰撞总窗口默认维持 150 ms，并改成双段包络：

- 0 至 45 ms：强主冲击，`low` 为主并加入短 `high` 瞬态。
- 45 至 65 ms：短间隔，不输出碰撞事件能量。
- 65 至 120 ms：弱回弹，峰值为主冲击约 45%。
- 120 至 150 ms：快速释放到 0。

碰撞方向继续由 `accel_x` 决定。主侧使用完整 event intensity，弱侧默认保留 35%，避免一侧完全安静。无明确横向方向时左右同强度。

碰撞 active 时，所有非碰撞握把能量乘以 `collision_background_duck = 0.20`，包括连续背景、握把红线、悬挂和换挡等瞬态。握把混音优先级为：

1. Collision event
2. Redline grip event
3. Gear/suspension transient
4. Engine/road/water/rumble-strip/slip continuous background

这项优先级只应用于 `HapticMixer`。L2/R2 扳机键继续使用 `Controller` 自己的优先级，不因握把碰撞而改变。

## 混音结构

`src/modules/haptics/mixer.py` 需要把当前边计算边累加的四个通道拆成至少三组局部能量：

- continuous background：engine、road、water、rumble strip、slip。
- transient：gear、suspension、ABS body pulse。
- priority events：grip redline、collision。

每组仍在同一个 `HapticMixer.update()` 中计算，不新增 transport 分支。最终先应用 redline/collision duck，再按优先级组合并执行一次 `clamp01()`。`engine_hz` 保留当前计算；`engine_amplitude` 作为 continuous background 同样服从 duck，确保 USB 音频引擎层不会在 off-phase 填满红线间隙。

### Bluetooth 侧别投影

当前 `to_compatible_rumble()` 使用 `max(left_low, right_low)` 和 `max(left_high, right_high)` 按频率下混，连续路面纹理因此能驱动低频和高频 motor，但握把侧别会丢失。若不处理这一点，“仅左握把”在 Bluetooth 上无法满足产品语义。

本轮保留连续背景的现有频率下混，只为 redline/collision priority event 增加显式 compatible projection。`HapticFrame` 增加可选的 `compatible_low_frequency` 和 `compatible_high_frequency` 最终值；`HapticMixer` 从同一事件状态、phase、normalized intensity 和左右选择同时生成：

- USB 四通道最终能量。
- Bluetooth 两 motor 最终能量，其中左侧 priority event 写入 `motor_l/low_frequency`，右侧 priority event 写入 `motor_r/high_frequency`。

`to_compatible_rumble()` 在显式 compatible 值存在时使用它们，否则保持当前通用下混，避免改变非 mixer 调用者。`HapticManager`、USB audio、DualSense HID report offsets、flags 和 CRC 不变。

这不是为 Bluetooth 建立另一套红线或碰撞算法，而是同一语义事件从四通道到两 motor 的物理投影。自动测试必须证明进入/退出、相位、duck 和 normalized event intensity 一致，并分别证明 left-only/right-only 落到对应 motor。

## 设置与配置兼容

### 字段归属

恢复 Enhanced R2 字段的原始含义：

- `enable_rev_limiter`：R2 扳机键红线开关。
- `rev_limit_ratio/freq/amp/hold_ms`：R2 扳机键红线参数，默认恢复为 R2 的 `0.93/30/12/120`。

新增握把专用字段，不再让同一 `rev_limit_freq/amp` 同时承担 HID trigger 和 body haptics 两种尺度不同的输出。所有新增可调参数定义在 `src/modules/config/settings.py`。

### R3 预发布配置修复

当前分支曾把 R2 命名 Profile 的 `30/12` 迁移为握把默认 `10/96`。R3 尚未发布，但本地测试产物可能已经保存 version 3 Profile，因此实现必须处理缺少新握把字段的 Profile：

- version 2 Profile：保留原有 `rev_limit_*` 作为扳机参数，补入新的握把默认值。
- version 3 且缺少新握把字段：把当前 `rev_limit_freq/amp` 复制为握把初始值；若二者恰好是已知预发布默认 `10/96`，扳机字段恢复为 `30/12`；其他自定义值继续保留为扳机值，同时复制给握把，避免静默丢失用户调校。
- 新 Default Profile：按代码默认值重建，扳机 `30/12`，握把 `10/192`，仅左握把开启。

迁移必须有 version 2、version 3 预发布默认、version 3 自定义值和 Default Profile 自动测试。

## GUI、TUI 与语言

GUI 和 TUI 使用同一组字段与顺序，并通过现有 parity test：

- 红线反馈组：`R2 扳机键红线震动`、`握把红线震动`、`左握把`、`右握把`。
- `左握把` 和 `右握把` 是握把红线的子选项；界面无法动态嵌套时仍紧邻总开关显示，并使用明确文案说明只影响握把红线。
- 普通设置显示进入阈值、扳机频率/强度、握把频率/强度。
- 释放阈值、low ratio、背景 duck、碰撞 cooldown、碰撞 rebound 和 collision duck 放入现有 Experimental features 展开区，并保留“不建议自行调节”提示。
- 同步 `de/ja/ru/tr/zh/zh_tw` catalog。中文始终写“R2 扳机键”，避免与 Enhanced R2 版本名混淆。

## 诊断日志

日志只记录状态边沿：

- 握把红线进入：RPM、max RPM、ratio、油门、启用侧。
- 握把红线退出：退出原因是 throttle、ratio、toggle、engine intensity 或 telemetry off。
- 碰撞 arm：source、jerk、smashable、intensity、direction。

不得逐帧记录 pulse phase 或 envelope。日志不得包含个人路径、设备序列号或其他隐私数据。

## 自动测试与实机验收

### 自动测试

- 恢复 R2 扳机键 `rev_buzz()` 的阈值、油门、handbrake、hold、开关和优先级测试。
- 握把红线覆盖进入/释放滞回、松油门立即清除、10 Hz/50% duty、强弱通道比例、左右四种组合和两个独立开关。
- 验证红线 active 时 continuous background 为 30%，transient 不被错误压低。
- 碰撞覆盖 jerk、smashable、both、方向、弱侧 35%、双段包络、250 ms cooldown 和基线 reset。
- 验证碰撞覆盖红线时 collision event 保持最高优先级，结束后红线按当前状态恢复。
- 验证 USB frame 和 Bluetooth compatible rumble 使用同一个 normalized envelope；Bluetooth left-only/right-only priority event 分别落到 `motor_l`/`motor_r`，连续背景仍保持现有频率下混。
- 覆盖 version 2、version 3 预发布配置修复、GUI/TUI parity、翻译 catalog 和 community defaults。

### 本地门禁

- 先运行最接近的 effects、mixer、settings 和 migration 定向测试。
- 运行 `uv run --project src pytest -q`。
- 运行 `uv run --project src python -m compileall -q src/modules src/lang`。
- 运行 `git diff --check` 并检查完整 diff。
- 构建 update-enabled ZUV 和 `FH-DualSense-Enhanced-R3.exe`，检查版本、图标和 `--help`。

### 真实硬件验收

1. 关闭握把红线，只验证 R2 扳机键原红线震动恢复。
2. 关闭扳机红线，只启用左握把，验证右握把不产生红线事件。
3. 改为只启用右握把，再启用两侧，验证路由和同相脉冲。
4. 红线持续、快速升挡、松油门各测试一次，并对照边沿日志。
5. 高速正面碰撞和擦碰/小物体碰撞各测试一次，并对照 collision arm 日志。
6. 至少分别使用 USB 和 Bluetooth 完成一轮。验收目标是逻辑、时序和 normalized intensity 一致，不预设 Bluetooth 较弱。

如果没有对应事件日志，进入检测器修复；如果日志正确但事件仍无法从底振中辨认，调整 event envelope 或 duck，不通过修改 transport 分支制造差异。

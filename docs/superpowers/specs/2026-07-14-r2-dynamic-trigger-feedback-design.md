# Enhanced R2 动态扳机反馈设计

## 状态

- 日期：2026-07-14
- 分支：`feat/r2-trigger-dynamics`
- 状态：实现和自动测试完成，USB/BT 核心手感已确认，DSX/真实遥测待验证
- 范围：动态轮胎打滑 R2、GT7 风格 ABS L2、折叠实验性设置

## 目标与边界

R2 在现有 `TriggerAnimations` 和 `Controller` 优先级链中升级 wheelspin 与 ABS，继续复用现有 USB、Bluetooth 和 DSX transport。R2 不改 body haptics 混音，不加入 boost resistance、碰撞扳机冲击或扳机路面底噪。

## 动态 wheelspin

1. 仅在油门超过 deadzone 时采纳驱动轮的 longitudinal `tire_slip_ratio_*`。松油漂移不进入 R2，仍由 body haptics 表达。
2. `drive_train` 决定前驱、后驱或四驱的采样轮。低于 `LOW_SPEED_KMH` 时 slip ratio 退化，改用驱动轮 `wheel_rotation_speed_*` 判断原地烧胎。
3. 一个主阈值配合 hysteresis 防止临界点抖动。`sensitivity` 通过降低或提高有效阈值工作，不改变遥测含义。
4. 使用按实际 `dt` 计算的非对称 EWMA。attack 默认约 40 ms，release 默认约 125 ms。该状态属于 `TriggerAnimations`，遥测关闭时必须复位。
5. slip 强度动态映射频率和振幅。主导驱动轮的 puddle 与 `surface_rumble` 选择 tarmac、water、dirt、gravel 频带，保留路面材质 signature。
6. G force 仅作温和反向 damping，默认影响约 25%，不替代 slip 主信号。

## GT7 风格 ABS wall

1. L2 顶部默认 3 个 zone 保持最大 wall，下部 zone 按 slip 动态振动，使用现有 `vibrate_zones()` 的 `0x26` 输出。
2. 每轮 longitudinal `tire_slip_ratio_*` 是主信号，`tire_combined_slip_*` 仅以较低权重辅助。
3. 约 6 km/h 的最低速度只负责 gating，不参与强度计算。强度和频率均随 normalized slip 动态映射。
4. 每次有效 ABS 信号延长约 100 ms hold deadline，减少遥测边界抖动。hold 结束后立即回到后续 L2 resistance/wall 链。
5. native USB 和 Bluetooth 使用完整 zoned wall。现有 DSX adapter 会把 `M_VIBRATE_ZONES` 明确退化为动态 `TM_VIBRATE`，不伪装成完整 wall。

## 设置边界

普通设置只暴露 wheelspin strength、wheelspin sensitivity、ABS strength 和 ABS sensitivity。阈值、频带、G damping、EWMA、hysteresis、burnout threshold、ABS frequency range、hold 与 wall zones 放入默认折叠的“实验性功能”，并显示“不建议自行调节”。所有新增参数均为 Profile 字段，不加入 `GLOBAL_FIELDS`。

## 架构约束

- 在 `src/modules/forzahorizon/effects.py` 内增加小型时间平滑 helper，不建立第二套控制器或 transport。
- 保持 `Controller.L2()` 和 `Controller.R2()` 的现有优先级；只升级对应 effect 返回值。
- 不改 `src/modules/dualsense/main.py` 的 USB/BT report layout、BT CRC 或原子 `set()` 路径。
- 不改 `src/modules/haptics/mixer.py` 的静止、滚动、烧胎和路面 gating。
- 每个行为先由 pytest 失败测试定义，再写生产代码。

## 验证标准

- 自动测试覆盖驱动轮 longitudinal slip、松油漂移排除、低速 raw rotation、surface signature、EWMA attack/release、hysteresis、ABS 动态 zoned wall、hold、低速 gating 与 DSX fallback。
- GUI/TUI 字段集合一致，实验性区域默认折叠，新增字段可以 Profile round-trip。
- 全量 pytest 通过后，再分别进行 USB、Bluetooth 和 DSX 实机验证；未做的硬件路径必须记录为待确认。

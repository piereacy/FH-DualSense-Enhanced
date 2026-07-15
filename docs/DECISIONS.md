# 项目决策记录

本文记录会影响后续开发方向、但不适合塞进架构说明的关键决定。新决定应注明日期、状态、原因和后果；已被替代的决定保留并标注替代关系。

## 2026-07-15：Enhanced R3 不接管游戏原生振动

- 状态：已决定，Enhanced R3 不实现。
- 背景：开启 Forza/Steam Input 原生振动时，原生 rumble 可能覆盖或掩盖本项目的左右碰撞方向。关闭游戏内振动后，本项目已有的方向碰撞可以辨认，但会失去上车过场、菜单/CG 切回可操控世界等原生事件。
- 决定：Enhanced R3 不用遥测猜测这些事件，也不把猜测式脉冲包装成完整接管。
- 原因：当前 `src/modules/forzahorizon/udp_listener.py` 只接收单向 Data Out telemetry，代码没有游戏原生 rumble 事件输入。准确接管需要新增独立的虚拟控制器桥接：转发物理 DualSense 输入、向游戏暴露虚拟控制器、捕获游戏 rumble、与项目触觉混音并写回 DualSense。这是 Windows 输入栈级子系统，不属于 Enhanced R3 的调校范围。
- 后果：Enhanced R3 的碰撞方向和握把冲击硬件测试必须记录游戏内振动和 Steam Input 状态。验证本项目输出时先关闭游戏内振动；未来版本若研究接管，必须单独设计输入转发、设备隐藏、故障回退、延迟和依赖维护方案。

## 2026-07-15：握把换挡冲击保留为独立默认关闭功能

- 状态：已实现。
- 背景：`src/modules/haptics/mixer.py` 原先在正挡变化时无条件加入双侧 `0.8` 低频冲击，持续时间复用 R2 扳机键的 `gear_shift_duration_ms`。关闭 R2 扳机键换挡开关不会关闭该握把冲击，因此用户感知到隐藏的换挡强震。
- 来源：该思路来自项目参考的 HorizonHaptics 握把换挡 kick；FH-DualSense-Enhanced 早期 body haptics 设计把它作为固定 transient 引入。
- 决定：保留该效果，但新增 `enable_grip_gear_shift_haptics`、`grip_gear_shift_strength` 和 `grip_gear_shift_duration_ms`。开关默认关闭，强度和持续时间放在普通设置，不放在实验性设置；三个字段与 R2 扳机键换挡参数完全解耦。
- 后果：关闭开关时运行中的握把冲击立即结束，但 mixer 继续更新挡位基线，重新开启不会补发旧换挡。USB 与 Bluetooth 继续使用同一个事件语义。

## 2026-07-15：握把红线默认关闭并使用 1.5 信号增益

- 状态：已实现，真实 Forza 手感待重新验证。
- 背景：握把红线脉冲已经能够辨认，但不应成为默认输出；用户启用后希望比原实现明显约 50%。
- 决定：`enable_grip_redline_haptics` 默认改为 `False`。新增 Profile 参数 `grip_redline_gain=1.5`，在红线基础幅度之后、最终通道限幅之前相乘；参数放在实验性设置。
- 后果：`1.5` 只表示信号域乘数，不保证人的触觉感知严格增强 50%。存在余量时信号为原来的 1.5 倍，超过 `1.0` 时继续由既有 `clamp01()` 安全削顶。命名 Profile 的显式红线开关保留，Default Profile 使用新默认值。

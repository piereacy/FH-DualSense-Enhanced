# 项目决策记录

本文记录会影响后续开发方向、但不适合塞进架构说明的关键决定。新决定应注明日期、状态、原因和后果；已被替代的决定保留并标注替代关系。

## 2026-07-15：默认使用握把红线，关闭 R2 扳机键红线

- 状态：已实现，取代本文后面的“握把红线默认关闭”决定中的默认开关部分；`1.5` 信号增益继续保留。
- 背景：R3 完整 EXE 的 Bluetooth 游戏内体验已经由用户确认可用。红线属于发动机和变速箱状态，默认放在握把更符合当前产品分层，也能避免 R2 扳机键红线与轮胎抓地力反馈争用同一执行器。
- 决定：`enable_rev_limiter=False`，默认关闭 R2 扳机键红线；`enable_grip_redline_haptics=True`，默认开启握把红线并继续只选择左握把。两个开关仍然独立，用户可以恢复扳机红线或关闭握把红线。
- Profile：`Default` Profile 每次启动按新默认值刷新。命名 Profile 中显式保存的开关保持不变；只在字段缺失时沿用现有迁移规则补齐。
- 后果：R2 扳机键默认优先表达抓地力和油门阻力，握把默认表达发动机红线。红线握把节奏仍不完美，后续版本继续调校，不阻止 Enhanced R3 发布。

## 2026-07-15：Enhanced R3 不接管游戏原生振动

- 状态：已决定，Enhanced R3 不实现。
- 背景：开启 Forza/Steam Input 原生振动时，原生 rumble 可能覆盖或掩盖本项目的左右碰撞方向。关闭游戏内振动后，本项目已有的方向碰撞可以辨认，但会失去上车过场、菜单/CG 切回可操控世界等原生事件。
- 决定：Enhanced R3 不用遥测猜测这些事件，也不把猜测式脉冲包装成完整接管。
- 原因：当前 `src/modules/forzahorizon/udp_listener.py` 只接收单向 Data Out telemetry，代码没有游戏原生 rumble 事件输入。准确接管需要新增独立的虚拟控制器桥接：转发物理 DualSense 输入、向游戏暴露虚拟控制器、捕获游戏 rumble、与项目触觉混音并写回 DualSense。这是 Windows 输入栈级子系统，不属于 Enhanced R3 的调校范围。
- 后果：Enhanced R3 的碰撞方向和握把冲击硬件测试必须记录游戏内振动和 Steam Input 状态。验证本项目输出时先关闭游戏内振动；未来版本若研究接管，必须单独设计输入转发、设备隐藏、故障回退、延迟和依赖维护方案。

## 2026-07-15：Bluetooth 直接发送 `0x36` HD haptics，不捆绑 vDS 驱动

- 状态：生产代码和自动测试已实现；Bluetooth 协议/频率探针已通过，Forza 主观对照和 USB 同场景对照待完成。
- 背景：Enhanced R1-R3 原 Bluetooth 路径把 `HapticFrame` 压缩成两个 compatible rumble motor 强度，左右取 `max()`。该降级必然丢失路面纹理、碰撞方向、红线波形和发动机频率，用户实测表现为持续“傻震”。
- 证据：vDS `0.3.0-rc7` 和 DS5Dongle 证明物理 DualSense 能通过 Bluetooth audio-haptics reports 接收左右 PCM。当前手柄的 HID descriptor 暴露 398 字节 report `0x36`；真实硬件已连续接受该报告，左握把探针使加速度计关键轴标准差从约 `13.1` 上升到约 `1931.2`，且连接未中断。
- 决定：USB 和 Bluetooth 复用 `HapticPcmRenderer`。USB 继续使用 48 kHz 四声道 endpoint；Bluetooth 在应用内生成 3 kHz、32-frame stereo int8，并通过现有 hidapi handle 发送 `0x36`。不安装或捆绑 vDS 的 `vds_usb.sys`、`vds_filter.sys`、daemon、test-signing 配置和 Opus runtime。
- 调度：Bluetooth 周期使用 `time.sleep()` 的高精度 waitable timer。禁止改回 `threading.Event.wait()` 作为 10.667 ms 定时器；该实现实测约 65 Hz 并导致 1.5 秒覆盖 48 个音频块。修复后实测平均间隔 `10.668 ms`、最大 `11.204 ms`、同段零覆盖。
- 回退：当前连接拒绝 `0x36` 时只禁用 HD haptics，扳机保持工作，并回退到既有 compatible rumble。重新连接后重试 HD haptics。停止、禁用或断开前发送全零 haptics block。
- 边界：此决定不替代“Enhanced R3 不接管游戏原生振动”。本项目只发送自身遥测合成的触觉；菜单、CG、上车过场等游戏原生音频触觉仍需未来单独研究虚拟 USB bridge。

## 2026-07-15：握把换挡冲击保留为独立默认关闭功能

- 状态：已实现。
- 背景：`src/modules/haptics/mixer.py` 原先在正挡变化时无条件加入双侧 `0.8` 低频冲击，持续时间复用 R2 扳机键的 `gear_shift_duration_ms`。关闭 R2 扳机键换挡开关不会关闭该握把冲击，因此用户感知到隐藏的换挡强震。
- 来源：该思路来自项目参考的 HorizonHaptics 握把换挡 kick；FH-DualSense-Enhanced 早期 body haptics 设计把它作为固定 transient 引入。
- 决定：保留该效果，但新增 `enable_grip_gear_shift_haptics`、`grip_gear_shift_strength` 和 `grip_gear_shift_duration_ms`。开关默认关闭，强度和持续时间放在普通设置，不放在实验性设置；三个字段与 R2 扳机键换挡参数完全解耦。
- 后果：关闭开关时运行中的握把冲击立即结束，但 mixer 继续更新挡位基线，重新开启不会补发旧换挡。USB 与 Bluetooth 继续使用同一个事件语义。

## 2026-07-15：握把红线默认关闭并使用 1.5 信号增益（默认开关已被取代）

- 状态：`1.5` 信号增益仍有效；默认关闭的决定已被上面的新决定取代。
- 背景：握把红线脉冲已经能够辨认，但不应成为默认输出；用户启用后希望比原实现明显约 50%。
- 决定：`enable_grip_redline_haptics` 默认改为 `False`。新增 Profile 参数 `grip_redline_gain=1.5`，在红线基础幅度之后、最终通道限幅之前相乘；参数放在实验性设置。
- 后果：`1.5` 只表示信号域乘数，不保证人的触觉感知严格增强 50%。存在余量时信号为原来的 1.5 倍，超过 `1.0` 时继续由既有 `clamp01()` 安全削顶。命名 Profile 的显式红线开关保留，Default Profile 使用新默认值。

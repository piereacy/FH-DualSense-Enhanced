# 项目决策记录

本文记录会影响后续开发方向、但不适合塞进架构说明的关键决定。新决定应注明日期、状态、原因和后果；已被替代的决定保留并标注替代关系。

## 2026-07-16：Enhanced R4 提供三种构建时 GUI 壳层，不分叉业务功能

- 状态：生产代码、打包配置和自动测试已实现；三个完整 EXE 已构建并分别完成启动、页面切换与退出冒烟，真实 Forza 审阅待用户执行。
- 背景：原界面的分类和层级不够清晰，用户要求至少三种初音未来青绿色前端供审阅，同时明确不能影响功能实现。
- 决定：Miku Console、Miku Stage、Miku Studio 只在 `src/modules/gui/variants.py` 中定义导航位置、宽度和紧凑模式，颜色统一来自 `src/modules/gui/theme.py`。三者必须实例化同一组 Tab、同一个 `Settings`、同一后端线程和配置格式，禁止复制业务页面。
- 构建：`FHDS_BUILD_VARIANT` 为每个 EXE 内置 `data/ui_variant.txt`；文件名分别为 `FH-DualSense-Enhanced-R4-Miku-Console.exe`、`...-Miku-Stage.exe` 和 `...-Miku-Studio.exe`。源码环境变量 `FHDS_UI_VARIANT` 只用于预览。
- 后果：任何新功能都必须一次进入三种 EXE；只修改某一壳层的业务能力属于回归。三者可以共享同一 `data` 配置，但同时运行仍会争用 UDP 端口。

## 2026-07-16：Windows 独立 EXE 使用内置更新器，ZUV 保留为可选入口

- 状态：查询、下载、校验、待安装恢复、Helper 替换/回滚、GUI/TUI 控件和自动测试已实现；真实已发布 R4 到 R5 的端到端更新尚无法执行。
- 背景：只下载 EXE 的用户不应再为了更新安装 Python、uv 或理解 ZUV；Windows 运行中的 EXE 又不能可靠地自行覆盖。
- 决定：仅冻结后的 Windows EXE 启用内置更新。它只接受仓库稳定 `R<n>` Release 中与当前 Miku 方案同名的 EXE 和 `.sha256`，以 `.part` 下载并检查长度、SHA-256、`MZ` 头。用户确认后由内置的独立 Helper 等待旧 PID、生成 `.old`、替换、重启，并在失败时回滚。
- 边界：源码、Linux 和 ZUV 运行不执行 EXE 自替换；不静默提权，不跨 Miku 方案更新。ZUV 和 `win_start.bat` 继续保留，作为兼容、开发和网络备用入口，而不是 R4 独立 EXE 的依赖。
- 已知差距：当前每次启动约 10 秒后检查一次，尚无跨启动 24 小时节流；只检查 `MZ` 头而未解析 PE 版本资源，也没有代码签名信任链；这些不能在文档中写成已实现。

## 2026-07-16：Enhanced R4 重做握把红线强度曲线并保留既有默认分工

- 状态：生产代码和自动测试已实现；R4 实车手感待用户使用成品 EXE 审阅。
- 背景：旧 `192/255 * 1.5` 在线性增益后会超过 `1.0` 并立即硬削顶，使继续调节几乎没有有效行程，也难以同时控制重量、节奏和进入瞬间的辨识度。
- 决定：继续默认关闭 R2 扳机键红线、开启左握把红线；默认改为 10 Hz、70% duty、峰值 `220/255`、low ratio `0.45`，并在进入后的 120 ms 叠加 `0.65` 起始冲击。保留兼容字段 `grip_redline_gain=1.5`，但改用 `1 - (1 - base)^gain` 非线性曲线，不再线性乘法后削顶。
- 后果：峰值、频率、占空比、重量和起始冲击可分别调节；旧命名 Profile 的显式值继续保留。此变更取代本文后面“1.5 信号增益”的线性实现部分，不改变握把红线与 R2 扳机键红线的独立开关。

## 2026-07-16：新增 HorizonHaptics 启发的可选层，并改善 Bluetooth 量化

- 状态：生产代码与自动测试已实现；真实 USB/Bluetooth 逐项手感验证尚未执行。
- 决定：新增默认关闭的涡轮增压阻力、G 力油门阻力、L2/R2 碰撞扳机冲击、松开扳机时的路面/减速带纹理、转速灯带和挡位 Player LEDs。碰撞握把和碰撞扳机共用 `src/modules/loop.py` 每帧只计算一次的 `CollisionSignal`；新扳机层不能覆盖现有抓地力、ABS 和高优先级冲击。
- 归属：算法参考 HorizonHaptics `1.3.0` 的功能方向，但按本项目现有 `Settings`、priority chain、HID 和 Profile 边界独立实现，不复制第二套 wheelspin 或 ABS 算法。所有新增体验功能均有开关，关闭时保持 Enhanced R3 的输出兼容。
- Bluetooth：继续使用同一 `HapticFrame` 和 `HapticPcmRenderer` 语义，但 3 kHz 路径在 int8 量化前使用归一化 `tanh` 软限幅，并以默认 `0.75` 一阶误差反馈保存低幅平均能量。USB 48 kHz float32 路径不改为该量化方式。
- 灯效：`ControllerVisualState` 写入 USB `0x02`、BT `0x31` 和 BT `0x36` state block；DSX 不写灯光，避免争夺 DSX 的 RGB 所有权。
- 边界：398 字节、3 kHz、32 stereo frames、序列和 CRC 均保持不变；这些改进不能被描述为 Bluetooth 变成真实 USB 音频设备，也不接管游戏原生振动。

## 2026-07-15：默认使用握把红线，关闭 R2 扳机键红线

- 状态：默认开关仍有效；`1.5` 的线性信号增益实现已被 Enhanced R4 的非线性感知曲线取代。
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

## 2026-07-15：握把红线默认关闭并使用 1.5 线性信号增益（已被 Enhanced R4 取代）

- 状态：默认关闭的决定先被 2026-07-15 的新默认取代；线性乘法又被 2026-07-16 的 Enhanced R4 非线性曲线取代。字段本身只为 Profile 兼容保留。
- 背景：握把红线脉冲已经能够辨认，但不应成为默认输出；用户启用后希望比原实现明显约 50%。
- 决定：`enable_grip_redline_haptics` 默认改为 `False`。新增 Profile 参数 `grip_redline_gain=1.5`，在红线基础幅度之后、最终通道限幅之前相乘；参数放在实验性设置。
- 后果：`1.5` 只表示信号域乘数，不保证人的触觉感知严格增强 50%。存在余量时信号为原来的 1.5 倍，超过 `1.0` 时继续由既有 `clamp01()` 安全削顶。命名 Profile 的显式红线开关保留，Default Profile 使用新默认值。

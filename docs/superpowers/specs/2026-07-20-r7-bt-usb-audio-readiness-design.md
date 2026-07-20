# R7 Bluetooth 到 USB 音频就绪门槛设计

日期：2026-07-20
状态：用户已确认方案 A，代码尚未实现

## 实机证据与问题定性

`dist-bt-teardown-1` 候选在真实 DualSense 上得到以下结果：

- Bluetooth 冷启动后的四通道握把触觉正常。
- 插入 USB 后，连接状态、输入与 L2/R2 扳机键进入 USB，但握把触觉完全消失。
- 运行日志按顺序出现 `DualSense Bluetooth control teardown accepted (48 byte(s))`、`DualSense transport handover complete: BT -> USB` 和 `No four-channel DualSense audio endpoint found`。
- handover 后的只读系统检查能够枚举到活动的 `DualSense Wireless Controller` USB render endpoint；新的独立 `sounddevice` 进程能够看到 Windows WASAPI 下 4 声道、48 kHz 的 DualSense 输出设备。
- 原应用在之后的周期同步中没有启动 USB body haptics。

这组证据否定了“仅发送 `0x08 / 0x02` 就能恢复 USB 握把触觉”的假设。当前最符合代码和实机现象的原因是：BT -> USB handover 在 Windows USB 音频端点完成枚举之前提交，应用第一次 PortAudio 设备查询得到不完整快照；端点稍后出现，但该进程中的设备表没有随系统状态更新。

该定性不把 UDP、握把 mixer 或 telemetry 写成故障来源。日志仍在持续产生碰撞与红线事件，L2/R2 扳机键也继续工作。

## 目标

1. BT -> USB 时保留 Bluetooth 输入和 `0x36` 握把触觉至少 3 秒，等待 Windows USB 音频端点稳定。
2. 在任何 PortAudio 设备查询之前，用不初始化 PortAudio 的 Windows 端点探针确认 DualSense USB render endpoint 已活动。
3. 只有端点就绪后才验证并提交 USB handover；未就绪时保留完整 Bluetooth 功能并按既有退避重试。
4. 保持 USB 冷启动、Bluetooth 冷启动、USB -> Bluetooth、完全掉线 reconnect 与 Enhanced R6 USB 音频生命周期不变。
5. 不再调用 `sounddevice` 私有 `_terminate()`、`_initialize()`，不加入额外 PortAudio heartbeat 或跨进程刷新。

## 方案比较

### 方案 A：3 秒稳定窗口加 Windows 音频端点门槛（采用）

同一手柄的 USB candidate 稳定出现后先保留当前 BT handle。经过 3 秒稳定窗口后，通过 Windows MMDevices render endpoint 状态进行只读判断；只有端点活动时才继续现有 USB candidate validation、Bluetooth control teardown 和原子 handover。

优点是 PortAudio 的第一次枚举发生在系统端点已经出现之后，并且失败时不会牺牲正在工作的 Bluetooth 握把触觉。探针使用 Python 标准库，不增加 EXE 第三方依赖。

### 方案 B：固定等待 3 秒后无条件提交

该方案改动更小，但端点在较慢系统上可能超过 3 秒才出现，仍会进入“显示 USB、握把触觉消失”的状态，不满足失败时保留 Bluetooth 的要求。

### 方案 C：强制重置 PortAudio 或长期维持双 transport

PortAudio 私有刷新在此前候选中已经造成生命周期与跨进程污染风险。长期使用 USB HID 加 Bluetooth haptics 又会扩大双句柄所有权、退出清理和状态展示边界。因此两者都不采用。

## 模块边界

### Windows 端点探针

新增一个只负责 Windows USB audio readiness 的小模块，建议位于 `src/modules/haptics/windows_endpoint.py`。它不得导入或调用 `sounddevice`，只使用标准库 `winreg` 读取：

- `HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio\Render`；
- endpoint 的 `DeviceState` 必须为活动状态；
- endpoint 属性必须能关联到 Sony DualSense 或 DualSense Edge 的 USB audio interface，硬件 ID 使用 `VID_054C`、`PID_0CE6` 或 `PID_0DF2`，并限定音频接口 `MI_00`。

名称匹配只作为兼容辅助，不能只依赖本地化后的“扬声器”文本。注册表不存在、访问失败或属性不足都返回“尚未就绪”，不得抛出导致 controller 断连的异常。非 Windows 平台不启用该门槛。

探针只证明 Windows 已发布活动 USB render endpoint。现有 `find_dualsense_output_device()` 仍负责在真正开流时验证 Windows WASAPI 与至少 4 个输出声道。

### orchestration 注入

`src/modules/__init__.py` 是 backend orchestration 层，由它把一个只读 readiness callback 注入原生 `DualSense` backend：

- `enable_body_haptics` 为关闭时，callback 允许 handover，不要求音频端点。
- `enable_body_haptics` 为开启时，callback 返回 Windows endpoint 探针结果。
- DSX 不使用该 callback。

`src/modules/dualsense/main.py` 不直接导入 GUI、TUI、settings 或 `sounddevice`。它只接收可注入的 callback，并在测试中使用 deterministic fake。

## 交接状态机

仅对当前 transport 为 Bluetooth、目标为同一物理手柄 USB interface 的自动 handover 应用以下流程：

1. Stable topology 首次返回 USB candidate 时，记录 candidate path 和 3 秒 deadline；不打开 candidate，不改变 snapshot，不停止 BT `0x36`。
2. deadline 之前的 topology scan 继续保留 Bluetooth，并且不调用 readiness callback 或 PortAudio。
3. deadline 到达后调用 readiness callback。
4. 若握把触觉已关闭，或 Windows endpoint 已就绪，则执行现有 candidate open、有效 USB input report 验证、旧 BT 静音、`0x08 / 0x02` control teardown 和原子 USB commit。
5. 若 endpoint 尚未就绪，不打开或提交 USB candidate，当前 BT handle、输入、扳机键、握把输出和 UI transport 全部保持不变。对该 path 使用现有 1/2/5 秒退避再次检查；已经完成的 3 秒稳定窗口不重复计时。
6. USB candidate 消失、身份变化或当前 transport 改变时，清除对应 settle 状态和 retry 状态。
7. USB commit 后，现有 `UsbAudioLifecycle` 第一次调用 `UsbAudioHaptics.start()`；此时才允许 `sounddevice.query_hostapis()` 与 `query_devices()` 初始化 PortAudio 设备表。

3 秒期间不阻塞唯一 DualSense I/O thread。BT input、pending trigger output 和 `0x36` haptics 必须继续正常调度。

`0x08 / 0x02` 仍保留为端点就绪后的旧 Bluetooth control teardown 步骤，但不再把它描述为单独修复。它返回成功只代表 host 接受 feature report，不代表 USB 握把触觉已经恢复。

## 失败处理与日志

- endpoint 未就绪：记录一次明确日志，说明保留 Bluetooth 并将在退避后重试；不得记录 controller disconnected。
- readiness callback 抛出异常：按“未就绪”处理并限频记录 warning，不能提交 USB。
- USB candidate validation 失败：沿用现有 1/2/5 秒退避，保持 BT。
- control teardown 失败：关闭未采用 USB candidate，保持 BT。
- endpoint 已就绪但 USB stream 开启失败：保留现有 R6 日志和失败处理，不调用 PortAudio 私有重置。该情况必须作为另一项实机故障记录，不能伪装成成功。
- 日志顺序应能证明 `USB audio endpoint ready` 出现在 control teardown 和 `BT -> USB` commit 之前，`USB body haptics started` 出现在 commit 之后。

## 自动测试

至少覆盖：

1. Windows endpoint 探针只接受活动的 DualSense/Edge USB audio render endpoint；拒绝 disabled、unplugged、非 Sony、错误 interface 和损坏属性。
2. 注册表缺失、权限异常和非 Windows 分支安全返回。
3. BT -> USB candidate 在 3 秒 deadline 前不验证、不提交，也不影响 BT pending output。
4. deadline 后 endpoint 未就绪时保持 BT snapshot、handle 和 haptics，并进入 1/2/5 秒重试。
5. endpoint 随后就绪时不重复 3 秒窗口，执行一次 validation、control teardown 与 commit。
6. candidate 消失或 transport 改变时清理 settle state。
7. 关闭握把触觉时不依赖 endpoint readiness，仍可完成 handover。
8. USB 冷启动、Bluetooth 冷启动、USB -> Bluetooth、普通 reconnect、DSX 和 XInput 路径不调用 readiness gate。
9. 现有 PortAudio 私有 API 禁用契约继续通过，`audio.py`、`lifecycle.py` 和 `manager.py` 不加入新的 refresh、heartbeat 或 retry 机制。

完成定向测试后运行完整 pytest、Ruff、Pyrefly、限定路径 compileall、`uv lock --check` 与 `git diff --check`。

## 实机验收

固定条件：Forza 游戏内振动关闭，Steam 版 Steam Input 开启，使用同一 Profile、车辆和路段。

1. USB 冷启动，确认握把触觉与 L2/R2 扳机键没有回归。
2. Bluetooth 冷启动，确认四通道握把触觉正常。
3. Bluetooth 正常输出时插入 USB：前 3 秒状态保持 Bluetooth 且握把继续工作；随后状态进入 USB，允许切换点短暂静默，但 USB 握把必须恢复且扳机键不得反复脉冲。
4. 检查日志顺序包含 endpoint ready、control teardown、transport commit 和 USB body haptics started，不再出现 handover 后永久缺少端点。
5. 拔掉 USB，确认 Bluetooth reconnect 与 `0x36` 握把触觉恢复。
6. 退出候选后直接运行已发布 R6，确认候选未留下跨进程污染。

如果第 3 步仍进入 USB 但没有握把触觉，或候选退出后破坏 R6，则方案 A 仍判定失败，不发布 R7。

## 明确不修改

- Forza UDP listener、telemetry、握把 mixer、红线、碰撞、路面和抓地力算法。
- L2/R2 扳机键效果、优先级和 Profile 默认值。
- Enhanced R6 的 USB stream 参数、PCM channel 2/3 映射、callback 与 stop 行为。
- GUI/TUI 页面、DPI、更新器、FH6 utilities、XInput bridge 和发布版本号。
- 不新增用户设置；3 秒窗口属于 transport 正确性交接。

## 成功标准

- 自动测试证明 PortAudio 不会在 endpoint readiness 之前初始化。
- endpoint 迟到或探针异常时，应用持续保留可用的 Bluetooth 握把触觉。
- 真实硬件证明 BT -> USB 后状态、L2/R2 扳机键和 USB 握把触觉都正常。
- 候选退出后 R6 无跨进程回归。
- 实机通过前不得发布 R7，也不得把 BT -> USB 握把触觉写成已修复。

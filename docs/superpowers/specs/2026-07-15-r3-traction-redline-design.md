# Enhanced R3 抓地力路由与红线握把警告设计

## 状态

- 日期：2026-07-15
- 分支：`feat/r3-traction-redline`
- 状态：用户已选择方案 A，并授权直接实施到真实游戏测试就绪
- 范围：通用轮胎抓地力扳机反馈、红线握把警告、R3 开发身份与对应设置/测试/文档

## 目标

Enhanced R3 将 R2 中仅属于油门 wheelspin 的扳机反馈扩展为通用轮胎抓地力/纵向滑移反馈，并按 Forza/Xbox 的踏板语义路由：制动状态进入 L2 扳机键，驱动状态进入 R2 扳机键，同时踩下油门和刹车时抓地力只进入 R2 扳机键。红线警告从 R2 扳机键移到双侧握把，避免轮胎状态与发动机状态争夺同一扳机。

## 输入定义

“握住 L2/R2”以 Forza Data Out 的 `brake` 和 `accel` 字节判断，不读取 DualSense 物理输入报告。踏板使用现有 `brake_deadzone` 与 `accel_deadzone`，因此 Steam Input 与游戏实际接受的输入仍是唯一事实来源。

路由表：

| 刹车 | 油门 | 通用抓地力输出 |
| --- | --- | --- |
| 未超过 deadzone | 未超过 deadzone | 无扳机抓地力反馈 |
| 超过 deadzone | 未超过 deadzone | L2 扳机键 |
| 未超过 deadzone | 超过 deadzone | R2 扳机键 |
| 超过 deadzone | 超过 deadzone | R2 扳机键 |

ABS 不是通用抓地力反馈。即使同时踩下两个踏板，真实 ABS 仍可在 L2 扳机键输出 GT7 风格 ABS wall，同时通用抓地力在 R2 扳机键输出。

## 通用抓地力信号

保留 R2 已验证的单个 stateful EWMA 与 hysteresis，不建立左右两套独立算法：

- 只有油门时，高于 `LOW_SPEED_KMH` 使用驱动轮绝对 longitudinal slip；低于该速度继续使用驱动轮绝对 wheel rotation，保留原地烧胎。
- 只有刹车时，高于 `LOW_SPEED_KMH` 使用四轮绝对 longitudinal slip；低速不使用 wheel rotation 猜测制动抓地力，因为缺少轮胎半径与可靠车辆参考速度。
- 同时踩下时，高于 `LOW_SPEED_KMH` 使用四轮最大绝对 longitudinal slip并输出到 R2；低速时仍只使用驱动轮 rotation，避免把正常滚动误判为烧胎。
- 没有踏板超过 deadzone 时立即解除 latch 并重置 EWMA，松油漂移和滑行不会让扳机自行振动。

产生最大有效信号的轮胎决定铺装、积水、泥土或碎石频带。材质只能改变已有滑移反馈的频率和强度，不能自行产生能量。为保持 R2 Profile 兼容，生产字段暂时保留 `wheelspin_*` 内部名称；GUI/TUI 和文档改称 Traction/grip feedback，并把内部命名债记录到 `PROJECT_STATE.md`。

## 扳机优先级

L2 扳机键：

1. Gear shift thump
2. ABS wall
3. 仅 L2 路由的通用抓地力
4. Firmware end wall
5. Static brake wall
6. Brake resistance

R2 扳机键：

1. Gear shift thump
2. Idle buzz
3. 路由到 R2 的通用抓地力
4. Firmware end wall
5. Throttle resistance

R2 扳机键不再包含 rev limiter effect。换挡冲击本轮保留在扳机，因为用户只要求迁移红线，而且短促换挡 kick 与持续的轮胎抓地力不存在同样的语义冲突。

## 红线握把警告

红线警告进入现有 `HapticMixer`，与发动机底振共享 telemetry、Body Haptics 总开关和 `engine_haptics_intensity`：

- 触发条件为油门超过 `accel_deadzone` 且 `rpm / max_rpm >= rev_limit_ratio`。
- 进入时立即从脉冲 on-phase 开始；高于阈值期间持续延长 hold，跌破阈值后使用 `rev_limit_hold_ms` 防止 RPM 跳动导致断续。
- 左右握把高频通道使用相同的 10 Hz、50% duty 断油式脉冲。USB 与 Bluetooth 使用完全相同的触发条件、时序和归一化强度；它们只有传输/合成路径不同，不定义高低配行为。
- 脉冲叠加在左右现有 high-frequency 分量上，连续发动机 saw wave 保留，因此用户感受到的是发动机底振上的对称急促断油提示。
- Body Haptics 关闭、`engine_haptics_intensity=0` 或 `enable_rev_limiter=False` 时不产生红线握把警告。
- 手刹加全油但没有达到 RPM 阈值不再伪造红线；低速烧胎由通用抓地力负责。

现有 `rev_limit_freq` 改为握把脉冲节奏，默认从 30 调为 10 Hz；`rev_limit_amp` 改为握把脉冲强度，默认从 12 调为 96/255；`rev_limit_ratio`、`rev_limit_hold_ms` 与 `enable_rev_limiter` 保留。读取版本 2 的命名 Profile 时，只把仍等于 R2 旧默认值的 30/12 迁移为 10/96，用户自定义值不覆盖。Default Profile 继续由 R3 代码默认值刷新。

## 设置、界面与版本

- GUI/TUI 把 `Redline (rev limiter) buzz` 解释为双侧握把警告，把 `Buzz speed` 改为 pulse rate。
- `Wheelspin buzz` 改为 `Traction/grip feedback`；高级区相应改名，但字段名保持兼容。
- 同步所有现有非英语 catalog，中文必须明确区分 Enhanced R3 与 R2 扳机键。
- R3 功能分支将内部版本改为 PEP 440 `3`，GUI/TUI 显示 `R3`，本地 Windows 测试产物名为 `FH-DualSense-Enhanced-R3.exe`。这不是公开 Release，也不修改现有 tag 或 R2 资产。

## 测试与明日实车验证

自动测试必须覆盖：

- 四种踏板组合的抓地力路由；
- L2 抓地力、R2 抓地力与双踏板时的 R2 唯一路由；
- 双踏板时 L2 ABS 与 R2 抓地力可同时存在；
- 低速刹车不使用 wheel rotation，低速油门仍保留 burnout；
- 松开踏板重置状态；四种材质频带仍由 dominant wheel 决定；
- R2 扳机键在红线、有抓地和无抓地时都不再产生 rev effect；
- 红线握把立即 on、按 10 Hz 交替、120 ms hold、双侧对称、服从三个开关/强度门控；
- USB frame 与 Bluetooth compatible rumble 对同一红线 envelope 保持相同 normalized timing/intensity；
- R2 Profile 旧默认迁移、自定义值保留，以及 GUI/TUI/翻译 parity；
- 内部版本 `3`、公开 `R3` 和 Windows 测试产物命名。

本地门禁为定向 pytest、全量 pytest、`compileall`、`git diff --check`、update-enabled ZUV inspect 和 Windows EXE build/version/icon/`--help` 冒烟。

明日真实游戏依次验证：普通高转但未过阈值、达到红线并持续、快速升挡穿越红线、抓地力与红线同时发生、USB/Bluetooth 各一轮。成功标准是红线脉冲能从连续发动机底振中辨认，同时不在 R2 扳机键出现；通用抓地力按踏板路由且 ABS 仍保持 L2 优先。

## 非目标

- 不修改 DualSense HID report、BT CRC、USB 音频设备选择、Forza packet offsets 或 DSX 行为。
- 不迁移换挡冲击，不新增基于实际手柄 input report 的踏板读取。
- 不发布 R3 Release，不修改 `R2`/`R2-preview` tag 或资产。
- 不在没有用户实车确认前把红线默认手感写成已验证。

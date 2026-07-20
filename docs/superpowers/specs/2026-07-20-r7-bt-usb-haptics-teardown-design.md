# R7 Bluetooth 到 USB 握把触觉交接设计

日期：2026-07-20

## 已验证问题

真实 DualSense 硬件测试已经确认以下行为：

- USB 冷启动与 Bluetooth 冷启动都可以正常产生握把触觉。
- 同一进程从 Bluetooth 切换到 USB 后，HID 输入、L2/R2 扳机键和连接状态能够进入 USB，但 USB 握把触觉消失。
- 退出并重启应用、拔插 USB 都不能恢复该 USB 握把触觉。
- 将手柄完全关机后再通过 USB 启动可以恢复。

上述证据说明问题不是 USB 冷启动生命周期、Forza UDP、Profile 强度或普通应用进程状态。最符合现象的解释是：手柄固件仍保留先前的 Bluetooth `0x36` 触觉会话，USB HID 已经接管输入和扳机键，但 USB audio haptics 未能重新接管握把执行器。该解释是基于实机行为的工程判断；Sony 没有公开确认此内部状态机。

## 目标

1. 在已经验证 USB 候选接口有效的 BT -> USB handover 中，明确终止旧 Bluetooth 触觉会话。
2. 交接后继续使用 Enhanced R6 已验证的 USB `sounddevice` / PortAudio 生命周期，不再修改其开流、回调或停止逻辑。
3. 保持 Enhanced R7 的同一手柄身份判断、USB 优先、候选句柄预验证、单 I/O thread 和原子 transport handover。
4. 允许交接时最多约一秒没有握把输出，但不得产生持续丢失、扳机键反复脉冲或跨进程污染。

## 方案比较

### 方案 A：通过旧 BT control handle 显式关闭 Bluetooth 会话（采用）

在 USB candidate 已经打开并读取到有效输入报告后，通过仍然有效的旧 BT handle 发送 feature report `0x08`，payload 首字节为 `0x02`。该命令来自 `awalol/DS5Dongle` 当前参考修订中的 `bt_power_off_controller()`；其源码说明 `1=on, 2=off`。

优点是它直接针对只有手柄完全关机才能清除的 Bluetooth 固件状态。缺点是该协议没有 Sony 官方公开文档，而且参考项目将其命名为“关闭控制器”，不能假定它只关闭 Bluetooth radio。因此先以隔离的硬件候选验证，不把成功写成既定事实。

### 方案 B：追加静音 `0x36` 并延时关闭

连续发送多帧静音 `0x36`，等待若干 packet period 后关闭 BT handle。该方式风险较小，但当前一帧静音已经证明只能停止样本，不能清除持久会话；没有证据表明增加帧数会改变固件状态，所以不采用。

### 方案 C：USB 输入与 BT 握把输出并存

USB 接管 HID 输入和扳机键，同时长期保留 BT handle 专门发送 `0x36`。它可能绕过 USB 接管失败，但会破坏单一 I/O owner、让界面显示的 USB 与实际触觉 transport 不一致，并引入双句柄竞争和退出清理问题，所以不采用。

## 协议封装

在 `src/modules/dualsense/bt_haptics.py` 中增加独立、纯函数式的 Bluetooth control feature-report builder，不把该命令混入普通 trigger、visual state 或 `0x36` packet builder。

输出契约依据 DS5Dongle 的 `set_feature_data(0x08, payload, 47)` 和 `fill_feature_report_checksum()`：

- hidapi buffer 总长为 48 bytes。
- byte 0 是 report id `0x08`。
- byte 1 是 Bluetooth control 值 `0x02`。
- 未使用 payload byte 为零。
- 最后四个 byte 保存 little-endian CRC32。
- CRC 覆盖 report id 以及校验字段之前的内容，并使用参考实现的 feature-report seed `0x2060EFC3`。

builder 必须有字节级单元测试，固定长度、report id、control byte、零填充和 CRC。Windows `hidapi.send_feature_report()` 接收的 buffer 从 report id 开始，不包含 Bluetooth HID control transaction byte `0x53`；`0x53` 只存在于 DS5Dongle 自己构造的 L2CAP control frame 中。

## 交接调用链

仅当当前 transport 为 Bluetooth、目标 transport 为 USB 且候选 USB handle 已读取到同一手柄的有效输入报告时执行以下顺序：

1. 保留已经验证的 USB candidate handle，不发布 transport 变化。
2. 在唯一 DualSense I/O thread 上，通过旧 BT handle 发送现有的一帧静音 `0x36` 和 L2/R2 扳机键 release。
3. 仍通过旧 BT handle 调用 `send_feature_report()` 发送 `0x08 / 0x02`。
4. 只有 feature report 返回正数时，才关闭旧 BT handle 并提交已验证 USB handle。
5. handover 发布为 USB 后，由现有 `HapticManager` transport routing 停止 BT backend，并由未修改的 Enhanced R6 USB lifecycle 启动 USB audio stream。
6. 应用不额外播放启动脉冲；正常 telemetry 下一帧恢复触觉，允许约一秒短暂静默。

普通 USB 冷启动、普通 Bluetooth 冷启动、USB -> Bluetooth、完全断线后的 reconnect、DSX 与 XInput bridge 不调用该 feature report。

## 失败处理

- USB candidate 打开、身份匹配或输入验证失败：保持现有 BT handle 与输出，沿用 1/2/5 秒 candidate backoff。
- `send_feature_report()` 抛出异常或返回非正数：关闭未采用的 USB candidate，保持旧 BT transport，并对该 candidate 使用现有 backoff；不得先关闭旧 BT handle。
- feature report 报告成功但使手柄两种接口都短暂掉线：正常 input watchdog 必须清除连接状态，之后仅通过既有 reconnect 流程重新打开有效 USB；不得伪造 USB connected。
- feature report 成功、USB 输入保持有效但握把仍不恢复：该协议探针判定为实机失败，停止继续叠加未经验证的 HID flag 或 PortAudio刷新。R7 不得据此发布。
- 日志必须区分 candidate validation、Bluetooth control teardown、transport commit 和 reconnect，且不得记录“成功恢复握把”这种只能由实机确认的结论。

## 自动测试

至少补充以下测试：

1. feature report builder 的 48-byte 固定布局和 CRC fixture。
2. BT -> USB 成功路径只调用一次旧 BT handle 的 `send_feature_report()`，且发生在旧 handle close 之前。
3. USB -> BT、USB 冷启动、BT 冷启动和普通 reconnect 不调用 feature report。
4. feature report 抛出异常或返回 `0` 时，USB candidate 被关闭，BT handle、snapshot、transport 和 pending output 保持不变，并进入现有 backoff。
5. 成功 commit 后不产生 startup pulse，旧 BT handle 被关闭一次，validated USB report 成为首个 USB snapshot。
6. 现有 USB audio lifecycle 文件继续与 tag `R6` 保持无差异。

执行定向测试后，还必须运行完整 `pytest -q`、Ruff、Pyrefly、限定路径 `compileall`、`uv lock --check` 和 `git diff --check`。

## 实机验收顺序

固定测试条件：Forza 游戏内振动关闭；Steam 版保持 Steam Input 开启；使用同一 Profile、车辆和路段。

1. 手柄完全关机后用 USB 冷启动候选，确认握把和 L2/R2 扳机键仍正常。
2. 手柄完全关机后用 Bluetooth 冷启动候选，确认四通道握把触觉没有变成 compatible rumble。
3. 在 Bluetooth 正常握把输出时插入 USB，允许约一秒静默，确认状态进入 USB、扳机键不反复脉冲、USB 握把恢复。
4. 退出候选后直接运行已发布 R6，确认候选没有留下会破坏 R6 的跨进程状态。
5. 拔掉 USB 回到 Bluetooth，确认 reconnect 和 Bluetooth `0x36` 握把触觉恢复。

如果第 3 步导致整只手柄掉电且不能依靠既有 reconnect 自动回到 USB，或 USB 握把仍不恢复，则方案 A 视为失败，不进入 R7 发布。

## 明确不修改

- `src/modules/haptics/audio.py`、`lifecycle.py` 和 `manager.py` 的 Enhanced R6 USB lifecycle。
- Forza telemetry、握把 mixer、L2/R2 扳机键算法、Profile 默认值和游戏手感。
- 正常 DualSense output state report 的 valid flags。
- GUI/TUI、更新器、DPI、FH6 utilities、XInput bridge 和发布版本号。
- 不增加设置开关；这是 transport 正确性交接，不是用户手感选项。

## 成功标准

- 自动测试证明命令只能出现在经过验证的 BT -> USB 边界，失败可安全保留当前 BT 会话。
- 真实硬件证明 Bluetooth 与 USB 冷启动均无回归。
- 真实硬件证明 BT -> USB 后 USB 握把在约一秒内恢复，L2/R2 扳机键无反复脉冲，连接状态为 USB。
- 候选退出后 Enhanced R6 仍可直接正常产生握把触觉。
- 未通过上述硬件验证前，不发布 R7，不把该行为写成已修复。

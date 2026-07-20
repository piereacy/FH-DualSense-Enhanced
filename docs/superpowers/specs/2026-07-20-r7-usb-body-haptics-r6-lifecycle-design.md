# R7 USB 握把触觉恢复 R6 生命周期设计

日期：2026-07-20

## 问题与证据

- 同一次 Windows 启动、同一根 USB 连接、同一游戏和配置下，已发布 R6 的 USB 握把振动正常，当前 R7 候选完全没有 USB 握把振动。
- R7 进程已经在 DualSense 四声道 WASAPI 端点建立活跃音频会话，但连续三秒采样到的四个通道峰值全部为零。因此问题位于 R7 USB PCM 生产或生命周期路径，不是设备缺失、用户强度为零、DSX、UDP 端口或手柄收到音频后不响应。
- 本问题只指 USB 握把触觉（body haptics）。L2/R2 扳机键反馈和 Bluetooth 握把触觉不属于本次回滚范围。

## 目标

1. 将 USB 握把音频的开流、`running` 判定、回调、停止和上层生命周期精确恢复到 R6 已验证实现。
2. 保留 R7 已有的控制器连接真值、USB/Bluetooth 拓扑探测、候选句柄预验证、原子 HID handover、USB 优先、连接状态界面和 Bluetooth `0x36` 握把输出。
3. 不再向 R6 生命周期叠加推测性修复；先恢复已知正常的 USB 冷启动，再实机验证现有热切换框架在该基线上是否仍能恢复握把输出。

## 修改边界

### `src/modules/haptics/audio.py`

USB `UsbAudioHaptics` 恢复为 tag `R6` 的行为：

- `running` 直接反映 R6 的 `_running` 状态。
- `start()` 使用 R6 的设备查询、四声道 `OutputStream` 构造与启动顺序。
- `_audio_callback()` 使用 R6 的锁、PCM renderer 和声道 2/3 映射。
- `stop()` 使用 R6 的静音、停止、关闭与 renderer reset 顺序。
- 删除 R7 新增的 callback heartbeat、callback timeout、实例级 lifecycle lock，以及 `_terminate()` / `_initialize()` PortAudio 强制刷新。

### `src/modules/haptics/lifecycle.py`

`UsbAudioLifecycle` 恢复为 tag `R6` 的行为：

- USB 且握把触觉启用时，已运行则保持，否则直接调用一次 `start()`。
- 不满足条件时静音并停止。
- 删除 R7 新增的 retry clock、retry interval、eligible 状态和 backoff。

### `src/modules/haptics/manager.py`

- USB routing 恢复 tag `R6` 的启动失败、共享 audio 实例和 frame 投递语义。
- 删除 R7 新增的 USB retry timer/backoff。
- Bluetooth HD、compatible fallback、transport routing 和关闭语义保持现有实现；不得借本次修复改变 Bluetooth 手感。

### 明确不修改

- `src/modules/dualsense/main.py` 中 R7 的拓扑 handover、输入真值、输出队列、HID report 长度、Bluetooth CRC 和当前已恢复的 R6 valid-bit 契约。
- `src/modules/dualsense/topology.py`、连接状态呈现、自动重连和重新连接命令。
- Forza 遥测、扳机算法、握把 mixer、社区默认参数、前端布局、更新器和 XInput bridge。
- 不恢复错误的 `valid_flag0=0x20` / `valid_flag1=0x20`，也不发送猜测性的单次 `0x01` 重置。

## 热切换边界

“保留热切换”指 R7 的设备发现、USB 优先、候选 USB handle 验证、原子 HID transport 交换、状态更新和 R2 扳机键脉冲抑制继续存在。本次不会删除后重写这些功能。

USB 握把音频在 handover 后能否随 R6 生命周期正确启动必须重新实测，不能由代码存在推断为已通过。如果 USB 冷启动恢复而 BT → USB 握把仍失败，应把该结果单独记录并设计下一项最小改动；本次不得提前把 PortAudio 强制刷新或 callback heartbeat 混回去。

## 自动验证

- 添加或调整测试，锁定 `UsbAudioHaptics`、`UsbAudioLifecycle` 和 `HapticManager` USB 分支的 R6 语义。
- 保留 HID 字节级测试，确保两个错误 `0x20` 不会重新出现。
- 执行完整 `pytest -W error`、Ruff、Pyrefly、限定路径 `compileall`、`uv lock --check` 和 `git diff --check`。
- 构建一个规范命名的 R7 Windows one-file 候选，检查 MZ、PE 版本、文件名和 SHA-256 sidecar。

## 实机验收

测试时固定：Forza 游戏内振动关闭；Steam 版保持 Steam Input 开启；使用同一车辆和同一路段。

1. 重启后运行 R6，确认 USB 握把基线正常。
2. 关闭 R6，运行新候选，确认 USB 冷启动握把正常；同时确认 L2/R2 扳机键没有回归。
3. 关闭新候选再运行 R6，确认新候选没有跨进程污染 R6。
4. 新候选以 Bluetooth 启动，确认 Bluetooth 握把没有回归。
5. 新候选执行 BT → USB → BT，允许切换时约一秒静默，但握把必须恢复、连接方式必须正确、R2 扳机键不得反复脉冲。

## 成功标准

- 新候选 USB 冷启动恢复与 R6 一致的握把振动。
- 新候选退出后 R6 仍正常。
- 自动测试和构建门禁全部通过。
- R7 热切换框架仍存在；真实 BT → USB → BT 结果被如实记录，未通过时不发布 R7，也不声称热切换完成。


# Enhanced R3 Bluetooth HD Haptics 设计

日期：2026-07-15
状态：设计已确认并实现，USB/Bluetooth 主观同场景对照进行中

## 目标

让 FH-DualSense-Enhanced 自身根据 Forza 遥测合成的握把触觉在 USB 与 Bluetooth 下使用同一套波形和左右声道语义。Bluetooth 不再把 `HapticFrame` 压缩成两个 compatible rumble 强度，而是直接向物理 DualSense 发送 Sony Bluetooth 音频触觉报告。

目标不包含接管游戏自身的 USB Audio、菜单、CG 或过场振动。那需要 vDS 式虚拟 USB 设备和过滤驱动，继续作为后续独立工作。

## 已确认事实

- 当前 USB 后端在 `src/modules/haptics/audio.py` 中以 48 kHz、四声道输出，后两个声道分别驱动左右握把。
- 当前 Bluetooth 路由在 `src/modules/haptics/manager.py` 中调用 `to_compatible_rumble()`；该函数对左右声道取 `max()`，因此必然丢失方向、任意频率和事件波形。
- vDS `0.3.0-rc7` 和 DS5Dongle 展示了 DualSense Bluetooth 音频触觉报告。vDS 使用 report ID `0x36`、398 字节报告和 64 字节交错左右触觉采样；采样率为 3 kHz。
- 当前手柄固件的 Bluetooth HID report descriptor 暴露了 `0x36` 对应的 398 字节输出报告。本项目现有 hidapi 句柄已实机连续写入：完整链平均发送间隔 `10.668 ms`、最大 `11.204 ms`、零覆盖且连接保持。

## 方案

### 共享波形合成

新增传输无关的 `HapticPcmRenderer`：

- 输入为现有 `HapticFrame`。
- 输出为左右两声道浮点 PCM。
- 保留当前 65 Hz 低频、190 Hz 复合高频、动态发动机锯齿波、相位连续和每 10.667 ms 一次的 0.35 电平平滑。
- USB 以 48 kHz、512 帧调用；Bluetooth 以 3 kHz、32 帧调用。两者块时长相同，因此使用同一算法和时间尺度。

### USB 传输

`UsbAudioHaptics` 继续打开 DualSense 四声道端点。回调只负责读取当前帧、调用共享 renderer，并把左右 PCM 写到声道 3/4；声道 1/2 保持静音。

### Bluetooth 传输

新增 `BluetoothAudioHaptics` 工作线程：

- 每 32 / 3000 秒生成 32 帧左右 PCM。
- 将浮点 PCM 量化为 64 字节交错 signed int8。
- 只保留最新待发送块，发生调度积压时丢弃旧块，避免以补发方式增加触觉延迟。
- 通过 DualSense I/O 线程队列发送，不从第二个线程直接并发写 hidapi 句柄。

DualSense 新增纯协议构建器：

- report ID `0x36`，总长 398。
- 包含当前 L2/R2 扳机状态的 63 字节 state block。
- 包含 64 字节 haptics block。
- 不启用或填充 controller speaker 数据块。
- CRC 继续使用 Bluetooth output 前缀 `0xA2`。
- report sequence 和 audio packet sequence 分别递增并回绕。

现有 `0x31` 状态报告继续负责普通扳机更新。所有 HID 写入仍由 `DualSense._io()` 串行完成。

### 路由与回退

`HapticManager` 的 Bluetooth 路由顺序：

1. 首选 `BluetoothAudioHaptics`。
2. 后端启动或写入失败时，记录一次警告并回退到 compatible rumble。
3. 断开、切换 USB、关闭 Body Haptics 或退出时，先发送静音块，再停止线程。
4. 重新连接 Bluetooth 后允许重新尝试 HD haptics，不能永久锁死在回退状态。

USB 端点失败仍只影响 USB body haptics，不影响扳机；Bluetooth HD haptics 失败同样不得阻塞扳机。

## 调度约束

- Bluetooth 音频周期约 10.667 ms。
- 队列深度为 1；新块覆盖尚未发送的旧块并计数。
- HID I/O 循环在有音频块时由 event 立即唤醒，不能依赖现有 500 ms watchdog 周期。
- 停止流时必须至少排队一个全零块，防止执行器保持最后一个非零样本。
- 遥测仍由 `UDPListener.recv_latest()` 丢弃旧包，不能因触觉发送改成逐包追赶。

## 测试与实机门禁

自动测试必须覆盖：

- 共享 renderer 的左右隔离、相位连续、静音和 USB 回归。
- signed int8 量化与交错顺序。
- `0x36` 长度、字段、state/trigger offset、序列回绕和 CRC。
- Bluetooth 队列覆盖、静音停止、transport 切换和 compatible rumble 回退。
- HID I/O 线程串行发送 `0x31` 与 `0x36`，失败不阻塞扳机/reconnect。
- 全量 pytest、compileall、`git diff --check` 和 PyInstaller EXE build/`--help` 冒烟。

实机必须分别记录：连接方式、游戏内振动开关、Steam Input 状态。先用合成左右/频率/碰撞段确认协议，再在相同路段和事件下对比 USB 与 Bluetooth；未实测不得宣称完全一致。

## 归属

Bluetooth 报告格式参考：

- hurryman2212/vds `0.3.0-rc7`，MIT License。
- awalol/DS5Dongle，参考 revision 的仓库根 `LICENSE` 为 MIT。

任何直接移植的实现都必须同步更新 `docs/THIRD_PARTY_NOTICES.md`，发行包继续包含该文件。

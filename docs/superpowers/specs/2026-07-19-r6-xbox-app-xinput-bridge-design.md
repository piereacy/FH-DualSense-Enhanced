# Enhanced R6 Xbox App XInput 桥设计

日期：2026-07-19

状态：设计已确认，待实现

## 1. 目标

在 Windows 版 FH-DualSense-Enhanced 内直接提供基础 DualSense 到 XInput 的输入桥，使 Xbox App 版 Forza Horizon 4、Forza Horizon 5 和 Forza Horizon 6 可以把物理 DualSense 当作标准 Xbox 手柄使用，不要求用户运行 DS4Windows，也不要求把 Xbox App 游戏添加到 Steam。

桥接目标固定为虚拟 Xbox 360 Controller。ViGEmBus 不支持真正的 Xbox One target，而 Xbox 360 与标准 Xbox One 手柄具有相同的基础按钮、摇杆和扳机布局；FH-DualSense-Enhanced 继续独立负责自适应扳机、USB/Bluetooth 握把触觉和灯效。

成功标准是：选择 Xbox App 平台、关闭 Steam Input 后，Steam 版 Forza 仍能通过 FH-DualSense-Enhanced 的虚拟手柄完整接收转向、油门、刹车和按钮。这可以验证 XInput 桥本身。由于当前没有 Xbox App 版游戏，真实 Xbox App 游戏验收必须保留为未执行，不能写成已验证。

## 2. 已确认的产品边界

- 仅支持 Windows x64。Linux、Windows x86 和 Windows ARM64 不启用该桥。
- 全局平台选择为 `Steam` 或 `Xbox App`，默认 `Steam`。
- Steam 模式完全不加载 ViGEmClient、不创建虚拟手柄，继续由 Steam Input 接管。
- Xbox App 模式在物理 DualSense 可用时自动创建虚拟 Xbox 360 Controller，不依赖 Forza UDP 是否已经收到遥测。
- 不安装、配置或利用 HidHide。现有 HidHide 探测只保留给既有 DualSense handle 保活逻辑，与 XInput 桥无关。
- 不集成或复制 DS4Windows。DS4Windows 的 GPL-3.0 代码不进入本项目。
- 不注册 ViGEm rumble callback，不接管、转发或混入游戏原生振动。Forza 游戏内振动仍要求关闭。
- 不模拟 Xbox One、GameInput impulse triggers、触摸板、陀螺仪、麦克风键或多手柄路由。
- 首版不发现或启动 Xbox App 游戏。Xbox App 模式明确提示用户从 Xbox App 手动启动游戏，不猜测 Package ID 或 URI。
- XInput 桥不自动管理 DS4Windows、Steam Input 或其他现有虚拟手柄；虚拟 target 使用 Windows 分配的空闲 XInput slot。

## 3. 选定架构

采用“单一 HID 读取者 + 最新状态槽 + 独立 ViGEm worker”。

### 3.1 输入解析层

新增 `src/modules/dualsense/input_state.py`，包含不可变 `DualSenseInputState` 和 USB/Bluetooth 报告解析纯函数。字段固定为：

- `left_x`、`left_y`、`right_x`、`right_y`：原始 `0..255`。
- `left_trigger`、`right_trigger`：原始 `0..255`。
- `dpad`：九种离散状态，包括中立和八方向。
- 标准数字按钮集合。
- `received_at` 不进入值对象，由发布槽单独记录单调时钟时间。

解析器必须根据 transport、report ID 和最小长度显式选择布局。错误 report ID、错误长度或无法解释的方向键值直接拒绝，不能用部分字节生成控制状态。USB 与 Bluetooth 的具体 offset 以真实 DualSense 报告和字节级测试固定，不从 DS4Windows 源码复制。

### 3.2 物理 HID 所有权

现有 `src/modules/dualsense/main.py` 的 I/O 线程继续是唯一调用物理 `hidapi` handle 读取输入的线程。禁止另一个线程或进程并发读取同一 handle。

Steam 模式保留当前空闲等待行为。Xbox App 模式启用输入 consumer 后：

- USB 目标轮询周期约 `1 ms`。
- Bluetooth 目标轮询周期约 `4 ms`。
- 每个有效报告解析后调用非阻塞 `publish_latest(state, received_at)`。
- 发布只替换最新值并设置 event，不执行 ViGEm 调用，不等待 worker，也不排队旧状态。

现有 trigger、灯效、compatible rumble 和 Bluetooth `0x36` 写入继续由同一 I/O 线程串行执行。输入轮询加速不能改变输出报告布局、CRC、触觉周期或左右映射。

### 3.3 XInput bridge worker

新增 `src/modules/xinput/bridge.py`。`XInputBridge` 独占 ViGEm client 和 Xbox 360 target，并提供最小生命周期：

- `start()`：启动 worker，但不保证 target 已存在。
- `publish_latest(state, received_at)`：常数时间发布最新输入。
- `stop()`：中立化、移除 target、释放 client 并停止 worker。
- `snapshot()`：返回线程安全、不可变的运行状态供 GUI/TUI 使用。

worker 被新状态 event 或安全超时唤醒。多个状态在处理前到达时只处理最后一个，不回放积压。只有 worker 可以调用 ViGEm target add、update、remove 和 client free。

### 3.4 ViGEmClient 适配层

新增 `src/modules/xinput/vigem_client.py`，使用 Python `ctypes` 定义最小 API 和 `XUSB_REPORT`：

- client alloc、connect、disconnect、free。
- Xbox 360 target alloc、add、update、remove、free。
- ViGEm error code 到项目异常的稳定映射。

不引入 `vgamepad` Python runtime，也不运行其 `setup.py`。仅内嵌经过固定哈希审计的 x64 `ViGEmClient.dll`，由本项目独立实现 Python 封装。

## 4. DualSense 到 Xbox 360 映射

| DualSense | Xbox 360 |
| --- | --- |
| Cross | A |
| Circle | B |
| Square | X |
| Triangle | Y |
| L1 / R1 | LB / RB |
| Create / Options | Back / Start |
| L3 / R3 | Left Thumb / Right Thumb |
| PS | Guide |
| D-pad | 对应方向，斜向同时设置两个方向 bit |
| L2 / R2 | `0..255` analog trigger |
| Left / Right Stick | 完整 signed 16-bit XInput axis |

摇杆转换必须满足：原始中心值映射为零，左右或上下端点覆盖 XInput 的正负端点，Y 轴方向符合 XInput 的“向上为正”。不能在桥内增加 deadzone、response curve、EWMA 或节流；Forza 的游戏内 deadzone 继续负责漂移处理。

触摸板点击、触摸坐标、陀螺仪、加速度计、麦克风键和电池状态不进入 `XUSB_REPORT`。

## 5. 生命周期与安全状态机

对外状态固定为：

- `DISABLED`：Steam 模式或非支持平台。
- `DRIVER_MISSING`：ViGEm client 无法连接到 bus。
- `INSTALLING`：用户已确认并正在运行官方安装器。
- `RESTART_REQUIRED`：安装器明确要求重启，或成功退出后仍无法连接新安装的 bus。
- `WAITING_CONTROLLER`：driver 可用，但尚无有效 DualSense 输入。
- `ACTIVE`：target 存在且持续接收有效输入。
- `STALE`：target 暂时保留，但已经发送中立状态。
- `ERROR`：DLL、client、target 或 update 发生不可恢复错误。

启动和切换规则：

1. Steam 模式不创建 bridge。
2. 切到 Xbox App 时启动 bridge，并尝试连接 ViGEmBus。
3. driver 可用且收到第一份有效 DualSense 状态后，创建 target，先发送中立状态，再发送当前状态。
4. 切回 Steam 或退出程序时，严格按“发送中立状态、移除 target、释放 client”的顺序清理。
5. target 已移除后不得补发先前缓存的按键或轴值。

卡键保护独立于现有 `persistent/latched`：

- 连续 `100 ms` 没有有效输入报告时，向现有 target 发送一次全中立状态并进入 `STALE`。
- 连续 `3 s` 没有有效报告时，移除 target 并进入 `WAITING_CONTROLLER`。
- 输入恢复后重新创建 target，并从中立状态重新开始。

因此，即使现有 DualSense 层因 latched mode 保留了失效 handle，也不能让虚拟油门、刹车、方向或按钮卡住。

## 6. 平台设置和用户界面

新增 global 字段 `preferred_forza_platform: str = "steam"`，允许值仅为 `steam` 和 `xbox_app`。它加入 `preferences.GLOBAL_FIELDS`，不进入车辆 Profile 或 share code。旧配置缺失字段时自动使用 Steam；恢复出厂设置恢复 Steam。

总览在现有 FH4/FH5/FH6 选择旁显示平台选择：

- Steam：保留现有安装发现和 `steam://run/<app-id>` 启动按钮。
- Xbox App：禁用 Steam 启动动作，显示“请从 Xbox App 启动”，并显示 bridge 状态。

GUI、TUI 和 headless 使用同一 global 字段和 bridge service。Tk 控件只读取不可变 `snapshot()` 并在主线程刷新，不能从日志推断状态。用户取消 driver 安装后仍保留 Xbox App 选择，页面显示 `DRIVER_MISSING` 并提供显式重试，不自动切回 Steam。

## 7. ViGEmBus 离线引导

### 7.1 兼容探测

不按安装版本号强制升级。bridge 以 `ViGEmClient` 成功连接 bus 为主要兼容条件，并在物理 DualSense 首次输入到达时通过真实 Xbox 360 target add 验证完整路径。当前电脑的 `1.21.442.0` 若连接成功就直接使用，不启动安装器。

client 已连接但 target add 失败时进入 `ERROR`，不把所有错误都误判成“缺少 driver”，也不循环触发 UAC。

### 7.2 内置安装器

固定使用官方 ViGEmBus Setup `1.22.0`：

- 文件名：`ViGEmBus_1.22.0_x64_x86_arm64.exe`。
- 大小：`6,278,576` 字节。
- SHA-256：`89220A7865076B342892F98865F3499FB7C4CFD673159E89D352C360FD014C6A`。
- Authenticode signer：Nefarius Software Solutions e.U.
- 官方 `1.22.0` 已彻底移除 updater；FH-DualSense-Enhanced 不为 driver 增加更新检查。

PyInstaller one-file 会在程序启动时把捆绑数据解包到临时 `_MEIPASS`，因此“按需”只表示安装器仅在缺少兼容 driver、用户明确确认后才执行，不表示二进制完全不经过启动临时解包。临时目录仍由 PyInstaller 在正常退出后清理。

执行安装前必须：

1. 比较固定 SHA-256。
2. 使用 Windows `WinVerifyTrust` 的 cache-only URL retrieval 验证 Authenticode，禁止为了证书吊销查询建立网络依赖；验证失败时拒绝执行。
3. 显示用途、来源、版本、UAC 和无需联网的明确确认。
4. 通过 `ShellExecuteW` 的 `runas` verb 触发 UAC，不静默提权。

UAC 取消返回 `DRIVER_MISSING` 并保留重试入口；installer 返回 `0` 后立即重新连接 bus，返回 Windows reboot-required code 时进入 `RESTART_REQUIRED`，其他非成功 code 进入 `ERROR`。installer 返回 `0` 但重新连接仍失败时同样进入 `RESTART_REQUIRED`。不能卸载、覆盖或升级已经可以连接的 driver。

## 8. 依赖、许可证和供应链

固定候选客户端资产：

- 来源：`yannbouteiller/vgamepad` `0.1.3` 仓库提交 `3f910aa8bbde49a576683db74ad5e4a0879f8a80` 中的 x64 `ViGEmClient.dll`。
- 大小：`130,048` 字节。
- SHA-256：`2BF0CB1D809039573C922737D298A1653D4DBC61408060FF45A9BCFDE82E97D2`。
- 文件版本资源：`1.0.0.1`。

该 DLL 无 Authenticode 签名，因此运行前以固定 SHA-256 验证打包资产，发布构建通过哈希契约防止被静默替换。最终发布同步更新：

- `docs/THIRD_PARTY_NOTICES.md`。
- GUI/TUI“关于与许可证”。
- Release 附带的 `THIRD_PARTY_NOTICES.md`。

分别保留 ViGEmClient MIT、vgamepad MIT 和 ViGEmBus BSD-3-Clause 声明及项目链接。FH-DualSense-Enhanced 本身继续使用现有自定义许可证，不复制 DS4Windows GPL-3.0 源码。

ViGEmBus 和 ViGEmClient 已归档并停止上游维护，这必须在架构与第三方声明中如实记录。该风险由固定版本、固定哈希、无自动更新和可关闭 bridge 的边界控制，不能写成仍受官方持续维护。

## 9. 错误隔离和日志

- parser 拒绝单个错误报告时保留上次有效时间；达到安全阈值后由 stale 保护中立化，不因随机垃圾字节控制车辆。
- ViGEm DLL load、client connect、target add/update/remove 错误进入 bridge snapshot，并记录稳定错误码和上下文。
- bridge 错误不得关闭 DualSense backend、Forza UDP、trigger、body haptics、灯效或 GUI。
- `ERROR` 状态停止发送，尝试中立化并释放 target；不会无限快速重试或重复弹 UAC。
- 用户切换平台或显式重试才重建不可恢复的 bridge；物理手柄输入恢复可以重建因 stale 超时移除的正常 target。
- 高频输入和 target update 不逐帧写 INFO 日志，只维护计数器和最近错误；详细逐帧诊断只能通过显式 debug 开关短时启用。
- 其他 XInput 设备占用 slot 时使用系统分配结果，不尝试隐藏、断开或重排用户设备。

## 10. 性能和体积预算

最新稳定 R5 Windows EXE 为 `47,218,192` 字节，约 `45.03 MiB`。安装器约 `5.99 MiB`，客户端 DLL 约 `0.12 MiB`。考虑 bridge 代码和 PyInstaller 开销，预计成品约 `51-52 MiB`，增加约 `6-7 MiB`，约 `13%-15%`。用户已在获知该预测后确认内嵌 A 方案。

首个真实构建必须报告：

- 最终 EXE 精确字节数和 MiB。
- 相对线上 R5 的绝对增量和百分比。
- 冷启动与温启动时长，说明 one-file 解包的可见影响。
- Xbox App 模式空闲 CPU 与 Steam 模式基线差异。

最终 EXE 超过 `52 MiB` 时必须暂停发布并重新取得确认。后续增加任何第三方二进制仍独立执行老三样规定的 `5 MiB` 或 `10%` 体积门槛，不能复用本次确认。

## 11. 测试与验收

### 11.1 纯自动测试

- USB 与 Bluetooth 报告分别覆盖全部标准按钮、PS、方向键八方向和中立。
- 两个摇杆覆盖中心和四个端点，Y 轴方向正确。
- L2/R2 覆盖 `0`、中间值和 `255`。
- 错误 report ID、截断报告和非法 D-pad 被拒绝。
- Cross/Circle/Square/Triangle 映射为 A/B/X/Y，Create/Options 映射为 Back/Start。
- `XUSB_REPORT` 字节布局、signed axes、trigger 和 button bits 有固定断言。
- latest slot 在生产速度高于消费速度时只保留最后一个状态。
- fake clock 验证 `100 ms` 中立化、`3 s` target 移除和恢复时不补发旧状态。
- fake ViGEm function table 覆盖 client/target 正常生命周期、各错误码和异常清理顺序。
- Steam 模式不加载 DLL、不启动 worker、不创建 target。
- Xbox App 平台值持久化、旧配置迁移、恢复出厂设置和 Profile/share code 隔离。
- installer SHA、资源文件名、版本、WinVerifyTrust 失败、UAC 取消和安装失败路径。
- 三种许可证与项目链接进入第三方声明和关于页面。
- PyInstaller spec 只使用固定资产并通过哈希契约。

### 11.2 Windows ViGEm 集成测试

在当前电脑现有 `1.21.442.0` 上：

1. 记录启动前 XInput slot。
2. 创建一个 target 并注入合成状态。
3. 用系统 `XInputGetState` 找到新增 slot，反向验证按键、摇杆和扳机。
4. 发送中立状态并移除 target，确认 slot 消失。
5. 验证 bridge 停止后没有残留虚拟设备。

当前电脑不卸载或升级由其他软件安装的 ViGEmBus。缺失 driver 和首次安装使用 mock 验证；真实干净 Windows 离线安装没有执行时必须标为“未执行”。

### 11.3 DualSense 硬件测试

USB 与 Bluetooth 分别执行：

- Windows XInput 反读全部标准按钮、方向、摇杆和扳机。
- 握住 R2 扳机键或方向后断开手柄，验证中立和移除时限。
- Xbox App 模式、Steam Input 关闭、Forza 游戏内振动关闭时，使用 Steam 版 Forza 验证车辆完整可控。
- 同时验证现有自适应扳机、握把触觉和灯效继续工作。
- 切回 Steam 模式后确认虚拟 target 消失；重新开启 Steam Input 后恢复既有 Steam 路径。

硬件记录必须同时写明连接方式、Steam Input、Forza 游戏内振动和最终输入来源。Steam 版结果只能证明 XInput 兼容路径，不能替代 Xbox App 实际游戏验收。

### 11.4 完成前检查

执行定向测试、完整 `uv run --project src pytest -q`、`python -m compileall -q src/modules src/lang`、`git diff --check`、Windows EXE 构建、SHA-256 sidecar 校验、冻结程序启动/退出冒烟和完整工作区差异复核。任何没有执行的 clean-machine driver 安装、Xbox App 游戏或硬件路径必须明确列出。

## 12. 不在本次范围

- Xbox One 或 Xbox Series 虚拟设备协议。
- GameInput、Windows.Gaming.Input 或 impulse-trigger 回传。
- 游戏原生 rumble 捕获、握把混音或原生振动接管。
- HidHide 安装、白名单、cloak 或自动配置。
- DS4Windows、vgamepad Python runtime 或 GPL 代码集成。
- Xbox App 游戏安装发现、Package ID、启动、修复或商店管理。
- 多个 DualSense 对多个 XInput slot 的映射。
- Touchpad、gyro、accelerometer、麦克风键、宏、键鼠映射和 Profile 编辑器。
- Linux 虚拟输入桥。
- 为 Xbox App 未实测状态做“完整支持已验证”的发布声明。

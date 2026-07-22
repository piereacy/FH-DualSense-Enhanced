# 项目决策记录

本文记录会影响后续开发方向、但不适合塞进架构说明的关键决定。新决定应注明日期、状态、原因和后果；已被替代的决定保留并标注替代关系。

## 2026-07-22：Xbox App 平面文件安装采用受限自动发现

- 状态：生产代码和自动测试已完成；当前 Windows 已验证 `.GamingRoot -> C:\XboxGames` 解析，但本机没有真实 Xbox App FH4/FH5/FH6，游戏目录与权限仍待用户环境验收。
- 背景：FH6 语言和图标工具此前只能缓存路径或让用户手动选择。Microsoft GDK flat-file 安装允许用户为每个磁盘配置游戏目录，默认常见位置为 `XboxGames`；对整盘、`WindowsApps` 或无限递归扫描既慢又会触碰不必要的权限边界。
- 决定：新增通用 `discover_xbox_forza_install()`。Windows 只枚举本地 fixed/removable drive，读取每盘最多 4096 字节的 `RGBX` `.GamingRoot` 相对路径并兼容默认 `XboxGames`；每个库只验证库根、标准游戏名和最多 512 个直属目录。候选必须保留在库根内，并通过 FH4/FH5/FH6 对应精确 EXE；FH6 语言和图标还分别要求自身资源目录。成功路径缓存到 `fh6_xbox_install_path`，手动选择与直接 `Content` 仍作为 fallback。
- 边界：不枚举网络或光驱，不扫描 `WindowsApps`、整盘或任意递归子目录，不绕过 ACL，不直启发现到的 EXE，也不把未知 Xbox App 游戏语言伪造成 English。显式手动选择继续用 serial 抢占后台发现。真实 Xbox App 安装验证完成前，只能写成生产代码与自动测试已实现。

## 2026-07-22：Xbox bridge 和物理 HID 故障采用分层自恢复

- 状态：生产代码与自动测试已完成；真实 DualSense Edge、Xbox App 和 30 至 60 分钟 Bluetooth 压力测试未执行。
- 背景：旧物理 HID worker 遇到未预期异常会永久退出，“立即重新连接”只能给已经死亡的线程排队；旧 ViGEm worker 的一次 `target.update()` 异常同样永久停止。XInput 在 100 ms 后中立、3 秒后移除 target，还会让 Forza 运行中面对 player slot 消失和重新出现。Bluetooth `0x36` 约每 10.667 ms 写入 398 字节，弱适配器或 Windows HID 栈长期运行时仍可能先失去输入，再被 3 秒 watchdog 判断整只手柄掉线。
- 决定：物理 HID 保持唯一 reader，但 `_io()` 改为同一 worker 内的 session supervisor，异常后关闭当前 handle 并按 0.25、1、5 秒上限恢复；手动 reconnect 在 worker 已死亡时先重启它。XInput 在 100 ms 输入空档只发送一次中立并保留 target/player slot，ViGEm 瞬时异常按同样有界退避重建 session。
- 后续修正：撤销“Bluetooth HD 已发送且连续 350 ms 无有效输入就永久降级当前连接”的保护。短暂弱信号在手柄靠近主机后可以恢复，不能以一次输入空档把 `0x36` 锁成 compatible rumble 直到重连。真实构建、队列或 HID write 失败仍可触发当前连接 fallback；持续约 3 秒无有效输入仍由物理 HID watchdog 断开并重连。
- 诊断：完整输入校验和 CRC 不放宽；连续拒绝限频记录，恢复后记录边沿，HID open 日志包含 PID。GUI、TUI 和 headless 共用 2 MiB、两个备份的 `data/runtime.log`，用于收集用户所说“玩到后面不认手柄”的跨会话证据。
- 边界：没有把 DualSense Edge 与普通 DualSense 写成完全实机等价，也没有改变 `dist-usb-audio-gate-1` 已接受的 BT → USB 握把生命周期、HID offsets、`0x36` 布局、CRC、扳机或握把算法。真实长时间测试无法执行时必须明确写未执行，不能用自动测试替代。

## 2026-07-22：红线使用共享动态估计器且保留原始 `max_rpm`

- 状态：生产代码、自动测试和独立 R7 候选已完成；真实车辆断油学习与手感验收待完成。
- 背景：现有握把和 R2 扳机键都按 `rpm / max_rpm` 判断，仪表最大刻度明显高于实际断油的车辆可能永远达不到阈值。参考 [TiansuoLi 的 dynamic-redline 分支](https://github.com/TiansuoLi/Forza-Horizon-DualSense-Python/tree/feature/dynamic-redline-rgb-shiftlights) 后确认可通过高油门功率切断事件学习实际红线，但该分支当前实现会覆盖共享 `t["max_rpm"]`、依赖精确 `0 W`，而且换挡备用分支会被前置挡位复位和 debounce 阻断，因此不直接复制。
- 决定：新增 `src/modules/forzahorizon/redline.py`。学习前使用按仪表范围变化并限制在 `80%..98%` 的经验预测；候选必须位于预测红线附近，在高油门、稳定同挡、低离合和非严重打滑条件下出现非正功率，或同时出现相对功率骤降及扭矩骤降/RPM 回落。事件继续保持原挡位 120 ms 才确认，排除自动/手动换挡；三个相近候选用中位数建立学习值，后续样本可平滑修正，候选队列有界。
- 数据边界：`src/modules/loop.py` 只新增 `effective_redline_rpm`、`rev_limiter_active` 和置信度，不覆盖 UDP 原始 `max_rpm`。R2 扳机键、握把红线与转速灯条共享派生红线；发动机底噪仍使用原始仪表范围。第一次真实断油确认即可短暂输出事件并强制灯条闪烁，三次聚类后再改变连续接近红线阈值；估计缺失时灯条回退原始范围。
- 后果：大红区车辆的触觉和灯条不再永久依赖固定仪表比例，换挡、离合和明显空转不会用于训练。Forza 没有公开的 limiter flag，本实现仍属于遥测推断；学习不跨应用重启持久化，真实 FH4/FH5/FH6 多车型结果必须在实机验收后再写成已验证。

## 2026-07-22：Xbox App 手动目录选择抢占后台扫描并接受直接 `Content`

- 状态：生产代码和自动测试已完成；真实 Xbox App FH6 目录仍待用户环境验收。
- 根因：FH6 实用功能页面显示后会立即启动后台语言与图标扫描，旧代码在 scan busy 时直接丢弃随后选中的目录且不提示。另一个失败路径是用户选择 Xbox App 展示的游戏外层目录，而验证器只检查所选目录本身是否直接包含 `ForzaHorizon6.exe` 和资源目录；返回 `None` 后界面仍显示原状态，看起来像按钮没有反应。
- 决定：GUI 的显式目录选择允许抢占同类后台扫描，以递增 serial 使旧 worker 结果失效；无效手动选择显示 toast。通用根验证只额外尝试所选目录的直接 `Content` 子目录，语言与图标工具共用该结果并保存解析后的 payload 根目录。
- 边界：本条当时的“不扫描驱动器或 `XboxGames`”已由同日后续的受限自动发现决定替代。仍不扫描 `WindowsApps`、整盘或任意递归子目录，不绕过访问控制，也不伪造 Xbox App 游戏语言。文件修改仍要求精确 EXE、目标资源、备份和游戏未运行验证。

## 2026-07-21：Xbox App 蓝牙输入采用 input-first 与 latest-only 调度

- 状态：生产代码和自动测试已完成；独立 R7 候选与真实 Xbox App/Bluetooth 手感验收待完成。
- 根因：Steam Input 自己读取 DualSense，不经过本项目的 ViGEm bridge；Xbox App 模式则经过 `DualSense HID I/O thread -> XInputBridge -> ViGEm X360`。Bluetooth HD haptics 每约 `10.667 ms` 产生一个 398 字节 `0x36` pending，旧调度只要看到任意 pending output 就把本轮读取限制为一条。Windows HID 输入因此可能积压，而每条旧报告又在实际读取时获得新时间戳，bridge 会把积压逐条当成实时输入；USB body haptics 走音频 endpoint，所以不出现同一竞争。
- 决定：继续保留唯一物理 HID reader。只在 XInput consumer 启用时，I/O thread 优先把当前输入队列 drain 到最新，只向 consumer 发布最新有效报告；单批达到安全上限时先继续追赶，再写出单槽合并后的输出。没有 consumer 的 Steam 路径保持原有输出优先行为。
- 输出合并：同一轮有 Bluetooth `0x36` 时，其 state block 已带最新 L2/R2 扳机键和灯效；若普通 pending frame 没有 compatible rumble，则省略重复的 `0x31`。显式 compatible rumble 和全零释放不省略，`0x36` 的 398 字节、3 kHz、32 帧、CRC 和左右声道契约不变。
- 验收：自动测试必须证明积压只提交最后有效状态、损坏尾包能回退到前一有效状态、连续 haptics pending 不阻止 drain、rumble release 不被吞掉。真实验收使用 Xbox bridge + Bluetooth + Steam Input 关闭，对照 body haptics 开/关检查操控延迟，并同时确认握把、L2/R2 扳机键、USB 路径和 Steam 模式无回归；在真实 Xbox App 游戏完成前不得宣称已实机修复。

## 2026-07-20：BT → USB 先等待 Windows USB 音频端点，再初始化 PortAudio

- 状态：生产代码和自动测试已完成；独立 Windows one-file 候选与真实 DualSense 验证待完成，不能写成已修复或发布。
- 证据：旧 `0x08 / 0x02` 候选在实机上记录 `Bluetooth control teardown accepted` 和 `transport handover complete: BT -> USB`，随后仍报 `No four-channel DualSense audio endpoint found` 且 USB 握把没有输出；同一时刻新启动的独立 sounddevice 进程可以枚举活动的四声道 DualSense WASAPI endpoint。当前锁定的 sounddevice 模块在 import 尾部立即调用 `_initialize()`，因此 Bluetooth 冷启动阶段的提前 import 会让 PortAudio 在 USB endpoint 出现前冻结设备快照。该现象解释了为什么系统已经显示 USB/充电，而旧进程仍看不到 USB 音频端点。
- 决定：`src/modules/haptics/audio.py` 不再顶层导入 sounddevice，只有 `UsbAudioHaptics.start()` 才延迟加载。启用 body haptics 的 BT → USB 在稳定 USB 候选出现后非阻塞等待 3 秒，期间 Bluetooth 输入、L2/R2 扳机键和 `0x36` 握把触觉继续工作；随后用 `src/modules/haptics/windows_endpoint.py` 只读枚举 Windows MMDevices registry，确认活动的 DualSense USB render endpoint。endpoint 未就绪或探测异常时保留 Bluetooth 并按既有 1/2/5 秒退避，后续重试不重复 settle；关闭 body haptics 时直接放行。
- 边界：readiness probe 不得导入 sounddevice、调用 PortAudio 私有 `_terminate()`/`_initialize()`、打开静音 stream、加入 callback 心跳或新增 lifecycle lock。readiness 通过后继续使用既有候选输入验证、静音和 `0x08 / 0x02` teardown；本决定没有把 teardown 返回成功当成握把修复证据，也没有改变 Enhanced R6 stream 参数和 start/stop 状态语义。
- 验收：固定 Forza 游戏内振动关闭、Steam 模式 Steam Input 开启，验证 USB 冷启动、Bluetooth 冷启动、BT → USB、退出候选后 R6、USB → BT。BT → USB 允许约 3 秒保持 Bluetooth 后再出现约 1 秒交接空档；最终必须显示 USB、恢复 USB 握把、L2/R2 扳机键不反复脉冲，且不能留下跨进程污染。

## 2026-07-20：BT → USB 交接显式结束旧 Bluetooth 触觉会话

- 状态：实机失败，已由上方“先等待 Windows USB 音频端点，再初始化 PortAudio”决定替代。保留本条记录为什么 `0x08 / 0x02` 仍存在于交接尾部，但不得再把它单独描述为待验证修复。
- 证据：恢复 Enhanced R6 USB 生命周期后，USB 与 Bluetooth 冷启动握把都正常，但同一手柄从 Bluetooth 切到 USB 后 USB 握把消失；退出并重启应用、拔插 USB 都不能恢复，只有让手柄完全关机后再启动才能恢复。HID 输入、L2/R2 扳机键与连接状态已经进入 USB，因此结论不是“整只手柄仍走蓝牙”，而是握把执行器最可能仍被固件锁在旧 Bluetooth `0x36` 会话。Sony 未公开确认该内部状态机，此处属于由实机行为支持的工程判断。
- 方案：保持候选 USB handle 先打开并读取有效报告。仅在 BT → USB 边界，由唯一 I/O thread 先发送现有静音 `0x36` 与扳机 release，再通过旧 BT handle 调用 `send_feature_report()` 发送 48 字节 `0x08 / 0x02`。包布局和 `0x53` seed CRC 来自 DS5Dongle 的 `bt_power_off_controller()`；返回正数后才提交 USB。命令异常或返回非正数时关闭候选、保留当前 BT 快照与输出，并使用既有 1/2/5 秒退避。
- 结果：实机中 feature report 返回正数且 HID 已提交 USB，但 USB 握把仍无输出；所以“旧 Bluetooth 触觉会话未结束”不是充分根因，report 被接受也不是 USB audio readiness。继续保留该命令必须服从上方 3 秒 endpoint gate，不能再单独扩展 HID flag、双 transport 输出或 PortAudio 私有 refresh。

## 2026-07-20：R7 USB 握把触觉生命周期完整恢复 Enhanced R6

- 状态：生产代码、自动测试和 Windows one-file 候选已完成；真实 DualSense 游戏内结果待用户验证，不能写成已修复。
- 新的同机 A/B 已排除“只在 handover 后失败”：电脑重启后先运行已发布 R6，USB 握把触觉正常；同一启动会话随后运行规范 R7 候选，USB 冷启动即完全没有握把触觉。R7 仍能打开正确的四声道 DualSense WASAPI endpoint，Core Audio session 为 active，但连续只读采样显示四个 channel peak 全为零。这证明 R7 USB 回归不应继续被归因于 UDP、HID transport 显示或单纯的 endpoint 缺失。
- 决定把 `src/modules/haptics/audio.py`、`src/modules/haptics/lifecycle.py` 和 `src/modules/haptics/manager.py` 的 USB lifecycle 恢复为 Enhanced R6 语义：不做私有 PortAudio snapshot refresh，不做 callback 心跳判活，不增加 lifecycle lock 或显式 backoff；GUI/TUI 在周期 eligibility sync 时启动共享 stream，headless 在同一 transport epoch 启动失败后用既有闩锁避免逐帧重开。测试层只额外保留“transport routing 不调用未经验证 HID audio-mode setter”的协议保护。
- 本决定替代下方同日决定中“保留 PortAudio hotplug refresh、实例级 `RLock`、callback 心跳和统一 1 秒 backoff”的部分，也替代同日全项目审计决定中的相同触觉恢复条款。那些实现曾通过自动测试和静音开流探针，但真实 R6/R7 A/B 证明其不能作为可接受的 R7 USB 生命周期继续保留。
- 本决定不回退 R7 的 controller topology、候选 handle 有效输入预验证、原子 HID handover、USB 优先、电量/transport 快照、switching 脉冲抑制、Bluetooth `0x36` 后端、反馈分页或 DPI/UI 改动。保留这些代码只表示架构仍在，不表示 BT → USB 后的 USB 握把音频已经实机通过。
- 验证边界：新候选必须依次验证 USB 冷启动、退出后 R6 USB、Bluetooth 冷启动、退出后 R6 Bluetooth 和 BT → USB → BT；每段记录 Forza 游戏内振动与 Steam Input。允许 handover 约 1 秒静默，但不能永久失去握把触觉，也不能污染随后运行的 R6。

## 2026-07-20：R7 热插拔、反馈分页、状态框和窗口 resize 按根因修复

- 现场日志证明 UDP、`HapticMixer`、碰撞和红线事件在故障时仍在运行；HID 已从 Bluetooth 成功切到 USB，但同一进程随后报告找不到四声道 DualSense 音频端点。新启动的独立 Python 进程却能枚举该 WASAPI endpoint，因此“只有扳机、没有握把”不是 UDP 回归，而是 PortAudio 在 Bluetooth 启动阶段建立的设备快照没有吸收 USB hotplug。
- 当时的并发回归认为 GUI lifecycle 与 telemetry manager 可能同时对同一个 `UsbAudioHaptics` 启动，因此加入实例级 `RLock`、PortAudio refresh 和 stream health probe。该实现与结论已由上方“完整恢复 Enhanced R6”决定替代；保留本条仅记录曾采用过的推理路径。
- 当时根据 BT → USB 现场为 `OutputStream` 增加 callback 心跳、1 秒超时重建和统一 1 秒 backoff。后续 USB 冷启动 A/B 证明 R7 仍失败，因此这些生产行为已由上方决定撤销；真实硬件结果仍以 `PROJECT_STATE.md` 为准。
- 后续实机证据推翻了“只在 handover 后假启动”的边界：重启电脑后 R6 正常，但运行 R7 后即使退出 R7，随后启动的 R6 在 USB 与 Bluetooth 下也会失去握把触觉，直到再次重启。这证明 R7 写入了跨进程保留的控制器状态；PortAudio、UDP 或进程内 worker 不能单独解释该现象。
- 协议复核确认 R7 新增的 `valid_flag0 0x20` 不是 haptics select，而是 speaker volume 字段有效位；报告从全零缓冲区构造，因此它会明确把 speaker volume 写为零。`valid_flag1 0x20` 也不是通用 USB audio-haptics 接管位。关闭 R7 时只取消有效位不会恢复已经写入的值，R6 也不会覆盖它。该错误来自直接采用 HorizonHaptics 的错误注释而没有核对完整 SetState 布局。
- 决定恢复 Enhanced R6 的普通 HID 输出契约：删除两个错误 `0x20`、DualSense audio-mode setter 和 `HapticManager` 调用；不保留已经实机失败的单次 `0x01` 重置。R7 的候选预验证、原子 handover和 USB 优先继续保留；本条原先同时保留的 PortAudio refresh、callback 健康检查和显式失败退避已经由上方决定撤销。新候选必须从重启后的干净状态验证，并证明退出后再次运行 R6 不受污染，才能标记修复。
- 自动 handover 改为非破坏性预验证：候选 handle 必须先打开并读到有效输入，成功后才静音旧输出并原子替换；失败时当前 BT/USB handle、状态和 pending output 保持不变。稳定失败候选与未知身份读取按 1、2、5 秒退避，候选消失即清除；切换不播放启动 R2 扳机键脉冲。这样保留 USB 优先与自动恢复，同时不再用“先断旧连接、再试新连接”的方式制造往返和脉冲。
- 前端输出类型按用户心智模型完全分离：`Trigger feedback` 与 `Grip haptics` 各自拥有开关、常用调节和实验区域；字段分组集中在 `src/modules/feedback_schema.py`，GUI/Console 只负责渲染，不再各自复制反馈分组。实验性扳机功能仍默认折叠且默认关闭。
- 顶部 Profile/控制器控件不再追求全胶囊外形，改为 28 logical px 高、8 logical px 圆角的小型状态框；所有关键尺寸为 4 的倍数，并缓存相同 presentation，目标是在 100%、125%、150%、175%、200% 下保持整数 device pixel。
- 页面仍然只 `grid()` 一次并用 `tkraise()` 切换；最大化/拖拽时只有可见页的 `FastScroll` 接受尺寸回流，40 ms debounce 只应用最新尺寸，反馈卡片另以 80 ms 合并列数变化且不先 `grid_forget()`。系统更新卡片把 snapshot 转为稳定 presentation，仅在文本、进度、动作或 Release 可见性改变时修改控件。不能为了性能退回销毁/重建页面或周期性无条件重排。
- 自动测试和真实 USB 静音四声道开流只能证明恢复路径可以启动，不能替代 BT 到 USB、USB 到 BT、Forza 手感和各缩放率目测；这些结果必须在 `PROJECT_STATE.md` 单独标注。

## 2026-07-20：全项目审计把外部输入、运行健康和双界面退出纳入统一边界

- 状态：生产代码与自动回归已实现；Windows 最终冻结构建、真实 DualSense、真实 Linux 和混合 DPI 验收分别以 `docs/PROJECT_STATE.md` 的当前记录为准。
- 范围：审计覆盖上游继承代码与 Enhanced R1 到 R7 的配置、启动、遥测、DualSense、扳机、握把触觉、GUI/TUI、FH 工具、XInput、更新器、构建、许可证和测试，不把结论限定为 R7 新增模块。
- 外部数据决定：偏好 JSON、Profile 分享码、UDP、GitHub Release/sidecar 和更新 transaction 都必须在进入运行时前做类型、有限数、结构、长度或路径归属校验。Profile 分享码采用有界解压，名称去除控制字符并限制长度，TUI 动态文本转义 Rich markup。配置写入使用唯一临时文件和原子替换；无法先保护现有有效配置时，恢复出厂和损坏恢复必须失败关闭。
- 启动健康决定：更新健康 ACK 不是“进程或窗口已经创建”。headless 必须完成 controller、可选 XInput 与 UDP listener 初始化；GUI/TUI 必须完成 backend、listener 和 telemetry worker 启动。ACK callback 只能执行一次，失败让新版退出并由 Helper 回滚。
- 退出一致性决定：GUI 与 TUI 的所有正常退出源都经过各自统一 `request_close()`，只在当前 `Default` Profile 的 Profile 字段变化时提供命名保存。更新 Helper 必须延迟到该决定完成后调度；强杀、崩溃和断电仍无法提示。
- 触觉恢复决定：GUI/TUI 的 USB audio lifecycle 和 headless 的 `HapticManager` 都在启动失败后限频自动重试。该策略允许临时设备错误自行恢复，同时禁止逐遥测帧重开 PortAudio。
- 环境和平台决定：主程序不读取当前工作目录中的 dotenv 文件，环境覆盖由 shell、IDE、CI 或 launcher 显式注入。Linux hidraw wrapper 的 `timeout_ms` 接口独立于 PyPI hidapi；Linux 构建使用锁文件环境，Windows 单元测试与脚本语法检查不能写成真实 Linux 验收。

## 2026-07-19：版本化 EXE 更新改为持久化事务和健康提交

- 状态：生产代码、自动测试和审计后冻结 R7 构建已完成；R7 尚未发布。真实已发布 R6 到 R7 的隔离升级使用审计前候选完成，验证了规范文件名、健康 ACK、快捷方式 target/icon/参数/工作目录迁移和旧文件清理；审计后候选未重复启动真实 EXE 的演练，当前由定向自动测试覆盖。
- 背景：R6 旧 Helper 会把新版字节写进旧版本文件名，并留下 `.old`，导致文件名、版本资源、快捷方式和回滚状态不一致。仅靠进程退出后 rename 无法覆盖断电、启动即退、杀毒锁文件、快捷方式部分失败和新旧进程竞争。
- 决定：R7 以后按规范文件名并排安装新版，以原子 transaction journal 记录阶段、绝对路径、版本、哈希、PID、公开启动参数、随机 token 和快捷方式进度。新版必须在 30 秒内写出 token、版本、路径、哈希一致的健康 ACK，并继续存活约 3 秒；之后才迁移快捷方式和删除旧版。正常路径不创建 `.old`，失败则保留并重启旧版。
- PyInstaller 边界：one-file 外层 bootloader 与内层应用可以使用不同 PID。随机 token 是 ACK 身份凭据，Helper 监视自己启动的外层进程存活，不要求 ACK PID 等于 `Popen.pid`。
- R6 兼容：只有当前文件名版本、内置 PE 版本与真实 `.old` 的 PE 版本严格匹配时，才运行一次第二阶段 legacy bootstrap。它恢复规范 R6、安装规范 R7 并走相同健康提交；快捷方式部分失败时保留真实 R6，不保留 `.old`，也不回滚健康 R7。
- 快捷方式与目录收口：健康提交后枚举同目录中所有严格命名且版本更低的规范 EXE，逐个迁移当前用户 Known Folders 与已知 pinned 目录中的精确 target，并保留参数、工作目录和 icon index。成功后静默删除旧规范 EXE及严格同名的 `.exe.old`、`.exe.sha256`，包括更早更新遗留的 R5 `.old`；不执行 `*.exe`/`*.old` 通配清理。无匹配静默成功；某一旧版部分失败时提示一次、记录 journal 并只保留该规范旧版，后续启动继续修复。
- 后果：主程序不得覆盖 `sys.executable`，启动恢复不得按文件存在性盲删。构建必须使用 `src/uv.lock` 中固定 PyInstaller；完成/回滚 journal 的保留期、跨启动 24 小时检查节流和代码签名仍是后续工作。

## 2026-07-19：DualSense 在线状态以有效输入为真值，传输切换归 I/O thread

- 状态：生产代码、自动测试、状态展示和配置迁移已实现；当前会话尚未枚举到真实 DualSense，因此 Enhanced R7 的关机、USB/Bluetooth 双向 handover、电量和触觉恢复仍待硬件验证。
- 背景：旧逻辑把仍持有 HID handle 当成在线，并在检测到 HidHide 或关闭自动重连时永久跳过 input watchdog。结果可能在手柄关机后仍显示已连接，也无法在同一手柄插入 USB 或拔线回 Bluetooth 时更新 transport。
- 决定：`ControllerSnapshot` 是 GUI/TUI 与其他消费者的唯一 native 状态事实。只有完整、report ID 正确且 Bluetooth CRC 有效的输入报告才能建立或刷新连接、电量和 latest input；约 3 秒无有效输入就清除旧状态。HidHide 只做诊断，`persistent` 不再改变 watchdog。
- 并发边界：所有 HID open/read/write/close、立即重连和 handover 继续在单一 I/O thread 串行执行。空闲输入 backlog 可批量丢弃，但 pending trigger/haptics 输出必须优先；XInput 只消费 latest parsed state，不能增加第二个 reader。
- 身份与切换：轻量拓扑约每秒 enumerate，新路径连续两次出现才稳定，未知身份 feature report 只读取一次并缓存。自动切换必须证明同一身份，双传输并存时 USB 优先；目标打开失败尝试恢复旧路径。传输 handover 不受完全掉线自动重连开关限制；失败目标 cooldown 与 switching 脉冲规则由 2026-07-20 后续决定补充。
- 配置：新安装默认开启 `enable_reconnect`；旧偏好通过 `r7_enable_reconnect_default` marker 只强制开启一次，之后尊重用户关闭，不改任何驾驶或命名 Profile 字段。“立即重新连接”是真实 I/O 命令，“重新扫描”仍只刷新设备列表。
- 电量：只显示硬件报告的 10% 档和充电状态，不伪造个位数。仅使用电池且为 10% 时电量文本变红，连接点保持绿色；DSX 不额外打开物理 HID，也不伪造电量。

## 2026-07-19：Windows GUI 以 Per-Monitor v2 为目标并公开实际 DPI 状态

- 状态：manifest、runtime hook、源码 probe、自动测试、最终 PE manifest 提取和系统页诊断已验证；不同缩放显示器间移动和运行中缩放的真实视觉验收待完成。
- 背景：旧代码在 GUI 构造阶段调用 `SetProcessDpiAwareness(2)`，既不是明确的 Per-Monitor v2，也可能因调用过晚而由 Windows 位图拉伸，造成部分用户界面模糊。文档此前把目标声明误写成已经成立。
- 决定：主 EXE 与 Update Helper 都嵌入 `PerMonitorV2, PerMonitor` manifest 和旧系统 fallback；PyInstaller runtime hook 与 `src/main.py` 在任何 Tk/CustomTkinter 窗口前执行 bootstrap。manifest 已确定后 API 返回 access denied 不是失败，必须查询实际 thread/window awareness 和 DPI。
- 展示：系统页和日志显示实际 awareness 与缩放率，不是 PMv2 时提示用户检查 Windows 兼容性高 DPI 覆盖。程序不改注册表、不引入第三个缩放滑块，也不以 bitmap stretch 或迟到的 awareness 调用掩盖问题。
- CustomTkinter 边界：CTk 继续管理自身 widget/window scaling，项目不重复乘缩放系数。混合显示器、动态 scale、睡眠/唤醒、扩展坞和远程桌面属于发布前人工验证项，在完成前不能写成已实机验证。

## 2026-07-19：FH6 三行语言状态落地，并把手动文件工具扩展到 Xbox App

- 状态：GUI/TUI 生产代码、共用展示层、六个非英语 catalog、自动测试和包含本决定的 R6 one-file 发布已完成；真实 Xbox App 游戏验证仍待完成。
- 背景：独立 FH6 页面仍显示原始 `Steam 语言：english`，遗漏了用户已确认的“当前游戏语言 / 实际显示语言 / 语音语言”三行界面。语言包交换本质只依赖经过内容识别的 `CHS.zip`、`EN.zip` 与同目录事务，不要求文件一定来自 Steam；Xbox App 版可以复用同一安全操作，但当前没有可靠的自动安装目录或游戏语言元数据来源。
- 决定：GUI/TUI 必须共同消费 `summarize_fh6_languages()` 与 `language_summary_view()`，常驻显示三行本地化状态。Steam 继续自动发现并读取 manifest；Xbox App 当时只验证用户手动选择并保存的 `fh6_xbox_install_path`，该路径发现范围现已由 2026-07-22 的受限自动发现决定扩展。Xbox App 或 Steam 手动路径无法证明当前游戏与语音语言时显示未知，启用前要求额外确认，不得为了显示“英语 / 中文 / 英语”而伪造 token。
- 安全边界：两种平台继续要求 Windows、精确 FH6 根目录、可识别的中英文 ZIP、游戏未运行、用户显式确认、三步同目录 rename 和失败回滚。平台扩展不允许自动交换、扫描受保护 Xbox package、静默提权或弱化中断恢复。
- 替代关系：本决定完成并替代下方“先建立 FH6 有效语言摘要，三行前端统一延后”；同时只替代 2026-07-17 决定中的 Steam-only 平台范围，原有事务与确认边界继续有效。

## 2026-07-19：GUI 页面常驻、差异渲染并拆出 FH6 实用功能

- 状态：GUI/TUI 生产代码、自动测试与包含三行/Xbox 语言补丁的 R6 one-file 发布已完成；混合 DPI 和更多系统环境的视觉验收仍待完成。
- 背景：CustomTkinter 原本在每次左侧导航时对完整页面执行 `pack_forget()` 和重新 `pack()`，会触发长页面重复布局；总览每秒无条件重配启动按钮、selector 和 XInput action，并每五秒切换 Steam 安装扫描状态，造成所有页面切换卡顿和快速入口抖动。FH6 语言与图标工具又长期在系统页运行两个五秒文件扫描。
- 导航决定：所有 GUI tab frame 创建后只 `grid()` 到同一内容单元格一次，切换只允许 `tkraise()`，并通过可选 `on_show()`/`on_hide()` 管理页面私有任务。失败时恢复上一页，不重建 Settings 或控件。根 `WheelRouter` 继续依赖当前最上层页面的指针命中结果。
- 探测决定：总览只扫描当前选择的 Steam 游戏；找到有效安装后停止，未找到时每 30 秒静默重试，path hint 变化或显式启动验证失效才重新发现。Xbox AUMID 仍只在点击启动时查找。按钮、游戏/平台 selector 和 XInput action 只在 presentation tuple 变化时更新，精确进程检测可以保持轻量轮询。
- 页面决定：FH6“中文文字 + 英文语音”和 DualSense 按键图标迁到独立 `FH6 utilities` 页面，导航位于系统与更新之后、语言之前；GUI/TUI `SystemTab` 不再持有其卡片、timer、worker 或隐藏入口。工具页只在首次显示、路径/平台变化、显式操作后或可见期间 30 秒未找到重试时扫描；找到后只保留进程状态检查。首次默认平台和非法平台回退继续为 Steam。
- 后果：以后增加页面不得恢复每次导航重新布局，也不得用高频文件扫描驱动按钮动画。三行语言摘要已由同日后续决定接入，本决定继续约束页面边界、探测节奏和界面稳定性。

## 2026-07-19：外部组件合并必须先通过 Windows EXE 体积预算

- 状态：长期发布门槛已确认并写入老三样；用户已在获知预计成品约 `51-52 MiB` 后确认继续内嵌 A 方案。Xbox App XInput bridge、固定 ViGEm 资产和 FH6 图标 MOD 已进入生产代码与 Windows spec，最终 R6 EXE 已完成实测。
- 背景：把驱动安装器、运行库、Mod 或其他二进制资产直接塞进 one-file EXE，能够换取离线和单文件体验，但也可能让每次下载与自动更新持续膨胀。源文件数量和源码目录大小无法反映 PyInstaller 最终产物。
- 决定：每项类似集成在实现前都以最新稳定 GitHub Release 的 Windows EXE 为基线，记录候选资产准确版本与原始字节数，并报告预计成品 MiB、绝对增量和百分比；实现后用真实构建重新测量。预计或实测增量超过 `5 MiB` 或 `10%` 任一门槛时，必须在合入或发布前取得用户明确确认，并比较内嵌、按需下载、可选 sidecar 和裁剪方案。
- 资产与实测：线上 R5 Windows EXE 为 `47,218,192` 字节（`45.03 MiB`）。官方 ViGEmBus `1.22.0` 安装器为 `6,278,576` 字节，SHA-256 为 `89220A7865076B342892F98865F3499FB7C4CFD673159E89D352C360FD014C6A`；固定 x64 `ViGEmClient.dll` 为 `130,048` 字节，SHA-256 为 `2BF0CB1D809039573C922737D298A1653D4DBC61408060FF45A9BCFDE82E97D2`；内置 MOD 为 `70,188` 字节，SHA-256 为 `9677E50BF04276A9606956819D7760588EA7B986CFAFEBC70396F35630C53A61`。包含三行语言状态与 Xbox App 手动语言目录补丁的最终本地 R6 EXE 为 `51,814,190` 字节（`49.414 MiB`），增加 `4,595,998` 字节（`4.383 MiB`，`9.73%`），低于 `52 MiB` 停止线，也没有超过长期规则的 `5 MiB` 或 `10%` 实测门槛。
- 离线边界：若采用已选择的内嵌 A 方案，缺少兼容 ViGEmBus 时才从 EXE 解出官方安装器，经哈希与签名校验并由用户确认后触发 UAC；安装过程不依赖下载安装包。官方 `1.22.0` 已移除 updater。Windows 仍可能自行联网检查证书吊销状态，但这不是安装资源的下载依赖。检测到兼容驱动时不解压、不安装，也不为追求版本号强制升级。
- 后果：A 方案的最终增量已经量化且未越线，可以继续 R6 发布验收。后续任何类似合并都重复同一流程，不能把本次确认泛化成无限制捆绑许可。

## 2026-07-19：Xbox App 使用内置 Xbox 360 XInput bridge，并提供显式启动入口

- 状态：基础 bridge 设计仍有效；其中“3 秒移除 target”已由 2026-07-22 的分层自恢复决定替代为“100 ms 中立后保留 player slot”。真实 Xbox App 版 Forza、clean-machine driver 安装和 USB/Bluetooth 游戏内回归仍待验收。
- 背景：Xbox App 版 Forza 不会像 Steam Input 那样直接把 DualSense 映射为 XInput。用户要求程序自身完成基础输入桥，并要求 Steam 模式不产生双输入。ViGEmBus 只能稳定提供 Xbox 360 target，不能生成真正的 Xbox One target。
- 决定：Windows x64 增加 `preferred_forza_platform`。Steam 模式完全停止 bridge；Xbox App 模式由现有 DualSense I/O thread 作为唯一 HID reader，发布 latest input 给独立 ViGEm worker，映射为虚拟 Xbox 360 Controller。100 ms 无输入先中立化，3 s 移除 target；停止或重连不得回放旧输入。当前不注册 rumble callback、不接管游戏原生振动、不安装或配置 HidHide，也不复制 DS4Windows GPL 代码。
- 驱动：固定内置 ViGEmBus `1.22.0` 安装器和 x64 `ViGEmClient.dll`。兼容性以实际 client connect/target add 为准，不按版本号强制升级；缺少 driver 时只在用户确认、SHA-256 与 cache-only Authenticode 均通过后触发 UAC。ViGEm 已归档/EOL，软件不提供 driver 自动更新。
- 启动：总览 Xbox App 入口先用 `Get-StartApps` 动态匹配当前代完整游戏名，只接受 `PackageFamilyName!Application` 形式并通过 `shell:AppsFolder` 激活；未发现已安装身份时打开固定 `msxbox://game/?productId=<id>` 产品页。启动始终由用户点击，不直启游戏 EXE，不把打开产品页写成游戏已启动，也不管理 Xbox 安装和许可。
- 后果：Steam 与 Xbox App 使用同一个游戏选择和进程状态，但输入所有权严格分离。Steam 版、Steam Input 关闭的实机控制只能证明 XInput 兼容链路，不能替代真实 Xbox App 游戏验收；Release 必须明确这一限制。

## 2026-07-19：FH6 DualSense 按键图标以可还原事务内置

- 状态：Windows 生产代码、GUI/TUI 入口、打包资产、哈希、临时目录自动测试和冻结 R6 EXE 已实现；真实 Steam/Xbox 游戏目录写入和游戏内图标显示仍未执行。
- 背景：用户已取得 MOD 集成许可，并要求软件内安装，避免用户手工寻找普通与 HiRes 两个目标。游戏更新或验证文件会恢复原件，覆盖前必须保留可靠还原路径。
- 决定：EXE 只携带一份 `DualSenseIcons 2.1.1` 的 `ControllerIcons.zip`，安装前校验固定 SHA-256，把两份不同原件分别备份到按已解析游戏根路径隔离的应用数据目录，再用同一 MOD 写入两个目标。安装、还原、部分状态修复都必须由用户显式触发；FH6 运行中拒绝修改，失效或不完整备份时拒绝静默覆盖。
- 平台：Steam 根目录通过 manifest 自动发现；Xbox App 根目录现通过受限 flat-file 发现或手动 fallback 获得，并保存在 global 字段。该图标工具仍仅支持 Windows/FH6，不能泛化为 FH4/FH5 或 Linux 支持。
- 归属：GUI/TUI 的独立 `FH6 utilities` 页面、关于页、三语 README、双语 Release 和 `docs/THIRD_PARTY_NOTICES.md` 必须以可点击 Nexus 链接鸣谢 `@hotline1337`。许可证说明只记录用户陈述的集成许可，不推断作者授予了更广泛的再许可。
- 后果：后续修改目标路径、资源版本或作者信息时必须同步哈希契约、事务测试、打包 spec、关于页和发布归属；不能用简单覆盖复制替代备份协议。

## 2026-07-19：先建立 FH6 有效语言摘要，三行前端统一延后（已被同日后续决定替代）

- 状态：这是阶段性历史决定。底层摘要当时先实现；GUI/TUI 三行文案现已由同日后续决定接入。五秒文件扫描抖动已由独立 `FH6 utilities` 页面、可见生命周期和 30 秒静默重试替代。
- 背景：现有界面显示原始 `Steam 语言：english`，容易被误解为 Steam 客户端界面语言；实际 token 来自 FH6 的 Steam manifest。当前 `SWAPPED` 状态意味着 FH6 游戏内容语言为 English、实际文字为中文、语音仍为英文。页面还会因五秒扫描暂时改标题并重新 pack 按钮而抖动。用户计划继续补充 R6 前端需求，因此不应先做半套界面。
- 决定：本轮只在 `fh6_language.py` 提供 `FH6LanguageSummary` 和纯函数 `summarize_fh6_languages()`，统一输出规范化游戏语言、实际文字语言和语音语言。它不访问或修改文件，不依赖界面或翻译。非英语、缺失、损坏和恢复状态不猜测实际文字语言。
- 后果：三行前端已经按本条约束直接消费共用摘要并本地化，GUI/TUI 不得重新分叉推导。

## 2026-07-18：通用 Steam 启动入口同时支持 FH4、FH5、FH6

- 状态：Steam 三游戏部分已实现；“仅支持 Steam”的平台范围已由 2026-07-19 Xbox App 决定替代。
- 背景：Enhanced R5 的总览按钮只启动 FH6。用户要求同一 Windows 应用支持 FH4、FH5、FH6，并要求今后的启动、更新和相关文案不能只考虑最新一代。Xbox App/MS Store 本轮没有明确可靠的统一发现契约。
- 决定：本段历史范围仅支持 Windows Steam 版三代游戏。总览使用分体按钮，左侧启动当前选择，右侧菜单只选择；首次默认 FH6，后续记住最后选择。未安装的游戏仍可选择，但主按钮禁用并显示对应“未找到”，不自动回退。三代 Steam 安装发现、精确进程检测和 URI 统一进入 `game_launch.py`；FH6 语言交换继续隔离在 `fh6_language.py`。当前 Xbox App 行为以上述 2026-07-19 决定为准。
- 并发边界：扫描结果携带游戏键和请求序号，GUI 主线程拒绝旧选择或旧序号覆盖当前状态。启动只由用户点击触发，不直启 EXE、不提权、不修改语言包。
- 文档后果：今后修改游戏启动、进程观察、安装发现、Release/更新说明、README 或对应界面文案时，默认同时检查 FH4、FH5、FH6。FH6“中文文字 + 英文语音”和 Nexus Mods 按键图标提醒仍明确属于 FH6 专属。

## 2026-07-18：更新导航提示使用透明白点

- 状态：生产代码与自动契约测试已实现；真实 GUI 已确认选中态为无黑底白点，未选中和 hover 状态待逐项目视。
- 背景：提示点原本挂在导航按钮外层容器上；尝试改成按钮的透明子 Label 后，真实 GUI 仍证明 CustomTkinter 会把该 Label 的背景解析成黑色矩形。
- 决定：删除独立 Label，改由 `widgets.NavButton` 在按钮自身 canvas 上直接绘制 5 px 白色圆点。圆点没有独立控件背景，点击仍由原导航按钮处理。
- 后果：选中、未选中和 hover 三种状态都必须进行可见检查；不得用带底色的位图或独立外层标签重新实现。

## 2026-07-18：GitHub 上的用户 README 提交必须参与本地语义合并

- 状态：长期协作规则已确认并写入老三样。
- 背景：用户可能直接在 GitHub 编辑并提交 README；本地分支随后也可能包含功能或发布相关的 README 更新。若只按本地旧文件覆盖，会静默丢失用户刚在远端完成的文案修改。
- 决定：提交或推送本地更新前先获取远端。发现远端 README 已变化时，逐段审阅差异，理解用户修改的内容和意图，在保留这些改动的基础上合入本地所需更新。禁止整文件覆盖、忽略远端提交或机械采用本地冲突侧。
- 后果：README 冲突必须作为内容合并处理；自动合并成功也不免除对最终差异的复核。只有用户明确要求撤销某项远端修改时，才可有意删除该内容。

## 2026-07-17：Enhanced R5 总览使用真实运行时状态，不再保留静态占位

- 状态：生产代码与定向自动测试已实现；源码 GUI 视觉冒烟和冻结 EXE 验收待执行。
- 背景：Enhanced R4 总览的四张状态卡虽然有 `refresh()`，但只在设置刷新链路触发，GUI 每秒 tick 没有调用，因此控制器、遥测、Profile 和更新状态经常停留在初始化占位值。UDP listener 也没有可供 UI 安全读取的数据包计数、来源和最后接收时间。
- 决定：`UDPListener` 维护只统计 324 字节有效包的线程安全不可变快照；总览用纯 presentation 层组合 backend、遥测、Profile 和更新快照。页面创建后立即刷新，运行期间每秒刷新。DSX 必须明确说明 fire-and-forget UDP 无 ACK，不能把 socket 打开写成手柄已确认连接。
- 错误边界：启动错误保存为运行时事实，不能被下一次普通状态 tick 覆盖。H1 只显示“后端错误”“UDP 绑定失败”“更新失败”等短文案，具体异常放在提示和日志。
- 后果：更新卡覆盖自动检查等待、检查关闭、检查中、最新、可用、下载百分比、校验、待安装、安装和失败；Profile 读取失败有显式状态，不再回退到 `-`。

## 2026-07-17：FH6 中文文字 + 英文语音只允许用户确认后的同目录改名

- 状态：事务与确认边界继续有效；Steam-only 平台范围已被 2026-07-19 的 Xbox App 手动目录决定替代。真实 Xbox App 游戏文件操作尚未执行。
- 背景：FH6 的 `media/Stripped/StringTables/CHS.zip` 保存中文文字，`EN.zip` 保存英文内容；在 Steam 游戏语言为 English 时交换两者名称可得到中文文字与英文语音。用户安装盘符和 Steam 库位置不固定，不能使用某台机器的 `C:\Program Files (x86)` 路径。
- 决定：本段原始范围只支持 Windows Steam FH6；当前范围以上方 2026-07-19 决定为准。Steam 自动流程仍通过 registry、`libraryfolders.vdf`、App ID `2483190` manifest、卸载信息或精确游戏进程路径发现安装；Xbox App 仅手动选目录。所有启动和刷新扫描只读，功能必须由按钮触发并确认，绝不自动交换。
- 安全门禁：操作前按 ZIP 内 `.str` 内容识别中文/英文，检查 Steam English、FH6 已关闭、目标目录和每一步源/目标存在性。启用和还原使用 `CHS -> temp -> EN` 的三步同目录 rename，并在进程内失败时逆序回滚；不复制文件、不创建永久备份、不静默提权。
- 崩溃恢复：temp 残留只报告“交换中断”。只有恰好两份可识别中英文文件时才显示修复按钮，仍需用户确认；不自动修复、覆盖或删除。Steam 更新或验证文件恢复原包后，重新检测应自然显示原始状态，不自动重新启用。
- 界面边界：GUI 用 modal 确认并把磁盘操作放到 worker thread；TUI 用二次按键确认。Steam manifest 明确为其他语言时按钮禁用，未知时允许额外确认；非 Windows 运行时只显示不可用。

## 2026-07-17：总览只通过 Steam 显式启动已验证的 FH6

- 状态：Enhanced R5 的历史实现；显式启动的安全边界继续有效，但单一 FH6 范围已由 2026-07-18 的三游戏决定替代。
- 背景：R5 已经能发现非系统盘和多 Steam library 中的 FH6，继续要求用户离开总览去 Steam 启动没有必要；但直启 `ForzaHorizon6.exe` 会绕过 Steam 的启动上下文，也会把“发现安装”和“自动启动”混为一谈。
- 决定：总览快捷入口增加跨两列的主按钮。只有 Windows Steam 安装已经验证且精确游戏进程未运行时才可点击；运行中显示“FH6 运行中”并禁用。点击后在 worker thread 中重新验证安装与进程，再调用 `steam://run/2483190` 交给 Steam，GUI 主线程只负责状态渲染和提示。
- 边界：启动必须保持显式按钮动作，不在应用启动、页面刷新、安装发现或语言扫描时自动执行；不直启游戏 EXE、不静默提权，也不借启动按钮交换、还原或修复语言包。请求发出后用二十秒临时状态等待进程出现，超时后允许用户重试，不把 URI 已提交误写成游戏已成功进入主菜单。

## 2026-07-17：所有产品表面统一使用水墨风 DualSense 赛车图标

- 状态：PNG、七尺寸 ICO、源码窗口/托盘引用、Windows 主 EXE、更新 Helper、自动测试和最终 PE 提取校验均已完成。
- 背景：发布前用户提供并最终选定新的正方形水墨风 DualSense 赛车图。窗口、托盘和冻结程序若各自保留不同资产，会出现标题栏已更新但 Explorer、任务栏或 Helper 仍显示旧图标的漂移。
- 决定：将最终图片缩放为 1024×1024 RGB `src/data/icon.png`，并从同一像素源生成含 16、24、32、48、64、128、256 七档的 `src/data/icon.ico`。所有运行面与打包面只引用这两个文件，测试固定 ICO 哈希与尺寸集合。
- 验证：最终 R5 EXE 从 PE 提取出的 32×32 associated icon 与新 ICO 的 32×32 帧逐像素一致；后续替换图标必须重新生成两份资产、更新哈希契约并重复 PE 校验。

## 2026-07-17：先诊断 R3/R4 油门扳机手感差异，不用 G 力层补偿未知回归

- 状态：代码审计已完成，用户报告的实机差异仍待受控复现；未修改业务代码或默认参数。
- 现象：用户报告 Enhanced R4 关闭 G 力阻力时，R2 扳机键油门手感与 Enhanced R3 明显不同；开启 G 力阻力后才出现接近 Enhanced R3 的感觉。
- 已确认事实：Enhanced R3 与 Enhanced R4 都保留 `enable_throttle_resistance=True`、`throttle_baseline_force=0`、`throttle_max_force=1`、`throttle_curve=5.0`。R4 的 `throttle_ramp()` 先计算原基础 ramp，再按开关加上 boost 与 G 力，`src/modules/dualsense/adaptive_trigger.py` 在两个 tag 之间没有变化。实验层关闭时，已确认的代码差异只有油门值恰为 `0` 时由 `rigid(0)` 改为 `off()`；这不足以解释整体手感变化。
- 强度解释：G 力最大附加 force 为 `28`，而基础 ramp 最大只有 `1`。使用默认权重和 `1.5G` 满量程时，稳定 `1G` 纵向加速度约增加 `19` force，因此开启后会主导背景阻力；手感相似不能证明它恢复了被删除的旧实现。
- 决定：G 力阻力继续属于默认关闭的实验功能，不以默认开启或盲目调高基础阻力来掩盖差异。下一次开发先在相同车辆、路段、Profile、连接方式下对照 Enhanced R3/Enhanced R4，并记录 Forza 游戏内振动关闭、Steam Input 开启以及每帧最终 R2 扳机键效果来源、mode 和 force。
- 局限：当前 G 力算法没有油门门控并丢弃加速度方向，刹车、过弯、碰撞和换挡瞬态都可能提高 R2 扳机键阻力；`70 ms` attack 与 `180 ms` release 只延迟触觉建立和释放，不增加游戏输入延迟。
- 后续判定：若两版最终 trigger frame 不同，先定位 priority、状态或配置来源；若 frame 相同但实机感觉不同，再检查 EXE 构建、USB/Bluetooth 输出调度和测试条件。未经该证据不得把问题归因于 G 力实现删除旧路径。

## 2026-07-17：Release 的 SHA-256 sidecar 必须跨平台生成并在上传前复核

- 状态：生产脚本、契约测试和 GitHub Actions 硬校验已实现；修复后的 Enhanced R4 Release 已发布并重新下载验证。
- 背景：首次 R4 CI 在 `windows-latest` 中调用 `Get-FileHash` 失败，但旧 BAT 继续写出了只含文件名的 30-byte sidecar，导致工作流表面成功而内置更新器必然拒绝资产。
- 决定：`packaging/windows/write_sha256.py` 使用 Python 标准库流式计算哈希，以固定 ASCII 格式写入 `<64 hex>  <filename>\n`。`build_exe.bat` 在生成失败时返回非零；Release workflow 在上传前以 `--check` 重新计算并严格比较 sidecar，失败即阻止 Release。
- 后果：Windows 发布不得重新依赖 `Get-FileHash`、`certutil` 输出文本或其他随 runner/语言环境变化的系统命令。每次发布验收必须从 GitHub Release 重新下载 EXE 与 sidecar，独立比较哈希；本地构建成功不能替代线上资产验证。

## 2026-07-17：GitHub 仓库脱离 fork network，许可归属保持不变

- 状态：GitHub API 已确认 `piereacy/FH-DualSense-Enhanced` 为 `isFork=false`、`parent=null`；R1-R4 Release、Git 历史和既有 Star 保留。
- 决定：项目作为独立仓库继续发布，不重写 Git 历史，也不移除原项目归属。`LICENSE`、独立“关于与许可证”页面和第三方声明继续保留作者署名、原项目链接、Sponsor 链接及 HorizonHaptics 等参考来源。
- 后果：后续自动更新、README、脚本和 Release 只指向 `piereacy/FH-DualSense-Enhanced`；独立仓库身份不改变许可证义务，也不能把上游或参考项目的工作声称为本项目原创。

## 2026-07-17：许可证信息独立成页，界面代号退回内部设计记录

- 状态：GUI/TUI 生产代码、完整自动验证与 Enhanced R4 发布均已完成。
- 背景：“关于与许可证”此前附着在“握把触觉”页面底部，使许可证与触觉调校形成错误的信息层级；总览页另有一个没有状态、设置或动作的 R4 工作台。用户同时要求正式产品不再显示内部界面代号。
- 决定：GUI 左侧导航和 TUI 页签均在“日志”之后新增独立“关于与许可证”页面，继续显示 `LICENSE` 要求的原作者署名、原项目和 Sponsor 链接；触觉设置页移除该卡片，总览页删除无功能工作台。窗口标题、翻译、Windows `FileDescription`、README、Release 和普通技术文档只使用 `FH-DualSense-Enhanced`。
- 设计来源：现有青绿色主题继续保留，其内部设计来源可在老三样中称为 Miku Console；这只是设计理念记录，不是产品名、构建变体或用户可见字符串。Git 历史不重写。
- 发布：从本决定起，每个 GitHub Release body 必须提供信息对等的完整中文和英文说明。

## 2026-07-17：README 必须明确列出相对上游 1.6.2 的累计增强

- 状态：比较口径、老三样约束、三语 README 功能清单与 Enhanced R4 发布均已完成。
- 背景：现有 README 虽然说明项目基于 `Forza-Horizon-DualSense-Python 1.6.2`，但功能亮点没有明确区分上游原有能力、Enhanced 各版本的累计增强和当前 Release 的本版新增，用户无法快速判断增强项目的实际价值。
- 决定：三语 README 必须以四到六个用户可感知类别，说明当前 Enhanced 版本相比上游 `1.6.2` 的累计核心增强。Release body 则继续说明当前版本相比上一稳定 Enhanced 版本的增量。
- 证据边界：累计增强只能来自生产代码、自动测试或已有真实硬件记录；不能写入仅设计、推测或尚未实现的能力，也不展开内部字段、滤波参数、HID 字节和逐项实验开关。
- 后果：讨论 Enhanced R4 时必须分别形成“Enhanced R4 相比上游 1.6.2”和“Enhanced R4 相比 Enhanced R3”两份清单。README 使用前者，R4 Release body 使用后者；三种语言同步同一组事实。

## 2026-07-17：R4 新增扳机反馈统一收进实验性功能

- 状态：生产代码、翻译、GUI/TUI 分组契约、自动测试与 Enhanced R4 发布均已完成。
- 背景：涡轮增压阻力、G 力阻力、L2/R2 碰撞扳机冲击和 L2/R2 空闲路面纹理均为 Enhanced R4 新增且默认关闭的反馈。原界面把六个开关放在普通“驾驶反馈”卡片、把参数分散在普通设置与实验性区域，容易让用户误认为这些效果已经成熟并自行启用。
- 决定：从 GUI/TUI 普通 L2/R2 控制页移除六个开关；开关与全部基础、进阶参数按动态阻力、碰撞反馈和路面反馈三组统一放入默认折叠的“实验性功能”，继续显示“不建议自行调节”的提示。
- 兼容：字段名、Profile/share-code 格式、即时保存、效果优先级和运行算法不变；六个开关继续默认 `False`，已有命名 Profile 的显式值不被覆盖。抓地力、GT7 风格 ABS 墙、基础刹车/油门阻力、红线和握把换挡等成熟功能继续留在普通页面。灯效不属于扳机反馈，保留独立页面。
- 后果：后续若要把某个实验性反馈提升为普通功能，必须先完成真实 USB/Bluetooth 手感验证并形成新的产品决定，不能只移动一个 UI 开关。

## 2026-07-17：README 不宣传界面设计代号，并要求关闭游戏内振动（命名边界已被独立关于页决定扩展）

- 状态：三语 README、文档契约和 GitHub `main` 已更新；应用界面和 R4 功能代码未修改。
- 命名：本决定当时只禁止 README 宣传内部界面代号；现由上方新决定扩展到全部用户界面、构建资产和普通文档。青绿色主题、布局和功能继续保留。
- 必需设置：Steam Input 必须保持开启，Forza 游戏设置中的“振动”必须关闭。游戏原生 rumble 会争用、掩盖或干扰握把触觉，因此 README 不再把关闭游戏内振动写成仅供比较时使用的可选建议。
- 呈现：三种 README 在启动顺序后使用 `IMPORTANT` 警告，不增加启动弹窗，也不在本轮修改 GUI/TUI 文案。
- 后果：后续讨论 Enhanced R4 功能时，应分别处理“保留视觉设计”和“是否调整程序内命名”，不能根据 README 的中性措辞推断应删除现有界面。

## 2026-07-17：README 默认英文、按语言拆分并保持用户导向

- 状态：三份用户指南、文档契约和 GitHub 默认分支均已更新。
- 背景：根 README 曾把简体中文、English、日本語完整拼接在同一页面，达到 641 行，并混入后台开关、Default 保存、滚轮、更新提示、触觉算法、Bluetooth 报文和开发构建等细节，普通用户难以找到安装与必要配置。
- 决定：根 `README.md` 只提供英文；`docs/ReadmeZH.md` 和 `docs/ReadmeJA.md` 分别提供简体中文与日语；删除重复的 `docs/ReadmeEN.md`。三个页面顶部互相链接，正文保持相同主题顺序。
- 内容边界：只保留项目用途、最多六条核心能力、下载、Steam Input、Data Out、启动顺序、USB/Bluetooth 简述、五项常见故障、按键图标 Mod、来源与许可证。小设置、版本历史、实现算法、报文字节、开发和构建命令不进入用户 README。
- 发布边界：README 使用 `FH-DualSense-Enhanced-R<n>.exe` 和 latest Release 链接，不硬编码尚未发布的具体版本。README 提交可独立同步到 `main`，不得借此合并未发布的业务代码。
- 后果：新增功能不自动获得 README 条目，只有改变首次安装、必需配置、核心产品能力或高频排障时才更新三种语言。实现细节应写入 `docs/ARCHITECTURE.md`、`docs/DECISIONS.md` 或 Release body。

## 2026-07-17：Enhanced R4 收敛为单一 Console，并建立持久化 Default 交互

- 状态：生产代码、自动测试、125% 缩放下的源码 GUI 视觉/滚轮冒烟、单一 EXE 构建和冻结程序冒烟均已完成；100% 与 150% 缩放和用户交互验收待执行。
- 背景：用户审阅三种 R4 前端后选择内部称为 Miku Console 的青绿色方案，并要求彻底删除 Stage、Studio。现有驾驶反馈页在 DPI 缩放窗口中压缩卡片且不能可靠使用滚轮；`Default` 又在每次启动时被代码默认值覆盖，无法承担无命名工作配置。
- 单一产品：删除 `src/modules/gui/variants.py`、`FHDS_UI_VARIANT`、`FHDS_BUILD_VARIANT` 和 `data/ui_variant.txt`。Windows 只构建 `FH-DualSense-Enhanced-R<n>.exe`，更新器只接受该规范资产及同名 `.sha256`。历史三壳层决定保留在下文，但已被本决定取代。
- 持久化：`Default` 与命名 Profile 一样即时保存并跨重启保留。代码内 `Settings()` 继续定义不可变的出厂起点，但发布新默认值不再覆盖用户已经保存的 `Default`。第一次有效配置自动匹配系统显示语言，用户后续选择不被自动检测覆盖。
- 退出：窗口、托盘、游戏关闭、遥测超时和更新重启使用同一退出入口。只有当前为 `Default` 且本会话修改过 Profile 字段时，才提示“保存为命名配置并退出 / 直接退出 / 取消”；建议名从 `profile1` 起选择首个空号。该提示不是落盘保证，强制结束或崩溃无法显示。
- 恢复：三个 GUI 入口调用同一确认框。恢复操作先写 `.bak`，保留命名 Profile，重建 `Default` 与 globals，重新检测语言并切回 `Default`；写入失败时不修改内存设置。
- 布局：保留 Per-Monitor v2 DPI，不通过缩小字体掩盖裁切。长页面注册到根窗口 `WheelRouter`，滚轮优先滚动指针下的内层容器，到边界后转交外层；驾驶反馈卡片保持自然高度并在窄宽度切成单列。
- 更新提示：新 Release 存在且处于可用、下载、校验、待安装或带 Release 的错误状态时，“系统与更新”旁持续显示白点，进入页面不清除。
- 后果：配置文件的 `Default` 也成为用户数据，改变代码默认值时必须通过显式“还原默认设置”才能应用到已有用户。更新安装必须在退出提示完成后调度，Helper 调度失败不得退出主程序。

## 2026-07-16：Enhanced R4 提供三种构建时 GUI 壳层，不分叉业务功能（已被单一 Console 取代）

- 状态：历史实现曾完成并构建；2026-07-17 用户选择 Console 后，生产代码、打包和更新资产契约已删除 Stage、Studio。
- 背景：原界面的分类和层级不够清晰，用户要求至少三种初音未来青绿色前端供审阅，同时明确不能影响功能实现。
- 决定：Miku Console、Miku Stage、Miku Studio 只在 `src/modules/gui/variants.py` 中定义导航位置、宽度和紧凑模式，颜色统一来自 `src/modules/gui/theme.py`。三者必须实例化同一组 Tab、同一个 `Settings`、同一后端线程和配置格式，禁止复制业务页面。
- 构建：`FHDS_BUILD_VARIANT` 为每个 EXE 内置 `data/ui_variant.txt`；文件名分别为 `FH-DualSense-Enhanced-R4-Miku-Console.exe`、`...-Miku-Stage.exe` 和 `...-Miku-Studio.exe`。源码环境变量 `FHDS_UI_VARIANT` 只用于预览。
- 后果：本段只保留选择过程的历史依据，不再约束当前代码。当前约束以上述单一 Console 决定为准。

## 2026-07-16：Windows 独立 EXE 使用内置更新器，ZUV 保留为可选入口（安装事务已被 2026-07-19 决定替代）

- 状态：这是内置更新器的历史起点。Release 查询、下载、校验、GUI/TUI 和 ZUV 边界继续有效；下述 `.old` 替换/回滚机制已被本文顶部 R7 事务更新决定替代。
- 背景：只下载 EXE 的用户不应再为了更新安装 Python、uv 或理解 ZUV；Windows 运行中的 EXE 又不能可靠地自行覆盖。
- 历史决定：仅冻结后的 Windows EXE 启用内置更新。它只接受仓库稳定 `R<n>` Release 中的 `FH-DualSense-Enhanced-R<n>.exe` 和同名 `.sha256`，以 `.part` 下载并检查长度、SHA-256、`MZ` 头。R4 到 R6 的 Helper 会等待旧 PID、生成 `.old`、替换、重启并在失败时回滚；R7 以后不得继续采用这套安装步骤。
- 边界：源码、Linux 和 ZUV 运行不执行 EXE 自替换；不静默提权。ZUV 和 `win_start.bat` 继续保留，作为兼容、开发和网络备用入口，而不是 R4 独立 EXE 的依赖。
- 仍有效的差距：当前每次启动约 10 秒后检查一次，尚无跨启动 24 小时节流，也没有代码签名信任链。R7 只在严格识别 R6 legacy bootstrap 时解析 PE 固定版本资源，该检查不是发布者身份验证。

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
- Profile：该历史默认迁移方式已被 2026-07-17 的持久化 `Default` 取代。当前不会在启动时覆盖 `Default`；命名 Profile 中显式保存的开关同样保持不变。
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

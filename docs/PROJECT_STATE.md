# FH-DualSense-Enhanced 当前项目状态

最后更新时间：2026-08-24

## 当前阶段

- 当前开发版本：`Enhanced R11`，`src/pyproject.toml` 版本为 `11`。
- 当前公开稳定版：GitHub Release `R10`，tag `R10` 指向 merge commit `08c5302`，发布于 2026-08-04。
- 当前阶段：R10 继续作为公开稳定版且 tag/线上资产保持不可变；post-R10 工作树已递增为 `Enhanced R11` PR 候选，并同步锁文件、Windows 版本资源、双语 Release 契约和三语 README。Haptics Lab 已从独立 GUI/TUI 菜单迁入“系统与更新”的默认折叠小卡片；R11 新 `Default` 已按配置 `33` 的最终 ABS 调教落地，旧默认保留为 `Default before R11`，“关于与许可证”已增加 Bilibili 开心散仙调教鸣谢。PR 流程不创建 tag 或发布资产。
- 当前开发重心：R11 汇总 Xbox App 键鼠/手柄热切换、默认关闭的 HidHide 1.7 会话隔离、Steam Input 风格体感到摇杆、系统页默认折叠的 Haptics Lab 和一键诊断包。按用户最终版本边界，R11 不包含新写的 Windows 前台窗口检测或 physical HID ownership gate：native backend 在应用生命周期内正常枚举并持有实体 DualSense，切到桌面或其他游戏不会主动释放。撤下的实现与原回归测试已隔离到 `experiments/foreground_ownership/`，不由生产源码或 PyInstaller 收集；当前 PR 不再准备旧 R10 监听备用包。R11 虚拟目标继续固定为 Xbox 360，不加入 Xbox One/Xbox Series 或 Share 系统键模拟。真实用户目录的内置更新和硬件联动验收只在用户明确要求时执行；不得为了后续修复改动已知可用的 R7 USB/BT 握把生命周期。
- R10 Release：<https://github.com/piereacy/FH-DualSense-Enhanced/releases/tag/R10>。

## 代码中已经实现

### 1. 事务式 Windows 自更新

- `src/modules/update/transaction.py` 定义原子 transaction journal、严格 schema/path/version/hash 校验、随机 token 健康 ACK 与阶段恢复。
- `src/modules/update/install.py` 在配置与 GUI/backend 初始化前检测旧覆盖式 Helper 的 legacy bootstrap，并按 journal 恢复未完成事务；不再看到 `.old` 就盲删。
- `packaging/windows/update_helper.py` 对 R7 以后版本采用规范文件名并排安装。新版在 30 秒内确认并继续存活约 3 秒后才迁移快捷方式和清理旧版；正常路径不创建 `.old`。
- 旧覆盖式 Helper 输出由一次性第二阶段处理：运行 PE 必须等于当前版本，紧邻 `.old` 的 PE 必须不低于文件名版本且低于当前版本。该顺序兼容 `R5.exe` 内置更高版本、`.old` 保存中间回滚版本的多跳形态；随后安装当前规范文件名并提交健康状态。快捷方式部分失败时保留真实回滚版本，而不是盲删 `.old`。
- `packaging/windows/shortcut_links.py` 使用原生 Shell Link COM 扫描当前用户 Desktop、Programs 和已知 pinned 目录，只迁移绝对 target 精确匹配旧 EXE 的 `.lnk`，并保留参数、工作目录和 icon index。
- 健康提交后会枚举同目录全部严格命名且低于新版的规范 EXE，逐个迁移快捷方式并静默删除；严格同名的旧 `.exe.old` 与 `.exe.sha256` 也会清理，包括 R5 更新遗留。其他 EXE、任意 `.old`、同版和更高版本不在清理范围；某一旧版快捷方式失败时只保留该规范 EXE。
- 安装前验证应用目录可写并阻止同一目录内其他规范版本进程参与更新；当前 one-file 内层进程及其同路径直接 bootloader 父进程按一个实例处理，另一次独立启动的进程对仍会阻止更新。legacy bootstrap 使用同一实例保护。每个 transaction 由跨进程锁串行化，主程序不再直接竞争写 pre-install phase。
- PyInstaller one-file 外层 bootloader 和内层应用 PID 不同的情况已处理：token 验证 ACK 身份，Helper 监视自己启动的外层进程存活。
- apply 只回收本次已接管且哈希仍匹配的新版；健康失败会停止完整 one-file 后代树，删除/停止/legacy 恢复任一步失败都保持可恢复的非终态，不再虚假写 `rolled_back`。恢复提交重新验证 ACK PID/实际 EXE 并观察约 3 秒；移动完成但 journal 尚未进入下一 phase 的断电窗口也按三端哈希收口。
- `.sha256` 只接受单个 digest 或明确指向当前规范资产的单行记录；pending 更新重载会复核严格字段、HTTPS、大小、MZ 和哈希。Helper 调度失败后 GUI/TUI 回到 `ready`，关闭冲突实例后可以原地重试。

### 2. DualSense 连接真值、电量和拓扑切换

- `src/modules/dualsense/controller_state.py` 提供不可变 `ControllerSnapshot`、phase、transport、电量和充电状态；GUI/TUI 不再以 `dev is not None` 推断在线。
- `src/modules/dualsense/input_state.py` 验证完整 USB/BT report、report ID、D-pad 和 Bluetooth `0xA1` CRC，并解析 10% 电量档和充电状态。损坏或不完整报告不能刷新在线时间、电量或 XInput consumer。
- `src/modules/dualsense/main.py` 在应用生命周期内由唯一 I/O worker 枚举、打开、读取和写入选定的实体 DualSense；Steam 模式没有 XInput consumer 时仍执行普通输入解析。约 3 秒无有效输入会清除旧 transport、电量和输入；HidHide 与关闭自动重连不绕过 watchdog。R11 已删除 active `passive_detection.py`、`ControllerPhase.AVAILABLE` 和 runtime ownership gate，实验副本只存在于 `experiments/foreground_ownership/`。
- 空闲 HID backlog 会批量 drain，防止旧缓冲延长“已连接”。Steam/无 XInput consumer 时 pending output 仍优先；Xbox bridge 启用时，I/O thread 优先追到输入队尾且只发布批次中的最新有效状态，连续 Bluetooth `0x36` 不再把读取限制为每轮一条。同轮 `0x36` 已携带扳机/灯效且普通 frame 没有 compatible rumble 时会合并重复写入，显式 rumble 与释放不受影响。
- `src/modules/dualsense/topology.py` 约每秒轻量 enumerate，新路径连续两次出现才稳定。未知身份 feature report 读取失败按 1/2/5 秒退避并在路径消失后清除；只对同一身份自动 handover，同一手柄 USB 优先。
- USB/BT handover 和“立即重新连接”都投递到唯一 HID I/O thread。候选 handle 会先打开并读到有效输入。启用 body haptics 的 BT → USB 对稳定候选非阻塞等待 3 秒，期间继续使用 Bluetooth 输入、L2/R2 扳机键和 `0x36` 握把；到期后用只读 Windows MMDevices registry probe 确认活动的 DualSense USB render endpoint。未就绪或异常时关闭候选、保持当前 BT transport/快照/pending output，并按 1/2/5 秒退避，重试不再重复 settle；关闭 body haptics 时绕过 endpoint 条件。readiness 通过后才静音，通过旧 BT handle 发送按 HIDP `0x53` seed CRC 构造的 48 字节 feature report `0x08 / 0x02`，返回正数后原子提交 USB。该命令不用于冷启动、USB → BT 或普通 reconnect。自动 handover 不受完全掉线重连开关限制，不播放启动 R2 扳机键脉冲；“重新扫描”仍只刷新设备列表。
- 临时 USB handle 在 `set_nonblocking` 失败时会关闭，controller lock serial 会规范化，避免设备泄漏和身份格式漂移。
- 普通 USB/BT state report 已恢复 R6 的字段所有权：扳机、compatible rumble 与灯效只声明各自已有的 valid bits。`HapticManager` 只选择 USB 四声道 PCM、Bluetooth `0x36` 或 compatible fallback，不再通过普通 HID report 猜测或切换“音频触觉模式”；也没有加入曾经失败的单次 `0x01` 重置写入。
- 唯一 HID worker 现由 `_io()` 监督 session。未预期异常会关闭当前 handle 并按 0.25/1/5 秒上限恢复；关闭自动重连时保留可由“立即重新连接”唤醒的 worker，按钮检测到旧 worker 已死亡时会重启它，不会并行创建第二个 reader。
- 输入拒绝不再只记录应用启动后的第一次：连续第 1/8/32/128 次及之后每 512 次限频记录，长错误串恢复时记录恢复边沿；HID open 日志包含产品 PID，便于区分 DualSense 与 DualSense Edge。
- 短暂 Bluetooth 输入空档不再永久禁用当前连接的 HD `0x36`；输入恢复后继续保持 HD 握把。只有真实构建、队列或 HID write 失败才进入当前连接的 compatible fallback，持续约 3 秒无有效输入仍由物理 HID watchdog 断开并重连。

### 3. 配置迁移与状态界面

- GUI/TUI 的 LightingTab 不再继承握把页的 `SWITCH_SECTIONS`，灯效页只展示转速灯条、颜色与档位 LED 设置。
- R11 出厂 `Default` 与用户确认的最终配置 `33` 在 136 个 Profile 字段上语义一致，共包含 70 项相对旧默认的实质变化；ABS 默认开启，四处 slider 浮点尾差规范化为十进制值。旧默认作为内置 `Default before R11`，`Original` 继续保留上游 1.6.2 扳机参数并启用 Enhanced body haptics。
- `r11_default_profile_from_33` 对已有配置只运行一次：升级前实际 `Default` 先转存为 `Default before R11`，再安装新 `Default`；命名 Profile 与 active 命名选择不变。首次安装和恢复出厂固定生成 `Default`、`Default before R11`、`Original` 三份内置 Profile。
- GUI/TUI 的“关于与许可证”共用 `modules.about` 中的调教鸣谢名称与 Bilibili URL，六种非英语 catalog 均包含该标签；链接目标不含用户消息末尾的中文句号。
- `src/modules/config/settings.py` 的 `enable_reconnect` 出厂默认改为 `True`。
- `src/modules/config/preferences.py` 通过 `r7_enable_reconnect_default` marker 对已有用户只强制开启一次自动重连。迁移不触碰驾驶体验、命名 Profile 或其他 global 字段，之后用户关闭会被尊重。
- GUI/TUI 的设备分组改为“连接与重连”，现有 Reconnect 已改为真实 I/O 命令；Rescan 语义保持列表刷新。
- 顶部 DualSense 状态框显示 phase、USB/BT、电量和充电状态。仅使用电池且为 10% 时电量细节为红色，连接点仍为绿色；断开后不保留旧电量。Profile/控制器控件已收敛为 28 logical px 高、8 logical px 圆角的小型状态框，并跳过相同状态的重复渲染。
- UDP bind 错误只进入总览遥测状态与日志，不再覆盖顶部控制器 Pill。全部非英语 catalog 已补齐新字段。
- `src/modules/feedback_schema.py` 统一声明扳机与握把字段归属。GUI/Console 的 `Trigger feedback` 顶部显示 Profile 级 `enable_trigger_feedback` 总开关，再显示 L2/R2 子开关、调节和扳机实验项；`Grip haptics` 只显示独立握把开关、调节和握把实验项。两页字段互斥并由翻译覆盖测试约束。
- R2 的“油门末端硬墙”现为独立 Profile 开关，GUI/TUI 均放在“重压阻力”正下方并默认关闭。旧 Profile 缺少该字段时补入 `False`；连续油门阻力、末端 wall 和轮胎抓地力分别由自己的开关控制。
- GUI 左侧导航与 TUI 顶层标签新增独立的“自定义 XBOX 按键映射”页面，全部映射项直接展示，不再放在系统页或折叠子界面。开关和 17 个数字来源属于 global 设置，不进入车辆 Profile 或分享码；关闭开关立即恢复 Steam 默认输出但保留自定义值，一键恢复只重置映射。只有游戏平台选择 Xbox App 时才允许启用或编辑；Steam 模式锁定控件、保留已存值，并明确告知用户应在 Steam 内自行修改映射。全部非英语 catalog 已覆盖该界面。
- 系统页新增默认关闭的“物理手柄隔离”global 开关和共享状态展示。它只在冻结 Windows EXE、Xbox App、direct HID、ViGEmBus ready 与已安装 HidHide 1.7+ 同时成立时工作；切到 Steam/DSX、恢复出厂或关闭开关会热清理，不重建仍可用的虚拟 X360 target。FHDS 不安装 HidHide，也不把该开关保存进车辆 Profile。
- Steam、Xbox App 与 DSX 只选择输入方案。GUI、TUI、headless 在启动/热切换时正常打开所选 backend；R11 不查询前台窗口，也不因桌面或其他游戏取得焦点而停止 HID、触觉或 UDP 输出。Xbox App direct-HID 模式在 service 生命周期内附加 input consumer、虚拟 X360、Raw Input 与用户显式开启的 HidHide；切回 Steam/DSX、安装/重试 driver 或退出时清理。DSX 不持有物理 HID，保留原有本地 UDP 生命周期。

### 3.1 Haptics Lab 与一键诊断包

Haptics Lab 与诊断都复用现有 backend 和只读运行时快照；R11 不再维护等待期被动 PnP 检测或前台许可字段。

- Haptics Lab 不占 GUI 左侧导航或 TUI 顶层标签，只位于“系统与更新”页内默认折叠的小卡片。展开后提供 `10%..65%` 强度、`0.25..3.0` 秒持续时间，以及引擎扫频、路面、积水、打滑、悬挂、左右碰撞、升降挡、红线、ABS、牵引力控制和 L2/R2 阻力场景；参数不进入 Profile。
- `src/modules/haptics/lab.py` 只发布不可变预览请求，`src/modules/loop.py` 继续独占手柄输出。backend 已连接时可播放最长 3 秒的有界预览；任一有效游戏遥测包会抢占预览。折叠卡片、离开系统页、窗口失焦/隐藏、控制器断连、到期、停止、重启或退出也会撤销；不会创建虚拟 X360、Raw Input、HidHide 或第二个 HID reader。USB/Bluetooth 握把复用现有 `HapticManager`，DSX 开放所有含扳机输出的场景并忽略握把层。
- `src/modules/diagnostics.py` 从 controller、UDP、DSX、XInput/HidHide、USB/Bluetooth 触觉、Lab 与运行时错误快照收集状态，并在 `data/diagnostics/` 原子写入 `diagnostics.json`、说明和有界日志 ZIP。包不包含 preferences/Profile 原文或原始 HID/UDP payload；控制器 identity 只保留短 SHA-256 指纹，不自动上传。系统页的 GUI/TUI 按钮都在后台执行导出。
- UDP、HID/DSX、USB audio、Bluetooth haptics 与路由层新增低成本诊断计数器；它们使用各自的短锁或既有所有权，不改变 HID report、PortAudio lifecycle 或 Bluetooth `0x36` 调度。

### 4. Windows Per-Monitor v2 与可复现构建

- `packaging/windows/fhds.manifest` 为主 EXE 与 Update Helper 声明 `PerMonitorV2, PerMonitor`、旧 fallback 和 `asInvoker`。
- `packaging/windows/dpi_runtime_hook.py` 与 `src/main.py` 在任何 Tk/CustomTkinter 窗口前调用 `modules.dpi.bootstrap_windows_dpi()`；旧的 GUI 构造后 `SetProcessDpiAwareness(2)` 已删除。
- `src/modules/dpi.py` 查询实际 thread/window awareness、窗口 DPI 与缩放率。GUI 系统页显示该诊断，不是 PMv2 时提示检查 Windows 兼容性覆盖，不修改注册表。
- `src/modules/gui/widgets.py` 让隐藏页暂停 `FastScroll` canvas 尺寸回流，可见页以 40 ms debounce 合并 resize；反馈开关卡片以 80 ms debounce 处理列数变化并复用既有 grid item。卡片说明按实际内宽换行：Tk configure 事件的物理像素先换回 CustomTkinter logical px，`W.Hint` 再根据文本请求高度增长，避免双列、窗口缩放和 125% DPI 下裁切后半句。`src/modules/gui/main.py` 在 `tkraise()` 导航边界切换活跃页，避免最大化时所有常驻长页同时重新布局；系统更新卡片只在稳定 presentation 变化时重绘，不再每 250 ms 无条件显隐按钮。新版本快照现在同时显示可点击的规范 EXE 手动下载直链，GUI 使用可换行标签避免长 URL 裁切，TUI 提供同一入口。
- `src/pyproject.toml` 和 `src/uv.lock` 固定 PyInstaller `6.16.0`；`packaging/windows/build_exe.bat` 使用 `uv run --project src --frozen pyinstaller` 构建 Helper 和主 EXE，不再用任意最新 `uvx` 解析。
- 审计后的 R7 候选已重新嵌入并验证 PMv2 manifest、R7 PE 版本资源和项目图标；精确产物信息见下方“已执行的测试和验证”。

### 5. 全项目审计中已落实的整改

- 配置与 Profile：`preferences.py` 对 JSON 根对象、嵌套 Profile、类型和非有限浮点做严格归一化；`udp_host`、`udp_timeout`、`telemetry_lost_exit_s` 明确归入 globals。写入使用 UUID 临时文件和原子 replace，恢复出厂或损坏恢复在无法先保护有效文件时失败关闭。
- 分享与显示：`profiles.py` 对压缩输入和解压输出设上限，Profile 名称去控制字符并限制 64 字符，重名 suffix 同样受限；TUI 对动态 Profile、路径、错误和状态文本禁用或转义 Rich markup。
- UDP 与遥测：listener 只在完整 324 字节包成功解析后推进“最后有效遥测”，字段进入效果计算前会清理非有限数；损坏流量不能持续刷新在线状态或让旧效果继续输出。latest-only drain 每轮限制为 64 个 datagram，持续灌包也会返回；同端口 localhost、wildcard 与完整 `127/8` 的明显自转发会在构造时剔除。
- 触觉：USB stream 生命周期保持 Enhanced R6。GUI/TUI 共享 stream 的 `start()/stop()` 只由 `UsbAudioLifecycle` 拥有，telemetry `HapticManager` 在 pause/close 时只写 `SILENT_FRAME`；backend、transport、设置和 Lab preview 的 eligibility 变化投递到 GUI/TUI 主线程，周期 1 秒继续负责恢复重试。headless `HapticManager` 在同一 transport epoch 启动失败后设置闩锁，避免逐遥测帧重开，并在 transport 或 eligibility 变化时复位。Windows `UsbAudioHaptics` 只在 `start()` 延迟导入 sounddevice，再查询当时初始化的 WASAPI snapshot；Bluetooth 阶段不会提前初始化 PortAudio。代码不调用私有 PortAudio refresh、不做 callback 心跳判活，也不增加 lifecycle lock。Bluetooth worker、`0x36`、USB/BT stop 和 compatible fallback 的失败隔离与释放路径仍保留。
- Linux：`_hidraw.py` 改用 wrapper 实际支持的 `timeout_ms` 关键字；`packaging/linux/build_elf.sh` 改为 `uv.lock` 冻结环境，并跳过 one-file 不需要的 PyGObject/pycairo。当前只完成 Windows 上的单元测试和 Bash 语法检查，不等同真实 Linux 构建。
- GUI/TUI：TUI 新增与 GUI 同语义的 `ProfileSession` 退出流程；快捷键、按钮、backend shutdown 和更新安装都经过统一关闭入口，取消时不会提前调度 Helper。更新健康 callback 在 backend、listener 和 telemetry worker 启动后才执行，构造窗口本身不再提前确认健康。扳机/握把两页现在从共享 schema 渲染，开关、常用调节和实验项不再混页。GUI 扳机页双列时让总开关和共享反馈各跨整行、L2/R2 同行配对，消除行高对齐造成的大块空白；窄窗口仍为单列。R2 与握把红线开关不再重复显示电动车运行时规则说明。
- 启动与依赖：删除 `src/dev.env` 和运行时 `python-dotenv`，主程序不再因快捷方式工作目录中的同名文件改变配置。Pillow、PyInstaller、Pyrefly 与锁文件依赖已经固定到当前项目声明。
- 更新与文件工具：Release、sidecar、pending metadata、transaction plan、路径和 checksum 采用严格 schema/HTTPS/credential/大小校验；FH6 语言与图标文件操作在无法证明目标、备份或进程状态时失败关闭，不以宽泛删除“修复”未知残留。

### 6. 共享动态红线估计

- `src/modules/forzahorizon/redline.py` 保留原始仪表 `max_rpm`，学习前提供经验预测。预测窗口内继续在高油门、稳定同挡、低离合和低轮胎滑移条件下检测功率/扭矩切断；已确认燃油车还可在预测窗口外用功率与扭矩同时塌陷进行宽范围冷启动，不再因仪表红区过大而无法收集第一个候选。两条路径都用 120 ms 同挡延迟确认排除换挡。
- 预测窗口内第一次确认断油即可产生短暂 `rev_limiter_active`；预测窗口外第一次只收集候选，第二个相近 RPM 候选才发布 limiter，三个相近候选以中位数建立 `effective_redline_rpm`，不同转速的分散事件不能互相确认。后续允许平滑修正；车辆 ordinal、PI、气缸数或仪表范围改变时重置，菜单临时归零不清除学习。电驱与缺少气缸字段的旧映射不进入宽范围冷启动。
- `src/modules/loop.py` 把同一派生状态交给 `effects.py` 的 R2 扳机键、`haptics/mixer.py` 的握把红线和 `forzahorizon/lighting.py` 的转速灯条；灯条直接消费学习后的极限，不再按仪表 `max_rpm` 重算另一套固定阈值。Default 的三路比例式提醒由 93% 后移到 95%，握把退出点为 92%；升级加载只在 Default 四项仍完整等于 R7 旧默认时一次性迁移，任一已调组合和命名 Profile 保持原样。alert gate 开启时确认断油仍会立即强制灯条闪烁，动态估计不可用时灯条回退原始 `max_rpm`。发动机底噪继续读取原始范围，代码未采用参考分支直接覆盖 telemetry 的做法。
- `RedlineDetector` 还发布 `redline_alert_allowed`：只要 `NumCylinders == 0`，握把与 R2 的比例式和确认 limiter 红线路径都保持静默，观察到二挡或更高挡也不会恢复；灯条继续显示 RPM 渐变，在接近极限时保持稳定红色但不进行换挡式闪烁。缺失气缸字段时保持旧行为。
- 合成遥测已覆盖预测红线约 `11760 RPM`、真实断油约 `6200 RPM` 的极端大红区冷启动，以及一次/不同 RPM 功率塌陷不触发和电驱不进入宽范围学习；灯效端到端回归还固定了学习前同一 RPM 不亮、学习到约 `6200 RPM` 后按共享极限进入红色。尚未用真实大红区车辆确认学习速度、牵引力控制误触发和手感。

### 7. R11 backend 生命周期与 Xbox bridge 恢复

- R11 生产源码已移除 `is_any_forza_game_foreground()`、Win32 foreground PID 查询、独立 detector、`WAITING_GAME`、runtime tick、被动 PnP 等待检测和延迟启动脉冲。native backend 随应用运行，实时 UDP 遥测不经过窗口许可；实验代码与旧测试保存在 `experiments/foreground_ownership/`，生产包必须验证未收集。
- Steam 的原生 DualSense backend、Xbox App direct HID 和 DSX socket 均在应用启动时打开并保持各自连接语义。Xbox App 在 direct-HID backend sync 后附加 input consumer、X360 target、Raw Input 与可选 HidHide；Steam 不创建本项目虚拟设备。Haptics Lab 与游戏共享同一输出 loop，第一份有效遥测会停止预览而不回放旧预览请求。
- `src/modules/xinput/bridge.py` 在 100 ms 无新输入时只发送一次中立状态，bridge 模式仍启用期间保留同一个 X360 target/player slot；新物理报告直接复用 target，切回 Steam 或停止应用时才移除。每次会话轮换 generation-bound publisher；stop timeout 后的新会话只登记一个 pending successor，等旧 target/client 关闭后自动恢复，不并发创建第二个虚拟手柄，也不接受旧 consumer 回放。
- `src/modules/xinput/hot_switch.py` 现用后台 Raw Input 隐藏窗口只注册 keyboard/mouse device class。键鼠边沿会把同一个 X360 target 中立化并把 `input_owner` 设为 keyboard/mouse；小幅摇杆/扳机噪声保持抑制，D-pad、按钮、触摸板点击或越过阈值的轴变化会恢复 controller owner。总览显示“键盘和鼠标正在使用”及恢复提示。
- Raw Input listener 只随 direct-HID Xbox App service 启停，Steam、DSX、不支持的平台、driver 安装、重试和退出都不保留注册线程。每轮慢启动有独立 cancellation event；startup/join 超时后 monitor 在旧线程真正结束前保留引用并禁止创建第二条 listener，退出后由周期 lifecycle pass 重试。启动失败时 bridge fail open。该层只停止本项目虚拟 X360 report；物理 HID 隔离由独立的 HidHide session 层处理。
- `src/modules/dualsense/hidhide.py` 直接实现 HidHide 1.7 control-device IOCTL。当前规范 EXE 的 application whitelist 是唯一允许的持久改动，并由 `data/hidhide_owned.json` 记录 ownership 以迁移版本化 EXE 路径；用户规则和永久 device blacklist 不被改写。DualSense instance 只加入调用 PID 的 session blacklist，正常停止显式 clear，崩溃或 kill 由 driver 自动回收。FHDS 永远不改全局 `Active`；用户未先在官方 Configuration Client 启用 device hiding、inverse 用户规则冲突、旧 driver 或写后校验失败时拒绝隔离并保持 direct HID fail open。
- `DualSense` 唯一 I/O worker 在打开普通接口和 handover 候选前调用 visibility observer；热启用则立即登记当前接口。observer 只配置过滤器，不持有 HID handle，也不能建立连接真值。游戏已经打开物理 handle 时可能必须重启游戏。
- USB/BT 共用输入解析现识别触摸板 click 和活动触点横坐标，并按本机 Steam PS5 Gamepad 模板把左半区映射为 Back/View、右半区映射为 Start/Menu；Create/Options 保留相同的独立入口。坐标不用于滑动或多点手势，麦克风键仍不进入 XInput。
- `src/modules/xinput/mapping.py` 统一声明 17 个数字来源、16 个 Xbox 目标（含 Disabled）和 Steam 默认值；非法偏好逐来源回退。自定义映射开启时可交换或合并数字键，摇杆轴与 L2/R2 模拟输入始终固定。GUI/TUI 独立页面只有在游戏平台选择 Xbox App 时才开放自定义开关、映射菜单和恢复动作；Steam 模式保留设置但锁定编辑。bridge 通过 mapping revision 重发仍新鲜的 latest state，热更新不会重建 X360 target/player slot。
- Xbox App 映射页现包含默认关闭的 Steam Input 风格体感兼容层。必须先开启“自定义 Xbox 映射”总开关，再开启“启用陀螺仪”子开关；任一关闭都会在运行层热发布 Off 并归零体感，而不是只禁用控件。DualSense USB/BT common report 的 gyro、accelerometer 与 3 MHz timestamp 由唯一 HID reader 解码，active handle 读取 feature `0x05` 校准，失败则安全回退 nominal scale。Camera 以角速度输出摇杆，Deflection 以 timestamp 积分并用重力方向缓慢纠偏；可选左右摇杆、Yaw/Roll/组合、垂直轴、激活键、反转、deadzone 与 smoothing。虚拟 X360 没有原生 sensor 通道，因此这里只生成叠加并 clamp 的摇杆 report；六语言 GUI/TUI、global persistence、热更新与键鼠 owner 回归已经加入，真实 DualSense/Forza 手感和与 Steam Input 的 A/B 尚未验收。
- “关于与许可证”现同时显示当前项目仓库 `https://github.com/piereacy/FH-DualSense-Enhanced`，并继续保留原作者、原项目、Sponsor、第三方组件和 Nexus MOD 链接。
- ViGEm 非 driver-missing session 异常会清理旧 target/client，并按 0.25/1/5 秒上限自动重建。driver 缺失仍维持稳定状态等待用户安装或显式重试；旧输入不会跨 stop/restart 回放。HidHide 的启用与清理失败保留真实状态并每秒重试，不再把失败结果缓存成已应用。
- `src/modules/runtime_logging.py` 为 GUI、TUI 和 headless 安装 2 MiB、两个备份的轮转 `data/runtime.log`；UI 关闭日志 handler 后，backend teardown 仍可写入。该文件用于用户反馈“玩到后面不认手柄”时区分 HID CRC、worker、ViGEm 和 handover 故障。
- 自动测试覆盖 target 保留、stale 后复用、映射热更新时保持同一 target、非法 target 回退、旧 consumer 代际隔离、stop timeout 后唯一 successor、HidHide IOCTL/MULTI_SZ、规则 ownership/迁移/回滚、session-only device 隐藏、实际 target 前置条件、Raw Input 启停、UDP drain 上限/自转发、GUI/TUI schema/翻译契约、ViGEm update 异常重建、物理 worker 恢复、手动 reconnect 复活 dead worker、Bluetooth stall 静音/降级及日志 handler。前台 ownership 的旧测试已随实现移入实验目录，不参与 R11 活动套件。真实 HidHide driver、DualSense Edge、崩坏：星穹铁道、Xbox App 游戏和 30 至 60 分钟 Bluetooth 压力测试未执行。

### 8. Xbox App flat-file 自动发现与 FH6 手动 fallback

- `game_launch.windows_local_drive_roots()` 只枚举 Windows 本地 fixed/removable drive；`xbox_library_roots()` 读取每盘最多 4096 字节的 `RGBX` `.GamingRoot` 相对路径，并兼容默认 `XboxGames`。每库只检查根目录、标准名称和最多 512 个直属目录，不访问网络盘、`WindowsApps`、全盘或递归子目录，也拒绝解析后跳出库根的链接。
- 通用 `discover_xbox_forza_install()` 按 FH4/FH5/FH6 精确 EXE 验证候选；FH6 语言和图标入口还要求各自资源目录。GUI/TUI 在 Xbox App 模式自动调用该发现并缓存 payload 根目录到 `fh6_xbox_install_path`。
- 手动选择仍可指向 payload 根目录或其直接父目录 `Content`。GUI 的显式选择以新 serial 抢占后台扫描，无效选择提供可见提示。生产代码和自动测试已完成；真实 Xbox App FH4/FH5/FH6 安装仍未在当前电脑验证。

### 9. L2/R2 基础阻力与 firmware end wall 所有权

- 旧 `Controller.L2()` 与 `Controller.R2()` 会在检查 `enable_brake_resistance` / `enable_throttle_resistance` 之前无条件锁存 `build_wall(wall_zones=2)`。因此即使两个基础阻力开关已经关闭，满踏板输入仍会返回 mode `0x21`，顶部两个 zone 保持满强度，形成约 80% 到 90% 行程的硬墙。
- L2 通用 wall 仍由 `Brake stiffness` 拥有；运行中关闭会立即清除 L2 latch。可选静态刹车 wall 继续独立生效，它按固定位置和硬度建立刹车限位，不读取 ABS、车速或轮胎滑移。
- R2 通用 wall 已从 `Throttle stiffness` 拆出，由默认关闭的 `enable_throttle_end_wall` 独立拥有。静止/重压阻力只形成连续 ramp；两值为零且 wall 关闭时全程自由，两值为零但用户显式开启 wall 时只在末端限位。关闭 wall 会立即清除 R2 latch。
- 旧 Profile 缺少新字段时写入安全默认 `False`，不会从当前 Profile 继承，也不会根据阻力值猜测。轮胎抓地力、红线、boost/G 力和其他震动继续服从各自开关；油门连续阻力和 wall 都关闭时，抓地力反馈仍可独立输出。
- 自动回归覆盖两侧 wall 所有者运行中关闭、R2 默认关闭、零阻力与显式 wall 组合、抓地力独立性、GUI/TUI 字段顺序、翻译和旧 Profile 回填。真实 DualSense/Forza 行程与手感尚未执行。

### 10. 自适应扳机总开关

- 现场 Profile 已关闭基础刹车/油门阻力、ABS、红线、换挡、碰撞和路面扳机效果，但 `enable_wheelspin_buzz=True` 仍可在油门与驱动轮打滑时输出 R2 vibration mode；这就是“震动全关后仍有反馈”的另一条独立路径。握把红线和 body collision 还会通过外壳传到扣住扳机键的手指，但不属于 L2/R2 frame。
- `enable_trigger_feedback=False` 现在位于全部 L2/R2 priority 之前：下一帧返回双 `off()`，清除换挡、ABS、抓地力、红线、碰撞、EWMA 和两侧 wall latch。direct `L2()` / `R2()` 也有相同 gate，`modules.make_backend()` 还会在总开关关闭时拒绝自动启动脉冲。
- 总开关默认 `True` 以保持现有 Profile 行为；关闭不会改写任何子开关或调节值。握把触觉仍由 `Grip haptics` 独立控制。
- 新冻结 R8 已在 Bluetooth DualSense 90% 电量、实时 Forza 遥测现场显示并保存总开关。冒烟时故意保留轮胎抓地力、刹车/油门阻力和 body haptics 为开启，只关闭总开关；偏好文件复核为 `enable_trigger_feedback=False`。实际 L2/R2 触感是否立即完全释放仍需用户确认。

## 文档、代码和推测的边界

- 已由生产代码和自动测试证明：transaction 恢复决策、多跳 legacy PE 顺序识别、快捷方式精确匹配、健康 token 与 ACK 时机、自适应扳机总开关、启动脉冲 gate、ControllerSnapshot、输入超时、电量映射、拓扑去抖、handover 候选预验证与 1/2/5 秒候选退避、switching 无启动脉冲、重连迁移、物理 HID worker 自恢复、ViGEm session 自恢复、100 ms 中立后 target 保留、HidHide 规则 ownership 与 session-only 清理、短暂 Bluetooth 输入空档保持 HD 队列、UDP 有效包边界、配置/分享码校验、TUI 正常退出、Enhanced R6 USB stream 状态语义、扳机/握把字段互斥、可见页 resize 合并、更新卡片 presentation cache、状态展示和 DPI 几何契约。Xbox 自动发现测试覆盖 `.GamingRoot`、默认库、FH4/FH5/FH6 精确识别、不安全 marker、非递归和链接逃逸拒绝。新增测试固定 sounddevice 构造时不加载、首次 `start()` 只加载一次，Windows endpoint active/inactive/权限错误边界，3 秒非阻塞 settle、等待期间 Bluetooth haptics 保持、readiness 失败/异常保留 BT、候选消失清理状态及 body haptics 关闭时绕过。字节级测试继续固定普通 USB/BT report 不声明两个未经验证的 `0x20` 控制位，以及 Bluetooth power-off feature report 的 48 字节布局和 `0x53` seed CRC `0x23A2EFE0`。当前机器没有安装 HidHide，因此真实 driver、崩坏：星穹铁道、长时间连接、DualSense Edge、握把恢复和真实 Xbox 游戏目录仍不属于自动测试已经证明的事实。
- 已由真实 Windows 隔离环境证明：当前线上 R7 资产可以事务升级到规范 R8，健康提交后 R7 EXE、严格同名 `.old` 与 `.sha256` 被清理，无关 `notes.old` 保留；另一次 `R5.exe` 内置 R8、`R5.exe.old` 保存真实 R6 的多跳引导也成功提交并规范化为 R8。早期已发布 R6 旧 Helper 到 R7 的快捷方式迁移演练仍作为历史证据保留。
- 已由当前 Windows 进程证明：源码 DPI probe 报告 Per-Monitor v2、120 DPI、125%；最终 PE manifest 可提取并包含 PMv2。
- 已由当前真实 Windows USB 设备证明：系统和新启动的 sounddevice 进程能枚举 index 27 的四声道 DualSense WASAPI endpoint；旧 teardown 候选却在同一现场报告找不到端点。当前锁定的 sounddevice 在 import 尾部调用 `_initialize()`，因此旧进程的 PortAudio snapshot 早于 USB hotplug。源码手工检查还证明导入 `modules` 和构造 native backend 都不会再把 sounddevice 放入 `sys.modules`，readiness probe 返回 `True` 时也不会加载它。
- 已由真实硬件复现并验收当前 `dist-usb-audio-gate-1`：USB 与 Bluetooth 冷启动握把正常，BT → USB 后 USB 握把恢复；代价是拔掉 USB 时手柄会关机，需要重新按 PS 键开机。旧 R6-lifecycle 和 `0x08 / 0x02` teardown 候选的失败记录仅作为根因历史保留。
- 已由当前 Windows 源码进程证明：本地磁盘枚举得到 `C:\`、`D:\`，`C:\.GamingRoot` 被解析为 `C:\XboxGames`。当前机器没有可验证的 Xbox App FH4/FH5/FH6，因此这里只证明 marker 与库发现，不证明真实游戏识别或文件权限。
- 尚未由真实显示器组合证明：不同缩放率显示器间移动、运行中更改缩放、睡眠/唤醒、扩展坞和远程桌面后的清晰度与单次缩放。
- 根据代码推测可能成立但不得写成已验证：同一身份判定能覆盖不同固件/蓝牙适配器和 DualSense Edge 的全部 raw identifier 组合。

## 正在进行

1. R10 已把 R2 油门末端硬墙拆成独立且默认关闭的开关，并完成版本、双语发布契约、自动回归、隔离 Windows 审阅构建和正式发布。真实 DualSense/Forza 行程与手感验收仍待执行；R10 tag 和线上资产保持不变。
2. 非破坏性 BT/USB HID handover、switching 脉冲抑制、Bluetooth `0x36`、扳机与握把分页、状态框像素对齐、更新 UI 缓存和最大化布局合并保留在当前候选。PortAudio 私有 refresh、并发 lifecycle lock、callback 心跳和额外 USB audio backoff 均未恢复。
3. `dist-usb-audio-gate-1` 已由用户实机确认：USB 与 Bluetooth 冷启动握把正常，Bluetooth 插入 USB 后 USB 握把恢复；拔掉 USB 时手柄会关机，需要用户重新开机。用户已接受该行为作为当前 R7 handover 基线，后续修复不得改动这条生命周期。
4. Xbox App Bluetooth 高延迟与长期掉线修复已进入 `src/modules/dualsense/main.py`、`src/modules/xinput/bridge.py` 和 `src/modules/runtime_logging.py`：包括 input-first/latest-only drain、重复 Bluetooth 写入合并、HID/ViGEm 自恢复、target 保留和持久日志。早期 350 ms `0x36` stall 永久降级已因无法从短暂弱信号自动恢复而撤销；真实 Bluetooth/XInput/DualSense Edge 手感与长时间稳定性尚待验证。
5. 动态红线估计已经进入生产路径；宽范围燃油车冷启动已解除大红区无法进入预测窗口的循环依赖，合成测试覆盖 `11760 → 6200 RPM` 学习、第二次聚类才发布 limiter、第三次建立学习值、分散事件不合并和电驱排除。R2、握把与灯条共用学习值，Default 提前点为 95%，握把退出点为 92%。全部电动车 alert gate 已进入当前源码：一挡、二挡和更高挡都禁止握把/R2 红线触觉，灯条继续渐变并在极限稳定红色；真实燃油车与电动车验收仍未执行。
6. Xbox App flat-file 自动发现已进入通用游戏模块与 FH6 语言/图标页面。代码和合成目录测试完成，本机 `.GamingRoot` 解析成功；真实 Xbox App 游戏目录仍待验收。
7. 发布后从桌面 R7 实际点击更新复现了错误阻断：同目录实例保护由 commit `7ce4479` 首次加入 R7，R5/R6 没有该检查，R8 原样继承。此前 R5/R6 → R7 由旧版更新入口执行，所以可以成功；R7 → R8 才第一次在真实桌面升级中运行这条新检查。2026-07-30 现场内层 PID `24424` 与直接父 PID `45212` 指向同一 `FH-DualSense-Enhanced-R5.exe`，该文件真实 PE 为 R7，紧邻 `.old` 真实 PE 为 R6，并非用户启动了第二个实例。修复后隔离冻结 R9 单实例能提交到 R10，额外启动的一对 R9 PID 仍在创建 transaction 前被拒绝；发布版 R7/R8 仍需一次手动升级才能获得修复。
8. HidHide 1.7 session isolation 已进入当前源码；本机未安装 driver，所以只完成 API 契约与 fake-driver 故障矩阵。真实验收需要安装官方 HidHide 1.7+，先在官方 Configuration Client 开启 Device hiding，再选择 Xbox App 和 direct HID、确认 ViGEmBus ready 后显式打开 FHDS 开关；随后重启已运行的崩坏：星穹铁道并检查物理 DualSense 不再被游戏枚举、虚拟 X360 与键鼠 owner 热切换正常。FHDS 不安装 driver、不改变全局 `Active` 或永久设备列表；测试后记录游戏内振动与 Steam Input 状态。

## 尚未完成

1. 动态红线需要三组实车：一辆仪表红区明显大于真实断油范围的燃油车，至少连续触发三次同挡位断油；一辆单挡电动车和一辆多挡电动车，分别从低速持续全油门到极速并经过坡度/颠簸，确认握把/R2 全程没有红线触觉、灯条仍随转速接近极限并只保持红色而不闪烁。各组都保持 Forza 游戏内振动关闭并记录 Steam Input 状态；仍需确认普通换挡、漂移、腾空和严重空转边界。
2. R10 本地审阅 EXE 已从当前源码隔离构建并通过无界面启动；仍需在 Bluetooth、Xbox App bridge 开启、Steam Input 关闭时做短时操控/握把/L2/R2 扳机键冒烟，并在可用的 DualSense Edge 上运行 30 至 60 分钟检查 `data/runtime.log`。用户当前无法执行长时间实机段，因此明确保留为未执行；`dist-usb-audio-gate-1` 仍是已知可用回退基线。
3. Windows DPI：125% 隔离设置窗口已确认扳机/握把卡片不吞字；仍需在 100%、125%、150% 的冻结 EXE 中目测顶部两个状态框边缘，并检查窗口最大化/还原和页面切换。混合 DPI 还需验证显示器间往返、运行中 scale 变化和弹窗/原生 Tk 控件清晰度。
4. Xbox App FH6 自动发现需要在真实安装上确认 `.GamingRoot`、wrapper/`Content` 布局、ACL、语言表和图标目标；当前机器只有库 marker，没有对应游戏。
5. R10 已正式发布；完整修复后的合成冻结 R9 → R10 成功、真多开拒绝、启动即退回滚、inner 挂死超时和 orphan journal 恢复均已验收。按用户要求，本次没有执行真实用户目录的 R9 → R10 按钮事务、快捷方式迁移或旧文件清理，也没有下载线上资产；这些验收只在用户明确要求后执行。
6. 真实只读/被占用快捷方式、任务栏 pin 缓存和快捷方式部分失败后的跨启动修复尚未在用户 shell 环境执行。
7. GitHub runner 已成功构建 Linux ELF，但真实 Linux 主机上的 `/dev/hidraw` 权限、USB audio 与桌面托盘仍未执行；Windows 上的脚本语法和适配层测试不能替代它们。
8. Xbox App/Bluetooth 延迟修复尚未用真实 Xbox App 游戏验收；可先用 Steam 版关闭 Steam Input、选择 Xbox App bridge 做输入链路 A/B，但该结果不能替代真实 Xbox App。
9. Xbox App FH6 自动发现、外层目录和直接 `Content` payload 的手动 fallback 均有自动测试，但尚未在真实 Xbox App 安装上验证权限、实际目录布局和语言/图标文件。
10. Steam Input 风格的 Camera/Deflection 体感到摇杆映射已完成自动回归与冻结包启动冒烟；仍需用真实 DualSense 分别在 USB、Bluetooth 下检查静止漂移、Roll 左摇杆转向、Yaw 右摇杆视角、L2/触摸板激活、键鼠中立后重新接管，以及实体摇杆与体感叠加 clamp。该验收应记录 full-stick 速度/角度、deadzone、smoothing、Steam Input 与游戏内振动状态，并与 Steam Input 同名模式做手感 A/B；不能把自动测试写成实机通过。

## 下一步建议顺序

1. 在 Steam 模式保持 Steam Input 开启、游戏内振动关闭；关闭 `Brake stiffness`、`Throttle stiffness` 与“油门末端硬墙”，分别把 L2/R2 压到全行程，确认不再约 89% 定住。随后让油门两项阻力保持为零，只开启末端硬墙，确认前段自由且仅末端限位；再逐项开启基础阻力和独立静态刹车 wall，确认各自所有权。
2. 保留真实测试的连接方式、Steam Input 与游戏内振动状态；自动测试或 EXE 冒烟不能替代手感验收。
3. R10 已正式发布；保持 tag 与资产不可变，不做发布后重复下载或测试。真实 R9 → R10 用户目录更新只在用户明确要求时执行。
4. 在真实 Linux 主机生成 ELF，并验证 hidraw 权限、USB audio 与托盘。

## 当前已知 Bug 和限制

- 已发布 R7 与 R8 的实例保护会把当前 PyInstaller one-file 外层 bootloader 误判为同目录第二个实例，导致更新在 Helper 启动前失败；工作树源码与冻结矩阵已修复，但现有用户必须手动安装一次递增版本，不能靠已受影响的内置更新入口自我修复。手动放入 R9 只保证新文件名正确，不会在无 journal 的情况下主动删除 R7/R8/`.old`；这些严格旧文件会在 R9 之后第一次健康的内置更新中收口。
- `dist-usb-audio-gate-1` 已实机恢复 BT → USB 后的 USB 握把，但代价是拔掉 USB 时手柄关机，需要用户重新开机；当前不尝试保持无线会话的替代方案。
- Xbox App FH4/FH5/FH6 真实游戏仍未在当前电脑验收。自动发现只支持可访问的 GDK flat-file 游戏库，不扫描受保护 `WindowsApps`；未找到或布局不兼容时仍需手动选择 payload 根目录或其直接父目录。
- Forza 游戏内振动必须关闭，否则 native rumble/Steam Input 可能掩盖本项目握把方向与细节；项目不接管游戏原生 rumble。
- 动态红线没有 Forza 官方 limiter flag 或总挡位数字段，只能从功率、扭矩、RPM、挡位、油门、离合、滑移与 `NumCylinders` 推断。宽范围冷启动用重复同 RPM 聚类降低一次功率波动误报，但真实牵引力控制、特殊限速、改装传动与游戏字段异常尚未验证；全部电动车 gate 目前仍只有合成回归。若游戏把改装或混合动力错误报告为 `NumCylinders == 0`，它也会关闭红线触觉，因此不能写成已经解决全部车型差异。
- XInput bridge 不接收游戏 rumble，也没有多手柄、Xbox One target、GameInput impulse trigger、触摸板滑动/手势或原生 sensor target。当前陀螺仪只能按 Steam Input 风格转换为叠加的 X360 摇杆输出，不是游戏可枚举的原生体感设备；普通摇杆/L2/R2 仍不提供自定义曲线或交换层。触摸板点击继续按横坐标把左右半区作为两个可配置数字来源，默认 Back/View 与 Start/Menu。
- Bluetooth 弱信号下仍可能出现短时输入延迟或最终触发约 3 秒物理连接 watchdog；撤销 350 ms 永久降级避免了靠近主机后仍停留在 compatible rumble，但真实 Xbox App、不同蓝牙适配器和 DualSense Edge 的长期稳定性仍待实机验证。
- ViGEm 上游 EOL；固定哈希不能替代未来安全维护。
- HidHide 不是随程序提供的依赖，当前集成要求用户另外安装 1.7+；游戏在启用隔离前已经打开物理 handle 时需要重启。异常退出由 driver 清理 session device entries，但 FHDS 自己的 application whitelist 会保留到下次版本迁移或用户关闭开关。
- 更新检查仍在每次启动约 10 秒后执行，没有跨启动 24 小时节流，也没有代码签名信任链。
- Linux build script 已改为锁定依赖并显式跳过 PyGObject/pycairo，但尚未在真实 Linux 主机生成 ELF；R7 的 Windows updater、Shell Link 和 DPI 改动明确只支持 Windows。

## 当前技术债

- 完成和回滚的 update transaction journal 没有按保留期自动清理；本轮新增的是安装目录旧 release/sidecar 收口，不是 journal 清理。
- `UpdateService.stop()` 不会取消或 join 已进入网络 I/O 的 daemon worker；退出时可能留下唯一命名的未完成 `.part`。无效 pending metadata 被删除后，无法证明归属的 staged EXE 会保守保留。
- Shell Link 扫描无法覆盖任意未知目录中的用户自建快捷方式；部分失败必须依靠保留旧版和后续重试。
- 偏好文件没有跨进程锁，多实例同时保存仍是 last-writer-wins；FH6 语言和图标文件事务也没有跨进程互斥。
- 扳机与握把 section 已集中到 `feedback_schema.py`；系统设置和灯效 section 仍由 GUI/TUI 分别声明，依靠测试保持一致。
- 遥测仍使用未类型化 `dict`。
- `ProcessWatcher` 的通用退出观察仍按 `forza` 子串匹配；启动器使用精确 EXE 名。
- USB audio stream 仍按 host API、名称和声道数自动选择，没有用户可选 endpoint；BT → USB readiness 只识别 Sony VID、DualSense PID、`MI_00` 和 active render state，不负责最终 PortAudio device index 选择。
- 多个同名 DualSense audio endpoint 存在时，当前代码不能按 HID serial 精确绑定音频设备。
- USB audio 使用 Enhanced R6 的 `_running` 布尔状态，无法直接证明 active stream 正在输出非零 PCM；readiness probe 和 sounddevice snapshot 都没有 HID serial 到音频 endpoint 的绑定。延迟 import 只解决当前进程首次 PortAudio 初始化时机，不能处理同一进程之后再次出现的任意音频拓扑变化。任何未来健康检测或 hotplug refresh 都必须先通过 R6/R7 冷启动与热切换实机 A/B，不能再次只靠 mock、registry 可见或静音开流合入。
- 三份 README 是独立文件，关键事实依赖契约测试和人工语义同步。
- 基础油门阻力与实验性 G 力层仍缺少受控 Enhanced R3/Enhanced R4 最终输出对照，这与本轮连接基础设施无关。
- 一键诊断 ZIP 已进入 GUI/TUI；仍缺少 HID report sequence gap 和蓝牙适配器射频指标，连续 CRC 错误目前只能按拒绝计数、限频日志和恢复边沿诊断。
- 原生 `tk.Listbox`、`tk.Text` 与 `tk.Scrollbar` 当前依赖 Tk 自身 DPI 行为，没有像 CTk widget 一样注册独立 scaling callback。是否需要专门 observer 必须由混合 DPI 视觉验收决定，当前状态为待确认，不能把设计计划写成已实现代码。

## 暂时不要修改

- 不要移动、覆盖或删除已经发布的 `R1` 到 `R6` tag、Release 和资产。
- 不要恢复正常更新的 `.old` rename 方案，不要绕过 transaction/token/health ACK。旧 release 清理只能在新版健康提交后针对严格规范名和更低版本执行，不得扩大为通配删除任意 EXE/`.old`。
- 不要改变 DualSense USB/BT 输入 offset、输出 report 长度、BT CRC、`0x36` 398 字节布局或左右通道映射，除非同时增加字节级测试与真实硬件验证。
- 不要在普通 state report 中恢复 `valid_flag0=0x20`、`valid_flag1=0x20`、已删除的 HID 音频模式 setter，或加入未经协议证明的单次 `0x01`“重置”。USB/BT 音频后端选择不拥有这些字段；任何新尝试必须先与 R6 字节逐项对照，并验证新版本退出后 R6 不受污染。
- 不要恢复 `dev is not None` 或 `persistent` 作为在线真值，不要给 GUI、拓扑或 XInput 增加第二个 HID reader。
- 不要让自动重连开关禁止同一手柄 USB/BT handover；不要把 Rescan 再次描述为真实重连。
- 不要在 Tk 窗口创建后设置 process DPI awareness，也不要同时手工缩放 CTk 已经缩放的 widget。
- 不要改变 Forza 遥测、trigger/haptics 算法或社区默认驾驶参数来掩盖连接、更新或 DPI 问题。
- 不要在推送前用本地旧 README 整体覆盖用户可能在 GitHub 提交的新文本；必须先 fetch 并逐段语义合并。

## 最近涉及的关键文件

- 启动与 DPI：`src/main.py`、`src/modules/dpi.py`、`packaging/windows/dpi_runtime_hook.py`、`packaging/windows/fhds.manifest`、`packaging/windows/fhds.spec`。
- 更新：`src/modules/update/install.py`、`src/modules/update/transaction.py`、`packaging/windows/update_helper.py`、`packaging/windows/shortcut_links.py`。
- 控制器与输入桥：`src/modules/dualsense/main.py`、`src/modules/dualsense/input_state.py`、`src/modules/dualsense/controller_state.py`、`src/modules/dualsense/topology.py`、`src/modules/dualsense/presentation.py`、`src/modules/dualsense/hidhide.py`、`src/modules/xinput/mapping.py`、`src/modules/xinput/report.py`、`src/modules/xinput/hot_switch.py`、`src/modules/xinput/bridge.py`、`src/modules/xinput/service.py`、`src/modules/forzahorizon/udp_listener.py`、`src/modules/runtime_logging.py`。
- 配置与界面：`src/modules/config/settings.py`、`src/modules/config/preferences.py`、`src/modules/config/profiles.py`、`src/modules/feedback_schema.py`、`src/modules/gui/controls_tab.py`、`src/modules/gui/settings_tab.py`、`src/modules/gui/system_tab.py`、`src/modules/gui/widgets.py`、`src/modules/tui/controls_tab.py`、`src/modules/tui/settings_tab.py`、`src/modules/tui/system_tab.py`、`src/lang/`。
- 触觉与诊断：`src/modules/haptics/lab.py`、`src/modules/haptics/audio.py`、`src/modules/haptics/bt_audio.py`、`src/modules/haptics/windows_endpoint.py`、`src/modules/haptics/manager.py`、`src/modules/haptics/lifecycle.py`、`src/modules/diagnostics.py`、`src/modules/dualsense/bt_haptics.py`、`src/modules/dualsense/main.py`、`src/modules/dualsense/_hidraw.py`、`src/modules/loop.py`、`src/modules/__init__.py`、`packaging/linux/build_elf.sh`。
- 红线：`src/modules/forzahorizon/redline.py`、`src/modules/loop.py`、`src/modules/forzahorizon/effects.py`、`src/modules/haptics/mixer.py`、`tests/forzahorizon/test_redline.py`。
- Xbox 安装发现：`src/modules/forzahorizon/game_launch.py`、`src/modules/forzahorizon/fh6_language.py`、`src/modules/gui/fh6_utilities_tab.py`、`src/modules/tui/fh6_utilities_tab.py`、`tests/forzahorizon/test_game_launch.py`、`tests/forzahorizon/test_fh6_language.py`。
- R8 扳机与 updater 修复：`src/modules/forzahorizon/effects.py`、`src/modules/config/settings.py`、`src/modules/feedback_schema.py`、`src/modules/__init__.py`、`src/modules/update/install.py`、`src/modules/update/transaction.py`、`tests/forzahorizon/test_effects.py`、`tests/test_backend_factory.py`、`tests/test_updater.py`、`AGENTS.md`、`docs/ARCHITECTURE.md`、`docs/DECISIONS.md`。
- 构建与测试：`packaging/windows/build_exe.bat`、`packaging/windows/fhds.spec`、`src/pyproject.toml`、`src/uv.lock`、`tests/test_update_*.py`、`tests/test_profile_persistence.py`、`tests/test_main_runtime.py`、`tests/test_tui_lifecycle.py`、`tests/haptics/test_audio.py`、`tests/haptics/test_windows_endpoint.py`、`tests/haptics/test_manager.py`、`tests/test_backend_factory.py`、`tests/dualsense/test_output_report.py`、`tests/dualsense/test_controller_runtime.py`、`tests/dualsense/test_controller_state.py`、`tests/dualsense/test_topology.py`、`tests/gui/test_header_status_frame.py`、`tests/test_dpi_contract.py`。

## 当前 Git 工作区状态

- PR 分支：`feat/r11-dualsense-enhanced`，基于 `origin/main` commit `398b85e`；GitHub PR [#5](https://github.com/piereacy/FH-DualSense-Enhanced/pull/5) 已创建，尚未合并。2026-08-24 已成功 fetch，远端没有新增 README 提交；现有 GitHub README 编辑意图已保留。分支内容包括 Xbox App 键鼠/手柄热切换、HidHide 1.7 session isolation、体感到摇杆、Haptics Lab、一键诊断包、新默认 Profile、调教鸣谢、翻译、发行文案与老三样更新；前台 ownership 实验已移出 `src` 并保存在 `experiments/foreground_ownership/`。版本为 R11，R10 tag 与线上发行资产保持不变，没有创建 R11 tag 或 Release。
- R10 tag、Release 正文和线上资产已固定。本轮发布后只读取 GitHub 元数据，没有下载资产或执行发布后测试。
- 本轮修改 README 前已 fetch 并确认远端没有新增提交；现有 GitHub 用户编辑意图已保留，新内容只补充 R11 的三份内置 Profile 与默认调教边界。
- `packaging/windows/build-*`、`dist-*`、`diagnostics-*` 和 `helper_work-*` 是本地隔离构建或诊断产物，不随源码提交；已知可用的 `dist-usb-audio-gate-1` 基线没有被覆盖。
- R8 tag 与 GitHub Release 已于 2026-07-30 发布；发布流水线和线上资产复核结果见下方。`packaging/windows/dist/` 的本地候选及其他隔离构建目录均被忽略，不进入提交；线上资产由干净 GitHub runner 独立构建。

## 已执行的测试和验证

- 2026-08-24 PR 收口复核：确认生产源码没有 Xbox One/Xbox Series、Share 系统键或前台 ownership detector 实现，旧 R10 监听备用包不进入当前 PR 或 R11 Release 正文；实验仅保留在无 package initializer 的 `experiments/foreground_ownership/`。本地构建/Helper 目录均由 `.gitignore` 排除，凭据模式扫描无命中。最终完整 `uv run --project src --frozen pytest -q -W error` 为 `925 passed in 9.98s`；Ruff 全仓库通过，Pyrefly 为 `0 errors`、`2 suppressed`、`144 warnings not shown`，限定源码与实验归档 compileall、`uv lock --check --project src`、新增 em dash 检查和 `git diff --check` 均通过。
- 2026-08-24 R11 新默认调教、三 Profile 迁移与鸣谢交付：`Settings` 出厂值已与用户配置 `33 + ABS` 的 136 个 Profile 字段语义对齐，相对旧默认共 70 项实质变化；内置顺序固定为 `Default`、`Default before R11`、`Original`，一次性迁移会保留升级前实际 `Default`，且不覆盖命名 Profile 或 active 命名选择。“关于与许可证”的 GUI/TUI 均新增 `Bilibili 开心散仙` 链接，URL 不包含消息末尾中文句号。最终完整 `uv run --project src --frozen pytest -q -W error` 为 `925 passed in 11.12s`；最终 Profile/About/发行契约定向回归为 `66 passed`；Ruff 全仓库通过，Pyrefly 为 `0 errors`、`2 suppressed`、`144 warnings not shown`，compileall、`uv lock --check --project src` 与 `git diff --check` 均通过。使用锁定 PyInstaller `6.16.0` 在 `packaging/windows/build-r11-default-abs-credit-review-1` / `dist-r11-default-abs-credit-review-1` 隔离构建；主 EXE 为 `52,368,594` 字节，SHA-256 `1f60d950ddc3fd195abebe031aa60ca6ac93420b2c65a1950a7855b31282e45b`。MZ、R11 File/ProductVersion、OriginalFilename、sidecar、`asInvoker` / `PerMonitorV2, PerMonitor` / `true/pm` manifest、About/Profile 模块与隐藏 `--help` 退出码 `0` 均通过；最终交付路径冒烟前后为零残留进程，配置哈希不变。递归归档检查确认 `modules.dualsense.passive_detection`、`foreground_ownership` 和 `experiments` 不在包内。最终 EXE/sidecar 已写入本地交付目录；其相邻配置已迁移为三份内置 Profile、active 为新 `Default`，迁移前原文件按字节备份为 `data/user_preferences.before-r11-default-20260824.json`。未正常启动 GUI、连接真实 DualSense、运行游戏、操作 HidHide、执行真实线上更新、提交、推送、tag 或发布。
- 2026-08-21 最终文档落盘后再次执行完整 `uv run --project src --frozen pytest -q -W error`：`922 passed in 16.82s`；下条记录中的 `14.57s` 是同一撤包状态在构建前已经通过的另一轮完整回归，不是旧 972 项前台实验套件。
- 2026-08-21 R11 前台检测撤包、实验隔离与最终本地构建：按用户最终边界从生产源码移除 Win32 exact-foreground detector、physical-HID runtime ownership gate、`ControllerPhase.AVAILABLE`、`WAITING_GAME`、runtime tick、延迟 backend/pulse 与对应 GUI/TUI/headless 接线；完整实现和原回归测试保存在无 `__init__.py` 的 `experiments/foreground_ownership/`，不由生产源码导入。Haptics Lab 保持“系统与更新”内默认折叠卡片，有效遥测会抢占预览。最终完整 `uv run --project src --frozen pytest -q -W error` 为 `922 passed in 14.57s`；Ruff 全仓库通过，Pyrefly 为 `0 errors`、`2 suppressed`、`144 warnings not shown`，compileall（含实验归档）、`uv lock --check --project src` 与 `git diff --check` 均通过。使用锁定 PyInstaller `6.16.0` 在全新隔离目录 `packaging/windows/dist-r11-foreground-isolated-review-1` / `build-r11-foreground-isolated-review-1` 构建；主 EXE 为 `52,364,327` 字节（约 `49.938 MiB`），SHA-256 `21c0ad0c8f26004260fa2b6a21addb542269e57ac9ddc43fe9830c4e0687f499`。MZ、R11 File/ProductVersion、OriginalFilename、sidecar、`asInvoker` / `PerMonitorV2, PerMonitor` / `true/pm` manifest、更新助手和 ViGEm 资产、隐藏 `--help` 退出码 `0` 与零残留进程均通过；对实际 EXE 递归归档检查确认 diagnostics、Haptics Lab、motion、gyro、hot-switch 与 HidHide 在包内，同时 `modules.dualsense.passive_detection`、`foreground_ownership` 和 `experiments` 均不在包内。最终 EXE/sidecar 已写入本地交付目录；旧 R10 备用 EXE 保持 `52,359,098` 字节和 SHA-256 `16e37d04ec4344fa67eec3df91d3fd31c742b263f56d6fffe7c86b0e37bb8a3d`，没有重建或覆盖。未正常启动 GUI、连接真实 DualSense、运行游戏、操作 HidHide、执行真实升级、提交、推送、tag 或发布。
- 2026-08-20 Haptics Lab 系统页收口与旧 R10 listener 备用交付：GUI 左侧 `Lab` 导航和 TUI 顶层 `tab-haptics-lab` 已移除，原有场景与安全逻辑改由“系统与更新”页内的 `HapticsLabCard` / `HapticsLabPanel` 承载；GUI 初始 `_expanded = False`，TUI `Collapsible(collapsed=True)`，折叠卡片、离开系统页和窗口失焦都会撤销预览 runtime lease。实际 Textual 挂载验证发现并修复了面板卸载期间子控件已移除导致的 `NoMatches` 生命周期回归，最终完整 `uv run --project src --frozen pytest -p no:cacheprovider -q -W error` 为 `972 passed in 13.40s`；Ruff 全仓库通过，Pyrefly 为 `0 errors`、`2 suppressed`、`167 warnings not shown`，限定源码 `compileall`、`uv lock --check --project src` 与 `git diff --check` 均通过。使用锁定 PyInstaller `6.16.0` 在全新隔离目录 `packaging/windows/dist-r11-system-lab-card-review-2` / `build-r11-system-lab-card-review-2` 构建；新 R11 主 EXE 为 `52,395,989` 字节（`49.969 MiB`），SHA-256 `db9788668ffe2b61a46ddce2d03a215c07399842e5179f967be9b3b006f4dcc9`，相对上一 R11 候选增加 `1,764` 字节，相对线上 R10 增加 `441,735` 字节（约 `0.421 MiB`、`0.8502%`），低于体积确认门槛。MZ、R11 File/ProductVersion、OriginalFilename、sidecar、`asInvoker` / `PerMonitorV2, PerMonitor` / `true/pm` manifest、GUI/TUI Lab/System 模块与 diagnostics/passive detection/gyro/hot-switch/HidHide 模块、内嵌 Helper `8,880,951` 字节及 SHA-256 `bffa8a3f9acf82f29e88df485c63674f188db783b88484ca55290d509a34af9c`、隐藏 `--help` 退出码 `0` 和前后零残留进程均通过。旧 R10 `dist-r10-physical-hid-release-review-2` 则按原字节复制为独立备用：`52,359,098` 字节、SHA-256 `16e37d04ec4344fa67eec3df91d3fd31c742b263f56d6fffe7c86b0e37bb8a3d`，MZ、R10 File/ProductVersion、OriginalFilename、sidecar 与隐藏 `--help` 退出码 `0` 重新核对通过；没有把它重新编译、混入或替换 R11 源码。两份包都没有正常启动 GUI、连接真实 DualSense、运行 FH4/FH5/FH6 或其他游戏、操作 HidHide 或执行真实更新事务，因此卡片视觉、Alt+Tab 实际 HID 释放时延和硬件手感仍待用户实机确认。
- 2026-08-20 本地 R11 构建：先 fetch 并确认 `main` 与 `origin/main` 均为 `398b85e`、ahead/behind `0/0`，远端没有新增 README 提交；随后把内部版本与锁文件从 `10` 递增为 `11`，同步双语 R11 Release 契约和三语 README 体感说明。主要新增链路定向回归为 `227 passed in 4.62s`，最终完整 `uv run --project src --frozen pytest -q -W error` 为 `970 passed in 14.33s`；Ruff 全仓库通过，Pyrefly 为 `0 errors`、`2 suppressed`、`166 warnings not shown`，限定源码 `compileall`、`uv lock --check --project src` 与 `git diff --check` 均通过。使用锁定 PyInstaller `6.16.0` 在全新隔离目录 `packaging/windows/dist-r11-local-review-1` / `build-r11-local-review-1` 构建，未覆盖标准 `dist`、旧候选或用户配置。`FH-DualSense-Enhanced-R11.exe` 为 `52,394,225` 字节（`49.967 MiB`），SHA-256 `c6b26f6c2352b78cb6571de06acc2c09ba15c597cfd9e724ce579ecc3f43f4ed`；相对线上 R10 `51,954,254` 字节增加 `439,971` 字节（约 `0.420 MiB`、`0.8468%`），低于体积确认门槛，相对同源码上一 R10 陀螺仪候选减少 `166` 字节。updater 源码未变，主包继续嵌入已验证 Helper `8,880,951` 字节、SHA-256 `bffa8a3f9acf82f29e88df485c63674f188db783b88484ca55290d509a34af9c`。MZ、R11 File/ProductVersion、OriginalFilename、sidecar `--check`、`asInvoker` / `PerMonitorV2, PerMonitor` / `true/pm` manifest、从 PE 提取的 32 px 图标与源 ICO 对应帧逐像素一致、diagnostics/Haptics Lab/motion/passive detection/gyro/hot-switch/HidHide 模块、Helper/ViGEm/MOD/许可资产、隐藏 `--help` 退出码 `0` 与前后零残留进程均通过。没有正常启动 GUI、连接真实 DualSense、运行 Forza/崩坏：星穹铁道、操作 HidHide、执行真实 R10 → R11 更新、提交/推送/tag 或发布；因此线上重新下载校验、完整 GUI/滚轮/退出提示/更新入口和真实硬件手感仍未执行。
- 2026-08-12 Bluetooth 关机误报修正：用户在 DualSense 已断联时指出界面仍显示“已检测到手柄”。现场复现确认 Configuration Manager 仍返回 2 个 `Present=True` 的 paired BTHENUM 服务节点，旧 `review-1` 因而错误聚合为 1 只控制器。当前实现保留无 HID handle 边界，但把 Bluetooth PnP MAC 与 Classic Bluetooth API connected-only 枚举相交；同一断联现场现为 `matching_pnp_records=2`、`connected_bluetooth=0`、`reported_controllers=0`。新增 remembered-node 断联、connected 恢复与 API flags/close 回归后，定向测试为 `56 passed`，完整回归为 `945 passed in 12.73s`；Ruff、Pyrefly `0 errors`、限定源码 `compileall`、锁文件与 `git diff --check` 均通过。新隔离候选位于 `dist-r10-physical-hid-release-review-2`，主 EXE 为 `52,359,098` 字节、SHA-256 `16e37d04ec4344fa67eec3df91d3fd31c742b263f56d6fffe7c86b0e37bb8a3d`；MZ、R10 版本资源、sidecar 与隐藏 `--help` 零残留进程通过。`review-1` 已被替代，不应继续测试。
- 2026-08-12 非地平线 physical HID 释放：旧 `dist-r10-project-fixes-review-2` 已由用户真实崩铁现场判定失败；Steam 模式、HidHide 关闭/未安装时，它仍在 `StarRail.exe` 场景记录 `DualSense HID opened (BT, pid=0x0ce6)`。当前源码改为 native worker 初始 gate 关闭、Windows 等待期只查询 Configuration Manager present-PnP、Forza/Lab lease 才允许 hidapi，以及慢 `open_path()`/handover 返回后的二次 gate 校验。定向回归为 `141 passed in 2.80s`，最终完整 `uv run --project src --frozen pytest -q -W error` 为 `942 passed in 15.18s`；Ruff 全仓库通过；Pyrefly 为 `0 errors`、`2 suppressed`、`161 warnings not shown`；限定源码 `compileall`、`uv lock --check --project src` 与 `git diff --check` 均通过。当前 Windows 只读 PnP 探针得到 2 个匹配节点并保守聚合为 1 只控制器，没有输出设备标识。使用锁定 PyInstaller `6.16.0` 在新目录 `packaging/windows/dist-r10-physical-hid-release-review-1` / `build-r10-physical-hid-release-review-1` 构建，未覆盖旧候选或标准 `dist`；主 EXE 为 `52,356,835` 字节（`49.931 MiB`），SHA-256 `20b992df705496646ac3405eeb45398ed2cb39a2910b201950d3cfeeef5786f8`，相对失败的 `review-2` 增加 `11,916` 字节（`0.0228%`）。updater 源码未变，继续嵌入已验证 Helper `8,880,951` 字节、SHA-256 `bffa8a3f9acf82f29e88df485c63674f188db783b88484ca55290d509a34af9c`。MZ、R10 File/ProductVersion、OriginalFilename、sidecar `--check`、`asInvoker` / `PerMonitorV2, PerMonitor` / `true/pm` manifest、关键模块分析、Helper/ViGEm 资产、隐藏 `--help` 退出码 `0` 与零残留新候选进程均通过。为避免干扰用户正在运行的旧 FHDS 与崩铁，本轮没有正常启动新 GUI、打开物理 HID、关闭旧进程或执行游戏联动，因此真实问题是否解决仍以用户测试新候选为准。
- 2026-08-10 项目级修复收口：精确前台 gate 与耗时 child lifecycle 解耦、会话 generation 失效、ViGEm 超时后单 successor 恢复、Raw Input 慢启动取消、HidHide ready/cleanup 重试、UDP 有界 drain/自转发保护、USB audio 单一生命周期所有权、诊断包标识脱敏及六种非英语说明均已合并验证。最终完整 `uv run --project src --frozen pytest -q -W error` 为 `915 passed in 10.93s`；`ruff check src tests packaging .github` 通过；Pyrefly 为 `0 errors`、`2 suppressed`、`154 warnings not shown`；限定源码 `compileall`、`uv lock --check --project src` 与 `git diff --check` 均通过。使用锁定 PyInstaller `6.16.0` 在新目录 `packaging/windows/dist-r10-project-fixes-review-2` / `build-r10-project-fixes-review-2` 隔离构建，未覆盖标准 `dist` 或已有基准；主 EXE 为 `52,344,919` 字节（`49.920 MiB`），SHA-256 `b7109d2c7e677ca23510091944beb0fbf9060798e84778d8c205c9d0d09bab58`，相对上一 Haptics Lab 审阅包增加 `22,905` 字节（`0.0438%`），相对线上 R10 增加 `390,665` 字节（`0.7519%`）。updater 源码未变，继续复用已验证 Helper：`8,880,951` 字节、SHA-256 `bffa8a3f9acf82f29e88df485c63674f188db783b88484ca55290d509a34af9c`。MZ、R10 版本资源、sidecar `--check`、内嵌 `asInvoker` / `PerMonitorV2, PerMonitor` / `true/pm` manifest、diagnostics/HidHide/haptics/XInput 模块、Helper/ViGEm 资产、隐藏窗口 `--help` 退出码 `0` 与退出后零残留进程均通过。Windows Raw Input listener 另连续实跑 5 次 start/stop，最终无残留线程；仍未连接真实 DualSense、运行 Forza 或崩坏：星穹铁道，也未操作真实 HidHide 配置和 Steam Input，因此游戏内鼠标释放及振动手感必须继续由实机验收。
- 2026-08-09 Haptics Lab 与一键诊断包：Lab renderer、边界/到期/抢占/断连、DSX 场景能力、loop 单一输出所有权、HapticManager/lifecycle、诊断隐私与 ZIP/日志轮转、UDP/HID/DSX 计数器、GUI/TUI 接线和语言的较宽定向回归为 `245 passed in 2.24s`；最终完整 `pytest -p no:cacheprovider -q -W error` 为 `884 passed in 10.22s`。Ruff 全仓库通过；Pyrefly 为 `0 errors`、`2 suppressed`、`136 warnings not shown`；限定源码 `compileall`、`uv lock --check --project src` 与 `git diff --check` 通过。使用锁定 PyInstaller `6.16.0` 在新目录 `packaging/windows/dist-r10-haptics-lab-review-2` / `build-r10-haptics-lab-review-2` 构建，未覆盖标准 `dist`、中间 `review-1` 或前三个 foreground gate 审阅包；主 EXE 为 `52,322,014` 字节，SHA-256 `65d5ec6bf39999808a9027851a8118fb595a9fa0452ca0843118501a2af61bf3`。相对上一 foreground gate 审阅包增加 `63,496` 字节（约 `0.0606 MiB`、`0.1215%`），相对线上 R10 增加 `367,760` 字节（约 `0.3507 MiB`、`0.7079%`），低于体积确认门槛。updater 源码未变，冻结包复用前一轮已验证的 Helper：`8,880,951` 字节、SHA-256 `bffa8a3f9acf82f29e88df485c63674f188db783b88484ca55290d509a34af9c`。MZ、R10 版本资源、sidecar `--check`、`asInvoker` 与 `PerMonitorV2, PerMonitor` manifest、Lab/diagnostics 模块、Helper/ViGEm 资产、隐藏 `--help` 退出码 `0` 和零残留进程均通过。没有启动 GUI、连接手柄、运行 Forza、改变 HidHide 或记录游戏内振动/Steam Input，因此这些不属于已验证事实。
- 2026-08-09 前台输出与物理检测解耦修正：读取用户实际启动 `dist-r10-foreground-gate-review-2` 后生成的 `data/runtime.log`，确认 Steam 模式、HidHide 关闭时旧审阅版只启动 UDP，没有进入 DualSense open/enumerate；由此把根因定位为 service 错误关闭 backend，而不是手柄或 Steam。main、GUI、TUI 现先打开 backend，前台 gate 只管理遥测反馈、触觉流和 Xbox 子链路；启动脉冲延迟到首次 gate 打开，失去前台时 haptics manager 可暂停并在恢复后重用。相关定向回归为 `114 passed in 0.87s`，最终完整 `pytest -p no:cacheprovider -q -W error` 为 `867 passed in 9.28s`；Ruff 全仓库通过，Pyrefly 为 `0 errors`、`2 suppressed`、`121 warnings not shown`，限定源码 `compileall`、`uv lock --check --project src` 与 `git diff --check` 通过。使用锁定 PyInstaller `6.16.0` 构建新的隔离审阅目录 `dist-r10-foreground-gate-review-3` / `build-r10-foreground-gate-review-3`；主 EXE 为 `52,258,518` 字节，SHA-256 `981e27389f05a312f7aa31e03479fe08130e0465c228922101be5b0e93e55718`，相对线上 R10 增加 `304,264` 字节（约 `0.290 MiB`、`0.5856%`），低于体积确认门槛。Helper 仍为 `8,880,951` 字节、SHA-256 `bffa8a3f9acf82f29e88df485c63674f188db783b88484ca55290d509a34af9c`；MZ、R10 版本资源、sidecar `--check`、manifest、关键模块与 Helper/ViGEm 资产、`--help` 退出码 `0` 和零残留进程均通过。隐藏 GUI 烟测日志已出现 reconnect mode、HID enumerate 与等待手柄，证明不在地平线前台时 physical worker 确实启动，不再只有 UDP；该次现场 Windows PnP 与 hidapi 均报告 `0` 个当前可见 DualSense，因此尚不能把“真实已连接手柄已显示”写成已验证。
- 2026-08-09 Windows 精确前台完整 controller-session gate（已被上方检测/输出解耦修正替代）：Win32 前台 PID、三代固定 basename、地平线后台但 `StarRail.exe` 前台、焦点切换 PID 消失、查询异常 fail closed、Steam/Xbox/DSX 完整 session 生命周期、GUI/TUI/headless runtime tick 与六种非英语状态文案的定向回归为 `99 passed in 4.54s`；最终完整 `pytest -p no:cacheprovider -q -W error` 为 `861 passed in 9.95s`。Ruff 全仓库通过；Pyrefly 为 `0 errors`、`2 suppressed`、`120 warnings not shown`；168 个 tracked Python 文件无落盘语法解析、`uv lock --check --project src` 与 `git diff --check` 通过。本机只读 Win32 探针取得非地平线前台 `crossfire.exe` 并返回 `supported_forza_foreground=False`，证明真实 API/进程名路径可用但不等同于 Forza/崩铁联动验收。使用锁定 PyInstaller `6.16.0` 在新目录 `packaging/windows/dist-r10-foreground-gate-review-2` / `build-r10-foreground-gate-review-2` 构建，未覆盖标准 `dist`；`FH-DualSense-Enhanced-R10.exe` 为 `52,122,191` 字节，SHA-256 `80b65059599e952572b709520e5f05bc49e4194fcef6176860ca06b8a1b782fb`，相对线上 R10 `51,954,254` 字节增加 `167,937` 字节（约 `0.160 MiB`、`0.3232%`），低于体积确认门槛。Helper 为 `8,880,951` 字节、SHA-256 `bffa8a3f9acf82f29e88df485c63674f188db783b88484ca55290d509a34af9c`；MZ、`FileVersion/ProductVersion=R10`、`OriginalFilename`、sidecar `--check`、内嵌 `PerMonitorV2, PerMonitor` / `true/pm` / `asInvoker`、前台检测与 service 模块、Helper/ViGEm 资产以及隐藏窗口 `--help` 退出码 `0`、退出后零残留进程均通过。该产物只是未提交工作树的本地审阅包，未启动 GUI、未连接手柄、未修改 HidHide，也未提交、推送或发布。
- 2026-08-09 中间版全模式 process gate（已由同日精确前台 gate 替代）：Steam、Xbox App、DSX backend 延迟打开/退出关闭、Xbox bridge/Raw Input/HidHide 边界、等待期 UDP 丢弃、退出单次静音、USB audio eligibility、GUI/TUI/headless 接线与状态翻译的定向回归为 `60 passed in 2.32s`；补入失败打开后的强制关闭后，最终完整 `pytest -p no:cacheprovider -q -W error` 为 `855 passed in 16.78s`。Ruff 全仓库通过；Pyrefly 指定项目 Python 后为 `0 errors`、`2 suppressed`、`116 warnings not shown`；168 个 tracked Python 文件无落盘语法解析、`uv lock --check --project src` 与 `git diff --check` 通过。本机只读严格进程扫描返回 `supported_forza_running=False`。该版尚未构建或实机验证，且“进程存在即可打开”语义不满足切到其他游戏后立即释放的现场要求，因此不再是当前实现。
- 2026-08-07 FH4/FH5/FH6 进程 gate：单次精确多 EXE 扫描、无游戏等待、游戏出现后整套虚拟输入启动、退出后 consumer/target/Raw Input/HidHide 清理、扫描异常 fail closed、500 ms 节流、GUI/TUI/headless runtime tick、状态与六种非英语翻译的较宽定向回归为 `366 passed in 4.52s`；最终完整 `pytest -p no:cacheprovider -q` 为 `851 passed in 13.75s`。Ruff 全仓库通过；Pyrefly 指定项目 Python 后为 `0 errors`、`2 suppressed`、`115 warnings not shown`；171 个 Python 文件无落盘语法解析、`uv lock --check --project src` 与 `git diff --check` 通过。本机严格真实进程扫描返回 `supported_forza_running=False`，与未运行地平线的当前环境一致；未创建虚拟 target、未连接手柄、未打开 HidHide control device，也未构建冻结 EXE 或执行崩坏：星穹铁道/真实 Xbox App Forza 联动验收。
- 2026-08-07 HidHide 1.7 物理 DualSense 会话隔离：IOCTL/MULTI_SZ、规则 ownership 与版本路径迁移、active/permanent/inverse 安全边界、session-only hide/clear、失败清理重试、连接前 observer、快速开关串行化、service mode gate、global 持久化和 GUI/TUI 翻译定向回归为 `105 passed in 1.63s`；最终完整 `pytest -p no:cacheprovider -q -W error` 为 `845 passed in 13.23s`。Ruff 全仓库通过；Pyrefly 指定项目 Python 后为 `0 errors`、`2 suppressed`、`112 warnings not shown`；171 个限定 Python 文件的无落盘语法编译、`uv lock --check --project src` 与 `git diff --check` 通过。当前 Windows 实际调用 `GetFinalPathNameByHandleW(..., VOLUME_NAME_NT)` 得到 `\Device\HarddiskVolume2\...\python.exe` 形式，证明 NT full image resolver 可用；只读检查未发现 HidHide service 或默认 CLI，因此没有打开真实 control device、修改本机 HidHide 配置或执行真实 DualSense/崩坏：星穹铁道验收。未构建冻结 EXE。
- 2026-08-07 Xbox App 输入热切换：Raw Input、bridge、service、GUI/TUI 状态和翻译定向回归为 `52 passed in 1.78s`；最终完整 `pytest -p no:cacheprovider -q -W error` 为 `815 passed in 11.24s`。Ruff 全仓库通过；Pyrefly 指定项目 Python 后为 `0 errors`、`2 suppressed`、`103 warnings not shown`；103 个限定源码文件的无落盘语法编译、`uv lock --check --project src` 与 `git diff --check` 通过。Windows 本机探针确认 listener 可注册、接收 `WM_INPUT` 并停止，连续 20 次启动/停止后残留 `fhds-raw-input` 线程数为 `0`。实现前曾以 50 ms 采样 Windows session last-input tick，两秒内 40 次采样出现 37 次变化，因此拒绝该分类器并改用 keyboard/mouse Raw Input。监听异常的自动测试还确认 bridge 只记录一次并保持 controller fail open。未构建冻结 EXE，也未执行真实 DualSense、崩坏：星穹铁道或 Xbox App Forza 游戏内验收。
- 2026-08-04 R10 正式 Release：PR #3 以 squash merge commit `08c5302` 合并，tag `R10` 指向同一 commit。工作流 `30905749789` 的 prepare、ZUV、Linux ELF、Windows EXE 和 combined release 五个 job 全部成功；只有依赖 action 的 Node.js 20 弃用提示，没有构建错误。GitHub 元数据显示 Release 为非草稿、非预发布，共 8 个资产：Windows EXE `FH-DualSense-Enhanced-R10.exe` 为 `51,954,254` 字节、digest `4190a67b425df7980e9ff08e5f11a8a8e13af5e2494f7a11b2c55a4afb5bf2d5`，Linux ELF 为 `47,416,848` 字节，ZUV 为 `7,446,733` 字节。最终 Release 正文不含用户要求删除的 TCR/抓地力独立说明和 R7/R8 手动下载安装提醒。本轮只读取 GitHub 元数据，没有下载线上资产，也没有执行发布后测试。
- 2026-08-04 R10 版本递增与 Windows 审阅构建：版本、扳机、Profile 和发行契约定向回归为 `121 passed in 13.48s`。第一次完整回归发现 pending-update 测试把 R10 写死为“未来版本”；夹具改为动态 `current + 1` 后，最终完整 `uv run --project src --frozen pytest -q -W error` 为 `806 passed in 23.34s`。Ruff 全仓库通过，Pyrefly 为 `0 errors`、`2 suppressed`、`101 warnings not shown`，限定源码 `compileall`、`uv lock --check --project src` 与 `git diff --check` 均通过。使用锁定 PyInstaller `6.16.0` 在全新隔离目录 `packaging/windows/dist-r10-throttle-wall-review-1` / `build-r10-throttle-wall-review-1` 构建，未覆盖标准 `dist`；updater 源码没有改动，因此审阅包复用当前已验证的 `8,880,264` 字节 Update Helper。`FH-DualSense-Enhanced-R10.exe` 为 `52,202,312` 字节（`49.784 MiB`），SHA-256 `dbec98fd0da36fbe7f65cb1bd18c6a1f3e2a15dfffa65eb1bf716444d8d4f676`；相对线上 R9 增加 `245,922` 字节（约 `0.235 MiB`、`0.4733%`），低于体积确认门槛。MZ、`FileVersion/ProductVersion=R10`、`OriginalFilename=FH-DualSense-Enhanced-R10.exe`、sidecar `--check`、内嵌 `PerMonitorV2, PerMonitor` / `true/pm` / `asInvoker`、归档中的 R10 配置/扳机模块与既有 Helper/ViGEm/图标/许可资产、隐藏窗口 `--help` 退出码 `0` 和退出后零残留进程均通过。未执行真实 DualSense/Forza 手感测试；该审阅阶段尚未提交、推送、发布或下载线上资产。
- 2026-08-02 post-R9 油门末端硬墙拆分：扳机算法、共享 GUI/TUI schema、六种非英语翻译、Profile 回填与社区默认值定向回归为 `108 passed in 1.70s`；最终完整 `uv run --project src --frozen pytest -q -W error` 为 `806 passed in 12.53s`。Ruff 全仓库通过，Pyrefly 为 `0 errors`、`2 suppressed`、`101 warnings not shown`，限定源码 `compileall`、`uv lock --check --project src` 与 `git diff --check` 均通过。未构建 EXE，也未执行真实 DualSense/Forza 手感测试。
- 2026-08-01 当前 R9 自定义 XBOX 按键映射审阅构建：最终完整 `uv run --project src --frozen pytest -q -W error` 为 `801 passed in 12.34s`；Ruff 全仓库通过，Pyrefly 为 `0 errors`、`2 suppressed`、`101 warnings not shown`，限定源码 `compileall`、`uv lock --check --project src` 与 `git diff --check` 均通过。GUI 隐藏挂载和 Textual 实际挂载均确认独立页面直接包含 17 个来源，Steam 模式锁定、Xbox App 加自定义开关后恢复编辑，并显示 Steam 用户应在 Steam 内修改映射的完整说明；最终审阅还清除了 TUI System 页对已迁出映射同步方法的残留调用，并用结构契约禁止映射逻辑回流 System 页。使用锁定 PyInstaller `6.16.0` 在全新隔离目录 `packaging/windows/dist-r9-custom-xbox-mapping-review-1` / `build-r9-custom-xbox-mapping-review-1` 重新构建，未覆盖标准 `dist`，也未停止桌面正在运行的旧实例。最终 `FH-DualSense-Enhanced-R9.exe` 为 `52,203,303` 字节（`49.785 MiB`），SHA-256 `056fed44a34c868c489f184e4d10a60b21217a7fd2c5384072db82be1eea959e`；相对线上 R8 增加 `412,876` 字节（约 `0.394 MiB`、`0.7972%`），低于体积确认门槛。MZ、`FileVersion/ProductVersion=R9`、`OriginalFilename=FH-DualSense-Enhanced-R9.exe`、sidecar `--check`、嵌入 `PerMonitorV2, PerMonitor` / `true/pm` / `asInvoker`、隐藏窗口 `--help` 退出码 `0` 和退出后零残留进程均通过。归档确认携带新 GUI/TUI 映射模块、映射 schema、`8,880,264` 字节的 Update Helper、ViGEmClient、ViGEmBus、ControllerIcons、LICENSE 与第三方声明。真实 Xbox App 游戏内映射和物理 DualSense 验收尚未执行；候选源码已提交到草稿 PR #1，本地 EXE 与正式 R9 Release 资产尚未发布。
- 2026-08-02 R9 正式 Release：工作流 `30709569218` 的 prepare、Windows EXE、ZUV、Linux ELF 和 combined release 五个 job 全部成功。GitHub 元数据显示正式 Windows 资产 `FH-DualSense-Enhanced-R9.exe` 为 `51,956,390` 字节，Release 为非草稿、非预发布；本轮没有下载线上资产，也没有执行发布后测试。
- 2026-08-01 当前 R8 源码审阅构建：使用锁定的 PyInstaller `6.16.0` 和新隔离目录 `packaging/windows/dist-r8-xbox-mapping-review-1` / `build-r8-xbox-mapping-review-1` 构建，未覆盖标准 `dist`，也未停止桌面正在运行的旧实例。`FH-DualSense-Enhanced-R8.exe` 为 `52,199,009` 字节（`49.781 MiB`），SHA-256 `d452d41b759a90b67bc414753f4d34b799ce092b928bd82a8891b0b612544076`；相对线上 R8 增加 `408,582` 字节（约 `0.390 MiB`、`0.7889%`），低于体积确认门槛。MZ、`FileVersion/ProductVersion=R8`、`OriginalFilename=FH-DualSense-Enhanced-R8.exe`、sidecar `--check`、嵌入 `PerMonitorV2, PerMonitor` / `true/pm` / `asInvoker` 和隐藏窗口 `--help` 退出码 `0` 均通过。归档内的 Update Helper 为本轮重建的 `8,881,321` 字节文件，并确认同时携带 ViGEmClient、ViGEmBus、ControllerIcons、LICENSE 与第三方声明。该产物仅供当前界面和功能审阅；因为项目版本尚未递增，它不是可发布的 R9 候选，也未执行真实 DualSense/Forza 验收。
- 2026-08-01 实验性 Xbox 数字按键映射与用户入口收口：共享 schema、XUSB 映射、bridge 热更新、service、global 持久化、恢复出厂、Xbox App 编辑 gate、更新 EXE 手动下载直链、关于页项目仓库入口、GUI/TUI 接线和六种非英语 catalog 契约均已回归；保持按键时切换映射会重发 latest state 且不重建 target。最终完整 `uv run --project src --frozen pytest -q -W error` 为 `799 passed in 15.62s`。隐藏 GUI 与 Textual 实际挂载确认 Steam 锁定、Xbox App 恢复编辑、活动 Release 显示完整 EXE URL 且无活动更新后隐藏。Ruff 全仓库、Pyrefly（`0 errors`、`2 suppressed`、`101 warnings not shown`）、compileall、`uv lock --check --project src` 与 `git diff --check` 均通过；真实 Xbox App 游戏内映射尚未执行。
- 2026-08-01 Steam 式触摸板左右点击映射：DualSense USB/BT 输入、XUSB report、bridge 与 service 定向回归为 `120 passed in 0.44s`；完整 `uv run --project src --frozen pytest -q -W error` 为 `785 passed in 11.41s`。Ruff 全仓库、Pyrefly（`0 errors`、`2 suppressed`、`101 warnings not shown`）、compileall 与 `uv lock --check --project src` 均通过。测试固定 click 位、两种 transport、`959/960` 中线边界、无触点 Back/View 回退、双触点双键、无 click 不发布区域，以及 Create/Options 既有输出保持；真实 DualSense 和 Xbox App 游戏内操作未执行。
- 2026-08-01 自动更新完整复审：更新器、transaction、启动恢复、快捷方式与运行时定向套件为 `110 passed in 4.25s`，新增覆盖预存目标不误删、changed target fail-closed、move → journal 窄窗口、legacy 备份恢复、回滚删除失败保留非终态、跨进程锁、恢复 ACK 死进程、pending 重载、严格 sidecar、调度失败重试和 GUI/TUI UDP 健康边界。最终完整 `uv run --project src --frozen pytest -q -W error` 为 `766 passed in 11.36s`；Ruff 全仓库、Pyrefly（`0 errors`、`2 suppressed`、`101 warnings not shown`）、compileall、`uv lock --check --project src` 与 `git diff --check` 全部通过。
- 2026-08-01 隔离冻结事务矩阵：从当前工作树复制 259 个 tracked 文件到 `%LOCALAPPDATA%\Temp\fhds-updater-e2e-20260801-1`，仅在隔离副本加入一次性测试入口并构建合成 R9/R10，未修改仓库版本号或桌面安装。单实例 R9 → R10 得到 `committed`，真实 R10 外层/内层 PID `8872/27420` 存活，R7/R8/R9 与严格 R8 `.old/.sha256` 被删除，`Other.exe`/`notes.old` 保留；另一个稳定 R9 进程对 `35372/46588` 存在时，第二次启动在创建 journal 前被拒绝（transaction 数 `0`）。R10 启动即退得到 `rolled_back`、新版删除、R9 重启且 R8/`.old` 保留。R10 inner 挂起不 ACK 时实际观测 PID `14404/51156`，30 秒超时后两者均被 Helper 终止，R10 文件删除并以 R9 PID `15288/46716` 重启。人为制造 `waiting_health` orphan journal 后，R10 无内部启动参数自行接管，ACK 到 `committed` 用时 `4.182s`，证明恢复路径重新观察约 3 秒。矩阵结束后隔离 case 下剩余 FHDS 进程数为 `0`。测试 Helper 为 `8,881,446` 字节，含一次性测试入口的 R9 probe 为 `52,052,832` 字节；二者不是正式发布候选。
- 2026-07-30 one-file 实例误判修复：现场确认桌面内层 PID `24424` 的直接父 PID 为 `45212`，二者指向完全相同的 `C:\Users\Administrator\Desktop\FH-DualSense-Enhanced-R5.exe`；此前失败日志中的 `44148`、`44584`、`45212` 都是同类外层 bootloader。修复后以当前活跃拓扑调用实例保护返回 `()`。updater 套件为 `38 passed in 3.74s`，父子实例/独立实例定向回归为 `3 passed`；完整 `uv run --project src --frozen pytest -q -W error` 为 `744 passed in 11.11s`。补写老三样与项目状态后，updater/发行契约联合回归为 `60 passed in 6.41s`。Ruff 全仓库、Pyrefly（`0 errors`、`2 suppressed`、`101 warnings not shown`）、`uv lock --check --project src` 和 `git diff --check` 均通过。
- 2026-07-30 one-file 父进程修复候选：`packaging/windows/dist-r8-updater-parent-fix-1/FH-DualSense-Enhanced-R8.exe` 为 `52,036,443` 字节（`49.626 MiB`），SHA-256 `7848049978005eb8ce52c36acb5917ff5597c144c8cbd8bfb74dc838326a6122`。MZ 为 `4D 5A`，`FileVersion/ProductVersion=R8`、`OriginalFilename=FH-DualSense-Enhanced-R8.exe`、sidecar `--check`、`PerMonitorV2, PerMonitor`、`true/pm`、`asInvoker` 和 `--help` 退出码 `0` 均通过。构建使用隔离 `dist-r8-updater-parent-fix-1` / `build-r8-updater-parent-fix-1`，没有覆盖标准 `dist`，也没有停止或修改桌面运行中的 R7；真实手动安装和后续在线更新仍未执行。
- 2026-07-30 R8 正式发布与线上复核：commit/tag 为 `d810c11` / `R8`，GitHub Actions run [`30541439716`](https://github.com/piereacy/FH-DualSense-Enhanced/actions/runs/30541439716) 的 `prepare`、ZUV、Windows EXE、Linux ELF 与合并 Release 五个 job 全部成功；只有依赖 action 的 Node.js 20 弃用提示，没有构建错误。Release 为非 draft、非 prerelease，共 8 个资产。重新下载的线上 `FH-DualSense-Enhanced-R8.exe` 为 `51,790,427` 字节（`49.391 MiB`），SHA-256 `897b828a2be63775960941e8610f39733dfb186e021418461711843ac50378a9`，与 Release digest 和线上 `.sha256` 一致；MZ、`FileVersion/ProductVersion=R8`、`OriginalFilename=FH-DualSense-Enhanced-R8.exe`、`PerMonitorV2, PerMonitor`、`true/pm`、`asInvoker` 与隐藏窗口 `--help` 退出码 `0` 均通过。线上 Linux ELF 为 `47,389,864` 字节，ZUV 为 `7,437,547` 字节。
- 2026-07-30 R8 最终本地 Windows 候选：`packaging/windows/dist/FH-DualSense-Enhanced-R8.exe` 为 `52,035,627` 字节（`49.625 MiB`），SHA-256 `239660997abd709207895826e2c6cf16d3ebd6478eca69a2f34607642a330d12`。MZ 为 `4D 5A`，`FileVersion/ProductVersion=R8`、`OriginalFilename=FH-DualSense-Enhanced-R8.exe`、sidecar `--check`、`PerMonitorV2, PerMonitor`、`true/pm`、`asInvoker` 和隐藏窗口 `--help` 退出码 `0` 均通过；相对当前线上 R7 增加 `253,594` 字节（约 `0.490%`），低于体积确认门槛。构建前保护的 `runtime.log`、`user_preferences.json` 与 `.bak` 已恢复并逐文件确认 SHA-256 未变化。
- 2026-07-30 R8 用户侧 Release 与 vDS 复核基线回归：Release 正文收敛为扳机、红线、排版、自动更新四类用户可感知更新，关闭自动 commit notes；内部链路留在老三样，vDS 声明同时保留 `0.3.0-rc7` 原始采用提交与 `0.4.0-rc1` 当前复核提交。发行与第三方声明定向回归为 `28 passed in 3.96s`；完整 `uv run --project src --frozen pytest -q -W error` 为 `742 passed in 8.51s`。Ruff 全仓库通过；Pyrefly 为 `0 errors`、`2 suppressed`、`101 warnings not shown`；一次性 PyYAML 解析、`uv lock --check --project src` 与 `git diff --check` 均通过，后者只有现有 LF/CRLF 转换提示。
- 2026-07-30 R8 排版/文案/红线时机发布前回归：相关 GUI、Profile 迁移、默认值、R2、握把、动态红线、灯条、loop、updater 与发行契约为 `281 passed in 7.77s`；完整 `uv run --project src --frozen pytest -q -W error` 为 `741 passed in 10.68s`。Ruff 全仓库通过；Pyrefly 为 `0 errors`、`2 suppressed`、`101 warnings not shown`；限定路径 `compileall`、`uv lock --check --project src` 和 `git diff --check` 均通过，后者只有现有 LF/CRLF 转换提示。Windows 125% 隔离 GUI 目测确认双列/整行卡片、握把长说明完整多行以及电动车红线开关说明移除；隔离窗口未连接手柄、未启动 Forza、未操作用户现有 EXE。
- 2026-07-30 动态红线大红区冷启动回归：`tests/forzahorizon/test_redline.py` 为 `17 passed in 0.21s`；红线、R2、握把、灯条与 loop 定向链路为 `162 passed in 0.35s`。完整 `uv run --project src --frozen pytest -q -W error` 为 `735 passed in 9.73s`。Ruff 全仓库通过；Pyrefly 为 `0 errors`、`2 suppressed`、`94 warnings not shown`；限定路径 `compileall`、`uv lock --check --project src` 和 `git diff --check` 均通过，后者只有现有 LF/CRLF 转换提示。合成测试确认预测红线约 `11760 RPM`、真实断油约 `6200 RPM` 时第一次宽范围候选静默、第二次发布 limiter、第三次学习到约 `6200 RPM`；单次候选、不同 RPM 的三次候选和同条件电驱均不学习。
- 2026-07-30 R8 扳机/updater/电动车红线/排版最终回归：修复前在两个基础阻力开关均关闭、刹车/油门均为 `255` 时可复现 L2/R2 同时输出 mode `0x21`；修复后同条件为 mode `0x05` 的 `off()`。当前 Profile 的轮胎抓地力开关还可单独复现 R2 vibration，总开关关闭后双侧强制 `off()` 并清理 transient/latch。最终红线、扳机、握把、灯条、loop、翻译与发行契约定向回归为 `202 passed in 5.47s`；完整 `uv run --project src --frozen pytest -q -W error` 为 `732 passed in 9.66s`。Ruff 全仓库通过；Pyrefly 为 `0 errors`、`2 suppressed`、`94 warnings not shown`；限定路径 `compileall`、`uv lock --check --project src` 和 `git diff --check` 均通过，后者只有现有 LF/CRLF 转换提示。
- 审计后最终完整测试：`uv run --project src --frozen pytest -q -W error`，结果 `648 passed`。Coverage 单独运行同样为 `648 passed`，总行覆盖率 `57%`；haptics mixer、XInput、Bluetooth haptics 和更新 transaction 等核心逻辑覆盖率较高，GUI/TUI 事件路径与 Windows 上无法执行的 Linux hidraw 路径仍较低。
- 第二轮 handover/audio/UI 定向回归为 `114 passed in 2.39s`；最终执行 `uv run --project src --frozen pytest -q -W error`，结果 `666 passed in 9.08s`。
- 最终 Ruff 全仓库通过；Pyrefly 为 `0 errors`、`2 suppressed`、`88 warnings not shown`；限定路径 `compileall` 和 `uv lock --check --project src` 通过；`git diff --check` 只有现有 LF/CRLF 转换提示，没有 whitespace error。
- 恢复 R6 HID 字节契约后，定向回归为 `91 passed`；最新完整 `uv run --project src --frozen pytest -q -W error` 为 `673 passed in 12.24s`。最新 Ruff 全仓库通过；Pyrefly 为 `0 errors`、`2 suppressed`、`89 warnings not shown`；限定路径 `compileall`、`uv lock --check --project src` 与 `git diff --check` 均通过。测试覆盖 USB/BT trigger-only、compatible rumble、灯效、Bluetooth CRC，以及 transport routing 不调用旧音频模式 setter。
- 完整恢复 R6 USB audio 生命周期后，haptics/output report 定向回归为 `54 passed in 1.16s`；完整 `uv run --project src --frozen pytest -q` 为 `660 passed in 12.15s`。Ruff 全仓库通过；Pyrefly 为 `0 errors`、`2 suppressed`、`86 warnings not shown`；限定路径 `compileall` 与 `uv lock --check --project src` 通过。测试总数下降来自撤销只覆盖 PortAudio 私有 refresh、callback 心跳和显式 retry/backoff 的实验测试，不是遗漏执行。
- 加入 Bluetooth teardown 后，DualSense 与 haptics 定向套件为 `252 passed in 0.95s`；完整 `uv run --project src --frozen pytest -q` 为 `664 passed in 12.32s`。Ruff 全仓库通过；Pyrefly 为 `0 errors`、`2 suppressed`、`86 warnings not shown`；限定路径 `compileall`、`uv lock --check --project src` 与 `git diff --check` 通过。`git diff R6 --exit-code -- src/modules/haptics/audio.py src/modules/haptics/lifecycle.py src/modules/haptics/manager.py` 返回成功，确认 USB 生命周期仍与 R6 相同。
- 历史 USB 开流探针：旧 R7 lifecycle 从 `work/hamza/src` 刷新后发现 index 27 的四声道 DualSense WASAPI endpoint，`started=True`、`running=True`，随后 `stopped=True`。该实现已撤销；探针未运行 Forza，游戏内振动和 Steam Input 状态未记录，不能证明当前候选或游戏手感。
- 新 USB audio readiness 实现的定向测试为 `47 passed in 0.51s`，覆盖 lazy sounddevice loader、Windows endpoint probe、3 秒非阻塞 gate、Bluetooth haptics 保持、失败/异常退避和 body haptics 关闭绕过；相关较宽套件为 `272 passed in 1.49s`。最终完整 `uv run --project src --frozen pytest -q -W error` 为 `678 passed in 11.77s`；Ruff 全仓库通过，Pyrefly 为 `0 errors`、`2 suppressed`、`88 warnings not shown`，限定路径 `compileall`、`uv lock --check --project src` 和 `git diff --check` 通过。
- Xbox App Bluetooth 输入调度修复的定向回归：`src\\.venv\\Scripts\\python.exe -m pytest tests\\dualsense tests\\xinput tests\\haptics tests\\test_loop_haptics.py -q`，结果 `336 passed in 0.92s`。覆盖 latest-only drain、损坏尾包回退、持续 haptics pending、普通/`0x36` 合并、rumble release、XInput stale neutral 与握把循环；真实无线输入延迟仍待实机判断。
- 灯效页、Original、Default ABS 与相关反馈回归共 `181 passed in 2.13s`；算法测试已显式开启 ABS，避免默认关闭后出现无效的 `None == None` 假通过。
- 动态红线完成后，红线、扳机、握把和 loop 定向回归为 `136 passed`；`tests/forzahorizon/test_redline.py` 为 `9 passed`。完整 `uv run --project src --frozen pytest -q` 为 `695 passed in 9.77s`；Ruff 全仓库通过，Pyrefly 为 `0 errors`、`2 suppressed`、`91 warnings not shown`，限定路径 `compileall` 和 `uv lock --check --project src` 通过。
- 撤销前的 HID/ViGEm 自恢复、target 保留、Bluetooth stall 降级和持久日志定向回归为 `92 passed in 1.84s`；当时完整测试为 `700 passed in 8.17s`。该结果仅保留为历史，不再代表当前 Bluetooth stall 行为。
- 撤销 350 ms 永久降级后，DualSense/XInput/haptics 定向回归为 `90 passed in 0.81s`；最新完整 `uv run --project src --frozen pytest -q -W error` 为 `699 passed in 10.34s`。测试总数减少一项来自将两个旧降级测试替换为一个“短暂输入空档保持 HD”回归测试。Ruff 全仓库通过；Pyrefly 为 `0 errors`、`2 suppressed`、`91 warnings not shown`；限定路径 `compileall`、`uv lock --check --project src` 和 `git diff --check` 通过。
- 发布准备复核：发布与构建定向测试 `74 passed in 6.54s`；随后完整 `uv run --project src --frozen pytest -q -W error` 为 `699 passed in 12.33s`。Ruff 全仓库、限定路径 `compileall`、`uv lock --check --project src` 和 `git diff --check` 通过；Pyrefly 为 `0 errors`、`2 suppressed`、`91 warnings not shown`。
- 动态红线灯条和 Xbox App 手动目录修复：相关定向与发布契约测试为 `90 passed in 5.14s`；完整 `uv run --project src --frozen pytest -q -W error` 为 `705 passed in 10.55s`。Ruff 全仓库、限定路径 `compileall`、`uv lock --check --project src` 和 `git diff --check` 通过；Pyrefly 为 `0 errors`、`2 suppressed`、`93 warnings not shown`。
- Xbox App 受限自动发现：路径、FH6 语言、图标、GUI/TUI 接线和发布契约定向回归为 `97 passed in 5.34s`；完整 `uv run --project src --frozen pytest -q -W error` 为 `715 passed in 9.98s`。Ruff 全仓库通过；Pyrefly 为 `0 errors`、`2 suppressed`、`93 warnings not shown`；限定路径 `compileall`、`uv lock --check --project src` 和 `git diff --check` 通过。
- 当前 Windows 源码进程手工检查：导入 `modules`、构造 native backend 和调用 endpoint readiness 均未导入 sounddevice；当前已连接 USB 的 registry probe 返回 `True`。这只证明依赖边界和系统可见性，不证明游戏内握把。
- Ruff 全仓库检查通过；Pyrefly 为 `0 errors`，仍有 warning；Vulture 对显式生产源码列表未发现确定的 dead code。`pip-audit` 对当前锁定环境未发现已知漏洞。Bandit 无 high severity，两个 medium 为允许配置的 UDP wildcard bind 和已经自行验证 HTTPS/redirect 的 `urlopen` 路径，属于人工复核后接受的告警。
- Windows Shell Link 临时集成测试通过：target、icon、参数与工作目录均可读写并保持。
- 2026-07-30 从当前 GitHub R7 Release 重新下载的 Windows 资产为 `51,782,033` 字节，SHA-256 `8cd7ceb1fa6c6dc4b72c259bddc0eee970577c5e48cf4fc7383585708b8cc8f0`，PE 为 R7；它与桌面 `FH-DualSense-Enhanced-R5.exe` 内的字节完全一致，说明旧文档记录的 `4cc106...` 已不是当前线上资产。
- 使用上述当前线上 R7、真实 R6 回滚字节作为故意放置的 `FH-DualSense-Enhanced-R7.exe.old`，以及新构建 R8，在短隔离目录执行正常事务：journal 为 `committed`，规范 R8 存在，R7 EXE、严格同名 `.old` 和 `.sha256` 全部删除，故意放置的无关 `notes.old` 保留。
- 另在短隔离目录把新 R8 复制为错误名称 `FH-DualSense-Enhanced-R5.exe`，旁边放置真实 R6 的严格 `.old`，直接启动冻结 EXE：legacy journal 为 `committed`、记录 `old_version=5` / `new_version=8`，规范 R8 生成，错误 R5 与 `.old` 删除，无关 `notes.old` 保留。两轮新 R8、Helper 和诊断进程最终计数均为 0；三处临时诊断目录已移入回收站，可恢复。
- 使用实际发布的 R6 EXE 构造旧 Helper 的真实输出形态，在隔离目录启动审计前 R7 候选：journal 为 `committed`，两条分别指向 R5/R6 的 Start Menu 测试快捷方式 target/icon 均迁移为 R7，参数和工作目录保持；R5 EXE、R5 `.old`、R5 `.sha256`、R6 EXE 与 R6 `.old` 全部清理。故意放置的 R8 EXE 和无关 `notes.old` 均保留，证明清理没有扩展为通配删除。
- 上述历史 R6 到 R7 真实升级使用线上 R6 SHA-256 `2a6c1ec005fd8cfd056ccdc68ef8d291cc8f7376bc632cc40c737b10cc01c1da`。外层进程 PID 与健康 ACK 内层 PID 不同的早期演练已证明并修复；审计前最终演练同样成功提交。两轮历史测试进程、快捷方式和临时目录均已清理，复核计数为 0。
- 恢复 R6 USB 生命周期的上一 R7 候选：`packaging/windows/dist/FH-DualSense-Enhanced-R7.exe`，SHA-256 `16430403acc2c4ff60d242181977e4604ad3cbc63e350d8b937c1ceaaa92c7aa`。真实硬件确认其 USB/BT 冷启动握把正常，但 BT → USB 后 USB 握把持续失效，应用重启和 USB 重插不能恢复，手柄完全关机可以恢复。
- Bluetooth teardown 隔离候选：`packaging/windows/dist-bt-teardown-1/FH-DualSense-Enhanced-R7.exe`，SHA-256 `84370969e02467b220c4db3c734693a5ea2a1dab4d20e666d10881f363aaa4c3`。真实硬件已经确认它在 teardown accepted、HID 切到 USB 后仍找不到四声道 endpoint，USB 握把无输出；该候选失败且已被替代。
- 当前 USB audio readiness 基线：`packaging/windows/dist-usb-audio-gate-1/FH-DualSense-Enhanced-R7.exe`，`51,959,364` 字节（`49.552 MiB`），SHA-256 `32604c85cb50ca0c404a07ccce0a36baeca480df2c5a553356f3286527492d5b`。用户已实机确认 USB/BT 冷启动和 BT → USB 握把；拔掉 USB 会让手柄关机。
- 当前 Xbox Bluetooth 延迟候选：`packaging/windows/dist-xinput-bt-latency-1/FH-DualSense-Enhanced-R7.exe`，`51,961,930` 字节（`49.555 MiB`），SHA-256 `10d34895574b4d28e4b6a6b559b21352f32b269523f72c6de6697bea9d1b2554`。MZ 头为 `4D 5A`，`FileVersion/ProductVersion=R7`、`OriginalFilename=FH-DualSense-Enhanced-R7.exe` 和 sidecar `--check` 均通过；相对已知可用基线仅增加 `2,566` 字节（`0.0049%`）。
- 当前 R7 发布候选：`packaging/windows/dist-r7-release-candidate-1/FH-DualSense-Enhanced-R7.exe`，`51,963,061` 字节（`49.556 MiB`），SHA-256 `2e913541d6a01cfd1fc9598d8eaeb0a88b89ba91fcd9795c7cd16936e939c507`。它在上一延迟候选上加入灯效页隔离、Original body haptics 和 Default ABS 关闭；版本资源与 sidecar 校验通过，尚待用户界面和 Bluetooth/XInput 实机确认。
- 当前动态红线候选：`packaging/windows/dist-dynamic-redline-1/FH-DualSense-Enhanced-R7.exe`，`51,972,532` 字节（`49.565 MiB`），SHA-256 `798a5ad98c856d7f8f93f14e1018d4e52805b70587755f4a0c30d15380581c31`。MZ 头、R7 File/ProductVersion、OriginalFilename 和 `.sha256 --check` 均通过；相对已知可用 `dist-usb-audio-gate-1` 增加 `13,168` 字节（`0.0253%`），未启动真实 EXE 或运行游戏。
- 当前 Xbox/DualSense Edge 恢复候选：`packaging/windows/dist-xinput-dse-recovery-1/FH-DualSense-Enhanced-R7.exe`，`52,023,359` 字节（`49.613 MiB`），SHA-256 `dd7a4ea10327526fd8fd5e8b03d9b5f5da466dd46dccbca95eaf1592a745f6f9`。MZ 头为 `4D 5A`，`FileVersion/ProductVersion=R7`、`OriginalFilename=FH-DualSense-Enhanced-R7.exe` 和 sidecar `--check` 均通过；相对已知可用 `dist-usb-audio-gate-1` 增加 `63,995` 字节（`0.1232%`），相对公开 R6 增加 `574,417` 字节（约 `0.548 MiB`，`1.116%`），低于体积确认门槛。未启动真实 EXE 或执行硬件长测。
- 当前线上 R7 基线资产：`FH-DualSense-Enhanced-R7.exe`，`51,782,033` 字节（`49.383 MiB`），SHA-256 `8cd7ceb1fa6c6dc4b72c259bddc0eee970577c5e48cf4fc7383585708b8cc8f0`，`FileVersion/ProductVersion=R7`、`OriginalFilename=FH-DualSense-Enhanced-R7.exe`。此前本地记录的 `52,027,090` 字节与 `4cc106...` 只保留为被线上资产替换前的历史值，不能继续用于当前下载校验。
- 上一份标准 R8 本地产物：`packaging/windows/dist/FH-DualSense-Enhanced-R8.exe` 当时为 `52,028,356` 字节（`49.618 MiB`），SHA-256 `3c00fb834344ee420022d508e0e46bb338711483cf94d79038a5967b71dfe711`。该版本的 125% 冻结 GUI 冒烟确认 R8 标识、Bluetooth DualSense 90%、实时 Forza 遥测、总开关显示/保存、长页滚动和更新入口正常；它已被本轮全部电动车 gate 构建覆盖。
- 历史扳机排版/单速电动车候选：`packaging/windows/dist-r8-ev-layout-2/FH-DualSense-Enhanced-R8.exe`，`52,031,213` 字节（`49.621 MiB`），SHA-256 `f1aa0140ff1ac04cf92c9ddb91679826d2bff9f203ab2049cb92173e181e0fd5`。MZ、R8 版本资源、OriginalFilename 和 sidecar 均曾通过；该候选已被后续 gate 规则替代。
- 历史单速电动车三路 gate 候选：`packaging/windows/dist-r8-ev-layout-3/FH-DualSense-Enhanced-R8.exe`，`52,031,956` 字节（`49.622 MiB`），SHA-256 `f02ee93001b2cbec09bd7b87f4b7706033770eacc2fd7f84b362e6c540a28f0e`。它仍在用户进程中运行，但“观察到二挡后恢复触觉”的旧规则已被全部电动车 gate 替代；本轮构建和校验没有关闭该进程。
- 上一份标准 R8 本地产物：`packaging/windows/dist/FH-DualSense-Enhanced-R8.exe`，`52,032,999` 字节（`49.623 MiB`），SHA-256 `558ba6ef4c4acd2f613dccb585a4ab9ae1bd6b6e8580d78b4361efb3fc0f3af1`。MZ 为 `4D 5A`，`FileVersion/ProductVersion=R8`、`OriginalFilename=FH-DualSense-Enhanced-R8.exe` 和 sidecar `--check` 均通过；相对上一份标准 R8 增加 `4,643` 字节（`0.0089%`），相对 `layout-3` 增加 `1,043` 字节（`0.0020%`），相对线上 R7 增加 `250,966` 字节（`0.4847%`），低于体积确认门槛。全量回归为 `736 passed`，Ruff、Pyrefly、compileall、锁文件与 `git diff --check` 均通过。标准 `dist/data` 中原有的 `runtime.log`、`user_preferences.json` 与 `.bak` 已在构建前保全，构建后逐文件 SHA-256 相同；冻结 EXE 在已有 `layout-3` 单实例运行时返回 `0`，未执行独立 GUI/真实手柄冒烟。该文件早于本轮 DPI 换行、UI 文案移除和 95% 红线默认值，只能作为历史候选，不能作为最终 R8 发布资产。
- 上一份本地 ZUV 产物：`packaging/zuv/dist/FH-DualSense-Enhanced.zuv.py`，`7,437,544` 字节，SHA-256 `117b3cb3085c7f223f4294525ee4f98e200980d0b0842e3881320911215a1222`，更新源为 `piereacy/FH-DualSense-Enhanced`。它早于本次扳机总开关和 updater 修复，不是当前 R8 源码的最终 ZUV；本轮只重建并验收 Windows EXE。GitHub workflow 会在干净 runner 的独立 `release/` 目录重新构建，不复用旧 `.zuv` 运行目录残留。
- 相对实际发布 R6 资产 `51,448,942` 字节，延迟候选增加 `512,988` 字节（约 `0.489 MiB`，`0.997%`），低于 `5 MiB` 和 `10%` 门槛。
- 已用 Windows SDK `mt.exe` 从审计后 R7 主 EXE 与 Update Helper 分别提取 manifest，均确认包含 `PerMonitorV2, PerMonitor`、`true/pm` 和 `asInvoker`。构建后的 updater/packaging 定向套件为 `109 passed in 4.41s`。

## 尚未执行或失败的验证

- 新油门末端硬墙尚未取得真实触感结论：自动测试已经区分连续阻力、独立 wall 和抓地力反馈，但尚未连接 DualSense 在 Forza 中确认默认关闭后是否全程自由，以及零阻力但显式开启时是否只在末端形成合适限位。实测必须记录连接方式、游戏内振动与 Steam Input 状态。
- 旧 `dist-r10-project-fixes-review-2` 的真实 DualSense/崩坏：星穹铁道联动已经失败：Steam 模式、`enable_hidhide=false` 且本机日志为 `HidHide: not detected` 时，`StarRail.exe` 运行期间 FHDS 日志仍出现 `DualSense HID opened (BT, pid=0x0ce6)`；只要 FHDS 运行且手柄保持开启，崩铁既不能由键鼠也不能由手柄控制，关闭 FHDS 后恢复。因此该旧候选不能继续用于验收，问题也不能归因于 Steam 或 HidHide。
- R11 当前源码按用户最终边界恢复应用生命周期内的普通 physical HID ownership；切到桌面、崩坏：星穹铁道或其他游戏不会主动释放。当前 PR 与 R11 发布不再准备或推荐旧 R10 监听备用候选。新的 R11 冻结包仍需连接真实 DualSense，分别记录 Steam/Xbox App、USB/Bluetooth、Steam Input、HidHide 和游戏内振动状态；不能把自动测试或旧 R10 现场结论写成 R11 实机验证。
- Haptics Lab 尚未连接真实 DualSense 逐项验证 USB/Bluetooth 握把方向、L2/R2 扳机阻力、DSX 扳机场景、到期释放以及有效游戏遥测抢占；实测必须记录连接方式、游戏内振动和 Steam Input 状态。一键诊断 ZIP 的自动测试只证明 schema、隐私过滤和文件边界，尚未用长时间真实 USB/Bluetooth 故障日志确认各计数器对现场问题的解释力。
- 当前源码尚未做真实大红区燃油车的三次断油学习、单挡/多挡电动车极速与地形波动静默、灯条接近极限和稳定红色、USB/Bluetooth 一致性或驾驶手感验收。
- 当前 125% 环境对隔离的当前源码设置窗口完成目测：扳机总开关与共享反馈各占整行、L2/R2 同行，握把 USB/蓝牙长说明会完整换成多行，两个红线开关下不再出现电动车说明。该 QA 未连接手柄、未启动 Forza，也未触碰用户此前运行的旧冻结 EXE。最终冻结 EXE 只完成 `--help` 无界面启动；100%、150%、最终冻结 GUI、最大化后的连续跨页操作、混合 DPI、多屏移动、动态缩放、睡眠/唤醒、扩展坞和远程桌面仍未执行。
- GitHub runner 的 Linux ELF 构建已成功；真实 Linux 主机上的 hidraw 权限、USB audio、启动与托盘验证仍未执行。
- clean-machine Update Helper、杀毒软件锁文件、真实只读 shortcut 和部分迁移提示未执行；自动测试与隔离目录不能完全替代这些环境。当前线上 R7 到本地 R8 的真实隔离事务与多跳 legacy 引导已执行，但桌面现有安装未被原地改名或清理。
- R10 已线上发布；实际 R7 界面按钮更新曾复现 one-file 父进程误判，完整修复已通过合成 R9 → R10 冻结事务矩阵。真实用户目录的 R9 → R10 在线事务尚未执行；旧 R7/R8 入口仍无法借由新版源码自行修复。
- Xbox App 自动发现和手动 fallback 已通过合成目录测试，本机 `.GamingRoot` 解析也成功；真实 Xbox App FH4/FH5/FH6 游戏、目录 ACL 与 FH6 文件工具仍未验证。

## 下一次 Codex 会话交接

开始时优先阅读：

1. `AGENTS.md`
2. 本文件 `docs/PROJECT_STATE.md`
3. `docs/ARCHITECTURE.md`
4. `docs/DECISIONS.md`
5. `docs/superpowers/specs/2026-07-19-r7-updater-controller-dpi-design.md`
6. `docs/superpowers/plans/2026-07-19-r7-updater-controller-dpi.md`
7. `docs/superpowers/specs/2026-07-20-r7-transport-ui-feedback-separation-design.md`
8. `docs/superpowers/plans/2026-07-20-r7-transport-ui-feedback-separation.md`
9. `docs/superpowers/specs/2026-07-20-r7-bt-usb-audio-readiness-design.md`
10. `docs/superpowers/plans/2026-07-20-r7-bt-usb-audio-readiness.md`
11. `docs/superpowers/specs/2026-07-20-r7-bt-usb-haptics-teardown-design.md`
12. `docs/superpowers/plans/2026-07-20-r7-bt-usb-haptics-teardown.md`
13. `src/modules/dualsense/main.py`
14. `src/modules/haptics/windows_endpoint.py`
15. `src/modules/haptics/audio.py`
16. `src/modules/__init__.py`
17. `src/modules/feedback_schema.py`

建议首先处理的具体任务：保持 R10 tag 与资产不可变，等待用户反馈油门末端硬墙的实际手感；真实测试记录连接方式、Forza 游戏内振动和 Steam Input 状态。只有用户明确要求时，才执行 R9 → R10 的真实用户目录更新或线上资产复核，不主动重复发布后测试或下载资产。

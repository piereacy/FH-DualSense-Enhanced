# FH-DualSense-Enhanced 当前项目状态

最后更新时间：2026-07-22

## 当前阶段

- 当前开发版本：`Enhanced R7`，`src/pyproject.toml` 版本为 `7`。
- 当前公开稳定版：GitHub Release `R6`，本地 tag `R6` 指向 `68ef199`。
- 当前阶段：R7 运行时基础与全项目审计整改已进入生产代码。错误 `valid_flag0=0x20` / `valid_flag1=0x20` HID 音频控制链已删除，USB stream 的 start/stop 仍保持 Enhanced R6 语义。旧 `0x08 / 0x02` teardown 候选已实机失败：report 被接受且 HID 完成 BT → USB，但旧进程随后找不到四声道 USB endpoint，握把仍无输出；新进程却能枚举该 endpoint。源码现已改为 Bluetooth 阶段不导入 sounddevice、稳定 USB 候选非阻塞等待 3 秒、Windows endpoint readiness 通过后才进入既有 teardown 和 USB 提交。
- 当前开发重心：以已知可用的 `dist-usb-audio-gate-1` 生命周期为基线，修复 Xbox App Bluetooth 长时间运行后物理 HID worker、ViGEm session 或 `0x36` 输出挤压输入导致的“延迟升高/不再识别手柄”。恢复候选已构建，下一边界是短时功能冒烟和真实 DualSense Edge 长时间验收；不得借此改动 USB/BT 握把 handover 生命周期。
- 当前代码不是已发布 R7。README、Release workflow 正文和线上资产仍以 R6 为准，这是有意保留的发布边界，不代表 R7 已完成发行准备。

## 代码中已经实现

### 1. 事务式 Windows 自更新

- `src/modules/update/transaction.py` 定义原子 transaction journal、严格 schema/path/version/hash 校验、随机 token 健康 ACK 与阶段恢复。
- `src/modules/update/install.py` 在配置与 GUI/backend 初始化前检测 R6 legacy bootstrap，并按 journal 恢复未完成事务；不再看到 `.old` 就盲删。
- `packaging/windows/update_helper.py` 对 R7 以后版本采用规范文件名并排安装。新版在 30 秒内确认并继续存活约 3 秒后才迁移快捷方式和清理旧版；正常路径不创建 `.old`。
- 已发布 R6 的旧 Helper 输出由一次性第二阶段处理：严格验证当前/备份 PE 版本后恢复规范 R6、安装规范 R7，再提交健康状态。快捷方式部分失败时保留真实 R6，而不是遗留 `.old`。
- `packaging/windows/shortcut_links.py` 使用原生 Shell Link COM 扫描当前用户 Desktop、Programs 和已知 pinned 目录，只迁移绝对 target 精确匹配旧 EXE 的 `.lnk`，并保留参数、工作目录和 icon index。
- 健康提交后会枚举同目录全部严格命名且低于新版的规范 EXE，逐个迁移快捷方式并静默删除；严格同名的旧 `.exe.old` 与 `.exe.sha256` 也会清理，包括 R5 更新遗留。其他 EXE、任意 `.old`、同版和更高版本不在清理范围；某一旧版快捷方式失败时只保留该规范 EXE。
- 安装前验证应用目录可写并阻止同一目录内其他规范版本进程参与更新；Helper/主程序竞争、陈旧 ACK、启动恢复和有限重试均有测试。
- PyInstaller one-file 外层 bootloader 和内层应用 PID 不同的情况已处理：token 验证 ACK 身份，Helper 监视自己启动的外层进程存活。

### 2. DualSense 连接真值、电量和拓扑切换

- `src/modules/dualsense/controller_state.py` 提供不可变 `ControllerSnapshot`、phase、transport、电量和充电状态；GUI/TUI 不再以 `dev is not None` 推断在线。
- `src/modules/dualsense/input_state.py` 验证完整 USB/BT report、report ID、D-pad 和 Bluetooth `0xA1` CRC，并解析 10% 电量档和充电状态。损坏或不完整报告不能刷新在线时间、电量或 XInput consumer。
- `src/modules/dualsense/main.py` 始终读取输入维持连接真值，即使 Steam 模式没有 XInput consumer。约 3 秒无有效输入就清除旧 transport、电量和输入；HidHide 与关闭自动重连不再绕过 watchdog。
- 空闲 HID backlog 会批量 drain，防止旧缓冲延长“已连接”。Steam/无 XInput consumer 时 pending output 仍优先；Xbox bridge 启用时，I/O thread 优先追到输入队尾且只发布批次中的最新有效状态，连续 Bluetooth `0x36` 不再把读取限制为每轮一条。同轮 `0x36` 已携带扳机/灯效且普通 frame 没有 compatible rumble 时会合并重复写入，显式 rumble 与释放不受影响。
- `src/modules/dualsense/topology.py` 约每秒轻量 enumerate，新路径连续两次出现才稳定。未知身份 feature report 读取失败按 1/2/5 秒退避并在路径消失后清除；只对同一身份自动 handover，同一手柄 USB 优先。
- USB/BT handover 和“立即重新连接”都投递到唯一 HID I/O thread。候选 handle 会先打开并读到有效输入。启用 body haptics 的 BT → USB 对稳定候选非阻塞等待 3 秒，期间继续使用 Bluetooth 输入、L2/R2 扳机键和 `0x36` 握把；到期后用只读 Windows MMDevices registry probe 确认活动的 DualSense USB render endpoint。未就绪或异常时关闭候选、保持当前 BT transport/快照/pending output，并按 1/2/5 秒退避，重试不再重复 settle；关闭 body haptics 时绕过 endpoint 条件。readiness 通过后才静音，通过旧 BT handle 发送按 HIDP `0x53` seed CRC 构造的 48 字节 feature report `0x08 / 0x02`，返回正数后原子提交 USB。该命令不用于冷启动、USB → BT 或普通 reconnect。自动 handover 不受完全掉线重连开关限制，不播放启动 R2 扳机键脉冲；“重新扫描”仍只刷新设备列表。
- 临时 USB handle 在 `set_nonblocking` 失败时会关闭，controller lock serial 会规范化，避免设备泄漏和身份格式漂移。
- 普通 USB/BT state report 已恢复 R6 的字段所有权：扳机、compatible rumble 与灯效只声明各自已有的 valid bits。`HapticManager` 只选择 USB 四声道 PCM、Bluetooth `0x36` 或 compatible fallback，不再通过普通 HID report 猜测或切换“音频触觉模式”；也没有加入曾经失败的单次 `0x01` 重置写入。
- 唯一 HID worker 现由 `_io()` 监督 session。未预期异常会关闭当前 handle 并按 0.25/1/5 秒上限恢复；关闭自动重连时保留可由“立即重新连接”唤醒的 worker，按钮检测到旧 worker 已死亡时会重启它，不会并行创建第二个 reader。
- 输入拒绝不再只记录应用启动后的第一次：连续第 1/8/32/128 次及之后每 512 次限频记录，长错误串恢复时记录恢复边沿；HID open 日志包含产品 PID，便于区分 DualSense 与 DualSense Edge。
- Bluetooth HD 已发送且连续 350 ms 没有有效输入时，当前连接先尽力发送零采样 `0x36`，再拒绝 HD 队列并转入 compatible rumble，避免继续用高带宽输出拖到整个 3 秒连接 watchdog 失效。重新建立 Bluetooth 连接后才重新尝试 HD。

### 3. 配置迁移与状态界面

- GUI/TUI 的 LightingTab 不再继承握把页的 `SWITCH_SECTIONS`，灯效页只展示转速灯条、颜色与档位 LED 设置。
- 出厂 `Default` 将 `enable_abs` 设为 `False`；这只影响新配置和恢复出厂，不强制覆盖已有用户保存的驾驶参数。内置 `Original` 保留上游 1.6.2 扳机参数，但启用 Enhanced body haptics，并在加载配置时刷新为当前规范值。
- `src/modules/config/settings.py` 的 `enable_reconnect` 出厂默认改为 `True`。
- `src/modules/config/preferences.py` 通过 `r7_enable_reconnect_default` marker 对已有用户只强制开启一次自动重连。迁移不触碰驾驶体验、命名 Profile 或其他 global 字段，之后用户关闭会被尊重。
- GUI/TUI 的设备分组改为“连接与重连”，现有 Reconnect 已改为真实 I/O 命令；Rescan 语义保持列表刷新。
- 顶部 DualSense 状态框显示 phase、USB/BT、电量和充电状态。仅使用电池且为 10% 时电量细节为红色，连接点仍为绿色；断开后不保留旧电量。Profile/控制器控件已收敛为 28 logical px 高、8 logical px 圆角的小型状态框，并跳过相同状态的重复渲染。
- UDP bind 错误只进入总览遥测状态与日志，不再覆盖顶部控制器 Pill。全部非英语 catalog 已补齐新字段。
- `src/modules/feedback_schema.py` 统一声明扳机与握把字段归属。GUI/Console 的 `Trigger feedback` 只显示 L2/R2 开关、调节和扳机实验项，`Grip haptics` 只显示握把开关、调节和握把实验项；两页字段互斥并由翻译覆盖测试约束。

### 4. Windows Per-Monitor v2 与可复现构建

- `packaging/windows/fhds.manifest` 为主 EXE 与 Update Helper 声明 `PerMonitorV2, PerMonitor`、旧 fallback 和 `asInvoker`。
- `packaging/windows/dpi_runtime_hook.py` 与 `src/main.py` 在任何 Tk/CustomTkinter 窗口前调用 `modules.dpi.bootstrap_windows_dpi()`；旧的 GUI 构造后 `SetProcessDpiAwareness(2)` 已删除。
- `src/modules/dpi.py` 查询实际 thread/window awareness、窗口 DPI 与缩放率。GUI 系统页显示该诊断，不是 PMv2 时提示检查 Windows 兼容性覆盖，不修改注册表。
- `src/modules/gui/widgets.py` 让隐藏页暂停 `FastScroll` canvas 尺寸回流，可见页以 40 ms debounce 合并 resize；反馈开关卡片以 80 ms debounce 处理列数变化并复用既有 grid item。`src/modules/gui/main.py` 在 `tkraise()` 导航边界切换活跃页，避免最大化时所有常驻长页同时重新布局；系统更新卡片只在稳定 presentation 变化时重绘，不再每 250 ms 无条件显隐按钮。
- `src/pyproject.toml` 和 `src/uv.lock` 固定 PyInstaller `6.16.0`；`packaging/windows/build_exe.bat` 使用 `uv run --project src --frozen pyinstaller` 构建 Helper 和主 EXE，不再用任意最新 `uvx` 解析。
- 审计后的 R7 候选已重新嵌入并验证 PMv2 manifest、R7 PE 版本资源和项目图标；精确产物信息见下方“已执行的测试和验证”。

### 5. 全项目审计中已落实的整改

- 配置与 Profile：`preferences.py` 对 JSON 根对象、嵌套 Profile、类型和非有限浮点做严格归一化；`udp_host`、`udp_timeout`、`telemetry_lost_exit_s` 明确归入 globals。写入使用 UUID 临时文件和原子 replace，恢复出厂或损坏恢复在无法先保护有效文件时失败关闭。
- 分享与显示：`profiles.py` 对压缩输入和解压输出设上限，Profile 名称去控制字符并限制 64 字符，重名 suffix 同样受限；TUI 对动态 Profile、路径、错误和状态文本禁用或转义 Rich markup。
- UDP 与遥测：listener 只在完整 324 字节包成功解析后推进“最后有效遥测”，字段进入效果计算前会清理非有限数；损坏流量不能持续刷新在线状态或让旧效果继续输出。
- 触觉：USB stream 生命周期保持 Enhanced R6。GUI/TUI 的 `UsbAudioLifecycle` 在周期 eligibility sync 中按 `_running` 启动或停止共享 stream；headless `HapticManager` 在同一 transport epoch 启动失败后设置闩锁，避免逐遥测帧重开，并在 transport 或 eligibility 变化时复位。Windows `UsbAudioHaptics` 只在 `start()` 延迟导入 sounddevice，再查询当时初始化的 WASAPI snapshot；Bluetooth 阶段不会提前初始化 PortAudio。代码不调用私有 PortAudio refresh、不做 callback 心跳判活，也不增加 lifecycle lock。Bluetooth worker、`0x36`、USB/BT stop 和 compatible fallback 的失败隔离与释放路径仍保留。
- Linux：`_hidraw.py` 改用 wrapper 实际支持的 `timeout_ms` 关键字；`packaging/linux/build_elf.sh` 改为 `uv.lock` 冻结环境，并跳过 one-file 不需要的 PyGObject/pycairo。当前只完成 Windows 上的单元测试和 Bash 语法检查，不等同真实 Linux 构建。
- GUI/TUI：TUI 新增与 GUI 同语义的 `ProfileSession` 退出流程；快捷键、按钮、backend shutdown 和更新安装都经过统一关闭入口，取消时不会提前调度 Helper。更新健康 callback 在 backend、listener 和 telemetry worker 启动后才执行，构造窗口本身不再提前确认健康。扳机/握把两页现在从共享 schema 渲染，开关、常用调节和实验项不再混页。
- 启动与依赖：删除 `src/dev.env` 和运行时 `python-dotenv`，主程序不再因快捷方式工作目录中的同名文件改变配置。Pillow、PyInstaller、Pyrefly 与锁文件依赖已经固定到当前项目声明。
- 更新与文件工具：Release、sidecar、pending metadata、transaction plan、路径和 checksum 采用严格 schema/HTTPS/credential/大小校验；FH6 语言与图标文件操作在无法证明目标、备份或进程状态时失败关闭，不以宽泛删除“修复”未知残留。

### 6. 共享动态红线估计

- `src/modules/forzahorizon/redline.py` 保留原始仪表 `max_rpm`，学习前提供经验预测；在接近预测红线、高油门、稳定同挡、低离合和低轮胎滑移条件下检测功率/扭矩切断，并用 120 ms 延迟确认排除换挡。
- 第一次确认断油即可产生短暂 `rev_limiter_active`；三个相近候选以中位数建立 `effective_redline_rpm`，后续允许平滑修正。车辆 ordinal、PI 或仪表范围改变时重置，菜单临时归零不清除学习。
- `src/modules/loop.py` 把同一派生状态交给 `effects.py` 的 R2 扳机键和 `haptics/mixer.py` 的握把红线；发动机底噪与灯效继续读取原始 `max_rpm`。代码未采用参考分支直接覆盖 telemetry 的做法。
- 当前只有自动测试和合成遥测验证，尚未用真实大红区车辆确认学习速度、误触发和手感。

### 7. Xbox bridge 长时间运行恢复与诊断

- `src/modules/xinput/bridge.py` 在 100 ms 无新输入时只发送一次中立状态，bridge 模式仍启用期间保留同一个 X360 target/player slot；新物理报告直接复用 target，切回 Steam 或停止应用时才移除。
- ViGEm 非 driver-missing session 异常会清理旧 target/client，并按 0.25/1/5 秒上限自动重建。driver 缺失仍维持稳定状态等待用户安装或显式重试；旧输入不会跨 stop/restart 回放。
- `src/modules/runtime_logging.py` 为 GUI、TUI 和 headless 安装 2 MiB、两个备份的轮转 `data/runtime.log`；UI 关闭日志 handler 后，backend teardown 仍可写入。该文件用于用户反馈“玩到后面不认手柄”时区分 HID CRC、worker、ViGEm 和 handover 故障。
- 自动测试已覆盖 target 保留、stale 后复用、ViGEm update 异常重建、物理 worker 恢复、手动 reconnect 复活 dead worker、Bluetooth stall 静音/降级及日志 handler。真实 DualSense Edge、Xbox App 游戏和 30 至 60 分钟 Bluetooth 压力测试未执行。

## 文档、代码和推测的边界

- 已由生产代码和自动测试证明：transaction 恢复决策、R6 legacy 识别、快捷方式精确匹配、健康 token 与 ACK 时机、ControllerSnapshot、输入超时、电量映射、拓扑去抖、handover 候选预验证与 1/2/5 秒候选退避、switching 无启动脉冲、重连迁移、物理 HID worker 自恢复、ViGEm session 自恢复、100 ms 中立后 target 保留、Bluetooth 输入 stall 降级、UDP 有效包边界、配置/分享码校验、TUI 正常退出、Enhanced R6 USB stream 状态语义、扳机/握把字段互斥、可见页 resize 合并、更新卡片 presentation cache、状态展示和 DPI 几何契约。新增测试固定 sounddevice 构造时不加载、首次 `start()` 只加载一次，Windows endpoint active/inactive/权限错误边界，3 秒非阻塞 settle、等待期间 Bluetooth haptics 保持、readiness 失败/异常保留 BT、候选消失清理状态及 body haptics 关闭时绕过。字节级测试继续固定普通 USB/BT report 不声明两个未经验证的 `0x20` 控制位，以及 Bluetooth power-off feature report 的 48 字节布局和 `0x53` seed CRC `0x23A2EFE0`。真实长时间连接、DualSense Edge 和握把恢复仍不属于自动测试已经证明的事实。
- 已由真实 Windows 隔离环境证明：已发布 R6 旧 Helper 形态可以迁移到规范 R7，测试快捷方式 target/icon 已改为 R7，参数和工作目录保留，事务提交后 R6/`.old` 被清理。
- 已由当前 Windows 进程证明：源码 DPI probe 报告 Per-Monitor v2、120 DPI、125%；最终 PE manifest 可提取并包含 PMv2。
- 已由当前真实 Windows USB 设备证明：系统和新启动的 sounddevice 进程能枚举 index 27 的四声道 DualSense WASAPI endpoint；旧 teardown 候选却在同一现场报告找不到端点。当前锁定的 sounddevice 在 import 尾部调用 `_initialize()`，因此旧进程的 PortAudio snapshot 早于 USB hotplug。源码手工检查还证明导入 `modules` 和构造 native backend 都不会再把 sounddevice 放入 `sys.modules`，readiness probe 返回 `True` 时也不会加载它。
- 已由真实硬件复现：恢复 R6 stream 生命周期的上一候选在 USB 与 Bluetooth 冷启动时握把正常；从 BT 切到 USB 后 HID 状态和 L2/R2 扳机键继续工作，但 USB 握把无输出。旧 `0x08 / 0x02` teardown 候选同样失败：日志显示 teardown accepted、HID 完成 USB handover，随后仍找不到四声道 endpoint，USB 握把没有恢复。新 3 秒 readiness/lazy-import 候选尚未实机运行；自动测试、registry readiness 和 feature report 返回值都不能替代游戏内握把结果。
- 尚未由真实显示器组合证明：不同缩放率显示器间移动、运行中更改缩放、睡眠/唤醒、扩展坞和远程桌面后的清晰度与单次缩放。
- 根据代码推测可能成立但不得写成已验证：同一身份判定能覆盖不同固件/蓝牙适配器和 DualSense Edge 的全部 raw identifier 组合。

## 正在进行

1. 非破坏性 BT/USB HID handover、switching 脉冲抑制、Bluetooth `0x36`、扳机与握把分页、状态框像素对齐、更新 UI 缓存和最大化布局合并保留在当前候选。PortAudio 私有 refresh、并发 lifecycle lock、callback 心跳和额外 USB audio backoff 均未恢复。
2. `dist-usb-audio-gate-1` 已由用户实机确认：USB 与 Bluetooth 冷启动握把正常，Bluetooth 插入 USB 后 USB 握把恢复；拔掉 USB 时手柄会关机，需要用户重新开机。用户已接受该行为作为当前 R7 handover 基线，后续修复不得改动这条生命周期。
3. Xbox App Bluetooth 高延迟与长期掉线修复已进入 `src/modules/dualsense/main.py`、`src/modules/xinput/bridge.py` 和 `src/modules/runtime_logging.py`：除了 input-first/latest-only drain，还加入 HID/ViGEm 自恢复、target 保留、350 ms `0x36` stall 降级和持久日志；自动测试和独立 `dist-xinput-dse-recovery-1` EXE 已完成，真实 Bluetooth/XInput/DualSense Edge 手感与长时间稳定性尚待验证。
4. 动态红线估计已经进入生产路径并构建 `dist-dynamic-redline-1`。其预测、同挡位确认、换挡/打滑排除、三样本聚类、车辆切换复位及扳机/握把共享消费均有自动测试；真实车辆尚未验收。

## 尚未完成

1. `dist-dynamic-redline-1` 需要选一辆仪表红区明显大于真实断油范围的车辆，保持 Forza 游戏内振动关闭并记录 Steam Input 状态，至少连续触发三次同挡位断油；检查第一次实际断油可感知、第三次后接近红线警告提前到正确区间，并确认普通换挡、漂移和严重空转不会训练或误触发。
2. 新的 `dist-xinput-dse-recovery-1` 需要先在 Bluetooth、Xbox App bridge 开启、Steam Input 关闭时做短时操控/握把/L2/R2 扳机键冒烟，再在可用的 DualSense Edge 上运行 30 至 60 分钟并检查 `data/runtime.log`。用户当前无法执行长时间实机段，因此明确保留为未执行；`dist-usb-audio-gate-1` 仍是已知可用回退基线。
3. Windows DPI：在 100%、125%、150% 分别目测顶部两个状态框边缘，并检查窗口最大化/还原和页面切换；混合 DPI 还需验证显示器间往返、运行中 scale 变化和弹窗/原生 Tk 控件清晰度。
4. 用户此前明确把 Xbox App FH6 内容目录自动发现留给 R7，但当前 R7 runtime foundation 规格与生产代码尚未实现它。发布 R7 前必须重新确定并完成该范围，或取得用户明确同意延期；现有行为仍是手动选择并缓存 `fh6_xbox_install_path`。
5. R7 README、三语用户指南增量、双语 Release body、workflow 版本正文、tag、push、Release 与线上重新下载验证均未执行。
6. R7 到 R8 的正常并排更新尚无真实已发布 R8 资产可做端到端验收；当前由自动测试覆盖。
7. 真实只读/被占用快捷方式、任务栏 pin 缓存和快捷方式部分失败后的跨启动修复尚未在用户 shell 环境执行。
8. 真实 Linux ELF 构建、`/dev/hidraw` 权限与桌面托盘未执行；Windows 上的脚本语法和适配层测试不能替代它们。
9. Xbox App/Bluetooth 延迟修复尚未用真实 Xbox App 游戏验收；可先用 Steam 版关闭 Steam Input、选择 Xbox App bridge 做输入链路 A/B，但该结果不能替代真实 Xbox App。

## 下一步建议顺序

1. 退出其他候选后启动 `dist-xinput-dse-recovery-1`；在 Bluetooth 下选择 Xbox App 模式并关闭 Steam Input，短时检查摇杆、按键、握把与 L2/R2 扳机键，同时记录 Forza 游戏内振动状态。
2. 有条件时保持同一场景运行 30 至 60 分钟，检查是否进入 compatible fallback、HID/ViGEm 是否自动恢复，并保留 `data/runtime.log`；没有 DualSense Edge 或无法长测时明确写未执行，不阻塞其他离线验证。
3. 短时输入通过后做一次 USB 冷启动和 BT → USB；若握把生命周期与 `dist-usb-audio-gate-1` 不同立即停止发布并回退。之后再用 `dist-dynamic-redline-1` 完成大红区车辆断油手感验收。
4. 在 100%、125%、150% 验证顶部状态框和最大化/还原流畅度；再在混合 DPI 环境目测主窗口、导航、原生 Tk 控件和弹窗。没有第二块不同缩放显示器时明确写未执行。
5. 在真实 Linux 主机生成 ELF，并验证 hidraw 权限、USB audio 与托盘。
6. 回到尚未实现的 Xbox App FH6 自动目录发现要求，先基于当前 Xbox package/游戏卷 API 重新确认安全边界，再实施或由用户明确延期。
7. 用户确认 R7 功能范围和候选后，先 fetch/review `origin/main`，语义合并远端 README 改动，再准备三语 README、双语 Release body、workflow、提交、tag 和发布。

## 当前已知 Bug 和限制

- `dist-usb-audio-gate-1` 已实机恢复 BT → USB 后的 USB 握把，但代价是拔掉 USB 时手柄关机，需要用户重新开机；当前不尝试保持无线会话的替代方案。
- Xbox App FH4/FH5/FH6 真实游戏仍未在当前电脑验收。FH6 内容目录、语言和图标工具继续需要手动选择路径。
- Forza 游戏内振动必须关闭，否则 native rumble/Steam Input 可能掩盖本项目握把方向与细节；项目不接管游戏原生 rumble。
- 动态红线没有 Forza 官方 limiter flag，只能从功率、扭矩、RPM、挡位、油门、离合和滑移推断。合成测试已覆盖主要误判边界，但真实车辆与改装组合尚未验证，不能写成已经解决全部红线差异。
- XInput bridge 不接收游戏 rumble，也没有多手柄、Xbox One target、GameInput impulse trigger、触摸板或陀螺仪映射。
- Bluetooth 输入 stall 会为保住操控链路而把当前连接的 HD `0x36` 降级为 compatible rumble；该连接的握把细节和左右分离可能降低，必须重新连接 Bluetooth 才会再试 HD。350 ms 门槛只有自动测试，没有不同蓝牙适配器和 DualSense Edge 的长期实机标定。
- ViGEm 上游 EOL；固定哈希不能替代未来安全维护。
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
- `runtime.log` 尚无 UI 内一键导出、HID report sequence 丢包统计或蓝牙适配器指标；连续 CRC 错误只能按限频计数和恢复边沿诊断。
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
- 控制器与输入桥：`src/modules/dualsense/main.py`、`src/modules/dualsense/input_state.py`、`src/modules/dualsense/controller_state.py`、`src/modules/dualsense/topology.py`、`src/modules/dualsense/presentation.py`、`src/modules/xinput/bridge.py`、`src/modules/xinput/service.py`、`src/modules/runtime_logging.py`。
- 配置与界面：`src/modules/config/settings.py`、`src/modules/config/preferences.py`、`src/modules/config/profiles.py`、`src/modules/feedback_schema.py`、`src/modules/gui/controls_tab.py`、`src/modules/gui/settings_tab.py`、`src/modules/gui/system_tab.py`、`src/modules/gui/widgets.py`、`src/modules/tui/controls_tab.py`、`src/modules/tui/settings_tab.py`、`src/modules/tui/system_tab.py`、`src/lang/`。
- 触觉与平台：`src/modules/haptics/audio.py`、`src/modules/haptics/windows_endpoint.py`、`src/modules/haptics/manager.py`、`src/modules/haptics/lifecycle.py`、`src/modules/dualsense/bt_haptics.py`、`src/modules/dualsense/main.py`、`src/modules/dualsense/_hidraw.py`、`src/modules/__init__.py`、`packaging/linux/build_elf.sh`。
- 红线：`src/modules/forzahorizon/redline.py`、`src/modules/loop.py`、`src/modules/forzahorizon/effects.py`、`src/modules/haptics/mixer.py`、`tests/forzahorizon/test_redline.py`。
- 构建与测试：`packaging/windows/build_exe.bat`、`packaging/windows/fhds.spec`、`src/pyproject.toml`、`src/uv.lock`、`tests/test_update_*.py`、`tests/test_profile_persistence.py`、`tests/test_main_runtime.py`、`tests/test_tui_lifecycle.py`、`tests/haptics/test_audio.py`、`tests/haptics/test_windows_endpoint.py`、`tests/haptics/test_manager.py`、`tests/test_backend_factory.py`、`tests/dualsense/test_output_report.py`、`tests/dualsense/test_controller_runtime.py`、`tests/dualsense/test_controller_state.py`、`tests/dualsense/test_topology.py`、`tests/gui/test_header_status_frame.py`、`tests/test_dpi_contract.py`。

## 当前 Git 工作区状态

- 分支：`main`。R7 runtime foundation、随后覆盖上游/R1-R7 的审计整改、生产源码、测试、老三样和构建配置已纳入当前 `main` 提交历史；精确 HEAD 与远端同步状态以 `git status -sb` 和 `git log -1` 为准。
- 本批实现建立在 13 个 R7 设计/计划提交之上；提交前的远端基线为 `b969826 docs: link icon author GitHub profile`，fetch 时远端没有新增提交或 README 冲突。
- `packaging/windows/build-*`、`dist-*`、`diagnostics-*` 和 `helper_work-*` 是本地隔离构建或诊断产物，不随源码提交；已知可用的 `dist-usb-audio-gate-1` 基线没有被覆盖。
- 没有创建或移动 R7 tag，也没有发布 R7 Release。当前公开稳定版仍是 R6。

## 已执行的测试和验证

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
- HID/ViGEm 自恢复、target 保留、Bluetooth stall 降级和持久日志的定向回归为 `92 passed in 1.84s`；最终完整 `uv run --project src --frozen pytest -q -W error` 为 `700 passed in 8.17s`。Ruff 全仓库通过；Pyrefly 为 `0 errors`、`2 suppressed`、`91 warnings not shown`；限定路径 `compileall`、`uv lock --check --project src` 和 `git diff --check` 通过。
- 当前 Windows 源码进程手工检查：导入 `modules`、构造 native backend 和调用 endpoint readiness 均未导入 sounddevice；当前已连接 USB 的 registry probe 返回 `True`。这只证明依赖边界和系统可见性，不证明游戏内握把。
- Ruff 全仓库检查通过；Pyrefly 为 `0 errors`，仍有 warning；Vulture 对显式生产源码列表未发现确定的 dead code。`pip-audit` 对当前锁定环境未发现已知漏洞。Bandit 无 high severity，两个 medium 为允许配置的 UDP wildcard bind 和已经自行验证 HTTPS/redirect 的 `urlopen` 路径，属于人工复核后接受的告警。
- Windows Shell Link 临时集成测试通过：target、icon、参数与工作目录均可读写并保持。
- 使用实际发布的 R6 EXE 构造旧 Helper 的真实输出形态，在隔离目录启动审计前 R7 候选：journal 为 `committed`，两条分别指向 R5/R6 的 Start Menu 测试快捷方式 target/icon 均迁移为 R7，参数和工作目录保持；R5 EXE、R5 `.old`、R5 `.sha256`、R6 EXE 与 R6 `.old` 全部清理。故意放置的 R8 EXE 和无关 `notes.old` 均保留，证明清理没有扩展为通配删除。
- 上述真实升级使用线上 R6 SHA-256 `2a6c1ec005fd8cfd056ccdc68ef8d291cc8f7376bc632cc40c737b10cc01c1da`。外层进程 PID 与健康 ACK 内层 PID 不同的早期演练已证明并修复；审计前最终演练同样成功提交。两轮测试进程、快捷方式和临时目录均已清理，复核计数为 0。审计后精确候选未重复这项会启动真实 EXE 的演练，当前由 109 项 updater/packaging 定向测试覆盖。
- 恢复 R6 USB 生命周期的上一 R7 候选：`packaging/windows/dist/FH-DualSense-Enhanced-R7.exe`，SHA-256 `16430403acc2c4ff60d242181977e4604ad3cbc63e350d8b937c1ceaaa92c7aa`。真实硬件确认其 USB/BT 冷启动握把正常，但 BT → USB 后 USB 握把持续失效，应用重启和 USB 重插不能恢复，手柄完全关机可以恢复。
- Bluetooth teardown 隔离候选：`packaging/windows/dist-bt-teardown-1/FH-DualSense-Enhanced-R7.exe`，SHA-256 `84370969e02467b220c4db3c734693a5ea2a1dab4d20e666d10881f363aaa4c3`。真实硬件已经确认它在 teardown accepted、HID 切到 USB 后仍找不到四声道 endpoint，USB 握把无输出；该候选失败且已被替代。
- 当前 USB audio readiness 基线：`packaging/windows/dist-usb-audio-gate-1/FH-DualSense-Enhanced-R7.exe`，`51,959,364` 字节（`49.552 MiB`），SHA-256 `32604c85cb50ca0c404a07ccce0a36baeca480df2c5a553356f3286527492d5b`。用户已实机确认 USB/BT 冷启动和 BT → USB 握把；拔掉 USB 会让手柄关机。
- 当前 Xbox Bluetooth 延迟候选：`packaging/windows/dist-xinput-bt-latency-1/FH-DualSense-Enhanced-R7.exe`，`51,961,930` 字节（`49.555 MiB`），SHA-256 `10d34895574b4d28e4b6a6b559b21352f32b269523f72c6de6697bea9d1b2554`。MZ 头为 `4D 5A`，`FileVersion/ProductVersion=R7`、`OriginalFilename=FH-DualSense-Enhanced-R7.exe` 和 sidecar `--check` 均通过；相对已知可用基线仅增加 `2,566` 字节（`0.0049%`）。
- 当前 R7 发布候选：`packaging/windows/dist-r7-release-candidate-1/FH-DualSense-Enhanced-R7.exe`，`51,963,061` 字节（`49.556 MiB`），SHA-256 `2e913541d6a01cfd1fc9598d8eaeb0a88b89ba91fcd9795c7cd16936e939c507`。它在上一延迟候选上加入灯效页隔离、Original body haptics 和 Default ABS 关闭；版本资源与 sidecar 校验通过，尚待用户界面和 Bluetooth/XInput 实机确认。
- 当前动态红线候选：`packaging/windows/dist-dynamic-redline-1/FH-DualSense-Enhanced-R7.exe`，`51,972,532` 字节（`49.565 MiB`），SHA-256 `798a5ad98c856d7f8f93f14e1018d4e52805b70587755f4a0c30d15380581c31`。MZ 头、R7 File/ProductVersion、OriginalFilename 和 `.sha256 --check` 均通过；相对已知可用 `dist-usb-audio-gate-1` 增加 `13,168` 字节（`0.0253%`），未启动真实 EXE 或运行游戏。
- 当前 Xbox/DualSense Edge 恢复候选：`packaging/windows/dist-xinput-dse-recovery-1/FH-DualSense-Enhanced-R7.exe`，`52,023,359` 字节（`49.613 MiB`），SHA-256 `dd7a4ea10327526fd8fd5e8b03d9b5f5da466dd46dccbca95eaf1592a745f6f9`。MZ 头为 `4D 5A`，`FileVersion/ProductVersion=R7`、`OriginalFilename=FH-DualSense-Enhanced-R7.exe` 和 sidecar `--check` 均通过；相对已知可用 `dist-usb-audio-gate-1` 增加 `63,995` 字节（`0.1232%`），相对公开 R6 增加 `574,417` 字节（约 `0.548 MiB`，`1.116%`），低于体积确认门槛。未启动真实 EXE 或执行硬件长测。
- 相对实际发布 R6 资产 `51,448,942` 字节，延迟候选增加 `512,988` 字节（约 `0.489 MiB`，`0.997%`），低于 `5 MiB` 和 `10%` 门槛。
- 已用 Windows SDK `mt.exe` 从审计后 R7 主 EXE 与 Update Helper 分别提取 manifest，均确认包含 `PerMonitorV2, PerMonitor`、`true/pm` 和 `asInvoker`。构建后的 updater/packaging 定向套件为 `109 passed in 4.41s`。

## 尚未执行或失败的验证

- `dist-xinput-dse-recovery-1` 尚未做真实 Bluetooth/XInput 延迟、30 至 60 分钟稳定性、DualSense Edge 和驾驶反馈验收；真实 Xbox App FH4/FH5/FH6 也仍未在当前电脑验证。
- `dist-dynamic-redline-1` 尚未做真实大红区车辆的三次断油学习、换挡/打滑误触发、USB/Bluetooth 一致性或驾驶手感验收。
- 当前 125% 环境曾对上一份 EXE 完成基础目测：两个顶部状态框没有原黑底白点问题，边缘未见先前的明显锯齿；最大化成功且没有等待所有页面重载。最新候选又加入反馈卡片/更新卡片缓存，尚未重新目测。100%、150%、最大化后的连续跨页操作、混合 DPI、多屏移动、动态缩放、睡眠/唤醒、扩展坞和远程桌面仍未执行。
- 真实 Linux ELF 构建、hidraw 权限和托盘验证未执行；仅完成 Windows 测试与 Bash 语法检查。
- clean-machine Update Helper、杀毒软件锁文件、真实只读 shortcut 和部分迁移提示未执行；自动测试与隔离目录不能完全替代这些环境。
- R7 README/Release workflow 更新、线上构建、tag、Release、线上重新下载和 R7 到下一版本更新均未执行。
- Xbox App FH6 内容目录自动发现尚未实现，也未验证真实 Xbox App 游戏。

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

建议首先处理的具体任务：退出其他候选后，用 SHA-256 为 `dd7a4ea10327526fd8fd5e8b03d9b5f5da466dd46dccbca95eaf1592a745f6f9` 的 `dist-xinput-dse-recovery-1`，在 Bluetooth、Xbox App bridge、Steam Input 关闭条件下做短时操控延迟与反馈冒烟；同时记录 Forza 游戏内振动状态。若后续能取得 DualSense Edge 长时间现场，再运行 30 至 60 分钟并保留 `data/runtime.log`；当前不能执行则明确保持未验证。

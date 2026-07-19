# Enhanced R7：事务更新、DualSense 状态与 Windows DPI 设计

日期：2026-07-19
状态：用户已确认设计，尚未实施

## 1. 背景与目标

Enhanced R7 集中修复三个彼此关联的运行时基础问题：

1. 内置更新把新版本内容写入旧版本文件名，并在成功后遗留 `.old`；版本化 EXE、失败回滚和快捷方式之间缺少完整事务。
2. DualSense backend 把“仍持有 HID handle”误当成“手柄在线”，不能可靠识别关机，也不会在同一手柄的 USB 与 Bluetooth 之间自动切换；GUI 尚未显示电量。
3. GUI 注释声称使用 Per-Monitor v2，实际只调用旧版 `SetProcessDpiAwareness(2)`，PyInstaller 构建也没有可验证的 PMv2 manifest；混合 DPI 环境可能由 Windows 位图拉伸而变模糊。

本设计不改变 Forza 遥测算法、扳机优先级、握把混音或社区默认驾驶参数。R7 只重构更新、手柄运行时状态和 Windows 显示缩放基础设施。

## 2. 已确认的产品行为

- 正式 EXE 始终使用规范文件名 `FH-DualSense-Enhanced-R<n>.exe`。
- 新版应在 30 秒内完成可运行初始化确认；确认不要求连接手柄、收到 Forza UDP 或启动游戏。
- 无快捷方式属于正常状态并静默跳过。只有发现精确匹配但迁移失败的快捷方式才提示。
- 快捷方式迁移失败时弹窗一次、写入日志并保留仍被失败快捷方式引用的旧版 EXE，后续继续修复；不会回滚已经健康运行的新版。
- 顶部 DualSense 状态 Pill 显示连接方式、电量和充电状态。电量按硬件提供的 10% 档位显示，不伪造个位数精度。
- 低电量不弹窗；仅 `10%` 电量文字变红，连接状态点仍保持绿色。充电中不标红。
- USB 与 Bluetooth 属于同一物理手柄的传输切换，始终自动完成，不受“手柄断开时自动重连”开关限制；该开关只控制完全掉线后的周期重试。
- 新传输连续检测到约 1 秒后切换；同一手柄同时存在时 USB 优先。
- R7 从旧版本首次启动时只把 `enable_reconnect` 一次性迁移为 `True`。之后用户主动关闭必须被尊重；所有驾驶体验参数保持原值。
- Windows GUI 使用完整 Per-Monitor v2 目标，并在“系统与更新”显示实际 DPI awareness 与当前缩放率，同时写日志。

## 3. 更新体系

### 3.1 后续版本采用并存提交，不再制造回滚副本

从 R7 更新到 R8 及以后版本时，旧版本化 EXE 本身就是回滚版本，不再把它改名为 `.old`：

1. 下载到 `data/updates/`，验证规范资产名、大小、MZ 头和 Release 配套 SHA-256。
2. 安装前确认应用目录可写，且没有另一个 FH-DualSense-Enhanced 实例占用同一安装目录。
3. 保留当前 `R<n>.exe`，把已验证的新版安装为旁边的规范 `R<n+1>.exe`。
4. 启动新版并等待带随机 token 的健康确认。
5. 确认成功后迁移快捷方式。
6. 没有快捷方式或全部迁移成功后删除旧版；部分迁移失败时暂时保留旧版并记录待修复状态。
7. 新版启动、初始化或健康确认失败时删除未提交的新版并重新启动原版本。

这种顺序保证安装中断或断电时，旧快捷方式和旧 EXE 仍然可以工作。正常的 R7 以后更新不创建 `.old` 或额外的完整 EXE 回滚副本。

### 3.2 R6 到 R7 的兼容引导

已经发布的 R6 内置旧 Helper；它只能把 R7 字节替换到当前 R6 路径，并生成 `R6.exe.old`。R7 代码无法改变已经分发出去的第一阶段，因此必须提供一次性的 legacy bootstrap：

1. 在任何 `cleanup_previous_update()` 或 GUI/backend 初始化之前，比较内置版本与当前 EXE 文件名。
2. 只有同时满足“内部版本为 R7 或更高、当前文件名仍是较低 R 版本、旁边存在旧 Helper 生成的 `.old`”并通过路径/PE 基础验证时，才自动进入兼容迁移。单纯由用户手工改名的 EXE 不静默重命名。
3. 当前 R7 字节使用 R7 新 Helper 执行第二阶段：退出错误命名的进程，把 R7 安装/移动为规范 `R7.exe`，同时把 `.old` 原子恢复为规范 `R6.exe`，再启动 R7 并等待健康确认。这样在确认完成前，旧快捷方式始终仍有可启动目标。
4. R7 健康后迁移所有精确指向 R6 路径的已知快捷方式。匹配数为 0 或全部迁移成功时删除恢复出的 R6；部分迁移失败时保留规范 R6 作为旧快捷方式的兼容目标，并把 transaction 留在 `cleanup_pending`，后续启动继续修复，但不回滚健康的 R7。
5. R7 启动或健康确认失败时删除未提交的 R7，保留并重新启动已恢复的真实 R6。

因此 R6 到 R7 的内置更新允许出现一次短暂的双重重启和临时 `.old`，但第二阶段必须消费该 `.old`；如果快捷方式迁移失败，留下的是规范的真实 R6，而不是 `.old`。R7 以后更新恢复单次重启。

### 3.3 持久化事务与恢复

每次安装使用唯一 transaction id，在 `data/updates/transactions/<id>/` 原子写入 journal。阶段至少包括：

- `prepared`
- `waiting_old_exit`
- `new_installed`
- `waiting_health`
- `shortcuts_migrating`
- `cleanup_pending`
- `committed`
- `rolled_back`

journal 记录旧/新绝对路径、预期版本、两端 SHA-256、发起 PID、原始启动参数、创建时间、随机确认 token 和已处理快捷方式。临时 JSON 先写同目录文件，再用 `replace()` 提交。

启动时先恢复未完成 transaction，再加载 pending Release。任何恢复逻辑都必须按 journal 阶段和哈希判断，不得只凭某个文件存在就删除。杀毒软件或 Explorer 的短暂文件锁采用有限次数退避重试；仍失败时保留可启动版本和 journal，禁止继续破坏性清理。

### 3.4 健康确认

Helper 向新版传入内部专用参数，包含 transaction id 和随机 token；原有公开 CLI 参数原样保留，内部参数不得传播到下一次普通启动。

新版通过原子 JSON 确认文件回报：

- token
- PID
- 内部 `R<n>` 版本
- 实际 `sys.executable` 路径
- EXE SHA-256
- 初始化时间

Helper 同时持有新进程 handle，验证确认内容与安装计划一致，并在确认后观察进程继续存活约 3 秒。整个确认窗口为 30 秒。GUI 的成功条件是窗口、配置体系和核心模块已能运行；TUI/headless 使用等价的模式入口确认。以下状态不导致回滚：

- 没有 DualSense
- 没有 Forza UDP
- UDP 端口已占用但 GUI 可正常显示错误
- 游戏没有启动
- 用户偏好损坏但应用已经成功显示可交互的 GUI 恢复界面

偏好损坏不能继续调用 windowed EXE 中不可见的 `input()`；必须转为 GUI 恢复流程。旧版使用同一损坏文件，因此不能把配置损坏误判为新版二进制故障。

### 3.5 快捷方式迁移

只扫描当前用户的 Windows Known Folders 和已知 pinned 目录：重定向桌面、开始菜单 Programs、任务栏 pinned shortcuts 与可识别的 ImplicitAppShortcuts。使用原生 Shell Link COM/`ctypes`，不增加 `pywin32`、`comtypes` 或 PowerShell 运行依赖。

规则如下：

- 按大小写不敏感、规范化后的绝对目标路径精确匹配旧 EXE；不修改指向 BAT、其他启动器或任意相似文件名的链接。
- 保留参数、工作目录、描述、窗口状态、AppUserModel 相关属性和图标索引。
- 如果图标路径本身精确指向旧 EXE，则同步改为新版 EXE；不能保留即将失效的旧图标路径。
- COM 保存后重新读取校验，并通过 Shell change notification 请求 Explorer 刷新。
- 匹配数为 0 时静默成功。
- 失败项有限重试；仍失败时一次性弹窗列出位置并写日志，保留旧 EXE，供后续启动再次修复。
- 任意未知目录中的用户自建快捷方式无法被完整发现，这是版本化文件名方案的固有限制，不得宣称百分百迁移。

### 3.6 多实例、权限和错误呈现

R7 不强制应用全局单实例，因为不同端口/配置的并行运行仍可能是合法用途。安装前必须检测同一安装目录内仍在运行的其他 FH-DualSense-Enhanced 进程；存在时停止安装并提示用户关闭，不能强杀。

Helper 的 `OpenProcess` 失败必须区分“PID 已退出”和“访问被拒绝”，不能一律当作已退出。已有同名目标只有在哈希与预期新版一致时才能复用，否则拒绝覆盖。

Helper 是 windowed EXE。不可恢复错误除写 `update-helper-error.log` 外，还必须使用原生 Windows 弹窗说明失败原因，并尽可能重新启动仍可用的旧版本。失败弹窗、Helper 和主 EXE 使用同一产品图标与合适的 DPI manifest。

## 4. DualSense 运行时状态

### 4.1 单一 HID 所有者与不可变快照

`DualSense` 现有 I/O 线程继续作为唯一物理 HID reader/writer。GUI、TUI、XInput bridge、电量显示和重连按钮不得另开第二个物理 handle。

新增线程安全、不可变的 controller snapshot，至少包含：

- phase：`WAITING`、`CONNECTING`、`CONNECTED`、`SWITCHING`、`RECONNECTING`、`ERROR`
- transport：`usb`、`bluetooth` 或空
- 规范化设备身份/序列号
- 最近有效输入时间与输入年龄
- battery level：`0..10` 或未知
- charging state：使用电池、充电中、已充满、异常/未知
- 最近错误摘要

`connected` 和 `transport` 的兼容属性可以由快照派生，但 GUI 不再直接用 `dev is not None` 推断在线状态。

### 4.2 输入验证、电量和在线判定

USB 与 Bluetooth 的完整输入报告无论 XInput bridge 是否启用都进入同一个 parser。XInput consumer 仍然只接收已经验证的最新状态，不改变物理 reader 所有权。

验证顺序：

1. transport 对应的 report ID 与完整长度。
2. Bluetooth 输入 report 使用 `0xA1` seed 校验末尾 CRC32。
3. 公共布局、D-pad 和状态字节合法。
4. 验证成功后才更新 `_last_input_at`、controller snapshot、电量和可选 XInput consumer。

损坏报告不能刷新在线时间。DualSense 在空闲时仍持续发送输入报告；连续约 3 秒没有有效报告时必须转为掉线/重连状态并清除旧电量，即使 Windows 仍保留陈旧 Bluetooth 枚举项或旧 handle 尚未报错。

电量读取公共 input payload 的 status 字段：低四位按官方驱动规则归一化为 `0..10` 档并显示 `0%..100%`。高四位按已验证的 DualSense charging status 映射；未知、异常温度/电压或未收到有效状态时显示“电量未知”，不能猜测。

DSX backend 没有物理 HID ACK；R7 不为了电量额外抢占 DSX 管理的手柄，DSX 模式不显示伪造电量。

### 4.3 轻量拓扑监视与身份保护

稳定连接期间约每 1 秒执行一次只读、后台的轻量 `hid.enumerate()`，只比较 VID/PID、usage、path、bus type 和已缓存身份。周期扫描不得打开设备或每秒读取 feature report `0x09`。

新路径连续两次出现后才成为稳定候选；只在新候选需要建立身份时执行一次受串行锁保护的 feature read 并缓存结果。自动传输切换必须能证明候选与当前手柄为同一身份：

- 同一手柄 USB 与 Bluetooth 同时存在时 USB 优先。
- USB 消失且同一手柄 Bluetooth 稳定存在约 1 秒时切回 Bluetooth。
- “Auto”模式在当前手柄仍在线时保持粘性；另一只 USB 手柄出现不能抢走当前 Bluetooth 手柄。
- 无法证明身份时不自动跨手柄切换；用户可在“系统与更新”显式选择或立即重连。

拓扑 absence 不能单独覆盖仍在持续收到有效输入的现有 handle，以兼容被可见性工具过滤但仍有效的句柄。HidHide 安装检测只保留为诊断信息，不再因为“检测到安装”或“自动重连关闭”永久跳过 watchdog。

### 4.4 切换、重连与输出恢复

USB/Bluetooth handover 和“立即重新连接”都作为命令投递到 HID I/O 线程，不能由 GUI 线程直接关闭 handle。切换顺序固定为：

1. 停止/清零旧 Bluetooth `0x36` 或 compatible rumble，并发送扳机释放/安全帧。
2. 关闭旧 handle，清除 transport 专属失败状态和旧电量。
3. 打开目标 transport，等待首个有效输入报告。
4. 重新排队最近一次目标 trigger、rumble、visual frame。
5. 通知 `HapticManager` 重新选择 USB audio 或 Bluetooth HD haptics。

完全找不到手柄时：`enable_reconnect=True` 按默认 5 秒间隔重试；关闭时只保留手动“立即重新连接”。同一手柄的 USB/Bluetooth handover 始终自动执行。

“系统与更新”中的原“重新连接”分组改为“连接与重连”，包含自动重连、间隔和真正的“立即重新连接”按钮。现有“重新扫描”仍只刷新手柄选择列表，不冒充重新连接。

### 4.5 R7 配置迁移

偏好文件增加独立、一次性的 R7 migration marker。读取 R6 或更早偏好且 marker 不存在时：

- 把全局 `enable_reconnect` 设为 `True`。
- 写入 migration marker。
- 不触碰任何 profile 字段、扳机/握把/红线/碰撞/抓地力/材质参数或其他 global 设置。

迁移完成后用户手动关闭自动重连必须长期保留。新安装和“恢复默认设置”同样以 `enable_reconnect=True` 为默认值。

## 5. GUI 状态与 DPI

### 5.1 顶部 DualSense 状态

顶部 Pill 只承担手柄状态，不能再被 UDP bind 错误覆盖。UDP 状态继续放在总览遥测卡和日志。

Pill 拆分为独立片段，示例：

- `DualSense · BT · 70%`
- `DualSense · USB · 充电中 70%`
- `DualSense · USB · 已充满`
- `DualSense · BT · 电量读取中`
- `DualSense · 等待连接`

连接状态点：连接为绿色，切换/重连为提示色，断开为红色。只有使用电池且电量为 `10%` 时，电量片段文字变红；不能把整个 Pill 或连接点变红。断开后不保留旧 transport、电量或充电状态。

最小窗口宽度和所有已支持语言下必须有紧凑布局；必要时顶部省略非关键长描述，而不是裁切电量或覆盖 Profile/version。

### 5.2 Per-Monitor v2 声明与运行时顺序

Windows 主 EXE 嵌入可由 CI 提取验证的 manifest：

- `dpiAwareness`: `PerMonitorV2, PerMonitor`
- 旧 `dpiAware` 提供兼容 fallback

manifest 是首选声明。源码/ZUV Windows 运行使用在 Tk/CustomTkinter 创建任何窗口前执行的 DPI bootstrap：优先 `SetProcessDpiAwarenessContext(PER_MONITOR_AWARE_V2)`，旧系统再降级到 `SetProcessDpiAwareness(2)` 与 `SetProcessDPIAware()`。

manifest 已设置时，后续 API 返回 access denied 是“模式已经确定”，不是失败；必须查询实际 process/thread/window context 后记录结果。

### 5.3 CustomTkinter 双重缩放保护

CustomTkinter 5.2.2 自带 PMv1 process call 与每窗口 DPI polling。R7 不能在未验证的情况下简单叠加 manifest。实施前必须用最小 probe 和正式 GUI 验证：

- 100%、125%、150%、175%、200% 单屏启动。
- 两块不同缩放率显示器间往返移动。
- 运行中改变 Windows scale、睡眠/唤醒、扩展坞或远程桌面导致的 DPI 变化。
- 窗口尺寸、CTk widget、字体、圆角 canvas、弹窗与标题栏是否只缩放一次。

如果 PMv2 与 `ScalingTracker` 产生重复缩放，项目统一接管 DPI 通知/缩放回调；不能用 Windows bitmap stretch 退回模糊，也不能增加第三个用户缩放滑块。

现有 `tk.Listbox`、`tk.Text` 和 `tk.Scrollbar` 不会自动跟随 CTk widget scaling，必须接入同一 DPI observer 更新字体、行高和尺寸。固定尺寸 modal、wraplength、窗口居中和 `_center_window()` 同时复核，避免物理像素与逻辑单位再次相乘或相除。

### 5.4 诊断呈现

“系统与更新”显示只读行，例如：

`DPI：Per-Monitor v2 · 150%`

日志记录 process/thread/window awareness、窗口 DPI、CTk widget/window scaling 和显示器变化。实际模式不是 PMv2 时使用黄色警告，提示检查 Windows EXE“兼容性→更改高 DPI 设置”的用户级覆盖；不自动修改注册表或兼容性设置。

## 6. 错误隔离与并发约束

- 更新、拓扑扫描和 HID I/O 不在 Tk 主线程执行；GUI 只读取不可变快照并在状态真正变化时重绘。
- 轻量拓扑扫描不得恢复曾导致页面抖动的持续路径/文件系统检测，也不得阻塞 GUI 导航。
- Controller snapshot、update transaction snapshot 和 DPI snapshot 分离。UDP 错误不能污染 controller snapshot，快捷方式失败不能把健康新版标为回滚失败。
- 更新 Helper、主应用和 shortcut migration 的日志带 transaction id；高频 HID 输入不逐帧写日志。
- 自动重连、手动重连和 transport handover 同时到达时由 I/O 线程串行化并丢弃过期命令。
- 关闭、更新重启、托盘退出和游戏关闭仍走统一退出入口；更新 transaction 只在用户完成现有未命名 Profile 提示后启动。

## 7. 预期代码边界

实施预计主要涉及：

- `packaging/windows/update_helper.py`
- `packaging/windows/fhds.spec`、Windows manifest/runtime hook 与 `packaging/windows/build_exe.bat`
- `src/main.py`
- `src/modules/update/`
- `src/modules/dualsense/main.py`、`input_state.py` 及新增状态/拓扑小模块
- `src/modules/config/settings.py`、`preferences.py`
- `src/modules/gui/main.py`、`system_tab.py`、`overview_status.py`、`widgets.py` 与原生 Tk 控件页面
- 对应 GUI/TUI 文案和 `src/lang/` 翻译
- updater、DualSense、GUI、打包契约测试

不把 update transaction、controller snapshot 和 DPI logic 塞进同一个“系统状态”类；三者生命周期、线程边界和失败语义必须独立。

## 8. 测试与验收

### 8.1 自动测试

- R6 legacy Helper 产物形态：R7 字节位于 R6 文件名、真实 R6 位于 `.old`，验证第二阶段成功和失败恢复。
- R7 以后正常并存更新：成功提交、30 秒超时、版本/哈希/token 不匹配、初始化进程提前退出。
- transaction 每个阶段模拟中断，再次启动能够恢复且至少保留一个可启动版本。
- 无快捷方式、桌面/开始菜单/任务栏多快捷方式、旧 EXE 图标路径、部分 COM 保存失败、重试后清理旧版。
- 同名新版冲突、只读目录、跨进程文件占用、另一个同目录实例、`OpenProcess` access denied。
- USB/BT 电量档位、充电/满电/未知状态、BT CRC 正确与损坏、损坏报告不刷新在线时间。
- 手柄关机、重新开机、BT→USB、USB→BT、候选抖动、多手柄、身份未知和手动强制重连状态机。
- transport 切换时旧输出静音、新连接恢复最近 trigger/rumble/visual，XInput latest-state consumer 不丢失所有权。
- 一次性 `enable_reconnect=True` 迁移只改目标 global field；后续用户关闭保留；恢复默认开启；驾驶参数逐字段不变。
- GUI controller Pill 不被 UDP error 覆盖，低电量只改变电量片段颜色，断开清除旧数据。
- CI 构建后提取主 EXE manifest，断言 PMv2、规范版本资源、图标和唯一规范 EXE 名。

### 8.2 Windows 集成与人工验证

在隔离临时目录复制 R6 Release EXE，通过真实 R6 内置更新路径升级本地 R7 构建，验证双重重启、最终文件名、`.old` 清理、设置保留和快捷方式迁移；不得拿用户日常使用目录直接做破坏性测试。

DualSense 硬件测试顺序：

1. Bluetooth 连接，确认顶部 transport、电量和低电量颜色语义。
2. 插入 USB，稳定约 1 秒后切到 USB，并确认扳机、握把触觉、灯效与 XInput bridge（若启用）恢复。
3. 拔出 USB，切回同一手柄 Bluetooth。
4. 关闭手柄，约 3 秒内转为等待且清除电量。
5. 重新开机，默认自动重连；再关闭自动重连验证只允许手动重连，但 USB/BT handover 仍自动。
6. 点击“立即重新连接”，验证不是只刷新设备列表。

触觉记录继续同时注明连接方式、Steam Input 和 Forza 游戏内振动状态。切换测试不得用游戏原生振动掩盖项目握把输出。

DPI 人工矩阵覆盖 Windows 10/11、100%–200%、混合 DPI 双屏、跨屏往返、运行中改变缩放、非拉丁语言、所有 modal、Profile/Language Listbox 和 Logs Text。使用截图和实际 DPI 日志共同判断，不能只看窗口尺寸。

### 8.3 完成门槛

- 定向测试和完整 `uv run --project src pytest -q` 通过。
- `python -m compileall -q src/modules src/lang`、`git diff --check` 通过。
- Windows R7 EXE 与 Helper 成功构建；SHA-256 sidecar 通过 `write_sha256.py --check`。
- 真实 EXE manifest、版本资源、图标、冷/温启动、退出、更新恢复与快捷方式集成验证完成。
- USB 与 Bluetooth 硬件 handover、电量、关机检测和手动重连完成。
- 未执行的 Windows 版本、多显示器、任务栏缓存或硬件组合必须明确列出，不得写成已验证。

## 9. 构建体积与供应链

R6 基线为 `51,814,190` 字节（约 `49.414 MiB`）。本设计使用标准库、Windows 原生 API 和现有 HID 输入，不引入新 runtime package 或二进制资源；预计功能代码净增加小于 `0.5 MiB`，最终 PyInstaller 波动目标控制在约 `1–2 MiB` 内。

Windows 构建不得继续依赖不可复现的任意最新临时依赖组合。PyInstaller 和运行依赖应固定到已验证版本或由仓库 lock 驱动；CI 记录最终字节数，并与 R6 基线给出绝对/百分比变化。若实测增加超过项目既有 `5 MiB` 或 `10%` 任一阈值，必须暂停并重新取得用户确认。

Release 的 EXE 与 `.sha256` 仍来自同一 GitHub Release。SHA-256 能检测传输损坏，但不能替代独立发布者签名；Authenticode 或独立公钥签名属于后续发布基础设施，本次记录为技术债，不伪装为已解决。

## 10. 本次不做

- 不接管菜单、CG、上车过场或其他 Forza 原生振动。
- 不新增 DSX 电量读取或第二物理 HID handle。
- 不自动安装、配置或修改 HidHide。
- 不强制整个应用单实例，也不强杀其他实例。
- 不添加用户自定义 UI 缩放滑块。
- 不扫描整个磁盘寻找任意位置的 `.lnk`。
- 不在 R7 引入 Authenticode 证书、独立签名服务或新的大型依赖。
- 不借连接/DPI/更新重构修改驾驶手感参数。

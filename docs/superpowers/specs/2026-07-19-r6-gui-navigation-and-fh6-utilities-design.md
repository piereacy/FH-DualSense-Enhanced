# Enhanced R6 界面切换、静默探测与 FH6 实用功能设计

日期：2026-07-19

状态：设计已确认，待实施

## 1. 背景与问题

冻结 R6 GUI 已能启动并显示 Steam/Xbox App、FH4/FH5/FH6 和 XInput bridge 状态，但真实操作暴露三个前端问题：

1. 从任意导航页切到另一页都会持续卡顿，不只发生在第一次打开长页面。
2. 总览的 Steam/Xbox App 快速入口会反复重绘或改变状态，产生可见抖动。用户怀疑程序持续探测。
3. FH6“中文文字 + 英文语音”和 FH6 DualSense/PlayStation 按键图标属于游戏实用工具，不应继续混在“系统与更新”中。

代码证据：

- `src/modules/gui/main.py::_select_nav()` 每次切页都对旧页面执行 `pack_forget()`，再对新页面执行 `pack()`。驾驶反馈和握把触觉包含大量 CustomTkinter 控件及嵌套滚动区，因此每次重新映射都会触发完整几何计算。
- `src/modules/gui/overview_tab.py::refresh()` 每秒无条件调用快速入口的多个 `configure()`，即使显示状态没有变化；Steam 未找到安装时还会每 5 秒进入一次“扫描中”展示。
- `src/modules/gui/system_tab.py` 同时承担控制器、更新、应用设置、FH6 语言文件和图标 MOD，两套 FH6 工具各自每 5 秒启动后台扫描并立即重绘状态。

## 2. 目标与成功标准

- GUI 页面只挂载一次。任何后续切换都不得 unmap/remap 整张页面，也不得重新创建设置控件。
- 导航动作只改变当前层级和按钮颜色，正常情况下不触发磁盘、注册表、HID 或网络操作。
- 快速入口只有状态真实变化时才更新控件。后台探测期间不反复改变按钮文字或布局。
- Steam 安装路径找到后停止发现；路径设置变化或已知路径失效时重新发现；未找到时只对当前选择的游戏每 30 秒静默重试。
- 每秒精确进程检测可以保留，但只读取进程列表，且结果未变化时不刷新 Tk 控件。
- 新增独立“FH6 实用功能”页面，只包含 FH6 语言工具和 FH6 DualSense/PlayStation 按键图标工具；“系统与更新”彻底移除这两项。
- GUI 与 TUI 保持相同的信息架构和功能入口。
- `preferred_forza_platform` 的源码默认、无效值回退和恢复出厂值均固定为 `steam`。

## 3. 不在本次范围

- 不改变任何遥测、扳机、握把触觉、灯效、XInput 映射或 Bluetooth HID 协议。
- 不改变 Steam/Xbox App 的启动 URI、AUMID 和 product ID。
- 不增加 Xbox App 安装目录自动发现。
- 不在本轮实现 FH6 游戏语言、实际文字语言和语音语言的三行前端；既有后端摘要继续保留。
- 不重做主题、字体、卡片视觉或导航宽度。
- 不把 FH6 工具扩展到 FH4/FH5。

## 4. 方案比较与选择

### 方案 1：页面一次挂载，切换只 raise，配合差异渲染

所有页面在内容容器同一网格单元中完成一次 `grid()`，之后使用 `tkraise()` 切换。快速入口把控件展示压缩为可比较的不可变状态，只在状态变化时调用 `configure()`。这是选定方案。

优点：直接消除重复几何计算；切页路径为常数次操作；不改变页面实例、Settings 引用和现有 refresh callback；测试边界清晰。

代价：所有页面继续在启动时创建，占用与现状相同的控件内存；启动时会完成一次整体布局。

### 方案 2：首次打开时延迟创建，之后缓存

首次选择页面时才实例化并永久缓存。

优点：初始启动更轻。

缺点：第一次进入每页仍会卡；翻译刷新、后台 worker、退出清理和页面依赖需要新的生命周期状态；不符合用户“每次都卡”的首要问题。

### 方案 3：保留 pack/unpack，只减少探测

仅优化扫描和无变化重绘。

优点：改动最小。

缺点：长页面每次仍会重新布局，不能解决主要症状。

## 5. GUI 页面生命周期

`TriggerGUI._build_body()` 创建 `_tab_frames` 后：

1. 为 `_content` 配置单一可伸缩 row/column。
2. 每个页面只执行一次 `grid(row=0, column=0, sticky="nsew", padx=..., pady=...)`。
3. `_select_nav(key)` 不再调用 `pack_forget()` 或 `pack()`，只更新旧/新导航按钮颜色并调用目标页面 `tkraise()`。
4. 可选页面钩子统一为 `on_hide()` 和 `on_show()`。没有钩子的页面不需要适配；钩子不能执行阻塞工作，只能安排后台扫描或刷新已有状态。

所有页面仍共享同一个 `Settings`、backend、UDP listener、日志队列和更新服务。该调整只改变视图映射，不建立第二套页面或业务状态。

滚轮仍由根 `WheelRouter` 根据当前最上层窗口命中目标。隐藏在下层的已映射页面不得接收滚轮；需要增加回归测试证明 wheel target 只来自当前 raised 页面。

## 6. 快速入口的探测状态机

### 6.1 Steam 安装发现

只处理当前选择的游戏。每代继续保留：

- 已验证 `ForzaInstall`。
- 当前设置中的 path hint。
- 最近一次发现时间。
- 当前 worker serial。
- 是否已经得到首次结果。

触发发现的条件只有：

1. 当前选择 Steam，且该代还没有首次结果。
2. 首次结果为未找到，距上次完成至少 30 秒。
3. 对应 `fh4_install_path`、`fh5_install_path` 或 `fh6_install_path` 与缓存 hint 不同。
4. 已知根目录在显式启动前重新验证失败，或运行中的精确 EXE 路径证明游戏已移动。

一旦发现有效根目录，周期发现停止。只要路径设置与已验证根一致，就不再枚举 registry、Steam libraries 或 manifest。切换到另一代只扫描新选择，不顺便扫描其余两代。

未找到后的 30 秒重试是静默的：第一次尚无结果时可以显示“正在查找”；已经显示“未找到”后，后台重试不得把按钮改回“正在查找”。只有从未找到变成已安装、路径改变、运行状态改变或发生实际错误时才改变展示。

### 6.2 Xbox App 与进程检测

Xbox App 模式不做 Steam 安装发现。AUMID 枚举仍只在用户点击启动时执行，不变成周期任务。

每秒的 `is_forza_game_running()` 精确进程检测保留，用于启动中、运行中和退出状态。它只读取进程列表，不扫描安装路径。检测结果未变化时不重新配置按钮或 selector。

### 6.3 差异渲染

快速入口把以下内容组成稳定 presentation tuple：

- 平台。
- 游戏键。
- 主按钮文字和 enabled 状态。
- 游戏 selector enabled 状态。
- 平台 selector enabled 状态。
- XInput bridge 可见状态、提示和动作类型。

只有 tuple 与上一次不同才调用对应控件的 `configure()`、`grid()` 或 `grid_forget()`。Bridge action 不得每秒先 `grid_forget()` 再重新 `grid()`；只有动作类型从有到无、从无到有或类型改变时才调整布局。

## 7. “FH6 实用功能”页面

### 7.1 GUI

新增独立页面类和导航项：

- 导航中文：`FH6 实用功能`。
- 英文：`FH6 utilities`。
- 日语及其余 catalog 同步增加翻译。
- 导航位置：`系统与更新`之后、`语言`之前。

页面只包含：

1. `FH6 中文文字 + 英文语音` 卡片，沿用现有内容识别、确认、游戏关闭检查、三步 rename 与恢复逻辑。
2. `FH6 DualSense/PlayStation 按键图标` 卡片，沿用现有哈希、双目标备份、安装、还原、运行中拒绝和 `@hotline1337` Nexus 鸣谢。

`SystemTab` 移除这两个卡片、相关字段、timer 和 worker，只保留控制器选择、更新与应用级设置。业务实现仍位于 `modules/forzahorizon/fh6_language.py` 和 `controller_icons.py`，不能复制到 GUI 类。

### 7.2 页面扫描

FH6 工具页不再永久每 5 秒读取两个文件集：

- 首次显示页面时后台检查一次。
- 用户点击重新扫描、选择目录、完成安装/还原/语言操作后立即检查。
- 未发现有效路径时，页面保持可见期间每 30 秒静默重试。
- 已发现有效路径后停止路径发现；只用轻量进程检测更新“请先关闭 FH6”状态。
- 页面隐藏时停止周期重试；再次显示时比较 path hint，只有变化、未找到或显式请求才重新检查文件。

状态 worker 继续遵守 Tk 主线程边界；过期 serial 或旧平台结果不得覆盖当前页面。

### 7.3 TUI

Textual 增加同名独立 tab/screen，并把现有 FH6 语言和图标区块及 worker 从 `SystemTab` 移入。TUI 原有 `on_show()`/worker group 语义继续使用；System 页不保留重复入口。

## 8. 默认平台与测试配置

- `Settings.preferred_forza_platform` 保持 `"steam"`。
- `normalize_forza_platform()` 对未知值回退 Steam。
- 恢复出厂设置继续从新的 `Settings()` 重建 globals，因此必须回到 Steam。
- 测试时切到 Xbox App 产生的 `packaging/windows/dist/data/user_preferences.json` 只是本机构建旁配置，不得打进 EXE、不得上传到 Release；冻结验收结束前恢复 Steam 或删除该测试数据目录后重新启动确认。

## 9. 错误处理与线程边界

- 安装发现、文件检查和 AUMID 枚举继续在 worker 中执行。
- Tk 控件只由主线程更新。
- worker 失败只更新对应稳定错误状态，不让导航卡死，也不每个 tick 重复记录同一异常。
- 页面隐藏或选择变化后返回的旧结果按 serial 丢弃。
- 路径探测失败不影响 controller backend、XInput bridge、UDP、触觉或更新服务。
- `tkraise()` 失败或目标 key 非法属于程序错误，记录并保持当前页面，不静默回退到另一页。

## 10. 测试与验收

### 10.1 自动测试

- 全部 GUI 页面只挂载一次，`_select_nav()` 使用 `tkraise()`，不包含 `pack_forget()` 或重复 `pack()`。
- 连续切换任意两个页面不会重新创建控件或改变 Settings。
- wheel routing 不会命中被覆盖的下层页面。
- presentation tuple 未变化时，不调用按钮、selector 或 bridge action 的 `configure/grid/grid_forget`。
- 首次 Steam 扫描立即执行；找到后在任意时钟推进下都不再执行。
- 未找到时，29.999 秒不重试，30 秒后只对当前游戏重试。
- 静默重试期间保持“未找到”文案，不闪回“正在查找”。
- path hint 改变会失效旧结果并立即重新扫描；旧 serial 结果被丢弃。
- Xbox App 模式不启动 Steam 发现；AUMID 仍只在显式启动调用。
- System 页源码与挂载测试不再包含 FH6 语言或图标卡片；FH6 实用功能页恰好包含这两项。
- GUI/TUI 导航和全部语言 catalog 都存在 `FH6 utilities`。
- `Settings()`、非法平台归一化和恢复出厂均为 Steam。

### 10.2 冻结 GUI 验收

- 连续在总览、驾驶反馈、握把触觉、灯效、配置、系统、FH6 实用功能、语言、日志和关于之间往返，页面不出现可感知的重复布局停顿。
- 在总览停留至少 35 秒：已找到路径时没有新发现；未找到时发生一次静默重试但按钮不抖动。
- Steam/Xbox App selector、FH4/FH5/FH6 selector、更新白点和 XInput 状态在不变化时保持稳定。
- FH6 两项工具只出现在新页面，系统页没有重复入口。
- 默认或恢复出厂后平台显示 Steam，Xbox 虚拟 target 不存在。
- 滚轮、退出保存提示和关于页链接继续工作。

### 10.3 完成前检查

运行定向测试、完整 `pytest`、`compileall`、lock check、`git diff --check`，重新构建 Windows EXE 并复核 sidecar、版本、体积、冻结 GUI 与默认 Steam。更新老三样、`docs/PROJECT_STATE.md`、三语 README 中的工具入口位置和双语 Release 正文。

## 11. 发布边界

本调整属于 Enhanced R6 收尾，不创建新的 `R7` 版本。最终构建继续命名 `FH-DualSense-Enhanced-R6.exe`。如果代码或资产使最终 EXE 超过既有 `52 MiB` 停止线，仍需暂停发布并重新确认；纯界面代码预计不会触发该门槛，但必须以真实构建为准。

# Enhanced R4 单一 Console、配置持久化与关键交互设计

日期：2026-07-16

状态：用户已确认设计，尚未实现

适用版本：FH-DualSense-Enhanced R4

## 1. 背景

Enhanced R4 当前生产代码包含 Miku Console、Miku Stage 和 Miku Studio 三种构建时 GUI 壳层。用户完成对比后选择 Miku Console 作为唯一正式前端，Stage 和 Studio 只用于方案评审，不进入最终产品。

当前代码还有四个需要在 R4 发布前解决的交互问题：

1. `src/modules/gui/widgets.py` 的 `FastScroll` 覆盖 CustomTkinter 私有 `_mouse_wheel_all`，但子控件事件经常不能通过 canvas 归属判断，导致用户只能拖动滚动条。`src/modules/gui/controls_tab.py` 还把全部开关卡片直接压入固定高度的两列网格，没有垂直滚动容器；新增开关后，在 DPI 缩放窗口中会裁掉卡片底部。
2. `src/modules/config/preferences.py` 虽然会把每次设置修改写入活动 Profile，却在每次启动时重新生成 `Default`，因此 Default 不能作为持久化工作配置。
3. 软件没有集中判断本次 Default 修改是否值得另存为命名 Profile，也没有覆盖窗口、托盘、游戏关闭和更新安装的统一退出确认流程。
4. 更新器状态只能在总览和“系统与更新”页面中看到，左侧导航没有新版本提醒。

本设计还加入首次启动按 PC 显示语言自动选择界面语言的行为。所有决定均以当前 `Settings`、Profile、GUI、更新器和打包代码为基础，不改变扳机、握把、灯效、UDP 或 DualSense HID 算法。

## 2. 目标

- R4 只保留一个 Miku Console GUI 和一个 Windows EXE。
- 所有长页面在鼠标位于其任意子控件上时都能用滚轮滚动。
- 页面内容超过可用高度时必须进入滚动区域，不能通过压缩卡片高度隐藏开关；窄窗口下允许从两列响应为单列。
- Default 成为跨启动持久化的工作 Profile，参数继续即时自动保存。
- 本次运行中修改 Default 的 Profile 参数后，所有正常 GUI 退出路径都提示用户可选另存命名 Profile。
- 用户不必改名，保存输入框默认提供下一个可用的 `profileN` 名称。
- 出厂默认参数始终由代码持有，完整恢复不会删除命名 Profile。
- 首次启动和完整恢复时根据 PC 显示语言选择界面语言，之后尊重用户手动选择。
- 有新版本待处理时，“系统与更新”导航旁持续显示小白点。
- 保持旧命名 Profile、分享码和旧配置迁移兼容。

## 3. 非目标和边界

- 不重新设计 Miku Console 的颜色、卡片或页面内容。
- 不修改触觉、扳机键、灯效、USB、Bluetooth 或 DSX 输出。
- 不删除 ZUV、Linux、TUI 或 headless 启动方式，但 Windows 内置更新仍只支持冻结 EXE。
- 不承诺在任务管理器强制结束、进程崩溃、断电或操作系统强制终止时显示保存弹窗。Default 的即时自动保存负责尽量降低这些场景的数据损失。
- 不删除用户的命名 Profile，也不让“还原默认设置”覆盖它们。
- 不在这次工作中实现更新器 24 小时节流、代码签名或应用内 Release 正文。

## 4. 单一 Miku Console 产品

### 4.1 源码

- 删除 Stage、Studio 和构建时前端选择机制。
- 删除 `src/modules/gui/variants.py`。
- `TriggerGUI` 直接使用当前 Console 的完整左侧文字导航、204 px 侧栏和 1040 px 基准窗口宽度。
- 窗口标题只显示项目名称，不再附加方案名称。
- 删除 `FHDS_UI_VARIANT` 和 `FHDS_BUILD_VARIANT` 的运行、文档和测试入口。
- 删除冻结包内的 `data/ui_variant.txt`。

### 4.2 构建和更新

- Windows 唯一产物为 `FH-DualSense-Enhanced-R<n>.exe`。
- 构建脚本只构建一次主程序，但仍先构建并内置 `FH-DualSense-Update-Helper.exe`。
- Release 同时提供 `FH-DualSense-Enhanced-R<n>.exe.sha256`。
- 更新器移除 `variant` 参数和三方案资产表，只接受标准单一 EXE 与其 `.sha256`。
- 本地三方案候选产生的旧待安装元数据若不符合新标准文件名，应按无效缓存安全丢弃。
- GitHub workflow、README、语言文档、AGENTS、架构和项目状态删除三方案发布说明。

R4 尚未公开发布，因此不提供 Miku Stage 或 Miku Studio 的更新兼容层，也不存在已发布 R4 用户被跨方案替换的问题。

## 5. 配置模型

### 5.1 出厂默认、Default 和命名 Profile

三种概念必须分离：

- 出厂默认：由 `Settings()` 中的代码值定义，不写成可被用户覆盖的 Profile 基线。
- Default：用户的持久化工作 Profile。GUI 修改继续立即写入它，重新启动后保留。
- 命名 Profile：用户主动保存的长期快照，继续支持加载、重命名、删除和分享码。

`preferences.load()` 不再在每次启动时用 `Settings()` 覆盖磁盘中的 Default。首次创建文件时才用出厂默认建立 Default。现有命名 Profile 和 globals 的迁移逻辑继续执行。

### 5.2 ProfileSession

新增轻量会话状态对象，职责仅限 GUI 退出判断，不改变配置文件 schema。它保存：

- GUI 启动时 Default 的 Profile 字段快照。
- 当前活动 Profile 名称。
- 最近一次严格写入错误状态。

判定“本次 Default 有未命名修改”必须同时满足：

1. 当前活动 Profile 是 `Default`。
2. 当前 `preferences._profile_fields(settings)` 与 GUI 启动时保存的 Default 快照不同。

这样具有以下语义：

- 用户本次没有修改参数时不重复提醒。
- 用户把所有参数手动调回启动值时不提醒。
- global fields 不参与比较，因为命名 Profile 不保存它们。
- 当前使用命名 Profile 时不提醒，因为修改已经自动写入该命名 Profile。
- 成功另存命名 Profile 后活动 Profile 随现有逻辑切换到新名称，因此不再满足提醒条件。
- 用户选择直接退出时，不另存命名 Profile，但已经自动写入 Default 的参数继续保留到下次启动。
- 完整恢复属于用户明确操作，完成后重新接受当前 Default 快照，不触发退出提醒。

不把临时 dirty 字段写入 `user_preferences.json`，避免进程崩溃留下永久提醒状态。

## 6. 系统显示语言

新增无 GUI 依赖的语言检测函数，并允许测试注入原始 locale 值。

Windows 优先读取用户显示语言，而不是键盘布局或数字格式。Windows API 失败或非 Windows 环境使用 Python locale 后备。规范化映射如下：

| 系统语言 | 应用语言 |
| --- | --- |
| 简体中文、中国大陆、新加坡、Hans | `zh` |
| 繁体中文、台湾、香港、澳门、Hant | `zh_tw` |
| 日语 | `ja` |
| 德语 | `de` |
| 俄语 | `ru` |
| 土耳其语 | `tr` |
| 其他或检测失败 | `en` |

检测只在以下两种情况发生：

1. 第一次创建有效配置文件。
2. 用户确认执行完整“还原默认设置”。

已有配置升级时不覆盖 `globals.language`。用户首次启动后手动选择的语言继续持久化并优先于系统语言。

## 7. 完整还原默认设置

总览页快捷入口、Profiles 页面和握把调校页现有按钮必须调用同一个中央恢复操作，不能各自实现不同语义。

恢复前显示模态确认，明确说明：

- 当前 Profile 参数与所有 global fields 都会恢复。
- 活动 Profile 将切回 Default。
- 命名 Profile 不会删除。
- 语言会恢复为当前 PC 显示语言。

确认后的数据流：

1. 读取当前配置并保留所有非 Default 命名 Profile。
2. 用 `Settings()` 构造新的 Profile 默认值和 global 默认值。
3. 用系统语言检测结果覆盖新 globals 的 `language`。
4. 将新 Default、保留的命名 Profile、全新 globals 和 `active_profile=Default` 组成完整配置。
5. 在覆盖前备份现有配置。
6. 通过 `.tmp` 和原子 replace 写入。
7. 只有写入成功后才原地更新运行中的 `Settings`。
8. 刷新全部设置控件、Profile 列表、标题状态和会话基线。
9. 提示用户重启后让语言、UDP 绑定、DSX 和其他后端级设置完全生效。

若备份或原子写入失败，保持磁盘配置和运行中 `Settings` 不变，并显示错误，不得呈现“恢复成功”。

## 8. 统一关闭协调器

所有正常 GUI 关闭请求统一进入 `request_close(reason, before_exit=None)`，包括：

- 窗口关闭按钮。
- 托盘菜单退出。
- 游戏进程关闭后的自动退出。
- 遥测超时退出。
- 更新器“重启并安装”。

`request_close` 必须防止并发弹出多个模态窗口，也不能在已经 teardown 后重复执行。

### 8.1 无未命名修改

直接执行对应的退出前操作，然后调用现有 teardown 和窗口销毁。

### 8.2 有未命名修改

若主窗口隐藏在托盘，先恢复并置前，然后显示模态保存窗口。窗口包含：

- 说明文字。
- Profile 名称输入框。
- “保存为命名配置并退出”。
- “直接退出”。
- “取消”。

名称默认使用第一个可用的 `profileN`，从 `profile1` 开始。用户可修改。若用户输入已存在的名称，不覆盖原 Profile，而是沿用现有唯一命名规则生成可用名称。

按钮行为：

- 保存为命名配置并退出：严格写入命名 Profile，确认磁盘写入成功后退出。
- 直接退出：不另存命名 Profile，Default 的即时保存结果继续保留，然后退出。
- 取消：关闭模态窗口并取消整个关闭请求。

### 8.3 更新安装

更新 Helper 不能在保存决策前启动。正确顺序为：

1. 用户点击“重启并安装”。
2. 进入统一关闭协调器。
3. 用户保存、直接退出或取消。
4. 只有保存成功或直接退出后，才调用 `install_on_exit()`。
5. Helper 调度成功后再 teardown 主程序。
6. Helper 调度失败时保持程序运行并显示错误。

## 9. 页面溢出、响应式网格与鼠标滚轮

### 9.1 页面溢出和响应式网格

“驾驶反馈”页的标题保留在页面顶部，标题下方改用 `FastScroll` 承载开关卡片。卡片按自身内容决定最小高度，不再通过 `grid_rowconfigure(weight=1)` 把三行内容压进固定可见高度。

布局规则：

- 内容宽度足够时保持当前两列卡片布局。
- 内容宽度不足以容纳两张可读卡片时切换为单列。
- 列数切换只重新排列现有卡片，不重新创建开关，也不触发设置回调。
- 卡片标题、所有开关和底部留白都必须位于滚动画布的 scrollregion 内。
- 页面改变尺寸或 Windows DPI 导致逻辑宽度变化时重新计算列数，并对连续 `<Configure>` 事件做合并，避免反复抖动。
- 不修改当前 Per-Monitor v2 DPI awareness、CustomTkinter scaling 或全局字体倍率；截图中的裁切根因由页面布局处理，而不是用缩小字体掩盖。

除“驾驶反馈”外，需要审计总览、Profiles、系统、语言、日志和灯效页面。任何自然内容高度可能超过可用区域的页面都必须使用同一滚动边界，不能依赖默认 700 px 逻辑窗口高度碰巧容纳。

### 9.2 鼠标滚轮路由

不再覆盖 CustomTkinter 私有 `_mouse_wheel_all`。GUI 根窗口安装一个滚轮路由器，并维护已注册的 `FastScroll` 容器。

每次事件发生时：

1. 根据鼠标屏幕坐标找到当前指针下的 Tk widget。
2. 从该 widget 向父级查找最近的已注册滚动容器。
3. Windows 处理 `<MouseWheel>`；Linux 处理 `<Button-4>` 和 `<Button-5>`。
4. 默认执行纵向滚动，不把滚轮交给滑块修改参数。
5. 若最近的内层容器仍可向目标方向滚动，则滚动内层。
6. 若内层已到达该方向边界，则继续查找并滚动外层容器。
7. 没有可滚动祖先时不消费事件。

滚动单位需规范化，避免 Windows 标准滚轮一次跳过大段内容，同时允许触控板连续事件自然移动。容器销毁时必须注销，防止保存已销毁 widget 引用。

## 10. 更新导航白点

Console 左侧“系统与更新”导航按钮右侧增加独立的 6 px 白色圆点。它是更新状态标记，不是一次性已读通知。

显示规则：

- 已发现新 Release 时显示。
- 下载、校验和等待重启安装期间继续显示。
- 下载失败但快照仍携带已确认的新 Release 时继续显示。
- 仅网络检查失败且从未确认新 Release 时不显示。
- 检查结果为当前最新或安装后当前版本不再落后时消失。
- 用户仅进入“系统与更新”页面不会清除白点。

实现应根据不可变 `UpdateSnapshot` 派生可见性，不能引入另一个需要持久化的“已读”状态。

## 11. 写入错误处理

当前 `_write()` 只记录错误，部分调用方无法判断是否真的保存。本次需要为严格操作提供明确结果，同时保留普通 UI 自动保存不崩溃的原则。

- 底层原子写入提供可检查的成功或失败结果。
- 普通自动保存失败时记录日志并显示用户可见提示；Default 会话比较仍能发现当前内存值与启动快照不同。
- 关闭弹窗的命名保存必须使用严格结果，失败时保持窗口和程序运行。
- 完整恢复必须使用严格结果，失败时不得更新内存状态。
- 更新 Helper 调度失败时不得退出主程序。
- 配置损坏时继续沿用现有备份和显式恢复流程。

## 12. 测试设计

### 12.1 配置和 Profile

- Default 在连续两次 `load()` 间保留修改。
- 首次创建 Default 仍来自当前 `Settings()`。
- 命名 Profile、迁移、导入、导出和分享码 round-trip 保持通过。
- ProfileSession 只在活动 Default 且本次 Profile 字段变化时返回需要提醒。
- global-only 修改不触发提醒。
- 参数调回启动快照后不触发提醒。
- 完整恢复重建 Default 和 globals、切换活动 Profile并保留命名 Profile。
- 恢复写入失败时不改变运行中 Settings。

### 12.2 语言

- 覆盖简体中文、繁体中文、香港、澳门、日语、德语、俄语、土耳其语和未知语言映射。
- Windows API 失败时验证 locale 后备。
- 已有用户语言不被启动检测覆盖。
- 完整恢复重新采用系统显示语言。

### 12.3 关闭流程

- 窗口、托盘、游戏关闭、遥测超时和更新安装都经过同一个协调器。
- Default 无变化时不弹窗。
- 三个按钮分别验证严格保存、直接退出和取消。
- 默认名称按 `profile1`、`profile2` 顺序选择。
- 保存失败不退出。
- 更新安装在取消时不调度 Helper，在确认后才调度。
- 托盘隐藏状态先恢复窗口再显示模态弹窗。

### 12.4 滚轮和更新提示

- 驾驶反馈页在内容高于窗口时显示完整 scrollregion，最底部开关可滚动到可见位置。
- 宽内容区保持两列，窄内容区切换单列，尺寸变化不重复创建控件或触发设置保存。
- 在 100%、125% 和 150% DPI 的逻辑尺寸模拟中，卡片不被固定网格裁切。
- 子控件上的滚轮事件能滚动所属页面。
- 内层可滚动时优先内层，到达边界后转交外层。
- Windows 和 Linux 事件归一化可测试。
- 滑块不接收滚轮数值修改。
- 更新白点覆盖 AVAILABLE、DOWNLOADING、VERIFYING、READY、ERROR-with-release、ERROR-without-release 和 UP_TO_DATE。
- 进入系统页不改变白点。

### 12.5 构建和契约

- 生产源码、自动测试、活跃用户文档和 workflow 不再依赖 Stage、Studio 或 GUI variant 环境变量；历史设计记录可以注明这些方案已淘汰，但不得继续把它们描述为可构建产品。
- PyInstaller spec 只生成 `FH-DualSense-Enhanced-R<n>.exe`。
- 构建仍内置更新 Helper、许可证和第三方声明。
- `.sha256` 与唯一 EXE 匹配。
- 更新器只接受标准单一资产名称。

## 13. 验收

实现完成后必须执行：

1. 与配置、关闭、滚轮、更新器和打包最相关的定向测试。
2. `uv run --project src pytest -q`。
3. `python -m compileall -q src/modules src/lang`。
4. `git diff --check`。
5. 构建唯一 Windows R4 EXE。
6. 检查 EXE 文件名、版本资源、Helper 内置状态和 SHA-256。
7. 在 Windows 100%、125% 和 150% DPI 下手动验证所有长页面不裁切，并验证两列/单列响应和嵌套滚动。
8. 手动验证三个恢复入口。
9. 手动验证保存命名、直接退出和取消。
10. 手动验证窗口关闭、托盘退出、自动退出和更新安装顺序。
11. 手动模拟更新快照，验证导航白点持续与消失规则。
12. 启动和正常退出冒烟，确认没有 crash log 或残留进程。

涉及的长期边界变化需同步“老三样”中的 `AGENTS.md`、`docs/ARCHITECTURE.md` 和 `docs/DECISIONS.md`；阶段、测试、构建和工作区状态另行同步 `docs/PROJECT_STATE.md`。README、三语言说明和 Release body 必须改为单一 Console/单一 EXE。

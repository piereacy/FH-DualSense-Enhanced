# 项目决策记录

本文记录会影响后续开发方向、但不适合塞进架构说明的关键决定。新决定应注明日期、状态、原因和后果；已被替代的决定保留并标注替代关系。

## 2026-07-17：Enhanced R5 总览使用真实运行时状态，不再保留静态占位

- 状态：生产代码与定向自动测试已实现；源码 GUI 视觉冒烟和冻结 EXE 验收待执行。
- 背景：Enhanced R4 总览的四张状态卡虽然有 `refresh()`，但只在设置刷新链路触发，GUI 每秒 tick 没有调用，因此控制器、遥测、Profile 和更新状态经常停留在初始化占位值。UDP listener 也没有可供 UI 安全读取的数据包计数、来源和最后接收时间。
- 决定：`UDPListener` 维护只统计 324 字节有效包的线程安全不可变快照；总览用纯 presentation 层组合 backend、遥测、Profile 和更新快照。页面创建后立即刷新，运行期间每秒刷新。DSX 必须明确说明 fire-and-forget UDP 无 ACK，不能把 socket 打开写成手柄已确认连接。
- 错误边界：启动错误保存为运行时事实，不能被下一次普通状态 tick 覆盖。H1 只显示“后端错误”“UDP 绑定失败”“更新失败”等短文案，具体异常放在提示和日志。
- 后果：更新卡覆盖自动检查等待、检查关闭、检查中、最新、可用、下载百分比、校验、待安装、安装和失败；Profile 读取失败有显式状态，不再回退到 `-`。

## 2026-07-17：FH6 中文文字 + 英文语音只允许用户确认后的同目录改名

- 状态：Windows Steam 路径发现、内容识别、启用/还原/显式修复、GUI/TUI 控件和自动测试已实现；真实游戏文件的按钮改名尚未执行。
- 背景：FH6 的 `media/Stripped/StringTables/CHS.zip` 保存中文文字，`EN.zip` 保存英文内容；在 Steam 游戏语言为 English 时交换两者名称可得到中文文字与英文语音。用户安装盘符和 Steam 库位置不固定，不能使用某台机器的 `C:\Program Files (x86)` 路径。
- 决定：只支持 Windows Steam FH6。自动流程通过 Steam registry、`libraryfolders.vdf`、App ID `2483190` manifest、卸载信息或精确游戏进程路径发现安装，并缓存已验证根目录为 global 设置。手动选目录保留为兜底。所有启动和刷新扫描只读，功能必须由按钮触发并确认，绝不自动交换。
- 安全门禁：操作前按 ZIP 内 `.str` 内容识别中文/英文，检查 Steam English、FH6 已关闭、目标目录和每一步源/目标存在性。启用和还原使用 `CHS -> temp -> EN` 的三步同目录 rename，并在进程内失败时逆序回滚；不复制文件、不创建永久备份、不静默提权。
- 崩溃恢复：temp 残留只报告“交换中断”。只有恰好两份可识别中英文文件时才显示修复按钮，仍需用户确认；不自动修复、覆盖或删除。Steam 更新或验证文件恢复原包后，重新检测应自然显示原始状态，不自动重新启用。
- 界面边界：GUI 用 modal 确认并把磁盘操作放到 worker thread；TUI 用二次按键确认。Steam manifest 明确为其他语言时按钮禁用，未知时允许额外确认；非 Windows 运行时只显示不可用。

## 2026-07-17：总览只通过 Steam 显式启动已验证的 FH6

- 状态：生产代码、六种翻译和定向自动测试已实现；源码与冻结 EXE 的真实 Steam 启动冒烟待执行。
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

## 2026-07-16：Windows 独立 EXE 使用内置更新器，ZUV 保留为可选入口

- 状态：查询、下载、校验、待安装恢复、Helper 替换/回滚、GUI/TUI 控件和自动测试已实现；真实已发布 R4 到 R5 的端到端更新尚无法执行。
- 背景：只下载 EXE 的用户不应再为了更新安装 Python、uv 或理解 ZUV；Windows 运行中的 EXE 又不能可靠地自行覆盖。
- 决定：仅冻结后的 Windows EXE 启用内置更新。它只接受仓库稳定 `R<n>` Release 中的 `FH-DualSense-Enhanced-R<n>.exe` 和同名 `.sha256`，以 `.part` 下载并检查长度、SHA-256、`MZ` 头。用户确认后由内置的独立 Helper 等待旧 PID、生成 `.old`、替换、重启，并在失败时回滚。
- 边界：源码、Linux 和 ZUV 运行不执行 EXE 自替换；不静默提权。ZUV 和 `win_start.bat` 继续保留，作为兼容、开发和网络备用入口，而不是 R4 独立 EXE 的依赖。
- 已知差距：当前每次启动约 10 秒后检查一次，尚无跨启动 24 小时节流；只检查 `MZ` 头而未解析 PE 版本资源，也没有代码签名信任链；这些不能在文档中写成已实现。

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

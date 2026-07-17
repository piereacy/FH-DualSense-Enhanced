# 项目当前状态

## 状态快照

- 最后更新：2026-07-17，Asia/Shanghai。
- 仓库：`piereacy/FH-DualSense-Enhanced`。
- 当前工作树：`work/hamza`。
- 当前分支：`main`。完整 R5 已提交为 `b2569d4`；远端新增的 `324c6d8` README 调整已通过合并提交 `cae277b` 保留并整合。当前相对 `origin/main` 领先 5 个提交，尚未推送。
- 当前开发身份：`src/pyproject.toml` 内部 PEP 440 版本 `5`，开发名称 `Enhanced R5`；当前公开稳定名称仍为 `Enhanced R4`。
- 当前公开稳定版：[`FH-DualSense-Enhanced R4`](https://github.com/piereacy/FH-DualSense-Enhanced/releases/tag/R4)，发布时间 `2026-07-17T07:33:04Z`；`R4` tag 指向 `e7184c2`，`main` 在其后一个仅含发布状态交接的提交 `16ba4e4`。
- GitHub 仓库已经脱离原项目 fork network；GitHub API 已确认 `isFork=false`、`parent=null`，原有 R1/R2/R3 Release 和 2 个 Star 均保留。
- 当前阶段：Enhanced R5 的总览运行时状态、FH6“中文文字 + 英文语音”、总览 Steam 启动按钮和新产品图标已完成本地实现与验证。真实 Steam 启动已进入 FH6 画面，最终冻结 R5 EXE 已重建并通过资源、哈希和启动校验；没有 tag、Release 或推送。
- 发布后校验缺陷已经修复：首次 R4 CI 因 runner 缺少 `Get-FileHash` 生成了不完整 sidecar；该 Release 已删除并在修复提交上重建，最终线上 `.sha256` 为 95 bytes 且与 EXE 精确匹配。

## 当前开发重心

Enhanced R5 的三项已批准功能、新产品图标和最终冻结构建验收已经在本地完成。用户已明确批准稳定版发布，当前重心是提交前范围审查、推送、`workflow_dispatch stable` 和线上资产复核，不再扩展功能。R3/R4 的 R2 扳机键油门手感差异仍是独立待办：在调整触觉默认值前，必须完成同条件实机 A/B 和最终 trigger frame 来源追踪，不能因为本轮 R5 状态/UI 工作而把该问题写成已解决。

## 最近完成的功能

以下内容已经有生产代码和自动测试：

### R5 总览运行时状态

- `src/modules/gui/overview_status.py` 将手柄、Forza 遥测、当前配置和更新器的运行时快照映射为稳定的卡片标题与详情，GUI 不再显示“等待中”“空闲”等无功能占位文本。
- 手柄卡片区分 USB、Bluetooth、断线等待、DSX、初始化错误和后端不可用；遥测卡片区分启动、等待、接收、丢失和 UDP 绑定错误，并显示有效包计数、来源或静默时间。
- 当前配置卡片明确显示 `Default` 或命名 Profile；更新卡片区分源码运行方式不可用、等待自动检查、已禁用、检查/下载/校验/安装阶段、进度与错误。
- `UDPListener` 只把 324-byte 有效包计入快照，线程安全地记录阶段、计数、最后包时间和来源；队列 drain 会保留最后一个有效包，即使其后跟有无效报文。原有静默警告和退出策略未改变。
- GUI 创建总览页后立即刷新，并由主循环每秒刷新；TUI 和主窗口会保留后端/UDP 错误，不再被下一次普通状态刷新覆盖。

### 总览 Steam 启动 FH6

- 总览快捷入口新增跨两列“启动 FH6”按钮，只在 Windows Steam 安装已验证且精确 `ForzaHorizon6.exe` 未运行时启用；点击后重新验证并通过 `steam://run/2483190` 交给 Steam，不直启 EXE，也不触碰语言 ZIP。
- 安装发现和启动请求使用 worker 结果队列，由 GUI 主线程每秒消费，修复了主循环启动前 worker 回调可能永久停在“正在查找 FH6”的竞态。
- 已找到安装后不再每五秒重复发现，只继续轮询精确进程状态；未找到时才按五秒间隔重试，因此可用按钮不会周期性闪回“正在查找 FH6”。
- 源码 GUI 连续观察十二秒跨过两个旧扫描周期，按钮保持“启动 FH6”；真实点击显示 Steam 请求提示并进入 FH6 启动画面，满足运行成功证据。

### FH6 中文文字 + 英文语音按钮

- `src/modules/forzahorizon/fh6_language.py` 只支持 Windows Steam 版 FH6。发现流程会读取 Steam 注册表、全部 `libraryfolders.vdf`、App ID `2483190` 的 manifest、卸载注册表和正在运行的精确 `ForzaHorizon6.exe` 完整路径，不硬编码 C 盘或 `Program Files`。
- 扫描会只读检查 `media/Stripped/StringTables`，按 ZIP 内 UTF-8 `.str` 内容识别 `CHS.zip`、`EN.zip` 和临时文件是中文、英文、未知还是损坏；未知或损坏状态会拒绝普通启用/还原操作。
- GUI/TUI 的“系统与更新”页提供重新扫描、选择目录和显式启用/还原按钮。扫描和启动不会自动改名；实际操作前必须再次确认，并要求 FH6 已退出、Steam 游戏语言为 English。
- 交换使用 `CHS.zip.fhds-swap.tmp` 完成精确三步 rename，每一步前重新检查游戏进程、路径和文件存在性；进程内失败会回滚，进程外中断留下的临时状态只允许通过显式修复处理，不自动删除、复制或猜测文件角色。
- `fh6_install_path` 是全局缓存提示，不覆盖每次扫描得到的真实结果。Windows 以外平台会显示不支持并禁用操作。
- 六个非英语 catalog、GUI/TUI 共用展示映射、R5 版本和双语 Release 正文已经同步；冻结 R4 更新器的回归测试确认能选择规范 R5 资产。

### 统一产品图标

- 用户最终选择的第二张水墨风 DualSense 赛车图片已规范化为 1024×1024 RGB `src/data/icon.png`，并生成含 16、24、32、48、64、128、256 七档的 `src/data/icon.ico`。
- Tk 标题栏、系统托盘、Windows 主 EXE、更新 Helper 和 Windows/Linux bundle 复用同一资产对；ICO 哈希契约为 `EDC4EBE4678D6A93B444E32CCE6689073FC0A59E12880E659383AE4F306B8AE4`。
- 最终 R5 EXE 的 associated icon 已从 PE 提取为 32×32 PNG，与新 ICO 的 32×32 帧逐像素完全一致。

### 单一 Console 前端和滚动布局

- 已删除 `src/modules/gui/variants.py`，不再支持 Stage、Studio、`FHDS_UI_VARIANT`、`FHDS_BUILD_VARIANT` 或 `data/ui_variant.txt`。GUI 固定为单一正式壳层，入口在 `src/modules/gui/main.py`。
- Windows 构建只生成规范资产 `FH-DualSense-Enhanced-R4.exe` 及同名 `.sha256`，对应配置在 `packaging/windows/fhds.spec` 和 `packaging/windows/build_exe.bat`。
- `src/modules/gui/controls_tab.py` 的驾驶反馈卡片使用自然高度和可滚动容器，不再被窗口高度压缩。逻辑宽度至少 720 px 时显示两列，较窄时自动切为单列。
- `src/modules/gui/widgets.py` 的根级 `WheelRouter` 统一处理滚轮。滚轮位于开关等子控件上时仍滚动所在页面；嵌套滚动到达边界后才转交外层；slider 不会被滚轮误改。
- 总览和配置文件页也改为可滚动页面，避免高 DPI 或小窗口下内容被裁切。

### Default 持久化、退出确认和恢复默认

- `src/modules/config/preferences.py` 不再在每次启动时覆盖 `Default`。Default 的 Profile 字段会即时保存并跨重启保留。
- 偏好写入使用临时文件替换；写入失败时返回失败，不再把未落盘操作报告为成功。
- `src/modules/config/profile_session.py` 只跟踪本次 GUI 会话对 Default Profile 字段的改动。纯 global 设置改动或当前命名 Profile 不触发退出另存提示。
- 窗口关闭、托盘退出、游戏关闭、遥测超时和更新重启均经过 `src/modules/gui/main.py` 的统一退出入口。
- Default 在本次会话被调节后，退出弹窗可选择“保存为命名配置并退出”“直接退出”或“取消”。命名输入框默认使用首个空闲的 `profile1`、`profile2` 等名称，保存失败时保持窗口开启。
- 总览快捷入口、配置文件页和设置页均可执行“恢复默认设置”。恢复操作先生成 `.bak`，重建 Default 和 global 字段、重新检测系统语言、切换到 Default，同时保留已有命名 Profile。

### 语言和更新提示

- 第一次启动且不存在有效偏好文件时，`src/modules/config/system_language.py` 根据 Windows 显示语言选择 `en`、`de`、`ja`、`ru`、`tr`、`zh` 或 `zh_tw`；之后仍可手动修改语言。
- “系统与更新”导航项旁会在发现可用更新、下载中、校验中、等待安装或更新错误时显示白点。进入页面不会提前清除提示。
- 更新器只接受唯一规范资产 `FH-DualSense-Enhanced-R<n>.exe` 及其 `.sha256`，不再按前端变体选择资产。
- 应用内六个非英语语言目录已同步 R4 界面行为；用户 README 另按英文、简体中文、日语三个独立页面维护。

### 独立关于页和正式命名

- GUI 左侧导航和 TUI 页签均在“日志”之后提供独立“关于与许可证”页面，继续显示 `LICENSE` 要求的署名、原项目与 Sponsor 链接。
- “握把触觉”不再混入许可证卡片；总览页已删除没有状态或动作的版本工作台。
- 窗口标题固定为 `FH-DualSense-Enhanced`，Windows `FileDescription` 为 `Enhanced Forza Horizon DualSense haptics`；旧界面代号只留在老三样记录设计来源。
- `.github/workflows/release.yml` 的 Enhanced R4 正文包含信息对等的完整中文和英文说明。

### 精简并拆分用户 README

- 根 `README.md` 现在是 96 行英文默认首页；`docs/ReadmeZH.md`、`docs/ReadmeJA.md` 是各 96 行的独立简体中文和日语页面，三者顶部可互相切换。
- 已删除重复的 `docs/ReadmeEN.md`，也删除三语同页锚点、后台行为等小设置、算法与报文说明、版本历史和开发构建命令。
- README 使用通用资产名 `FH-DualSense-Enhanced-R<n>.exe`，因此发布 R4 后不需要把固定版本号写死在三个语言页面中。
- README 与契约测试在 R4 分支提交为 `311c268`；移植到 `main` 后生成 `b2bb4ca` 并已推送到 `origin/main`。
- 三语 README 已移除旧界面代号功能卖点，并用 `IMPORTANT` 明确 Steam Input 保持开启、Forza 游戏内振动必须关闭。R4 分支提交为 `12478e4`，`main` 提交为 `e57e7c1`。
- 最终窗口标题、总览页、翻译目录、Release workflow 和 Windows 文件描述均已使用正式项目名；青绿色视觉设计保留。

### R4 既有触觉和灯效

- Enhanced R4 已包含红线握把反馈、可选扳机层、转速灯带、挡位 Player LEDs、Bluetooth HD haptics 软限幅和误差反馈等此前提交的功能。
- R5 本轮没有改变 HID report、Bluetooth `0x36`、Forza 遥测 offset 或任何手感参数。UDP 变更只新增运行时快照和“保留最后一个有效包”的 drain 行为，不改变 324-byte 报文解析布局。

## 正在进行的工作

- R5 业务实现、测试、翻译、Release 正文、新图标和长期文档已提交为 `b2569d4`；三个批准的设计分别为 `11808e8`、`355b2fa` 和 `a990301`。
- 源码 GUI、冻结 R5 GUI、真实 Steam/FH6 发现与启动、新图标嵌入和全量自动测试已经完成。远端 README 更新已无冲突合并；下一阶段是推送 `main` 并执行已获批准的稳定发布流程。
- 代码审计已确认基础油门 ramp、默认参数和 adaptive trigger primitive 未被 R4 的 G 力实现删除。R4 的 G 力 force 是加法层，默认最大 `28`，明显大于基础 ramp 最大 `1`；用户报告的实机差异尚不能由现有代码差异解释。
- R4/R5 的真实 Forza、不同显示缩放和后续自动更新替换仍属于验收/观察项，不应写成已经完成。

## 尚未完成的工作

1. 当前实机文件重扫为 `swapped`：`CHS.zip` 内容为英文、`EN.zip` 内容为中文，临时文件不存在。本轮启动按钮开发没有执行 rename；游戏内“中文文字 + 英文语音”效果和显式还原仍需用户按需验收。
2. 真实 Enhanced R4 到 R5 的更新替换；需要先存在公开稳定 R5 Release 才能端到端验证。
3. 在 100% 和 150% Windows 显示缩放下逐档目视检查；本轮可见 GUI 验收沿用当前桌面缩放。
4. 用户对 Default 跨重启、退出另存、恢复默认和更新白点的完整交互验收。
5. 用户对 Enhanced R4/R5 触觉、灯效和 Bluetooth 手感的真实 Forza 验收。本轮没有进行游戏内触觉或灯效测试。
6. 本地 Linux ELF 构建和真实 Linux DualSense 验证；R4 的 GitHub Actions Linux ELF 构建已经通过，FH6 语言功能在非 Windows 平台按设计禁用。
7. 在同一车辆、路段、Profile 和连接方式下进行 Enhanced R3/Enhanced R4 油门扳机 A/B，记录游戏内振动、Steam Input、最终效果来源、mode 与 force；当前尚未执行。

## 当前已知 Bug 和待确认风险

- 当前自动化和 125% 目视检查未发现长页面裁切或滚轮失效；100% 与 150% 缩放结果仍待确认。
- FH6 ZIP 角色由 `.str` 内容识别；如果游戏更新改变容器结构、编码或文本特征，扫描会进入 unknown/corrupt 并拒绝普通操作，需要重新验证识别规则，不能放宽为按文件名猜测。
- 三步 rename 在本进程内失败时会回滚，但断电、强制结束进程或外部工具同时改名仍可能留下 `CHS.zip.fhds-swap.tmp`。此状态只允许显式修复，且必须能唯一识别两份存档的语言角色。
- Steam 校验文件或游戏更新可能恢复原始 `CHS.zip` / `EN.zip`；应用每次扫描都以文件内容为准，不把缓存路径或上次操作结果当成真实状态。
- FH6 路径发现覆盖多 Steam library 和非系统盘，但当前只支持 Windows Steam 版；Microsoft Store 或其他发行方式未实现。
- 更新器设计中的“最多每 24 小时检查一次”尚未实现。当前每次启动约 10 秒后检查，没有持久化节流。
- 下载校验包含规范文件名、大小、SHA-256 与 `MZ` 头，但没有解析 PE 版本资源或验证代码签名。
- GUI/TUI 不在应用内展开 Release body，只提供查看 Release 的入口。
- R5 尚未发布，因此更新 Helper 的真实 R4 到 R5 跨版本替换仍待确认。
- 仓库脱离 fork network 后，两次 `R4` tag push 都没有创建 Actions run；工作流本身为 active 且 Actions 已启用，最终发布通过 `workflow_dispatch channel=stable` 成功完成。未来稳定 tag 的自动触发是否恢复仍待确认。
- GitHub Actions 提示 `actions/checkout@v4`、`actions/upload-artifact@v4`、`actions/download-artifact@v4`、`astral-sh/setup-uv@v5` 和 `softprops/action-gh-release@v2` 的 Node.js 20 运行时已弃用并被强制切到 Node.js 24；当前 R4 构建成功，但应在后续维护中升级对应 action major version。
- 不同 DualSense 固件或 Bluetooth adapter 仍可能拒绝 398 字节 `0x36` 并回退 compatible rumble，社区发生率待确认。
- 游戏原生振动或 Steam Input 可能掩盖本项目的碰撞方向；Enhanced R4 仍不接管菜单、CG、上车过场等原生振动。
- 同时运行两个实例会争用默认 UDP 端口 `5300`。
- 用户报告 Enhanced R4 关闭 G 力阻力时的 R2 扳机键油门手感与 Enhanced R3 明显不同。代码审计只发现油门值为 `0` 时 `rigid(0)` 与 `off()` 的差异，按下后的基础 ramp 理论应兼容；真实原因待受控 A/B，当前不能写成已经定位的代码回归。

## 当前技术债

- 遥测业务数据仍使用无类型 `dict`；新增的监听器状态已经使用不可变快照，但 GUI/TUI 设置声明仍有重复，主要依赖测试防止漂移。
- `wheelspin_*` 内部字段名与 traction/grip UI 术语不一致，直接重命名会破坏 Profile 和 share-code 兼容。
- 更新器缺少 24 小时节流、PE 版本解析、代码签名和应用内 Release 摘要。
- 稳定 Release 的 tag push 自动触发在仓库独立化后尚未恢复验证，当前有 `workflow_dispatch stable` 恢复入口。
- `src/lang/` 仍保留旧 ZUV sentinel 的未使用翻译键。
- USB audio endpoint 依赖名称 heuristic，没有用户选择和多 host API fallback。
- DSX 无 ACK、不提供本项目 body haptics，也不接收灯效。
- 三个独立语言 README 仍有事实重复；契约测试不能发现所有翻译语义漂移。
- 没有 Enhanced R3/Enhanced R4 全油门行程输出回归测试，也没有可直接记录最终 R2 扳机键效果来源、mode 和 force 的诊断入口。G 力层 `28` 与基础 ramp `1` 的量级差会放大主观差异。
- FH6 Steam VDF/manifest 读取是针对当前 Steam 文件格式的轻量解析，没有依赖 Valve 官方解析库；相关变化主要依赖 fixture 和真实只读扫描发现。

## 暂时不要修改的部分

- `src/modules/dualsense/bt_haptics.py` 的 report `0x36` 长度、offset、序列、CRC 和 haptics-only speaker omission；修改必须同时具备字节测试和真实硬件探针。
- `src/modules/dualsense/main.py` 的 `0x02`、`0x31` trigger layout、pending compatible release、单槽队列和 event clear/check 顺序。
- `src/modules/forzahorizon/udp_listener.py` 的 324 字节 offsets，以及 drain 完整队列但返回最后一个有效 324-byte 报文的语义。
- `src/modules/forzahorizon/fh6_language.py` 的按钮触发、内容识别、逐步前置检查、临时文件和显式恢复边界；不要改成启动时自动交换，也不要按盘符或文件名猜测状态。
- `src/modules/loop.py` 的 shared `CollisionSignal`、状态改变写入 gate、静音和 body-haptics failure isolation。
- 当前单一 Console 边界。不要恢复 Stage、Studio 或基于构建产物的页面分叉。
- Windows updater 的规范单资产、`.sha256`、Helper 和 `.old` 回滚边界。
- `LICENSE`、`src/modules/about.py` 和 `docs/THIRD_PARTY_NOTICES.md` 的署名、原项目与第三方声明。
- 已发布 Enhanced R1、R2、R3、R4 的 tag、Release 和资产；不得移动、覆盖或删除。

## 最近涉及的关键文件

- GUI：`src/modules/gui/main.py`、`overview_tab.py`、`overview_status.py`、`system_tab.py`、`dialogs.py`、`widgets.py`。
- FH6 与遥测：`src/modules/forzahorizon/fh6_language.py`、`fh6_language_presentation.py`、`process_watch.py`、`udp_listener.py`。
- TUI：`src/modules/tui/main.py`、`system_tab.py`。
- 配置：`src/modules/config/preferences.py`、`profiles.py`、`profile_session.py`、`system_language.py`。
- 更新器：`src/modules/update/github.py`、`service.py`、`presentation.py`。
- 构建和发布：`packaging/windows/fhds.spec`、`packaging/windows/build_exe.bat`、`packaging/windows/write_sha256.py`、`.github/workflows/release.yml`。
- 测试：`tests/gui/test_overview_status.py`、`test_r4_frontend.py`、`tests/forzahorizon/test_fh6_language.py`、`test_fh6_language_presentation.py`、`test_process_watch.py`、`test_udp_listener.py`、`tests/test_updater.py`、`tests/test_enhanced_distribution.py`。
- 用户文档：`README.md`、`docs/ReadmeZH.md`、`docs/ReadmeJA.md`；`docs/ReadmeEN.md` 已删除。
- 长期文档：`AGENTS.md`、`docs/ARCHITECTURE.md`、`docs/DECISIONS.md`。
- 本轮设计：`docs/superpowers/specs/2026-07-17-r5-overview-runtime-status-design.md`、`docs/superpowers/specs/2026-07-17-r5-fh6-chinese-text-english-voice-design.md`。

## 当前 Git 工作区状态

- 分支：`main`；R5 代码提交为 `b2569d4 feat: complete Enhanced R5`，远端 README 提交为 `324c6d8 docs: emphasize Forza Horizon 6 at README opening`，二者由本地 `cae277b` 无冲突合并。
- R4 功能合并提交：`1596b6f merge: integrate Enhanced R4`。
- 发布校验修复：`f987cc7 fix: validate release checksum sidecar`。
- 双语校验说明：`e7184c2 docs: note R4 checksum validation`。
- annotated tag `R4` 解引用后指向 `e7184c2`；Release workflow run `29563348374` 全部成功。
- `main` 在 `16ba4e4 docs: record R4 publication` 之后新增 `11808e8 docs: design R5 overview runtime status`、`355b2fa docs: design FH6 language swap controls` 和 `a990301 docs: design R5 Steam game launch`。
- R5 生产代码、测试、六个非英语 catalog、版本/锁文件、新 PNG/ICO、Release workflow 和四份长期文档均已提交；原有 R3/R4 油门扳机诊断记录与远端 README 修改均已保留。
- 构建产物、截图、缓存和用户偏好文件没有加入 Git。

## 已执行的测试和验证结果

- R5 最终全量测试：`uv run --project src pytest -q`，结果 `329 passed in 7.28s`。
- R5 定向回归：最终启动/语言核心为 `20 passed`，图标契约单测为 `1 passed`。完整覆盖非系统盘、多 Steam library、无扫描副作用、启动 URI 与运行中拒绝、启用/还原、Steam 语言门槛、三步 rename 失败回滚、步骤 1/2 中断恢复、unknown/corrupt 拒绝、非 Windows 禁用、总览防闪烁和冻结 R4 选择规范 R5 资产。
- 真实 FH6 首次只读扫描：从 Steam manifest 自动发现 `C:\Program Files (x86)\Steam\steamapps\common\ForzaHorizon6`，Steam 语言为 `english`，当时状态为 `native`，`CHS.zip` 识别为中文、`EN.zip` 识别为英文。之后的最新重扫为 `swapped`，两份已知哈希对调且临时文件不存在；启动按钮实现与测试没有执行 rename。
- 真实只读文件指纹：`CHS.zip` 为 `2,988,625` bytes / `50D262CB58A5E2EBEC12213B92F9C8E97424BC9D9520508646CA4BA014B925D3`；`EN.zip` 为 `2,890,321` bytes / `83511B02AADBD33DDFA54B6EA1D4134B74E7219B08B221A9B686753B6DA0F658`。
- 源码 GUI 可见冒烟：总览实际显示 Bluetooth 手柄已连接、UDP `5300` 等待遥测、当前 `Default` 和源码运行方式下更新不可用；启动按钮完成首次发现后连续十二秒保持“启动 FH6”，不再周期性闪回扫描。真实点击显示“已向 Steam 发送 FH6 启动请求”，随后 FH6 启动画面可见。
- R5 Windows 最终离线构建：PyInstaller `6.21.0` 成功生成唯一 `FH-DualSense-Enhanced-R5.exe`，大小 `47,566,499` bytes，SHA-256 `656e9dad476c37a904fa938b6a6111a8628e33e66fdde3828a67601e9cce3041`；95-byte sidecar 复核通过，MZ 头正确，`--help` 退出码为 `0`。
- R5 版本资源：`FileVersion` 与 `ProductVersion` 均为 `R5`，`OriginalFilename` 为 `FH-DualSense-Enhanced-R5.exe`，`InternalName` 为 `FH-DualSense-Enhanced-R5`，产品名与文件描述正确。PyInstaller archive 包含更新 Helper、FH6 语言模块和总览状态模块，不包含已删除的 UI variants。
- R5 图标验证：源 PNG 为 1024×1024 RGB；ICO 含七个规定尺寸且 SHA-256 为 `EDC4EBE4678D6A93B444E32CCE6689073FC0A59E12880E659383AE4F306B8AE4`。最终 EXE archive 同时包含 `data/icon.png` 与 `data/icon.ico`，从 PE 提取的 32×32 icon 与 ICO 对应帧四通道平均差为 `0`。
- 冻结 R5 GUI 可见冒烟：首轮发现真实更新错误详情过长后，将总览错误摘要限制为 64 字符并增加回归测试；最终重建包显示 Bluetooth 已连接、遥测等待、`Default` 和“当前已是最新版本”。系统页的原始语言状态、自动发现路径、Steam `english` 与完整按钮行均已在冻结包中可见。窗口正常关闭、无残留 R5 进程，FH6 两个 ZIP 哈希保持不变且临时交换文件不存在。
- R5 收尾静态检查：`python -m compileall -q src/modules src/lang`、`uv lock --check --project src` 和 `git diff --check` 均通过；Git 只报告既有的 LF/CRLF 转换提示。
- 最终发布代码全量测试：`uv run --project src pytest -q`，结果 `301 passed in 7.46s`。
- 校验修复定向测试：`tests/test_enhanced_distribution.py`、`tests/test_updater.py`、`tests/test_about_and_release.py`，结果 `42 passed in 3.55s`；双语正文更新后 `tests/test_enhanced_distribution.py` 再次为 `20 passed in 4.17s`。
- README 重构后 R4 分支全量测试：`294 passed in 4.66s`；相对链接检查通过。
- README 提交移植到稳定 R3 `main` 后全量测试：`242 passed in 4.31s`；GitHub API 已确认英文根首页、中日文页面和 `docs/ReadmeEN.md` 删除均已生效。
- 强制振动警告更新后 R4 分支全量测试：`295 passed in 4.58s`；稳定 R3 `main` 全量测试：`243 passed in 3.87s`。GitHub API 已确认三语警告和 README 中无旧界面代号。
- 字节码检查：`python -m compileall -q src/modules src/lang` 与 `python -m py_compile packaging/windows/write_sha256.py`，通过。
- 空白检查：`git diff --check`，通过；仅有 Git 的 LF/CRLF 提示。
- 125% Windows 显示缩放目视检查：驾驶反馈页卡片保持自然高度，右侧滚动条可用，底部内容位于滚动区域内，没有再被卡片裁切。
- 合成滚轮冒烟：鼠标位于子级开关时，单次标准滚轮使页面移动约 36 px；嵌套边界和 slider 保护由 `tests/gui/test_scroll_routing.py` 覆盖。
- 退出弹窗目视检查：中文标题、说明、默认 `profile1` 输入框及三个操作按钮均完整显示。
- 修复后本地 Windows 离线构建：PyInstaller `6.21.0` 成功生成唯一 `FH-DualSense-Enhanced-R4.exe`，大小 `46,322,911` bytes，SHA-256 `ba0cb7920bc4d3b0333571328053437cf3c0409abd20b7cadac1a2fbcd977ccf`；95-byte sidecar 与实际文件匹配，`--help` 退出码为 `0`。
- 最终 GitHub Release EXE 已重新下载独立验证：大小 `45,994,910` bytes，SHA-256 `df31c2edf49d235665348748847aa214a27a78f3b5dac69e87991e73ba019f49`；线上 95-byte sidecar 包含同一哈希，`FileVersion` 和 `ProductVersion` 为 `R4`，`OriginalFilename` 为 `FH-DualSense-Enhanced-R4.exe`。
- GitHub Actions run `29563348374` 的 `prepare`、`bundle`、`exe`、`elf`、`release` 全部成功；新增 `Verify EXE checksum sidecar` 步骤通过。最终 R4 Release 为 Latest、非 Draft、非 Prerelease，包含 8 个资产及信息对等的完整中文/英文正文。
- PyInstaller archive 包含 `data/FH-DualSense-Update-Helper.exe`、`modules.gui.about_tab` 和 `modules.tui.about_tab`，不包含 `ui_variant` 或 `variants`；`--help` 退出码为 `0`。
- 最终冻结 GUI 已完成隐藏和普通启动冒烟，均未产生新 crash log 或残留进程；当前自动化桌面环境未从进程 API 取得 Tk 窗口标题，因此独立关于页的最终可见布局仍未人工点击检查。窗口标题由源码与契约测试确认。
- Enhanced R5 真实 USB/Bluetooth Forza 触觉测试：本轮未执行；仅在源码 GUI 中观察到 Bluetooth 连接状态。
- 本轮游戏内振动状态：仅进入 FH6 启动画面，未检查或调整游戏内振动，不能据此形成触觉结论。
- 本轮 Steam Input 状态：启动交由 Steam URI 以保留 Steam 上下文，但未读取或调整用户的 Steam Input 开关，状态未知。

## 尚未执行或失败的验证

- 最新只读重扫已检测到 FH6 ZIP 为 `swapped`，但本轮启动按钮开发没有执行 rename；游戏内“中文文字 + 英文语音”效果和显式还原流程尚未完整记录。
- 100% 与 150% 显示缩放的逐档人工目视检查尚未执行。
- 真实手柄、Forza 遥测、触觉和灯效验证尚未执行。
- 本地 Linux ELF 构建和真实 Linux 运行尚未执行；GitHub Actions 的 Linux ELF 构建已成功。
- R5 稳定版尚未发布，因此真实 R4 到 R5 自动更新替换尚未执行。
- 第一次本地构建因 PyPI TLS 握手中断而失败；确认 PyInstaller 和依赖已存在于 uv 缓存后，以 `UV_OFFLINE=1` 重建成功。
- 首次 R4 CI 的 sidecar 缺少哈希，根因是 runner 的 Windows PowerShell 没有 `Get-FileHash` 且旧 BAT 未传播错误；首次 Release 已删除。最终发布改用 `packaging/windows/write_sha256.py`，并由 CI 上传前复核，问题已经解决。

## 下一次会话开始时优先阅读

1. `AGENTS.md`
2. 本文件 `docs/PROJECT_STATE.md`
3. `docs/ARCHITECTURE.md`
4. `docs/DECISIONS.md`
5. `docs/superpowers/specs/2026-07-17-r5-overview-runtime-status-design.md`
6. `docs/superpowers/specs/2026-07-17-r5-fh6-chinese-text-english-voice-design.md`
7. `docs/superpowers/specs/2026-07-17-r5-overview-steam-launch-design.md`
8. `src/modules/gui/main.py`、`overview_tab.py`、`overview_status.py`、`system_tab.py`
9. `src/modules/forzahorizon/fh6_language.py`、`fh6_language_presentation.py`、`process_watch.py`、`udp_listener.py`
10. `git status --short --branch`、`git diff` 和最近 10 条提交

下一次会话建议首先处理的具体任务：完整 R5 已完成本地构建与验收，用户已明确批准发布；先审查并提交当前 R5 范围，再推送 `main`、执行 `workflow_dispatch stable`，最后重新下载线上 EXE 与 sidecar 复核。R3/R4 扳机差异仍按原计划处理：增加仅用于诊断的效果来源、mode 和 force 记录，并在相同车辆、路段、Profile、连接方式下做 A/B；两轮都必须记录游戏内振动和 Steam Input 状态。保留现有青绿色视觉设计和新水墨风图标，不恢复界面变体。

# 项目当前状态

## 状态快照

- 最后更新：2026-07-17，Asia/Shanghai。
- 仓库：`piereacy/FH-DualSense-Enhanced`。
- 当前工作树：`work/hamza`。
- 当前分支：`main`，与 `origin/main` 同步。
- 当前开发身份：`src/pyproject.toml` 内部 PEP 440 版本 `4`，公开稳定名称 `Enhanced R4`。
- 当前公开稳定版：[`FH-DualSense-Enhanced R4`](https://github.com/piereacy/FH-DualSense-Enhanced/releases/tag/R4)，发布时间 `2026-07-17T07:33:04Z`；`R4` tag 与 `main` 均指向提交 `e7184c2`。
- GitHub 仓库已经脱离原项目 fork network；GitHub API 已确认 `isFork=false`、`parent=null`，原有 R1/R2/R3 Release 和 2 个 Star 均保留。
- 当前阶段：Enhanced R4 的触觉、灯效、内置更新器、单一桌面前端、独立“关于与许可证”页面、双语 Release 和发布资产均已完成并发布。
- 发布后校验缺陷已经修复：首次 R4 CI 因 runner 缺少 `Get-FileHash` 生成了不完整 sidecar；该 Release 已删除并在修复提交上重建，最终线上 `.sha256` 为 95 bytes 且与 EXE 精确匹配。

## 当前开发重心

Enhanced R4 发布收尾已经完成，当前没有未提交的业务实现。下一阶段应先收集 R4 真实用户反馈，再按优先级处理红线振动调校、自动更新节流与签名能力、前端细节优化；开始新版本前应由用户明确下一公开版本号。现有青绿色主题和单一界面边界继续保留。

## 最近完成的功能

以下内容已经有生产代码和自动测试：

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
- 本轮没有改变 HID report、Bluetooth `0x36`、Forza 遥测 offset 或手感参数，只修改前端、配置会话、更新资产选择、文档和测试。

## 正在进行的工作

- 没有正在进行且尚未提交的业务代码。
- R4 发布后的真实 Forza、不同显示缩放和后续自动更新替换仍属于验收/观察项，不应写成已经完成。

## 尚未完成的工作

1. 在 100% 和 150% Windows 显示缩放下逐档目视检查；本轮只在 125% 缩放下完成目视确认。
2. 用户对 Default 跨重启、退出另存、恢复默认和更新白点的完整交互验收。
3. 用户对 Enhanced R4 触觉、灯效和 Bluetooth 手感的真实 Forza 验收。本轮界面修复没有进行手柄或游戏测试。
4. 真实 Enhanced R4 到下一稳定版的更新替换；需要后续存在高于 R4 的稳定 Release 才能端到端验证。
5. 本地 Linux ELF 构建和真实 Linux DualSense 验证；R4 的 GitHub Actions Linux ELF 构建已经通过。

## 当前已知 Bug 和待确认风险

- 当前自动化和 125% 目视检查未发现长页面裁切或滚轮失效；100% 与 150% 缩放结果仍待确认。
- 更新器设计中的“最多每 24 小时检查一次”尚未实现。当前每次启动约 10 秒后检查，没有持久化节流。
- 下载校验包含规范文件名、大小、SHA-256 与 `MZ` 头，但没有解析 PE 版本资源或验证代码签名。
- GUI/TUI 不在应用内展开 Release body，只提供查看 Release 的入口。
- 当前没有已发布的下一稳定版资产，因此更新 Helper 的真实跨版本替换仍待确认。
- 仓库脱离 fork network 后，两次 `R4` tag push 都没有创建 Actions run；工作流本身为 active 且 Actions 已启用，最终发布通过 `workflow_dispatch channel=stable` 成功完成。未来稳定 tag 的自动触发是否恢复仍待确认。
- GitHub Actions 提示 `actions/checkout@v4`、`actions/upload-artifact@v4`、`actions/download-artifact@v4`、`astral-sh/setup-uv@v5` 和 `softprops/action-gh-release@v2` 的 Node.js 20 运行时已弃用并被强制切到 Node.js 24；当前 R4 构建成功，但应在后续维护中升级对应 action major version。
- 不同 DualSense 固件或 Bluetooth adapter 仍可能拒绝 398 字节 `0x36` 并回退 compatible rumble，社区发生率待确认。
- 游戏原生振动或 Steam Input 可能掩盖本项目的碰撞方向；Enhanced R4 仍不接管菜单、CG、上车过场等原生振动。
- 同时运行两个实例会争用默认 UDP 端口 `5300`。

## 当前技术债

- 遥测仍使用无类型 `dict`；GUI/TUI 设置声明仍有重复，主要依赖测试防止漂移。
- `wheelspin_*` 内部字段名与 traction/grip UI 术语不一致，直接重命名会破坏 Profile 和 share-code 兼容。
- 更新器缺少 24 小时节流、PE 版本解析、代码签名和应用内 Release 摘要。
- 稳定 Release 的 tag push 自动触发在仓库独立化后尚未恢复验证，当前有 `workflow_dispatch stable` 恢复入口。
- `src/lang/` 仍保留旧 ZUV sentinel 的未使用翻译键。
- USB audio endpoint 依赖名称 heuristic，没有用户选择和多 host API fallback。
- DSX 无 ACK、不提供本项目 body haptics，也不接收灯效。
- 三个独立语言 README 仍有事实重复；契约测试不能发现所有翻译语义漂移。

## 暂时不要修改的部分

- `src/modules/dualsense/bt_haptics.py` 的 report `0x36` 长度、offset、序列、CRC 和 haptics-only speaker omission；修改必须同时具备字节测试和真实硬件探针。
- `src/modules/dualsense/main.py` 的 `0x02`、`0x31` trigger layout、pending compatible release、单槽队列和 event clear/check 顺序。
- `src/modules/forzahorizon/udp_listener.py` 的 324 字节 offsets 与 `recv_latest()` drain 语义。
- `src/modules/loop.py` 的 shared `CollisionSignal`、状态改变写入 gate、静音和 body-haptics failure isolation。
- 当前单一 Console 边界。不要恢复 Stage、Studio 或基于构建产物的页面分叉。
- Windows updater 的规范单资产、`.sha256`、Helper 和 `.old` 回滚边界。
- `LICENSE`、`src/modules/about.py` 和 `docs/THIRD_PARTY_NOTICES.md` 的署名、原项目与第三方声明。
- 已发布 Enhanced R1、R2、R3、R4 的 tag、Release 和资产；不得移动、覆盖或删除。

## 最近涉及的关键文件

- GUI：`src/modules/gui/main.py`、`about_tab.py`、`dialogs.py`、`widgets.py`、`controls_tab.py`、`overview_tab.py`、`profiles_tab.py`、`settings_tab.py`、`system_tab.py`。
- 配置：`src/modules/config/preferences.py`、`profiles.py`、`profile_session.py`、`system_language.py`。
- 更新器：`src/modules/update/github.py`、`service.py`、`presentation.py`。
- 构建和发布：`packaging/windows/fhds.spec`、`packaging/windows/build_exe.bat`、`packaging/windows/write_sha256.py`、`.github/workflows/release.yml`。
- 测试：`tests/gui/test_r4_frontend.py`、`tests/gui/test_scroll_routing.py`、`tests/test_profile_persistence.py`、`tests/test_system_language.py`、`tests/test_updater.py`、`tests/test_enhanced_distribution.py`。
- 用户文档：`README.md`、`docs/ReadmeZH.md`、`docs/ReadmeJA.md`；`docs/ReadmeEN.md` 已删除。
- 长期文档：`AGENTS.md`、`docs/ARCHITECTURE.md`、`docs/DECISIONS.md`。
- 本轮设计：`docs/superpowers/specs/2026-07-16-r4-console-persistence-interactions-design.md`、`docs/superpowers/plans/2026-07-17-r4-console-persistence-interactions.md`、`docs/superpowers/specs/2026-07-17-readme-language-split-and-simplification-design.md`。

## 当前 Git 工作区状态

- 分支：`main`，发布前远端与本地均为 `e7184c27203d120c0fd6e02f4abf8a92dd2901b6`。
- R4 功能合并提交：`1596b6f merge: integrate Enhanced R4`。
- 发布校验修复：`f987cc7 fix: validate release checksum sidecar`。
- 双语校验说明：`e7184c2 docs: note R4 checksum validation`。
- annotated tag `R4` 解引用后指向 `e7184c2`；Release workflow run `29563348374` 全部成功。
- 本文件提交并推送后，`main` 将领先 `R4` tag 一个仅含状态交接文档的提交，这是预期状态。
- 构建产物、截图、缓存和用户偏好文件没有加入 Git。

## 已执行的测试和验证结果

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
- Enhanced R4 真实 USB/Bluetooth Forza 测试：本轮未执行。
- 本轮游戏内振动状态：未参与。
- 本轮 Steam Input 状态：未参与。

## 尚未执行或失败的验证

- 100% 与 150% 显示缩放的逐档人工目视检查尚未执行。
- 真实手柄、Forza 遥测、触觉和灯效验证尚未执行。
- 本地 Linux ELF 构建和真实 Linux 运行尚未执行；GitHub Actions 的 Linux ELF 构建已成功。
- 下一稳定版尚不存在，因此真实自动更新替换尚未执行。
- 第一次本地构建因 PyPI TLS 握手中断而失败；确认 PyInstaller 和依赖已存在于 uv 缓存后，以 `UV_OFFLINE=1` 重建成功。
- 首次 R4 CI 的 sidecar 缺少哈希，根因是 runner 的 Windows PowerShell 没有 `Get-FileHash` 且旧 BAT 未传播错误；首次 Release 已删除。最终发布改用 `packaging/windows/write_sha256.py`，并由 CI 上传前复核，问题已经解决。

## 下一次会话开始时优先阅读

1. `AGENTS.md`
2. 本文件 `docs/PROJECT_STATE.md`
3. `docs/ARCHITECTURE.md`
4. `docs/DECISIONS.md`
5. `docs/superpowers/specs/2026-07-16-r4-console-persistence-interactions-design.md`
6. `docs/superpowers/plans/2026-07-17-r4-console-persistence-interactions.md`
7. `src/modules/gui/main.py`、`src/modules/gui/widgets.py`、`src/modules/config/preferences.py`
8. `git status --short --branch`、`git diff` 和最近 10 条提交

下一次会话建议首先处理的具体任务：先确认用户希望优先调校红线振动、实现自动更新 24 小时节流，还是继续前端细节优化；涉及新公开版本时先确定版本号。保留现有青绿色视觉设计，不恢复界面变体。若触碰发布流程，先调查独立仓库的 tag push 为什么未创建 Actions run，并保留 `workflow_dispatch stable` 恢复入口。

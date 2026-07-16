# 项目当前状态

## 状态快照

- 最后更新：2026-07-17，Asia/Shanghai。
- 仓库：`piereacy/FH-DualSense-Enhanced`。
- 当前工作树：`work/hamza/.worktrees/r4-ui-updater-haptics`。
- 当前分支：`feat/r4-ui-updater-haptics`。
- 当前开发身份：`src/pyproject.toml` 内部 PEP 440 版本 `4`，公开候选名称 `Enhanced R4`。
- 当前公开稳定版仍是 Enhanced R3。Enhanced R4 尚未 tag、推送或发布，不得移动或覆盖 R3 tag。
- 当前阶段：Enhanced R4 的触觉、灯效、内置更新器和最终 Console 前端已经进入生产代码。单一 Windows 候选 EXE 已完成构建和本地冒烟，等待用户审阅。
- 本轮界面与配置实现提交：`88c4d52 feat: finalize R4 Console persistence experience`。

## 当前开发重心

当前重心是审阅唯一保留的 Miku Console，重点确认长页面滚动、不同显示缩放、Default 持久化、退出另存和恢复默认设置。只有收到明确发布指令后才准备或发布 Enhanced R4。

## 最近完成的功能

以下内容已经有生产代码和自动测试：

### 单一 Console 前端和滚动布局

- 已删除 `src/modules/gui/variants.py`，不再支持 Stage、Studio、`FHDS_UI_VARIANT`、`FHDS_BUILD_VARIANT` 或 `data/ui_variant.txt`。GUI 固定为 Miku Console，入口在 `src/modules/gui/main.py`。
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
- README 的简中、English、日本語同页内容、独立语言镜像和六个非英语语言目录已同步本轮行为。

### R4 既有触觉和灯效

- Enhanced R4 已包含红线握把反馈、可选扳机层、转速灯带、挡位 Player LEDs、Bluetooth HD haptics 软限幅和误差反馈等此前提交的功能。
- 本轮没有改变 HID report、Bluetooth `0x36`、Forza 遥测 offset 或手感参数，只修改前端、配置会话、更新资产选择、文档和测试。

## 正在进行的工作

- 本地候选位于工作区根部 `outputs/FH-DualSense-Enhanced-R4-review/FH-DualSense-Enhanced-R4.exe`，等待用户审阅。
- Enhanced R4 未发布。本分支当前只进行本地提交和验证，不自动推送、tag 或创建 Release。

## 尚未完成的工作

1. 在 100% 和 150% Windows 显示缩放下逐档目视检查；本轮只在 125% 缩放下完成目视确认。
2. 用户对 Default 跨重启、退出另存、恢复默认和更新白点的完整交互验收。
3. 用户对 Enhanced R4 触觉、灯效和 Bluetooth 手感的真实 Forza 验收。本轮界面修复没有进行手柄或游戏测试。
4. 真实 Enhanced R4 到下一稳定版的更新替换；需要后续存在可用 Release 资产才能端到端验证。
5. 本地 Linux ELF 构建和真实 Linux DualSense 验证。

## 当前已知 Bug 和待确认风险

- 当前自动化和 125% 目视检查未发现长页面裁切或滚轮失效；100% 与 150% 缩放结果仍待确认。
- 更新器设计中的“最多每 24 小时检查一次”尚未实现。当前每次启动约 10 秒后检查，没有持久化节流。
- 下载校验包含规范文件名、大小、SHA-256 与 `MZ` 头，但没有解析 PE 版本资源或验证代码签名。
- GUI/TUI 不在应用内展开 Release body，只提供查看 Release 的入口。
- 当前没有已发布的下一稳定版资产，因此更新 Helper 的真实跨版本替换仍待确认。
- 不同 DualSense 固件或 Bluetooth adapter 仍可能拒绝 398 字节 `0x36` 并回退 compatible rumble，社区发生率待确认。
- 游戏原生振动或 Steam Input 可能掩盖本项目的碰撞方向；Enhanced R4 仍不接管菜单、CG、上车过场等原生振动。
- 同时运行两个实例会争用默认 UDP 端口 `5300`。

## 当前技术债

- 遥测仍使用无类型 `dict`；GUI/TUI 设置声明仍有重复，主要依赖测试防止漂移。
- `wheelspin_*` 内部字段名与 traction/grip UI 术语不一致，直接重命名会破坏 Profile 和 share-code 兼容。
- 更新器缺少 24 小时节流、PE 版本解析、代码签名和应用内 Release 摘要。
- `src/lang/` 仍保留旧 ZUV sentinel 的未使用翻译键。
- USB audio endpoint 依赖名称 heuristic，没有用户选择和多 host API fallback。
- DSX 无 ACK、不提供本项目 body haptics，也不接收灯效。
- 根 README 与两个独立语言镜像存在重复内容，后续仍有漂移风险。

## 暂时不要修改的部分

- `src/modules/dualsense/bt_haptics.py` 的 report `0x36` 长度、offset、序列、CRC 和 haptics-only speaker omission；修改必须同时具备字节测试和真实硬件探针。
- `src/modules/dualsense/main.py` 的 `0x02`、`0x31` trigger layout、pending compatible release、单槽队列和 event clear/check 顺序。
- `src/modules/forzahorizon/udp_listener.py` 的 324 字节 offsets 与 `recv_latest()` drain 语义。
- `src/modules/loop.py` 的 shared `CollisionSignal`、状态改变写入 gate、静音和 body-haptics failure isolation。
- 当前单一 Console 边界。不要恢复 Stage、Studio 或基于构建产物的页面分叉。
- Windows updater 的规范单资产、`.sha256`、Helper 和 `.old` 回滚边界。
- `LICENSE`、`src/modules/about.py` 和 `docs/THIRD_PARTY_NOTICES.md` 的署名、原项目与第三方声明。
- 已发布 Enhanced R1、R2、R3 的 tag、Release 和资产。

## 最近涉及的关键文件

- GUI：`src/modules/gui/main.py`、`dialogs.py`、`widgets.py`、`controls_tab.py`、`overview_tab.py`、`profiles_tab.py`、`settings_tab.py`、`system_tab.py`。
- 配置：`src/modules/config/preferences.py`、`profiles.py`、`profile_session.py`、`system_language.py`。
- 更新器：`src/modules/update/github.py`、`service.py`、`presentation.py`。
- 构建和发布：`packaging/windows/fhds.spec`、`packaging/windows/build_exe.bat`、`.github/workflows/release.yml`。
- 测试：`tests/gui/test_r4_frontend.py`、`tests/gui/test_scroll_routing.py`、`tests/test_profile_persistence.py`、`tests/test_system_language.py`、`tests/test_updater.py`、`tests/test_enhanced_distribution.py`。
- 长期文档：`AGENTS.md`、`docs/ARCHITECTURE.md`、`docs/DECISIONS.md`。
- 本轮设计：`docs/superpowers/specs/2026-07-16-r4-console-persistence-interactions-design.md`、`docs/superpowers/plans/2026-07-17-r4-console-persistence-interactions.md`。

## 当前 Git 工作区状态

- 分支：`feat/r4-ui-updater-haptics`。
- 本轮实现提交：`88c4d52 feat: finalize R4 Console persistence experience`。
- 本文件提交并完成最终状态检查后，工作树应保持清洁。
- 构建产物、截图、缓存和用户偏好文件没有加入 Git。

## 已执行的测试和验证结果

- 全量测试：`src/.venv/Scripts/python.exe -m pytest -q`，结果 `294 passed in 4.07s`。
- 字节码检查：`src/.venv/Scripts/python.exe -m compileall -q src/modules src/lang`，通过。
- 空白检查：`git diff --check`，通过；仅有 Git 的 LF/CRLF 提示。
- 125% Windows 显示缩放目视检查：驾驶反馈页卡片保持自然高度，右侧滚动条可用，底部内容位于滚动区域内，没有再被卡片裁切。
- 合成滚轮冒烟：鼠标位于子级开关时，单次标准滚轮使页面移动约 36 px；嵌套边界和 slider 保护由 `tests/gui/test_scroll_routing.py` 覆盖。
- 退出弹窗目视检查：中文标题、说明、默认 `profile1` 输入框及三个操作按钮均完整显示。
- 最终 Windows 构建：PyInstaller `6.21.0` 成功生成唯一 `FH-DualSense-Enhanced-R4.exe`，大小 `46,320,513` bytes，SHA-256 `828bb93104e7c446e509d6e8d1ae3d253b79bea8c812e3b99710c9669f632ee2`。
- 配套 `.sha256` 与实际文件匹配；`FileVersion` 和 `ProductVersion` 为 `R4`，`OriginalFilename` 为 `FH-DualSense-Enhanced-R4.exe`。
- PyInstaller archive 包含 `data/FH-DualSense-Update-Helper.exe`，不包含 `ui_variant` 或 `variants`；`--help` 退出码为 `0`。
- 冻结 GUI 已启动并显示 `FH-DualSense-Enhanced · Miku Console`，随后正常关闭，没有生成 crash log 或残留主程序进程。
- Enhanced R4 真实 USB/Bluetooth Forza 测试：本轮未执行。
- 本轮游戏内振动状态：未参与。
- 本轮 Steam Input 状态：未参与。

## 尚未执行或失败的验证

- 100% 与 150% 显示缩放的逐档人工目视检查尚未执行。
- 真实手柄、Forza 遥测、触觉和灯效验证尚未执行。
- Linux ELF 构建尚未执行。
- 下一稳定版尚不存在，因此真实自动更新替换尚未执行。
- 本轮没有失败的自动测试、编译检查或构建步骤。

## 下一次会话开始时优先阅读

1. `AGENTS.md`
2. 本文件 `docs/PROJECT_STATE.md`
3. `docs/ARCHITECTURE.md`
4. `docs/DECISIONS.md`
5. `docs/superpowers/specs/2026-07-16-r4-console-persistence-interactions-design.md`
6. `docs/superpowers/plans/2026-07-17-r4-console-persistence-interactions.md`
7. `src/modules/gui/main.py`、`src/modules/gui/widgets.py`、`src/modules/config/preferences.py`
8. `git status --short --branch`、`git diff` 和最近 10 条提交

下一次会话建议首先处理的具体任务：让用户运行唯一的 R4 候选 EXE，确认 100%、125%、150% 显示缩放下的滚动与布局，并验证 Default 跨重启、退出另存和恢复默认。没有新的发布指令时，不要自动 tag、推送或发布 Enhanced R4。

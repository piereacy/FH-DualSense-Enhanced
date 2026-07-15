# 项目当前状态

## 状态快照

- 最后更新：2026-07-16，Asia/Shanghai。
- 仓库：`piereacy/FH-DualSense-Enhanced`。
- 当前工作树：`work/hamza/.worktrees/r4-ui-updater-haptics`。
- 当前分支：`feat/r4-ui-updater-haptics`。
- 当前开发身份：`src/pyproject.toml` 内部 PEP 440 版本 `4`，公开候选名称 `Enhanced R4`。
- 当前公开稳定版仍是 Enhanced R3，tag `R3` 固定在 `61a99cc feat: finish R3 Bluetooth HD haptics`。Enhanced R4 尚未发布，不得移动或覆盖 R3 tag。
- 当前阶段：Enhanced R4 的三套前端、内置更新器、触觉扩展、灯效和 Bluetooth 细节改进已进入生产代码；全量回归、三个 Windows EXE 构建、哈希/版本资源检查和逐案启动冒烟均已完成，等待用户审阅本地候选。

## 当前开发重心

Enhanced R4 本地候选已经完成。当前重心是把三套 EXE 交给用户对比界面并在真实 Forza 中审阅红线、可选扳机层、灯效与 Bluetooth 细节；只有获得新的明确指令后才发布 R4。

## 最近完成的功能

以下项目已经有生产代码和自动测试，但不等同于完成真实手柄手感验证：

### 三种共享前端

- `src/modules/gui/variants.py` 定义 Miku Console、Miku Stage、Miku Studio；三者共用同一批 Tab、`Settings`、后端线程和 Profile 格式。
- `src/modules/gui/theme.py` 集中定义以 `#39C5BB` 为主色的 Miku 青绿色令牌，没有打包角色图、字体或第三方商标素材。
- Console 使用完整左侧文字导航；Stage 使用顶部导航；Studio 使用紧凑导航轨、短标签和 Tooltip。
- `src/modules/gui/overview_tab.py` 提供手柄、遥测、Profile、更新器四张状态卡；新增 `LightingTab` 和独立“系统与更新”入口。
- `packaging/windows/fhds.spec` 读取 `FHDS_BUILD_VARIANT`，内置 `data/ui_variant.txt` 并生成三个明确文件名。`.github/workflows/release.yml` 已改为调用统一批处理并上传三案。

### Windows 内置更新器

- `src/modules/update/model.py` 定义不可变 Release/状态快照和更新状态机。
- `src/modules/update/github.py` 只筛选稳定 `R<n>` Release，要求当前 Miku 方案的 EXE 与同名 `.sha256`，限制响应/下载大小和超时，以 `.part` 下载并校验长度、SHA-256 与 `MZ` 头。
- `src/modules/update/service.py` 在后台线程检查、下载和恢复待安装状态；自动检查默认开启，后台下载默认关闭，安装必须由用户确认。
- `src/modules/update/install.py` 只允许冻结后的 Windows EXE 调度替换。源码、Linux 和 ZUV 运行的 GUI/TUI 更新操作被禁用并显示明确状态。
- `packaging/windows/update_helper.py` 使用 Win32 `OpenProcess`/`WaitForSingleObject` 等待旧程序，执行 `.old` 备份、原子替换、重启和失败回滚。
- Windows spec 内置独立 `FH-DualSense-Update-Helper.exe`；构建脚本为三个 EXE 分别生成 `.sha256`。

### 触觉、扳机与灯效

- 握把红线默认仍为左侧开启、R2 扳机键红线关闭；默认峰值改为 `220/255`、10 Hz、70% duty、low ratio `0.45`，进入后前 120 ms 叠加 `0.65` 起始冲击。
- `grip_redline_gain=1.5` 继续兼容旧 Profile，但现在使用 `1 - (1 - base)^gain` 非线性曲线，避免线性放大后过早削顶。
- `src/modules/forzahorizon/effects.py` 新增默认关闭的涡轮增压附加阻力、经 EWMA 的 G 力油门阻力、L2/R2 碰撞扳机冲击、松开扳机时的路面/减速带纹理。
- `src/modules/loop.py` 每个 telemetry tick 只计算一次 `CollisionSignal`，同时传给 `Controller` 和 `HapticMixer`。
- `src/modules/forzahorizon/lighting.py` 新增默认关闭的转速灯带、红线闪烁和挡位 Player LEDs；`ControllerVisualState` 同时进入 USB `0x02`、BT `0x31` 和 BT `0x36` state block，DSX 不写灯光。
- Bluetooth 3 kHz renderer 在量化前使用归一化 `tanh` 软限幅；`BluetoothPcmQuantizer` 使用默认 `0.75` 一阶误差反馈保存低幅平均能量。398 字节、32 stereo frames、序列和 CRC 未改变。
- 新增设置已进入 GUI/TUI、Profile/share code 和六个非英语目录；静态翻译审计在当前代码上未发现 GUI/TUI 常量键缺失。

### 公开说明和发布准备

- `README.md` 继续在同一页面集成简中、English、日本語，不恢复独立跳转式主页。
- `docs/ReadmeEN.md`、`docs/ReadmeJA.md` 继续保留为独立镜像文档，但不作为根 README 的语言切换目标。
- `.github/workflows/release.yml` 的 R4 Release body 已写入中文功能说明、三案文件名、更新器、Bluetooth 改进、上游 `1.6.2` 和 HorizonHaptics `1.3.0` 参考信息。
- ZUV、`win_start.bat` 和 Linux 路径继续保留；Windows 独立 EXE 现在是 README 推荐入口。

## 正在进行的工作

- 本地候选已整理到工作区根部的 `outputs/FH-DualSense-Enhanced-R4-review/`，等待用户选择界面并进行真实游戏体验。
- 当前代码、测试与文档准备提交到 `feat/r4-ui-updater-haptics`；Enhanced R4 仍未 tag、未推送 Release。

## 尚未完成的工作

1. 由用户进行真实 Forza 手感审阅。新红线、新扳机层、灯效和 Bluetooth 软限幅/误差反馈尚无 R4 实车评价。
2. 三种窗口在当前桌面尺度已通过视觉冒烟，但 100%、125%、150% 三档 DPI 的逐档检查尚未执行。
3. 真实 R4 到下一稳定版的更新替换需等后续 Release 资产才能端到端验证。
4. 本地 Linux ELF 构建和真实 Linux DualSense 验证仍未执行。
5. 24 小时更新节流、PE 版本解析、签名信任和应用内 Release 摘要保留为后续改进，不阻塞本地 R4 审阅。

## 当前已知 Bug 和待确认风险

- 更新器设计稿要求“最多每 24 小时检查一次”，当前 `UpdateService` 只在每次启动约 10 秒后检查，没有持久化节流，属于已确认未实现项。
- 更新下载检查文件名、大小、SHA-256 与 `MZ` 头，但没有解析 PE 版本资源或验证代码签名；不能把后两项写成已实现。
- GUI/TUI 不在应用内展开中文 Release body，只提供“查看 Release”链接；是否需要内嵌摘要待用户后续决定。
- 当前没有一个已发布的 Enhanced R5 资产，因此真实“R4 EXE 检查并替换为下一稳定版”的端到端更新只能在后续 Release 环境验证。
- 不同 DualSense 固件或 Bluetooth adapter 仍可能拒绝 398 字节 `0x36` 并回退 compatible rumble；社区发生率待确认。
- 游戏/Steam Input 原生振动可能掩盖本项目碰撞方向。Enhanced R4 仍不接管菜单、CG、上车过场等原生振动。
- 三案共享设置目录。若用户同时运行两个 EXE，会争用默认 UDP 端口 `5300`；这是并行运行限制，不是功能差异。

## 当前技术债

- 遥测仍是无类型 `dict`；GUI/TUI 设置声明仍有重复，依赖测试防止漂移。
- `wheelspin_*` 内部字段名与 traction/grip UI 术语不一致，直接重命名会破坏 Profile/share-code 兼容。
- 更新器没有 24 小时节流、PE 版本解析、代码签名和应用内 Release 摘要。
- `src/lang/` 仍保留旧 ZUV sentinel 的未使用翻译键。
- Windows 三案通过同一 spec 循环构建，耗时较长；当前没有针对三案的 CI 启动截图或 DPI 自动化。
- DSX 无 ACK、没有本项目 body haptics，也不接收灯效。
- USB audio endpoint 依赖名称 heuristic，没有用户选择和多 host API fallback。
- 根 README 与两个独立语言镜像重复内容，后续仍有漂移风险。

## 暂时不要修改的部分

- 已验证的 `src/modules/dualsense/bt_haptics.py` report `0x36` 长度、offset、序列、CRC 和 haptics-only speaker omission；变更必须同时有字节测试与真实硬件探针。
- `src/modules/dualsense/main.py` 的 `0x02`/`0x31` trigger layout、pending compatible release、单槽队列和 event clear/check 顺序。
- `src/modules/forzahorizon/udp_listener.py` 的 324 字节 offsets 与 `recv_latest()` drain 语义。
- `src/modules/loop.py` 的 shared `CollisionSignal`、状态改变写入 gate、静音和 body-haptics failure isolation。
- 三案共用 Tab/Settings/backend 的边界；不要为视觉差异复制 `main.py` 或设置页面。
- Windows updater 的当前方案资产锁定、`.sha256`、Helper 和 `.old` 回滚边界。
- `LICENSE`、`src/modules/about.py` 和 `docs/THIRD_PARTY_NOTICES.md` 的署名、原项目与第三方声明。
- 已发布 Enhanced R1/R2/R3 tag、Release 和资产。

## 最近涉及的关键文件

- 前端：`src/modules/gui/main.py`、`variants.py`、`theme.py`、`widgets.py`、`overview_tab.py`、`system_tab.py`、`lighting_tab.py`。
- TUI：`src/modules/tui/main.py`、`system_tab.py`、`lighting_tab.py`。
- 更新器：`src/modules/update/model.py`、`github.py`、`service.py`、`install.py`、`presentation.py`、`packaging/windows/update_helper.py`。
- 触觉与扳机：`src/modules/haptics/mixer.py`、`pcm.py`、`bt_audio.py`、`src/modules/forzahorizon/effects.py`、`collision.py`、`lighting.py`、`src/modules/loop.py`。
- HID：`src/modules/dualsense/main.py`、`bt_haptics.py`、`output_state.py`。
- 配置/语言：`src/modules/config/settings.py`、`preferences.py`、`src/lang/*.py`。
- 构建/发布：`src/pyproject.toml`、`src/uv.lock`、`packaging/windows/fhds.spec`、`build_exe.bat`、`.github/workflows/release.yml`。
- 契约测试：`tests/test_updater.py`、`tests/gui/test_r4_frontend.py`、`tests/test_enhanced_distribution.py`、`tests/test_packaging_haptics.py`、`tests/test_about_and_release.py`。
- 设计：`docs/superpowers/specs/2026-07-16-r4-frontend-variants-design.md`、`...r4-built-in-updater-design.md`、`...r4-haptics-expansion-design.md`。

## 当前 Git 工作区状态

- 已提交的 R4 设计与实现节点：
  - `0a9412e docs: design R4 frontend updater and haptics`
  - `2259a5c feat: add R4 GUI variants and built-in updater`
  - `3dd6e8d feat: expand R4 haptics and controller lighting`
- `3dd6e8d` 之后的更新器 Windows 等待修复、运行时 gate、状态翻译、前端细节、R4 版本、打包、workflow、测试与文档改动正在整理为本地提交。
- `packaging/windows/dist`、build、helper_dist 等生成目录应由 `.gitignore` 排除；最终提交前仍需确认没有产物进入 Git。

## 已执行的测试和验证结果

- 在 `3dd6e8d` 触觉/灯效实现节点运行全量测试：`274 passed`。
- 更新器与 Helper 定向测试在后续修复后：`14 passed`。
- R4 前端、更新器、设置组合定向测试：`36 passed`。
- 早期 packaging/updater 契约的 4 个文档失败已随 README/Release body 修正；最终全量测试覆盖这些用例并通过。
- 静态翻译键审计在六个非英语目录未发现当前 GUI/TUI 常量键缺失。
- 当前工作树最终全量测试：`uv run --project src pytest -q` 为 `282 passed in 3.94s`。
- `python -m compileall -q src/modules src/lang` 与 `git diff --check` 通过；Git 只提示工作树未来可能进行 LF/CRLF 转换，没有空白错误。
- `packaging/windows/build_exe.bat` 完整执行成功，Helper 和三个 one-file EXE 均由 PyInstaller `6.21.0` 构建。Console archive 已确认包含 `data/FH-DualSense-Update-Helper.exe` 与 `data/ui_variant.txt`。
- 三个 EXE 的 `FileVersion`/`ProductVersion` 都是 `R4`，`ProductName` 为 `FH-DualSense-Enhanced`，`OriginalFilename` 与各自方案文件名一致；三个配套 `.sha256` 均与实际文件匹配，`--help` 退出码均为 `0`：
  - Console：`46,300,574` bytes，SHA-256 `09e8cf7c5026db5b38baabc5559ee7d63e2bbe1b483325d0bfc8a7185f6f7c27`。
  - Stage：`46,300,567` bytes，SHA-256 `fc021f42255db771861b2413a89bd9bbccb60458bb6ea3382c661e1bc113fc2c`。
  - Studio：`46,299,413` bytes，SHA-256 `6c89b77c74824bb23f975af19f6cafff95421142d10e85e28359269bd9625215`。
- 三案逐一启动并正常退出：Console 显示完整左侧导航，Stage 显示顶部导航，Studio 显示紧凑导航；三者总览状态卡、系统与更新页和页面切换可用，Console 灯效页也已目视检查。更新控件在冻结 Windows EXE 中正确启用，自动检查开、后台下载关。没有生成 crash log，也没有残留主程序进程。
- Enhanced R4 真实 USB/Bluetooth Forza 测试：尚未执行；游戏内振动状态、Steam Input 状态均未记录。

## 下一次会话开始时优先阅读

1. `AGENTS.md`
2. 本文件 `docs/PROJECT_STATE.md`
3. `docs/ARCHITECTURE.md`
4. `docs/DECISIONS.md`
5. 三份 `docs/superpowers/specs/2026-07-16-r4-*.md`
6. `src/modules/update/`、`src/modules/gui/variants.py`、`packaging/windows/build_exe.bat`
7. `git status --short --branch`、`git diff` 和最近 10 条提交

下一次会话建议首先处理的具体任务：读取用户对 Console、Stage、Studio 与真实 Forza 手感的审阅结果；记录连接方式、游戏内振动和 Steam Input 状态后再调参。没有新的发布指令时，不要自动 tag 或发布 Enhanced R4。

# Enhanced R7 传输、触觉续航与反馈页面拆分实施计划

日期：2026-07-20  
对应规格：`docs/superpowers/specs/2026-07-20-r7-transport-ui-feedback-separation-design.md`

## 1. 固定现状与回归测试

- 保留当前脏工作区和既有 R7 修改，只暂存本计划文件。
- 先运行 DualSense runtime、USB audio、haptics manager、GUI layout、settings contract 的定向测试，记录实现前结果。
- 为身份读取瞬时失败、候选预验证、PortAudio 并发启动、失活 stream 和反馈字段归属先补失败测试。

## 2. 非破坏性 USB/Bluetooth handover

- 在 `src/modules/dualsense/main.py` 用按 path 保存的 retry state 替换 `_identity_attempted` 一次性集合。
- 实现 `1 s -> 2 s -> 5 s` 身份/候选验证 backoff，并在 path 消失或成功后清除。
- 把候选 handle 的 open、非阻塞设置和首份有效 input report 读取提取为预验证步骤；失败只关闭候选 handle。
- 把已验证 handle 的接管提取为 I/O thread 内的提交步骤，不再先调用 `_disconnect()` 拆掉工作中的旧传输。
- 提交时发布候选首个有效 input state、关闭旧 handle、重置 BT haptics builder 并只重放一次锁存输出；继续禁止 startup pulse。
- 保持 USB 优先、同一身份约束、USB -> BT fallback 和单物理 HID reader 边界。
- 扩展 `tests/dualsense/test_controller_runtime.py` 与 `tests/dualsense/test_topology.py`。

## 3. 修复 USB body haptics 生命周期竞争

- 在 `src/modules/haptics/audio.py` 为完整 start/stop transaction 增加实例级可重入锁。
- 只在没有健康 stream 时执行进程级 PortAudio refresh；并发第二次 start 必须复用第一个成功 stream。
- 让 `running` 检查底层 stream 的 `active` / `stopped`，识别 `_running=True` 但实际失活的状态。
- 失活后安全清理并让现有 5 秒限频逻辑重建 stream。
- 扩展 `tests/haptics/test_audio.py`、`test_lifecycle.py` 和 `test_manager.py`，覆盖并发 start、start/stop 串行化和失活恢复。

## 4. 拆分扳机反馈与握把触觉

- 新增不依赖 GUI/TUI 的纯数据反馈页面 schema，集中保存 trigger/grip 的开关、普通参数和实验参数分组。
- `src/modules/gui/controls_tab.py` 改为完整“扳机反馈”页：扳机开关、调节参数和折叠实验参数。
- `src/modules/gui/settings_tab.py` 保留通用字段 renderer，并将默认 `SettingsTab` 改为完整“握把触觉”页；`SystemTab` 继续复用 renderer 但只读取系统分组。
- `src/modules/tui/controls_tab.py` 与 `src/modules/tui/settings_tab.py` 使用同一 schema，分别显示“扳机反馈”和“握把触觉”。
- 更新 GUI/TUI 导航、总览快捷入口和所有 `src/lang/*.py` 目录。
- 将 `Traction/grip feedback` 改为 `Tire grip trigger feedback`，中文使用“轮胎抓地力扳机反馈”。
- 更新 `tests/test_haptic_settings.py` 和 GUI/TUI 导航契约，证明字段互斥、覆盖完整且两套前端一致。

## 5. 修复最大化重排和更新页空转

- 把扳机页响应式重排改成约 80 ms trailing debounce。
- 隐藏页不调度重排；列数未变不触碰卡片；列数变化使用 `grid_configure()`，不 `grid_forget()`。
- 为 `SystemTab` 更新区域增加 presentation tuple 缓存，仅在文字、进度、action 或 release 可见性变化时更新控件。
- 扩展 `tests/gui/test_r4_frontend.py`、`test_system_tab_initialization.py` 或新增窄范围测试。

## 6. 状态框与缩放验收

- 完成 `docs/superpowers/specs/2026-07-20-header-status-frame-rendering-design.md` 已确定的 `28` 高度、`8` 圆角和 4 倍数间距实现。
- 保留相同 presentation 不重绘的缓存。
- 自动测试尺寸契约；真实 EXE 在 Windows 100%、125%、150% 查看原始分辨率截图。
- 若 125%/150% 仍出现连续阶梯或底边缺口，将圆角改为 `0`，不继续增加复杂绘制路径。

## 7. 文档与验证

- 行为落地后同步老三样：`AGENTS.md`、`docs/ARCHITECTURE.md`、`docs/DECISIONS.md`。
- 同步 `docs/PROJECT_STATE.md` 的实际实现、测试和待硬件验收状态。
- 运行定向测试、完整 pytest、ruff、pyrefly、compileall、lock check 和 `git diff --check`。
- 构建 Windows R7 EXE，检查文件名、版本、图标、manifest、SHA-256 和相对 R6 的体积变化。
- 实机依次验证 BT、BT -> USB、USB -> BT、20 分钟握把触觉续航与窗口缩放；记录连接方式、Steam Input 和游戏内振动状态。

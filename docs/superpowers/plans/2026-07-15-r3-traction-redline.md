# Enhanced R3 抓地力路由与红线握把警告实施计划

**Goal:** 将通用轮胎抓地力反馈按 Forza 踏板遥测路由到 L2/R2 扳机键，并把红线警告从 R2 扳机键迁移为 USB/蓝牙一致的双侧握把断油脉冲，最终生成可供实车验证的 R3 Windows EXE。

**Architecture:** 保留 `TriggerAnimations` 的有状态 EWMA/hysteresis 与 `Controller` 的扳机优先级仲裁；把既有 wheelspin 算法扩展为纵向抓地力信号，并只生成一个按踏板状态路由的触发器 effect。红线状态迁入 `HapticMixer`，叠加到现有左右 `high` 通道；`HapticManager`、USB audio 与 Bluetooth compatible rumble 继续消费同一 `HapticFrame`，不建立传输模式专属强度或时序。

**Reference:** `docs/superpowers/specs/2026-07-15-r3-traction-redline-design.md`

## Global Constraints

- 工作分支为 `feat/r3-traction-redline`，工作树为 `.worktrees/r3-traction-redline`。
- 每个生产行为先添加失败测试；不得通过修改测试来掩盖回归。
- “握住 L2/R2”只由 Forza Data Out 的 `brake`/`accel` 判断，不读取 DualSense 物理 input report。
- USB 与蓝牙使用相同红线触发条件、脉冲相位、hold 和归一化强度；只允许现有底层合成路径不同。
- 不修改 HID report、Bluetooth CRC、USB 音频端点选择、Forza packet offsets 或 DSX 行为。
- 不创建 tag、不发布 R3 Release；本轮交付为本地测试产物。

## Task 1：锁定通用抓地力路由

- [ ] 在 `tests/forzahorizon/test_effects.py` 添加四种踏板组合、低速制动/烧胎、四材质 dominant wheel 和状态重置测试。
- [ ] 添加 L2 ABS 与 R2 抓地力在双踏板状态并存的控制器优先级测试。
- [ ] 在 `src/modules/forzahorizon/effects.py` 将 wheelspin 扩展为单一通用纵向抓地力信号，并按 L2/R2 路由表注入控制器。
- [ ] 删除 R2 扳机键 rev effect，保留换挡、idle、wall 和 resistance 优先级。
- [ ] 运行 effects 与 DSX 回归测试。

## Task 2：实现红线双侧握把断油脉冲

- [ ] 在 `tests/haptics/test_mixer.py` 添加立即 on、10 Hz/50% duty、120 ms hold、双侧对称、阈值/油门/开关/强度门控测试。
- [ ] 添加同一 `HapticFrame` 经 USB frame 与 Bluetooth compatible rumble 保持同一 normalized envelope 的测试。
- [ ] 在 `src/modules/haptics/mixer.py` 添加红线 deadline/phase 状态并把脉冲叠加到左右 high 通道。
- [ ] 确认 Body Haptics 总开关、`engine_haptics_intensity` 与 `enable_rev_limiter` 均能关闭红线握把脉冲。
- [ ] 运行 mixer、manager、audio 与 loop 回归测试。

## Task 3：迁移设置并同步界面

- [ ] 先添加旧 R2 默认值 30/12 迁移到 10/96、用户自定义值保留和 Default Profile 刷新的测试。
- [ ] 把默认红线频率/强度改为 10/96，并在读取 version 2 named Profile 时执行精确默认值迁移。
- [ ] 将 GUI/TUI 的 `Wheelspin` 文案改为 `Traction/grip`，把红线文案改为双侧握把警告与 pulse rate。
- [ ] 同步 `de/ja/ru/tr/zh/zh_tw` catalog，并通过 GUI/TUI parity 测试。

## Task 4：切换 R3 开发身份

- [ ] 将 `src/pyproject.toml` 版本改为 PEP 440 `3`，同步 `src/uv.lock`。
- [ ] 将运行时显示和本地构建产物映射为 `R3`/`FH-DualSense-Enhanced-R3.exe`。
- [ ] 将内部当前版本与 README 已发布稳定版本的测试常量分离，README 继续正确记录 R2 稳定版。
- [ ] 运行发布身份与 about 测试，确认没有修改 R2 tag/release 语义。

## Task 5：质量门禁与文档交接

- [ ] 更新 `AGENTS.md` 和 `docs/PROJECT_STATE.md`，只记录代码已实现和自动验证完成的事实；实车手感保持“待用户验证”。
- [ ] 运行定向测试、`uv run --project src pytest -q`、`compileall` 和 `git diff --check`。
- [ ] 检查完整 diff、工作区状态、TODO/临时代码和 USB/蓝牙一致性断言。

## Task 6：生成明日实车测试产物

- [ ] 使用现有构建入口生成 update-enabled ZUV 并检查内部版本、入口和 update repo。
- [ ] 构建 `FH-DualSense-Enhanced-R3.exe`，检查 VERSIONINFO、应用图标和 `--help` 冒烟。
- [ ] 输出绝对产物路径与最短实车测试序列：阈值下高转、持续红线、快速升挡穿越、抓地力与红线同时发生、USB/蓝牙各一轮。
- [ ] 不在用户确认手感前发布 R3。

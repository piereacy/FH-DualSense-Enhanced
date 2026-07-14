# Enhanced R2 真实路面材质验证执行计划

**Goal:** 使用 Bluetooth DualSense 和真实 Forza Data Out，逐段确认铺装、积水、泥土和碎石 wheelspin 的材质分类、R2 扳机键频带与手感。

**Architecture:** 不修改生产代码。每段使用新的 `Controller` 和 trigger-only 监听器，将现有 `UDPListener -> parse_packet -> Controller.update -> DualSense.set` 调用链直接接到 Bluetooth 手柄。body haptics 不参与，异常与段尾统一归零。

**Reference:** `docs/superpowers/specs/2026-07-14-r2-material-live-validation-design.md`

## 全局约束

- 在 `.worktrees/r2-trigger-dynamics` 的 `feat/r2-trigger-dynamics` 上执行。
- 只使用 Bluetooth；不重复 USB，不测试 DSX，不测试前驱/后驱。
- 每段最长 120 秒，用户完成一次稳定 wheelspin 后停止驾驶。
- 一段只有在日志证据与用户手感均通过时才算完成。
- 一段失败后停止后续测试，先保存真实遥测并建立失败回归。
- 任意退出路径都必须把 L2/R2 扳机键归零并关闭 HID handle。

### Task 1：基线与运行前检查

- [ ] 执行 `uv run --project src pytest -q tests/forzahorizon/test_effects.py`。
- [ ] 使用 `Get-NetUDPEndpoint -LocalPort 5300 -ErrorAction SilentlyContinue` 确认端口空闲。
- [ ] 使用 `_enumerate_dualsenses()` 确认仅选择 Bluetooth DualSense。
- [ ] 确认 Forza Data Out 的目标为 `127.0.0.1:5300`，packet size 为 324 字节。

### Task 2：铺装路面

- [ ] 启动新的 trigger-only listener，明确通知用户开始。
- [ ] 记录主导驱动轮、slip/rotation、puddle、surface rumble、分类和 R2 扳机键 frame。
- [ ] 确认分类为铺装路面，frequency 落入 `90..180`。
- [ ] 用户确认手感；段尾归零。

### Task 3：积水路面

- [ ] 使用新的 listener 和 `Controller`。
- [ ] 确认主导驱动轮 `wheel_in_puddle > 0`，分类为积水路面。
- [ ] 确认 frequency 落入 `80..150`。
- [ ] 用户确认与铺装路面可辨；段尾归零。

### Task 4：泥土路面

- [ ] 使用新的 listener 和 `Controller`。
- [ ] 确认主导驱动轮 `0.10 < abs(surface_rumble) <= 0.30`，分类为泥土路面。
- [ ] 确认 frequency 落入 `30..70`。
- [ ] 用户确认与已通过材质可辨；段尾归零。

### Task 5：碎石路面

- [ ] 使用新的 listener 和 `Controller`。
- [ ] 确认主导驱动轮 `abs(surface_rumble) > 0.30`，分类为碎石路面。
- [ ] 确认 frequency 落入 `12..30`。
- [ ] 用户确认与已通过材质可辨；段尾归零。

### Task 6：交付检查

- [ ] 将四段结果、失败或无法确认项写入 `docs/PROJECT_STATE.md`。
- [ ] 执行 `uv run --project src pytest -q`。
- [ ] 执行 `git diff --check`。
- [ ] 确认没有未经真实数据支持的算法或默认值修改。
- [ ] 提交验证记录；功能分支保持未合入、未发布，等待后续合并决定。

# R7 Bluetooth 到 USB 握把触觉交接实施计划

日期：2026-07-20
状态：自动测试通过但实机验证失败，停止执行；后续计划不得把本方案写成修复完成

对应规格：`docs/superpowers/specs/2026-07-20-r7-bt-usb-haptics-teardown-design.md`

## 1. 固定协议字节

- 在 `src/modules/dualsense/bt_haptics.py` 增加独立的 `0x08 / 0x02` Bluetooth control feature-report builder。
- 按 DS5Dongle 的 HIDP SET_REPORT `0x53` seed、48-byte report 和 little-endian CRC32 生成 bytes。
- 在 `tests/dualsense/test_bt_haptics.py` 固定 report id、control byte、零填充、长度、CRC 和不可变输出。

## 2. 扩展测试设备

- 让 `tests/dualsense/test_controller_runtime.py` 的 fake HID device 记录 `write()`、`send_feature_report()`、`close()` 的全局顺序。
- 支持 feature report 成功、返回零和抛异常三种结果。
- 保持现有 candidate validation、startup pulse 和 snapshot fixture 不变。

## 3. 接入 BT -> USB handover

- 仅在旧 layout 为 BT、validated candidate layout 为 USB 时，通过旧 BT handle 发送 control feature report。
- 调用继续位于唯一 DualSense I/O thread；先执行既有静音和 trigger release，再发送 feature report。
- 返回正数后才原子提交 USB candidate 并关闭旧 BT handle；普通 handover 不改变。

## 4. 失败保持与退避

- feature report 抛异常或返回非正数时关闭 USB candidate，保留旧 BT handle、snapshot、transport 和 pending output。
- `_perform_handover()` 使用现有 1/2/5 秒 retry state，并记录明确 warning。
- 不触碰 USB/BT 冷启动、USB -> BT、完全掉线 reconnect、normal output valid flags 或 startup pulse。

## 5. 自动验证

- 运行 DualSense builder/runtime/output、haptics manager/audio 的定向测试。
- 确认 `src/modules/haptics/audio.py`、`lifecycle.py` 和 `manager.py` 与 tag `R6` 无差异。
- 运行完整 pytest、Ruff、Pyrefly、compileall、lock check 和 diff check。

## 6. 文档同步

- 实现完成后更新老三样：`AGENTS.md`、`docs/ARCHITECTURE.md`、`docs/DECISIONS.md`。
- 把代码状态、自动测试、候选路径与待执行实机验收写入 `docs/PROJECT_STATE.md`。
- 未经实机确认不得写成 BT -> USB 握把已修复或可发布。

## 7. 构建与实机候选

- 使用独立 work/dist 目录构建规范 R7 EXE，避免覆盖正在运行的候选。
- 校验 MZ、PE `FileVersion` / `ProductVersion`、`OriginalFilename`、唯一 EXE 和 SHA-256 sidecar。
- 用户按规格顺序验证 USB 冷启动、BT 冷启动、BT -> USB、退出后 R6、USB -> BT；通过前不发布。

# Enhanced R3 Bluetooth HD Haptics 实施计划

**目标：** 让应用自身合成的握把触觉在 USB 与 Bluetooth 下共用同一波形，并构建可运行的完整 Windows EXE。

**设计：** `docs/superpowers/specs/2026-07-15-r3-bluetooth-hd-haptics-design.md`

## 1. 共享 PCM renderer

- [x] 新增 `src/modules/haptics/pcm.py`。
- [x] 将 `UsbAudioHaptics` 改为使用共享 renderer，保持既有输出手感。
- [x] 新增左右隔离、平滑、相位与 USB 回归测试。
- [x] 运行 `uv run --project src pytest -q tests/haptics/test_pcm.py tests/haptics/test_audio.py`。

## 2. Bluetooth 0x36 协议

- [x] 新增 `src/modules/dualsense/bt_haptics.py`，实现量化、state block 和报告构建。
- [x] 在 `DualSense` 中新增单槽队列、序列状态和 I/O 线程串行写入。
- [x] 覆盖长度、offset、CRC、sequence、覆盖丢包和错误路径。
- [x] 运行 `uv run --project src pytest -q tests/dualsense/test_bt_haptics.py tests/dualsense/test_output_report.py tests/dualsense/test_reconnect_output.py`。

## 3. Bluetooth renderer 与路由

- [x] 新增 `BluetoothAudioHaptics` 的 3 kHz / 32 帧调度线程。
- [x] 将 `HapticManager` 改为 Bluetooth HD haptics 优先、compatible rumble 回退。
- [x] 处理启停、静音、transport 切换、断线重试与关闭。
- [x] 更新 loop/manager/lifecycle 测试。
- [x] 运行 `uv run --project src pytest -q tests/haptics tests/test_loop_haptics.py`。

## 4. 实机分段验证

- [x] Bluetooth 静音 `0x36` 探针：不掉线、扳机仍正常。
- [ ] Bluetooth 左握把、右握把、低频、高频、发动机波形分段测试。
- [ ] Bluetooth 碰撞方向、红线、路面材质游戏测试。
- [ ] USB 同一组分段和游戏场景对照。
- [ ] 记录游戏内振动和 Steam Input 状态。

## 5. 文档、回归与构建

- [x] 更新“老三样”：`AGENTS.md`、`docs/ARCHITECTURE.md`、`docs/DECISIONS.md`。
- [x] 更新 `docs/PROJECT_STATE.md`、README 三语段落和 `docs/THIRD_PARTY_NOTICES.md`。
- [x] 运行 `uv run --project src pytest -q`。
- [x] 运行 `python -m compileall -q src/modules src/lang`、`git diff --check`。
- [x] 运行 `packaging/windows/build_exe.bat`。
- [x] 检查 EXE version/icon、依赖归档和 `--help` 冒烟。
- [ ] 最终审计工作区、测试证据、硬件记录和目标要求。

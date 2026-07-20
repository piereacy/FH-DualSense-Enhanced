# R7 Bluetooth 到 USB 音频就绪门槛实施计划

日期：2026-07-20
状态：实施中

对应规格：`docs/superpowers/specs/2026-07-20-r7-bt-usb-audio-readiness-design.md`

## 1. 固定 Windows endpoint 探针契约

- 新增 `src/modules/haptics/windows_endpoint.py`，只使用标准库 `winreg` 枚举活动 render endpoint。
- 识别 `VID_054C`、DualSense/Edge PID 与 `MI_00`，注册表缺失、权限异常、非 Windows 都安全返回。
- 新增独立单元测试，使用 fake registry 覆盖 active、disabled、错误设备、损坏属性和异常。

## 2. 延迟加载 `sounddevice`

- 调整 `UsbAudioHaptics` 默认依赖解析，使导入 haptics 与构造实例不导入真实 `sounddevice`。
- 仅在第一次 USB `start()` 时加载默认 backend；测试注入的 fake backend 不触发真实加载。
- 保持 R6 stream 参数、callback、PCM channel 2/3、stop 和失败日志不变。

## 3. 加入非阻塞 3 秒 handover gate

- 为 `DualSense` 注入 readiness callback，并按 candidate path 记录 settle deadline。
- BT -> USB candidate 在 deadline 前继续走 BT I/O 与 `0x36` 输出，不打开或提交 USB。
- deadline 后 readiness 未通过时保持 BT，复用 1/2/5 秒退避；通过后执行既有 validation、control teardown 与 commit。
- candidate 消失、transport 改变和 disconnect 时清理 settle state。

## 4. orchestration 与回归测试

- `make_backend()` 根据实时 `enable_body_haptics` 生成 callback；关闭握把触觉时跳过 endpoint 要求。
- 补充 gate 时间、失败保持、后续就绪、清理、bypass、冷启动和 USB -> BT 回归测试。
- 补充契约测试，禁止 Bluetooth 启动路径提前导入 `sounddevice`。

## 5. 验证、文档与候选构建

- 运行定向测试、完整 pytest、Ruff、Pyrefly、compileall、lock check 和 diff check。
- 更新老三样与 `docs/PROJECT_STATE.md`，明确自动验证和待执行硬件验收。
- 构建到新的独立 build/dist 目录，校验 R7 PE 版本、MZ、SHA-256 和唯一规范 EXE。
- 实机通过前不发布，不把 BT -> USB 握把触觉写成已修复。

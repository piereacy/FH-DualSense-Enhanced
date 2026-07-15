# Enhanced R3 发布收尾设计

日期：2026-07-15

状态：用户已确认设计方案 A，等待规格文件复核后实施。

## 目标

在不扩大 Enhanced R3 功能范围的前提下完成正式发布收尾：修正红线反馈的默认开关，补齐 Bluetooth HD haptics 的中文技术说明，记录已知后续工作，并发布稳定版 `R3`。

## 默认设置

`src/modules/config/settings.py` 的新建设置与每次启动刷新的 `Default` Profile 使用以下默认值：

- `enable_rev_limiter = False`：默认关闭 R2 扳机键红线警告。
- `enable_grip_redline_haptics = True`：默认开启握把红线警告。
- 握把红线默认继续只输出到左握把；现有强度、频率、阈值和 `1.5` 信号增益不在本次修改。

已有命名 Profile 中显式保存的两个开关不强制覆盖，避免破坏用户调校。旧 Profile 缺少握把红线字段时继续走现有迁移逻辑补齐，不新增一次性强制迁移。

## 文档范围

同步更新以下内容：

- `AGENTS.md`：增加稳定的默认值修改验证规则，不记录临时开发进度。
- `docs/ARCHITECTURE.md`：修正默认开关，并准确描述 USB 与 Bluetooth 共用 PCM renderer 的传输边界。
- `docs/DECISIONS.md`：新增一条取代旧默认值决定的记录，保留历史原因。
- `docs/PROJECT_STATE.md`：记录用户已完成 Bluetooth 游戏内验证、R3 发布状态及发布后的待解决问题。
- `README.md`：用中文详细解释 Bluetooth 如何复现 USB 合成波形的语义，而不是宣称虚拟 USB 或接管游戏原生振动。
- `.github/workflows/release.yml`：修正 R3 中文 Release 正文中的默认设置描述。

README 的技术说明必须明确：

1. `src/modules/haptics/mixer.py` 先把同一帧 Forza 遥测混合为左右 low/high 与 engine 信号。
2. `src/modules/haptics/pcm.py` 的共享 renderer 用相同频率、相位连续性、平滑和限幅生成左右 PCM。
3. USB 后端把 48 kHz PCM 写入 DualSense 四声道音频端点的触觉通道。
4. Bluetooth 后端按约 10.67 ms 一块把同一波形降采样为 3 kHz、32 帧、双声道 signed int8，封装进 398 字节 HID report `0x36`，附带序列号和 Bluetooth CRC。
5. `src/modules/dualsense/main.py` 在同一 HID I/O 线程串行发送扳机状态与触觉报告，单槽队列只保留最新音频块，避免旧触觉积压增加延迟。
6. `0x36` 创建、调度或写入失败时才回退到 compatible rumble；这不是虚拟 USB，也没有还原菜单、CG 等游戏原生振动。

## 已知后续工作

以下内容不阻止 R3 发布，也不在本次收尾实现：

- 红线握把振动的节奏和辨识度仍需继续调校。
- ZUV/启动器自动更新流程需要改良。
- GUI/TUI 的前端信息层级与交互需要优化。

## 验证

实施后执行：

- 默认值与 Profile 迁移定向测试。
- Bluetooth `0x36`、PCM、haptics manager 和发布文档定向测试。
- `uv run --project src pytest -q`。
- `python -m compileall -q src/modules src/lang`。
- `git diff --check`。
- `packaging\windows\build_exe.bat`，并核对 EXE ProductVersion/FileVersion 为 `R3`。

用户已经确认 Bluetooth 游戏内手感“完全没问题”。最终项目状态记录还需注明该观察对应的游戏内振动与 Steam Input 状态待确认，不能从本次反馈自行补写。

## 发布

所有检查通过后，将功能分支快进合入本地 `main`，推送 `origin/main`，创建并推送稳定标签 `R3`。由 `.github/workflows/release.yml` 构建 ZUV、Windows EXE 和 Linux ELF，并发布包含中文正文的正式 GitHub Release。发布完成后核对标签目标、Actions 结果、资产名称、下载可用性和 Release 中文说明。

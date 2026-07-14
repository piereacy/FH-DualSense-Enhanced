# Codex 项目工作指引

## 项目目标

FH-DualSense-Enhanced 读取 Forza Horizon Data Out 的 UDP 遥测，将车辆状态转换为 DualSense 自适应扳机和 USB 或 Bluetooth 握把触觉。

## 技术栈

- Python `>=3.13`，依赖和运行环境由 `uv` 管理，锁文件为 `src/uv.lock`。
- GUI 使用 `CustomTkinter`，TUI 使用 `Textual`。
- 原生手柄输出使用 `hidapi`，USB 握把触觉使用 `sounddevice`、PortAudio 和 `NumPy`。
- 系统托盘使用 `pystray` 和 `Pillow`，进程检测使用 `psutil`。
- 测试使用 `pytest`，发布使用 ZUV、PyInstaller 和 GitHub Actions。

## 开始任务前

1. 阅读 `docs/PROJECT_STATE.md`，确认当前阶段、已知问题和未完成验证。
2. 涉及运行链路或模块边界时阅读 `docs/ARCHITECTURE.md`。
3. 阅读与任务直接相关的代码和测试，不要只依据 README 或旧设计文档。
4. 执行 `git status --short --branch`、`git diff` 和 `git log -10 --oneline`，保留用户已有改动。
5. 用户文档和发行信息以 `README.md`、`LICENSE`、`docs/THIRD_PARTY_NOTICES.md` 和 `.github/workflows/release.yml` 为准，但发现其与代码不一致时必须明确指出。

## 核心入口

| 位置 | 职责 |
| --- | --- |
| `src/main.py` | CLI、配置加载、GUI/TUI/headless 启动和崩溃日志入口 |
| `src/modules/loop.py` | 遥测热循环、空闲静音、退出检测和输出去重 |
| `src/modules/forzahorizon/udp_listener.py` | UDP 监听、324 字节包解析和原始包转发 |
| `src/modules/forzahorizon/effects.py` | Forza 专用 L2/R2 效果、优先级和跨帧状态 |
| `src/modules/haptics/` | 传输无关的握把混音、USB 音频和 Bluetooth 降级路由 |
| `src/modules/dualsense/` | DualSense 枚举、USB/BT HID 报告、自适应扳机和重连 |
| `src/modules/dsx/` | DSX UDP 适配，只负责自适应扳机 |
| `src/modules/config/` | 默认设置、偏好文件、Profile 和路径规则 |
| `src/modules/gui/`、`src/modules/tui/` | 两套交互界面，设置能力应保持一致 |
| `tests/` | 行为、HID 字节、触觉、配置、发布和文档契约测试 |
| `packaging/`、`.github/workflows/release.yml` | ZUV、Windows EXE、Linux ELF 和 Release 构建 |

## 常用命令

以下命令均从仓库根目录执行，除非命令中显式进入 `src`。

安装或同步开发环境：

```powershell
cd src
uv sync
```

从源码启动默认 GUI：

```powershell
cd src
uv run main.py
```

其他启动方式：

```powershell
cd src
uv run main.py --tui
uv run main.py --headless --debug
```

完整测试：

```powershell
uv run --project src pytest -q
```

基础检查：

```powershell
git diff --check
git status --short --branch
git diff --name-only
```

仓库只配置了 Ruff 的行宽，没有定义稳定的 lint 或 type-check 命令。不要声称执行了未配置的检查。

构建本地 ZUV：

```powershell
packaging\zuv\build_zuv.bat
```

构建带本仓库更新源的 ZUV，需要在 `cmd.exe` 中执行：

```bat
set UPDATE_REPO=piereacy/FH-DualSense-Enhanced
packaging\zuv\build_zuv.bat
```

构建 Windows EXE：

```powershell
packaging\windows\build_exe.bat
```

构建 Linux ELF：

```bash
bash packaging/linux/build_elf.sh
```

## 修改原则和限制

- 所有可调参数集中在 `src/modules/config/settings.py`。新增系统级设置时同步更新 `preferences.GLOBAL_FIELDS`；车辆手感参数默认应保持 Profile 级。
- GUI 和 TUI 的同类设置必须同时更新，并补齐 `src/lang/` 中所有非英语语言目录的翻译或明确回退行为。
- UDP 热路径必须继续使用 `UDPListener.recv_latest()` 丢弃积压包，不能改为逐包处理旧遥测。
- `src/modules/loop.py` 只在 `(left, right, rumble)` 状态改变时调用手柄输出；USB 音频目标仍需要逐帧更新。
- Body haptics 关闭时不得占用 rumble flags 或 motor bytes。Bluetooth 的 rumble 释放帧不能被后续 trigger-only 帧吞掉。
- 不要随意修改 324 字节遥测偏移、USB/BT HID offset、BT CRC、trigger mode byte 和左右扳机映射。修改时必须增加字节级测试。
- HidHide 检测只能探测，当前代码不调用 `HidHideCLI.exe` 或修改 HidHide 配置。
- DSX 是无 ACK 的 UDP 后端，`connected` 只表示 socket 已打开。当前 DSX 不提供握把触觉。
- `Default` Profile 每次启动会按代码默认值刷新，命名 Profile 和 global fields 必须保留。不要在不了解迁移规则时改写偏好文件结构。
- 保留 `LICENSE` 要求的署名、原项目链接和 Sponsor 链接，以及 `docs/THIRD_PARTY_NOTICES.md` 中的 HorizonHaptics 归属。
- 不要把尚未通过测试或实机验证的 R2 行为写成已验证或已发布。以生产代码、自动测试和硬件记录分别标注事实层级。
- 术语必须消除歧义：版本阶段写 `Enhanced R2`，手柄右扳机写 `R2 扳机键`；不要单独写无法判断含义的 `R2`。
- 源码和文档使用 UTF-8。项目现有规则要求不新增 em dash 字符，使用普通连字符或中文标点。

## 完成任务前

1. 运行与改动最接近的定向测试。
2. 运行 `uv run --project src pytest -q`。若已有失败仍存在，记录精确测试名和原因，不得写成全部通过。
3. 运行 `git diff --check`，再次查看 `git status --short --branch` 和完整 `git diff`。
4. 确认未覆盖无关改动，未产生构建产物、缓存或用户配置。
5. 涉及 HID、USB 音频或 Bluetooth 时，单元测试之外还需记录真实硬件验证的连接方式和结果。未执行就写“未执行”。
6. 涉及发行时核对 `src/pyproject.toml`、构建脚本、Release workflow、README 和二进制名称的一致性。

## `docs/PROJECT_STATE.md` 更新规则

出现以下任一情况时必须同步更新 `docs/PROJECT_STATE.md`：

- 功能从计划变为实现、验证或发布。
- 当前开发重心、下一步顺序或暂时禁止修改的范围改变。
- 新增或解决 Bug、技术债、文档与代码不一致。
- 测试、构建、CI 或真实硬件验证结果改变。
- Git 分支、版本、关键文件或工作区状态发生对后续会话有意义的变化。

只记录已验证事实。会话决定但尚无代码的内容必须标为“设计已确认，代码未实现”；无法确认的内容写“待确认”。架构边界发生长期变化时同时更新 `docs/ARCHITECTURE.md`。

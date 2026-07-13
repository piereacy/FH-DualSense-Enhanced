<p align="right">
  <strong>简体中文</strong> •
  <a href="docs/ReadmeEN.md">English</a> •
  <a href="docs/ReadmeJA.md">日本語</a>
</p>

<div align="center">
  <img src="src/data/icon.png" alt="FH-DualSense-Enhanced" width="180">
  <h1>FH-DualSense-Enhanced</h1>
  <p><strong>为 PC 版《极限竞速：地平线》提供 DualSense 自适应扳机与遥测驱动握把触觉。</strong></p>
</div>

FH-DualSense-Enhanced `1.6.2.post1` 是基于 `Forza-Horizon-DualSense-Python 1.6.2` 制作的增强版本。程序读取游戏通过 UDP 输出的车辆遥测数据，让刹车、油门、发动机、路面、轮胎和碰撞状态直接反馈到 DualSense 手柄。

本项目不是原项目的官方版本，也不代表原作者立场。

## 功能亮点

- 左扳机根据制动力提供渐进阻力，并在 ABS 介入时产生脉冲。
- 右扳机根据油门开度提供阻力，可反馈换挡、红线和轮胎空转。
- 握把触觉包含发动机、路面材质、悬挂、碰撞、积水、轮胎打滑、烧胎和 ABS。
- 车辆真正静止且保持怠速时不会无意义地持续振动。
- 原地轰油门和烧胎仍会产生符合车辆状态的反馈。
- 路面材质只在车辆移动或轮胎空转产生实际激励时参与反馈。
- 支持 USB 和 Bluetooth 连接。
- 支持独立配置文件、后台托盘、随游戏退出和自动更新。

默认参数参考了社区反馈，并经过实际驾驶测试。它是一套开箱即用的起点，不代表适合每一辆车或每一位玩家。

## USB 与蓝牙

USB 和蓝牙的实际体验差距不大，两种连接方式都保留自适应扳机和握把反馈。

| 连接方式 | 输出方式 |
| --- | --- |
| USB | 使用 DualSense 四声道音频端点输出左右触觉，并通过 HID 控制扳机 |
| Bluetooth | 使用兼容的高低频振动输出握把效果，并与扳机状态一起发送 |

不同电脑、手柄固件和蓝牙适配器可能造成细微差异。USB 音频端点不可用时，扳机功能仍可继续工作。

## 快速安装

### Windows 推荐方式

1. 打开 [最新 Release](https://github.com/piereacy/FH-DualSense-Enhanced/releases/latest)。
2. 只需下载 `win_start.bat`。
3. 双击运行。启动器会下载 `FH-DualSense-Enhanced.zuv.py`，并自动准备 uv 和独立 Python 环境。

网络不稳定时，同时下载 `FH-DualSense-Enhanced.zuv.py`，把它放在 `win_start.bat` 旁边后重新运行。启动器会优先使用旁边的文件。

### 独立 EXE

只下载 `FH-DualSense-Enhanced-vX.Y.Z.exe` 也能正常使用。EXE 已包含 Python 和程序依赖，不需要 BAT、ZUV、uv 或本机 Python。

独立 EXE 不会自动更新。设置会保存在 EXE 旁边的 `data` 文件夹中。

### Linux

下载并运行 `linux_start.sh`。Linux 需要 hidapi 和对应的 udev 权限，启动器会给出安装提示。

## 必须完成的游戏设置

### 1. 开启 Steam Input

在 Steam 库中右键游戏，进入 **属性 -> 控制器**，为游戏开启 Steam Input。还应开启 Steam 的 DualSense 振动支持。

Steam Input 负责按键映射和游戏原生振动，本程序负责自适应扳机和遥测握把触觉。

### 2. 开启 Forza Data Out

进入游戏的 **设置 -> HUD 与游戏玩法**，滚动到数据输出区域：

| 设置 | 值 |
| --- | --- |
| Data Out | ON |
| Data Out IP Address | `127.0.0.1` |
| Data Out IP Port | `5300` |

如果 `127.0.0.1` 收不到数据，可以尝试 IPv6 环回地址 `::1`，并在软件中使用相同监听地址。

### 3. 启动顺序

1. 连接 DualSense 手柄。
2. 启动 FH-DualSense-Enhanced。
3. 确认软件已经识别手柄并开始监听 UDP。
4. 启动游戏。

如果使用 SISR 或其他会占用手柄的工具，优先启动 FH-DualSense-Enhanced，再启动对应工具和游戏。

### 4. 游戏振动选项

握把触觉由遥测数据独立合成，不依赖游戏内的“振动”开关。通常可以保持开启；如果感觉原生振动和合成触觉重复，再尝试关闭游戏振动进行比较。

## DualSense 按键图标

如果希望《极限竞速：地平线 6》的游戏界面显示 PlayStation / DualSense 按键图标，可以使用 Nexus Mods 上的 [PlayStation Controller Icons (DualSense)](https://www.nexusmods.com/forzahorizon6/mods/2)。该 Mod 会把默认的 Xbox 按键提示替换为 DualSense 图标。

游戏更新可能会恢复被替换的界面文件。每次游戏更新后，需要重新复制并替换一次该 Mod 文件。

## 握把触觉如何工作

程序不会使用一个固定波形让手柄无脑振动。每个效果都来自实时遥测：

- 发动机层根据转速、负载和油门变化。
- 路面层根据车速、轮胎旋转和路面材质变化。
- 打滑层区分普通行驶、轮胎失去抓地力和原地烧胎。
- ABS 层只在制动和轮胎状态满足条件时触发。
- 碰撞、悬挂和积水层只在对应事件出现时触发。

可在 **设置 -> 握把触觉** 调整总体、发动机、路面、碰撞和打滑强度，也可以完全关闭握把触觉，只保留自适应扳机。

## 后台行为

以下选项可以分别控制：

- 关闭游戏后同时关闭软件。
- 最小化窗口后移动到系统托盘。

两项都不是强制行为，可在设置页面独立开关。

## 防火墙与网络

程序只监听本机 UDP 端口，不会把遥测数据上传到互联网。

如果一直显示 `No UDP packets yet`：

1. 确认 Data Out 已开启，IP 和端口填写正确。
2. 在 Windows 防火墙中允许 EXE，或允许 BAT 模式使用的 `python.exe` 和 UDP 5300。
3. 检查是否已经启动了另一个程序实例。
4. 仅在诊断时临时关闭防火墙进行对比，确认后立即重新开启。不要长期关闭防火墙。

## 故障排查

| 现象 | 处理方法 |
| --- | --- |
| `No UDP packets yet` | 检查 Data Out、监听地址、UDP 5300 和防火墙规则；必要时尝试 `::1` |
| `WinError 10048` | UDP 5300 已被占用，关闭重复的软件实例或其他监听程序 |
| 找不到 DualSense | 检查连接、Steam 占用和 HidHide 白名单；BAT 模式通常需要允许 `python.exe` |
| USB 握把触觉启动失败 | 确认 Windows 显示 DualSense 四声道音频端点，关闭占用该端点的音频程序后重新插拔 USB |
| `PaErrorCode -9999` 或 WDM-KS 错误 | 让程序自动尝试兼容后端；若仍失败，检查 Windows 音频服务和手柄音频设备，扳机功能不受影响 |
| Bluetooth 感觉略有不同 | 属于正常现象，蓝牙使用兼容振动输出，但整体反馈逻辑与 USB 相同 |
| 扳机或握把过强 | 在设置中降低对应强度，或创建单独的车辆配置文件 |

## 开发与构建

```powershell
git clone https://github.com/piereacy/FH-DualSense-Enhanced.git
cd FH-DualSense-Enhanced\src
uv sync
uv run main.py
```

运行测试：

```powershell
uv run --project src pytest -q
```

构建 ZUV：

```powershell
set UPDATE_REPO=piereacy/FH-DualSense-Enhanced
packaging\zuv\build_zuv.bat
```

构建 Windows EXE：

```powershell
packaging\windows\build_exe.bat
```

## 项目来源与许可证

FH-DualSense-Enhanced 是以下项目的修改版本：

Originally created by Hamza Yeşilmen (HamzaYslmn).

Source: <https://github.com/HamzaYslmn/Forza-Horizon-DualSense-Python>

握把触觉和 USB 声道实现参考了 [HorizonHaptics](https://github.com/haritha99ch/HorizonHaptics)，相关 MIT 声明见 [THIRD_PARTY_NOTICES.md](docs/THIRD_PARTY_NOTICES.md)。

本项目使用自定义的源码可见许可证，仅允许个人、非商业使用。复制、修改或重新分发前，请完整阅读 [LICENSE](LICENSE)。

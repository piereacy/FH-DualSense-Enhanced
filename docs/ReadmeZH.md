<p align="right">
  <a href="../README.md">English</a> •
  <strong>简体中文</strong> •
  <a href="ReadmeJA.md">日本語</a>
</p>

<div align="center">
  <img src="../src/data/icon.png" alt="FH-DualSense-Enhanced" width="180">
  <h1>FH-DualSense-Enhanced</h1>
  <p><strong>为 PC 版《极限竞速：地平线》提供 DualSense 自适应扳机和遥测驱动触觉。</strong></p>
</div>

FH-DualSense-Enhanced 读取《极限竞速：地平线》的 Data Out 遥测，将刹车、油门、发动机、路面、轮胎和碰撞数据转换为 DualSense 反馈。

这是基于 `Forza-Horizon-DualSense-Python 1.6.2` 制作，并参考 `HorizonHaptics 1.3.0` 的非官方增强版本。

## 功能亮点

- L2、R2 扳机键可反馈刹车、ABS、油门和 wheelspin。
- 握把触觉覆盖发动机、路面、悬挂、积水、轮胎打滑和碰撞。
- 实时遥测驱动具有方向感的碰撞以及随路面变化的抓地力反馈。
- USB 和 Bluetooth 使用相同的扳机与遥测效果集合。
- 支持强度调节、分车辆配置和参考社区反馈的默认参数。
- 提供可选手柄灯效和简洁的 Miku Console 界面。

## 下载

### Windows 推荐方式

1. 打开[最新 Release](https://github.com/piereacy/FH-DualSense-Enhanced/releases/latest)。
2. 下载 `FH-DualSense-Enhanced-R<n>.exe`。
3. 直接运行 EXE，不需要 Python、BAT、ZUV 或 uv。

其他启动方式：

- Windows 启动器：下载 `win_start.bat`。网络不稳定时，可提前把 `FH-DualSense-Enhanced.zuv.py` 放在它旁边。
- Linux：下载 `linux_start.sh`。如果手柄权限不足，请手动安装项目提供的 [`70-dualsense.rules`](../packaging/linux/70-dualsense.rules)。

## 必需的游戏设置

### 1. 开启 Steam Input

在 Steam 中打开**游戏属性 -> 控制器**，为游戏启用 Steam Input，同时开启 Steam 的 DualSense 振动支持。

### 2. 开启 Forza Data Out

进入游戏的**设置 -> HUD 与游戏玩法**，填写：

| 设置 | 值 |
| --- | --- |
| Data Out | ON |
| Data Out IP Address | `127.0.0.1` |
| Data Out IP Port | `5300` |

如果环回地址收不到数据，可以在游戏和软件中同时改用 `::1`。

### 3. 按顺序启动

1. 连接 DualSense 手柄。
2. 启动 FH-DualSense-Enhanced，确认手柄和 UDP 监听已经就绪。
3. 启动游戏。

遥测触觉不依赖游戏内的振动选项。保持游戏振动开启可以保留菜单和过场反馈，但可能掩盖碰撞方向；比较方向或重复效果时，可以临时关闭游戏振动。

## USB 与 Bluetooth

两种连接都使用相同的遥测判断，并支持自适应扳机、路面细节、发动机、红线和方向碰撞反馈。

| 连接方式 | 说明 |
| --- | --- |
| USB | 握把触觉使用 DualSense 音频端点，自适应扳机使用 HID。 |
| Bluetooth | 触觉和扳机通过 HID 发送；HD haptics 不可用时会自动回退，扳机功能仍然保留。 |

## 常见问题

| 现象 | 检查内容 |
| --- | --- |
| `No UDP packets yet` | 检查 Data Out、监听地址、UDP 端口 `5300` 和 Windows 防火墙规则。 |
| `WinError 10048` | 另一个程序实例占用了 UDP 端口 `5300`，关闭重复监听程序。 |
| 找不到 DualSense | 重新连接手柄，并检查 Steam、HidHide 或其他可能占用手柄的软件。 |
| USB 触觉或 `PaErrorCode -9999` | 检查 DualSense 音频设备，关闭占用它的软件后重新连接 USB；扳机仍可使用。 |
| Bluetooth 触觉回退 | 重新连接手柄以再次尝试 HD haptics；回退期间扳机仍可使用。 |

## DualSense 按键图标

如果希望《极限竞速：地平线 6》显示 PlayStation 按键图标，可使用 [PlayStation Controller Icons (DualSense)](https://www.nexusmods.com/forzahorizon6/mods/2)。游戏更新可能恢复原文件，因此更新后可能需要再次安装 Mod。

## 来源与许可证

原作者 Hamza Yeşilmen（HamzaYslmn）：
[Forza-Horizon-DualSense-Python](https://github.com/HamzaYslmn/Forza-Horizon-DualSense-Python)

握把触觉参考了 [HorizonHaptics](https://github.com/haritha99ch/HorizonHaptics)，Bluetooth 协议参考了 [vDS](https://github.com/hurryman2212/vds)。相关声明见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

本项目使用自定义的源码可见许可证，仅允许个人、非商业使用。复制、修改或重新分发前，请阅读 [LICENSE](../LICENSE)。

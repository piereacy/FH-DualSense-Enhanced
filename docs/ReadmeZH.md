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

目前支持 Windows Steam 与 Xbox App 的《极限竞速：地平线 4》《极限竞速：地平线 5》和《极限竞速：地平线 6》使用流程；总览页可以选择并记住平台与游戏。

这是基于 `Forza-Horizon-DualSense-Python 1.6.2` 制作，并参考 `HorizonHaptics 1.3.0` 的非官方增强版本。

## 相比上游 1.6.2 的增强

- 遥测驱动的握把触觉融合发动机、路面、悬挂、积水、轮胎打滑、ABS、红线和方向碰撞反馈。
- 扩展的自适应扳机加入动态抓地力与 wheelspin、按路面变化的频率区间、分区 ABS 和可选遥测反馈层。
- USB 和 Bluetooth 使用同一套立体声握把混音；Bluetooth 增加 HD 传输并在不可用时自动兼容回退。
- 参考社区反馈的默认参数、Default 持久化自动保存、分车辆命名配置和安全恢复出厂设置让配置流程更加可靠。
- 响应式多语言桌面界面提供记忆选择的 FH4/FH5/FH6 Steam/Xbox App 启动入口、内置 DualSense 到 XInput 连接桥，以及可还原的 FH6 DualSense 按键图标。
- 统一的独立 EXE 支持校验更新下载、重启替换，并在替换失败时回滚。

## 下载

### Windows 推荐方式

1. 打开[最新 Release](https://github.com/piereacy/FH-DualSense-Enhanced/releases/latest)。
2. 下载 `FH-DualSense-Enhanced-R<n>.exe`。
3. 直接运行 EXE，不需要 Python、BAT、ZUV 或 uv。

其他启动方式：

- Windows 启动器：下载 `win_start.bat`。网络不稳定时，可提前把 `FH-DualSense-Enhanced.zuv.py` 放在它旁边。
- Linux：下载 `linux_start.sh`。如果手柄权限不足，请手动安装项目提供的 [`70-dualsense.rules`](../packaging/linux/70-dualsense.rules)。

## 必需的游戏设置

### 1. 选择游戏平台

- **Steam：**在**游戏属性 -> 控制器**中，Steam Input 必须保持开启，同时开启 Steam 的 DualSense 振动支持。
- **Xbox App：**在 FH-DualSense-Enhanced 中选择 Xbox App。内置 XInput 连接桥代替 DS4Windows 或 Steam Input；首次使用可能需要通过 Windows UAC 安装内置 ViGEmBus 驱动，安装不需要联网。

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

> [!IMPORTANT]
> Steam 模式下 Steam Input 必须保持开启；所有模式都必须在 Forza 游戏设置中关闭“振动”。游戏原生振动会争用并掩盖手柄握把触觉，因此开启游戏内振动时，握把反馈无法正常工作。

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
| Xbox App 没有手柄输入 | 在软件中选择 Xbox App，按提示完成 ViGEmBus 设置，并避免让 Steam Input 或 DS4Windows 同时接管同一手柄。 |

## FH6 实用功能

独立的 **FH6 实用功能**页面为 Steam 或 Xbox App 安装提供“中文文字 + 英文语音”文件交换和可还原的 DualSense 按键图标 MOD。Steam 路径自动检测，Xbox App 路径由用户手动选择；语言状态会分别显示当前游戏语言、实际显示语言和语音语言，无法验证的值不会被猜测。游戏更新可能恢复原文件，届时可再次执行。感谢 [@hotline1337](https://www.nexusmods.com/forzahorizon6/mods/2)。

## 来源与许可证

原作者 Hamza Yeşilmen（HamzaYslmn）：
[Forza-Horizon-DualSense-Python](https://github.com/HamzaYslmn/Forza-Horizon-DualSense-Python)

握把触觉参考了 [HorizonHaptics](https://github.com/haritha99ch/HorizonHaptics)，Bluetooth 协议参考了 [vDS](https://github.com/hurryman2212/vds)。相关声明见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

本项目使用自定义的源码可见许可证，仅允许个人、非商业使用。复制、修改或重新分发前，请阅读 [LICENSE](../LICENSE)。

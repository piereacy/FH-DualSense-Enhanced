<a id="readme-zh-cn"></a>

<p align="right">
  <strong>简体中文</strong> •
  <a href="#readme-en">English</a> •
  <a href="#readme-ja">日本語</a>
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

下载并运行 `linux_start.sh`。启动器只负责下载并启动应用，不会安装系统级 udev 规则。如果日志提示 DualSense 权限不足，请下载仓库中的 [`70-dualsense.rules`](packaging/linux/70-dualsense.rules)，然后执行：

```bash
sudo cp 70-dualsense.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
```

完成后重新插拔 USB 手柄，或重新配对 Bluetooth 手柄。

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

---

<a id="readme-en"></a>

<p align="right">
  <a href="#readme-zh-cn">简体中文</a> •
  <strong>English</strong> •
  <a href="#readme-ja">日本語</a>
</p>

<div align="center">
  <img src="src/data/icon.png" alt="FH-DualSense-Enhanced" width="180">
  <h1>FH-DualSense-Enhanced</h1>
  <p><strong>DualSense adaptive triggers and telemetry-driven body haptics for Forza Horizon on PC.</strong></p>
</div>

FH-DualSense-Enhanced `1.6.2.post1` is an enhanced fork based on `Forza-Horizon-DualSense-Python 1.6.2`. It reads vehicle telemetry sent by the game over UDP and turns braking, throttle, engine, road, tire, and impact states into DualSense feedback.

This is not an official upstream release and does not represent the upstream author's views.

## Highlights

- Progressive brake-trigger resistance with ABS pulses.
- Progressive throttle-trigger resistance with shift, redline, and wheelspin feedback.
- Body haptics for engine, road material, suspension, impacts, puddles, tire slip, burnouts, and ABS.
- No meaningless continuous vibration when the vehicle is truly stationary at idle.
- Revving and burnouts while stationary still produce appropriate feedback.
- Road material contributes only while the car moves or the tires create physical excitation.
- USB and Bluetooth support.
- Profiles, tray behavior, exit-with-game behavior, and ZUV updates.

The default tuning is informed by community feedback and refined through hands-on driving tests. It is a practical starting point, not a universal setting for every car or player.

## USB and Bluetooth

The practical experience is broadly similar over USB and Bluetooth. Both retain adaptive triggers and body feedback.

| Connection | Output path |
| --- | --- |
| USB | Uses the DualSense four-channel audio endpoint for left and right haptics, plus HID trigger control |
| Bluetooth | Uses compatible low and high frequency rumble, sent together with trigger state |

Small differences can depend on the PC, controller firmware, and Bluetooth adapter. Trigger feedback continues to work if the USB audio endpoint is unavailable.

## Quick installation

### Recommended Windows method

1. Open the [latest Release](https://github.com/piereacy/FH-DualSense-Enhanced/releases/latest).
2. Download only `win_start.bat`.
3. Run it. The launcher downloads `FH-DualSense-Enhanced.zuv.py` and prepares uv plus an isolated Python environment.

For the manual network fallback, also download `FH-DualSense-Enhanced.zuv.py`, place it beside `win_start.bat`, and run the launcher again. The adjacent bundle is used first.

### Standalone EXE

Downloading only `FH-DualSense-Enhanced-vX.Y.Z.exe` also works. The EXE includes Python and all application dependencies, so BAT, ZUV, uv, and a system Python installation are not required.

The standalone EXE does not update itself. Settings are stored in a `data` folder beside the EXE.

### Linux

Download and run `linux_start.sh`. The launcher only downloads and starts the application; it does not install system udev rules. If the log reports insufficient DualSense permissions, download [`70-dualsense.rules`](packaging/linux/70-dualsense.rules), then run:

```bash
sudo cp 70-dualsense.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
```

Reconnect the USB controller or pair the Bluetooth controller again afterward.

## Required game setup

### 1. Enable Steam Input

Right-click the game in Steam, open **Properties -> Controller**, and enable Steam Input for the game. Enable Steam's DualSense vibration support as well.

Steam Input supplies button mapping and native game rumble. This app adds adaptive triggers and telemetry-driven body haptics.

### 2. Enable Forza Data Out

Open **Settings -> HUD and Gameplay** in Forza Horizon and scroll to the Data Out section:

| Setting | Value |
| --- | --- |
| Data Out | ON |
| Data Out IP Address | `127.0.0.1` |
| Data Out IP Port | `5300` |

If `127.0.0.1` receives no packets, try the IPv6 loopback address `::1` and use the same listen address in the app.

### 3. Startup order

1. Connect the DualSense controller.
2. Start FH-DualSense-Enhanced.
3. Confirm that the controller is detected and UDP listening has started.
4. Launch the game.

When using SISR or another tool that can claim the controller, start FH-DualSense-Enhanced first, then the other tool and the game.

### 4. In-game vibration

Body haptics are synthesized from telemetry and do not depend on the in-game vibration toggle. It can normally remain enabled. If native rumble feels duplicated, compare the result with in-game vibration disabled.

## DualSense button icons

If you want PlayStation / DualSense button prompts in the Forza Horizon 6 interface, use [PlayStation Controller Icons (DualSense)](https://www.nexusmods.com/forzahorizon6/mods/2) from Nexus Mods. It replaces the default Xbox prompts with DualSense icons.

A game update may restore the replaced interface files. Recopy and replace the mod files after each game update.

## How body haptics work

The app does not play a fixed waveform or vibrate without context. Every layer comes from live telemetry:

- The engine layer follows RPM, load, and throttle.
- The road layer follows speed, wheel rotation, and road material.
- The slip layer distinguishes normal driving, loss of grip, and stationary burnouts.
- ABS activates only when braking and tire conditions qualify.
- Impact, suspension, and puddle layers activate only for matching events.

Open **Settings -> Body haptics** to adjust master, engine, road, impact, and slip strength. Body haptics can also be disabled while adaptive triggers remain active.

## Background behavior

Two independent settings control background behavior:

- Exit the application when the game closes.
- Move the window to the system tray when minimized.

Neither behavior is mandatory.

## Firewall and networking

The app listens on a local UDP port and does not upload telemetry to the internet.

If the log keeps showing `No UDP packets yet`:

1. Confirm that Data Out, the IP address, and the port are correct.
2. Allow the EXE through Windows Firewall, or allow the `python.exe` used by BAT mode and UDP 5300.
3. Check whether another app instance is already running.
4. Disable the firewall only as a temporary diagnostic comparison, then turn it back on immediately. Do not leave the firewall disabled.

## Troubleshooting

| Symptom | Resolution |
| --- | --- |
| `No UDP packets yet` | Check Data Out, listen address, UDP 5300, and firewall rules; try `::1` if needed |
| `WinError 10048` | UDP 5300 is already in use; close the duplicate app instance or other listener |
| DualSense not found | Check the connection, Steam ownership, and the HidHide allowlist; BAT mode normally needs `python.exe` allowed |
| USB body haptics cannot start | Confirm that Windows exposes the DualSense four-channel audio endpoint, close apps using it, and reconnect USB |
| `PaErrorCode -9999` or WDM-KS error | Let the app try its compatibility fallback; if it still fails, check Windows Audio and the controller audio device; triggers remain available |
| Bluetooth feels slightly different | This is normal because Bluetooth uses compatible rumble, while the feedback logic remains the same |
| Triggers or body haptics are too strong | Lower the relevant strength in Settings or create a vehicle-specific profile |

## Development and builds

```powershell
git clone https://github.com/piereacy/FH-DualSense-Enhanced.git
cd FH-DualSense-Enhanced\src
uv sync
uv run main.py
```

Run tests:

```powershell
uv run --project src pytest -q
```

Build ZUV:

```powershell
set UPDATE_REPO=piereacy/FH-DualSense-Enhanced
packaging\zuv\build_zuv.bat
```

Build the Windows EXE:

```powershell
packaging\windows\build_exe.bat
```

## Origin and license

FH-DualSense-Enhanced is a modified version of the following project:

Originally created by Hamza Yeşilmen (HamzaYslmn).

Source: <https://github.com/HamzaYslmn/Forza-Horizon-DualSense-Python>

The body-haptics and USB-channel work references [HorizonHaptics](https://github.com/haritha99ch/HorizonHaptics). Its MIT notice is included in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

This project uses a custom source-available license for personal, non-commercial use. Read [LICENSE](LICENSE) before copying, modifying, or redistributing it.

---

<a id="readme-ja"></a>

<p align="right">
  <a href="#readme-zh-cn">简体中文</a> •
  <a href="#readme-en">English</a> •
  <strong>日本語</strong>
</p>

<div align="center">
  <img src="src/data/icon.png" alt="FH-DualSense-Enhanced" width="180">
  <h1>FH-DualSense-Enhanced</h1>
  <p><strong>PC 版 Forza Horizon に DualSense のアダプティブトリガーとテレメトリ駆動の握把触覚を追加します。</strong></p>
</div>

FH-DualSense-Enhanced `1.6.2.post1` は、`Forza-Horizon-DualSense-Python 1.6.2` を基にした拡張版です。ゲームが UDP で送信する車両テレメトリを読み取り、ブレーキ、アクセル、エンジン、路面、タイヤ、衝突の状態を DualSense のフィードバックに変換します。

このプロジェクトは上流プロジェクトの公式リリースではなく、上流作者の見解を示すものでもありません。

## 主な機能

- ブレーキ量に応じて左トリガーの抵抗が増加し、ABS 作動時にはパルスを発生させます。
- アクセル量に応じて右トリガーの抵抗が変化し、シフト、レッドライン、ホイールスピンを伝えます。
- エンジン、路面材質、サスペンション、衝突、水たまり、タイヤスリップ、バーンアウト、ABS に対応した握把触覚を備えています。
- 車両が完全に停止してアイドリングしているときは、意味のない連続振動を発生させません。
- 停車中の空ぶかしやバーンアウトでは、車両状態に合ったフィードバックが発生します。
- 路面材質の効果は、車両の移動またはタイヤの空転による実際の励振がある場合だけ加わります。
- USB と Bluetooth の両方に対応します。
- プロファイル、システムトレイ、ゲーム終了時の自動終了、ZUV 更新に対応します。

既定の調整値はコミュニティのフィードバックを参考にし、実際の走行テストで調整されています。多くの環境で使いやすい出発点ですが、すべての車両やプレイヤーに最適とは限りません。

## USB と Bluetooth

USB と Bluetooth の実用上の体験差は大きくありません。どちらでもアダプティブトリガーと握把触覚を利用できます。

| 接続方式 | 出力方式 |
| --- | --- |
| USB | DualSense の 4 チャンネル音声エンドポイントで左右の触覚を出力し、HID でトリガーを制御します |
| Bluetooth | 互換性のある低周波と高周波の振動を、トリガー状態と同じ HID レポートで送信します |

PC、コントローラーのファームウェア、Bluetooth アダプターによって細かな差が生じる場合があります。USB の音声エンドポイントを利用できない場合でも、トリガーフィードバックは引き続き動作します。

## クイックインストール

### Windows の推奨方法

1. [最新 Release](https://github.com/piereacy/FH-DualSense-Enhanced/releases/latest) を開きます。
2. `win_start.bat` だけをダウンロードします。
3. ダブルクリックして実行します。ランチャーが `FH-DualSense-Enhanced.zuv.py` をダウンロードし、uv と分離された Python 環境を自動的に準備します。

ネットワークが不安定な場合は、`FH-DualSense-Enhanced.zuv.py` も手動でダウンロードし、`win_start.bat` と同じフォルダーに置いてからランチャーを再実行してください。隣にあるバンドルが優先して使用されます。

### 単体 EXE

`FH-DualSense-Enhanced-vX.Y.Z.exe` だけをダウンロードしても使用できます。EXE には Python とすべてのアプリケーション依存関係が含まれているため、BAT、ZUV、uv、システムにインストールされた Python は不要です。

単体 EXE は自動更新されません。設定は EXE と同じ場所にある `data` フォルダーへ保存されます。

### Linux

`linux_start.sh` をダウンロードして実行します。ランチャーはアプリのダウンロードと起動だけを行い、システムの udev ルールはインストールしません。ログに DualSense の権限不足が表示された場合は、[`70-dualsense.rules`](packaging/linux/70-dualsense.rules) をダウンロードして、次を実行してください。

```bash
sudo cp 70-dualsense.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
```

完了後、USB コントローラーを接続し直すか、Bluetooth コントローラーを再ペアリングしてください。

## 必須のゲーム設定

### 1. Steam Input を有効にする

Steam ライブラリでゲームを右クリックし、**プロパティ -> コントローラー** を開いて、そのゲームの Steam Input を有効にします。Steam の DualSense 振動サポートも有効にしてください。

Steam Input はボタン割り当てとゲーム本来の振動を担当します。本アプリはアダプティブトリガーとテレメトリ駆動の握把触覚を追加します。

### 2. Forza Data Out を有効にする

Forza Horizon の **設定 -> HUD とゲームプレイ** を開き、Data Out の項目までスクロールします。

| 設定 | 値 |
| --- | --- |
| Data Out | ON |
| Data Out IP Address | `127.0.0.1` |
| Data Out IP Port | `5300` |

`127.0.0.1` でパケットを受信できない場合は、IPv6 ループバックアドレス `::1` を試し、アプリ側でも同じ待受アドレスを使用してください。

### 3. 起動順序

1. DualSense コントローラーを接続します。
2. FH-DualSense-Enhanced を起動します。
3. コントローラーが認識され、UDP の待受が開始されたことを確認します。
4. ゲームを起動します。

SISR などコントローラーを占有する可能性があるツールを使用する場合は、最初に FH-DualSense-Enhanced を起動し、その後でツールとゲームを起動してください。

### 4. ゲーム内の振動設定

握把触覚はテレメトリから独立して合成されるため、ゲーム内の振動設定には依存しません。通常は有効のままで問題ありません。ゲーム本来の振動と合成された触覚が重複して感じられる場合だけ、ゲーム内振動を無効にして比較してください。

## DualSense ボタンアイコン

Forza Horizon 6 の画面に PlayStation / DualSense のボタン表示を使用したい場合は、Nexus Mods の [PlayStation Controller Icons (DualSense)](https://www.nexusmods.com/forzahorizon6/mods/2) を利用できます。標準の Xbox ボタン表示を DualSense アイコンへ置き換える Mod です。

ゲームのアップデートによって、置き換えた画面ファイルが元に戻る場合があります。ゲーム更新後は、その都度 Mod ファイルをもう一度コピーして置き換えてください。

## 握把触覚の仕組み

アプリは固定波形を再生したり、状況を無視して振動し続けたりしません。すべてのレイヤーはリアルタイムのテレメトリから生成されます。

- エンジンレイヤーは RPM、負荷、アクセルに追従します。
- 路面レイヤーは速度、車輪回転、路面材質に追従します。
- スリップレイヤーは通常走行、グリップ喪失、停車中のバーンアウトを区別します。
- ABS はブレーキとタイヤの条件を満たしたときだけ作動します。
- 衝突、サスペンション、水たまりの各レイヤーは対応するイベントが発生したときだけ作動します。

**設定 -> 握把触覚** から、全体、エンジン、路面、衝突、スリップの強度を調整できます。握把触覚だけを無効にして、アダプティブトリガーを有効のまま残すこともできます。

## バックグラウンド動作

次の 2 項目は個別に設定できます。

- ゲーム終了時にアプリも終了する。
- ウィンドウを最小化したときにシステムトレイへ移動する。

どちらも必須ではありません。

## ファイアウォールとネットワーク

アプリはローカル UDP ポートを待ち受けるだけで、テレメトリをインターネットへアップロードしません。

ログに `No UDP packets yet` が表示され続ける場合:

1. Data Out、IP アドレス、ポートが正しいことを確認します。
2. Windows ファイアウォールで EXE を許可します。BAT モードでは、使用される `python.exe` と UDP 5300 も許可します。
3. 別のアプリインスタンスがすでに起動していないか確認します。
4. ファイアウォールを無効にするのは一時的な診断比較だけにし、確認後はすぐに有効へ戻してください。無効のまま使用しないでください。

## トラブルシューティング

| 症状 | 対処方法 |
| --- | --- |
| `No UDP packets yet` | Data Out、待受アドレス、UDP 5300、ファイアウォール規則を確認し、必要なら `::1` を試します |
| `WinError 10048` | UDP 5300 がすでに使用されています。重複したアプリインスタンスまたは別の待受プログラムを終了します |
| DualSense が見つからない | 接続、Steam による占有、HidHide の許可リストを確認します。BAT モードでは通常 `python.exe` の許可が必要です |
| USB 握把触覚を開始できない | Windows に DualSense の 4 チャンネル音声エンドポイントが表示されていることを確認し、それを使用中のアプリを閉じて USB を接続し直します |
| `PaErrorCode -9999` または WDM-KS エラー | アプリの互換バックエンドへの自動切り替えを待ちます。失敗が続く場合は Windows Audio とコントローラー音声デバイスを確認してください。トリガー機能は引き続き利用できます |
| Bluetooth の感触が少し異なる | Bluetooth は互換振動を使用するため正常です。フィードバックロジック自体は USB と同じです |
| トリガーまたは握把触覚が強すぎる | 設定で該当する強度を下げるか、車両専用のプロファイルを作成します |

## 開発とビルド

```powershell
git clone https://github.com/piereacy/FH-DualSense-Enhanced.git
cd FH-DualSense-Enhanced\src
uv sync
uv run main.py
```

テストを実行:

```powershell
uv run --project src pytest -q
```

ZUV をビルド:

```powershell
set UPDATE_REPO=piereacy/FH-DualSense-Enhanced
packaging\zuv\build_zuv.bat
```

Windows EXE をビルド:

```powershell
packaging\windows\build_exe.bat
```

## プロジェクトの由来とライセンス

FH-DualSense-Enhanced は次のプロジェクトを変更したものです。

Originally created by Hamza Yeşilmen (HamzaYslmn).

Source: <https://github.com/HamzaYslmn/Forza-Horizon-DualSense-Python>

握把触覚と USB チャンネルの実装では [HorizonHaptics](https://github.com/haritha99ch/HorizonHaptics) を参照しています。MIT ライセンス表記は [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) に収録されています。

本プロジェクトは、個人かつ非商用利用に限定した独自のソース公開ライセンスを採用しています。コピー、変更、再配布を行う前に [LICENSE](LICENSE) を全文確認してください。

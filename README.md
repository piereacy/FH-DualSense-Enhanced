<p align="right">
  <strong>English</strong> •
  <a href="docs/ReadmeZH.md">简体中文</a> •
  <a href="docs/ReadmeJA.md">日本語</a>
</p>

<div align="center">
  <img src="src/data/icon.png" alt="FH-DualSense-Enhanced" width="180">
  <h1>FH-DualSense-Enhanced</h1>
  <p><strong>Adaptive triggers and telemetry-driven DualSense haptics for Forza Horizon on PC.</strong></p>
</div>

FH-DualSense-Enhanced reads Forza Horizon Data Out telemetry and turns braking, throttle, engine, road, tire, and impact data into DualSense feedback.

This is an unofficial enhanced fork based on `Forza-Horizon-DualSense-Python 1.6.2`, with haptics work informed by `HorizonHaptics 1.3.0`.

## Highlights

- Adaptive L2 and R2 triggers for braking, ABS, throttle, and wheelspin.
- Body haptics for the engine, road surface, suspension, water, tire slip, and impacts.
- Directional collision feedback and surface-aware grip effects driven by live telemetry.
- The same trigger and telemetry effect set over USB and Bluetooth.
- Adjustable strengths, per-car profiles, and community-informed defaults.
- Optional controller lighting and a focused desktop interface.

## Download

### Windows, recommended

1. Open the [latest release](https://github.com/piereacy/FH-DualSense-Enhanced/releases/latest).
2. Download `FH-DualSense-Enhanced-R<n>.exe`.
3. Run the EXE. Python, BAT, ZUV, and uv are not required.

Other launch options:

- Windows bootstrap: download `win_start.bat`. If your connection is unreliable, place `FH-DualSense-Enhanced.zuv.py` beside it before running.
- Linux: download `linux_start.sh`. If controller permissions fail, install the provided [`70-dualsense.rules`](packaging/linux/70-dualsense.rules) manually.

## Required game setup

### 1. Enable Steam Input

In Steam, open **Game Properties -> Controller** and enable Steam Input for the game. Enable DualSense vibration support in Steam as well.

### 2. Enable Forza Data Out

In Forza Horizon, open **Settings -> HUD and Gameplay** and set:

| Setting | Value |
| --- | --- |
| Data Out | ON |
| Data Out IP Address | `127.0.0.1` |
| Data Out IP Port | `5300` |

If loopback packets are not received, try `::1` in both the game and the app.

### 3. Start in this order

1. Connect the DualSense controller.
2. Start FH-DualSense-Enhanced and confirm that the controller and UDP listener are ready.
3. Start the game.

> [!IMPORTANT]
> Keep Steam Input enabled, but turn **Vibration** off in Forza's own settings. Native game rumble competes with and masks the controller's grip haptics, so grip feedback will not work correctly while in-game vibration is enabled.

## USB and Bluetooth

Both connections use the same telemetry decisions and support adaptive triggers, road detail, engine feedback, redline effects, and directional impacts.

| Connection | Notes |
| --- | --- |
| USB | Body haptics use the DualSense audio endpoint; adaptive triggers use HID. |
| Bluetooth | Haptics and triggers are sent through HID. If HD haptics are unavailable, the app falls back automatically while keeping trigger support. |

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| `No UDP packets yet` | Verify Data Out, the listen address, UDP port `5300`, and the Windows Firewall rule. |
| `WinError 10048` | Another app instance already owns UDP port `5300`; close the duplicate listener. |
| DualSense not found | Reconnect the controller and check Steam, HidHide, or another app that may have claimed it. |
| USB haptics or `PaErrorCode -9999` | Check the DualSense audio device, close apps using it, and reconnect USB. Trigger feedback remains available. |
| Bluetooth haptics fallback | Reconnect the controller to retry HD haptics. Trigger feedback remains available during fallback. |

## DualSense button icons

For PlayStation button prompts in Forza Horizon 6, see [PlayStation Controller Icons (DualSense)](https://www.nexusmods.com/forzahorizon6/mods/2). Game updates may restore the original files, so the mod may need to be applied again.

## Credits and license

Originally created by Hamza Yeşilmen (HamzaYslmn):
[Forza-Horizon-DualSense-Python](https://github.com/HamzaYslmn/Forza-Horizon-DualSense-Python)

The body-haptics work references [HorizonHaptics](https://github.com/haritha99ch/HorizonHaptics), and the Bluetooth protocol work references [vDS](https://github.com/hurryman2212/vds). Their notices are included in [THIRD_PARTY_NOTICES.md](docs/THIRD_PARTY_NOTICES.md).

This project uses a custom source-available license for personal, non-commercial use. Read [LICENSE](LICENSE) before copying, modifying, or redistributing it.

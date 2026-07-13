<p align="right">
  <a href="README.md">简体中文</a> | <strong>English</strong>
</p>

<div align="center">
  <img src="src/data/icon.png" alt="FH-DualSense-Enhanced" width="180">
  <h1>FH-DualSense-Enhanced</h1>
  <p><strong>DualSense adaptive triggers and telemetry-driven body haptics for Forza Horizon on PC.</strong></p>
</div>

FH-DualSense-Enhanced is an enhanced fork based on `Forza-Horizon-DualSense-Python 1.6.2`. It reads vehicle telemetry sent by the game over UDP and turns braking, throttle, engine, road, tire, and impact states into DualSense feedback.

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

Download and run `linux_start.sh`. Linux requires hidapi and suitable udev permissions; the launcher provides setup guidance.

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

The body-haptics and USB-channel work references [HorizonHaptics](https://github.com/haritha99ch/HorizonHaptics). Its MIT notice is included in [THIRD_PARTY_NOTICES.md](docs/THIRD_PARTY_NOTICES.md).

This project uses a custom source-available license for personal, non-commercial use. Read [LICENSE](LICENSE) before copying, modifying, or redistributing it.

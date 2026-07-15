<p align="right">
  <a href="../README.md">简体中文</a> •
  <strong>English</strong> •
  <a href="ReadmeJA.md">日本語</a>
</p>

<div align="center">
  <img src="../src/data/icon.png" alt="FH-DualSense-Enhanced" width="180">
  <h1>FH-DualSense-Enhanced</h1>
  <p><strong>DualSense adaptive triggers and telemetry-driven body haptics for Forza Horizon on PC.</strong></p>
</div>

FH-DualSense-Enhanced `R3` is an enhanced fork based on `Forza-Horizon-DualSense-Python 1.6.2` and informed by `HorizonHaptics 1.3.0`. It reads vehicle telemetry sent by the game over UDP and turns braking, throttle, engine, road, tire, and impact states into DualSense feedback.

This is not an official upstream release and does not represent the upstream author's views.

Starting with R2, this project uses its own concise `R` version series to avoid looking like an official upstream version. Historical Enhanced R1 used `1.6.2.post1`; the upstream base version is no longer embedded in the current product version.

## Highlights

- The L2 trigger provides progressive brake resistance and a GT7-style ABS wall, preserving an upper resistance wall while pulsing the lower zones.
- The R2 trigger provides dynamic wheelspin feedback derived from driven-wheel slip, low-speed wheel rotation, asymmetric EWMA smoothing, hysteresis, and G-force damping; it takes priority over the rev limiter.
- Traction feedback follows pedal state: brake only routes to L2, throttle only routes to the R2 trigger, and pressing both routes traction to the R2 trigger while L2 ABS remains independent.
- Tarmac, puddles, dirt, and gravel use distinct R2-trigger material frequency bands.
- Body haptics for engine, road material, suspension, impacts, puddles, tire slip, burnouts, and ABS.
- R2-trigger redline and grip redline use independent switches. Trigger redline is off by default, while grip redline is on by default and provides an enhanced fuel-cut pulse on the left grip.
- Collision body feedback uses a directional envelope. The optional grip gear-shift thump is off by default and has independent strength and duration controls.
- No meaningless continuous vibration when the vehicle is truly stationary at idle.
- Revving and burnouts while stationary still produce appropriate feedback.
- Road material contributes only while the car moves or the tires create physical excitation.
- USB and Bluetooth support.
- Profiles, tray behavior, exit-with-game behavior, and ZUV updates.
- Advanced traction, ABS, redline, and collision controls live under a collapsed Experimental section. Grip gear-shift tuning is a normal setting.

The default tuning is informed by community feedback and refined through hands-on driving tests. It is a practical starting point, not a universal setting for every car or player.

## USB and Bluetooth

USB and Bluetooth now use the same stereo waveform synthesis. Both retain adaptive triggers, road texture, engine, redline, and directional collision feedback.

| Connection | Output path |
| --- | --- |
| USB | Uses the DualSense four-channel audio endpoint for left and right haptics, plus HID trigger control |
| Bluetooth | Sends 3 kHz stereo HD haptics directly over HID report `0x36`; trigger state remains under HID control |

Small differences can depend on the PC, controller firmware, and Bluetooth adapter. If Bluetooth HD haptics cannot start, the app automatically falls back to compatible rumble; a haptics failure does not block triggers.

## Quick installation

### Recommended Windows method

1. Open the [latest Release](https://github.com/piereacy/FH-DualSense-Enhanced/releases/latest).
2. Download only `win_start.bat`.
3. Run it. The launcher downloads `FH-DualSense-Enhanced.zuv.py` and prepares uv plus an isolated Python environment.

For the manual network fallback, also download `FH-DualSense-Enhanced.zuv.py`, place it beside `win_start.bat`, and run the launcher again. The adjacent bundle is used first.

### Standalone EXE

Downloading only `FH-DualSense-Enhanced-R3.exe` also works. The EXE includes Python and all application dependencies, so BAT, ZUV, uv, and a system Python installation are not required.

The standalone EXE does not update itself. Settings are stored in a `data` folder beside the EXE.

To try rolling test builds, use the `R3-preview` Release and run `uv run FH-DualSense-Enhanced.zuv.py --prerelease` to follow the prerelease channel.

### Linux

Download and run `linux_start.sh`. The launcher only downloads and starts the application; it does not install system udev rules. If the log reports insufficient DualSense permissions, download [`70-dualsense.rules`](../packaging/linux/70-dualsense.rules), then run:

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

Body haptics are synthesized from telemetry and do not depend on the in-game vibration toggle. Keeping it enabled preserves menu, cutscene, and other native game rumble, but native rumble can mask this project's left/right collision direction. Disable in-game vibration when validating direction or comparing duplicated output. This project does not currently capture or fully reproduce native game rumble.

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
| Log reports a Bluetooth HD haptics fallback | The current connection rejected report `0x36`; compatible rumble remains active and HD haptics is retried after reconnecting the controller |
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

The body-haptics and USB-channel work references [HorizonHaptics](https://github.com/haritha99ch/HorizonHaptics). The Bluetooth HD haptics protocol references [vDS](https://github.com/hurryman2212/vds). Their MIT notices are included in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

This project uses a custom source-available license for personal, non-commercial use. Read [LICENSE](../LICENSE) before copying, modifying, or redistributing it.

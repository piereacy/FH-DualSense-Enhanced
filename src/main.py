import argparse
import logging
import os
import sys
import traceback
from datetime import datetime
from dotenv import load_dotenv
load_dotenv("./dev.env")


from modules import forzahorizon, make_backend, setup_logging, loop
from modules.config import paths, preferences, Settings

log = logging.getLogger("fhds")

# MARK: Crash log - only written on unhandled exceptions
CRASH_LOG = paths.DATA / "crash.log"


def _excepthook(exc_type, exc, tb):
    if issubclass(exc_type, KeyboardInterrupt):
        print("\nInterrupted.", file=sys.stderr)
        return
    try:
        paths.DATA.mkdir(parents=True, exist_ok=True)
        with open(CRASH_LOG, "w", encoding="utf-8") as f:
            f.write(f"Crash at {datetime.now():%Y-%m-%d %H:%M:%S}\n\n")
            traceback.print_exception(exc_type, exc, tb, file=f)
    except OSError:
        pass
    log.critical("Unhandled exception", exc_info=(exc_type, exc, tb))


def _log_zuv_status() -> None:
    found = os.environ.get("IS_ZUV", "").lower() == "true"
    print(f"ZUV: {'detected' if found else 'not detected'}", file=sys.stderr, flush=True)


def run(s: Settings) -> None:
    ds = make_backend(s, s.enable_startup_pulse)
    ds.open()
    try:
        with forzahorizon.UDPListener(s.udp_host, s.udp_port, s.udp_timeout,
                                      s.udp_forward_to, s.udp_forward) as listener:
            log.info("Listening on %s:%d | Ctrl+C to quit", s.udp_host, s.udp_port)
            log.info("  In game: HUD & Gameplay -> Data Out: ON, IP 127.0.0.1, Port %d", s.udp_port)
            if s.use_dsx:
                log.info("  DSX mode: sending triggers to %s:%d", s.dsx_host, s.dsx_port)
            loop.run(ds, listener, s)
    finally:
        ds.close()


def run_tui(s: Settings) -> None:
    from modules.tui import TriggerTUI
    TriggerTUI(s).run()


def run_gui(s: Settings) -> None:
    from modules.gui import TriggerGUI
    TriggerGUI(s).run()


def _confirm(prompt: str) -> bool:
    try:
        return input(prompt).strip().lower() in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        return False


# MARK: Entry point
if __name__ == "__main__":
    p = argparse.ArgumentParser(description="FH DualSense adaptive triggers and optional body haptics")
    p.add_argument("--host", default="127.0.0.1", help="UDP bind address")
    p.add_argument("--port", type=int, default=None, help="UDP port")
    p.add_argument("--debug", action="store_true", help="Verbose per-packet logs")
    p.add_argument("--headless", action="store_true", help="Disable UI, use console logs")
    p.add_argument("--gui", action="store_true", help="Use the CustomTkinter GUI instead of the TUI")
    p.add_argument("--tui", action="store_true", help="Force the Textual TUI (overrides UI env var)")
    args = p.parse_args()

    settings = Settings()
    try:
        preferences.load(settings)
    except preferences.PreferencesError as e:
        print(f"\n{e}", file=sys.stderr)
        if not _confirm(f"Reset {preferences.PATH.name} to defaults? "
                        f"(backup saved as {preferences.PATH.name}.bak) [y/N]: "):
            print("Aborted. Please fix or delete the file manually, then retry.",
                  file=sys.stderr)
            sys.exit(1)
        preferences.reset_file()
        preferences.load(settings)
    if args.host is not None: settings.udp_host = args.host
    if args.port is not None: settings.udp_port = args.port

    sys.excepthook = _excepthook

    _log_zuv_status()

    try:
        if args.headless:
            setup_logging(args.debug)
            run(settings)
        elif args.tui:
            run_tui(settings)
        elif args.gui:
            run_gui(settings)
        elif getattr(sys, "frozen", False):
            run_gui(settings)
        else:
            run_gui(settings)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)

import argparse
import logging
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path

from modules import forzahorizon, make_backend, setup_logging, loop
from modules.about import APP_NAME
from modules.config import paths, preferences, Settings
from modules.dpi import bootstrap_windows_dpi
from modules.update.install import launch_legacy_bootstrap, recover_incomplete_updates
from modules.update.transaction import write_health_ack
from modules.xinput.service import XInputBridgeService

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


def run(s: Settings, *, on_ready=None) -> None:
    ds = make_backend(s, s.enable_startup_pulse)
    xinput = XInputBridgeService(s)
    try:
        ds.open()
        xinput.sync(ds)
        with forzahorizon.UDPListener(s.udp_host, s.udp_port, s.udp_timeout,
                                      s.udp_forward_to, s.udp_forward) as listener:
            log.info("Listening on %s:%d | Ctrl+C to quit", s.udp_host, s.udp_port)
            log.info("  In game: HUD & Gameplay -> Data Out: ON, IP 127.0.0.1, Port %d", s.udp_port)
            if s.use_dsx:
                log.info("  DSX mode: sending triggers to %s:%d", s.dsx_host, s.dsx_port)
            if on_ready is not None:
                on_ready()
            loop.run(ds, listener, s)
    finally:
        xinput.stop()
        ds.close()


def run_tui(s: Settings, *, on_ready=None) -> None:
    from modules.tui import TriggerTUI
    app = TriggerTUI(s, on_ready=on_ready)
    app.run()


def run_gui(s: Settings, *, on_ready=None) -> None:
    from modules.gui import TriggerGUI
    app = TriggerGUI(s, on_ready=on_ready)
    app.run()


def _confirm(prompt: str) -> bool:
    try:
        return input(prompt).strip().lower() in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        return False


def _release_number() -> int:
    label = preferences._release_version()
    try:
        return int(label.removeprefix("R"))
    except ValueError:
        return 0


def acknowledge_update_health(
    transaction_id: str,
    token: str,
    *,
    executable=None,
    pid: int | None = None,
):
    """Confirm that the selected application mode reached its usable boundary."""
    if not transaction_id and not token:
        return None
    if not transaction_id or not token:
        raise ValueError("both update transaction id and token are required")
    version = _release_number()
    if version <= 0:
        raise ValueError("application release version is unavailable")
    return write_health_ack(
        root=paths.DATA / "updates" / "transactions",
        transaction_id=transaction_id,
        token=token,
        executable=Path(sys.executable if executable is None else executable),
        version=version,
        pid=pid,
    )


def _confirm_gui_preferences_reset(error: Exception, *, on_ready=None) -> bool:
    """Show preference recovery in a real GUI instead of a hidden console."""
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        root.update_idletasks()
        if on_ready is not None:
            on_ready()
        try:
            return bool(
                messagebox.askyesno(
                    f"{APP_NAME} - Preferences",
                    f"{error}\n\nReset {preferences.PATH.name} to defaults? "
                    f"A backup will be saved as {preferences.PATH.name}.bak.",
                    parent=root,
                )
            )
        finally:
            root.destroy()
    except Exception as exc:
        print(f"Could not show preferences recovery dialog: {exc}", file=sys.stderr)
        return False


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=f"{APP_NAME} adaptive triggers and optional body haptics"
    )
    parser.add_argument("--host", default=None, help="UDP bind address")
    parser.add_argument("--port", type=int, default=None, help="UDP port")
    parser.add_argument("--debug", action="store_true", help="Verbose per-packet logs")
    parser.add_argument("--headless", action="store_true", help="Disable UI, use console logs")
    parser.add_argument("--gui", action="store_true", help="Use the CustomTkinter GUI instead of the TUI")
    parser.add_argument("--tui", action="store_true", help="Force the Textual TUI (overrides UI env var)")
    parser.add_argument("--fhds-update-transaction", default="", help=argparse.SUPPRESS)
    parser.add_argument("--fhds-update-token", default="", help=argparse.SUPPRESS)
    return parser


def main(argv: list[str] | None = None) -> int:
    bootstrap_windows_dpi()
    args = _parser().parse_args(argv)
    try:
        legacy_plan = launch_legacy_bootstrap(argv=list(argv) if argv is not None else None)
    except Exception:
        try:
            paths.DATA.mkdir(parents=True, exist_ok=True)
            with (paths.DATA / "legacy-update-bootstrap-error.log").open(
                "w", encoding="utf-8"
            ) as stream:
                traceback.print_exc(file=stream)
        except OSError:
            pass
        legacy_plan = None
    if legacy_plan is not None:
        return 0

    try:
        recover_incomplete_updates(
            active_transaction_id=args.fhds_update_transaction,
            ready=False,
        )
    except Exception:
        log.exception("Update transaction startup recovery failed")

    health_done = False

    def acknowledge_once():
        nonlocal health_done
        if health_done:
            return None
        result = acknowledge_update_health(
            args.fhds_update_transaction,
            args.fhds_update_token,
        )
        try:
            recover_incomplete_updates(
                active_transaction_id=args.fhds_update_transaction,
                ready=True,
            )
        except Exception:
            log.exception("Update transaction ready recovery failed")
        health_done = True
        return result

    settings = Settings()
    try:
        preferences.load(settings)
    except preferences.PreferencesError as error:
        print(f"\n{error}", file=sys.stderr)
        gui_mode = not args.headless and not args.tui
        if gui_mode:
            confirmed = _confirm_gui_preferences_reset(error, on_ready=acknowledge_once)
        else:
            confirmed = _confirm(
                f"Reset {preferences.PATH.name} to defaults? "
                f"(backup saved as {preferences.PATH.name}.bak) [y/N]: "
            )
        if not confirmed:
            print(
                "Aborted. Please fix or delete the file manually, then retry.",
                file=sys.stderr,
            )
            return 1
        try:
            preferences.reset_file()
            preferences.load(settings)
        except preferences.PreferencesError as reset_error:
            print(f"Preferences reset failed: {reset_error}", file=sys.stderr)
            return 1
    if args.host is not None:
        settings.udp_host = args.host
    if args.port is not None:
        settings.udp_port = args.port

    sys.excepthook = _excepthook
    _log_zuv_status()

    try:
        if args.headless:
            setup_logging(args.debug)
            run(settings, on_ready=acknowledge_once)
        elif args.tui:
            run_tui(settings, on_ready=acknowledge_once)
        else:
            run_gui(settings, on_ready=acknowledge_once)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
    return 0


# MARK: Entry point
if __name__ == "__main__":
    raise SystemExit(main())

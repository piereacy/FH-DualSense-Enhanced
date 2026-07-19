"""At-a-glance status and shortcuts shared by the GUI shell."""
from __future__ import annotations

import logging
import queue
import tkinter as tk
import threading
import time

import customtkinter as ctk

from lang import t
from modules.config import preferences, profiles
from modules.forzahorizon import (
    DEFAULT_FORZA_GAME_KEY,
    FORZA_GAME_KEYS,
    FORZA_GAMES,
    ForzaInstall,
    discover_forza_install,
    get_forza_game,
    is_forza_game_running,
    is_windows_steam_supported,
    launch_forza_via_steam,
    launch_forza_via_xbox_app,
)
from modules.xinput.bridge import BridgeStatus
from modules.xinput.driver import InstallStatus
from modules.xinput.service import (
    STEAM_PLATFORM,
    XBOX_APP_PLATFORM,
    normalize_forza_platform,
)
from . import theme as T
from . import widgets as W
from .dialogs import ConfirmationDialog
from .overview_status import (
    controller_status,
    forza_launch_button_status,
    profile_status,
    should_scan_forza_install,
    telemetry_status,
    update_status,
    xinput_bridge_status,
)

log = logging.getLogger("fhds.gui.overview")

FORZA_SCAN_INTERVAL_S = 30.0
FORZA_LAUNCH_TIMEOUT_S = 20.0


class OverviewTab(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.settings = app.settings
        self._selected_game_key = self._validated_preferred_game()
        self._selected_platform = self._validated_preferred_platform()
        self._game_installs: dict[str, ForzaInstall] = {}
        self._game_scan_busy: dict[str, int] = {}
        self._game_scan_serial = 0
        self._game_last_scan = {key: 0.0 for key in FORZA_GAME_KEYS}
        self._game_scan_has_result = {key: False for key in FORZA_GAME_KEYS}
        self._game_path_hints = {
            key: str(getattr(self.settings, FORZA_GAMES[key].install_path_field, ""))
            for key in FORZA_GAME_KEYS
        }
        self._launching_game_key: str | None = None
        self._launch_request_busy = False
        self._game_launch_deadline = 0.0
        self._game_scan_results: queue.SimpleQueue[
            tuple[str, int, ForzaInstall | None]
        ] = queue.SimpleQueue()
        self._game_launch_results: queue.SimpleQueue[
            tuple[str, str, str, bool]
        ] = queue.SimpleQueue()
        self._driver_install_busy = False
        self._status_render_cache: dict[str, tuple[str, str]] = {}
        self._bridge_render_cache = None
        self._launch_render_cache = None
        self._build()
        app.register_refresh(self.refresh)
        self.refresh()

    def _validated_preferred_game(self) -> str:
        key = str(
            getattr(self.settings, "preferred_forza_game", DEFAULT_FORZA_GAME_KEY)
        ).strip().casefold()
        try:
            get_forza_game(key)
        except ValueError:
            log.warning(
                "Unsupported saved Forza game key %r; restoring %s",
                key,
                DEFAULT_FORZA_GAME_KEY,
            )
            key = DEFAULT_FORZA_GAME_KEY
            self.settings.preferred_forza_game = key
            preferences.save(self.settings)
        return key

    def _validated_preferred_platform(self) -> str:
        raw = getattr(self.settings, "preferred_forza_platform", STEAM_PLATFORM)
        platform = normalize_forza_platform(raw)
        if platform != raw:
            self.settings.preferred_forza_platform = platform
            preferences.save(self.settings)
        return platform

    def _build(self):
        W.PageHeader(
            self, t("Overview"),
            t("Controller, telemetry, profile, and update status at a glance."),
        ).pack(fill="x", pady=(0, T.PAD_MD))

        scroll = W.FastScroll(self)
        scroll.pack(fill="both", expand=True)

        status = ctk.CTkFrame(scroll, fg_color="transparent")
        status.pack(fill="x")
        for col in range(2):
            status.grid_columnconfigure(col, weight=1, uniform="overview")

        _, self.controller_value, self.controller_hint = self._status_card(
            status, 0, t("DualSense"), t("Waiting"), t("USB or Bluetooth")
        )
        _, self.telemetry_value, self.telemetry_hint = self._status_card(
            status, 1, t("Forza telemetry"), t("Waiting for packets"), t("UDP data out")
        )
        _, self.profile_value, self.profile_hint = self._status_card(
            status, 2, t("Active profile"), "-", t("Changes save instantly")
        )
        _, self.update_value, self.update_hint = self._status_card(
            status, 3, t("Updates"), t("Update status: idle"), t("Built-in updater")
        )

        quick = W.Card(scroll)
        quick.pack(fill="x", pady=(T.PAD_MD, 0))
        W.H2(quick, t("Quick access")).pack(
            anchor="w", padx=T.PAD_MD, pady=(T.PAD_MD, T.PAD_SM)
        )
        row = ctk.CTkFrame(quick, fg_color="transparent")
        row.pack(fill="x", padx=T.PAD_MD, pady=(0, T.PAD_MD))
        row.grid_columnconfigure((0, 1), weight=1, uniform="quick")
        W.PrimaryButton(
            row, text=t("Driving feedback"), command=lambda: self.app._select_nav("Driving")
        ).grid(row=0, column=0, sticky="ew", padx=(0, T.PAD_XS), pady=(0, T.PAD_XS))
        W.SecondaryButton(
            row, text=t("Grip haptics"), command=lambda: self.app._select_nav("Haptics")
        ).grid(row=0, column=1, sticky="ew", padx=(T.PAD_XS, 0), pady=(0, T.PAD_XS))
        W.SecondaryButton(
            row, text=t("System and updates"), command=lambda: self.app._select_nav("System")
        ).grid(row=1, column=0, sticky="ew", padx=(0, T.PAD_XS), pady=(T.PAD_XS, 0))
        W.DangerButton(
            row, text=t("Restore defaults"), command=self.app.request_factory_reset
        ).grid(row=1, column=1, sticky="ew", padx=(T.PAD_XS, 0), pady=(T.PAD_XS, 0))
        self._platform_label_to_key = {
            "Steam": STEAM_PLATFORM,
            "Xbox App": XBOX_APP_PLATFORM,
        }
        self._platform_key_to_label = {
            value: key for key, value in self._platform_label_to_key.items()
        }
        self._platform_selector = ctk.CTkSegmentedButton(
            row,
            values=list(self._platform_label_to_key),
            command=self._select_forza_platform,
        )
        self._platform_selector.set(
            self._platform_key_to_label[self._selected_platform]
        )
        self._platform_selector.grid(
            row=2,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(T.PAD_SM, 0),
        )
        launch_group = ctk.CTkFrame(row, fg_color="transparent")
        launch_group.grid_columnconfigure(0, weight=1)
        launch_group.grid_columnconfigure(1, weight=0)
        launch_group.grid(
            row=3,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(T.PAD_SM, 0),
        )
        self._game_launch_button = W.PrimaryButton(
            launch_group,
            text=t("Finding {game}...").format(
                game=FORZA_GAMES[self._selected_game_key].short_name
            ),
            command=self._launch_selected_game,
        )
        self._game_launch_button.grid(row=0, column=0, sticky="ew", padx=(0, 2))
        self._game_launch_button.configure(state="disabled")
        self._game_selector_button = W.PrimaryButton(
            launch_group,
            text="▾",
            width=42,
            command=self._show_forza_game_menu,
        )
        self._game_selector_button.grid(row=0, column=1, sticky="e")
        self._game_choice_var = tk.StringVar(master=self, value=self._selected_game_key)
        self._game_menu = tk.Menu(
            self,
            tearoff=False,
            bg=T.BG_PANEL[1],
            fg=T.TEXT[1],
            activebackground=T.BG_ACTIVE[1],
            activeforeground=T.TEXT[1],
            selectcolor=T.ACCENT,
            relief="flat",
            borderwidth=1,
        )
        for key in FORZA_GAME_KEYS:
            game = FORZA_GAMES[key]
            self._game_menu.add_radiobutton(
                label=game.full_name,
                value=key,
                variable=self._game_choice_var,
                command=lambda selected=key: self._select_forza_game(selected),
            )
        self._bridge_status = W.Body(row, "")
        self._bridge_status.grid(
            row=4,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(T.PAD_SM, 0),
        )
        self._bridge_hint = W.Hint(row, "", wrap=self.app.px(640))
        self._bridge_hint.grid(
            row=5,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(T.PAD_XS, 0),
        )
        self._bridge_action = W.SecondaryButton(
            row,
            text=t("Install ViGEmBus"),
            command=self._on_bridge_action,
        )

    @staticmethod
    def _status_card(parent, index, title, value, hint):
        row, column = divmod(index, 2)
        card = W.Card(parent)
        card.grid(row=row, column=column, sticky="nsew",
                  padx=(0 if column == 0 else T.PAD_SM // 2,
                        T.PAD_SM // 2 if column == 0 else 0),
                  pady=(0 if row == 0 else T.PAD_SM // 2,
                        T.PAD_SM // 2 if row == 0 else 0))
        W.Hint(card, title).pack(anchor="w", padx=T.PAD_MD, pady=(T.PAD_MD, T.PAD_XS))
        value_label = ctk.CTkLabel(
            card, text=value, anchor="w", text_color=T.TEXT,
            font=ctk.CTkFont(size=T.FS_H1, weight="bold"),
        )
        value_label.pack(fill="x", padx=T.PAD_MD)
        hint_label = W.Hint(card, hint)
        hint_label.pack(anchor="w", padx=T.PAD_MD, pady=(T.PAD_XS, T.PAD_MD))
        return card, value_label, hint_label

    def refresh(self):
        controller = controller_status(
            getattr(self.app, "_ds", None),
            self.settings,
            t,
            error=getattr(self.app, "_backend_error", ""),
        )
        telemetry = telemetry_status(
            getattr(self.app, "_listener", None),
            self.settings,
            t,
            error=getattr(self.app, "_udp_error", ""),
        )
        try:
            profile = profile_status(profiles.active_name(), t)
        except Exception as exc:
            profile = profile_status("", t, error=str(exc))
        update = update_status(self.app._update_service, self.settings, t)

        for key, value_widget, hint_widget, status in (
            ("controller", self.controller_value, self.controller_hint, controller),
            ("telemetry", self.telemetry_value, self.telemetry_hint, telemetry),
            ("profile", self.profile_value, self.profile_hint, profile),
            ("update", self.update_value, self.update_hint, update),
        ):
            render = (status.value, status.hint)
            if self._status_render_cache.get(key) == render:
                continue
            self._status_render_cache[key] = render
            value_widget.configure(text=status.value)
            hint_widget.configure(text=status.hint)
        self._refresh_platform_status()
        self._refresh_forza_launch()

    def _refresh_platform_status(self):
        visible = xinput_bridge_status(
            getattr(self.app, "_xinput_service", None),
            self._selected_platform,
            t,
        )
        action_kind = ""
        if self._selected_platform == XBOX_APP_PLATFORM:
            snapshot = self.app._xinput_service.snapshot()
            if snapshot.status is BridgeStatus.DRIVER_MISSING:
                action_kind = "install"
            elif snapshot.status is BridgeStatus.ERROR:
                action_kind = "retry"
        action_label = {
            "install": t("Install ViGEmBus"),
            "retry": t("Retry XInput bridge"),
        }.get(action_kind, "")
        action_state = "disabled" if self._driver_install_busy else "normal"
        render = (
            visible.value,
            visible.hint,
            action_kind,
            action_label,
            action_state,
        )
        previous = self._bridge_render_cache
        if render == previous:
            return
        self._bridge_render_cache = render
        if previous is None or previous[:2] != render[:2]:
            self._bridge_status.configure(text=visible.value)
            self._bridge_hint.configure(text=visible.hint)
        previous_kind = previous[2] if previous is not None else ""
        if not action_kind:
            if previous_kind:
                self._bridge_action.grid_forget()
            return
        if previous is None or previous[2:] != render[2:]:
            self._bridge_action.configure(text=action_label, state=action_state)
        if not previous_kind:
            self._bridge_action.grid(
                row=6,
                column=0,
                columnspan=2,
                sticky="w",
                pady=(T.PAD_SM, 0),
            )

    def _render_forza_launch(self, label: str, enabled: bool):
        selector_state = "disabled" if self._launch_request_busy else "normal"
        render = (
            self._selected_platform,
            self._selected_game_key,
            label,
            bool(enabled),
            selector_state,
        )
        previous = self._launch_render_cache
        if render == previous:
            return
        self._launch_render_cache = render
        if previous is None or previous[2:4] != render[2:4]:
            self._game_launch_button.configure(
                text=label,
                state="normal" if enabled else "disabled",
            )
        if previous is None or previous[4] != selector_state:
            self._game_selector_button.configure(state=selector_state)
            self._platform_selector.configure(state=selector_state)

    def _refresh_forza_launch(self):
        if self.app._tearing_down:
            return
        self._drain_game_worker_results()
        now = time.monotonic()
        key = self._selected_game_key
        game = FORZA_GAMES[key]
        if self._selected_platform == XBOX_APP_PLATFORM:
            try:
                running = is_forza_game_running(game)
            except Exception:
                running = False
                log.exception("%s process check failed", game.short_name)
            launching = self._launching_game_key == key
            if launching and running:
                self._clear_launch_wait()
                launching = False
            elif launching and now >= self._game_launch_deadline:
                log.warning("%s did not start before the Xbox launch timeout", game.short_name)
                self._clear_launch_wait()
                launching = False
                self.app.toast(
                    t("{game} did not start before the timeout").format(
                        game=game.short_name
                    )
                )
            if running:
                label = t("{game} is running").format(game=game.short_name)
                enabled = False
            elif launching:
                label = t("Launching {game}...").format(game=game.short_name)
                enabled = False
            else:
                label = t("Launch {game} with Xbox App").format(
                    game=game.short_name
                )
                enabled = True
            self._render_forza_launch(label, enabled)
            return
        path_hint = str(getattr(self.settings, game.install_path_field, ""))
        if path_hint != self._game_path_hints[key]:
            self._game_path_hints[key] = path_hint
            self._game_installs.pop(key, None)
            self._game_scan_busy.pop(key, None)
            self._game_scan_has_result[key] = False
            self._game_last_scan[key] = 0.0

        install = self._game_installs.get(key)
        try:
            running = is_forza_game_running(game, install)
        except Exception:
            running = False
            log.exception("%s process check failed", game.short_name)

        if self._launching_game_key == key:
            if running:
                self._clear_launch_wait()
            elif now >= self._game_launch_deadline:
                log.warning("%s did not start before the launch timeout", game.short_name)
                self._clear_launch_wait()
                self.app.toast(
                    t("{game} did not start before the timeout").format(
                        game=game.short_name
                    )
                )

        supported = is_windows_steam_supported()
        scanning = key in self._game_scan_busy
        launching = self._launching_game_key == key
        if should_scan_forza_install(
            supported=supported,
            installed=install is not None,
            scanning=scanning,
            launching=launching,
            has_result=self._game_scan_has_result[key],
            now=now,
            last_scan=self._game_last_scan[key],
            retry_interval=FORZA_SCAN_INTERVAL_S,
        ):
            self._start_game_scan(key)
            scanning = True

        status = forza_launch_button_status(
            t,
            game_label=game.short_name,
            supported=supported,
            scanning=scanning and not self._game_scan_has_result[key],
            installed=install is not None,
            running=running,
            launching=launching,
        )
        self._render_forza_launch(status.label, status.enabled)

    def _clear_launch_wait(self):
        self._launching_game_key = None
        self._launch_request_busy = False
        self._game_launch_deadline = 0.0

    def _drain_game_worker_results(self):
        try:
            while True:
                self._apply_game_scan(*self._game_scan_results.get_nowait())
        except queue.Empty:
            pass
        try:
            while True:
                self._finish_game_launch(*self._game_launch_results.get_nowait())
        except queue.Empty:
            pass

    def _start_game_scan(self, key: str):
        if (
            key in self._game_scan_busy
            or self.app._tearing_down
            or key != self._selected_game_key
            or self._selected_platform != STEAM_PLATFORM
        ):
            return
        game = get_forza_game(key)
        cached_path = str(getattr(self.settings, game.install_path_field, ""))
        self._game_scan_serial += 1
        serial = self._game_scan_serial
        self._game_scan_busy[key] = serial
        self._game_last_scan[key] = time.monotonic()

        def worker():
            install = None
            try:
                install = discover_forza_install(game, cached_path)
            except Exception:
                log.exception("%s launch discovery failed", game.short_name)
            self._game_scan_results.put((key, serial, install))

        threading.Thread(
            target=worker,
            name=f"fhds-{key}-launch-scan",
            daemon=True,
        ).start()

    def _apply_game_scan(
        self,
        key: str,
        serial: int,
        install: ForzaInstall | None,
    ):
        if self._game_scan_busy.get(key) != serial:
            return
        self._game_scan_busy.pop(key, None)
        if (
            self.app._tearing_down
            or key != self._selected_game_key
            or self._selected_platform != STEAM_PLATFORM
        ):
            return
        self._game_scan_has_result[key] = True
        if install is None:
            self._game_installs.pop(key, None)
            return
        self._game_installs[key] = install
        game = FORZA_GAMES[key]
        resolved = str(install.root)
        self._game_path_hints[key] = resolved
        if getattr(self.settings, game.install_path_field, "") != resolved:
            setattr(self.settings, game.install_path_field, resolved)
            preferences.save(self.settings)

    def _show_forza_game_menu(self):
        if self.app._tearing_down or self._launch_request_busy:
            return
        try:
            self._game_menu.tk_popup(
                self._game_selector_button.winfo_rootx(),
                self._game_selector_button.winfo_rooty()
                + self._game_selector_button.winfo_height(),
            )
        finally:
            self._game_menu.grab_release()

    def _select_forza_game(self, key: str):
        if self.app._tearing_down or self._launch_request_busy:
            self._game_choice_var.set(self._selected_game_key)
            return
        game = get_forza_game(key)
        if key == self._selected_game_key:
            self._game_choice_var.set(key)
            return
        if self._launching_game_key is not None:
            self._clear_launch_wait()
        self._selected_game_key = key
        self._game_choice_var.set(key)
        self.settings.preferred_forza_game = key
        preferences.save(self.settings)
        if key not in self._game_installs:
            self._game_scan_has_result[key] = False
            self._game_last_scan[key] = 0.0
        log.info("Selected %s for the Forza shortcut", game.short_name)
        self._refresh_forza_launch()

    def _select_forza_platform(self, label: str):
        if self._launch_request_busy:
            self._platform_selector.set(
                self._platform_key_to_label[self._selected_platform]
            )
            return
        platform = self._platform_label_to_key.get(label, STEAM_PLATFORM)
        if platform == self._selected_platform:
            return
        self._selected_platform = platform
        self.settings.preferred_forza_platform = platform
        preferences.save(self.settings)
        self.app._xinput_service.sync(getattr(self.app, "_ds", None))
        log.info("Forza platform = %s", platform)
        self._refresh_platform_status()
        self._refresh_forza_launch()

    def _on_bridge_action(self):
        snapshot = self.app._xinput_service.snapshot()
        if snapshot.status is BridgeStatus.DRIVER_MISSING:
            ConfirmationDialog(
                self.app.root,
                heading=t("Install ViGEmBus?"),
                message=t(
                    "FH-DualSense-Enhanced will verify and open the bundled official ViGEmBus 1.22.0 installer. "
                    "Windows will show UAC. The installation does not require internet access."
                ),
                confirm_label=t("Install ViGEmBus"),
                on_confirm=self._start_driver_install,
            )
        elif snapshot.status is BridgeStatus.ERROR:
            self.app._xinput_service.retry()
            self._refresh_platform_status()

    def _start_driver_install(self):
        if self._driver_install_busy or self.app._tearing_down:
            return
        self._driver_install_busy = True
        self._refresh_platform_status()

        def worker():
            result = self.app._xinput_service.install_driver()
            try:
                self.app.root.after(0, lambda: self._finish_driver_install(result))
            except (RuntimeError, tk.TclError):
                pass

        threading.Thread(
            target=worker,
            name="fhds-vigembus-install",
            daemon=True,
        ).start()

    def _finish_driver_install(self, result):
        self._driver_install_busy = False
        self._refresh_platform_status()
        if result.status is InstallStatus.SUCCESS:
            self.app.toast(t("ViGEmBus is ready"))
        elif result.status is InstallStatus.RESTART_REQUIRED:
            self.app.toast(t("Restart Windows to finish ViGEmBus setup"))
        elif result.status is InstallStatus.FAILED:
            self.app.toast(t("ViGEmBus installation failed: {error}").format(
                error=result.error[:96]
            ))

    def _launch_selected_game(self):
        key = self._selected_game_key
        game = FORZA_GAMES[key]
        platform = self._selected_platform
        install = self._game_installs.get(key)
        if (
            (platform == STEAM_PLATFORM and install is None)
            or self._launching_game_key is not None
            or self.app._tearing_down
        ):
            return
        self._launching_game_key = key
        self._launch_request_busy = True
        self._game_launch_deadline = time.monotonic() + FORZA_LAUNCH_TIMEOUT_S
        self._refresh_forza_launch()

        def worker():
            error = ""
            direct = True
            try:
                if platform == XBOX_APP_PLATFORM:
                    result = launch_forza_via_xbox_app(game)
                    direct = result.direct
                else:
                    launch_forza_via_steam(install)
            except Exception as exc:
                error = str(exc) or type(exc).__name__
                log.exception(
                    "Could not launch %s through %s",
                    game.short_name,
                    platform,
                )
            self._game_launch_results.put((key, platform, error, direct))

        threading.Thread(
            target=worker,
            name=f"fhds-{key}-{platform}-launch",
            daemon=True,
        ).start()

    def _finish_game_launch(
        self,
        key: str,
        platform: str,
        error: str,
        direct: bool,
    ):
        if self.app._tearing_down or key != self._launching_game_key:
            return
        self._launch_request_busy = False
        game = FORZA_GAMES[key]
        if error:
            self._clear_launch_wait()
            if platform == STEAM_PLATFORM and "no longer valid" in error.casefold():
                self._game_installs.pop(key, None)
                self._game_scan_has_result[key] = False
                self._game_last_scan[key] = 0.0
            self.app.toast(
                t("Could not launch {game}: {error}").format(
                    game=game.short_name,
                    error=error[:96],
                )
            )
        else:
            if platform == XBOX_APP_PLATFORM and not direct:
                message = t(
                    "Opened {game} in Xbox App; press Play if it is installed"
                )
            elif platform == XBOX_APP_PLATFORM:
                message = t("Sent {game} launch request to Xbox App")
            else:
                message = t("Sent {game} launch request to Steam")
            self.app.toast(message.format(game=game.short_name))

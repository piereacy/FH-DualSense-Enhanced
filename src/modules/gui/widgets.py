"""Reusable widget primitives. Build screens by composing these, not by
re-implementing colors/spacing each time.
"""
import customtkinter as ctk

from . import theme as T


class Tooltip:
    """Small delayed tooltip used by the compact Studio navigation rail."""

    def __init__(self, widget, text: str, delay_ms: int = 450):
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self._after = None
        self._window = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _event=None):
        self._cancel()
        self._after = self.widget.after(self.delay_ms, self._show)

    def _cancel(self):
        if self._after is not None:
            try:
                self.widget.after_cancel(self._after)
            except Exception:
                pass
            self._after = None

    def _show(self):
        self._after = None
        if self._window is not None or not self.widget.winfo_exists():
            return
        top = self._window = ctk.CTkToplevel(self.widget)
        top.overrideredirect(True)
        try:
            top.attributes("-topmost", True)
        except Exception:
            pass
        ctk.CTkLabel(
            top,
            text=self.text,
            fg_color=T.BG_PANEL,
            text_color=T.TEXT,
            corner_radius=6,
            padx=10,
            pady=6,
        ).pack()
        top.update_idletasks()
        x = self.widget.winfo_rootx() + self.widget.winfo_width() + 8
        y = self.widget.winfo_rooty() + max(
            0, (self.widget.winfo_height() - top.winfo_height()) // 2
        )
        top.geometry(f"+{x}+{y}")

    def _hide(self, _event=None):
        self._cancel()
        if self._window is not None:
            try:
                self._window.destroy()
            except Exception:
                pass
            self._window = None


# MARK: typography --------------------------------------------------------

class H1(ctk.CTkLabel):
    """Page title - one per screen."""
    def __init__(self, parent, text: str, **kw):
        super().__init__(parent, text=text, anchor="w",
                         font=ctk.CTkFont(size=T.FS_H1, weight="bold"),
                         text_color=T.TEXT, **kw)


class H2(ctk.CTkLabel):
    """Section header inside a card."""
    def __init__(self, parent, text: str, **kw):
        super().__init__(parent, text=text, anchor="w",
                         font=ctk.CTkFont(size=T.FS_H2, weight="bold"),
                         text_color=T.TEXT, **kw)


class Body(ctk.CTkLabel):
    def __init__(self, parent, text: str, **kw):
        super().__init__(parent, text=text, anchor="w", justify="left",
                         font=ctk.CTkFont(size=T.FS_BODY),
                         text_color=T.TEXT, **kw)


class Hint(ctk.CTkLabel):
    """Muted helper text."""
    def __init__(self, parent, text: str, wrap: int = 0, **kw):
        super().__init__(parent, text=text, anchor="w", justify="left",
                         font=ctk.CTkFont(size=T.FS_SMALL),
                         text_color=T.TEXT_MUTED, **kw)
        if wrap:
            self.configure(wraplength=wrap)


class Warning(ctk.CTkLabel):
    def __init__(self, parent, text: str, wrap: int = 0, **kw):
        super().__init__(parent, text=text, anchor="w", justify="left",
                         font=ctk.CTkFont(size=T.FS_SMALL),
                         text_color=T.YELLOW, **kw)
        if wrap:
            self.configure(wraplength=wrap)


class Danger(ctk.CTkLabel):
    def __init__(self, parent, text: str, wrap: int = 0, **kw):
        super().__init__(parent, text=text, anchor="w", justify="left",
                         font=ctk.CTkFont(size=T.FS_SMALL),
                         text_color=T.RED, **kw)
        if wrap:
            self.configure(wraplength=wrap)


# MARK: surfaces ----------------------------------------------------------

class Card(ctk.CTkFrame):
    """A panel with rounded corners. Use as the primary content container."""
    def __init__(self, parent, **kw):
        kw.setdefault("fg_color", T.BG_PANEL)
        kw.setdefault("corner_radius", 8)
        super().__init__(parent, **kw)


class Section(ctk.CTkFrame):
    """A titled section inside a card (header + body container)."""
    def __init__(self, parent, title: str, **kw):
        super().__init__(parent, fg_color="transparent", **kw)
        H2(self, title).pack(anchor="w", padx=T.PAD_MD, pady=(T.PAD_MD, T.PAD_SM))
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=T.PAD_MD, pady=(0, T.PAD_MD))


# MARK: chips / pills -----------------------------------------------------

class Pill(ctk.CTkFrame):
    """Rounded chip. Optional colored dot + prefix label + main label."""
    def __init__(self, parent, label: str = "", prefix: str = "",
                 dot_color=None, **kw):
        kw.setdefault("fg_color", T.BG_HOVER)
        kw.setdefault("corner_radius", 14)
        kw.setdefault("height", 26)
        super().__init__(parent, **kw)
        self._dot = None
        self._prefix = None
        if dot_color is not None:
            self._dot = ctk.CTkLabel(self, text=T.ICON["dot"], width=8,
                                     text_color=dot_color,
                                     font=ctk.CTkFont(size=10))
            self._dot.pack(side="left", padx=(12, 6), pady=0)
        if prefix:
            self._prefix = ctk.CTkLabel(self, text=f"{prefix.upper()}",
                                        text_color=T.TEXT_FAINT,
                                        font=ctk.CTkFont(size=T.FS_TINY,
                                                         weight="bold"))
            self._prefix.pack(side="left",
                              padx=(12 if dot_color is None else 0, 6),
                              pady=0)
        self._label = ctk.CTkLabel(self, text=label, text_color=T.TEXT,
                                   font=ctk.CTkFont(size=T.FS_SMALL,
                                                    weight="bold"))
        self._label.pack(side="left", padx=(0, 14), pady=0)

    def set_label(self, text: str):
        self._label.configure(text=text)

    def set_dot_color(self, color):
        if self._dot is not None:
            self._dot.configure(text_color=color)


# MARK: buttons -----------------------------------------------------------

class PrimaryButton(ctk.CTkButton):
    def __init__(self, parent, text: str, command=None, **kw):
        kw.setdefault("height", 32)
        kw.setdefault("fg_color", T.ACCENT)
        kw.setdefault("hover_color", T.ACCENT_HOVER)
        kw.setdefault("text_color", "white")
        kw.setdefault("font", ctk.CTkFont(size=T.FS_BODY, weight="bold"))
        super().__init__(parent, text=text, command=command, **kw)


class GhostButton(ctk.CTkButton):
    """Transparent button - blends into toolbars."""
    def __init__(self, parent, text: str, command=None, **kw):
        kw.setdefault("height", 30)
        kw.setdefault("fg_color", "transparent")
        kw.setdefault("hover_color", T.BG_HOVER)
        kw.setdefault("text_color", T.TEXT)
        kw.setdefault("font", ctk.CTkFont(size=T.FS_BODY))
        super().__init__(parent, text=text, command=command, **kw)


class SecondaryButton(ctk.CTkButton):
    """Filled neutral button - for non-primary actions in a row."""
    def __init__(self, parent, text: str, command=None, **kw):
        kw.setdefault("height", 32)
        kw.setdefault("fg_color", T.BG_HOVER)
        kw.setdefault("hover_color", T.BG_ACTIVE)
        kw.setdefault("text_color", T.TEXT)
        kw.setdefault("font", ctk.CTkFont(size=T.FS_BODY))
        super().__init__(parent, text=text, command=command, **kw)


class DangerButton(ctk.CTkButton):
    def __init__(self, parent, text: str, command=None, **kw):
        kw.setdefault("height", 32)
        kw.setdefault("fg_color", T.RED)
        kw.setdefault("hover_color", "#dc2626")
        kw.setdefault("text_color", "white")
        kw.setdefault("font", ctk.CTkFont(size=T.FS_BODY, weight="bold"))
        super().__init__(parent, text=text, command=command, **kw)


# MARK: form layout helpers -----------------------------------------------

class FieldRow(ctk.CTkFrame):
    """A row with a fixed-width label column and a flexible control column.

    Usage:
        row = FieldRow(parent, "Reconnect interval")
        ctk.CTkSlider(row.controls, ...).pack(...)
    """
    LABEL_W = 220  # logical px; CTk scales for DPI

    def __init__(self, parent, label: str, hint: str = "", hint_wrap: int = 0, **kw):
        kw.setdefault("fg_color", "transparent")
        super().__init__(parent, **kw)
        self.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(self, text=label, anchor="w", width=self.LABEL_W,
                     text_color=T.TEXT,
                     font=ctk.CTkFont(size=T.FS_BODY)
                     ).grid(row=0, column=0, padx=(0, T.PAD_MD), sticky="w")
        self.controls = ctk.CTkFrame(self, fg_color="transparent")
        self.controls.grid(row=0, column=1, sticky="ew")
        if hint:
            Hint(self, hint, wrap=hint_wrap).grid(row=1, column=1, sticky="w",
                                                  pady=(T.PAD_XS, 0))


class PageHeader(ctk.CTkFrame):
    """Title + optional subtitle at the top of a tab content area."""
    def __init__(self, parent, title: str, subtitle: str = "", **kw):
        kw.setdefault("fg_color", "transparent")
        super().__init__(parent, **kw)
        H1(self, title).pack(anchor="w")
        if subtitle:
            Hint(self, subtitle).pack(anchor="w", pady=(T.PAD_XS, 0))


# MARK: scrollable card ---------------------------------------------------

WHEEL_MULT = 5  # multiplier on top of CTk's default step (event.delta/6 px on Windows)


class FastScroll(ctk.CTkScrollableFrame):
    """CTkScrollableFrame with faster, synchronously-repainted scrolling.

    Overrides CTkScrollableFrame._mouse_wheel_all (CTk binds <MouseWheel> via
    bind_all() in __init__, so rebinding from outside is shadowed).
    Calls update_idletasks() after each scroll so embedded widgets repaint
    immediately instead of one frame late.

    Uses a visible scrollbar (accent thumb on a panel-tinted track) so users
    can tell at a glance that the area is scrollable.
    """
    def __init__(self, parent, **kw):
        kw.setdefault("fg_color", "transparent")
        kw.setdefault("scrollbar_fg_color", T.BG_PANEL)
        kw.setdefault("scrollbar_button_color", T.BG_ACTIVE)
        kw.setdefault("scrollbar_button_hover_color", T.ACCENT)
        super().__init__(parent, **kw)

    def _mouse_wheel_all(self, event):
        import sys as _sys
        if not self.check_if_master_is_canvas(event.widget):
            return
        cv = self._parent_canvas
        if _sys.platform.startswith("win"):
            step = -int(event.delta / 6) * WHEEL_MULT
        else:
            step = -int(event.delta) * WHEEL_MULT
        if self._shift_pressed:
            if cv.xview() != (0.0, 1.0):
                cv.xview("scroll", step, "units")
        else:
            if cv.yview() != (0.0, 1.0):
                cv.yview("scroll", step, "units")
        cv.update_idletasks()


class ScrollCard(ctk.CTkScrollableFrame):
    """Card-styled scrollable container for long forms."""
    def __init__(self, parent, **kw):
        kw.setdefault("fg_color", T.BG_PANEL)
        kw.setdefault("corner_radius", 8)
        super().__init__(parent, **kw)

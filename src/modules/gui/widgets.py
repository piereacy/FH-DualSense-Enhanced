"""Reusable widget primitives. Build screens by composing these, not by
re-implementing colors/spacing each time.
"""
import tkinter as tk
import weakref

import customtkinter as ctk

from . import theme as T


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

WHEEL_PIXELS = 36


def wheel_direction(event) -> int:
    """Normalize Windows/macOS deltas and Linux wheel buttons to -1 or 1."""
    number = getattr(event, "num", None)
    if number == 4:
        return -1
    if number == 5:
        return 1
    delta = getattr(event, "delta", 0)
    if delta > 0:
        return -1
    if delta < 0:
        return 1
    return 0


def wheel_scroll_amount(event) -> int:
    """Return a bounded pixel-like canvas step with natural touchpad scaling."""
    direction = wheel_direction(event)
    if direction == 0:
        return 0
    if getattr(event, "num", None) in (4, 5):
        return direction * WHEEL_PIXELS
    raw = abs(int(getattr(event, "delta", 0)))
    if raw >= 120:
        notches = max(1, min(3, int(round(raw / 120))))
        magnitude = WHEEL_PIXELS * notches
    else:
        magnitude = max(1, min(WHEEL_PIXELS, int(round(raw / 3))))
    return direction * magnitude


def _view_can_scroll(view: tuple[float, float], direction: int) -> bool:
    first, last = view
    return first > 0.001 if direction < 0 else last < 0.999


def scrollable_ancestor_chain(widget, registered) -> list:
    """Return registered ancestors nearest-first for deterministic nesting."""
    result = []
    current = widget
    while current is not None:
        if current in registered:
            result.append(current)
        current = getattr(current, "master", None)
    return result


def first_scrollable_index(views: list[tuple[float, float]], direction: int):
    for index, view in enumerate(views):
        if view != (0.0, 1.0) and _view_can_scroll(view, direction):
            return index
    return None


class WheelRouter:
    """One root-level wheel binding for all registered scroll containers."""

    def __init__(self, root):
        self.root = root
        self._containers = weakref.WeakSet()
        self._rebind()

    def register(self, container) -> None:
        self._containers.add(container)
        # CTkScrollableFrame installs a private bind_all in its constructor.
        # Rebinding here removes that handler and restores our public root route.
        self._rebind()

    def unregister(self, container) -> None:
        self._containers.discard(container)
        self._rebind()

    def _rebind(self):
        try:
            for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                self.root.unbind_all(sequence)
                self.root.bind_all(sequence, self._on_wheel, add="+")
        except tk.TclError:
            pass

    def _pointer_widget(self, event):
        try:
            x = getattr(event, "x_root", None)
            y = getattr(event, "y_root", None)
            if x is None or y is None:
                x, y = self.root.winfo_pointerx(), self.root.winfo_pointery()
            return self.root.winfo_containing(x, y) or event.widget
        except tk.TclError:
            return getattr(event, "widget", None)

    def _on_wheel(self, event):
        amount = wheel_scroll_amount(event)
        if amount == 0:
            return None
        widget = self._pointer_widget(event)
        candidates = scrollable_ancestor_chain(widget, self._containers)
        views = []
        alive = []
        for candidate in candidates:
            try:
                views.append(candidate._parent_canvas.yview())
                alive.append(candidate)
            except tk.TclError:
                self._containers.discard(candidate)
        index = first_scrollable_index(views, -1 if amount < 0 else 1)
        if index is None:
            return None
        canvas = alive[index]._parent_canvas
        canvas.yview_scroll(amount, "units")
        canvas.update_idletasks()
        return "break"


def install_wheel_router(root) -> WheelRouter:
    router = getattr(root, "_fhds_wheel_router", None)
    if router is None:
        router = WheelRouter(root)
        root._fhds_wheel_router = router
    return router


class FastScroll(ctk.CTkScrollableFrame):
    """Scrollable frame registered with the root-level WheelRouter."""
    def __init__(self, parent, **kw):
        kw.setdefault("fg_color", "transparent")
        kw.setdefault("scrollbar_fg_color", T.BG_PANEL)
        kw.setdefault("scrollbar_button_color", T.BG_ACTIVE)
        kw.setdefault("scrollbar_button_hover_color", T.ACCENT)
        super().__init__(parent, **kw)
        self._wheel_router = install_wheel_router(self.winfo_toplevel())
        self._wheel_router.register(self)

    def destroy(self):
        router = getattr(self, "_wheel_router", None)
        if router is not None:
            router.unregister(self)
        super().destroy()


class ScrollCard(FastScroll):
    """Card-styled scrollable container for long forms."""
    def __init__(self, parent, **kw):
        kw.setdefault("fg_color", T.BG_PANEL)
        kw.setdefault("corner_radius", 8)
        super().__init__(parent, **kw)

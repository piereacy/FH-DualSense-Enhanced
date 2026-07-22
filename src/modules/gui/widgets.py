"""Reusable widget primitives. Build screens by composing these, not by
re-implementing colors/spacing each time.
"""
import tkinter as tk
import weakref
from typing import Any

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
    """Pixel-aligned header status frame with optional segmented detail."""

    HEIGHT = 28
    CORNER_RADIUS = 8
    DOT_SIZE = 8
    GAP = 4

    def __init__(self, parent, label: str = "", prefix: str = "",
                 dot_color=None, **kw):
        kw.setdefault("fg_color", T.BG_HOVER)
        kw.setdefault("corner_radius", self.CORNER_RADIUS)
        kw.setdefault("height", self.HEIGHT)
        super().__init__(parent, **kw)
        self._dot = None
        self._prefix = None
        self._label_value = label
        self._dot_color_value = dot_color
        self._detail_value = ""
        self._detail_color_value = T.TEXT_MUTED
        if dot_color is not None:
            self._dot = ctk.CTkLabel(self, text=T.ICON["dot"],
                                     width=self.DOT_SIZE, height=self.HEIGHT,
                                     text_color=dot_color,
                                     font=ctk.CTkFont(size=self.DOT_SIZE))
            self._dot.pack(side="left", padx=(12, self.GAP), pady=0)
        if prefix:
            self._prefix = ctk.CTkLabel(self, text=f"{prefix.upper()}",
                                        height=self.HEIGHT,
                                        text_color=T.TEXT_FAINT,
                                        font=ctk.CTkFont(size=T.FS_TINY,
                                                         weight="bold"))
            self._prefix.pack(side="left",
                              padx=(12 if dot_color is None else 0, self.GAP),
                              pady=0)
        self._label = ctk.CTkLabel(self, text=label, height=self.HEIGHT,
                                   text_color=T.TEXT,
                                   font=ctk.CTkFont(size=T.FS_SMALL,
                                                    weight="bold"))
        self._label.pack(side="left", padx=(0, self.GAP), pady=0)
        self._detail = ctk.CTkLabel(
            self,
            text="",
            height=self.HEIGHT,
            text_color=T.TEXT_MUTED,
            font=ctk.CTkFont(size=T.FS_SMALL, weight="bold"),
        )
        self._detail.pack(side="left", padx=(0, 12), pady=0)

    def set_label(self, text: str):
        if text == self._label_value:
            return
        self._label_value = text
        self._label.configure(text=text)

    def set_dot_color(self, color):
        if self._dot is None or color == self._dot_color_value:
            return
        self._dot_color_value = color
        self._dot.configure(text_color=color)

    def set_detail(self, text: str, color=None):
        resolved_color = T.TEXT_MUTED if color is None else color
        changes: dict[str, Any] = {}
        if text != self._detail_value:
            self._detail_value = text
            changes["text"] = text
        if resolved_color != self._detail_color_value:
            self._detail_color_value = resolved_color
            changes["text_color"] = resolved_color
        if not changes:
            return
        self._detail.configure(
            **changes,
        )


# MARK: buttons -----------------------------------------------------------

class PrimaryButton(ctk.CTkButton):
    def __init__(self, parent, text: str, command=None, **kw):
        kw.setdefault("height", 32)
        kw.setdefault("fg_color", T.ACCENT)
        kw.setdefault("hover_color", T.ACCENT_HOVER)
        kw.setdefault("text_color", "white")
        kw.setdefault("font", ctk.CTkFont(size=T.FS_BODY, weight="bold"))
        super().__init__(parent, text=text, command=command, **kw)


class NavButton(ctk.CTkButton):
    """Sidebar button with an optional canvas-drawn update notice dot."""

    NOTICE_TAG = "fhds_update_notice"

    def __init__(self, parent, **kw):
        self._notice_visible = False
        super().__init__(parent, **kw)

    def set_notice_visible(self, visible: bool) -> None:
        visible = bool(visible)
        if visible == self._notice_visible:
            return
        self._notice_visible = visible
        self._draw()

    def _draw(self, no_color_updates=False):
        super()._draw(no_color_updates)
        self._canvas.delete(self.NOTICE_TAG)
        if not self._notice_visible:
            return
        diameter = self._apply_widget_scaling(5)
        radius = diameter / 2
        center_x = self._apply_widget_scaling(self._current_width - 14)
        center_y = self._apply_widget_scaling(self._current_height / 2)
        self._canvas.create_oval(
            center_x - radius,
            center_y - radius,
            center_x + radius,
            center_y + radius,
            fill="white",
            outline="",
            tags=self.NOTICE_TAG,
        )
        self._canvas.tag_raise(self.NOTICE_TAG)


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
    """Scrollable frame with wheel routing and coalesced width reflow."""

    RESIZE_DEBOUNCE_MS = 40

    def __init__(self, parent, **kw):
        self._layout_active = True
        self._fit_after = None
        self._pending_fit_dimension = None
        self._applied_fit_dimension = None
        kw.setdefault("fg_color", "transparent")
        kw.setdefault("scrollbar_fg_color", T.BG_PANEL)
        kw.setdefault("scrollbar_button_color", T.BG_ACTIVE)
        kw.setdefault("scrollbar_button_hover_color", T.ACCENT)
        super().__init__(parent, **kw)
        self._wheel_router = install_wheel_router(self.winfo_toplevel())
        self._wheel_router.register(self)

    def _fit_frame_dimensions_to_canvas(self, event):
        dimension = event.height if self._orientation == "horizontal" else event.width
        self._pending_fit_dimension = max(1, int(dimension))
        if not self._layout_active:
            return
        self._schedule_canvas_fit(self.RESIZE_DEBOUNCE_MS)

    def _schedule_canvas_fit(self, delay_ms: int) -> None:
        if self._fit_after is not None:
            try:
                self.after_cancel(self._fit_after)
            except tk.TclError:
                pass
        try:
            self._fit_after = self.after(delay_ms, self._apply_canvas_fit)
        except tk.TclError:
            self._fit_after = None

    def _apply_canvas_fit(self) -> None:
        self._fit_after = None
        if not self._layout_active:
            return
        dimension = self._pending_fit_dimension
        if dimension is None:
            try:
                dimension = (
                    self._parent_canvas.winfo_height()
                    if self._orientation == "horizontal"
                    else self._parent_canvas.winfo_width()
                )
            except tk.TclError:
                return
        if dimension <= 1 or dimension == self._applied_fit_dimension:
            return
        try:
            if self._orientation == "horizontal":
                self._parent_canvas.itemconfigure(
                    self._create_window_id,
                    height=dimension,
                )
            else:
                self._parent_canvas.itemconfigure(
                    self._create_window_id,
                    width=dimension,
                )
        except tk.TclError:
            return
        self._applied_fit_dimension = dimension

    def set_layout_active(self, active: bool) -> None:
        active = bool(active)
        if active == self._layout_active:
            return
        self._layout_active = active
        if not active:
            if self._fit_after is not None:
                try:
                    self.after_cancel(self._fit_after)
                except tk.TclError:
                    pass
                self._fit_after = None
            return
        try:
            self._pending_fit_dimension = (
                self._parent_canvas.winfo_height()
                if self._orientation == "horizontal"
                else self._parent_canvas.winfo_width()
            )
        except tk.TclError:
            return
        self._schedule_canvas_fit(0)

    def destroy(self):
        if self._fit_after is not None:
            try:
                self.after_cancel(self._fit_after)
            except tk.TclError:
                pass
            self._fit_after = None
        router = getattr(self, "_wheel_router", None)
        if router is not None:
            router.unregister(self)
        super().destroy()


def set_scroll_layout_active(root, active: bool) -> None:
    """Enable expensive canvas-width reflow only for the visible page."""
    stack = [root]
    while stack:
        widget = stack.pop()
        if isinstance(widget, FastScroll):
            widget.set_layout_active(active)
        children = getattr(widget, "winfo_children", None)
        if not callable(children):
            continue
        try:
            stack.extend(children())
        except tk.TclError:
            continue


class ScrollCard(FastScroll):
    """Card-styled scrollable container for long forms."""
    def __init__(self, parent, **kw):
        kw.setdefault("fg_color", T.BG_PANEL)
        kw.setdefault("corner_radius", 8)
        super().__init__(parent, **kw)

from types import SimpleNamespace

from modules.gui import theme as T
from modules.gui.widgets import FastScroll, Pill


class _ConfiguredWidget:
    def __init__(self):
        self.calls = []

    def configure(self, **kwargs):
        self.calls.append(kwargs)


class _Canvas:
    def __init__(self, width=900, height=600):
        self.width = width
        self.height = height
        self.itemconfigure_calls = []

    def winfo_width(self):
        return self.width

    def winfo_height(self):
        return self.height

    def itemconfigure(self, item, **kwargs):
        self.itemconfigure_calls.append((item, kwargs))


def _pill_shell():
    pill = Pill.__new__(Pill)
    pill._label = _ConfiguredWidget()
    pill._dot = _ConfiguredWidget()
    pill._detail = _ConfiguredWidget()
    pill._label_value = "USB"
    pill._dot_color_value = T.GREEN
    pill._detail_value = "Charging 40%"
    pill._detail_color_value = T.TEXT_MUTED
    return pill


def _scroll_shell(*, active=True):
    scroll = FastScroll.__new__(FastScroll)
    scroll._orientation = "vertical"
    scroll._layout_active = active
    scroll._fit_after = None
    scroll._pending_fit_dimension = None
    scroll._applied_fit_dimension = None
    scroll._parent_canvas = _Canvas()
    scroll._create_window_id = 7
    scheduled = []
    cancelled = []

    def after(delay, callback):
        token = f"after-{len(scheduled)}"
        scheduled.append((token, delay, callback))
        return token

    scroll.after = after
    scroll.after_cancel = cancelled.append
    return scroll, scheduled, cancelled


def test_header_status_frame_geometry_is_pixel_aligned_for_common_scales():
    assert Pill.HEIGHT == 28
    assert Pill.CORNER_RADIUS == 8
    assert Pill.DOT_SIZE == 8
    assert Pill.GAP == 4
    for scale in (1.0, 1.25, 1.5, 1.75, 2.0):
        assert Pill.HEIGHT * scale == int(Pill.HEIGHT * scale)
        assert Pill.CORNER_RADIUS * scale == int(Pill.CORNER_RADIUS * scale)


def test_header_status_frame_skips_unchanged_render_values():
    pill = _pill_shell()

    pill.set_label("USB")
    pill.set_dot_color(T.GREEN)
    pill.set_detail("Charging 40%")

    assert pill._label.calls == []
    assert pill._dot.calls == []
    assert pill._detail.calls == []

    pill.set_label("BT")
    pill.set_dot_color(T.YELLOW)
    pill.set_detail("10%", T.RED)

    assert pill._label.calls == [{"text": "BT"}]
    assert pill._dot.calls == [{"text_color": T.YELLOW}]
    assert pill._detail.calls == [{"text": "10%", "text_color": T.RED}]


def test_hidden_scroll_page_records_resize_without_reflowing_content():
    scroll, scheduled, _cancelled = _scroll_shell(active=False)

    scroll._fit_frame_dimensions_to_canvas(SimpleNamespace(width=1200, height=700))

    assert scroll._pending_fit_dimension == 1200
    assert scheduled == []
    assert scroll._parent_canvas.itemconfigure_calls == []


def test_visible_scroll_page_coalesces_resize_and_applies_latest_width():
    scroll, scheduled, cancelled = _scroll_shell(active=True)

    scroll._fit_frame_dimensions_to_canvas(SimpleNamespace(width=1000, height=700))
    scroll._fit_frame_dimensions_to_canvas(SimpleNamespace(width=1200, height=700))

    assert len(scheduled) == 2
    assert scheduled[-1][1] == FastScroll.RESIZE_DEBOUNCE_MS
    assert cancelled == [scheduled[0][0]]
    scheduled[-1][2]()
    assert scroll._parent_canvas.itemconfigure_calls == [(7, {"width": 1200})]

    scroll._fit_frame_dimensions_to_canvas(SimpleNamespace(width=1200, height=700))
    scheduled[-1][2]()
    assert scroll._parent_canvas.itemconfigure_calls == [(7, {"width": 1200})]

from modules.gui.widgets import (
    first_scrollable_index,
    scrollable_ancestor_chain,
    wheel_direction,
    wheel_scroll_amount,
)


class Event:
    def __init__(self, *, delta=0, num=None):
        self.delta = delta
        self.num = num


def test_windows_and_linux_wheel_events_have_bounded_steps():
    assert wheel_direction(Event(delta=120)) == -1
    assert wheel_scroll_amount(Event(delta=120)) == -36
    assert wheel_scroll_amount(Event(delta=-120)) == 36
    assert wheel_scroll_amount(Event(delta=-1200)) == 108
    assert wheel_scroll_amount(Event(delta=9)) == -3
    assert wheel_scroll_amount(Event(num=4)) == -36
    assert wheel_scroll_amount(Event(num=5)) == 36


def test_registered_ancestors_are_nearest_first():
    outer = type("Node", (), {"master": None})()
    inner = type("Node", (), {"master": outer})()
    child = type("Node", (), {"master": inner})()

    assert scrollable_ancestor_chain(child, {outer, inner}) == [inner, outer]


def test_boundary_hands_wheel_from_inner_to_outer():
    views = [(0.0, 0.5), (0.2, 0.8)]
    assert first_scrollable_index(views, -1) == 1
    assert first_scrollable_index(views, 1) == 0
    assert first_scrollable_index([(0.0, 1.0), (0.0, 1.0)], 1) is None

from types import SimpleNamespace

from modules.config.settings import Settings
from modules.gui.main import TriggerGUI


class _Root:
    def state(self):
        return "iconic"


def _app(minimize_to_tray):
    app = object.__new__(TriggerGUI)
    app.settings = Settings()
    app.settings.minimize_to_tray = minimize_to_tray
    app.root = _Root()
    app.hide_calls = 0
    app._hide_to_tray = lambda: setattr(app, "hide_calls", app.hide_calls + 1)
    return app


def test_minimize_hides_to_tray_when_enabled():
    app = _app(True)

    app._on_unmap(SimpleNamespace(widget=app.root))

    assert app.hide_calls == 1


def test_minimize_stays_on_taskbar_when_disabled():
    app = _app(False)

    app._on_unmap(SimpleNamespace(widget=app.root))

    assert app.hide_calls == 0

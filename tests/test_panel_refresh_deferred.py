# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Side panels never refresh under the user's hands (release_check 09-10).

After every edit the viewport says the model changed. The Components «In
model» list (its thumbnails' signatures) and the Browser (every row's
state) answered at once — +20 ms per edit on the Plaza, even with the
section folded or the tab hidden. Now: hidden, they wait until shown;
on screen, one refresh 300 ms after the last edit of a burst.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

_app = QApplication.instance() or QApplication([])


@pytest.fixture
def win():
    from views.main_window import MainWindow
    w = MainWindow()
    w.show()
    _app.processEvents()
    yield w
    w._saved_version = w.viewport.scene.version
    w.close()


def _count_calls(monkeypatch, obj, name):
    calls = []
    original = getattr(obj, name)
    monkeypatch.setattr(obj, name, lambda *a, **k: (calls.append(1),
                                                   original(*a, **k)))
    return calls


def test_a_hidden_components_list_waits_until_it_is_shown(win, monkeypatch):
    panel = win.tray.components
    panel.hide()
    calls = _count_calls(monkeypatch, panel, "refresh_in_model")
    for _ in range(3):
        panel.on_scene_changed()                 # three edits, panel hidden
    assert calls == []
    panel.show()
    _app.processEvents()
    assert len(calls) == 1                       # caught up on showing


def test_a_burst_of_edits_refreshes_the_visible_panels_once(win, monkeypatch):
    panel = win.tray.components
    outliner = win.project_browser.outliner
    if not (panel.isVisible() and outliner.isVisible()):
        pytest.skip("the factory layout hides one of the panels here")
    comp_calls = _count_calls(monkeypatch, panel, "refresh_in_model")
    tree_calls = _count_calls(monkeypatch, outliner, "refresh")
    for _ in range(5):
        panel.on_scene_changed()
        outliner.on_scene_changed()
    assert comp_calls == [] and tree_calls == []     # nothing inline
    panel._in_model_timer.timeout.emit()
    outliner._refresh_timer.timeout.emit()
    assert len(comp_calls) == 1 and len(tree_calls) == 1

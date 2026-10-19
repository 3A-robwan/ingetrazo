# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""The edge-reference dwell is persistent, bounded and applied only on OK."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtCore import QLocale, QSettings
from PySide6.QtWidgets import QFormLayout, QWidget

from core import general_settings as gs
from core import i18n
import views.preferences_dialog as prefs_mod


@pytest.fixture
def settings(tmp_path, monkeypatch):
    path = tmp_path / "parallel.ini"
    factory = lambda: QSettings(str(path), QSettings.IniFormat)
    monkeypatch.setattr(prefs_mod, "QSettings", factory)
    monkeypatch.setattr(gs, "QSettings", factory)
    return factory()


class _Window(QWidget):
    def __init__(self):
        super().__init__()
        self.delays = []
        self.viewport = SimpleNamespace(
            edit_rest_mode="fade", parallel_edge_dwell_ms=500,
            inference=SimpleNamespace(set_parallel_edge_dwell_ms=self.delays.append))
        self._rest_actions = {}


@pytest.mark.parametrize("raw, expected", [
    (None, 500), ("wrong", 500), ("nan", 500), ("inf", 500),
    (float("-inf"), 500), (0, 100), (-700, 100),
    (1000000, 10000), ("1200", 1200), (750.4, 750),
])
def test_dwell_reader_defaults_validates_and_clamps(settings, raw, expected):
    if raw is not None:
        gs.set_value("parallel_edge_dwell_ms", raw, settings)
    assert gs.parallel_edge_dwell_ms(settings) == expected


def test_old_general_namespace_is_still_supported(settings):
    settings.setValue("general/parallel_edge_dwell_ms", 800)
    assert gs.parallel_edge_dwell_ms(settings) == 800
    gs.set_value("parallel_edge_dwell_ms", 1200, settings)
    assert gs.parallel_edge_dwell_ms(settings) == 1200


def test_default_is_half_second_and_ok_saves_and_applies(settings):
    win = _Window()
    dialog = prefs_mod.PreferencesDialog(win)
    spin = dialog._parallel_edge_dwell
    assert spin.value() == 0.5
    assert spin.minimum() == 0.1
    assert spin.maximum() == 10.0
    spin.setValue(1.2)
    dialog.accept()
    assert int(settings.value("General/parallel_edge_dwell_ms")) == 1200
    assert win.viewport.parallel_edge_dwell_ms == 1200
    assert win.delays == [1200]
    reopened = prefs_mod.PreferencesDialog(win)
    assert reopened._parallel_edge_dwell.value() == 1.2


def test_cancel_keeps_saved_and_pending_inference_unchanged(settings):
    gs.set_value("parallel_edge_dwell_ms", 900, settings)
    win = _Window()
    win.viewport.parallel_edge_dwell_ms = 900
    dialog = prefs_mod.PreferencesDialog(win)
    assert dialog._parallel_edge_dwell.value() == 0.9
    dialog._parallel_edge_dwell.setValue(3.0)
    dialog.reject()
    assert gs.parallel_edge_dwell_ms(settings) == 900
    assert win.viewport.parallel_edge_dwell_ms == 900
    assert not win.delays


def test_seconds_accept_polish_decimal_comma_and_use_polish_description(settings):
    before = i18n.current_language()
    i18n.set_language("pl")
    try:
        win = _Window()
        dialog = prefs_mod.PreferencesDialog(win)
        spin = dialog._parallel_edge_dwell
        spin.setLocale(QLocale("pl_PL"))
        spin.lineEdit().setText("0,8 s")
        spin.interpretText()
        assert spin.value() == 0.8
        assert "Wierzchołki" in spin.toolTip()
        form = spin.parent().layout()
        assert isinstance(form, QFormLayout)
        assert form.labelForField(spin).text() == "Czas wskazania krawędzi dla równoległości:"
        dialog.accept()
        assert gs.parallel_edge_dwell_ms(settings) == 800
    finally:
        i18n.set_language(before)


def test_viewport_loads_saved_delay_before_inference_engine(settings):
    from views.viewport import Viewport

    gs.set_value("parallel_edge_dwell_ms", 1600, settings)
    viewport = Viewport()
    try:
        assert viewport.parallel_edge_dwell_ms == 1600
    finally:
        viewport.close()

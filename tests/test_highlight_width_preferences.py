# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 IngeTrazo contributors.
"""Independent hover/selection widths are bounded, persistent and applied on OK."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtCore import QPoint, QRect, QSettings
from PySide6.QtWidgets import (QApplication, QDialogButtonBox, QFormLayout,
                               QScrollArea, QWidget)

from core import general_settings as gs
from core import i18n
import views.preferences_dialog as prefs_mod


NAMES = ("hover_edge_width", "selected_edge_width")


@pytest.fixture
def settings(tmp_path, monkeypatch):
    path = tmp_path / "highlight.ini"
    factory = lambda: QSettings(str(path), QSettings.IniFormat)
    monkeypatch.setattr(prefs_mod, "QSettings", factory)
    monkeypatch.setattr(gs, "QSettings", factory)
    return factory()


class _Window(QWidget):
    def __init__(self):
        super().__init__()
        self.updates = []
        self.viewport = SimpleNamespace(
            edit_rest_mode="fade", hover_edge_width=2, selected_edge_width=2,
            _msaa=4, update=lambda: self.updates.append(True))
        self._rest_actions = {}


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("raw, expected", [
    (None, 2), ("bad", 2), ("nan", 2), ("inf", 2), (False, 2),
    (-100, 1), (100, 3), ("1", 1), (3.0, 3), (2.4, 2),
])
def test_width_reader_defaults_validates_and_clamps(settings, name, raw, expected):
    if raw is not None:
        gs.set_value(name, raw, settings)
    assert gs.edge_highlight_width(name, settings) == expected


def test_missing_widths_default_to_two_and_ui_has_one_to_three_range(settings):
    win = _Window()
    dialog = prefs_mod.PreferencesDialog(win)
    for name in NAMES:
        control = getattr(dialog, "_" + name)
        assert control.value() == 2
        assert control.minimum() == 1
        assert control.maximum() == 3
        assert control.suffix() == " px"


def test_ok_saves_both_independently_reopens_and_updates_live_viewport(settings):
    win = _Window()
    dialog = prefs_mod.PreferencesDialog(win)
    dialog._hover_edge_width.setValue(1)
    dialog._selected_edge_width.setValue(3)
    assert win.viewport.hover_edge_width == 2
    assert win.viewport.selected_edge_width == 2
    dialog.accept()
    fresh = QSettings(settings.fileName(), QSettings.IniFormat)
    assert int(fresh.value("General/hover_edge_width")) == 1
    assert int(fresh.value("General/selected_edge_width")) == 3
    assert win.viewport.hover_edge_width == 1
    assert win.viewport.selected_edge_width == 3
    assert win.updates
    reopened = prefs_mod.PreferencesDialog(win)
    assert reopened._hover_edge_width.value() == 1
    assert reopened._selected_edge_width.value() == 3
    reopened._hover_edge_width.setValue(2)
    reopened.accept()
    assert gs.edge_highlight_width("hover_edge_width", fresh) == 2
    assert gs.edge_highlight_width("selected_edge_width", fresh) == 3


def test_cancel_keeps_saved_and_live_widths_unchanged(settings):
    gs.set_value("hover_edge_width", 1, settings)
    gs.set_value("selected_edge_width", 3, settings)
    win = _Window()
    win.viewport.hover_edge_width = 1
    win.viewport.selected_edge_width = 3
    dialog = prefs_mod.PreferencesDialog(win)
    dialog._hover_edge_width.setValue(3)
    dialog._selected_edge_width.setValue(1)
    dialog.reject()
    assert gs.edge_highlight_width("hover_edge_width", settings) == 1
    assert gs.edge_highlight_width("selected_edge_width", settings) == 3
    assert win.viewport.hover_edge_width == 1
    assert win.viewport.selected_edge_width == 3
    assert not win.updates


def test_legacy_namespace_is_read_but_canonical_values_take_precedence(settings):
    settings.setValue("general/hover_edge_width", 1)
    settings.setValue("general/selected_edge_width", 3)
    assert gs.edge_highlight_width("hover_edge_width", settings) == 1
    assert gs.edge_highlight_width("selected_edge_width", settings) == 3
    gs.set_value("hover_edge_width", 3, settings)
    assert gs.edge_highlight_width("hover_edge_width", settings) == 3
    assert gs.edge_highlight_width("selected_edge_width", settings) == 3


@pytest.mark.parametrize("language, labels", [
    ("pl", ("Grubość niebieskiej krawędzi pod kursorem:",
             "Grubość zaznaczonych krawędzi (pomarańczowych):")),
    ("es", ("Grosor de arista bajo el cursor (azul):",
             "Grosor de aristas seleccionadas (naranja):")),
])
def test_translated_labels_distinguish_hover_from_selection(settings, language, labels):
    before = i18n.current_language()
    i18n.set_language(language)
    try:
        win = _Window()
        dialog = prefs_mod.PreferencesDialog(win)
        for name, expected in zip(NAMES, labels):
            control = getattr(dialog, "_" + name)
            form = control.parent().layout()
            assert isinstance(form, QFormLayout)
            assert form.labelForField(control).text() == expected
    finally:
        i18n.set_language(before)


def test_polish_general_page_scrolls_at_six_hundred_pixels_with_controls_and_ok_reachable(settings):
    before = i18n.current_language()
    i18n.set_language("pl")
    win = _Window()
    dialog = prefs_mod.PreferencesDialog(win)
    try:
        dialog.resize(520, 600)
        dialog.show()
        QApplication.processEvents()
        assert dialog.height() <= 600
        scroll = dialog._tabs.widget(0)
        assert isinstance(scroll, QScrollArea)
        assert scroll.verticalScrollBar().maximum() > 0
        for name in NAMES:
            control = getattr(dialog, "_" + name)
            scroll.ensureWidgetVisible(control, 0, 4)
            QApplication.processEvents()
            visible_rect = QRect(control.mapTo(scroll.viewport(), QPoint()), control.size())
            assert scroll.viewport().rect().contains(visible_rect)
            assert control.isVisibleTo(dialog)
        buttons = dialog.findChild(QDialogButtonBox)
        ok = buttons.button(QDialogButtonBox.Ok)
        ok_rect = QRect(ok.mapTo(dialog, QPoint()), ok.size())
        assert dialog.rect().contains(ok_rect)
        assert ok.isVisibleTo(dialog) and ok.isEnabled()
    finally:
        dialog.close()
        i18n.set_language(before)


def test_viewport_loads_the_independent_saved_widths_on_startup(settings):
    from views.viewport import Viewport

    gs.set_value("hover_edge_width", 3, settings)
    gs.set_value("selected_edge_width", 1, settings)
    viewport = Viewport()
    try:
        assert viewport.hover_edge_width == 3
        assert viewport.selected_edge_width == 1
    finally:
        viewport.close()

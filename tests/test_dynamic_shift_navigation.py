# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Shift changes Orbit/Pan within one gesture, without moving the camera on a key tap."""
from __future__ import annotations

import copy

import pytest
from PySide6.QtCore import QEvent, QPointF, QSettings, Qt
from PySide6.QtGui import QCursor, QKeyEvent, QMouseEvent, QVector3D as V, QVector4D

from core import general_settings
from views.viewport import Viewport


@pytest.fixture
def vp(monkeypatch):
    viewport = Viewport()
    viewport.resize(800, 600)
    viewport.camera.set_aspect(800, 600)
    viewport._dynamic_shift_nav = True
    # An off-centre model point at a different depth from the camera target.
    pivot = viewport.camera.eye() + viewport.camera.forward() * 7.0 + V(1, 0, 1)
    monkeypatch.setattr(viewport, "_orbit_pivot_at", lambda x, y: V(pivot))
    shapes = {"orbit": Qt.OpenHandCursor, "pan": Qt.ClosedHandCursor,
              "zoom": Qt.SizeVerCursor, "zoom_window": Qt.CrossCursor}
    monkeypatch.setattr("views.icons.tool_cursor",
                        lambda name, *args: QCursor(shapes.get(name, Qt.ArrowCursor)))
    yield viewport
    viewport.close()


def _mouse(vp, kind, x, y, button, buttons, shift=False):
    event = QMouseEvent(kind, QPointF(x, y), QPointF(x, y), button, buttons,
                        Qt.ShiftModifier if shift else Qt.NoModifier)
    {QEvent.MouseButtonPress: vp.mousePressEvent,
     QEvent.MouseMove: vp.mouseMoveEvent,
     QEvent.MouseButtonRelease: vp.mouseReleaseEvent}[kind](event)


def _press(vp, button=Qt.MiddleButton, shift=False):
    _mouse(vp, QEvent.MouseButtonPress, 100, 100, button, button, shift)


def _move(vp, x, y, button=Qt.MiddleButton, shift=False):
    _mouse(vp, QEvent.MouseMove, x, y, Qt.NoButton, button, shift)


def _shift(vp, down):
    event = QKeyEvent(QEvent.KeyPress if down else QEvent.KeyRelease,
                      Qt.Key_Shift, Qt.ShiftModifier if down else Qt.NoModifier)
    (vp.keyPressEvent if down else vp.keyReleaseEvent)(event)


def _pose(cam):
    return (cam.yaw, cam.pitch, cam.distance,
            cam.target.x(), cam.target.y(), cam.target.z())


def _screen(vp, point):
    clip = (vp.camera.projection_matrix() * vp.camera.view_matrix()).map(
        QVector4D(point.x(), point.y(), point.z(), 1))
    return ((clip.x() / clip.w() + 1) * vp.width() / 2,
            (1 - clip.y() / clip.w()) * vp.height() / 2)


def test_middle_drag_follows_shift_even_without_key_events(vp):
    _press(vp)
    _move(vp, 120, 110)
    pivot = V(vp._orbit_pivot)
    before = _pose(vp.camera)
    screen_before = _screen(vp, pivot)
    _move(vp, 150, 130, shift=True)
    assert (vp.camera.yaw, vp.camera.pitch) == before[:2], "Shift must pan, not orbit"
    screen_after = _screen(vp, pivot)
    assert screen_after[0] - screen_before[0] == pytest.approx(30, abs=0.05)
    assert screen_after[1] - screen_before[1] == pytest.approx(20, abs=0.05)
    assert vp._orbit_pivot == pivot, "switching must retain the grabbed world point"
    before = _pose(vp.camera)
    _move(vp, 170, 140)
    assert vp.camera.yaw != before[0], "releasing Shift must resume orbit"
    assert vp._orbit_pivot == pivot


def test_shift_keys_switch_cursor_immediately_without_camera_jump(vp):
    _press(vp)
    _move(vp, 120, 110)
    before, last = _pose(vp.camera), vp._last_pos
    _shift(vp, True)
    assert vp.cursor().shape() == Qt.ClosedHandCursor
    assert _pose(vp.camera) == before and vp._last_pos == last
    reference = copy.copy(vp.camera)
    reference.pan(5, 3, vp.height(), depth=vp._depth_of(vp._orbit_pivot))
    _move(vp, 125, 113, shift=True)
    assert _pose(vp.camera) == pytest.approx(_pose(reference), abs=1e-6)
    before = _pose(vp.camera)
    _shift(vp, False)
    assert vp.cursor().shape() == Qt.OpenHandCursor
    assert _pose(vp.camera) == before


@pytest.mark.parametrize("initial_shift", [False, True])
def test_explicit_orbit_supports_shift_and_depth_from_either_start(vp, initial_shift):
    vp.set_nav_mode("orbit")
    _press(vp, Qt.LeftButton, initial_shift)
    pivot = V(vp._orbit_pivot)
    _move(vp, 120, 110, Qt.LeftButton, shift=True)
    assert vp.cursor().shape() == Qt.ClosedHandCursor
    assert vp._pan_depth == pytest.approx(vp._depth_of(pivot))
    before = _pose(vp.camera)
    _move(vp, 140, 120, Qt.LeftButton, shift=False)
    assert vp.camera.yaw != before[0]
    _mouse(vp, QEvent.MouseButtonRelease, 140, 120,
           Qt.LeftButton, Qt.NoButton)
    assert vp._orbit_pivot is None
    assert vp.cursor().shape() == Qt.OpenHandCursor


@pytest.mark.parametrize("mode", ["pan", "zoom", "zoom_window"])
def test_middle_drag_is_independent_of_selected_navigation_tool(vp, mode):
    vp.set_nav_mode(mode)
    _press(vp)
    distance = vp.camera.distance
    _move(vp, 120, 110)
    assert vp.camera.distance == distance, "MMB must orbit even with Zoom selected"
    assert not vp._pan_mode
    before = _pose(vp.camera)
    _move(vp, 140, 120, shift=True)
    assert vp._pan_mode
    assert (vp.camera.yaw, vp.camera.pitch) == before[:2]


def test_explicit_pan_does_not_turn_into_orbit(vp):
    vp.set_nav_mode("pan")
    _press(vp, Qt.LeftButton)
    before = _pose(vp.camera)
    _shift(vp, True)
    _move(vp, 120, 110, Qt.LeftButton, True)
    _shift(vp, False)
    _move(vp, 140, 120, Qt.LeftButton)
    assert (vp.camera.yaw, vp.camera.pitch) == before[:2]
    assert vp._pan_mode


@pytest.mark.parametrize("mode", ["zoom", "zoom_window"])
def test_shift_does_not_change_explicit_zoom_tools(vp, mode):
    vp.set_nav_mode(mode)
    _press(vp, Qt.LeftButton)
    before = _pose(vp.camera)
    _shift(vp, True)
    _move(vp, 120, 110, Qt.LeftButton, True)
    assert (vp.camera.yaw, vp.camera.pitch) == before[:2]
    assert vp.cursor().shape() == (Qt.SizeVerCursor if mode == "zoom" else Qt.CrossCursor)
    if mode == "zoom":
        assert vp.camera.distance != before[2]
    else:
        assert _pose(vp.camera) == before
        assert vp._zoom_box_active


@pytest.mark.parametrize("initial_shift", [False, True])
def test_disabled_preference_latches_the_press_mode(vp, initial_shift):
    vp._dynamic_shift_nav = False
    _press(vp, shift=initial_shift)
    before = _pose(vp.camera)
    _shift(vp, not initial_shift)
    _move(vp, 120, 110, shift=not initial_shift)
    assert vp._pan_mode is initial_shift
    assert (vp.camera.yaw == before[0]) is initial_shift


def test_shift_still_reaches_modeling_locks_outside_camera_drag(vp, monkeypatch):
    calls = []
    monkeypatch.setattr(vp, "_capture_shift_lock", lambda: calls.append("capture"))
    monkeypatch.setattr(vp, "_refresh_snap", lambda: calls.append("refresh"))
    _shift(vp, True)
    assert calls == ["capture", "refresh"]
    vp._shift_lock = object()
    _shift(vp, False)
    assert vp._shift_lock is None


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("key_release", [False, True])
def test_releasing_shift_during_navigation_clears_an_existing_drawing_lock(
        vp, monkeypatch, enabled, key_release):
    vp._dynamic_shift_nav = enabled
    vp._shift_lock = (V(1, 0, 0), "red")  # captured before starting the camera gesture
    monkeypatch.setattr(vp, "_capture_shift_lock",
                        lambda: pytest.fail("camera Shift must not capture a drawing lock"))
    monkeypatch.setattr(vp, "_refresh_snap",
                        lambda: pytest.fail("camera Shift must not refresh modeling hover"))
    _press(vp, shift=True)
    if key_release:
        before = _pose(vp.camera)
        _shift(vp, False)
        assert _pose(vp.camera) == before
    else:
        _move(vp, 120, 110, shift=False)  # the release was delivered elsewhere
    _mouse(vp, QEvent.MouseButtonRelease, 120, 110, Qt.MiddleButton, Qt.NoButton)
    assert vp._shift_lock is None


def test_saved_setting_defaults_on_and_accepts_native_booleans(tmp_path):
    from views.viewport import _load_dynamic_shift_navigation
    settings = QSettings(str(tmp_path / "nav.ini"), QSettings.IniFormat)
    assert _load_dynamic_shift_navigation(settings) is True
    for value, expected in (("0", False), (False, False), ("1", True), (True, True)):
        general_settings.set_value("dynamic_shift_navigation", value, settings)
        settings.sync()
        reopened = QSettings(settings.fileName(), QSettings.IniFormat)
        assert _load_dynamic_shift_navigation(reopened) is expected


def test_new_viewport_reads_the_saved_navigation_setting(tmp_path, monkeypatch):
    settings = QSettings(str(tmp_path / "nav.ini"), QSettings.IniFormat)
    general_settings.set_value("dynamic_shift_navigation", "0", settings)
    settings.sync()
    monkeypatch.setattr(general_settings, "QSettings", lambda: settings)
    viewport = Viewport()
    try:
        assert viewport._dynamic_shift_nav is False
    finally:
        viewport.close()

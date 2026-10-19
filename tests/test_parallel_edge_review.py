# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 IngeTrazo contributors.
"""Real camera/picker integration and pending edge timer boundaries."""
from __future__ import annotations

import math
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QFocusEvent, QVector3D as V

from core.snap import COLOR_REFERENCE
from tools.line import LineTool
from views.viewport import Viewport


@pytest.fixture
def drawing():
    viewport = Viewport()
    viewport.resize(800, 600)
    viewport.camera.set_aspect(800, 600)
    viewport.camera.target = V(4, 5, 0)
    viewport.camera.distance = 20
    viewport.camera.yaw = math.radians(90)
    viewport.camera.pitch = math.radians(90)
    viewport.scene.mesh.add_face([V(0, 0, 0), V(8, 0, 0),
                                  V(8, 10, 0), V(0, 10, 0)])
    reference = viewport.scene.mesh.add_edge(V(1, 1, 0), V(3, 2, 0))
    viewport.scene.version += 1
    tool = LineTool()
    tool.start_point = V(2, 3, 0)
    tool.work_plane = (V(0, 0, 0), V(0, 0, 1))
    viewport.active_tool = tool
    yield viewport, reference
    viewport.inference.reset()
    viewport.close()


def _hover(viewport, point):
    pixel = viewport._world_to_pixel(point)
    assert pixel is not None
    viewport._last_mouse_pos = QPointF(*pixel)
    viewport.inference.acquire(*pixel)
    return pixel


def _fire(viewport):
    timer = viewport.inference._edge_dwell_timer
    timer.stop()
    timer.timeout.emit()


@pytest.mark.parametrize("perspective", [False, True])
def test_real_camera_picks_and_parallel_landing_on_a_rectangle(drawing, perspective):
    viewport, reference = drawing
    viewport.camera.perspective = perspective
    _hover(viewport, V(2, 1.5, 0))
    assert viewport.inference._edge_dwell_timer.isActive()
    _fire(viewport)
    assert viewport._acquired_edge is reference
    pixel = _hover(viewport, V(8, 6.04, 0))
    assert viewport._acquired_edge is reference
    result = viewport.inference.snap(*pixel, Qt.NoModifier)
    assert result.kind == "intersection"
    assert (result.point - V(8, 6, 0)).length() < 1e-4


def _boundary(viewport, name):
    if name == "leave":
        viewport.leaveEvent(QEvent(QEvent.Leave))
    elif name == "focus":
        viewport.focusOutEvent(QFocusEvent(QEvent.FocusOut))
    elif name == "wheel":
        event = SimpleNamespace(position=lambda: QPointF(400, 300),
                                angleDelta=lambda: QPoint(0, 120))
        viewport.wheelEvent(event)
    else:
        event = SimpleNamespace(position=lambda: QPointF(400, 300),
                                modifiers=lambda: Qt.NoModifier)
        viewport._begin_camera_drag(event, "orbit")


@pytest.mark.parametrize("boundary", ["leave", "camera", "focus", "wheel"])
def test_viewport_leave_and_camera_gesture_cancel_pending_edge_dwell(drawing, boundary):
    viewport, _reference = drawing
    _hover(viewport, V(2, 1.5, 0))
    assert viewport.inference._edge_dwell_timer.isActive()
    _boundary(viewport, boundary)
    assert not viewport.inference._edge_dwell_timer.isActive()
    _fire(viewport)
    assert viewport._acquired_edge is None


@pytest.mark.parametrize("boundary", ["leave", "camera", "focus", "wheel"])
def test_leaving_or_navigating_preserves_an_already_confirmed_edge(drawing, boundary):
    viewport, reference = drawing
    _hover(viewport, V(2, 1.5, 0))
    _fire(viewport)
    assert viewport._acquired_edge is reference
    _hover(viewport, V(8, 6.04, 0))
    assert viewport.inference._edge_dwell_timer.isActive()
    _boundary(viewport, boundary)
    assert not viewport.inference._edge_dwell_timer.isActive()
    _fire(viewport)
    assert viewport._acquired_edge is reference


def test_actual_parallel_landing_keeps_solid_preview_magenta_and_shift_can_capture_it(drawing):
    viewport, _reference = drawing
    _hover(viewport, V(2, 1.5, 0))
    _fire(viewport)
    pixel = _hover(viewport, V(8, 6.04, 0))
    result = viewport.inference.snap(*pixel, Qt.NoModifier)
    assert result.kind == "intersection"
    viewport.last_snap = result
    viewport.active_tool.hover_point = result.point
    viewport._draw_rubber_band()
    segments, color, _width = viewport._overlay_rubber
    assert segments
    assert color[:3] == COLOR_REFERENCE
    viewport._capture_shift_lock()
    direction, lock_color = viewport._shift_lock
    assert lock_color == COLOR_REFERENCE
    assert V.crossProduct(direction, V(2, 1, 0)).length() < 1e-5


@pytest.mark.parametrize("boundary", ["leave", "focus"])
def test_a_queued_coalesced_hover_cannot_restart_dwell_after_the_view_loses_input(drawing, boundary):
    viewport, _reference = drawing
    pixel = viewport._world_to_pixel(V(2, 1.5, 0))
    viewport._pending_hover = (QPointF(*pixel), Qt.NoModifier)
    _boundary(viewport, boundary)
    viewport._run_pending_hover()
    assert not viewport.inference._edge_dwell_timer.isActive()

# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 IngeTrazo contributors.
"""A perpendicular draw can simultaneously land level with an acquired midpoint."""
from __future__ import annotations

import math

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QMatrix4x4, QMouseEvent, QVector3D as V
from PySide6.QtTest import QTest

from core.snap import AXIS_COLORS, COLOR_REFERENCE
from tools.line import LineTool
from views.viewport import Viewport


@pytest.fixture(params=[(False, "xy", 0), (True, "xy", 0),
                        (False, "xy", 25), (True, "xy", 25),
                        (False, "yz", 0), (True, "yz", 0)],
                ids=["ortho", "perspective", "ortho-rotated", "perspective-rotated",
                     "ortho-YZ", "perspective-YZ"])
def drawing(request):
    perspective, plane, angle = request.param
    transform = QMatrix4x4()
    if plane == "yz":
        transform.rotate(90, V(0, 1, 0))
        transform.rotate(90, V(0, 0, 1))
    transform.rotate(angle, V(0, 0, 1))
    point = transform.map
    viewport = Viewport()
    viewport.resize(800, 600)
    viewport.camera.set_aspect(800, 600)
    viewport.camera.target = point(V(4, 3, 0))
    viewport.camera.distance = 20
    viewport.camera.yaw = 0 if plane == "yz" else math.radians(90)
    viewport.camera.pitch = 0 if plane == "yz" else math.radians(90)
    viewport.camera.perspective = perspective
    viewport.scene.mesh.add_face([point(V(0, 0, 0)), point(V(8, 0, 0)),
                                  point(V(8, 6, 0)), point(V(0, 6, 0))])
    viewport.scene.version += 1
    viewport.active_tool = LineTool()
    yield viewport, point
    viewport.inference.reset()
    viewport.close()


def _hover(viewport, point):
    pixel = viewport._world_to_pixel(point)
    assert pixel is not None
    viewport._process_hover(QPointF(*pixel), Qt.NoModifier)
    return viewport.last_snap


def _click(viewport, point):
    pixel = viewport._world_to_pixel(point)
    assert pixel is not None
    viewport._dispatch_tool_click(QMouseEvent(
        QMouseEvent.MouseButtonPress, QPointF(*pixel), QPointF(*pixel),
        Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))


def test_acquired_side_midpoint_sets_height_while_draw_remains_perpendicular(drawing):
    viewport, point = drawing
    start, reference, center = (point(V(4, 0, 0)), point(V(8, 3, 0)),
                                point(V(4, 3, 0)))
    _click(viewport, start)
    assert (viewport.active_tool.start_point - start).length() < 1e-5
    midpoint = _hover(viewport, reference)
    assert midpoint.kind == "midpoint"
    QTest.qWait(300)  # Actual 250 ms point-encouragement timer.
    assert viewport._acquired_point is not None
    assert (viewport._acquired_point - reference).length() < 1e-5
    _hover(viewport, point(V(5.5, 2, 0)))
    cursor = point(V(4.03, 3.05, 0))
    result = _hover(viewport, cursor)
    assert (result.point - center).length() < 1e-4
    bottom_direction = (point(V(8, 0, 0)) - point(V(0, 0, 0))).normalized()
    draw = result.point - start
    assert abs(V.dotProduct(draw, bottom_direction)) < 1e-5
    assert result.guide is not None
    assert (result.guide[0] - reference).length() < 1e-4
    assert (result.guide[1] - center).length() < 1e-4

    _click(viewport, cursor)
    assert viewport.history.undo_stack
    assert (viewport.active_tool.start_point - center).length() < 1e-4
    assert any(
        ((edge.a - start).length() < 1e-4 and (edge.b - center).length() < 1e-4)
        or ((edge.b - start).length() < 1e-4 and (edge.a - center).length() < 1e-4)
        for edge in viewport.scene.mesh.edges)


def test_combined_midpoint_landing_keeps_direction_color_and_can_be_shift_locked(drawing):
    viewport, point = drawing
    start, reference, center = (point(V(4, 0, 0)), point(V(8, 3, 0)),
                                point(V(4, 3, 0)))
    _click(viewport, start)
    _hover(viewport, reference)
    QTest.qWait(300)
    _hover(viewport, point(V(5.5, 2, 0)))
    result = _hover(viewport, point(V(4.03, 3.05, 0)))
    assert (result.point - center).length() < 1e-4
    direction = (center - start).normalized()
    expected_color = (AXIS_COLORS["y"] if abs(direction.y()) > 0.9999
                      else AXIS_COLORS["z"] if abs(direction.z()) > 0.9999
                      else COLOR_REFERENCE)
    viewport._draw_rubber_band()
    _segments, color, _width = viewport._overlay_rubber
    assert color[:3] == expected_color
    viewport._capture_shift_lock()
    assert viewport._shift_lock is not None
    locked_direction, locked_color = viewport._shift_lock
    assert V.crossProduct(locked_direction, direction).length() < 1e-5
    assert locked_color == expected_color

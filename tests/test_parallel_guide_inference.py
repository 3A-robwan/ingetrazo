# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 IngeTrazo contributors.
"""Construction lines can supply the same deliberate parallel reference as edges."""
from __future__ import annotations

import math

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QVector3D as V
from PySide6.QtTest import QTest

from core.guide import Guide
from core.layers import Layer
from core.snap import COLOR_REFERENCE
from tools.line import LineTool
from views.viewport import Viewport


@pytest.fixture(params=[False, True], ids=["orthographic", "perspective"])
def drawing(request):
    viewport = Viewport()
    viewport.resize(800, 600)
    viewport.camera.set_aspect(800, 600)
    viewport.camera.target = V(4, 5, 0)
    viewport.camera.distance = 20
    viewport.camera.yaw = math.radians(90)
    viewport.camera.pitch = math.radians(90)
    viewport.camera.perspective = request.param
    viewport.scene.mesh.add_face([V(0, 0, 0), V(8, 0, 0),
                                  V(8, 10, 0), V(0, 10, 0)])
    guide = Guide(V(1, 1, 0), V(2, 1, 0))
    viewport.scene.guides.append(guide)
    viewport.scene.version += 1
    tool = LineTool()
    tool.start_point = V(2, 3, 0)
    tool.work_plane = (V(0, 0, 0), V(0, 0, 1))
    viewport.active_tool = tool
    viewport.inference.set_parallel_edge_dwell_ms(100)
    yield viewport, guide
    viewport.inference.reset()
    viewport.close()


def _hover(viewport, point):
    pixel = viewport._world_to_pixel(point)
    assert pixel is not None
    viewport._process_hover(QPointF(*pixel), Qt.NoModifier)
    return viewport.last_snap


def _acquire_guide(viewport, guide, point):
    _hover(viewport, point)
    assert viewport._acquired_edge is None
    QTest.qWait(160)
    reference = viewport._acquired_edge
    assert reference is not None, "a stationary construction-line hover must acquire its direction"
    direction = (reference.b - reference.a).normalized()
    assert V.crossProduct(direction, guide.direction).length() < 1e-5
    return reference


def test_guide_direction_drives_parallel_landing_pause_and_revisit(drawing):
    viewport, guide = drawing
    reference = _acquire_guide(viewport, guide, V(2, 1.5, 0))
    preview = _hover(viewport, V(6, 5.04, 0))
    assert preview.kind == "reference"
    assert preview.color == COLOR_REFERENCE
    assert V.crossProduct(preview.point - V(2, 3, 0), guide.direction).length() < 1e-5
    landing = _hover(viewport, V(8, 6.04, 0))
    assert landing.kind == "intersection"
    assert (landing.point - V(8, 6, 0)).length() < 1e-4
    QTest.qWait(350)  # Both the 100 ms direction dwell and 250 ms point dwell.
    assert viewport._acquired_edge is reference
    for _ in range(2):
        _hover(viewport, V(6, 5, 0))
        result = _hover(viewport, V(8, 6.04, 0))
        assert result.kind == "intersection"
        assert (result.point - V(8, 6, 0)).length() < 1e-4
        assert viewport._acquired_edge is reference


def test_a_point_guide_does_not_acquire_the_direction_of_its_drawn_origin_connector(drawing):
    viewport, guide = drawing
    point = Guide(V(2, 1.5, 0), origin=V(1, 1, 0))
    viewport.scene.guides[:] = [point]
    viewport.scene.version += 1
    _hover(viewport, V(2, 1.5, 0))
    QTest.qWait(160)
    assert viewport._acquired_edge is None


@pytest.mark.parametrize("blocked", ["hidden_layer", "excluded"])
def test_hidden_and_transform_excluded_guides_cannot_supply_a_direction(drawing, blocked):
    viewport, guide = drawing
    if blocked == "hidden_layer":
        viewport.scene.layers.append(Layer("Hidden construction", visible=False))
        guide.layer = "Hidden construction"
    else:
        viewport.active_tool.snap_excluded_guides = lambda: {id(guide)}
    viewport.scene.version += 1
    _hover(viewport, V(2, 1.5, 0))
    QTest.qWait(160)
    assert viewport._acquired_edge is None


@pytest.mark.parametrize("change", ["removed", "excluded"])
def test_guide_that_disappears_during_the_pause_is_not_acquired(drawing, change):
    viewport, guide = drawing
    _hover(viewport, V(2, 1.5, 0))
    if change == "removed":
        viewport.scene.guides.remove(guide)
    else:
        viewport.active_tool.snap_excluded_guides = lambda: {id(guide)}
    viewport.scene.version += 1
    QTest.qWait(160)
    assert viewport._acquired_edge is None


def test_guide_anchor_is_preserved_and_direction_remains_precise(drawing):
    viewport, old_guide = drawing
    guide = Guide(V(0.371, -0.243, 0), V(0.89, 0.456789, 0))
    original_point = V(guide.point)
    original_direction = V(guide.direction)
    viewport.scene.guides[:] = [guide]
    viewport.scene.version += 1
    _acquire_guide(viewport, guide, guide.point + guide.direction * 3)
    start = viewport.active_tool.start_point
    perpendicular = V(-guide.direction.y(), guide.direction.x(), 0)
    result = _hover(viewport, start + guide.direction * 5 + perpendicular * 0.005)
    assert result.kind == "reference"
    assert V.crossProduct(result.point - start, original_direction).length() < 1e-5
    assert guide.point == original_point
    assert guide.direction == original_direction

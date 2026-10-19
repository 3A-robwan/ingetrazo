# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 IngeTrazo contributors.
"""Dwelling on a parallel landing must not make its target edge steal the reference."""
from __future__ import annotations

import math

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QMatrix4x4, QVector3D as V
from PySide6.QtTest import QTest

from tools.line import LineTool
from views.viewport import Viewport


@pytest.fixture
def drawing(request):
    perspective, rotation, *height = request.param
    height = height[0] if height else 10
    transform = QMatrix4x4()
    transform.rotate(rotation, V(0, 0, 1))
    point = transform.map
    viewport = Viewport()
    viewport.resize(800, 600)
    viewport.camera.set_aspect(800, 600)
    viewport.camera.target = point(V(4, 5, 0))
    viewport.camera.distance = 20
    viewport.camera.yaw = math.radians(90)
    viewport.camera.pitch = math.radians(90)
    viewport.camera.perspective = perspective
    viewport.scene.mesh.add_face([point(V(0, 0, 0)), point(V(8, 0, 0)),
                                  point(V(8, height, 0)), point(V(0, height, 0))])
    reference = viewport.scene.mesh.add_edge(point(V(1, 1, 0)), point(V(3, 2, 0)))
    viewport.scene.version += 1
    tool = LineTool()
    tool.start_point = point(V(2, 3, 0))
    tool.work_plane = (V(0, 0, 0), V(0, 0, 1))
    viewport.active_tool = tool
    yield viewport, reference, point
    viewport.inference.reset()
    viewport.close()


def _hover(viewport, point):
    pixel = viewport._world_to_pixel(point)
    assert pixel is not None
    viewport._process_hover(QPointF(*pixel), Qt.NoModifier)
    return viewport.last_snap


def _wait_for_reference(viewport, reference, point, wait_ms=560):
    _hover(viewport, point)
    QTest.qWait(wait_ms)
    assert viewport._acquired_edge is reference


def _edge_approach(viewport, landing, along_wall):
    """Twelve px is inside edge snap (14), outside point encouragement (9)."""
    pixel = viewport._world_to_pixel(landing)
    shifted = viewport._world_to_pixel(landing + along_wall)
    pixels_per_metre = math.hypot(shifted[0] - pixel[0], shifted[1] - pixel[1])
    return landing + along_wall * (12.0 / pixels_per_metre)


def _exercise_revisit(drawing, initial_wait_ms=560, ending_wait_ms=300):
    viewport, reference, point = drawing
    landing = point(V(8, 6, 0))
    _wait_for_reference(viewport, reference, point(V(2, 1.5, 0)), initial_wait_ms)
    along_wall = point(V(0, 1, 0)) - point(V(0, 0, 0))
    approach = _edge_approach(viewport, landing, along_wall)
    initial = _hover(viewport, approach)
    assert initial.kind == "intersection"
    assert (initial.point - landing).length() < 1e-4
    QTest.qWait(300)
    assert viewport._acquired_point is not None
    assert (viewport._acquired_point - landing).length() < 1e-4
    QTest.qWait(ending_wait_ms)
    assert viewport._acquired_edge is reference
    for _ in range(2):
        _hover(viewport, point(V(6, 5, 0)))
        result = _hover(viewport, approach)
        assert viewport._acquired_edge is reference
        assert result.kind == "intersection"
        assert (result.point - landing).length() < 1e-4


@pytest.mark.parametrize("drawing", [(False, 0), (True, 0), (False, 25), (True, 25)],
                         indirect=True)
def test_point_and_edge_dwell_at_parallel_landing_preserve_reference_and_return_snap(drawing):
    _exercise_revisit(drawing)


@pytest.mark.parametrize("drawing", [(False, 0, 12), (True, 0, 12)], indirect=True)
def test_revisiting_a_parallel_landing_at_the_target_edges_midpoint(drawing):
    _exercise_revisit(drawing)


@pytest.mark.parametrize("drawing", [(True, 0)], indirect=True)
def test_fast_edge_dwell_before_point_encouragement_still_preserves_the_landing(drawing):
    viewport, _reference, _point = drawing
    viewport.inference.set_parallel_edge_dwell_ms(100)
    _exercise_revisit(drawing, initial_wait_ms=160, ending_wait_ms=50)


@pytest.mark.parametrize("drawing", [(False, 0), (True, 25)], indirect=True)
def test_an_edge_can_still_become_a_new_reference_away_from_the_parallel_landing(drawing):
    viewport, reference, point = drawing
    _wait_for_reference(viewport, reference, point(V(2, 1.5, 0)))
    landing = _hover(viewport, point(V(8, 6.04, 0)))
    assert landing.kind == "intersection"
    # This point is outside the old parallel cone and away from endpoints /
    # midpoint, on the SAME edge just visited as a landing. There is only one
    # new mouse position before the pause: the previous last_snap must not
    # suppress its timer and require the user to move again.
    _hover(viewport, point(V(8, 8, 0)))
    candidate = viewport._hover_edge
    assert candidate is not None and candidate is not reference
    QTest.qWait(560)
    assert viewport._acquired_edge is candidate

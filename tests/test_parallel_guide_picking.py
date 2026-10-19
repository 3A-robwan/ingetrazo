# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 IngeTrazo contributors.
"""Guide-direction picking keeps model picks, visibility and precise directions."""
from __future__ import annotations

import math
from types import SimpleNamespace

import pytest
from PySide6.QtGui import QVector3D as V

from core.guide import Guide
from core.snap import compute_snap
from tools.line import LineTool
from views.viewport import Viewport


@pytest.fixture(params=[False, True], ids=["orthographic", "perspective"])
def view(request):
    viewport = Viewport()
    viewport.resize(800, 600)
    viewport.camera.set_aspect(800, 600)
    viewport.camera.target = V(4, 5, 0)
    viewport.camera.distance = 20
    viewport.camera.yaw = math.radians(90)
    viewport.camera.pitch = math.radians(90)
    viewport.camera.perspective = request.param
    tool = LineTool()
    tool.start_point = V(2, 3, 0)
    tool.work_plane = (V(), V(0, 0, 1))
    viewport.active_tool = tool
    yield viewport
    viewport.inference.reset()
    viewport.close()


def _pixel(viewport, point=V(4, 5, 0)):
    pixel = viewport._world_to_pixel(point)
    assert pixel is not None
    return pixel


@pytest.mark.parametrize("edge_offset, guide_offset, winner", [
    (0.03, 0.12, "edge"),
    (0.12, 0.03, "guide"),
    (0.0, 0.0, "edge"),
], ids=["closer-edge", "closer-guide", "coincident-geometry-wins"])
def test_nearest_reference_wins_and_geometry_keeps_exact_ties(
        view, edge_offset, guide_offset, winner):
    edge = view.scene.mesh.add_edge(V(1, 5 + edge_offset, 0), V(7, 5 + edge_offset, 0))
    guide = Guide(V(4, 5 + guide_offset, 0), V(1, 0, 0))
    view.scene.guides.append(guide)
    view.scene.version += 1
    px, py = _pixel(view)
    assert view.pick_edge_any(px, py) is edge
    result = view.pick_parallel_reference(px, py, edge)
    assert result is (edge if winner == "edge" else guide)


def test_a_closer_point_guide_does_not_mask_a_line_guide(view):
    point = Guide(V(4, 5, 0), origin=V(3, 4, 0))
    line = Guide(V(4, 5.1, 0), V(1, 0, 0))
    view.scene.guides[:] = [point, line]
    px, py = _pixel(view)
    assert view.pick_guide(px, py) is point
    assert view.pick_parallel_reference(px, py) is line


def _cover(view):
    view.scene.mesh.add_face([V(2, 3, 1), V(6, 3, 1), V(6, 7, 1), V(2, 7, 1)])
    view.scene.version += 1


def test_a_guide_behind_a_face_is_not_a_parallel_reference(view):
    guide = Guide(V(4, 5, 0), V(1, 0, 0))
    view.scene.guides.append(guide)
    _cover(view)
    assert view._is_occluded(guide.point)
    assert view.pick_parallel_reference(*_pixel(view)) is None


def test_an_occluded_nearest_guide_does_not_mask_a_visible_guide(view):
    hidden = Guide(V(4, 5, 0), V(1, 0, 0))
    visible = Guide(V(4, 5.1, 2), V(1, 0, 0))
    view.scene.guides[:] = [hidden, visible]
    _cover(view)
    assert view._is_occluded(hidden.point)
    assert not view._is_occluded(visible.point)
    assert view.pick_parallel_reference(*_pixel(view)) is visible


def test_a_line_guide_anchor_is_not_treated_as_an_endpoint(view):
    guide = Guide(V(4, 5, 0), V(2, 1, 0))
    view.scene.guides.append(guide)
    px, py = _pixel(view)
    view.inference.acquire(px, py)
    assert view.inference._edge_dwell_edge is guide
    view.inference._edge_dwell_timer.stop()
    view.inference._edge_dwell_timer.timeout.emit()
    assert view._acquired_edge is guide
    assert view._hover_edge is None


def test_guide_acquisition_keeps_the_model_hover_edge(view):
    edge = view.scene.mesh.add_edge(V(1, 5.12, 0), V(7, 5.12, 0))
    guide = Guide(V(4, 5.03, 0), V(2, 1, 0))
    view.scene.guides.append(guide)
    view.scene.version += 1
    view.inference.acquire(*_pixel(view))
    assert view._hover_edge is edge
    assert view.inference._edge_dwell_edge is guide


def test_camera_clipping_does_not_change_guide_reference_identity(view):
    guide = Guide(V(4, 5, 0), V(2, 1, 0))
    view.scene.guides.append(guide)
    key = view.inference._edge_key(guide)
    initial_segment = view._guide_snap_segment(guide)
    view.camera.pitch = math.radians(40)
    view.camera.yaw = math.radians(-30)
    assert view._guide_snap_segment(guide) != initial_segment
    chosen = view.pick_parallel_reference(*_pixel(view))
    assert chosen is guide
    assert view.inference._edge_key(chosen) == key


def test_parallel_direction_does_not_use_far_away_artificial_guide_endpoints():
    guide = Guide(V(1e8, 1e8, 1e8), V(1, 0.5, 0.125))
    start = V(2, 3, 4)
    direction = guide.direction
    candidate = start + direction * 5

    def project(origin, axis):
        return origin + axis * V.dotProduct(candidate - origin, axis)

    result = compute_snap(
        candidate_world=candidate,
        candidate_pixel=(candidate.x() * 10, candidate.y() * 10),
        scene=SimpleNamespace(edges=[]),
        world_to_pixel=lambda point: (point.x() * 10, point.y() * 10),
        threshold_px=9,
        start_point=start,
        acquired_edge=guide,
        project_onto_line=project,
    )
    assert result.kind == "reference"
    assert V.crossProduct(result.point - start, direction).length() < 1e-6

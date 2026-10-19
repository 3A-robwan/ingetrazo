# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Edge picks follow the displayed camera ray in both camera projections."""
from __future__ import annotations

import math

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QVector3D as V

from core.group import Group
from core.layers import Layer, assign_layer
from core.mesh import Mesh
from core.section import SectionPlane
from core.style import Style
from tools.base import ToolContext
from tools.select import SelectTool
from views.viewport import Viewport


@pytest.fixture
def viewport():
    vp = Viewport(None)
    vp.resize(1000, 600)
    vp.camera.set_aspect(1000, 600)
    vp.camera.set_view("top")
    yield vp
    vp.close()
    vp.deleteLater()


def _lid(mesh, x=0):
    return mesh.add_face([V(x, 0, 1), V(x + 2, 0, 1),
                          V(x + 2, 2, 1), V(x, 2, 1)])


def _scene(vp, case, grouped=False):
    mesh = Mesh() if grouped else vp.scene.mesh
    lid = _lid(mesh)
    blocker = lid
    if grouped:
        blocker = Group(mesh, "Lid")
        vp.scene.groups.append(blocker)
    if case == "parallel-eye-ray":
        vp.camera.perspective = False
        vp.camera.target = V(5, 3, 0)
        vp.camera.distance = 12
        edge = vp.scene.mesh.add_edge(V(1.75, 1, 0), V(1.85, 1, 0))
        point = V(1.8, 1, 0)
    else:
        assert case == "perspective-interpolation"
        vp.camera.perspective = True
        vp.camera.target = V(1, 1, 0)
        vp.camera.distance = 6
        edge = vp.scene.mesh.add_edge(V(-4, 1, -8), V(4, 1, 0))
        point = V(-0.5 / 0.85, 1, -0.5 / 0.85 - 4)
    vp.scene.version += 1
    return edge, point, blocker


def _pixel(vp, point):
    pixel = vp._world_to_pixel(point)
    assert pixel is not None
    return pixel


def _lid_ray(vp, point):
    """Independent plane intersection of the actual pixel ray, not eye→point.

    All test lids occupy [0, 2] × [0, 2] at z=1. Intersecting that plane
    gives an oracle independent of the occlusion and interpolation helpers.
    """
    origin, direction = vp._pixel_to_ray(*_pixel(vp, point))
    assert origin is not None and direction is not None
    assert direction.length() == pytest.approx(1, abs=1e-6)
    point_t = V.dotProduct(point - origin, direction)
    assert (origin + direction * point_t - point).length() < 0.002
    lid_t = (1 - origin.z()) / direction.z()
    hit = origin + direction * lid_t
    return (0 < lid_t < point_t - 1e-3
            and 0 <= hit.x() <= 2 and 0 <= hit.y() <= 2)


def _context(vp, point):
    return ToolContext(viewport=vp, world=point,
                       screen=QPointF(*_pixel(vp, point)),
                       modifiers=Qt.NoModifier, snap=None)


def _signature(mesh):
    def xyz(p):
        return tuple(round(float(v), 6) for v in p.toTuple())
    return sorted(tuple(sorted((xyz(e.a), xyz(e.b)))) for e in mesh.edges)


@pytest.mark.parametrize("case", ["parallel-eye-ray", "perspective-interpolation"])
def test_hidden_fragment_hover_click_delete_and_undo(viewport, case):
    vp = viewport
    edge, point, lid = _scene(vp, case)
    before = _signature(vp.scene.mesh)
    assert _lid_ray(vp, point)
    assert vp.pick_edge(*_pixel(vp, point)) is edge
    assert vp.pick_visible_edge(*_pixel(vp, point)) is None

    tool = SelectTool()
    tool.on_hover(_context(vp, point))
    assert vp._hover_entity is lid
    tool.on_click(_context(vp, point))
    assert vp.scene.selection == {lid}
    assert tool.on_key(vp, Qt.Key_Delete, Qt.NoModifier)
    assert edge in vp.scene.mesh.edges
    assert _signature(vp.scene.mesh) == before
    assert not vp.scene.mesh.faces
    assert vp.history.undo()
    assert _signature(vp.scene.mesh) == before
    assert len(vp.scene.mesh.faces) == 1
    assert vp.history.redo()
    assert _signature(vp.scene.mesh) == before
    assert not vp.scene.mesh.faces


@pytest.mark.parametrize("fraction", [0, 0.2, 0.5, 0.85, 1])
def test_perspective_sample_projects_back_to_cursor(viewport, fraction):
    vp = viewport
    edge, _point, _lid_face = _scene(vp, "perspective-interpolation")
    actual = edge.a + (edge.b - edge.a) * fraction
    pixel = _pixel(vp, actual)
    sampled = vp.edge_point_under_cursor(edge, *pixel)
    assert sampled is not None
    assert (sampled - actual).length() < 1e-4
    assert _pixel(vp, sampled) == pytest.approx(pixel, abs=0.002)


def test_two_point_perspective_sample_projects_back_to_cursor(viewport):
    vp = viewport
    edge, _point, _lid_face = _scene(vp, "perspective-interpolation")
    vp.camera.yaw = math.radians(-45)
    vp.camera.pitch = math.radians(30)
    vp.camera.two_point = True
    assert vp.camera._level_forward() is not None
    for fraction in (0.2, 0.5, 0.85):
        actual = edge.a + (edge.b - edge.a) * fraction
        pixel = _pixel(vp, actual)
        sampled = vp.edge_point_under_cursor(edge, *pixel)
        assert sampled is not None
        assert (sampled - actual).length() < 1e-4
        assert _pixel(vp, sampled) == pytest.approx(pixel, abs=0.002)


@pytest.mark.parametrize("case", ["parallel-eye-ray", "perspective-interpolation"])
def test_visible_edge_without_blocker_can_be_deleted_and_restored(viewport, case):
    vp = viewport
    edge, point, lid = _scene(vp, case)
    vp.scene.mesh.remove_face(lid)
    vp.scene.version += 1
    before = _signature(vp.scene.mesh)
    assert vp.pick_visible_edge(*_pixel(vp, point)) is edge
    tool = SelectTool()
    tool.on_hover(_context(vp, point))
    assert vp._hover_entity is edge
    tool.on_click(_context(vp, point))
    assert vp.scene.selection == {edge}
    assert tool.on_key(vp, Qt.Key_Delete, Qt.NoModifier)
    assert len(vp.scene.mesh.edges) == len(before) - 1
    assert vp.history.undo()
    assert _signature(vp.scene.mesh) == before
    assert vp.history.redo()
    assert len(vp.scene.mesh.edges) == len(before) - 1


def test_one_perspective_edge_has_hidden_and_visible_fragments(viewport):
    vp = viewport
    edge, covered, lid = _scene(vp, "perspective-interpolation")
    open_point = V(-3, 1, -7)
    assert _lid_ray(vp, covered)
    assert not _lid_ray(vp, open_point)
    assert vp.pick_visible_edge(*_pixel(vp, covered)) is None
    assert SelectTool()._pick(vp, *_pixel(vp, covered)) is lid
    assert vp.pick_visible_edge(*_pixel(vp, open_point)) is edge
    assert SelectTool()._pick(vp, *_pixel(vp, open_point)) is edge


@pytest.mark.parametrize("case", ["parallel-eye-ray", "perspective-interpolation"])
def test_group_face_blocks_a_loose_edge(viewport, case):
    vp = viewport
    edge, point, group = _scene(vp, case, grouped=True)
    assert _lid_ray(vp, point)
    assert vp.pick_visible_edge(*_pixel(vp, point)) is None
    assert SelectTool()._pick(vp, *_pixel(vp, point)) is group
    SelectTool().on_click(_context(vp, point))
    assert vp.scene.selection == {group}
    assert edge not in vp.scene.selection


@pytest.mark.parametrize("case", ["parallel-eye-ray", "perspective-interpolation"])
def test_hidden_edges_are_rejected_inside_group_edit(viewport, case):
    vp = viewport
    edge, point, lid = _scene(vp, case)
    group = Group(vp.scene.mesh, "Editable")
    vp.scene.mesh = Mesh()
    vp.scene.groups.append(group)
    vp.scene.begin_group_edit(group)
    try:
        assert vp.scene.mesh is group.mesh
        assert _lid_ray(vp, point)
        assert vp.pick_visible_edge(*_pixel(vp, point)) is None
        tool = SelectTool()
        tool.on_hover(_context(vp, point))
        assert vp._hover_entity is lid
        tool.on_click(_context(vp, point))
        assert vp.scene.selection == {lid}
        assert edge not in vp.scene.selection
    finally:
        vp.scene.end_group_edit()


@pytest.mark.parametrize("perspective", [False, True])
def test_edge_on_group_face_remains_selectable(viewport, perspective):
    vp = viewport
    vp.camera.perspective = perspective
    vp.camera.target = V(5, 3, 0)
    vp.camera.distance = 12
    mesh = Mesh()
    _lid(mesh)
    group = Group(mesh, "Lid")
    vp.scene.groups.append(group)
    edge = vp.scene.mesh.add_edge(V(0.5, 1, 1), V(1.5, 1, 1))
    vp.scene.version += 1
    point = V(1, 1, 1)
    assert not vp._is_occluded(point)
    assert vp.pick_visible_edge(*_pixel(vp, point)) is edge
    assert SelectTool()._pick(vp, *_pixel(vp, point)) is edge


@pytest.mark.parametrize("state", ["locked-blocker", "hidden-blocker",
                                    "locked-edge", "hidden-edge"])
def test_visible_and_selectable_layer_rules_are_distinct(viewport, state):
    vp = viewport
    edge, point, lid = _scene(vp, "parallel-eye-ray")
    layer = Layer("Test", visible=not state.startswith("hidden"),
                  locked=state.startswith("locked"))
    vp.scene.layers.append(layer)
    assign_layer(lid if state.endswith("blocker") else edge, layer.name)
    vp.scene.version += 1
    pixel = _pixel(vp, point)
    if state == "hidden-blocker":
        assert not vp._is_occluded(point)
        assert vp.pick_visible_edge(*pixel) is edge
        assert SelectTool()._pick(vp, *pixel) is edge
    else:
        assert vp._is_occluded(point)
        assert vp.pick_visible_edge(*pixel) is None
        assert edge is not SelectTool()._pick(vp, *pixel)
        if state.endswith("edge"):
            # Lock/Hide also excludes an edge with no face in front of it.
            vp.scene.mesh.remove_face(lid)
            vp.scene.version += 1
            assert not vp._is_occluded(point)
            assert vp.pick_edge(*pixel) is None
            assert vp.pick_visible_edge(*pixel) is None


def test_distant_oblique_orthographic_face_does_not_occlude_itself(viewport):
    vp = viewport
    vp.camera.perspective = False
    vp.camera.target = V(0, 0, 0)
    vp.camera.yaw = math.radians(45)
    vp.camera.pitch = math.radians(30)
    vp.camera.distance = 10000
    assert vp.camera.far_plane() == 40000
    vp.scene.mesh.add_face([V(-100, -100, 0), V(100, -100, 0),
                            V(100, 100, 0), V(-100, 100, 0)])
    vp.scene.version += 1
    forward = vp.camera.forward()
    on_face = [V(10, 10, 0), V(-10, 10, 0), V(15, 15, 0)]
    points = on_face + [on_face[1] + forward * 0.1,
                        on_face[1] - forward * 0.1]
    expected = [False, False, False, True, False]
    assert [vp._is_occluded(p) for p in points] == expected
    assert vp._occluded_many(points) == expected


@pytest.mark.parametrize("many_spans", [False, True])
@pytest.mark.parametrize("block_size", [2_000_000, 4], ids=["full", "small-blocks"])
def test_orthographic_batch_matches_pixel_ray_oracle_and_scalar(
        viewport, many_spans, block_size, monkeypatch):
    vp = viewport
    monkeypatch.setattr(vp, "_OCCL_BLOCK", block_size)
    vp.camera.perspective = False
    vp.camera.target = V(5, 3, 0)
    vp.camera.distance = 12
    for i in range(66 if many_spans else 1):
        mesh = Mesh()
        _lid(mesh, x=3 * i)
        vp.scene.groups.append(Group(mesh, "Panel"))
    vp.scene.version += 1
    points = [V(1.8, 1, 0), V(-0.5, 1, 0), V(2.5, 1, 0),
              V(1, 1, 1), V(1, 1, 2)]
    expected = [_lid_ray(vp, p) for p in points]
    assert expected == [True, False, False, False, False]
    idx = vp._pick_index()
    count = len(idx.tri_spans or []) + len(idx.own_spans)
    assert (count > 64) == many_spans
    scalar = [vp._is_occluded(p) for p in points]
    assert scalar == expected
    assert vp._occluded_many(iter(points)) == scalar
    assert vp._occluded_many([]) == []


@pytest.mark.parametrize("mode", ["shaded", "xray", "wireframe"])
def test_section_removes_blocker_and_clips_edge_in_every_style(viewport, mode):
    vp = viewport
    edge, point, _lid_face = _scene(vp, "parallel-eye-ray")
    vp.scene.display_style = Style(name=mode, face_mode=mode)
    cut = SectionPlane(V(0, 0, 0.5), V(0, 0, 1), hidden=True)
    vp.scene.section_planes.append(cut)
    vp.scene.set_active_section(cut)
    vp.scene.version += 1
    assert not vp._is_occluded(point)
    assert vp._occluded_many([point, V(1.8, 1, 1)]) == [False, True]
    assert vp.pick_visible_edge(*_pixel(vp, point)) is edge
    cut.flip()
    vp.scene.version += 1
    assert vp._is_occluded(point)
    assert vp.pick_visible_edge(*_pixel(vp, point)) is None


def test_section_clips_only_the_removed_fragment_of_a_crossing_edge(viewport):
    vp = viewport
    vp.camera.perspective = False
    vp.camera.target = V(5, 3, 0)
    vp.camera.distance = 12
    edge = vp.scene.mesh.add_edge(V(0.5, 1, 0), V(1.5, 1, 1))
    cut = SectionPlane(V(0, 0, 0.5), V(0, 0, 1), hidden=True)
    vp.scene.section_planes.append(cut)
    vp.scene.set_active_section(cut)
    vp.scene.version += 1
    kept, removed = V(0.7, 1, 0.2), V(1.3, 1, 0.8)
    assert vp.pick_visible_edge(*_pixel(vp, kept)) is edge
    assert vp.pick_visible_edge(*_pixel(vp, removed)) is None
    assert vp._occluded_many([kept, removed]) == [False, True]


def test_orthographic_occluder_behind_eye_is_still_visible(viewport):
    vp = viewport
    vp.camera.perspective = False
    vp.camera.target = V(5, 3, 0)
    vp.camera.distance = 12
    z = vp.camera.eye().z()
    point = V(1.8, 1, z + 1)
    edge = vp.scene.mesh.add_edge(V(1.75, 1, z + 1), V(1.85, 1, z + 1))
    vp.scene.mesh.add_face([V(0, 0, z + 2), V(2, 0, z + 2),
                            V(2, 2, z + 2), V(0, 2, z + 2)])
    vp.scene.version += 1
    origin, direction = vp._pixel_to_ray(*_pixel(vp, point))
    point_t = V.dotProduct(point - origin, direction)
    face_t = (z + 2 - origin.z()) / direction.z()
    assert 0 < face_t < point_t
    assert vp._is_occluded(point)
    assert vp._occluded_many([point]) == [True]
    assert vp.pick_edge(*_pixel(vp, point)) is edge
    assert vp.pick_visible_edge(*_pixel(vp, point)) is None


def test_orthographic_geometry_before_near_clip_does_not_occlude(viewport):
    vp = viewport
    vp.camera.perspective = False
    vp.camera.target = V(5, 3, 0)
    vp.camera.distance = 12
    edge = vp.scene.mesh.add_edge(V(1.75, 1, 0), V(1.85, 1, 0))
    z = vp.camera.eye().z() + vp.camera.far_plane() + 100
    vp.scene.mesh.add_face([V(0, 0, z), V(2, 0, z),
                            V(2, 2, z), V(0, 2, z)])
    vp.scene.version += 1
    point = V(1.8, 1, 0)
    assert not vp._is_occluded(point)
    assert vp._occluded_many([point]) == [False]
    assert vp.pick_visible_edge(*_pixel(vp, point)) is edge

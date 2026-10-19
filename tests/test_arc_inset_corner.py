# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 IngeTrazo contributors.
"""Rounding an inset loop also rounds the surrounding face's hole boundary."""
from __future__ import annotations

import math

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QMatrix4x4, QVector3D as V

from core.history import MoveVerticesCommand
from tools.arc import ArcTool
from tools.base import ToolContext
from tools.rectangle import RectangleTool
from views.viewport import Viewport


def _context(viewport, point, modifiers=Qt.NoModifier):
    pixel = viewport._world_to_pixel(point)
    assert pixel is not None
    return ToolContext(viewport=viewport, world=V(point), screen=QPointF(*pixel),
                       modifiers=modifiers, snap=None)


def _rectangle(viewport, start, end, normal):
    tool = RectangleTool()
    viewport.active_tool = tool
    tool.on_activate(viewport)
    tool.work_plane = (V(start), V(normal))
    tool.on_click(_context(viewport, start))
    tool.on_hover(_context(viewport, end))
    tool.on_click(_context(viewport, end))
    assert viewport.history.last_error is None


@pytest.fixture
def inset(request):
    mode = getattr(request, "param", "xy")
    transform = QMatrix4x4()
    if mode == "yz":
        transform.rotate(90, V(0, 1, 0))
        transform.rotate(90, V(0, 0, 1))
    point = transform.map
    normal = transform.mapVector(V(0, 0, 1))
    viewport = Viewport()
    viewport.resize(1000, 700)
    viewport.camera.set_aspect(1000, 700)
    viewport.camera.target = point(V(5, 4, 0))
    viewport.camera.distance = 15
    viewport.camera.yaw = 0 if mode == "yz" else math.radians(90)
    viewport.camera.pitch = 0 if mode == "yz" else math.radians(90)
    viewport.camera.perspective = False
    viewport.flash_status = lambda *args, **kwargs: None
    _rectangle(viewport, point(V(0, 0, 0)), point(V(10, 8, 0)), normal)
    _rectangle(viewport, point(V(2, 2, 0)), point(V(8, 6, 0)), normal)
    if mode == "busy_3d":
        viewport.scene.mesh.add_face([V(0, 0, 0), V(0, 8, 0),
                                      V(0, 8, 2), V(0, 0, 2)])
        viewport.scene.version += 1
    yield viewport, point, normal
    viewport.inference.reset()
    viewport.close()


def _round(inset, modifiers=Qt.NoModifier):
    viewport, point, normal = inset
    tool = ArcTool()
    viewport.active_tool = tool
    tool.on_activate(viewport)
    tool.hover_plane = (point(V(0, 0, 0)), normal)
    tool.on_click(_context(viewport, point(V(7, 2, 0))))
    tool.on_hover(_context(viewport, point(V(8, 3, 0))))
    assert tool._equidistant is not None
    tool.on_click(_context(viewport, point(V(8, 3, 0))))
    assert tool._fillet is not None
    tool.on_double_click(_context(viewport, point(V(8, 3, 0)), modifiers))
    assert viewport.history.last_error is None
    return tool


def _area(mesh):
    return sum(V.crossProduct(b - a, c - a).length() * 0.5
               for face in mesh.faces for a, b, c in face.triangulate())


def _assert_real_boundaries(mesh):
    for face in mesh.faces:
        for loop in (face.loop, *face.hole_loops):
            for a, b in zip(loop, loop[1:] + loop[:1]):
                edge = mesh.find_edge(a, b)
                assert edge is not None and face in edge.faces


def _assert_no_old_corner(inset):
    viewport, point, _normal = inset
    corner = point(V(8, 2, 0))
    assert viewport.scene.mesh.vertex_at(corner) is None
    assert all((vertex.position - corner).length() > 1e-5
               for face in viewport.scene.mesh.faces
               for loop in (face.loop, *face.hole_loops) for vertex in loop)


def _assert_healthy_rounded_inset(inset, expected_area):
    viewport, point, normal = inset
    mesh = viewport.scene.mesh
    assert _area(mesh) == pytest.approx(expected_area, abs=1e-4)
    _assert_real_boundaries(mesh)
    _assert_no_old_corner(inset)
    coplanar = [face for face in mesh.faces
                if abs(V.dotProduct(face.normal(), normal)) > 0.999]
    surrounding = [face for face in coplanar if face.hole_loops]
    assert len(surrounding) == 1
    rounded = min(coplanar, key=lambda face: face.area())
    assert len(surrounding[0].hole_loops) == 1
    assert set(surrounding[0].hole_loops[0]) == set(rounded.loop)
    return rounded


@pytest.mark.parametrize("inset", ["xy", "yz", "busy_3d"], indirect=True)
def test_rounding_inset_preserves_surface_and_has_reversible_shared_hole_boundary(inset):
    viewport, point, _normal = inset
    initial_area = _area(viewport.scene.mesh)
    initial_edges = len(viewport.scene.mesh.edges)
    _round(inset)
    _assert_healthy_rounded_inset(inset, initial_area)
    assert viewport.history.undo()
    assert _area(viewport.scene.mesh) == pytest.approx(initial_area, abs=1e-4)
    assert len(viewport.scene.mesh.edges) == initial_edges
    assert viewport.scene.mesh.vertex_at(point(V(8, 2, 0))) is not None
    _assert_real_boundaries(viewport.scene.mesh)
    assert viewport.history.redo()
    _assert_healthy_rounded_inset(inset, initial_area)


@pytest.mark.parametrize("inset", ["xy", "yz", "busy_3d"], indirect=True)
def test_retyping_segments_and_radius_keeps_the_surrounding_surface_and_one_undo_step(inset):
    viewport, _point, _normal = inset
    initial_area = _area(viewport.scene.mesh)
    tool = _round(inset)
    stack_size = len(viewport.history.undo_stack)
    assert tool.on_segments_value(viewport, 8)
    assert sum(edge.curve is not None for edge in viewport.scene.mesh.edges) == 8
    _assert_healthy_rounded_inset(inset, initial_area)
    assert tool.on_radius_value(viewport, 0.5)
    _assert_healthy_rounded_inset(inset, initial_area)
    assert len(viewport.history.undo_stack) == stack_size
    assert viewport.history.undo()
    assert not any(edge.curve is not None for edge in viewport.scene.mesh.edges)
    assert viewport.history.redo()
    _assert_healthy_rounded_inset(inset, initial_area)


@pytest.mark.parametrize("inset", ["xy", "yz", "busy_3d"], indirect=True)
def test_moving_the_rounded_face_out_of_plane_cannot_resurrect_the_invisible_corner(inset):
    viewport, _point, normal = inset
    initial_area = _area(viewport.scene.mesh)
    _round(inset)
    rounded = _assert_healthy_rounded_inset(inset, initial_area)
    viewport.history.execute(MoveVerticesCommand(rounded.vertices, normal))
    assert viewport.history.last_error is None
    _assert_no_old_corner(inset)
    _assert_real_boundaries(viewport.scene.mesh)
    assert viewport.history.undo()
    _assert_healthy_rounded_inset(inset, initial_area)
    assert viewport.history.redo()
    _assert_no_old_corner(inset)
    _assert_real_boundaries(viewport.scene.mesh)


def test_alt_rounding_keeps_the_corner_stubs_and_fills_every_region(inset):
    viewport, point, _normal = inset
    initial_area = _area(viewport.scene.mesh)
    _round(inset, Qt.AltModifier)
    assert _area(viewport.scene.mesh) == pytest.approx(initial_area, abs=1e-4)
    corner = viewport.scene.mesh.vertex_at(point(V(8, 2, 0)))
    assert corner is not None and len(corner.edges) == 2
    _assert_real_boundaries(viewport.scene.mesh)


@pytest.mark.parametrize("reverse_host", [False, True])
@pytest.mark.parametrize("paint_host", [False, True])
@pytest.mark.parametrize("inset", ["busy_3d"], indirect=True)
def test_surrounding_face_keeps_its_own_paint_and_orientation(
    inset, reverse_host, paint_host
):
    viewport, _point, _normal = inset
    mesh = viewport.scene.mesh
    host = next(face for face in mesh.faces if face.hole_loops)
    inner = next(face for face in mesh.faces if not face.hole_loops)
    inner.attrs = {"color": (0.2, 0.4, 0.6), "mat": "Inset"}
    host.attrs = {"color": (0.7, 0.3, 0.2), "mat": "Surrounding"} if paint_host else {}
    if reverse_host:
        host.loop.reverse()
        for hole in host.hole_loops:
            hole.reverse()
    host_normal, host_attrs, inner_attrs = host.normal(), dict(host.attrs), dict(inner.attrs)
    area = _area(mesh)
    _round(inset)
    rounded = _assert_healthy_rounded_inset(inset, area)
    surrounding = next(face for face in mesh.faces if face.hole_loops)
    assert V.dotProduct(surrounding.normal(), host_normal) > 0.999
    assert surrounding.attrs == host_attrs
    assert rounded.attrs == inner_attrs
    assert viewport.history.undo()
    assert host in mesh.faces and inner in mesh.faces
    assert host.attrs == host_attrs and inner.attrs == inner_attrs
    assert viewport.history.redo()
    surrounding = next(face for face in mesh.faces if face.hole_loops)
    assert surrounding.attrs == host_attrs
    assert V.dotProduct(surrounding.normal(), host_normal) > 0.999


@pytest.mark.parametrize("inset", ["busy_3d"], indirect=True)
def test_rounding_does_not_fill_another_existing_hole_on_the_same_plane(inset):
    viewport, _point, _normal = inset
    mesh = viewport.scene.mesh
    host = next(face for face in mesh.faces if face.hole_loops)
    empty_hole = [V(0.3, 0.3, 0), V(0.3, 1.3, 0),
                  V(1.3, 1.3, 0), V(1.3, 0.3, 0)]
    hole_vertices = set(mesh.add_hole(host, empty_hole))
    area = _area(mesh)
    _round(inset)
    assert _area(mesh) == pytest.approx(area, abs=1e-4)
    _assert_real_boundaries(mesh)
    _assert_no_old_corner(inset)
    assert any(set(hole) == hole_vertices
               for face in mesh.faces for hole in face.hole_loops)

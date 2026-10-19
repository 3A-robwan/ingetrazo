# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 IngeTrazo contributors.
"""Erase only selected segments of a closed outline drawn on an existing face.

An inner face and its surrounding ring share the entire closed outline. A
coplanar merge must heal their surface without erasing unselected segments.
Those segments remain as ordinary loose edges until the outline closes again.
"""
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QVector3D as V

from core.group import Group
from core.history import EraseSelectionCommand, History
from core.scene import Scene
from tools.base import ToolContext
from tools.line import LineTool
from tools.select import SelectTool


class _View:
    def __init__(self):
        self.scene = Scene()
        self.history = History(self.scene)
        self.picked_edge = None

    def update(self):
        pass

    def pick_group(self, *_):
        return None

    def pick_edge(self, *_):
        return self.picked_edge


def _ctx(view, point, modifiers=Qt.NoModifier):
    return ToolContext(view, point, QPointF(point.x() * 20, point.y() * 20),
                       modifiers, SimpleNamespace(kind="none"))


def _point(x, y, plane="xy"):
    if plane == "yz":
        return V(0, x, y)
    if plane == "tilted":
        # Unit orthogonal plane axes: distances and areas stay unchanged.
        return V(x * .6, y, x * .8)
    return V(x, y, 0)


def _corners(plane, low=0, high=10):
    return [_point(low, low, plane), _point(high, low, plane),
            _point(high, high, plane), _point(low, high, plane)]


def _draw_loop(view, corners):
    tool = LineTool()
    for p in [*corners, corners[0]]:
        tool.on_click(_ctx(view, p))
        assert view.history.last_error is None


def _edge(mesh, a, b):
    va, vb = mesh.vertex_at(a), mesh.vertex_at(b)
    return mesh.find_edge(va, vb) if va is not None and vb is not None else None


def _outlined_face(plane="xy", reverse=False, view=None):
    view = view or _View()
    mesh = view.scene.mesh
    outer = _corners(plane)
    if reverse:
        outer.reverse()
    host = mesh.add_face(outer)
    host.attrs = {"color": "#cc8844", "back": {"color": "#336699"}}
    normal = host.normal()
    inner = _corners(plane, 2, 8)
    _draw_loop(view, inner)
    edges = [_edge(mesh, inner[i], inner[(i + 1) % 4]) for i in range(4)]
    assert len(mesh.faces) == 2 and len(mesh.edges) == 8
    assert all(e is not None and len(e.faces) == 2 for e in edges)
    return view, inner, edges, normal


def _assert_healed(mesh, normal, attrs):
    assert len(mesh.faces) == 1
    face = mesh.faces[0]
    assert face.area() == pytest.approx(100, abs=1e-4)
    assert not face.holes
    assert V.dotProduct(face.normal(), normal) > .999
    assert face.attrs == attrs


@pytest.mark.parametrize("plane", ["xy", "yz", "tilted"])
@pytest.mark.parametrize("reverse", [False, True])
def test_line_outline_select_one_segment_then_delete_preserves_the_other_three(
    plane, reverse
):
    view, points, edges, normal = _outlined_face(plane, reverse)
    mesh = view.scene.mesh
    before = set(mesh.edges)
    # A merge inherits paint from the dominant host, not the inner fragment.
    attrs = dict(max(mesh.faces, key=lambda f: f.area()).attrs)
    view.picked_edge = edges[0]
    select = SelectTool()
    select.on_click(_ctx(view, (points[0] + points[1]) / 2))
    assert view.scene.selection == {edges[0]}
    assert select.on_key(view, Qt.Key_Delete, Qt.NoModifier)
    assert view.history.last_error is None
    assert set(mesh.edges) == before - {edges[0]}
    assert all(edge in mesh.edges and not edge.faces for edge in edges[1:])
    _assert_healed(mesh, normal, attrs)


@pytest.mark.parametrize("selected", [(0,), (0, 1), (0, 2), (0, 1, 2, 3)],
                         ids=["single", "adjacent", "opposite", "whole"])
def test_multiple_selected_outline_segments_leave_every_unselected_edge(selected):
    view, _, edges, normal = _outlined_face()
    mesh = view.scene.mesh
    attrs = dict(max(mesh.faces, key=lambda f: f.area()).attrs)
    before = set(mesh.edges)
    chosen = {edges[i] for i in selected}
    view.history.execute(EraseSelectionCommand(chosen))
    assert view.history.last_error is None
    assert set(mesh.edges) == before - chosen
    assert len(mesh.edges) == 8 - len(chosen)
    _assert_healed(mesh, normal, attrs)


def test_partial_erase_undo_redo_restores_edge_objects_and_face_attributes():
    view, _, edges, normal = _outlined_face()
    mesh = view.scene.mesh
    old_edges, old_faces = set(mesh.edges), set(mesh.faces)
    for i, face in enumerate(mesh.faces):
        face.attrs["part"] = f"region-{i}"
    attrs = {face: dict(face.attrs) for face in mesh.faces}
    before_history = len(view.history.undo_stack)
    view.history.execute(EraseSelectionCommand([edges[0]]))
    assert set(mesh.edges) == old_edges - {edges[0]}
    assert len(view.history.undo_stack) == before_history + 1
    assert view.history.undo()
    assert set(mesh.edges) == old_edges
    assert set(mesh.faces) == old_faces
    assert all(face.attrs == attrs[face] for face in old_faces)
    assert all(len(edge.faces) == 2 for edge in edges)
    assert view.history.redo()
    assert set(mesh.edges) == old_edges - {edges[0]}
    assert all(not edge.faces for edge in edges[1:])
    assert len(mesh.faces) == 1
    assert V.dotProduct(mesh.faces[0].normal(), normal) > .999


def test_a_second_delete_removes_only_the_next_remaining_segment():
    view, _, edges, _ = _outlined_face()
    mesh = view.scene.mesh
    before = set(mesh.edges)
    view.history.execute(EraseSelectionCommand([edges[0]]))
    assert edges[1] in mesh.edges
    view.history.execute(EraseSelectionCommand([edges[1]]))
    assert view.history.last_error is None
    assert set(mesh.edges) == before - {edges[0], edges[1]}
    assert len(mesh.faces) == 1 and mesh.faces[0].area() == pytest.approx(100)
    assert view.history.undo()
    assert set(mesh.edges) == before - {edges[0]}
    assert view.history.redo()
    assert set(mesh.edges) == before - {edges[0], edges[1]}


def test_drawing_back_the_missing_segment_closes_the_inner_face_again():
    view, points, edges, normal = _outlined_face()
    mesh = view.scene.mesh
    view.history.execute(EraseSelectionCommand([edges[0]]))
    survivors = edges[1:]
    assert all(edge in mesh.edges for edge in survivors)
    line = LineTool()
    line.on_click(_ctx(view, points[0]))
    line.on_click(_ctx(view, points[1]))
    assert view.history.last_error is None
    assert len(mesh.edges) == 8 and len(mesh.faces) == 2
    assert all(edge in mesh.edges and len(edge.faces) == 2 for edge in survivors)
    assert all(V.dotProduct(face.normal(), normal) > .999 for face in mesh.faces)


def test_erasing_inside_an_open_group_does_not_change_the_loose_mesh():
    view = _View()
    outside = view.scene.mesh.add_edge(V(-3, -3, 0), V(-1, -3, 0))
    group = Group(name="Edited outline")
    view.scene.groups.append(group)
    view.scene.begin_group_edit(group)
    view, _, edges, normal = _outlined_face(view=view)
    mesh = group.mesh
    attrs = dict(max(mesh.faces, key=lambda f: f.area()).attrs)
    view.history.execute(EraseSelectionCommand([edges[0]]))
    assert view.history.last_error is None
    assert view.scene.mesh is mesh and view.scene.edit_group is group
    assert view.scene.loose_mesh.edges == [outside]
    assert len(mesh.edges) == 7
    _assert_healed(mesh, normal, attrs)
    assert view.history.undo()
    assert len(mesh.edges) == 8
    assert view.scene.loose_mesh.edges == [outside]


def test_erasing_an_outline_leaves_other_subdivisions_and_3d_faces_untouched():
    view, _, edges, _ = _outlined_face()
    mesh = view.scene.mesh
    second = [_point(x, y) for x, y in [(0.5, 4), (1.5, 4), (1.5, 6), (.5, 6)]]
    _draw_loop(view, second)
    other_edges = {_edge(mesh, second[i], second[(i + 1) % 4]) for i in range(4)}
    wall = mesh.add_face([V(20, 0, 0), V(20, 3, 0), V(20, 3, 2), V(20, 0, 2)])
    wall.attrs = {"color": "#654321"}
    wall_edges = {edge for edge in mesh.edges if wall in edge.faces}
    all_edges = set(mesh.edges)
    view.history.execute(EraseSelectionCommand([edges[0]]))
    assert view.history.last_error is None
    assert set(mesh.edges) == all_edges - {edges[0]}
    assert other_edges <= set(mesh.edges) and wall_edges <= set(mesh.edges)
    assert wall in mesh.faces and wall.attrs == {"color": "#654321"}
    assert all(len(edge.faces) == 2 for edge in other_edges)


def test_a_closed_outline_on_empty_workplane_loses_its_face_but_only_one_edge():
    view = _View()
    points = _corners("xy", 2, 8)
    _draw_loop(view, points)
    mesh = view.scene.mesh
    assert len(mesh.faces) == 1
    before = set(mesh.edges)
    edge = _edge(mesh, points[0], points[1])
    view.history.execute(EraseSelectionCommand([edge]))
    assert view.history.last_error is None
    assert mesh.faces == []
    assert set(mesh.edges) == before - {edge}
    assert view.history.undo()
    assert len(mesh.faces) == 1 and set(mesh.edges) == before


def test_mesh_default_region_merge_still_removes_all_shared_seams():
    view, _, edges, normal = _outlined_face()
    mesh = view.scene.mesh
    merged = mesh.dissolve_coplanar_region(list(mesh.faces))
    assert merged is not None
    assert len(mesh.edges) == 4
    assert all(edge not in mesh.edges for edge in edges)
    assert len(mesh.faces) == 1
    assert V.dotProduct(merged.normal(), normal) > .999

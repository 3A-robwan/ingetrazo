# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Numeric corrections replace a finished shape, keeping its original frame."""
from __future__ import annotations

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QVector3D

from core.group import Group
from core.history import AddEdgeCommand, History
from core.scene import Scene
from tools.base import ToolContext
from tools.circle import CircleTool, PolygonTool
from tools.rectangle import RectangleTool
from tools.rotated_rectangle import RotatedRectangleTool


def V(x, y, z=0.0):
    return QVector3D(float(x), float(y), float(z))


class _VP:
    def __init__(self):
        self.scene = Scene()
        self.history = History(self.scene)

    def update(self):
        pass

    def flash_status(self, *args, **kwargs):
        pass

    def pick_face_any(self, *args):
        return None, None


def _ctx(vp, point):
    return ToolContext(viewport=vp, world=point, screen=QPointF(),
                       modifiers=Qt.NoModifier, snap=None)


def _geometry(scene):
    return scene.mesh.capture_state()


def _points(scene):
    return [v.position for v in scene.mesh.vertices if v.edges]


def _keys(points):
    return {tuple(round(c, 5) for c in p.toTuple()) for p in points}


def _rectangle(vp, *, typed=False, centered=False):
    tool = RectangleTool()
    tool.on_activate(vp)
    tool._from_center = centered
    origin, far = V(3, 4, 5), V(-1, 7, 5)
    tool.work_plane = (origin, V(0, 0, 1))
    tool.on_click(_ctx(vp, origin))
    tool.on_hover(_ctx(vp, far))
    if typed:
        assert tool.on_value(vp, (4.0, 3.0))
    else:
        tool.on_click(_ctx(vp, far))
    return tool


def _rotated(vp, *, typed=False):
    tool = RotatedRectangleTool()
    tool.on_activate(vp)
    origin, base = V(1, 2, 3), V(3, 4, 3)
    tool.on_click(_ctx(vp, origin))
    tool.on_click(_ctx(vp, base))
    far = base + V(0, 0, 2)
    tool.on_hover(_ctx(vp, far))
    if typed:
        assert tool.on_value(vp, (2.0, 90.0))
    else:
        tool.on_click(_ctx(vp, far))
    return tool


def _radial(vp, *, cls=CircleTool, typed=False):
    tool = cls()
    tool.on_activate(vp)
    origin, rim = V(1, 2, 3), V(4, 2, 3)
    tool.work_plane = (origin, V(0, 1, 0))
    tool.on_click(_ctx(vp, origin))
    tool.on_hover(_ctx(vp, rim))
    if typed:
        assert tool.on_value(vp, 3.0)
    else:
        tool.on_click(_ctx(vp, rim))
    return tool


@pytest.mark.parametrize("typed", [False, True], ids=["click", "enter"])
@pytest.mark.parametrize("centered", [False, True], ids=["corner", "center"])
def test_rectangle_retype_keeps_anchor_quadrant_and_one_undo(typed, centered):
    vp = _VP()
    tool = _rectangle(vp, typed=typed, centered=centered)
    # Hovering elsewhere after the commit must not change its saved frame.
    tool.on_hover(_ctx(vp, V(100, -100, 20)))
    assert tool.on_value(vp, (6.0, 2.0))
    assert tool.on_value(vp, (8.0, 4.0))
    if centered:
        expected = [V(7, 2, 5), V(-1, 2, 5), V(-1, 6, 5), V(7, 6, 5)]
    else:
        expected = [V(3, 4, 5), V(-5, 4, 5), V(-5, 8, 5), V(3, 8, 5)]
    assert _keys(_points(vp.scene)) == _keys(expected)
    assert len(vp.history.undo_stack) == 1
    assert vp.history.undo()
    assert not vp.scene.mesh.edges and not vp.scene.mesh.faces
    assert vp.history.redo()
    assert _keys(_points(vp.scene)) == _keys(expected)


def test_rectangle_retype_preserves_a_tilted_plane():
    vp = _VP()
    tool = RectangleTool()
    origin, normal = V(1, 2, 3), V(0, 1, 1).normalized()
    tool.work_plane = (origin, normal)
    tool.start_point = origin
    u, v = tool._axes()
    tool.hover_point = origin - u * 4 + v * 3
    assert tool.on_value(vp, (4.0, 3.0))
    assert tool.on_value(vp, (2.0, 5.0))
    expected = [origin, origin - u * 2, origin - u * 2 + v * 5, origin + v * 5]
    assert _keys(_points(vp.scene)) == _keys(expected)


@pytest.mark.parametrize("typed", [False, True], ids=["click", "enter"])
def test_rotated_retype_keeps_base_and_changes_width_and_angle(typed):
    vp = _VP()
    tool = _rotated(vp, typed=typed)
    tool.on_hover(_ctx(vp, V(100, -100, 20)))
    assert tool.on_value(vp, 4.0)
    assert _keys(_points(vp.scene)) == _keys(
        [V(1, 2, 3), V(3, 4, 3), V(3, 4, 7), V(1, 2, 7)])
    assert tool.on_value(vp, (2.0, 0.0))
    off = V(-1, 1).normalized() * 2
    expected = [V(1, 2, 3), V(3, 4, 3), V(3, 4, 3) + off, V(1, 2, 3) + off]
    assert _keys(_points(vp.scene)) == _keys(expected)
    assert len(vp.history.undo_stack) == 1
    assert vp.history.undo()
    assert not vp.scene.mesh.edges


def test_rotated_retype_can_change_both_dimensions_with_mm_angle(monkeypatch):
    import core.units as units
    vp = _VP()
    tool = _rotated(vp)
    monkeypatch.setattr(units, "bare_number_scale", lambda: 0.001)
    # The parser has already converted 6000;4000;90 in an mm document.
    assert tool.on_value(vp, (6.0, 4.0, 0.09))
    origin = V(1, 2, 3)
    base = origin + V(1, 1).normalized() * 6
    assert _keys(_points(vp.scene)) == _keys(
        [origin, base, base + V(0, 0, 4), origin + V(0, 0, 4)])


@pytest.mark.parametrize("cls", [CircleTool, PolygonTool])
@pytest.mark.parametrize("typed", [False, True], ids=["click", "enter"])
def test_radial_radius_and_side_corrections_preserve_plane_and_one_undo(cls, typed):
    vp = _VP()
    tool = _radial(vp, cls=cls, typed=typed)
    assert not tool.value_is_unitless(), "a hot idle circle still expects a radius"
    assert tool.vcb_caption() == "Radius"
    tool.on_hover(_ctx(vp, V(100, -100, 20)))
    assert tool.on_value(vp, 2.0)
    assert tool.on_segments_value(vp, 12)
    assert tool.on_segments_value(vp, 8)
    pts = _points(vp.scene)
    assert len(vp.scene.mesh.edges) == 8
    assert all(abs(p.y() - 2) < 1e-6 for p in pts)
    assert all(abs((p - V(1, 2, 3)).length() - 2) < 1e-5 for p in pts)
    assert (4.0, 2.0, 3.0) not in _keys(pts)
    assert (3.0, 2.0, 3.0) in _keys(pts), "the original first-vertex direction stays"
    assert len(vp.history.undo_stack) == 1
    assert vp.history.undo()
    assert not vp.scene.mesh.edges and not vp.scene.mesh.faces
    assert vp.history.redo()
    assert len(vp.scene.mesh.edges) == 8


_FACTORIES = [_rectangle, _rotated, _radial]


@pytest.mark.parametrize("make", _FACTORIES)
@pytest.mark.parametrize("boundary", ["cancel", "deactivate", "new-click", "undo-redo",
                                      "other-command", "context-round-trip"])
def test_shape_retype_window_ends_at_operation_boundaries(make, boundary):
    vp = _VP()
    tool = make(vp)
    if boundary == "cancel":
        tool.on_cancel(vp)
    elif boundary == "deactivate":
        tool.on_deactivate(vp)
        tool.on_activate(vp)
    elif boundary == "new-click":
        tool.on_click(_ctx(vp, V(20, 20, 20)))
        tool.on_cancel(vp)
    elif boundary == "undo-redo":
        vp.history.undo()
        vp.history.redo()
    elif boundary == "other-command":
        vp.history.execute(AddEdgeCommand(V(100, 100), V(101, 100)))
        vp.history.undo()
    else:
        group = Group(name="Other context")
        vp.scene.groups.append(group)
        vp.scene.begin_group_edit(group)
        vp.scene.end_group_edit()
    before = _geometry(vp.scene)
    tool.on_value(vp, (7.0, 5.0) if make is _rectangle else 7.0)
    assert _geometry(vp.scene) == before
    if make is _radial:
        assert tool.value_is_unitless()


@pytest.mark.parametrize("make", _FACTORIES)
@pytest.mark.parametrize("bad", [0.0, float("nan"), float("inf"), 1e100])
def test_invalid_correction_preserves_shape_and_allows_retry(make, bad):
    vp = _VP()
    tool = make(vp)
    before = _geometry(vp.scene)
    value = (bad, 2.0) if make is _rectangle else bad
    assert tool.on_value(vp, value) is False
    assert _geometry(vp.scene) == before
    assert len(vp.history.undo_stack) == 1
    assert tool.on_value(vp, (6.0, 2.0) if make is _rectangle else 2.0)
    assert len(vp.history.undo_stack) == 1


@pytest.mark.parametrize("make,module", [(_rectangle, "tools.rectangle"),
                                         (_rotated, "tools.rotated_rectangle"),
                                         (_radial, "tools.circle")])
def test_failed_rebuild_preserves_shape_and_allows_retry(make, module, monkeypatch):
    import importlib
    vp = _VP()
    tool = make(vp)
    before = _geometry(vp.scene)
    imported = importlib.import_module(module)
    original = imported.build_add_edges

    def fail(*args, **kwargs):
        raise RuntimeError("cannot build replacement")

    monkeypatch.setattr(imported, "build_add_edges", fail)
    value = (6.0, 2.0) if make is _rectangle else 2.0
    assert tool.on_value(vp, value) is False
    assert _geometry(vp.scene) == before
    assert len(vp.history.undo_stack) == 1
    monkeypatch.setattr(imported, "build_add_edges", original)
    assert tool.on_value(vp, value)
    assert len(vp.history.undo_stack) == 1


@pytest.mark.parametrize("make", _FACTORIES)
def test_shape_correction_stays_inside_the_open_group(make):
    vp = _VP()
    outside = vp.scene.mesh.add_edge(V(-10, -10), V(-9, -10))
    group = Group(name="Edited")
    vp.scene.groups.append(group)
    vp.scene.begin_group_edit(group)
    tool = make(vp)
    assert tool.on_value(vp, (6.0, 2.0) if make is _rectangle else 2.0)
    assert vp.scene.edit_group is group
    assert vp.scene.mesh is group.mesh
    assert vp.scene.loose_mesh.edges == [outside]
    assert len(vp.history.undo_stack) == 1
    assert vp.history.undo()
    assert not group.mesh.edges
    assert vp.scene.loose_mesh.edges == [outside]


@pytest.mark.parametrize("cls", [CircleTool, PolygonTool])
def test_invalid_or_failed_side_correction_preserves_radius_and_sides(cls, monkeypatch):
    import tools.circle as circle
    vp = _VP()
    tool = _radial(vp, cls=cls)
    before, sides = _geometry(vp.scene), tool.sides
    assert tool.on_segments_value(vp, 2) is False
    assert tool.on_segments_value(vp, float("nan")) is False
    assert _geometry(vp.scene) == before and tool.sides == sides
    build = circle.build_add_edges

    def fail(*args, **kwargs):
        raise RuntimeError("cannot resample")

    monkeypatch.setattr(circle, "build_add_edges", fail)
    assert tool.on_segments_value(vp, 8) is False
    assert _geometry(vp.scene) == before and tool.sides == sides
    monkeypatch.setattr(circle, "build_add_edges", build)
    assert tool.on_segments_value(vp, 8)
    assert len(vp.scene.mesh.edges) == 8 and tool.sides == 8


@pytest.mark.parametrize("square", [False, True])
def test_rectangle_keeps_its_single_side_or_square_entry_after_commit(square):
    vp = _VP()
    tool = RectangleTool()
    tool.on_click(_ctx(vp, V(0, 0)))
    tool.on_hover(_ctx(vp, V(0.5, 2)))
    tool.on_hover(_ctx(vp, V(3, 2)))
    tool._arrow_square_lock = square
    tool.on_click(_ctx(vp, V(3, 2)))
    assert tool.on_value(vp, 4.0)
    far = V(4, 4) if square else V(4, 2)
    assert _keys(_points(vp.scene)) == _keys([V(0, 0), V(far.x(), 0), far, V(0, far.y())])

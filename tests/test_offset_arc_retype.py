# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Retyping changes the finished result, including topology, as one undo step."""
from __future__ import annotations

import math

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QVector3D as V

from core.group import Group
from core.guide import Guide
from core.history import AddGuideCommand, History
from core.scene import Scene
from tools.arc import ArcTool, CenterArcTool, PieTool, ThreePointArcTool
from tools.base import ToolContext
from tools.offset import OffsetTool


class _Viewport:
    def __init__(self):
        self.scene = Scene()
        self.history = History(self.scene)

    def update(self):
        pass

    def set_hover(self, *_):
        pass

    def flash_status(self, *_args, **_kwargs):
        pass


def _ctx(vp, point):
    return ToolContext(viewport=vp, world=V(point), screen=QPointF(0, 0),
                       modifiers=Qt.NoModifier, snap=None)


def _signature(mesh):
    return sorted(tuple(sorted((tuple(round(c, 5) for c in (e.a.x(), e.a.y(), e.a.z())),
                                tuple(round(c, 5) for c in (e.b.x(), e.b.y(), e.b.z())))))
                  for e in mesh.edges)


def _offset(vp, chain=False):
    tool = OffsetTool()
    if chain:
        loop = [V(0, 0, 0), V(0, 4, 0), V(0, 4, 4)]
        for a, b in zip(loop, loop[1:]):
            vp.scene.mesh.add_edge(a, b)
        tool._chain, tool._closed = True, False
        tool._normal = V(1, 0, 0)
    else:
        loop = [V(0, 0, 0), V(6, 0, 0), V(6, 4, 0), V(0, 4, 0)]
        face = vp.scene.mesh.add_face(loop)
        face.attrs["mat"] = "Paint"
        tool.base_face = face
        tool._normal = face.normal()
    tool._loop = [V(p) for p in loop]
    tool.distance = 0.25
    before = _signature(vp.scene.mesh)
    tool._commit(vp)
    return tool, before


def _arc(vp, cls, vertical=False):
    tool = cls()
    tool.on_activate(vp)
    tool.segments = 6
    points = ([V(0, 0, 0), V(4, 0, 0), V(2, 1, 0)] if cls is ArcTool else
              [V(0, 0, 0), V(2, 1, 0), V(4, 0, 0)] if cls is ThreePointArcTool else
              [V(0, 0, 0), V(2, 0, 0), V(0, 2, 0)])
    if vertical:
        points = [V(p.x(), 3, p.y()) for p in points]
    for index, point in enumerate(points):
        if index and vertical:
            tool.work_plane = (V(0, 3, 0), V(0, -1, 0))
        tool.on_hover(_ctx(vp, point))
        tool.on_click(_ctx(vp, point))
    return tool


@pytest.mark.parametrize("chain", [False, True], ids=["painted-face", "vertical-chain"])
def test_offset_retypes_the_original_outline_and_one_undo_restores_it(chain):
    vp = _Viewport()
    tool, before = _offset(vp, chain)
    assert tool.on_value(vp, 0.5)
    assert tool.on_value(vp, 1.0)
    assert len(vp.history.undo_stack) == 1
    if chain:
        assert all(abs(v.position.x()) < 1e-6 for v in vp.scene.mesh.vertices)
        positive = _signature(vp.scene.mesh)
        assert tool.on_value(vp, -0.5)
        assert _signature(vp.scene.mesh) != positive
        assert len(vp.scene.mesh.edges) == 4
    else:
        ring = next(f for f in vp.scene.mesh.faces if f.holes)
        assert min(p.x() for p in ring.holes[0]) == pytest.approx(1.0)
        assert all(f.attrs.get("mat") == "Paint" for f in vp.scene.mesh.faces)
    result = _signature(vp.scene.mesh)
    assert vp.history.undo()
    assert _signature(vp.scene.mesh) == before
    assert vp.history.redo()
    assert _signature(vp.scene.mesh) == result


@pytest.mark.parametrize("cls", [ArcTool, ThreePointArcTool, CenterArcTool, PieTool])
def test_arc_size_and_segments_retype_finished_geometry_in_its_plane(cls):
    vp = _Viewport()
    tool = _arc(vp, cls, vertical=True)
    original = _signature(vp.scene.mesh)
    value = 1.5 if cls is ArcTool else 3.0 if cls is ThreePointArcTool else 45.0
    assert tool.on_value(vp, value)
    assert _signature(vp.scene.mesh) != original
    assert tool.on_radius_value(vp, 3.5)
    assert tool.on_segments_value(vp, 12)
    assert len(vp.scene.mesh.edges) == 12 + (2 if cls is PieTool else 0)
    assert all(v.position.y() == pytest.approx(3.0) for v in vp.scene.mesh.vertices)
    assert len(vp.history.undo_stack) == 1
    result = _signature(vp.scene.mesh)
    assert vp.history.undo()
    assert not vp.scene.mesh.edges and not vp.scene.mesh.faces
    assert vp.history.redo()
    assert _signature(vp.scene.mesh) == result


def test_center_arc_and_pie_retain_center_start_direction_and_sweep():
    for cls in (CenterArcTool, PieTool):
        vp = _Viewport()
        tool = _arc(vp, cls)
        assert tool.on_value(vp, 60.0)
        assert tool.on_radius_value(vp, 3.0)
        points = [v.position for v in vp.scene.mesh.vertices if v.position.length() > 1e-5]
        assert all(p.length() == pytest.approx(3.0, abs=1e-5) for p in points)
        assert max(p.y() for p in points) == pytest.approx(3 * math.sin(math.pi / 3), abs=1e-5)
        assert min(p.x() for p in points) == pytest.approx(1.5, abs=1e-5)


def test_an_impossible_offset_restores_the_previous_result_and_can_be_corrected():
    vp = _Viewport()
    tool, before = _offset(vp)
    result = _signature(vp.scene.mesh)
    assert tool.on_value(vp, 10.0) is False       # the inner region would disappear
    assert _signature(vp.scene.mesh) == result
    assert tool.on_value(vp, 0.75)
    assert len(vp.history.undo_stack) == 1
    assert vp.history.undo()
    assert _signature(vp.scene.mesh) == before


def test_bulge_retyping_uses_the_original_side_and_keeps_both_endpoints():
    vp = _Viewport()
    tool = _arc(vp, ArcTool)
    assert tool.on_value(vp, -1.5)
    assert min(v.position.y() for v in vp.scene.mesh.vertices) == pytest.approx(-1.5)
    result = _signature(vp.scene.mesh)
    assert tool.on_value(vp, -1.5)
    assert _signature(vp.scene.mesh) == result
    assert tool.on_radius_value(vp, 3.0)
    assert min(v.position.y() for v in vp.scene.mesh.vertices) < -0.5
    assert max(v.position.y() for v in vp.scene.mesh.vertices) < 1e-5
    assert tool.on_value(vp, 2.0)
    assert max(v.position.y() for v in vp.scene.mesh.vertices) == pytest.approx(2.0)
    assert vp.scene.mesh.vertex_at(V(0, 0, 0)) is not None
    assert vp.scene.mesh.vertex_at(V(4, 0, 0)) is not None


def test_three_point_arc_radius_keeps_a_major_arc_instead_of_switching_sweeps():
    vp = _Viewport()
    tool = ThreePointArcTool()
    tool.segments = 24
    for point in (V(1, 0, 0), V(0, -1, 0), V(0, 1, 0)):
        tool.on_click(_ctx(vp, point))
    assert tool.on_value(vp, 2.0)
    assert sum(e.length() for e in vp.scene.mesh.edges) > 2 * math.pi
    assert vp.scene.mesh.vertex_at(V(1, 0, 0)) is not None
    assert vp.scene.mesh.vertex_at(V(0, 1, 0)) is not None
    assert len(vp.history.undo_stack) == 1


def test_arc_fillet_radius_retype_preserves_the_tangencies_and_corner_trim():
    vp = _Viewport()
    mesh = vp.scene.mesh
    mesh.add_face([V(0, 0, 0), V(4, 0, 0), V(4, 4, 0), V(0, 4, 0)])
    before = _signature(mesh)
    corner = mesh.vertex_at(V(4, 0, 0))
    tool = ArcTool()
    tool._viewport = vp
    tool._round_corner(vp, (corner, *list(corner.edges)), 0.5, Qt.NoModifier)
    assert tool.on_value(vp, 1.0)
    assert tool.on_segments_value(vp, 8)
    curved = [e for e in mesh.edges if e.curve is not None]
    assert len(curved) == 8
    corner = mesh.vertex_at(V(4, 0, 0))
    assert corner is None or not corner.edges
    assert all((p - V(3, 1, 0)).length() == pytest.approx(1.0, abs=1e-5)
               for edge in curved for p in (edge.a, edge.b))
    assert len(mesh.faces) == 1 and len(vp.history.undo_stack) == 1
    assert vp.history.undo()
    assert _signature(mesh) == before


@pytest.mark.parametrize("cls", [ArcTool, ThreePointArcTool, CenterArcTool, PieTool, OffsetTool])
@pytest.mark.parametrize("ending", ["cancel", "deactivate", "click", "undo-redo", "other",
                                    "context", "context-roundtrip"])
def test_retype_cannot_reach_a_finished_operation_after_window_closes(cls, ending):
    vp = _Viewport()
    tool = _offset(vp)[0] if cls is OffsetTool else _arc(vp, cls)
    if ending == "cancel":
        tool.on_cancel(vp)
    elif ending == "deactivate":
        tool.on_deactivate(vp)
    elif ending == "click":
        tool.on_click(_ctx(vp, V(10, 10, 0)))
    elif ending == "undo-redo":
        vp.history.undo()
        vp.history.redo()
    elif ending == "other":
        vp.history.execute(AddGuideCommand(Guide(V(10, 10, 0))))
    else:
        group = Group(name="Elsewhere")
        group.mesh.add_edge(V(20, 0, 0), V(21, 0, 0))
        vp.scene.groups.append(group)
        vp.scene.begin_group_edit(group)
        if ending == "context-roundtrip":
            vp.scene.end_group_edit()
    before = _signature(vp.scene.mesh)
    tool.on_value(vp, 8.0)
    assert _signature(vp.scene.mesh) == before


@pytest.mark.parametrize("cls", [ArcTool, ThreePointArcTool, CenterArcTool, PieTool, OffsetTool])
def test_invalid_retype_preserves_the_result_and_allows_a_valid_retry(cls):
    vp = _Viewport()
    tool = _offset(vp)[0] if cls is OffsetTool else _arc(vp, cls)
    before = _signature(vp.scene.mesh)
    assert tool.on_value(vp, 0.0) is False
    assert _signature(vp.scene.mesh) == before
    assert tool.on_value(vp, 0.5 if cls in (ArcTool, OffsetTool) else 3.0 if cls is ThreePointArcTool else 30.0)
    assert len(vp.history.undo_stack) == 1

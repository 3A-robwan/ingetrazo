# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Eraser hover and strokes only target the edge visible at the cursor."""
from __future__ import annotations

import math
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QVector3D as V

from core.group import Group
from core.mesh import Mesh
from core.scene import Scene
from tools.base import ToolContext
from tools.eraser import EraserTool
from tools.select import delete_selection_or_hover
from views.viewport import Viewport


@pytest.fixture(params=[False, True], ids=["orthographic", "perspective"])
def vp(request):
    view = Viewport()
    view.resize(1000, 700)
    view.camera.set_aspect(1000, 700)
    view.camera.target = V(0, 0, 1)
    view.camera.distance = 20
    view.camera.yaw = math.radians(-45)
    view.camera.pitch = math.radians(30)
    view.camera.perspective = request.param
    view.scene.display_style.face_mode = "shaded"
    view.flash_status = lambda *args, **kwargs: None
    yield view
    view.inference.reset()
    view.close()


def _box(mesh):
    for loop in (
        [V(-3, -3, 0), V(-3, 3, 0), V(3, 3, 0), V(3, -3, 0)],
        [V(-3, -3, 2), V(3, -3, 2), V(3, 3, 2), V(-3, 3, 2)],
        [V(-3, -3, 0), V(3, -3, 0), V(3, -3, 2), V(-3, -3, 2)],
        [V(3, -3, 0), V(3, 3, 0), V(3, 3, 2), V(3, -3, 2)],
        [V(3, 3, 0), V(-3, 3, 0), V(-3, 3, 2), V(3, 3, 2)],
        [V(-3, 3, 0), V(-3, -3, 0), V(-3, -3, 2), V(-3, 3, 2)],
    ):
        mesh.add_face(loop)


def _box_scene(view):
    _box(view.scene.mesh)
    view.scene.version += 1


def _context(view, world, modifiers=Qt.NoModifier):
    px = view._world_to_pixel(world)
    assert px is not None
    return ToolContext(viewport=view, world=world, screen=QPointF(*px),
                       modifiers=modifiers, snap=None)


def _edge_at(view, world):
    return view.pick_edge(*view._world_to_pixel(world))


def _keys(view):
    return {frozenset((tuple(e.a.toTuple()), tuple(e.b.toTuple())))
            for e in view.scene.mesh.edges}


def test_hover_click_and_delete_ignore_the_occluded_box_edge(vp):
    _box_scene(vp)
    ctx = _context(vp, V(-3, 3, 1))
    hidden = _edge_at(vp, ctx.world)
    assert hidden is not None and vp._is_occluded(ctx.world)
    before, faces = _keys(vp), set(vp.scene.mesh.faces)
    tool = EraserTool()

    tool.on_hover(ctx)
    assert vp._hover_entity is None
    assert not delete_selection_or_hover(vp)
    tool.on_click(ctx)
    assert not tool.marked
    tool.on_release(vp)

    assert _keys(vp) == before
    assert set(vp.scene.mesh.faces) == faces
    assert not vp.history.undo()


def test_drag_erases_only_visible_box_edge_in_one_undo_step(vp):
    _box_scene(vp)
    front = _context(vp, V(3, -3, 1))
    back = _context(vp, V(-3, 3, 1))
    visible, hidden = _edge_at(vp, front.world), _edge_at(vp, back.world)
    before = _keys(vp)
    tool = EraserTool()

    tool.on_click(front)
    tool.on_hover(back)
    assert tool.marked == {visible}
    tool.on_release(vp)
    assert hidden in vp.scene.mesh.edges
    assert len(vp.scene.mesh.edges) == 11
    assert len(vp.scene.mesh.faces) == 4
    after = _keys(vp)
    assert len(before - after) == 1
    assert vp.history.undo()
    assert _keys(vp) == before
    assert not vp.history.undo()
    assert vp.history.redo()
    assert _keys(vp) == after


def test_delete_after_visible_hover_and_cancelled_stroke(vp):
    _box_scene(vp)
    ctx = _context(vp, V(3, -3, 1))
    before = _keys(vp)
    tool = EraserTool()
    tool.on_click(ctx)
    assert tool.marked
    tool.on_cancel(vp)
    tool.on_release(vp)
    assert _keys(vp) == before
    assert not vp.history.undo()

    tool.on_hover(ctx)
    assert vp._hover_entity is _edge_at(vp, ctx.world)
    assert delete_selection_or_hover(vp)
    assert len(before - _keys(vp)) == 1
    assert vp.history.undo()
    assert _keys(vp) == before


def test_shift_drag_hides_only_visible_box_edge_and_undo_redo(vp):
    _box_scene(vp)
    front = _context(vp, V(3, -3, 1), Qt.ShiftModifier)
    back = _context(vp, V(-3, 3, 1), Qt.ShiftModifier)
    visible, hidden = _edge_at(vp, front.world), _edge_at(vp, back.world)
    before = _keys(vp)
    tool = EraserTool()

    tool.on_click(front)
    tool.on_hover(back)
    assert tool.marked == {visible}
    tool.on_release(vp)
    assert visible.hidden and not hidden.hidden
    assert _keys(vp) == before
    assert vp.history.undo()
    assert not visible.hidden and not hidden.hidden
    assert vp.history.redo()
    assert visible.hidden and not hidden.hidden


@pytest.mark.parametrize("style", ["xray", "wireframe"])
def test_transparent_styles_still_allow_erasing_the_back_edge(vp, style):
    _box_scene(vp)
    vp.scene.display_style.face_mode = style
    ctx = _context(vp, V(-3, 3, 1))
    hidden = _edge_at(vp, ctx.world)
    tool = EraserTool()
    tool.on_hover(ctx)
    assert vp._hover_entity is hidden
    tool.on_click(ctx)
    assert tool.marked == {hidden}
    tool.on_release(vp)
    assert hidden not in vp.scene.mesh.edges
    assert vp.history.undo()
    assert hidden in vp.scene.mesh.edges


def _partial_edge(view, *, grouped_lid=False):
    view.camera.set_view("top")
    view.camera.target = V(3, 3, 0)
    view.camera.distance = 14
    edge = view.scene.mesh.add_edge(V(0, 3, 0), V(6, 3, 0))
    mesh = Mesh() if grouped_lid else view.scene.mesh
    mesh.add_face([V(-1, -1, 1), V(3, -1, 1), V(3, 7, 1), V(-1, 7, 1)])
    group = Group(mesh, "Lid") if grouped_lid else None
    if group is not None:
        view.scene.groups.append(group)
    view.scene.version += 1
    return edge, group


def test_partial_edge_uses_the_visible_part_under_the_cursor(vp):
    edge, _ = _partial_edge(vp)
    tool = EraserTool()
    covered = _context(vp, V(1, 3, 0))
    exposed = _context(vp, V(5, 3, 0))
    assert _edge_at(vp, covered.world) is edge
    assert vp._is_occluded(covered.world)
    tool.on_hover(covered)
    assert vp._hover_entity is None
    tool.on_click(covered)
    assert not tool.marked
    tool.on_hover(exposed)
    assert tool.marked == {edge}
    tool.on_release(vp)
    assert edge not in vp.scene.mesh.edges
    assert vp.history.undo()
    assert edge in vp.scene.mesh.edges


def test_group_face_takes_stroke_before_a_loose_edge_behind_it(vp):
    edge, group = _partial_edge(vp, grouped_lid=True)
    tool = EraserTool()
    ctx = _context(vp, V(1, 3, 0))
    assert vp.pick_group(ctx.screen.x(), ctx.screen.y()) is group
    tool.on_hover(ctx)
    assert vp._hover_entity is None
    tool.on_click(ctx)
    assert tool.marked == {group}
    tool.on_release(vp)
    assert group not in vp.scene.groups
    assert edge in vp.scene.mesh.edges
    assert vp.history.undo()
    assert group in vp.scene.groups and edge in vp.scene.mesh.edges


def test_inside_group_keeps_the_back_edge_and_erases_the_visible_edge(vp):
    mesh = Mesh()
    _box(mesh)
    group = Group(mesh, "Box")
    vp.scene.groups.append(group)
    vp.scene.begin_group_edit(group)
    front = _context(vp, V(3, -3, 1))
    back = _context(vp, V(-3, 3, 1))
    visible, hidden = _edge_at(vp, front.world), _edge_at(vp, back.world)
    tool = EraserTool()
    tool.on_click(back)
    assert not tool.marked
    tool.on_hover(front)
    assert tool.marked == {visible}
    tool.on_release(vp)
    assert vp.scene.edit_group is group
    assert group in vp.scene.groups
    assert hidden in group.mesh.edges and visible not in group.mesh.edges
    assert vp.history.undo()
    assert visible in group.mesh.edges and hidden in group.mesh.edges
    vp.scene.end_group_edit()


@pytest.mark.parametrize("attribute", ["hidden", "soft"])
def test_hidden_geometry_setting_controls_hidden_and_soft_edge_targets(vp,
                                                                     attribute):
    vp.camera.set_view("top")
    vp.camera.target = V(0, 0, 0)
    edge = vp.scene.mesh.add_edge(V(-2, 0, 0), V(2, 0, 0))
    setattr(edge, attribute, True)
    vp.scene.version += 1
    ctx = _context(vp, V(0, 0, 0))
    tool = EraserTool()
    tool.on_hover(ctx)
    assert vp._hover_entity is None
    tool.on_click(ctx)
    assert not tool.marked
    tool.on_cancel(vp)

    vp.scene.show_hidden_geometry = True
    vp.scene.version += 1
    tool.on_hover(ctx)
    assert vp._hover_entity is edge
    tool.on_click(ctx)
    assert tool.marked == {edge}


def test_visible_curve_segment_still_marks_the_whole_contour(vp):
    mesh = vp.scene.mesh
    count = 12
    bottom = [V(2 * math.cos(2 * math.pi * i / count),
                2 * math.sin(2 * math.pi * i / count), 0)
              for i in range(count)]
    top = [point + V(0, 0, 3) for point in bottom]
    mesh.add_face(list(reversed(bottom)))
    mesh.add_face(top)
    for i in range(count):
        j = (i + 1) % count
        mesh.add_face([bottom[i], bottom[j], top[j], top[i]])
    mesh.tag_curve(bottom, closed=True)
    vp.scene.version += 1
    contour = set(mesh.curve_edges(mesh.find_edge(mesh.vertex_at(bottom[0]),
                                                mesh.vertex_at(bottom[1]))))
    visible = [e for e in contour if not vp._is_occluded((e.a + e.b) * 0.5)]
    covered = [e for e in contour if vp._is_occluded((e.a + e.b) * 0.5)]
    assert visible and covered
    ctx = _context(vp, (visible[0].a + visible[0].b) * 0.5)
    tool = EraserTool()
    tool.on_click(ctx)
    assert tool.marked == contour
    tool.on_release(vp)
    assert not contour.intersection(mesh.edges)
    assert vp.history.undo()
    assert contour.issubset(mesh.edges)


def test_old_viewport_stub_without_visible_picker_still_supports_eraser():
    scene = Scene()
    edge = scene.mesh.add_edge(V(0, 0, 0), V(1, 0, 0))
    view = SimpleNamespace(scene=scene, pick_edge=lambda *_: edge,
                           set_hover=lambda entity: setattr(view, "hover", entity),
                           update=lambda: None)
    ctx = ToolContext(viewport=view, world=V(0, 0, 0), screen=QPointF(0, 0),
                      modifiers=Qt.NoModifier, snap=None)
    tool = EraserTool()
    tool.on_hover(ctx)
    assert view.hover is edge
    tool.on_click(ctx)
    assert tool.marked == {edge}

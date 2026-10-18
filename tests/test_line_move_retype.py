# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Numeric corrections replace a committed Line/Move without stacking edits."""
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QVector3D as V

from core.group import Group
from core.history import AddEdgeCommand, History
from core.mesh import Mesh
from core.scene import Scene
from tools.base import ToolContext
from tools.line import LineTool
from tools.move import MoveTool


class View:
    def __init__(self):
        self.scene = Scene()
        self.history = History(self.scene)

    def update(self):
        pass

    def flash_status(self, *args):
        pass

    def pick_group(self, *args):
        return None

    pick_edge = pick_face = pick_group


def context(vp, x, y=0, z=0, close=False):
    return ToolContext(vp, V(x, y, z), QPointF(x * 20, y * 20),
                       Qt.NoModifier, SimpleNamespace(kind="close" if close else "none"))


def points(mesh):
    return sorted(tuple(round(c, 5) for c in v.position.toTuple()) for v in mesh.vertices)


def moving(copy=False, group=False):
    vp, tool = View(), MoveTool()
    mesh = Mesh() if group else vp.scene.mesh
    face = mesh.add_face([V(0, 0, 0), V(1, 0, 0), V(1, 1, 0), V(0, 1, 0)])
    if group:
        item = Group(mesh)
        vp.scene.groups.append(item)
    else:
        item = face
    vp.scene.select([item])
    original = points(mesh)
    tool.on_click(context(vp, 5, 2))  # a grab distinct from the origin
    if copy:
        tool.on_key(vp, Qt.Key_Control, Qt.NoModifier)
    tool.on_hover(context(vp, 7, 2))
    tool.on_click(context(vp, 7, 2))
    return vp, tool, mesh, original


@pytest.mark.parametrize("group", [False, True])
def test_move_scalar_and_delta_retype_use_the_original_grab_and_direction(group):
    vp, tool, mesh, original = moving(group=group)
    assert tool.on_value(vp, 4.0)
    assert min(p[0] for p in points(mesh)) == 4
    assert tool.on_value(vp, (0.0, 3.0, 1.0))
    assert min(p[0] for p in points(mesh)) == 0
    assert min(p[1] for p in points(mesh)) == 3
    assert min(p[2] for p in points(mesh)) == 1
    assert tool.on_value(vp, -2.0)
    assert min(p[0] for p in points(mesh)) == -2
    assert min(p[1] for p in points(mesh)) == 0
    assert len(vp.history.undo_stack) == 1
    assert vp.history.undo()
    assert points(mesh) == original


def test_copy_retype_and_array_spacing_replace_one_history_step():
    vp, tool, _, _ = moving(copy=True, group=True)
    assert tool.on_value(vp, 3.0)
    assert len(vp.scene.groups) == 2
    assert tool.on_array_value(vp, 3, "x")
    assert len(vp.scene.groups) == 4
    assert tool.on_value(vp, 4.0)
    xs = sorted(min(p[0] for p in points(g.mesh)) for g in vp.scene.groups)
    assert xs == [0, 4, 8, 12]
    assert tool.on_array_value(vp, 2, "/", step=10.0)
    xs = sorted(min(p[0] for p in points(g.mesh)) for g in vp.scene.groups)
    assert xs == [0, 5, 10]
    assert len(vp.history.undo_stack) == 1
    vp.history.undo()
    assert len(vp.scene.groups) == 1


@pytest.mark.parametrize("value", [0.0, float("nan"), float("inf"), (1.0, 2.0),
                                  (0.0, 0.0, 0.0), (float("inf"), 0.0, 0.0)])
def test_invalid_move_retype_preserves_geometry_and_can_retry(value):
    vp, tool, mesh, _ = moving()
    before = points(mesh)
    assert not tool.on_value(vp, value)
    assert points(mesh) == before
    assert len(vp.history.undo_stack) == 1
    assert tool.on_value(vp, 3.0)


@pytest.mark.parametrize("operation", ["undo_redo", "other_command", "context", "cancel",
                                       "deactivate", "content_change", "leave_return"])
def test_move_retype_cannot_reach_a_stale_operation(operation):
    vp, tool, mesh, _ = moving()
    if operation == "undo_redo":
        vp.history.undo()
        vp.history.redo()
    elif operation == "other_command":
        vp.history.execute(AddEdgeCommand(V(20, 0, 0), V(21, 0, 0)))
    elif operation == "context":
        vp.scene.edit_group = Group(Mesh())
    elif operation == "cancel":
        tool.on_cancel(vp)
    elif operation == "content_change":
        vp.scene.version += 1
    elif operation == "leave_return":
        group = Group(Mesh())
        vp.scene.groups.append(group)
        vp.scene.begin_group_edit(group)
        vp.scene.end_group_edit()
    else:
        tool.on_deactivate(vp)
        tool.on_activate(vp)
    before = points(mesh)
    assert not tool.on_value(vp, 8.0)
    assert points(mesh) == before


def test_move_builder_failure_keeps_the_old_move_and_allows_retry():
    vp, tool, mesh, _ = moving(copy=True)
    before = points(mesh)
    build = tool._last["build"]
    tool._last["build"] = lambda _: None
    assert not tool.on_value(vp, 5.0)
    assert points(mesh) == before
    assert len(vp.history.undo_stack) == 1
    tool._last["build"] = build
    assert tool.on_value(vp, 3.0)


def test_selection_only_changes_do_not_end_move_correction():
    vp, tool, mesh, _ = moving()
    vp.scene.select([])
    assert tool.on_value(vp, 4.0)
    assert min(p[0] for p in points(mesh)) == 4


def test_rejected_move_correction_restores_geometry_and_can_retry():
    vp, tool = View(), MoveTool()
    face = vp.scene.mesh.add_face([V(0, 0, 0), V(1, 0, 0), V(1, 1, 0), V(0, 1, 0)])
    vp.scene.mesh.add_face([V(4, 0, 0), V(5, 0, 0), V(5, 1, 0), V(4, 1, 0)])
    vp.scene.select([face])
    tool.on_click(context(vp, 0))
    tool.on_click(context(vp, 2))
    before = points(vp.scene.mesh)
    assert not tool.on_value(vp, 4.0)  # would drop one complete face on the other
    assert vp.history.last_rejected
    assert points(vp.scene.mesh) == before
    assert len(vp.history.undo_stack) == 1
    assert tool.on_value(vp, 1.0)


def line_segment():
    vp, tool = View(), LineTool()
    tool.on_click(context(vp, 0))
    tool.on_hover(context(vp, 2))
    tool.on_click(context(vp, 2))
    return vp, tool


def test_line_click_commit_then_repeated_numeric_correction_updates_chain_endpoint():
    vp, tool = line_segment()
    assert tool.on_value(vp, 4.0)
    assert points(vp.scene.mesh) == [(0, 0, 0), (4, 0, 0)]
    assert tool.start_point == V(4, 0, 0)
    assert tool.chain_first_point == V(0, 0, 0)
    assert tool.on_value(vp, (3.0, 2.0, 1.0))
    assert points(vp.scene.mesh) == [(0, 0, 0), (3, 2, 1)]
    assert tool.on_value(vp, -2.0)
    assert points(vp.scene.mesh) == [(-2, 0, 0), (0, 0, 0)]
    assert len(vp.history.undo_stack) == 1
    tool.on_undo(vp)
    assert not vp.scene.mesh.edges
    assert tool.start_point == V(0, 0, 0)


def test_line_typed_commit_can_be_corrected_without_drawing_an_extra_edge():
    vp, tool = View(), LineTool()
    tool.on_click(context(vp, 0))
    tool.on_hover(context(vp, 1))
    assert tool.on_value(vp, 2.0)
    assert tool.on_value(vp, 5.0)
    assert points(vp.scene.mesh) == [(0, 0, 0), (5, 0, 0)]
    assert len(vp.history.undo_stack) == 1


def test_moving_the_mouse_after_line_commit_draws_the_next_segment():
    vp, tool = line_segment()
    tool.on_hover(context(vp, 2, 1))
    assert tool.on_value(vp, 3.0)
    assert points(vp.scene.mesh) == [(0, 0, 0), (2, 0, 0), (2, 3, 0)]
    assert len(vp.history.undo_stack) == 2


def test_snap_refresh_at_the_same_pixel_does_not_end_line_correction():
    vp, tool = line_segment()
    refresh = context(vp, 2, 1)
    refresh.screen = QPointF(40, 0)  # same pointer, refreshed inference after the commit
    tool.on_hover(refresh)
    assert tool.on_value(vp, 3.0)
    assert points(vp.scene.mesh) == [(0, 0, 0), (3, 0, 0)]
    assert len(vp.history.undo_stack) == 1


def test_line_correction_replans_crossings_from_the_original_geometry():
    vp, tool = View(), LineTool()
    vp.scene.mesh.add_edge(V(2, -1, 0), V(2, 1, 0))
    tool.on_click(context(vp, 0))
    tool.on_click(context(vp, 4))
    assert len(vp.scene.mesh.edges) == 4  # both lines were split at the crossing
    assert tool.on_value(vp, 1.0)
    assert len(vp.scene.mesh.edges) == 2
    assert points(vp.scene.mesh) == [(0, 0, 0), (1, 0, 0), (2, -1, 0), (2, 1, 0)]


def test_simple_line_correction_undo_redo_leaves_no_old_endpoints():
    vp, tool = line_segment()
    assert tool.on_value(vp, 4.0)
    vp.history.undo()
    assert not points(vp.scene.mesh)
    vp.history.redo()
    assert points(vp.scene.mesh) == [(0, 0, 0), (4, 0, 0)]
    assert len(vp.scene.mesh.edges) == 1


def test_retyping_the_closing_line_removes_and_restores_its_face():
    vp, tool = View(), LineTool()
    for x, y, close in ((0, 0, False), (4, 0, False), (4, 3, False),
                        (0, 3, False), (0, 0, True)):
        tool.on_click(context(vp, x, y, close=close))
    assert len(vp.scene.mesh.faces) == 1 and tool.start_point is None
    assert tool.on_value(vp, 1.0)
    assert not vp.scene.mesh.faces
    assert tool.start_point == V(0, 2, 0)
    assert tool.chain_first_point == V(0, 0, 0)
    assert tool.chain_vertices == [V(0, 0, 0), V(4, 0, 0), V(4, 3, 0),
                                   V(0, 3, 0), V(0, 2, 0)]
    assert tool.on_value(vp, 3.0)
    assert len(vp.scene.mesh.faces) == 1 and tool.start_point is None
    assert len(vp.history.undo_stack) == 4
    vp.history.undo()
    assert not vp.scene.mesh.faces and len(vp.scene.mesh.edges) == 3


@pytest.mark.parametrize("value", [0.0, float("nan"), float("inf"), (1.0, 2.0),
                                  (0.0, 0.0, 0.0)])
def test_invalid_line_correction_preserves_the_edge_and_retry_window(value):
    vp, tool = line_segment()
    before = points(vp.scene.mesh)
    assert not tool.on_value(vp, value)
    assert points(vp.scene.mesh) == before
    assert tool.on_value(vp, 3.0)


def test_line_replanning_failure_restores_the_old_edge(monkeypatch):
    vp, tool = line_segment()
    before = points(vp.scene.mesh)
    builder = tool._commit_edge

    def fail(*args):
        raise ValueError("injected planner failure")

    monkeypatch.setattr(tool, "_commit_edge", fail)
    assert not tool.on_value(vp, 4.0)
    assert points(vp.scene.mesh) == before
    assert len(vp.history.undo_stack) == 1
    monkeypatch.setattr(tool, "_commit_edge", builder)
    assert tool.on_value(vp, 3.0)


@pytest.mark.parametrize("operation", ["undo_redo", "other_command", "context", "cancel",
                                       "deactivate", "content_change", "leave_return"])
def test_line_correction_cannot_replace_a_stale_edge(operation):
    vp, tool = line_segment()
    if operation == "undo_redo":
        vp.history.undo()
        vp.history.redo()
    elif operation == "other_command":
        vp.history.execute(AddEdgeCommand(V(20, 0, 0), V(21, 0, 0)))
    elif operation == "context":
        vp.scene.edit_group = Group(Mesh())
    elif operation == "cancel":
        tool.on_cancel(vp)
    elif operation == "content_change":
        vp.scene.version += 1
    elif operation == "leave_return":
        group = Group(Mesh())
        vp.scene.groups.append(group)
        vp.scene.begin_group_edit(group)
        vp.scene.end_group_edit()
    else:
        tool.on_deactivate(vp)
        tool.on_activate(vp)
    before = points(vp.scene.mesh)
    assert not tool.on_value(vp, 8.0)
    assert points(vp.scene.mesh) == before

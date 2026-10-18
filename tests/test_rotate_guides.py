# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Rotate construction guides with the same gestures as model geometry."""
import math

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QMatrix4x4, QVector3D as V

from core.group import Group
from core.guide import Guide
from core.history import AddGuideCommand, History
from core.mesh import Mesh
from core.scene import Scene
from core.section import SectionPlane
from tools.base import ToolContext
from tools.rotate import RotateTool


class View:
    def __init__(self):
        self.scene = Scene()
        self.history = History(self.scene)
        self.hits = {}

    def update(self):
        pass

    def flash_status(self, *args):
        pass

    def pick_group(self, *args):
        return self.hits.get("group")

    def pick_edge(self, *args):
        return self.hits.get("edge")

    def pick_face(self, *args):
        return self.hits.get("face")

    def pick_guide(self, *args):
        return self.hits.get("guide")

    def pick_section_plane(self, *args):
        return self.hits.get("section")


class FrozenView(View):
    """Viewport preview keeps the group's actual mesh frozen until commit."""

    def begin_groups_preview(self, groups):
        self.preview_groups = list(groups)

    def set_groups_preview_matrix(self, matrix):
        self.preview_matrix = QMatrix4x4(matrix)

    def end_groups_preview(self):
        self.preview_groups = []


def context(vp, x=0, y=0, z=0):
    return ToolContext(vp, V(x, y, z), QPointF(x * 20, y * 20),
                       Qt.NoModifier, None)


def near(actual, expected):
    assert (actual - expected).length() < 1e-5


def add_guide(vp, point=False):
    guide = (Guide(V(2, 0, 0), origin=V(1, 0, 0)) if point
             else Guide(V(2, 0, 0), V(1, 0, 0)))
    vp.scene.guides.append(guide)
    return guide


def group(vp):
    mesh = Mesh()
    mesh.add_edge(V(3, 0, 0), V(4, 0, 0))
    item = Group(mesh)
    vp.scene.groups.append(item)
    return item


def begin(vp, tool):
    tool.on_click(context(vp))
    tool.on_click(context(vp, 1, 0))


def finish(vp, tool, degrees=90):
    radians = math.radians(degrees)
    target = context(vp, math.cos(radians), math.sin(radians))
    tool.on_hover(target)
    tool.on_click(target)


def guide_angles(vp):
    return sorted(round(math.degrees(math.atan2(g.point.y(), g.point.x()))
                        % 360, 3) for g in vp.scene.guides)


@pytest.mark.parametrize("point", [False, True])
def test_selected_guide_rotates_live_then_commits_with_undo_redo(point):
    vp, tool = View(), RotateTool()
    guide = add_guide(vp, point)
    vp.scene.select([guide])
    begin(vp, tool)
    tool.on_hover(context(vp, 0, 1))
    near(guide.point, V(0, 2, 0))
    if point:
        near(guide.origin, V(0, 1, 0))
    else:
        near(guide.direction, V(0, 1, 0))
    assert not vp.history.undo_stack
    tool.on_click(context(vp, 0, 1))
    assert len(vp.history.undo_stack) == 1
    assert vp.scene.guides == [guide]
    assert not vp.scene.edges and not vp.scene.faces
    near(guide.point, V(0, 2, 0))
    assert vp.history.undo()
    near(guide.point, V(2, 0, 0))
    if point:
        near(guide.origin, V(1, 0, 0))
    else:
        near(guide.direction, V(1, 0, 0))
    assert vp.history.redo()
    near(guide.point, V(0, 2, 0))


@pytest.mark.parametrize("point", [False, True])
@pytest.mark.parametrize("end", ["on_cancel", "on_deactivate"])
def test_repeated_preview_cancel_and_tool_switch_restore_exact_coordinates(point, end):
    vp, tool = View(), RotateTool()
    guide = add_guide(vp, point)
    original = guide.to_dict()
    vp.scene.select([guide])
    begin(vp, tool)
    for k in range(120):
        radians = math.radians(39 * math.sin(k * 0.31) + k * 0.013)
        tool.on_hover(context(vp, math.cos(radians), math.sin(radians)))
    getattr(tool, end)(vp)
    assert guide.to_dict() == original
    assert not vp.history.undo_stack
    assert tool.snap_excluded_guides() == set()


@pytest.mark.parametrize("point", [False, True])
def test_typed_angle_and_hot_correction_start_at_original_pose(point):
    vp, tool = View(), RotateTool()
    guide = add_guide(vp, point)
    vp.scene.select([guide])
    begin(vp, tool)
    tool.on_hover(context(vp, 1, 1))
    assert tool.on_value(vp, 90.0)
    near(guide.point, V(0, 2, 0))
    assert tool.on_value(vp, 180.0)
    near(guide.point, V(-2, 0, 0))
    assert tool.on_value(vp, -90.0)
    near(guide.point, V(0, -2, 0))
    if point:
        near(guide.origin, V(0, -1, 0))
    else:
        near(guide.direction, V(0, -1, 0))
    assert len(vp.history.undo_stack) == 1
    assert vp.history.undo()
    near(guide.point, V(2, 0, 0))
    assert vp.history.redo()
    near(guide.point, V(0, -2, 0))


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf"),
                                  1e100, (1.0, 2.0), True])
@pytest.mark.parametrize("hot", [False, True])
def test_invalid_angle_keeps_previous_pose_and_allows_valid_retry(value, hot):
    vp, tool = View(), RotateTool()
    guide = add_guide(vp)
    vp.scene.select([guide])
    begin(vp, tool)
    if hot:
        finish(vp, tool)
    else:
        tool.on_hover(context(vp, 1, 1))
    original = guide.to_dict()
    depth = len(vp.history.undo_stack)
    assert not tool.on_value(vp, value)
    assert guide.to_dict() == original
    assert len(vp.history.undo_stack) == depth
    assert tool.on_value(vp, 180.0)
    near(guide.point, V(-2, 0, 0))
    assert len(vp.history.undo_stack) == 1


@pytest.mark.parametrize("point", [False, True])
def test_ctrl_copy_preserves_original_and_retypes_polar_array(point):
    vp, tool = View(), RotateTool()
    guide = add_guide(vp, point)
    vp.scene.select([guide])
    begin(vp, tool)
    tool.on_hover(context(vp, 0, 1))
    tool.on_key(vp, Qt.Key_Control, Qt.NoModifier)
    near(guide.point, V(2, 0, 0))
    assert tool.snap_excluded_guides() == set()
    tool.on_click(context(vp, 0, 1))
    assert guide_angles(vp) == [0, 90]
    assert tool.array_pending(vp)
    assert tool.on_array_value(vp, 3, "x")
    assert guide_angles(vp) == [0, 90, 180, 270]
    assert tool.on_value(vp, 30.0)
    assert guide_angles(vp) == [0, 30, 60, 90]
    assert tool.on_array_value(vp, 3, "/")
    assert guide_angles(vp) == [0, 10, 20, 30]
    assert tool.on_value(vp, 90.0)
    assert guide_angles(vp) == [0, 30, 60, 90]
    for copied in vp.scene.guides[1:]:
        assert copied is not guide
        if point:
            assert (copied.point - copied.origin).length() == pytest.approx(1)
        else:
            assert copied.direction.length() == pytest.approx(1)
            near(copied.direction * 2, copied.point)
    assert len(vp.history.undo_stack) == 1
    assert vp.history.undo()
    assert vp.scene.guides == [guide]
    assert vp.history.redo()
    assert guide_angles(vp) == [0, 30, 60, 90]


def test_turning_copy_off_resumes_original_preview_and_cancel_restores_it():
    vp, tool = View(), RotateTool()
    guide = add_guide(vp)
    vp.scene.select([guide])
    begin(vp, tool)
    tool.on_hover(context(vp, 0, 1))
    tool.on_key(vp, Qt.Key_Control, Qt.NoModifier)
    near(guide.point, V(2, 0, 0))
    tool.on_hover(context(vp, -1, 0))
    tool.on_key(vp, Qt.Key_Control, Qt.NoModifier)
    tool.on_hover(context(vp, -1, 0))
    near(guide.point, V(-2, 0, 0))
    assert tool.snap_excluded_guides() == {id(guide)}
    tool.on_cancel(vp)
    near(guide.point, V(2, 0, 0))
    assert vp.scene.guides == [guide]


@pytest.mark.parametrize("copy", [False, True])
def test_direct_hover_grabs_guide_instead_of_the_face_behind_it(copy):
    vp, tool = View(), RotateTool()
    guide = add_guide(vp)
    face = vp.scene.mesh.add_face([V(0, 0, 0), V(4, 0, 0),
                                   V(4, 4, 0), V(0, 4, 0)])
    original = [V(v) for v in face.vertices]
    vp.hits.update(guide=guide, face=face)
    begin(vp, tool)
    if copy:
        tool.on_key(vp, Qt.Key_Control, Qt.NoModifier)
    finish(vp, tool)
    if copy:
        near(guide.point, V(2, 0, 0))
        assert len(vp.scene.guides) == 2
        near(vp.scene.guides[1].point, V(0, 2, 0))
    else:
        near(guide.point, V(0, 2, 0))
    assert vp.scene.faces == [face]
    for actual, expected in zip(face.vertices, original):
        near(actual, expected)


@pytest.mark.parametrize("kind", ["group", "edge", "section"])
def test_specific_entity_has_priority_over_guide_when_picked_directly(kind):
    vp, tool = View(), RotateTool()
    guide = add_guide(vp)
    if kind == "group":
        item = group(vp)
    elif kind == "edge":
        item = vp.scene.mesh.add_edge(V(3, 0, 0), V(4, 0, 0))
    else:
        item = SectionPlane(V(3, 0, 0), V(0, 0, 1))
        vp.scene.section_planes.append(item)
    vp.hits.update(guide=guide, **{kind: item})
    begin(vp, tool)
    finish(vp, tool)
    near(guide.point, V(2, 0, 0))
    assert len(vp.history.undo_stack) == 1
    actual = (item.mesh.edges[0].a if kind == "group" else
              item.a if kind == "edge" else item.point)
    near(actual, V(0, 3, 0))


def test_mixed_guides_loose_geometry_and_group_commit_as_one_operation():
    vp, tool = View(), RotateTool()
    guide = add_guide(vp, point=True)
    edge = vp.scene.mesh.add_edge(V(5, 0, 0), V(6, 0, 0))
    item = group(vp)
    vp.scene.select([guide, edge, item])
    begin(vp, tool)
    tool.on_hover(context(vp, 0, 1))
    near(guide.point, V(0, 2, 0))
    near(edge.a, V(0, 5, 0))
    near(item.mesh.edges[0].a, V(0, 3, 0))
    tool.on_click(context(vp, 0, 1))
    assert len(vp.history.undo_stack) == 1
    assert vp.history.undo()
    near(guide.point, V(2, 0, 0))
    near(vp.scene.mesh.edges[0].a, V(5, 0, 0))
    near(item.mesh.edges[0].a, V(3, 0, 0))


@pytest.mark.parametrize("cancel", [False, True])
def test_guide_rotates_live_beside_group_using_fast_viewport_preview(cancel):
    vp, tool = FrozenView(), RotateTool()
    guide = add_guide(vp, point=True)
    item = group(vp)
    vp.scene.select([guide, item])
    begin(vp, tool)
    tool.on_hover(context(vp, 0, 1))
    near(guide.point, V(0, 2, 0))
    near(guide.origin, V(0, 1, 0))
    near(vp.preview_matrix.map(V(3, 0, 0)), V(0, 3, 0))
    near(item.mesh.edges[0].a, V(3, 0, 0))
    if cancel:
        tool.on_cancel(vp)
        assert not vp.history.undo_stack
        near(item.mesh.edges[0].a, V(3, 0, 0))
    else:
        tool.on_click(context(vp, 0, 1))
        near(item.mesh.edges[0].a, V(0, 3, 0))
        assert vp.history.undo()
    near(guide.point, V(2, 0, 0))
    near(guide.origin, V(1, 0, 0))


def test_guide_in_open_group_stays_global_and_can_undo_after_exit():
    vp, tool = View(), RotateTool()
    guide = add_guide(vp)
    item = group(vp)
    vp.scene.begin_group_edit(item)
    vp.scene.select([guide])
    begin(vp, tool)
    finish(vp, tool)
    vp.scene.end_group_edit()
    assert vp.scene.guides == [guide]
    near(guide.point, V(0, 2, 0))
    near(item.mesh.edges[0].a, V(3, 0, 0))
    assert vp.history.undo()
    near(guide.point, V(2, 0, 0))
    assert vp.history.redo()
    near(guide.point, V(0, 2, 0))


@pytest.mark.parametrize("change", ["undo_redo", "new_command", "context", "cancel"])
def test_hot_correction_expires_after_history_context_or_cancel(change):
    vp, tool = View(), RotateTool()
    guide = add_guide(vp)
    item = group(vp)
    vp.scene.begin_group_edit(item)
    vp.scene.select([guide])
    begin(vp, tool)
    finish(vp, tool)
    if change == "undo_redo":
        assert vp.history.undo()
        assert vp.history.redo()
    elif change == "new_command":
        vp.history.execute(AddGuideCommand(Guide(V(8, 8, 0))))
    elif change == "context":
        vp.scene.end_group_edit()
        vp.scene.begin_group_edit(item)
    else:
        tool.on_cancel(vp)
    assert not tool.on_value(vp, 180.0)
    near(guide.point, V(0, 2, 0))


def test_snap_candidates_exclude_only_live_rotating_guides():
    from views.viewport import Viewport

    vp, tool = View(), RotateTool()
    rotating = add_guide(vp)
    still = Guide(V(4, 4, 4))
    vp.scene.guides.append(still)
    vp.scene.select([rotating])
    vp.active_tool = tool
    vp._guide_snap_segment = lambda guide: guide.segment()
    vp._selection_box_points = lambda **kwargs: []
    assert tool.snap_excluded_guides() == set()
    assert len(Viewport._snap_scene(vp).edges) == 2
    tool.on_click(context(vp))
    assert tool.snap_excluded_guides() == set()
    tool.on_click(context(vp, 1, 0))
    tool.on_hover(context(vp, 0, 1))
    assert tool.snap_excluded_guides() == {id(rotating)}
    snap_edges = Viewport._snap_scene(vp).edges
    assert len(snap_edges) == 1
    near(snap_edges[0].a, still.point)
    tool.on_key(vp, Qt.Key_Control, Qt.NoModifier)
    assert len(Viewport._snap_scene(vp).edges) == 2
    tool.on_cancel(vp)
    assert len(Viewport._snap_scene(vp).edges) == 2


def test_guide_command_rotates_multiple_guides_about_non_origin_custom_axis():
    from core.history import RotateGuidesCommand

    vp = View()
    line = Guide(V(2, 3, 4), V(0, 1, 0))
    point = Guide(V(2, 3, 4), origin=V(2, 2, 4))
    vp.scene.guides.extend([line, point])
    before = [guide.to_dict() for guide in vp.scene.guides]
    vp.history.execute(RotateGuidesCommand([line, point], V(1, 1, 1),
                                           V(1, 0, 0), 90.0))
    assert vp.scene.guides == [line, point]
    near(line.point, V(2, -2, 3))
    near(line.direction, V(0, 0, 1))
    near(point.point, V(2, -2, 3))
    near(point.origin, V(2, -2, 2))
    assert vp.history.undo()
    assert [guide.to_dict() for guide in vp.scene.guides] == before
    assert vp.history.redo()
    near(point.origin, V(2, -2, 2))


def test_hot_zero_angle_restores_starting_pose_without_adding_an_undo_step():
    vp, tool = View(), RotateTool()
    guide = Guide(V(2, 0, 0))
    vp.scene.guides.append(guide)
    vp.scene.select([guide])
    begin(vp, tool)
    finish(vp, tool)
    assert tool.on_value(vp, 0.0)
    near(guide.point, V(2, 0, 0))
    assert guide.direction is None and guide.origin is None
    assert len(vp.history.undo_stack) == 1
    assert vp.history.undo()
    near(guide.point, V(2, 0, 0))
    assert vp.history.redo()
    near(guide.point, V(2, 0, 0))


@pytest.mark.parametrize("failure", ["none", "raise"])
def test_failed_hot_rebuild_restores_previous_copies_history_and_allows_retry(failure,
                                                                          monkeypatch):
    vp, tool = View(), RotateTool()
    guide = add_guide(vp, point=True)
    vp.scene.select([guide])
    begin(vp, tool)
    tool.on_key(vp, Qt.Key_Control, Qt.NoModifier)
    finish(vp, tool, 30)
    assert tool.on_array_value(vp, 3, "x")
    before = [g.to_dict() for g in vp.scene.guides]
    previous = vp.history.undo_stack[-1]
    revision = vp.history.revision
    original_build = tool._last["build"]

    def invalid_build(angles):
        if failure == "raise":
            raise ValueError("Cannot build this rotation")
        return None

    monkeypatch.setattr(vp.history, "_log_failure", lambda *args: None)
    tool._last["build"] = invalid_build
    assert not tool.on_value(vp, 45.0)
    assert [g.to_dict() for g in vp.scene.guides] == before
    assert vp.history.undo_stack == [previous]
    assert vp.history.revision == revision
    assert tool.array_pending(vp)
    tool._last["build"] = original_build
    assert tool.on_value(vp, 45.0)
    assert guide_angles(vp) == [0, 45, 90, 135]
    assert len(vp.history.undo_stack) == 1
    assert vp.history.undo()
    assert vp.scene.guides == [guide]


@pytest.mark.parametrize("count", [0, -1, 10 ** 40])
def test_invalid_or_unrepresentable_polar_array_keeps_last_copy_and_retry(count):
    vp, tool = View(), RotateTool()
    guide = add_guide(vp)
    vp.scene.select([guide])
    begin(vp, tool)
    tool.on_key(vp, Qt.Key_Control, Qt.NoModifier)
    finish(vp, tool)
    before = [g.to_dict() for g in vp.scene.guides]
    previous = vp.history.undo_stack[-1]
    assert not tool.on_array_value(vp, count, "x")
    assert [g.to_dict() for g in vp.scene.guides] == before
    assert vp.history.undo_stack == [previous]
    assert tool.array_pending(vp)
    assert tool.on_array_value(vp, 2, "x")
    assert guide_angles(vp) == [0, 90, 180]

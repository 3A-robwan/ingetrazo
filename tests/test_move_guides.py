# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Construction guides participate in Move without becoming model edges."""
import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QVector3D as V

from core.dimension import Dimension
from core.group import Group
from core.guide import Guide
from core.history import History, MoveGuidesCommand
from core.mesh import Mesh
from core.scene import Scene
from core.section import SectionPlane
from core.textlabel import TextLabel
from tools.base import ToolContext
from tools.move import MoveTool


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

    def pick_dimension(self, *args):
        return self.hits.get("dimension")

    def pick_text_label(self, *args, **kwargs):
        return self.hits.get("label")

    def pick_section_plane(self, *args):
        return self.hits.get("section")


class FrozenView(View):
    """The group-only fast preview does not mutate the group's mesh."""

    def begin_groups_preview(self, groups):
        self.preview_groups = list(groups)

    def set_groups_preview_offset(self, delta):
        self.preview_offset = V(delta)

    def end_groups_preview(self):
        self.preview_groups = []


def context(vp, x=0, y=0, z=0):
    return ToolContext(vp, V(x, y, z), QPointF(x * 20, y * 20),
                       Qt.NoModifier, None)


def near(actual, expected):
    assert (actual - expected).length() < 1e-5


def add_guide(vp, point=False):
    guide = (Guide(V(1, 2, 3), origin=V(-1, 2, 3)) if point
             else Guide(V(1, 2, 3), V(1, 0, 0)))
    vp.scene.guides.append(guide)
    return guide


def group(vp):
    mesh = Mesh()
    mesh.add_edge(V(0, 0, 0), V(1, 0, 0))
    item = Group(mesh)
    vp.scene.groups.append(item)
    return item


@pytest.mark.parametrize("point", [False, True])
def test_selected_guide_follows_live_preview_and_commits_as_one_undo(point):
    vp, tool = View(), MoveTool()
    guide = add_guide(vp, point)
    vp.scene.select([guide])
    tool.on_click(context(vp, 5, 6, 7))
    tool.on_hover(context(vp, 5, 8, 8))
    near(guide.point, V(1, 4, 4))
    if point:
        near(guide.origin, V(-1, 4, 4))
    else:
        near(guide.direction, V(1, 0, 0))
    assert not vp.history.undo_stack
    tool.on_click(context(vp, 5, 8, 8))
    near(guide.point, V(1, 4, 4))
    assert len(vp.history.undo_stack) == 1
    assert vp.scene.guides == [guide]
    assert not vp.scene.edges and not vp.scene.faces
    assert vp.history.undo()
    near(guide.point, V(1, 2, 3))
    if point:
        near(guide.origin, V(-1, 2, 3))
    assert vp.history.redo()
    near(guide.point, V(1, 4, 4))


@pytest.mark.parametrize("point", [False, True])
@pytest.mark.parametrize("finish", ["on_cancel", "on_deactivate"])
def test_cancel_or_tool_switch_restores_guide_without_history(point, finish):
    vp, tool = View(), MoveTool()
    guide = add_guide(vp, point)
    vp.scene.select([guide])
    tool.on_click(context(vp))
    tool.on_hover(context(vp, 1, 2, 3))
    tool.on_hover(context(vp, -3, 4, 1))
    getattr(tool, finish)(vp)
    near(guide.point, V(1, 2, 3))
    if point:
        near(guide.origin, V(-1, 2, 3))
    assert not vp.history.undo_stack
    assert tool.snap_excluded_guides() == set()


def test_typed_move_and_post_operation_corrections_use_original_location():
    vp, tool = View(), MoveTool()
    guide = add_guide(vp, point=True)
    vp.scene.select([guide])
    tool.on_click(context(vp, 4, 5, 6))
    tool.on_hover(context(vp, 4, 7, 6))
    assert tool.on_value(vp, 3.0)
    near(guide.point, V(1, 5, 3))
    assert tool.on_value(vp, 5.0)
    near(guide.point, V(1, 7, 3))
    assert tool.on_value(vp, (2.0, 0.0, -1.0))
    near(guide.point, V(3, 2, 2))
    near(guide.origin, V(1, 2, 2))
    assert len(vp.history.undo_stack) == 1
    assert vp.history.undo()
    near(guide.point, V(1, 2, 3))
    assert vp.history.redo()
    near(guide.point, V(3, 2, 2))


@pytest.mark.parametrize("value", [float("nan"), float("inf"), 1e100,
                                  (1e100, 0, 0), (1.0, 2.0)])
def test_invalid_numeric_correction_preserves_previous_move_and_retry(value):
    vp, tool = View(), MoveTool()
    guide = add_guide(vp)
    vp.scene.select([guide])
    tool.on_click(context(vp))
    tool.on_hover(context(vp, 0, 2, 0))
    tool.on_click(context(vp, 0, 2, 0))
    assert not tool.on_value(vp, value)
    near(guide.point, V(1, 4, 3))
    assert len(vp.history.undo_stack) == 1
    assert tool.on_value(vp, 4.0)
    near(guide.point, V(1, 6, 3))


@pytest.mark.parametrize("point", [False, True])
def test_ctrl_copy_keeps_original_and_retypes_external_and_internal_arrays(point):
    vp, tool = View(), MoveTool()
    guide = add_guide(vp, point)
    vp.scene.select([guide])
    tool.on_click(context(vp))
    tool.on_hover(context(vp, 0, 2, 0))
    tool.on_key(vp, Qt.Key_Control, Qt.NoModifier)
    near(guide.point, V(1, 2, 3))
    assert tool.snap_excluded_guides() == set()
    tool.on_click(context(vp, 0, 2, 0))
    assert len(vp.scene.guides) == 2
    near(vp.scene.guides[1].point, V(1, 4, 3))
    assert tool.on_array_value(vp, 3, "x")
    assert sorted(round(g.point.y(), 5) for g in vp.scene.guides) == [2, 4, 6, 8]
    assert tool.on_value(vp, 4.0)
    assert sorted(round(g.point.y(), 5) for g in vp.scene.guides) == [2, 6, 10, 14]
    assert tool.on_array_value(vp, 2, "/", step=10.0)
    assert sorted(round(g.point.y(), 5) for g in vp.scene.guides) == [2, 7, 12]
    for copied in vp.scene.guides[1:]:
        assert copied is not guide
        if point:
            near(copied.point - copied.origin, V(2, 0, 0))
        else:
            near(copied.direction, guide.direction)
    assert len(vp.history.undo_stack) == 1
    assert vp.history.undo()
    assert vp.scene.guides == [guide]
    assert vp.history.redo()
    assert sorted(round(g.point.y(), 5) for g in vp.scene.guides) == [2, 7, 12]


def test_toggling_copy_off_resumes_live_guide_and_cancel_restores_it():
    vp, tool = View(), MoveTool()
    guide = add_guide(vp)
    vp.scene.select([guide])
    tool.on_click(context(vp))
    tool.on_hover(context(vp, 0, 2, 0))
    tool.on_key(vp, Qt.Key_Control, Qt.NoModifier)
    near(guide.point, V(1, 2, 3))
    tool.on_hover(context(vp, 0, 5, 0))
    tool.on_key(vp, Qt.Key_Control, Qt.NoModifier)
    near(guide.point, V(1, 7, 3))
    assert tool.snap_excluded_guides() == {id(guide)}
    tool.on_cancel(vp)
    near(guide.point, V(1, 2, 3))
    assert vp.scene.guides == [guide]


def test_direct_hover_grabs_guide_even_when_a_face_is_behind_it():
    vp, tool = View(), MoveTool()
    guide = add_guide(vp)
    face = vp.scene.mesh.add_face([V(0, 0, 3), V(4, 0, 3),
                                   V(4, 4, 3), V(0, 4, 3)])
    vp.hits.update(guide=guide, face=face)
    original = [V(v) for v in face.vertices]
    tool.on_click(context(vp, 2, 2, 3))
    tool.on_hover(context(vp, 2, 4, 3))
    tool.on_click(context(vp, 2, 4, 3))
    near(guide.point, V(1, 4, 3))
    for actual, expected in zip(face.vertices, original):
        near(actual, expected)


@pytest.mark.parametrize("kind", ["group", "edge", "dimension", "label", "section"])
def test_direct_hover_prefers_specific_real_entity_over_guide(kind):
    vp, tool = View(), MoveTool()
    guide = add_guide(vp)
    if kind == "group":
        item = group(vp)
    elif kind == "edge":
        item = vp.scene.mesh.add_edge(V(0, 0, 0), V(1, 0, 0))
    elif kind == "dimension":
        item = Dimension(V(0, 0, 0), V(1, 0, 0), V(0, 1, 0))
        vp.scene.dimensions.append(item)
    elif kind == "label":
        item = TextLabel(V(0, 0, 0), V(0, 1, 0), "Test")
        vp.scene.text_labels.append(item)
    else:
        item = SectionPlane(V(0, 0, 0), V(0, 0, 1))
        vp.scene.section_planes.append(item)
    vp.hits.update(guide=guide, **{kind: item})
    tool.on_click(context(vp))
    tool.on_hover(context(vp, 0, 2, 0))
    tool.on_click(context(vp, 0, 2, 0))
    near(guide.point, V(1, 2, 3))
    assert len(vp.history.undo_stack) == 1


def test_mixed_guide_loose_geometry_and_group_move_as_one_operation():
    vp, tool = View(), MoveTool()
    guide = add_guide(vp)
    edge = vp.scene.mesh.add_edge(V(5, 0, 0), V(6, 0, 0))
    item = group(vp)
    vp.scene.select([guide, edge, item])
    tool.on_click(context(vp))
    tool.on_hover(context(vp, 0, 2, 0))
    near(guide.point, V(1, 4, 3))
    near(edge.a, V(5, 2, 0))
    near(item.mesh.edges[0].a, V(0, 2, 0))
    tool.on_click(context(vp, 0, 2, 0))
    assert len(vp.history.undo_stack) == 1
    assert vp.history.undo()
    near(guide.point, V(1, 2, 3))
    near(vp.scene.mesh.edges[0].a, V(5, 0, 0))
    near(item.mesh.edges[0].a, V(0, 0, 0))


@pytest.mark.parametrize("cancel", [False, True])
def test_guide_moves_live_beside_group_using_fast_viewport_preview(cancel):
    vp, tool = FrozenView(), MoveTool()
    guide = add_guide(vp, point=True)
    item = group(vp)
    vp.scene.select([guide, item])
    tool.on_click(context(vp))
    tool.on_hover(context(vp, 0, 2, 0))
    near(guide.point, V(1, 4, 3))
    near(guide.origin, V(-1, 4, 3))
    near(vp.preview_offset, V(0, 2, 0))
    near(item.mesh.edges[0].a, V(0, 0, 0))
    if cancel:
        tool.on_cancel(vp)
        assert not vp.history.undo_stack
        near(item.mesh.edges[0].a, V(0, 0, 0))
    else:
        tool.on_click(context(vp, 0, 2, 0))
        near(item.mesh.edges[0].a, V(0, 2, 0))
        assert vp.history.undo()
    near(guide.point, V(1, 2, 3))
    near(guide.origin, V(-1, 2, 3))


def test_guide_inside_open_group_remains_global_and_undo_works_after_exit():
    vp, tool = View(), MoveTool()
    guide = add_guide(vp)
    item = group(vp)
    vp.scene.begin_group_edit(item)
    vp.scene.select([guide])
    tool.on_click(context(vp))
    tool.on_hover(context(vp, 0, 2, 0))
    tool.on_click(context(vp, 0, 2, 0))
    vp.scene.end_group_edit()
    near(guide.point, V(1, 4, 3))
    assert vp.scene.guides == [guide]
    near(item.mesh.edges[0].a, V(0, 0, 0))
    assert vp.history.undo()
    near(guide.point, V(1, 2, 3))
    assert vp.history.redo()
    near(guide.point, V(1, 4, 3))


def test_snap_scene_excludes_only_the_guides_being_moved_and_restores_in_copy_mode():
    from views.viewport import Viewport

    vp, tool = View(), MoveTool()
    moving = add_guide(vp)
    still = Guide(V(4, 4, 4))
    vp.scene.guides.append(still)
    vp.scene.select([moving])
    vp.active_tool = tool
    vp._guide_snap_segment = lambda g: g.segment()
    vp._selection_box_points = lambda **kwargs: []
    assert len(Viewport._snap_scene(vp).edges) == 2
    tool.on_click(context(vp))
    tool.on_hover(context(vp, 0, 2, 0))
    snap_edges = Viewport._snap_scene(vp).edges
    assert len(snap_edges) == 1
    near(snap_edges[0].a, still.point)
    near(snap_edges[0].b, still.point)
    tool.on_key(vp, Qt.Key_Control, Qt.NoModifier)
    assert len(Viewport._snap_scene(vp).edges) == 2
    tool.on_cancel(vp)
    assert len(Viewport._snap_scene(vp).edges) == 2


def test_guide_command_moves_multiple_guides_and_preserves_their_identities():
    vp = View()
    line, point = add_guide(vp), add_guide(vp, point=True)
    vp.history.execute(MoveGuidesCommand([line, point], V(0, 3, 0)))
    assert vp.scene.guides == [line, point]
    near(line.point, V(1, 5, 3))
    near(point.origin, V(-1, 5, 3))
    assert vp.history.undo()
    near(line.point, V(1, 2, 3))
    near(point.origin, V(-1, 2, 3))
    assert vp.history.redo()
    near(point.point, V(1, 5, 3))

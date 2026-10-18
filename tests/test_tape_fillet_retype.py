# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Correct finished construction guides and bevels without adding Undo steps."""
from __future__ import annotations

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QVector3D as V

from core.guide import Guide
from core.history import AddEdgeCommand, History
from core.orient import is_closed, signed_volume
from core.scene import Scene
from core.snap import SnapResult
from tools.base import ToolContext
from tools.fillet import FilletTool
from tools.tape import TapeMeasureTool
from tests.test_fillet import box, edge_at


class VP:
    def __init__(self):
        self.scene = Scene()
        self.history = History(self.scene)
        self.source = None

    def update(self):
        pass

    def flash_status(self, *args, **kwargs):
        pass

    def pick_edge(self, *args):
        return None

    def pick_guide(self, *args):
        return self.source


def ctx(vp, x, y, kind="on_edge"):
    point = V(x, y, 0)
    return ToolContext(vp, point, QPointF(x * 100, y * 100), Qt.NoModifier,
                       SnapResult(point, kind, (0, 0, 0)))


def line_guide():
    vp = VP()
    vp.source = Guide(V(0, 1, 0), V(1, 0, 0))
    vp.scene.guides.append(vp.source)
    tool = TapeMeasureTool()
    tool.on_activate(vp)
    tool.on_click(ctx(vp, 3, 1))
    tool.on_click(ctx(vp, 3, 3, "none"))
    return vp, tool


def test_tape_line_retype_keeps_source_direction_and_one_undo():
    vp, tool = line_guide()
    for distance in (4.0, 2.5, -1.0, 0.0):
        assert tool.on_value(vp, distance)
        assert len(vp.scene.guides) == 2
        guide = vp.scene.guides[-1]
        assert guide.point.y() == pytest.approx(1 + distance)
        assert guide.direction == V(1, 0, 0)
        assert len(vp.history.undo_stack) == 1
    vp.history.undo()
    assert vp.scene.guides == [vp.source]
    vp.history.redo()
    assert vp.scene.guides[-1].point.y() == pytest.approx(1)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), 1e100, (2.0, 3.0)])
def test_invalid_tape_retype_never_replaces_a_finite_guide(value):
    vp, tool = line_guide()
    original = vp.scene.guides[-1]
    revision = vp.history.revision
    assert not tool.on_value(vp, value)
    assert vp.scene.guides[-1] is original
    assert original.point == V(3, 3, 0)
    assert vp.history.revision == revision
    assert tool.on_value(vp, 4.0)


@pytest.mark.parametrize("point_mode", [False, True])
def test_tape_point_retype_preserves_its_measured_origin(point_mode):
    vp = VP()
    tool = TapeMeasureTool()
    tool.on_activate(vp)
    if point_mode:
        tool._mode = "point"
    tool.on_click(ctx(vp, 1, 1, "origin"))
    tool.on_click(ctx(vp, 3, 1, "none"))
    assert tool.on_value(vp, 5.0)
    assert len(vp.scene.guides) == 1
    guide = vp.scene.guides[0]
    assert guide.point == V(6, 1, 0) and not guide.is_line
    assert guide.origin == (None if point_mode else V(1, 1, 0))
    assert len(vp.history.undo_stack) == 1
    vp.history.undo()
    assert not vp.scene.guides


@pytest.mark.parametrize("finish", ["cancel", "deactivate", "undo-redo", "other"])
def test_tape_retype_window_cannot_reach_back_to_an_old_guide(finish):
    vp, tool = line_guide()
    original = vp.scene.guides[-1]
    if finish == "cancel":
        tool.on_cancel(vp)
    elif finish == "deactivate":
        tool.on_deactivate(vp)
    elif finish == "undo-redo":
        vp.history.undo()
        vp.history.redo()
    else:
        vp.history.execute(AddEdgeCommand(V(0, 0, 0), V(1, 0, 0)))
    assert not tool.on_value(vp, 8.0)
    assert original.point == V(3, 3, 0)


@pytest.fixture
def fillet():
    saved = FilletTool._settings()
    FilletTool.radius, FilletTool.segments, FilletTool.profile = 0.1, 8, 0.5
    FilletTool.measure, FilletTool.corners = "radius", "round"
    FilletTool.affect, FilletTool.shape = "edges", None
    vp = VP()
    for face in box().faces:
        vp.scene.mesh.add_face(face.vertices)
    vp.scene.selection.add(edge_at(vp.scene.mesh, (0, 0, 1), (2, 0, 1)))
    tool = FilletTool()
    tool.on_activate(vp)
    assert tool.on_value(vp, 0.1)
    yield vp, tool
    for name, value in saved.items():
        setattr(FilletTool, name, value)


def test_fillet_retype_rebuilds_original_solid_and_has_one_undo(fillet):
    vp, tool = fillet
    volume = abs(signed_volume(vp.scene.mesh))
    assert tool.on_value(vp, 0.25)
    assert abs(signed_volume(vp.scene.mesh)) < volume
    assert is_closed(vp.scene.mesh)
    assert tool.on_value(vp, 0.15)
    assert tool.on_segments_value(vp, 4)
    assert len(vp.scene.mesh.faces) == 10
    assert tool.on_profile_value(vp, 0.3)
    assert is_closed(vp.scene.mesh)
    assert len(vp.history.undo_stack) == 1
    vp.history.undo()
    assert len(vp.scene.mesh.faces) == 6 and len(vp.scene.mesh.edges) == 12
    vp.history.redo()
    assert len(vp.scene.mesh.faces) == 10 and is_closed(vp.scene.mesh)


def test_invalid_fillet_preserves_result_and_can_be_corrected_again(fillet):
    vp, tool = fillet
    before = vp.scene.mesh.capture_state()
    revision = vp.history.revision
    assert not tool.on_value(vp, 20.0)
    assert vp.scene.mesh.capture_state() == before
    assert vp.history.revision == revision
    assert FilletTool.radius == 0.1
    assert tool.on_value(vp, 0.2)
    assert len(vp.history.undo_stack) == 1


def test_undo_redo_expires_fillet_correction(fillet):
    vp, tool = fillet
    vp.history.undo()
    vp.history.redo()
    before = vp.scene.mesh.capture_state()
    assert tool.on_value(vp, 0.2)  # Sets the NEXT operation's size when idle.
    assert vp.scene.mesh.capture_state() == before
    assert len(vp.history.undo_stack) == 1


def test_panel_size_prepares_a_new_fillet_without_reopening_the_previous_one(fillet):
    vp, tool = fillet
    before = vp.scene.mesh.capture_state()
    tool.set_size(vp, 0.3)
    assert tool.on_segments_value(vp, 4)
    assert FilletTool.radius == 0.3
    assert vp.scene.mesh.capture_state() == before

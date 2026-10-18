# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Finished shapes still receive lengths, angles and counts in the right units."""
from __future__ import annotations

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QMouseEvent

from core import units
from core.scene import Scene
from views.viewport import Viewport
from tests.test_offset_arc_retype import _Viewport, _arc
from tests.test_shape_retype import _VP, _radial, _rectangle, _rotated, _points
from tools.arc import CenterArcTool, PieTool
from tests.test_line_move_retype import moving, context
from tools.line import LineTool


class Event:
    def text(self):
        return ""

    def key(self):
        return Qt.Key_Return


def enter(vp, tool, text):
    dispatcher = Viewport.__new__(Viewport)
    dispatcher.scene, dispatcher.history = vp.scene, vp.history
    dispatcher.active_tool = tool
    dispatcher._value_buffer = text
    dispatcher.valueBufferChanged = type("Signal", (), {"emit": lambda self, value: None})()
    dispatcher.update = lambda: None
    dispatcher.flash_status = lambda *args: None
    dispatcher._release_axis_lock_after_operation = lambda *args, **kwargs: None
    assert dispatcher._handle_value_key(Event())


@pytest.fixture(autouse=True)
def reset_units():
    yield
    units.bind_scene(None)


def test_hot_circle_reads_radius_as_a_document_length_and_suffix_as_count():
    vp = _VP()
    tool = _radial(vp)
    vp.scene.units = {"length": "mm", "precision": 0}
    units.bind_scene(vp.scene)
    enter(vp, tool, "500")
    center = (1, 2, 3)
    assert all((p - type(p)(*center)).length() == pytest.approx(0.5) for p in _points(vp.scene))
    enter(vp, tool, "12s")
    assert len(vp.scene.mesh.edges) == 12
    assert len(vp.history.undo_stack) == 1


def test_hot_rectangle_pair_converts_each_explicit_unit():
    vp = _VP()
    tool = _rectangle(vp)
    units.bind_scene(vp.scene)
    enter(vp, tool, "200mm;30cm")
    points = _points(vp.scene)
    assert max(p.x() for p in points) - min(p.x() for p in points) == pytest.approx(0.2)
    assert max(p.y() for p in points) - min(p.y() for p in points) == pytest.approx(0.3)
    assert len(vp.history.undo_stack) == 1


def test_hot_rotated_rectangle_mixes_lengths_with_an_unscaled_angle():
    vp = _VP()
    tool = _rotated(vp)
    vp.scene.units = {"length": "mm", "precision": 0}
    units.bind_scene(vp.scene)
    enter(vp, tool, "6000;4000;90")
    assert max(p.z() for p in _points(vp.scene)) == pytest.approx(7)
    assert len(vp.history.undo_stack) == 1


@pytest.mark.parametrize("cls", [CenterArcTool, PieTool])
@pytest.mark.parametrize("typed", ["500r", "50cmr", "0.5mr"])
def test_hot_center_arc_radius_is_a_length_even_when_its_plain_input_is_an_angle(cls, typed):
    vp = _Viewport()
    tool = _arc(vp, cls)
    vp.scene.units = {"length": "mm", "precision": 0}
    units.bind_scene(vp.scene)
    enter(vp, tool, "60")
    enter(vp, tool, typed)
    points = [v.position for v in vp.scene.mesh.vertices if v.edges and v.position.length() > 1e-5]
    assert all(p.length() == pytest.approx(0.5, abs=1e-5) for p in points)
    assert len(vp.history.undo_stack) == 1


def escape(vp, tool):
    vp._value_buffer = ""
    vp.release_constraints = lambda: False
    vp.active_tool = tool
    vp._array_pending = lambda: bool(getattr(tool, "array_pending", lambda vp: False)(vp))
    vp._tool_busy = Viewport._tool_busy
    vp._release_linear_mode = lambda: None
    vp.extension_pick = None
    vp.clear_extension_pick = lambda: None
    Viewport.escape(vp)


def test_a_plain_move_does_not_claim_array_shortcuts_and_escape_closes_correction():
    vp, tool, mesh, _ = moving()
    assert not tool.array_pending(vp)
    before = mesh.capture_state()
    escape(vp, tool)
    assert not vp.scene.selection
    assert not tool.on_value(vp, 5.0)
    assert mesh.capture_state() == before


def test_escape_expires_a_hot_circle_even_when_it_clears_a_selection():
    vp = _VP()
    tool = _radial(vp)
    vp.scene.select([vp.scene.mesh.faces[0]])
    before = vp.scene.mesh.capture_state()
    escape(vp, tool)
    assert not vp.scene.selection
    assert tool.on_value(vp, 8.0)  # Side count for the next circle, not its old radius.
    assert vp.scene.mesh.capture_state() == before


def test_axis_release_snap_refresh_does_not_look_like_a_new_line_mouse_move(monkeypatch):
    vp = Viewport()
    tool = LineTool()
    vp.set_active_tool(tool)
    monkeypatch.setattr(vp, "pick_face_placement", lambda *args: (None, None))
    monkeypatch.setattr(vp, "_build_ctx", lambda ev: context(vp, ev.position().x() / 20))

    def refresh():
        pixel = vp._last_mouse_pos
        tool.on_hover(context(vp, pixel.x() / 20))

    monkeypatch.setattr(vp, "_refresh_snap", refresh)

    def click(pixel):
        event = QMouseEvent(QMouseEvent.MouseButtonPress, QPointF(pixel, 0),
                            QPointF(pixel, 0), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
        vp._dispatch_tool_click(event)

    try:
        click(0)
        vp.axis_lock = "x"
        vp._last_mouse_pos = QPointF(39, 0)  # previous move, just before the final click
        click(40)
        assert tool.on_value(vp, 3.0)
        assert len(vp.scene.mesh.edges) == 1
        assert max(max(e.a.x(), e.b.x()) for e in vp.scene.mesh.edges) == 3
    finally:
        vp.close()

# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 IngeTrazo contributors.
"""An edge becomes a parallel reference only after a stationary interior dwell.

The Qt timer must fire without another mouse event. Crossing a different edge
briefly leaves the existing reference intact, and a vertex is never an edge
acquisition target. Small fake viewports keep these timing tests independent
of OpenGL and camera-dependent picking.
"""
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QObject, QPointF, Qt
from PySide6.QtGui import QVector3D as V
from PySide6.QtTest import QTest

from core.group import Group
from core.history import AddEdgeCommand, History
from core.inference import InferenceEngine
from core.scene import Scene


class _View(QObject):
    ENCOURAGE_MS = 500
    snap_threshold_px = 9
    edge_snap_threshold_px = 14
    parallel_edge_dwell_ms = 500

    def __init__(self):
        super().__init__()
        self.scene = Scene()
        self.history = History(self.scene)
        self.active_tool = SimpleNamespace(uses_snap=True, start_point=V(-1, -1, 0))
        self.edge = self.scene.mesh.add_edge(V(0, 0, 0), V(8, 4, 0))
        self.corner = None
        self._last_mouse_pos = QPointF(40, 20)
        self.refreshes = 0
        self.updates = 0

    def pick_edge(self, _x, _y):
        return self.edge

    pick_edge_any = pick_edge

    def pick_vertex(self, _x, _y):
        return self.corner

    def pick_face_placement(self, _x, _y):
        return None, None

    def _update_center_ref(self, _x, _y):
        return None

    def _world_to_pixel(self, point):
        return point.x() * 10, point.y() * 10

    def _refresh_snap(self, *_args, **_kwargs):
        self.refreshes += 1

    def update(self):
        self.updates += 1


@pytest.fixture
def state():
    view = _View()
    engine = InferenceEngine(view)
    view.inference = engine
    yield view, engine
    engine.reset()


def _hover(view, engine, x=40, y=20):
    view._last_mouse_pos = QPointF(x, y)
    engine.acquire(x, y)


def _fire(engine):
    """Deliver the real timer signal to test validation without wall-clock waits."""
    engine._edge_dwell_timer.stop()
    engine._edge_dwell_timer.timeout.emit()


def test_default_dwell_is_half_a_second_and_has_a_precise_single_shot_timer(state):
    view, engine = state
    assert view.parallel_edge_dwell_ms == 500
    assert engine._edge_dwell_timer.interval() == 500
    assert engine._edge_dwell_timer.isSingleShot()
    assert engine._edge_dwell_timer.timerType() == Qt.PreciseTimer


def test_stationary_edge_body_acquires_after_timeout_without_another_hover(state):
    view, engine = state
    engine.set_parallel_edge_dwell_ms(100)
    _hover(view, engine)
    assert engine._hover_edge is view.edge
    assert engine._acquired_edge is None
    assert engine._edge_dwell_timer.isActive()
    QTest.qWait(35)
    assert engine._acquired_edge is None
    QTest.qWait(100)
    assert engine._acquired_edge is view.edge
    assert not engine._edge_dwell_timer.isActive()
    assert view.refreshes > 0 or view.updates > 0


@pytest.mark.parametrize("interval", [100, 250, 10000])
def test_configured_dwell_interval_is_used_and_resets_a_pending_capture(state, interval):
    view, engine = state
    _hover(view, engine)
    engine.set_parallel_edge_dwell_ms(interval)
    assert engine._edge_dwell_timer.interval() == interval
    assert not engine._edge_dwell_timer.isActive()
    assert engine._edge_dwell_edge is None
    assert engine._acquired_edge is None
    _hover(view, engine)
    assert engine._edge_dwell_timer.isActive()


def test_brief_crossing_of_another_edge_does_not_replace_an_acquired_reference(state):
    view, engine = state
    original = view.edge
    _hover(view, engine)
    _fire(engine)
    assert engine._acquired_edge is original
    view.edge = view.scene.mesh.add_edge(V(0, 4, 0), V(8, 0, 0))
    _hover(view, engine)
    assert engine._hover_edge is view.edge
    assert engine._acquired_edge is original
    assert engine._edge_dwell_timer.isActive()
    view.edge = None
    _hover(view, engine, 100, 100)
    assert not engine._edge_dwell_timer.isActive()
    assert engine._acquired_edge is original
    _fire(engine)
    assert engine._acquired_edge is original


def test_dwelling_on_another_edge_replaces_the_old_reference_only_at_timeout(state):
    view, engine = state
    original = view.edge
    _hover(view, engine)
    _fire(engine)
    view.edge = view.scene.mesh.add_edge(V(0, 4, 0), V(8, 0, 0))
    replacement = view.edge
    _hover(view, engine)
    assert engine._acquired_edge is original
    _fire(engine)
    assert engine._acquired_edge is replacement


@pytest.mark.parametrize("corner", [V(0, 0, 0), V(4, 2, 0)])
def test_a_vertex_cancels_pending_edge_capture_even_if_an_edge_is_under_it(state, corner):
    view, engine = state
    _hover(view, engine)
    assert engine._edge_dwell_timer.isActive()
    view.corner = corner
    _hover(view, engine)
    assert engine._acquired_edge is None
    assert not engine._edge_dwell_timer.isActive()
    _fire(engine)
    assert engine._acquired_edge is None


def test_near_an_edge_endpoint_is_not_an_interior_acquisition_even_without_vertex_pick(state):
    view, engine = state
    _hover(view, engine, 1, 1)
    assert engine._acquired_edge is None
    assert not engine._edge_dwell_timer.isActive()
    _fire(engine)
    assert engine._acquired_edge is None


def test_crossing_a_vertex_preserves_the_previously_acquired_edge(state):
    view, engine = state
    _hover(view, engine)
    _fire(engine)
    reference = engine._acquired_edge
    assert reference is view.edge
    view.edge = view.scene.mesh.add_edge(V(0, 4, 0), V(8, 0, 0))
    view.corner = V(4, 2, 0)
    _hover(view, engine)
    assert engine._acquired_edge is reference
    assert not engine._edge_dwell_timer.isActive()
    _fire(engine)
    assert engine._acquired_edge is reference


def test_movement_is_measured_from_the_fixed_anchor_not_the_previous_mouse_event(state):
    view, engine = state
    engine.set_parallel_edge_dwell_ms(100)
    _hover(view, engine)
    QTest.qWait(70)
    _hover(view, engine, 42, 20)  # small hand jitter keeps the initial anchor
    _hover(view, engine, 44, 20)  # two 2 px steps still exceed the 3 px allowance
    QTest.qWait(50)
    assert engine._acquired_edge is None
    assert engine._edge_dwell_timer.isActive()
    QTest.qWait(75)
    assert engine._acquired_edge is view.edge


@pytest.mark.parametrize("boundary", ["clear_references", "reset"])
def test_reset_and_clear_references_cancel_pending_timer_callbacks(state, boundary):
    view, engine = state
    _hover(view, engine)
    getattr(engine, boundary)()
    assert not engine._edge_dwell_timer.isActive()
    assert engine._edge_dwell_edge is None
    _fire(engine)
    assert engine._acquired_edge is None


@pytest.mark.parametrize("change", ["tool", "start", "start_in_place", "finish", "no_snap",
                                    "scene", "edit_group", "history"])
def test_a_new_drawing_context_cannot_inherit_the_pending_or_acquired_edge(state, change):
    view, engine = state
    _hover(view, engine)
    _fire(engine)
    assert engine._acquired_edge is view.edge
    if change == "tool":
        view.active_tool = SimpleNamespace(uses_snap=True, start_point=V(-1, -1, 0))
    elif change == "start":
        view.active_tool.start_point = V(-2, -2, 0)
    elif change == "start_in_place":
        view.active_tool.start_point.setX(-2)
    elif change == "finish":
        view.active_tool.start_point = None
    elif change == "no_snap":
        view.active_tool.uses_snap = False
    elif change == "scene":
        view.scene = Scene()
    elif change == "history":
        view.history.execute(AddEdgeCommand(V(20, 0, 0), V(21, 0, 0)))
    else:
        view.scene.edit_group = object()
    _hover(view, engine)
    assert engine._acquired_edge is None


@pytest.mark.parametrize("change", ["edge", "vertex", "leave", "delete", "history"])
def test_timeout_rechecks_the_cursor_and_document_instead_of_acquiring_stale_target(state, change):
    view, engine = state
    _hover(view, engine)
    original = view.edge
    if change == "edge":
        view.edge = view.scene.mesh.add_edge(V(0, 4, 0), V(8, 0, 0))
    elif change == "vertex":
        view.corner = V(4, 2, 0)
    elif change == "leave":
        view.edge = None
    elif change == "delete":
        view.scene.mesh.remove_edge(original)
    else:
        view.history.execute(AddEdgeCommand(V(20, 0, 0), V(21, 0, 0)))
    _fire(engine)
    assert engine._acquired_edge is None


def test_equivalent_fresh_group_edge_proxies_do_not_restart_dwell(state):
    from views.viewport import _SnapEdge

    view, engine = state
    engine.set_parallel_edge_dwell_ms(100)
    owner = Group(name="Parallel edge owner")
    a, b = V(0, 0, 0), V(8, 4, 0)
    owner.mesh.add_edge(a, b)
    view.scene.groups.append(owner)
    view.edge = _SnapEdge(a, b, in_group=True, context="group", group=owner)
    _hover(view, engine)
    QTest.qWait(70)
    view.edge = _SnapEdge(V(a), V(b), in_group=True, context="group", group=owner)
    _hover(view, engine)
    QTest.qWait(60)
    acquired = engine._acquired_edge
    assert acquired is not None
    assert (acquired.a - a).length() < 1e-6
    assert (acquired.b - b).length() < 1e-6
    assert acquired.group is owner


def test_same_endpoints_in_a_different_group_are_a_different_candidate(state):
    from views.viewport import _SnapEdge

    view, engine = state
    first, second = Group(), Group()
    for group in (first, second):
        group.mesh.add_edge(V(0, 0, 0), V(8, 4, 0))
        view.scene.groups.append(group)
    view.edge = _SnapEdge(V(0, 0, 0), V(8, 4, 0), in_group=True,
                          context="group", group=first)
    _hover(view, engine)
    original = view.edge
    _fire(engine)
    assert engine._acquired_edge is original
    view.edge = _SnapEdge(V(0, 0, 0), V(8, 4, 0), in_group=True,
                          context="group", group=second)
    _hover(view, engine)
    assert engine._acquired_edge is original
    assert engine._edge_dwell_timer.isActive()

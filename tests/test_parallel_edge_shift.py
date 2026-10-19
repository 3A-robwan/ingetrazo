# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Shift captures a parallel landing without treating every crossing as a lock."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent, QVector3D

from core.snap import COLOR_ENDPOINT, COLOR_REFERENCE, SnapResult, compute_snap
from views.viewport import Viewport


def V(x, y, z=0.0):
    return QVector3D(float(x), float(y), float(z))


START, HIT = V(2, 3), V(8, 6)


@pytest.fixture
def vp():
    viewport = Viewport()
    viewport.active_tool = SimpleNamespace(start_point=QVector3D(START))
    viewport._refresh_snap = lambda: None
    yield viewport
    viewport.close()


def _landing(**overrides):
    fields = dict(point=QVector3D(HIT), kind="intersection", color=COLOR_ENDPOINT,
                  guide=(QVector3D(START), QVector3D(HIT)), guide_color=COLOR_REFERENCE)
    fields.update(overrides)
    return SnapResult(**fields)


def test_shift_captures_parallel_direction_at_its_exact_edge_landing(vp):
    vp.last_snap = _landing()
    vp._capture_shift_lock()
    assert vp._shift_lock is not None
    direction, color = vp._shift_lock
    assert (direction - (HIT - START).normalized()).length() < 1e-6
    assert color == COLOR_REFERENCE


@pytest.mark.parametrize("overrides", [
    {"guide_color": None},
    {"guide_color": COLOR_ENDPOINT},
    {"guide": None},
    {"guide": (V(0, 0), HIT)},
    {"point": START, "guide": (START, START)},
], ids=["ordinary-crossing", "other-guide-color", "no-guide", "other-start", "zero-span"])
def test_unrelated_intersections_do_not_start_a_shift_lock(vp, overrides):
    vp.last_snap = _landing(**overrides)
    vp._capture_shift_lock()
    assert vp._shift_lock is None


def test_existing_reference_inference_remains_shift_lockable(vp):
    vp.last_snap = SnapResult(HIT, "reference", COLOR_REFERENCE)
    vp._capture_shift_lock()
    assert vp._shift_lock is not None
    direction, color = vp._shift_lock
    assert (direction - (HIT - START).normalized()).length() < 1e-6
    assert color == COLOR_REFERENCE


def test_captured_parallel_holds_outside_the_soft_cone_until_shift_release(vp):
    vp.last_snap = _landing()
    vp._capture_shift_lock()
    assert vp._shift_lock is not None
    direction, color = vp._shift_lock
    candidate = V(8, 8)

    def project(origin, unit):
        return origin + unit * QVector3D.dotProduct(candidate - origin, unit)

    snap = compute_snap(
        candidate_world=candidate, candidate_pixel=(800.0, 800.0),
        scene=SimpleNamespace(edges=[]), world_to_pixel=lambda p: (p.x() * 100, p.y() * 100),
        threshold_px=9.0, start_point=START, project_onto_line=project,
        shift_lock_dir=direction, shift_lock_color=color, linear_mode="off")
    assert snap.kind == "reference" and snap.color == COLOR_REFERENCE
    assert QVector3D.crossProduct(snap.point - START, direction).length() < 1e-5
    vp.keyReleaseEvent(QKeyEvent(QEvent.KeyRelease, Qt.Key_Shift, Qt.NoModifier))
    assert vp._shift_lock is None

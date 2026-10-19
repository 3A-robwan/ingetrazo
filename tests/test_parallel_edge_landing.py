# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""A confirmed parallel edge reference survives landing on other geometry."""
from __future__ import annotations

import math
from types import SimpleNamespace

import pytest
from PySide6.QtGui import QVector3D

from core.snap import COLOR_REFERENCE, compute_snap


def V(x, y, z=0.0):
    return QVector3D(float(x), float(y), float(z))


def edge(a, b, **attributes):
    return SimpleNamespace(a=a, b=b, center=False, **attributes)


REFERENCE = edge(V(1, 1), V(3, 2))
START = V(2, 3)


def _screen(point):
    return point.x() * 100.0, (point.y() + point.z() * 0.2) * 100.0


def _snap(candidate, *, start=START, reference=REFERENCE, edges=(), **options):
    def project(origin, direction):
        scale = QVector3D.dotProduct(candidate - origin, direction)
        scale /= QVector3D.dotProduct(direction, direction)
        return origin + direction * scale

    defaults = dict(start_point=start, acquired_edge=reference,
                    project_onto_line=project, edge_threshold_px=14.0)
    defaults.update(options)
    return compute_snap(candidate_world=candidate, candidate_pixel=_screen(candidate),
                        scene=SimpleNamespace(edges=list(edges)), world_to_pixel=_screen,
                        threshold_px=9.0, **defaults)


def _same(actual, expected):
    assert (actual - expected).length() < 1e-5


def _parallel(point, start=START, reference=REFERENCE):
    direction = (reference.b - reference.a).normalized()
    delta = point - start
    assert QVector3D.crossProduct(delta, direction).length() < 1e-5


@pytest.mark.parametrize("offset", [0.04, 0.12])
@pytest.mark.parametrize("mode", ["all", "parallel_perp"])
def test_parallel_lands_at_the_exact_wall_crossing(offset, mode):
    wall = edge(V(8, 0), V(8, 10))
    snap = _snap(V(8, 6 + offset), edges=[wall], linear_mode=mode)
    assert snap.kind == "intersection"
    _same(snap.point, V(8, 6))
    assert snap.guide is not None
    _same(snap.guide[0], START)
    _same(snap.guide[1], snap.point)


@pytest.mark.parametrize("target", ["endpoint", "midpoint"])
def test_a_nearby_point_off_the_parallel_does_not_steal_the_wall_landing(target):
    wall = (edge(V(8, 0), V(8, 6.04)) if target == "endpoint"
            else edge(V(8, 0.04), V(8, 12.04)))
    snap = _snap(V(8, 6.04), edges=[wall])
    assert snap.kind == "intersection"
    _same(snap.point, V(8, 6))


@pytest.mark.parametrize("target", ["endpoint", "center", "arc_midpoint", "component_origin"])
def test_an_off_parallel_named_point_cannot_break_the_soft_direction(target):
    point = V(8, 6.04)
    item = (edge(point, V(8, 9)) if target == "endpoint"
            else SimpleNamespace(a=point, b=point, **{target: True}))
    snap = _snap(point, edges=[item])
    assert snap.kind == "reference"
    assert snap.color == COLOR_REFERENCE
    _parallel(snap.point)


@pytest.mark.parametrize("target", ["endpoint", "midpoint", "center", "arc_midpoint",
                                    "component_origin", "close"])
def test_points_on_the_parallel_keep_their_identity(target):
    point = V(8, 6)
    if target == "endpoint":
        item = edge(point, V(8, 9), context="component")
    elif target == "midpoint":
        item = edge(V(7, 5.5), V(9, 6.5), context="component")
    else:
        item = SimpleNamespace(a=point, b=point, **{target: True})
    options = {"chain_first_point": point} if target == "close" else {}
    snap = _snap(V(8, 6.04), edges=[] if target == "close" else [item], **options)
    assert snap.kind == target
    _same(snap.point, point)
    if target in ("endpoint", "midpoint"):
        assert snap.context == "component"


def test_the_origin_on_the_parallel_remains_an_origin_target():
    snap = _snap(V(0.02, 0.01), start=V(2, 1))
    assert snap.kind == "origin"
    _same(snap.point, V(0, 0))


@pytest.mark.parametrize("reverse_draw", [False, True])
@pytest.mark.parametrize("reverse_reference", [False, True])
def test_parallel_and_wall_landing_work_in_both_directions(reverse_draw, reverse_reference):
    reference = edge(REFERENCE.b, REFERENCE.a) if reverse_reference else REFERENCE
    start, x, y = (V(8, 6), 2, 3) if reverse_draw else (START, 8, 6)
    wall = edge(V(x, -1), V(x, 11))
    snap = _snap(V(x, y + 0.04), start=start, reference=reference, edges=[wall])
    assert snap.kind == "intersection"
    _same(snap.point, V(x, y))


def test_parallel_landing_is_a_real_intersection_in_a_tilted_3d_plane():
    reference = edge(V(1, 1, 1), V(3, 2, 3))
    start = V(2, 3, 4)
    wall = edge(V(8, 0, 10), V(8, 12, 10))
    snap = _snap(V(8, 6.04, 10), start=start, reference=reference, edges=[wall])
    assert snap.kind == "intersection"
    _same(snap.point, V(8, 6, 10))


@pytest.mark.parametrize("wall", [edge(V(8, 0, 1), V(8, 10, 1)),
                                  edge(V(8, 0, 0.0005), V(8, 10, 0.0005)),
                                  edge(V(0, 2), V(20, 12.1))],
                         ids=["skew", "near-skew", "far-crossing"])
def test_skew_or_distant_crossings_leave_a_plain_parallel_cue(wall):
    snap = _snap(V(8, 6.04), edges=[wall])
    assert snap.kind == "reference"
    _parallel(snap.point)


def test_hidden_crossing_does_not_become_a_parallel_landing():
    wall = edge(V(8, 0), V(8, 10))
    snap = _snap(V(8, 6.04), edges=[wall], is_occluded=lambda point: True)
    assert snap.kind == "reference"
    _parallel(snap.point)


def test_explicit_shift_keeps_its_existing_intersection_tolerance():
    wall = edge(V(8, 0, 0.0005), V(8, 10, 0.0005))
    snap = _snap(V(8, 6.04), edges=[wall],
                 shift_lock_dir=(REFERENCE.b - REFERENCE.a).normalized())
    assert snap.kind == "intersection"
    _same(snap.point, V(8, 6, 0.0005))


@pytest.mark.parametrize("angle", [3.1, 8.0])
def test_leaving_the_soft_cone_restores_normal_edge_snapping(angle):
    direction = math.atan2(1, 2) + math.radians(angle)
    y = START.y() + 6 * math.tan(direction)
    point = V(8, y)
    snap = _snap(point, edges=[edge(V(8, 0), V(8, 12))])
    assert snap.kind == "on_edge"
    _same(snap.point, point)


@pytest.mark.parametrize("options", [{"linear_mode": "off"}, {"acquired_edge": None}])
def test_disabling_parallel_preserves_the_ordinary_edge_point(options):
    point = V(8, 6.04)
    snap = _snap(point, edges=[edge(V(8, 0), V(8, 10))], **options)
    assert snap.kind == "on_edge"
    _same(snap.point, point)


@pytest.mark.parametrize("lock", [{"axis_lock": "x"}, {"shift_lock_dir": V(1, 0)},
                                  {"reference_edge": edge(V(0, 1), V(1, 1)),
                                   "reference_mode": "parallel"}])
def test_explicit_axis_shift_and_down_locks_keep_priority(lock):
    snap = _snap(V(8, 6.04), edges=[edge(V(8, 0), V(8, 10))], **lock)
    assert abs(snap.point.y() - START.y()) < 1e-5


def test_an_engaged_axis_still_overrides_the_acquired_parallel():
    angle = math.radians(12)
    direction = V(math.cos(angle), math.sin(angle))
    reference = edge(V(1, -2), V(1, -2) + direction * 2)
    snap = _snap(START + direction * 6, reference=reference, magnetic_axis_deg=15.0)
    assert snap.kind == "axis" and snap.axis == "x"
    assert abs(snap.point.y() - START.y()) < 1e-5

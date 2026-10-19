# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 IngeTrazo contributors.
"""An explicitly acquired point can locate a foot on a strong direction."""
from __future__ import annotations

import math
from types import SimpleNamespace

import pytest
from PySide6.QtGui import QVector3D as V

from core.snap import AXIS_COLORS, COLOR_ENDPOINT, COLOR_REFERENCE, compute_snap


def _edge(a, b, **attributes):
    return SimpleNamespace(a=a, b=b, center=False, **attributes)


def _screen(point):
    return ((point.x() + point.z() * 0.2) * 100,
            (point.y() + point.z() * 0.3) * 100)


def _case(kind, reverse=False, tilted=False):
    start = V(2, 3, 1)
    normal = V(0, 0, 1)
    if kind in ("x", "y", "z"):
        direction = {"x": V(1, 0, 0), "y": V(0, 1, 0), "z": V(0, 0, 1)}[kind]
        side = V(0, 1, 0) if kind == "x" else V(1, 0, 0)
        edges, acquired_edge = [], None
    elif kind == "perpendicular":
        if tilted:
            normal = V(0, -1, 1).normalized()
            side = V(2, 1, 1).normalized()
        else:
            side = V(2, 1, 0).normalized()
        direction = V.crossProduct(normal, side).normalized()
        edges = [_edge(start - side * 2, start + side * 2)]
        acquired_edge = None
    else:
        direction = V(2, 1, 0).normalized()
        side = V(-direction.y(), direction.x(), 0)
        edges = []
        acquired_edge = _edge(V(1, 1, 1), V(3, 2, 1))
    if reverse:
        direction = -direction
    foot = start + direction * 4
    return SimpleNamespace(
        kind=kind, start=start, direction=direction, side=side, normal=normal,
        foot=foot, reference=foot + side * 1.5,
        candidate=foot + direction * 0.04 + side * 0.01,
        edges=edges, acquired_edge=acquired_edge)


def _snap(case, **overrides):
    candidate = overrides.pop("candidate", case.candidate)
    edges = overrides.pop("edges", case.edges)

    def project(origin, direction):
        return origin + direction * (V.dotProduct(candidate - origin, direction)
                                     / V.dotProduct(direction, direction))

    options = dict(
        start_point=case.start, acquired_point=case.reference,
        acquired_edge=case.acquired_edge, project_onto_line=project,
        magnetic_axis_deg=3 if case.kind in ("x", "y", "z") else None,
        edge_threshold_px=14, work_plane_normal=case.normal)
    options.update(overrides)
    return compute_snap(
        candidate_world=candidate, candidate_pixel=_screen(candidate),
        scene=SimpleNamespace(edges=list(edges)), world_to_pixel=_screen,
        threshold_px=9, **options)


def _same(actual, expected):
    assert (actual - expected).length() < 1e-5


@pytest.mark.parametrize("kind", ["x", "y", "z", "perpendicular", "parallel"])
@pytest.mark.parametrize("reverse", [False, True], ids=["forward", "reverse"])
def test_acquired_point_fixes_the_length_without_bending_the_active_direction(kind, reverse):
    case = _case(kind, reverse)
    result = _snap(case)
    assert result.kind == "from_point"
    assert result.color == COLOR_ENDPOINT
    _same(result.point, case.foot)
    _same(result.guide[0], case.reference)
    _same(result.guide[1], case.foot)
    assert V.crossProduct(result.point - case.start, case.direction).length() < 1e-5
    constraint = result.constraint_dir
    assert constraint is not None
    assert constraint.length() == pytest.approx(1, abs=1e-6)
    assert V.crossProduct(constraint, case.direction).length() < 1e-6
    expected_color = AXIS_COLORS[kind] if kind in ("x", "y", "z") else COLOR_REFERENCE
    assert result.constraint_color == expected_color


@pytest.mark.parametrize("reverse", [False, True])
def test_rotated_perpendicular_projection_remains_on_a_tilted_work_plane(reverse):
    case = _case("perpendicular", reverse, tilted=True)
    result = _snap(case)
    assert result.kind == "from_point"
    _same(result.point, case.foot)
    assert abs(V.dotProduct(result.point - case.start, case.normal)) < 1e-5


@pytest.mark.parametrize("kind", ["x", "perpendicular", "parallel"])
@pytest.mark.parametrize("mode", ["off", "parallel_perp"])
def test_alt_modes_do_not_enable_the_new_from_point_projection(kind, mode):
    assert _snap(_case(kind), linear_mode=mode).kind != "from_point"


@pytest.mark.parametrize("kind", ["x", "perpendicular", "parallel"])
def test_radial_arms_do_not_gain_line_drawing_point_projections(kind):
    assert _snap(_case(kind), radial_arm=True).kind != "from_point"


@pytest.mark.parametrize("kind", ["x", "perpendicular", "parallel"])
def test_reference_foot_outside_the_small_point_radius_does_not_attract(kind):
    case = _case(kind)
    candidate = case.foot + case.direction * 0.2
    assert _snap(case, candidate=candidate).kind != "from_point"


@pytest.mark.parametrize("kind", ["x", "perpendicular", "parallel"])
def test_a_hidden_foot_is_not_offered(kind):
    case = _case(kind)
    assert _snap(case, is_occluded=lambda point: (point - case.foot).length() < 1e-4).kind != (
        "from_point")


@pytest.mark.parametrize("kind", ["x", "perpendicular", "parallel"])
def test_the_original_reference_can_be_hidden_if_its_acquired_foot_is_visible(kind):
    case = _case(kind)
    result = _snap(case, is_occluded=lambda point: (point - case.reference).length() < 1e-4)
    assert result.kind == "from_point"
    _same(result.point, case.foot)


def test_a_reference_at_the_operation_start_does_not_replace_the_axis():
    case = _case("x")
    assert _snap(case, acquired_point=case.start).kind == "axis"


def test_projection_back_to_the_start_does_not_create_a_zero_length_target():
    case = _case("x")
    reference = case.start + case.side * 2
    candidate = case.start + case.direction * 0.05
    result = _snap(case, acquired_point=reference, candidate=candidate)
    assert result.kind == "axis"
    _same(result.point, candidate)


def test_a_collinear_reference_keeps_existing_through_point_behavior():
    case = _case("x")
    candidate = case.foot + case.direction * 0.2 + case.side * 0.01
    result = _snap(case, acquired_point=case.foot, candidate=candidate)
    assert result.kind == "through_point"


def test_an_unacquired_scene_corner_stays_silent_under_the_axis_magnet():
    case = _case("x")
    edge = _edge(case.reference, case.reference + case.direction)
    assert _snap(case, edges=[edge], acquired_point=None).kind == "axis"


def test_an_unconstrained_from_point_does_not_claim_a_strong_direction():
    result = _snap(_case("x"), start_point=None)
    assert result.kind == "from_point"
    assert result.constraint_dir is None
    assert result.constraint_color is None


@pytest.mark.parametrize("kind", ["endpoint", "midpoint", "center", "close"])
def test_named_points_keep_priority_over_the_axis_foot(kind):
    case = _case("x")
    point = case.foot + case.side * 0.02
    if kind == "endpoint":
        edges = [_edge(point, point + case.side)]
    elif kind == "midpoint":
        edges = [_edge(point - case.direction * 0.3, point + case.direction * 0.3)]
    elif kind == "center":
        edges = [SimpleNamespace(a=point, b=point, center=True)]
    else:
        edges = []
    options = {"chain_first_point": point} if kind == "close" else {}
    result = _snap(case, edges=edges, **options)
    assert result.kind == kind
    _same(result.point, point)
    assert result.constraint_dir is None


@pytest.mark.parametrize("kind", ["perpendicular", "parallel"])
def test_a_midpoint_on_the_exact_direction_beats_a_derived_point_foot(kind):
    case = _case(kind)
    target = _edge(case.foot - case.direction * 0.3, case.foot + case.direction * 0.3)
    result = _snap(case, edges=case.edges + [target])
    assert result.kind == "midpoint"
    _same(result.point, case.foot)


def test_near_axis_perpendicular_never_falls_back_to_a_different_world_axis():
    case = _case("perpendicular")
    angle = math.radians(5)
    side = V(math.cos(angle), -math.sin(angle), 0)
    direction = V(math.sin(angle), math.cos(angle), 0)
    case.edges = [_edge(case.start - side * 2, case.start + side * 2)]
    case.reference = case.start + V(2, 3, 0)
    candidate = case.start + V(0.04, 3.03, 0)
    result = _snap(case, candidate=candidate)
    assert V.crossProduct(result.point - case.start, direction).length() < 1e-5


@pytest.mark.parametrize("lock", ["axis", "shift", "reference"])
def test_explicit_direction_locks_keep_priority(lock):
    case = _case("x")
    if lock == "axis":
        options = {"axis_lock": "y"}
    elif lock == "shift":
        options = {"shift_lock_dir": V(0, 1, 0)}
    else:
        options = {"reference_edge": _edge(V(), V(0, 1, 0)),
                   "reference_mode": "parallel"}
    result = _snap(case, **options)
    assert result.kind in ("axis", "reference")
    assert result.point.x() == pytest.approx(case.start.x())
    assert result.point.z() == pytest.approx(case.start.z())

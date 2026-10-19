# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 IngeTrazo contributors.
"""Screen highlights have logical-pixel weights without losing GL depth state."""
from __future__ import annotations

import math
from types import SimpleNamespace

import pytest
from PySide6.QtGui import QMatrix4x4, QVector4D

from views import viewport as rendering


@pytest.mark.parametrize("width", [1, 2, 3])
@pytest.mark.parametrize("dpr", [1.0, 1.25, 1.5, 2.0])
def test_highlight_weight_is_centered_and_scales_in_logical_pixels(width, dpr):
    w, h = 1200, 800
    offsets = rendering._highlight_jitter(width, dpr, w, h)
    assert offsets[0] == (0.0, 0.0), "keep the original edge even with fractional DPI"
    pixels = {(round(dx * w / 2, 8), round(dy * h / 2, 8)) for dx, dy in offsets}
    assert pixels == {(-dx, -dy) for dx, dy in pixels}
    expected = width * dpr
    actual_x = max(x for x, _y in pixels) - min(x for x, _y in pixels) + 1
    actual_y = max(y for _x, y in pixels) - min(y for _x, y in pixels) + 1
    assert actual_x == pytest.approx(expected, abs=1e-6)
    assert actual_y == pytest.approx(expected, abs=1e-6)
    assert all(math.isfinite(dx) and math.isfinite(dy) for dx, dy in offsets)


def test_highlight_jitter_scales_offsets_with_framebuffer_size():
    small = rendering._highlight_jitter(3, 1.5, 800, 600)
    large = rendering._highlight_jitter(3, 1.5, 1600, 1200)
    assert len(small) == len(large)
    for (sx, sy), (lx, ly) in zip(small, large):
        assert sx == pytest.approx(2 * lx)
        assert sy == pytest.approx(2 * ly)


@pytest.mark.parametrize("given, clamped", [(-1, 1), (0, 1), (4, 3), (100, 3)])
def test_highlight_width_stays_inside_the_preference_range(given, clamped):
    assert rendering._highlight_jitter(given, 1, 800, 600) == (
        rendering._highlight_jitter(clamped, 1, 800, 600))


class _Program:
    def __init__(self, matrix, events):
        self.current = QMatrix4x4(matrix)
        self.events = events

    def setUniformValue(self, location, matrix):
        assert location == 37
        self.current = QMatrix4x4(matrix)
        self.events.append(("matrix", QMatrix4x4(matrix)))


class _GL:
    def __init__(self, program, events, fail=False):
        self.program = program
        self.events = events
        self.depth_write = True
        self.fail = fail
        self.draws = []

    def glDepthMask(self, value):
        self.depth_write = bool(value)
        self.events.append(("depth_write", self.depth_write))

    def glDrawArrays(self, primitive, first, count):
        assert primitive == rendering.GL_LINES
        self.draws.append((first, count, self.depth_write, QMatrix4x4(self.program.current)))
        self.events.append(("draw", first, count))
        if self.fail:
            raise RuntimeError("simulated driver error")

    # No enable/disable or depth-function API: the pass must preserve these.


class _VAO:
    def __init__(self, events):
        self.events = events

    def bind(self):
        self.events.append(("bind",))

    def release(self):
        self.events.append(("release",))


def _renderer(dpr=1.0, export=None, fail=False):
    events = []
    matrix = QMatrix4x4()
    matrix.perspective(45, 1.5, 0.1, 100)
    matrix.translate(1, -2, -8)
    program = _Program(matrix, events)
    gl = _GL(program, events, fail)
    view = SimpleNamespace(
        _export_size=export,
        _program=program,
        _loc_mvp=37,
        _gl=gl,
        _set_color=lambda *color: events.append(("color", color)),
        devicePixelRatioF=lambda: dpr,
    )
    return view, _VAO(events), matrix, events


@pytest.mark.parametrize("width, dpr", [(1, 1), (2, 1), (3, 1.5), (2, 2)])
def test_highlight_retains_vertex_count_depth_test_and_camera_matrix(width, dpr):
    view, vao, matrix, events = _renderer(dpr)
    color = (0.3, 0.55, 0.95, 1.0)
    rendering.Viewport._draw_edge_highlight(view, vao, 24, color, width, matrix, 1200, 800)
    draws = view._gl.draws
    offsets = rendering._highlight_jitter(width, dpr, 1200, 800)
    assert len(draws) == len(offsets)
    assert all((first, count, depth_write) == (0, 24, False)
               for first, count, depth_write, _matrix in draws)
    assert ("color", color) in events
    assert [event for event in events if event[0] == "depth_write"] == [
        ("depth_write", False), ("depth_write", True)]
    assert view._program.current == matrix
    assert view._gl.depth_write
    assert events[-1] == ("release",)
    original = matrix.map(QVector4D(0, 0, 0, 1))
    for (_first, _count, _depth, drawn), (dx, dy) in zip(draws, offsets):
        shifted = drawn.map(QVector4D(0, 0, 0, 1))
        assert shifted.x() / shifted.w() - original.x() / original.w() == pytest.approx(
            dx, abs=1e-6)
        assert shifted.y() / shifted.w() - original.y() / original.w() == pytest.approx(
            dy, abs=1e-6)
        assert shifted.z() == original.z()
        assert shifted.w() == original.w()


@pytest.mark.parametrize("count, export", [(0, None), (24, (1200, 800))])
def test_empty_or_export_pass_never_changes_gl_state(count, export):
    view, vao, matrix, events = _renderer(export=export)
    rendering.Viewport._draw_edge_highlight(
        view, vao, count, (1, 0.5, 0, 1), 3, matrix, 1200, 800)
    assert not events


def test_failed_highlight_restores_camera_depth_writes_and_vao():
    view, vao, matrix, events = _renderer(fail=True)
    with pytest.raises(RuntimeError, match="simulated driver error"):
        rendering.Viewport._draw_edge_highlight(
            view, vao, 24, (1, 0.5, 0, 1), 3, matrix, 1200, 800)
    assert view._program.current == matrix
    assert view._gl.depth_write
    assert events[-1] == ("release",)

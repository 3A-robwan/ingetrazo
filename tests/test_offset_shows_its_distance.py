# SPDX-License-Identifier: GPL-3.0-or-later
"""The Offset tool shows its live distance in the measurement box (#604).

Dragging an offset left the box empty: the tool had no ``value_label``,
which is what the box reads (rectangle sizes, push distance, ...)."""
from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QVector3D as V

from core.scene import Scene
from tools.base import ToolContext
from tools.offset import OffsetTool


class _Viewport:
    """Top view, 100 px per metre: pixel (x, y) is the point (x/100, y/100)."""

    def __init__(self, scene, face):
        self.scene, self._face = scene, face

    def _pixel_to_ray(self, sx, sy):
        return V(sx / 100.0, sy / 100.0, 10.0), V(0, 0, -1)

    def pick_face(self, sx, sy):
        return self._face

    def set_hover(self, *a):
        pass

    def update(self):
        pass


def _ctx(vp, x, y):
    return ToolContext(viewport=vp, world=V(x, y, 0),
                       screen=QPointF(x * 100.0, y * 100.0),
                       modifiers=Qt.NoModifier, snap=None)


def test_dragging_an_offset_shows_how_far():
    scene = Scene()
    face = scene.mesh.add_face([V(0, 0, 0), V(4, 0, 0), V(4, 3, 0), V(0, 3, 0)])
    vp = _Viewport(scene, face)
    tool = OffsetTool()
    tool.on_activate(vp)
    assert tool.value_label() is None             # nothing before the drag
    tool.on_hover(_ctx(vp, 2.0, 0.1))
    tool.on_click(_ctx(vp, 2.0, 0.1))              # grab near the bottom edge
    tool.on_hover(_ctx(vp, 2.0, 0.6))              # 0.6 m in from that edge
    text, at = tool.value_label()
    assert text.replace(",", ".").startswith("0.6")
    assert at is not None

# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Ctrl+A tells the rest of the program (@pacaeiro, issue #38).

Select All built the selection set by hand, behind ``Scene.select()``'s
back, so the scene version never moved: the status bar counted the
entities, the viewport drew none of them selected, Entity Info said
"nothing selected" — and the first drag with Move brought them all along.
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from PySide6.QtGui import QVector3D
from PySide6.QtWidgets import QApplication

if QApplication.instance() is None:
    QApplication(sys.argv[:1])


def V(x, y, z=0.0):
    return QVector3D(float(x), float(y), float(z))


def test_select_all_bumps_the_version_and_notifies():
    from views.main_window import MainWindow
    win = MainWindow()
    try:
        scene = win.viewport.scene
        scene.mesh.add_face([V(0, 0), V(2, 0), V(2, 2), V(0, 2)])
        seen: list = []
        win.viewport.sceneVersionChanged.connect(seen.append)

        before = scene.version
        win._on_select_all()

        assert scene.selection, "nothing selected"
        assert scene.version > before          # the GL colour caches are keyed on it
        assert seen and seen[-1] == scene.version   # and the tray hears about it
    finally:
        win._saved_version = win.viewport.scene.version
        win.close()


@pytest.mark.parametrize("edit_group", [False, True], ids=["model", "inside-group"])
def test_select_all_includes_guide_lines_and_points_in_the_edit_context(edit_group):
    from core.dimension import Dimension
    from core.group import Group
    from core.guide import Guide
    from views.main_window import MainWindow

    win = MainWindow()
    try:
        scene = win.viewport.scene
        scene.clear()
        scene.mesh.add_face([V(0, 0), V(2, 0), V(2, 2), V(0, 2)])
        parent = Group(name="Parent")
        parent.mesh.add_face([V(4, 0), V(6, 0), V(6, 2), V(4, 2)])
        child = Group(name="Child")
        child.mesh.add_face([V(8, 0), V(10, 0), V(10, 2), V(8, 2)])
        parent.adopt([child])
        sibling = Group(name="Sibling")
        sibling.mesh.add_face([V(12, 0), V(14, 0), V(14, 2), V(12, 2)])
        scene.groups.extend([parent, sibling])
        dimension = Dimension(V(0, 0), V(2, 0), V(0, -1))
        scene.dimensions.append(dimension)
        line = Guide(V(0, 3), V(1, 0))
        point = Guide(V(3, 3), origin=V(3, 0))
        scene.guides.extend([line, point])

        outside_geometry = set(scene.edges) | set(scene.faces)
        if edit_group:
            scene.begin_group_edit(parent)
        scene.edges[0].soft = True
        # Ctrl+A replaces an earlier selection instead of keeping stale entities.
        scene.selection.add(Guide(V(-1, -1)))

        win._on_select_all()

        assert {line, point} <= scene.selection
        context_groups = [child] if edit_group else [parent, sibling]
        expected = (set(scene.edges) | set(scene.faces) | set(context_groups)
                    | {dimension, line, point})
        assert scene.selection == expected
        if edit_group:
            assert scene.selection.isdisjoint(outside_geometry | {parent, sibling})
        else:
            assert child not in scene.selection
    finally:
        win._saved_version = win.viewport.scene.version
        win.close()

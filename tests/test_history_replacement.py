# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Numeric corrections replace a command without losing a valid prior result."""
from __future__ import annotations

import pytest
from PySide6.QtGui import QVector3D as V

from core.history import AddEdgeCommand, Command, History
from core.scene import Scene


def _edge(length):
    return AddEdgeCommand(V(0, 0, 0), V(length, 0, 0))


def _extent(scene):
    return max(max(e.a.x(), e.b.x()) for e in scene.mesh.edges)


def test_repeated_replacement_is_one_undo_step_with_redo():
    scene = Scene()
    history = History(scene)
    command = _edge(2)
    history.execute(command)
    for length in (3, 5, 1):
        revision = history.revision
        command = history.replace_last(command, lambda: _edge(length), revision=revision)
        assert command is history.undo_stack[-1]
        assert len(history.undo_stack) == 1
        assert history.revision == revision + 1
        assert _extent(scene) == length
    assert history.undo()
    assert not scene.mesh.edges
    assert history.redo()
    assert _extent(scene) == 1


@pytest.mark.parametrize("failure", ["invalid", "builder", "execution"])
def test_failed_replacement_preserves_geometry_history_selection_and_revision(tmp_path, failure):
    scene = Scene()
    history = History(scene)
    history.error_log = str(tmp_path / "errors.log")
    command = _edge(2)
    history.execute(command)
    selected = scene.mesh.edges[0]
    scene.selection.add(selected)
    revision = history.revision

    class BrokenCommand(Command):
        def do(self, target):
            target.mesh.add_edge(V(0, 2, 0), V(7, 2, 0))
            raise ValueError("replacement failed")

        def undo(self, target):
            raise AssertionError("failed command must never enter history")

    def build():
        if failure == "builder":
            raise ValueError("builder failed")
        return BrokenCommand() if failure == "execution" else None

    assert history.replace_last(command, build, revision=revision) is None
    assert len(scene.mesh.edges) == 1 and _extent(scene) == 2
    assert scene.selection == {selected}
    assert history.undo_stack == [command] and not history.redo_stack
    assert history.revision == revision
    assert history.replace_last(command, lambda: _edge(4), revision=revision) is not None
    assert _extent(scene) == 4


def test_undo_redo_and_other_commands_expire_a_saved_revision():
    scene = Scene()
    history = History(scene)
    command = _edge(2)
    history.execute(command)
    revision = history.revision
    history.undo()
    history.redo()
    assert history.undo_stack[-1] is command
    assert history.replace_last(command, lambda: _edge(3), revision=revision) is None
    other = AddEdgeCommand(V(0, 3, 0), V(2, 3, 0))
    history.execute(other)
    assert history.replace_last(command, lambda: _edge(3)) is None
    history.clear()
    assert history.revision > revision


def test_replacement_refuses_another_group_edit_context():
    from core.group import Group
    scene = Scene()
    history = History(scene)
    command = _edge(2)
    history.execute(command)
    revision = history.revision
    group = Group(name="Other")
    scene.groups.append(group)
    scene.begin_group_edit(group)
    assert history.replace_last(command, lambda: _edge(4), revision=revision) is None
    assert not group.mesh.edges

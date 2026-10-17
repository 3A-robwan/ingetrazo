# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Lazy meshes (the experimental engine): a format-3 block opens as a
deferred mesh whose objects are built on first touch. Built, it must be
exactly the mesh an eager open makes — same vertices, edges, faces, holes,
flags and attributes, in the same order — whatever touched it first."""
from __future__ import annotations

import copy
import random

import pytest
from PySide6.QtGui import QVector3D as V

import core._native as _native
from core import mesh as M
from core.group import Group
from core.scene import Scene
from formats import igz
from tests.test_igz_format3 import _canonical, _scene


@pytest.fixture
def binary(monkeypatch):
    monkeypatch.setattr(igz, "_LARGE_DOCUMENT", 0)
    monkeypatch.setattr(igz, "_BULK_MIN", 1)


def _open(monkeypatch, path, lazy):
    monkeypatch.setattr(_native, "wanted", lambda: lazy)
    scene = Scene()
    igz.load_into(scene, path)
    return scene


def _meshes(scene):
    """Each mesh once (placements share their prototype's)."""
    seen = set()
    for m in [scene.mesh] + [g.mesh for g in scene.groups]:
        if id(m) not in seen:
            seen.add(id(m))
            yield m


def _random_scene(rng) -> Scene:
    """Faces with holes and edges, some corners within a hair of each
    other (the weld merges them), a few placements sharing a prototype."""
    scene = Scene()

    def jitter(p):
        if rng.random() < 0.3:
            return p + V(*(rng.choice([0, 2e-6, -3e-5, 6e-5])
                           for _ in range(3)))
        return p

    def fill(m, n):
        for _ in range(n):
            o = V(*(rng.randrange(-6, 6) * 0.5 for _ in range(3)))
            w, d = rng.choice([0.5, 1, 2]), rng.choice([0.5, 1, 3])
            outer = [jitter(o + V(*q)) for q in
                     ((0, 0, 0), (w, 0, 0), (w, d, 0), (0, d, 0))]
            holes = None
            if rng.random() < 0.3:
                holes = [[o + V(w * a, d * b, 0) for a, b in
                          ((.3, .3), (.6, .3), (.6, .6), (.3, .6))]]
            try:
                f = m.add_face(outer, holes)
            except ValueError:
                continue
            if rng.random() < 0.4:
                f.attrs["color"] = [rng.random(), 0.5, 0.25]
        for _ in range(n // 3):
            a = V(*(rng.randrange(-6, 6) * 0.5 for _ in range(3)))
            e = m.add_edge(a, jitter(a + V(1, 0.5, 0)))
            e.soft = rng.random() < 0.5
            e.hidden = rng.random() < 0.2

    fill(scene.mesh, 30)
    proto = M.Mesh()
    fill(proto, 25)
    for k in range(3):
        g = Group(proto, name=f"P{k}")
        from PySide6.QtGui import QMatrix4x4
        x = QMatrix4x4()
        x.translate(k * 10, 0, 0)
        g.xform = x
        scene.groups.append(g)
    classic = Group(name="C")
    fill(classic.mesh, 20)
    scene.groups.append(classic)
    return scene


@pytest.mark.parametrize("seed", [None] + list(range(6)))
def test_built_on_touch_is_the_eager_mesh(binary, monkeypatch, tmp_path,
                                          seed):
    scene = _scene(tmp_path) if seed is None else \
        _random_scene(random.Random(seed))
    path = tmp_path / "doc.igz"
    igz.save_scene(scene, path)
    eager = _open(monkeypatch, path, False)
    lazy = _open(monkeypatch, path, True)
    assert all(type(m) is M.Mesh for m in _meshes(eager))
    deferred = [m for m in _meshes(lazy) if type(m) is M.DeferredMesh]
    assert deferred, "the binary meshes should open deferred"
    # Counted without building.
    for m in deferred:
        n = M.face_count(m)
        assert type(m) is M.DeferredMesh
        assert n == len(m.faces)
    assert _canonical(lazy) == _canonical(eager)


def test_any_first_touch_builds_it(binary, monkeypatch, tmp_path):
    """Whatever touches a deferred mesh first — a read, a lookup, a copy,
    an edit — it is built before, so the result is the eager mesh's with
    the same touch."""
    path = tmp_path / "doc.igz"
    igz.save_scene(_random_scene(random.Random(9)), path)
    touches = (lambda m: m.vertices, lambda m: m.edges, lambda m: m.faces,
               lambda m: m.vertex_at(V(0, 0, 0)),
               lambda m: m.vertex(V(0, 0, 0)), lambda m: copy.deepcopy(m),
               lambda m: m.add_edge(V(90, 0, 0), V(91, 0, 0)))
    for touch in touches:
        out = []
        for lazy in (False, True):
            scene = _open(monkeypatch, path, lazy)
            for m in _meshes(scene):
                touch(m)
                assert type(m) is M.Mesh
            out.append(_canonical(scene))
        assert out[0] == out[1], touch


def test_a_deep_copy_is_its_own_mesh(binary, monkeypatch, tmp_path):
    path = tmp_path / "doc.igz"
    igz.save_scene(_random_scene(random.Random(4)), path)
    lazy = _open(monkeypatch, path, True)
    m = lazy.groups[-1].mesh
    assert type(m) is M.DeferredMesh
    c = copy.deepcopy(m)
    assert c is not m and type(c) is M.Mesh
    assert [v.position.toTuple() for v in c.vertices] == \
        [v.position.toTuple() for v in m.vertices]
    c.add_edge(V(50, 0, 0), V(51, 0, 0))
    assert len(c.edges) == len(m.edges) + 1


def test_off_by_default_nothing_deferred(binary, monkeypatch, tmp_path):
    path = tmp_path / "doc.igz"
    igz.save_scene(_random_scene(random.Random(2)), path)
    monkeypatch.delenv("INGETRAZO_RUST", raising=False)
    monkeypatch.setattr(_native, "wanted", lambda: False)
    scene = Scene()
    igz.load_into(scene, path)
    assert all(type(m) is M.Mesh for m in _meshes(scene))


def test_defer_takes_only_an_empty_plain_mesh():
    m = M.Mesh()
    m.add_edge(V(0, 0, 0), V(1, 0, 0))
    assert not M.DeferredMesh.defer(m, lambda mesh: None, 0)
    assert type(m) is M.Mesh

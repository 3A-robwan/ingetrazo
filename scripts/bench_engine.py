# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Where the engine spends its time on a real document: the model-side
operations, timed, each with the functions that cost the most (cProfile).

The viewport side (orbit, hover with inferences, move, undo) is
``bench_interaction.py``; this one needs no window. Run it once per engine
to compare (the engine is fixed per process):

    INGETRAZO_RUST=0 venv/bin/python scripts/bench_engine.py ~/Descargas/plaza.igz \\
        --out py.json
    INGETRAZO_RUST=1 venv/bin/python scripts/bench_engine.py ~/Descargas/plaza.igz \\
        --out rs.json

``--only open,save`` picks operations; ``--top 15`` the rows of each
profile; ``--no-profile`` times without cProfile (its overhead is ~2×
on Python-heavy code, so the times to quote are the unprofiled ones)."""
from __future__ import annotations

import argparse
import cProfile
import io
import json
import os
import pstats
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Never the user's own settings (see bench_session.py).
_tmp = tempfile.mkdtemp(prefix="ingetrazo-bench-engine-")
os.environ["XDG_DATA_HOME"] = _tmp

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

QSettings.setDefaultFormat(QSettings.IniFormat)
for _scope in (QSettings.UserScope, QSettings.SystemScope):
    QSettings.setPath(QSettings.IniFormat, _scope, _tmp)
_app = QApplication.instance() or QApplication([])

from core._native import engine  # noqa: E402
from core.scene import Scene  # noqa: E402
from formats import igz  # noqa: E402


def _biggest_group(scene):
    from core.group import Group, iter_placements
    best, n = None, -1
    for g in scene.groups:
        if not isinstance(g, Group):
            continue
        k = sum(len(m.mesh.faces) for m, _ in iter_placements(g))
        if k > n:
            best, n = g, k
    return best


def op_open(ctx):
    scene = Scene()
    igz.load_into(scene, ctx["doc"])
    ctx["scene"] = scene


def op_save(ctx):
    igz.save_scene(ctx["scene"], Path(_tmp) / "out.igz")


def op_stl(ctx):
    from formats.stl import save_stl
    save_stl(ctx["scene"], Path(_tmp) / "out.stl")


def op_obj(ctx):
    from formats.obj import save_obj
    save_obj(ctx["scene"], Path(_tmp) / "out.obj")


def op_collect(ctx):
    from core.hlr import collect_geometry
    collect_geometry(ctx["scene"])


def _hlr(ctx, view):
    from core.camera import OrbitCamera
    from core.hlr import hlr_drawing
    scene = ctx["scene"]
    cam = OrbitCamera()
    cam.set_view(view)
    lo, hi = scene.bounds()
    if lo is not None:
        cam.fit_to(lo, hi)
    hlr_drawing(scene, cam)


def op_hlr_top(ctx):
    _hlr(ctx, "top")


def op_hlr_iso(ctx):
    _hlr(ctx, "iso")


def op_intersect_find(ctx):
    """Intersect Faces ▸ With Model on the biggest group: the crossings."""
    from core.intersect import WITH_MODEL, segments_for
    scene = ctx["scene"]
    g = _biggest_group(scene)
    scene.selection.clear()
    scene.selection.add(g)
    ctx["segs"] = segments_for(scene, WITH_MODEL)


def op_intersect_apply(ctx):
    """…and adding them as edges (one undo step), as the menu does."""
    from core.edits import build_add_edges
    from core.history import History
    scene = ctx["scene"]
    segs = [(a, b) for a, b in ctx.get("segs", [])
            if (b - a).length() >= 1e-4][:ctx["apply_cap"]]
    ctx["applied"] = len(segs)
    if segs:
        History(scene).execute(build_add_edges(scene, segs,
                                               detect_faces=True))


def op_orient(ctx):
    """Orient Faces over the biggest group's meshes."""
    from core.group import iter_placements
    from core.orient import orient_outward
    for m, _ in iter_placements(_biggest_group(ctx["scene"])):
        orient_outward(m.mesh)


def op_triangulate(ctx):
    """Every face triangulated again (what a full GPU rebuild asks)."""
    from core.group import iter_placements
    scene = ctx["scene"]
    for f in scene.mesh.faces:
        f.triangulate()
    for g in scene.groups:
        for m, _ in iter_placements(g):
            for f in m.mesh.faces:
                f.triangulate()


OPS = [("open", op_open), ("save", op_save), ("stl", op_stl),
       ("obj", op_obj), ("collect", op_collect), ("hlr_top", op_hlr_top),
       ("hlr_iso", op_hlr_iso), ("triangulate", op_triangulate),
       ("orient", op_orient), ("intersect_find", op_intersect_find),
       ("intersect_apply", op_intersect_apply)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("document")
    ap.add_argument("--only", default="")
    ap.add_argument("--top", type=int, default=12)
    ap.add_argument("--no-profile", action="store_true")
    ap.add_argument("--apply-cap", type=int, default=2000,
                    help="crossings added by intersect_apply (all: >15 min)")
    ap.add_argument("--out")
    args = ap.parse_args()
    only = set(filter(None, args.only.split(",")))
    ctx = {"doc": Path(args.document).expanduser(),
           "apply_cap": args.apply_cap}
    res = {"engine": engine(), "document": str(ctx["doc"]),
           "commit": os.popen("git rev-parse --short HEAD").read().strip(),
           "ops": {}}
    print(f"engine: {res['engine']}  commit {res['commit']}")
    for name, fn in OPS:
        if only and name not in only and name != "open":
            continue
        prof = None if args.no_profile else cProfile.Profile()
        t = time.perf_counter()
        if prof:
            prof.enable()
        try:
            fn(ctx)
            err = None
        except Exception as exc:  # noqa: BLE001 — report, go on
            err = f"{type(exc).__name__}: {exc}"
        if prof:
            prof.disable()
        dt = time.perf_counter() - t
        row = {"s": round(dt, 3)}
        if err:
            row["error"] = err
        if name == "intersect_find":
            row["crossings"] = len(ctx.get("segs", []))
        if name == "intersect_apply":
            row["applied"] = ctx.get("applied", 0)
        if prof:
            buf = io.StringIO()
            st = pstats.Stats(prof, stream=buf)
            st.sort_stats("tottime")
            rows = []
            for (file, line, func), (_cc, nc, tt, ct, _c) in sorted(
                    st.stats.items(), key=lambda kv: -kv[1][2])[:args.top]:
                rows.append({"func": f"{Path(file).name}:{line}:{func}",
                             "calls": nc, "self_s": round(tt, 3),
                             "cum_s": round(ct, 3)})
            row["top"] = rows
        res["ops"][name] = row
        extra = "".join(f"  {k}={row[k]}" for k in ("crossings", "applied",
                                                    "error") if k in row)
        print(f"{name:>16}: {dt:9.2f} s{extra}")
        for r in row.get("top", [])[:5]:
            print(f"{'':>18}{r['self_s']:8.2f} s self  {r['func']}")
    if args.out:
        Path(args.out).write_text(json.dumps(res, indent=1, ensure_ascii=False))
        print("saved", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())

# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Line tool: click points to draw edges; auto-close polygons.

Behavior follows the classic convention:
- First click sets the start point of a fresh chain.
- Each next click finalises a segment and chains into the next one.
- Snapping to the chain's first point (snap kind ``"close"``) finishes the
  polygon and resets the chain.
- Esc cancels the chain without committing the pending segment.
- Retyping a length immediately after a segment corrects that segment.
  Moving the mouse first starts the next direction in the chain instead.

The tool exposes ``start_point``, ``hover_point`` and ``chain_first_point``
so the viewport can:
  * draw the rubber-band preview during ``paintGL``,
  * feed those into the snap engine for close-polygon detection.
"""
from __future__ import annotations

import math

from PySide6.QtGui import QVector3D

from core.edits import build_add_edge
from core.history import AddEdgeCommand, Command
from tools.base import Tool, ToolContext


class _LineEdgeCommand(AddEdgeCommand):
    """Undo a simple segment without leaving its new endpoints behind."""

    def __init__(self, edge_command) -> None:
        super().__init__(edge_command.a, edge_command.b, merge=edge_command.merge,
                         soft=edge_command.soft, curve=edge_command.curve)
        self._created_vertices = None

    def do(self, scene) -> None:
        if self._created_vertices is None:
            missing = [p for p in (self.a, self.b) if scene.mesh.vertex_at(p) is None]
            super().do(scene)
            self._created_vertices = [scene.mesh.vertex_at(p) for p in missing]
        else:
            scene.mesh.relink_vertices(self._created_vertices)
            super().do(scene)

    def undo(self, scene) -> None:
        super().undo(scene)
        scene.mesh.drop_orphan_vertices(self._created_vertices or ())


class LineTool(Tool):
    name = "Line"
    shortcut = "L"
    description = "Draw edges point by point; closing a loop makes a face."
    vcb_label = "Length"

    #: The axis inference MAGNETISES, it does not merely light up.
    #:
    #: @pacaeiro (issue #31): «The Soft inference of Axis shows the message
    #: "In Red Axis (hold Shift to lock)", but only when we hit Shift the
    #: Vector gets aligned with the X. It should magnetically align with
    #: the axis (like other snap point). That allows to write a distance
    #: and press Enter, finishing the line in the vector X.»
    #:
    #: He is right, and measured it is worse than "not aligned": the label
    #: was a promise the engine did not keep. Within the inference angle
    #: the point came back RAW — 2, 5, 8 cm off the axis at a 2 m reach —
    #: while the status bar said you were on it. Shift is for pinning a
    #: direction while you go hunting for a snap point elsewhere, not for
    #: the everyday case of drawing something straight.
    #:
    #: The value is the soft inference angle, not Move's generous 15°, so
    #: WHEN the cue appears is exactly as before and only WHAT it returns
    #: changes. Drawing deliberately off-axis by a couple of degrees stays
    #: possible; the toggle Alt still switches it off entirely.
    magnetic_axis_deg = 3.0

    #: …and the axes that the one above CANNOT reach, found in pixels.
    #:
    #: @pacaeiro (issue #31, second point): «in certain viewport positions,
    #: is impossible to get Inference of the 3 axis (X, Y, Z)». Measured
    #: over the whole camera grid, every camera reaches exactly TWO and
    #: never three — x/y from the top, x/z from the front, y/z from the
    #: side — because the cursor becomes a world point by landing on the
    #: work plane, and a plane holds at most two of the three axes. Drawing
    #: in plan, blue does not exist; from the front, green does not.
    #:
    #: The engine consults this only where the world detector found
    #: nothing, so the two axes that already worked keep coming from where
    #: they always did. The threshold is the one point snaps already use
    #: rather than a new constant of its own.
    screen_axis_px = 9.0

    def __init__(self) -> None:
        self.start_point: QVector3D | None = None
        self.hover_point: QVector3D | None = None
        self.chain_first_point: QVector3D | None = None
        # Ordered list of vertices in the current chain. Populated as the
        # user clicks; consumed to build a Face when the chain auto-closes.
        self.chain_vertices: list[QVector3D] = []
        # (point, normal) of the face the chain was started on, if any.
        # The viewport reads this to keep subsequent points coplanar.
        self.work_plane: tuple[QVector3D, QVector3D] | None = None
        self._last: dict | None = None
        self._hover_screen: tuple | None = None
        self._chain_context: tuple | None = None

    # ---- Lifecycle ----------------------------------------------------------
    def on_activate(self, viewport) -> None:
        self._reset()

    def on_deactivate(self, viewport) -> None:
        self._reset()
        self.hover_point = None

    # ---- Spatial input ------------------------------------------------------
    def on_click(self, ctx: ToolContext) -> None:
        self._check_context(ctx.viewport)
        self._last = None
        self._hover_screen = (ctx.screen.x(), ctx.screen.y())
        clicked = ctx.world
        if self.start_point is None:
            self.start_point = clicked
            self.hover_point = clicked
            self.chain_first_point = clicked
            self.chain_vertices = [clicked]
            self._chain_context = self._context(ctx.viewport)
            return

        if (clicked - self.start_point).length() < 1e-9:
            # The start itself: nothing to draw. Reachable on purpose since
            # issue #34 — under a lock, a reference level with the start
            # shows its guide and lands here — and it used to go to the
            # history as a degenerate edge and come back as a noisy
            # rollback.
            return
        self._commit_segment(ctx.viewport, clicked)

    def on_hover(self, ctx: ToolContext) -> None:
        self._check_context(ctx.viewport)
        screen = (ctx.screen.x(), ctx.screen.y())
        if (self._last is not None and self._last["screen"] is not None
                and screen != self._last["screen"]):
            # Keyboard/snap refreshes reuse the pixel and keep the edit
            # window. A real mouse move points out the NEXT segment.
            self._last = None
        self._hover_screen = screen
        self.hover_point = ctx.world
        ctx.viewport.update()

    def on_cancel(self, viewport) -> None:
        self._reset()
        viewport.update()

    def on_undo(self, viewport) -> bool:
        """Ctrl+Z in the middle of a chain (@pacaeiro, #175: «the last
        picked point is not freed»). The segment just drawn is undone and
        the chain steps back to its previous vertex, so the rubber band
        leaves from where the line now really ends. With only the first
        point placed there is nothing of this chain to undo: the point is
        let go. Idle, the ordinary undo runs."""
        self._last = None
        self._hover_screen = None
        if self.start_point is None:
            return False
        if len(self.chain_vertices) > 1:
            if not viewport.history.undo():
                self._reset()
                viewport.update()
                return True
            self.chain_vertices.pop()
            self.start_point = self.chain_vertices[-1]
            if len(self.chain_vertices) == 1:
                self.chain_first_point = self.start_point
        else:
            self._reset()
        viewport.update()
        return True

    def rubber_band_lines(self):
        if self.start_point is None or self.hover_point is None:
            return []
        return [(self.start_point, self.hover_point)]

    def on_value(self, viewport, value) -> bool:
        """Commit a segment from the VCB input.

        ``value`` is either:
        - ``float``  → length along the current rubber-band direction
                        (negative = the opposite way, the usual convention).
        - 3-tuple    → ``(dx, dy, dz)`` delta added to the start point,
                        which makes inclined / elevated lines trivial to
                        construct numerically (start, then type "3;4;5"
                        for a +3 X, +4 Y, +5 Z delta).
        """
        if not self._check_context(viewport):
            return False
        last = self._last
        if (last is not None and last["screen"] is None and self.hover_point is not None
                and (self.hover_point - last["endpoint"]).length() > 1e-9):
            # Script callers can set a new rubber-band point directly,
            # without delivering mouse events or screen coordinates.
            self._last = last = None
        if last is not None:
            history = viewport.history
            if (history is not last["history"] or history.revision != last["revision"]
                    or not history.undo_stack or history.undo_stack[-1] is not last["cmd"]):
                self._reset()
                return False
            endpoint = self._value_endpoint(value, last["start"], last["direction"])
            if endpoint is None:
                return False
            cmd = history.replace_last(
                last["cmd"], lambda: self._commit_edge(viewport, last["start"], endpoint),
                revision=last["revision"])
            if cmd is None:
                last["content_version"] = viewport.scene.content_version
                return False
            last.update(cmd=cmd, revision=history.revision, endpoint=QVector3D(endpoint),
                        content_version=viewport.scene.content_version)
            self._finish_segment(last, endpoint)
            self._last = last
            viewport.update()
            return True
        if self.start_point is None:
            return False
        direction = (self.hover_point - self.start_point
                     if self.hover_point is not None else None)
        endpoint = self._value_endpoint(value, self.start_point, direction)
        return endpoint is not None and self._commit_segment(viewport, endpoint)

    # ---- Internals ----------------------------------------------------------
    @staticmethod
    def _value_endpoint(value, start, direction):
        if isinstance(value, bool):
            return None
        try:
            if isinstance(value, tuple):
                if len(value) != 3 or not all(math.isfinite(float(v)) for v in value):
                    return None
                delta = QVector3D(*(float(v) for v in value))
            else:
                length = float(value)
                if (not math.isfinite(length) or direction is None
                        or direction.length() < 1e-9):
                    return None
                delta = direction.normalized() * length
        except (TypeError, ValueError, OverflowError):
            return None
        endpoint = start + delta
        if (not all(math.isfinite(v) for v in (endpoint.x(), endpoint.y(), endpoint.z()))
                or delta.length() < 1e-9):
            return None
        return endpoint

    @staticmethod
    def _context(viewport):
        return viewport.scene, viewport.scene.mesh, getattr(viewport.scene, "edit_group", None)

    def _check_context(self, viewport) -> bool:
        context = self._last["context"] if self._last is not None else self._chain_context
        changed = (self._last is not None
                   and self._last["content_version"] != viewport.scene.content_version)
        if changed or (context is not None and any(
                a is not b for a, b in zip(context, self._context(viewport)))):
            self._reset()
            return False
        return True

    def _commit_segment(self, viewport, endpoint) -> bool:
        start = QVector3D(self.start_point)
        before = [QVector3D(p) for p in self.chain_vertices] or [QVector3D(start)]
        first = QVector3D(self.chain_first_point) if self.chain_first_point is not None else before[0]
        last = {"start": start, "direction": (endpoint - start).normalized(),
                "endpoint": QVector3D(endpoint), "vertices": before, "first": first,
                "plane": self.work_plane, "screen": self._hover_screen,
                "context": self._context(viewport), "history": viewport.history}
        try:
            cmd = self._commit_edge(viewport, start, endpoint)
        except Exception:
            return False
        viewport.history.execute(cmd)
        if not viewport.history.undo_stack or viewport.history.undo_stack[-1] is not cmd:
            return False
        last.update(cmd=cmd, revision=viewport.history.revision,
                    content_version=viewport.scene.content_version)
        self._finish_segment(last, endpoint)
        self._last = last
        viewport.update()
        return True

    def _finish_segment(self, last, endpoint) -> None:
        if len(last["vertices"]) >= 3 and (endpoint - last["first"]).length() < 1e-6:
            self._reset()
        else:
            self.chain_vertices = [QVector3D(p) for p in last["vertices"]] + [QVector3D(endpoint)]
            self.start_point = QVector3D(endpoint)
            self.chain_first_point = QVector3D(last["first"])
            self.work_plane = last["plane"]
            self._chain_context = last["context"]
        self.hover_point = QVector3D(endpoint)
        self._hover_screen = last["screen"]

    def _commit_edge(self, viewport, start: QVector3D, end: QVector3D) -> Command:
        """Build the command for a new edge. ``build_add_edge`` welds
        coincident edges, splits any existing edge the new one crosses
        (introducing a shared vertex), and attaches a face when the new edge
        closes a planar cycle — the classic "any planar loop becomes a
        face" behaviour, now correct even when the loop relies on a crossing."""
        cam = getattr(viewport, "camera", None)
        eye = cam.eye() if cam is not None and hasattr(cam, "eye") else None
        cmd = build_add_edge(viewport.scene, start, end, detect_faces=True, eye=eye)
        return _LineEdgeCommand(cmd) if type(cmd) is AddEdgeCommand else cmd

    def _reset(self) -> None:
        self.start_point = None
        self.chain_first_point = None
        self.chain_vertices = []
        self.work_plane = None
        self._last = None
        self._hover_screen = None
        self._chain_context = None

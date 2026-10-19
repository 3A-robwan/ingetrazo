# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""The viewport's snapping inference, in one place.

``Viewport`` had grown a small state machine -- the edge and centre under the
cursor, the reference edge/corner acquired while drawing, the encouraged
points the cursor paused on, the axis and reference locks, the snap search
itself -- threaded through a dozen private attributes and half a dozen
methods. Keeping it beside the widget made every one of those methods read as
part of the drawing surface.

This collaborator owns that state and its rules. The viewport still hands it
the cursor (``_process_hover`` reads the picks through :meth:`acquire`, and
``_build_ctx`` / ``_refresh_snap`` ask :meth:`snap`) and renders what it
decides (``_snap_scene``, ``_draw_overlay``), but the "which point is the
reference, what is encouraged, which axis is locked" bookkeeping lives here.
The dialogue is one-way -- the engine reaches back to the viewport for the
picks, the projections and a repaint, never the other way -- and the viewport
exposes thin delegating properties so the rest of the class, tools,
extensions, the probe and the tests keep reading ``vp._acquired_point``,
``vp.axis_lock`` and friends unchanged.

The two post-processors that used to run on the viewport at the end of
the search -- the axis-source cue (the Tape hovering a model axis) and
the extension hooks -- now run at the end of :meth:`snap`, so what the
viewport draws is what the engine decided, with no second pass.
"""
from __future__ import annotations

import math
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QVector3D

from core.guide import Guide
from core.snap import COLOR_REFERENCE, SnapResult, compute_snap


def _no_snap_fast() -> bool:
    """The viewport's ``INGETRAZO_NO_SNAP_FAST`` switch (batched occlusion
    off, for A/B timing), read at call time to avoid a circular import."""
    from views import viewport as _viewport
    return bool(getattr(_viewport, "_NO_SNAP_FAST", False))


class InferenceEngine:
    """Snap-target state the viewport keeps between moves.

    The reference state -- the edge and centre under the cursor, the
    'from point' reference and the soft references held while a segment is
    drawn, the two encouraged points behind it, the axis / reference locks
    and the last snap result -- plus the search that reads them. The dwell
    timers turn pauses over points and edge interiors into references. Both
    are parented to the viewport and die with it.
    """

    def __init__(self, viewport) -> None:
        self.viewport = viewport
        # Arrow-key axis lock: None | "x" | "y" | "z".
        self.axis_lock: Optional[str] = None
        # The snap engine's last answer, kept for the marker and readouts.
        self.last_snap: Optional[SnapResult] = None
        # Reference edge (Down arrow -- parallel / perpendicular): the edge
        # and the mode it was taken in.
        self.reference_edge = None
        self.reference_mode: Optional[str] = None
        # Sticky inference lock (Shift): (direction, color) captured from the
        # active inference, held until Shift is released.
        self._shift_lock: Optional[tuple] = None
        # Last edge under the cursor (candidate for capture) and the centre of
        # the last circle or arc the cursor visited (its edge, or a face it
        # bounds), kept as a reference until another circle takes its place or
        # the tool changes.
        self._hover_edge = None
        self._hover_center = None
        # ``(centre, radius, key, version, source, mesh, group)``.
        self._center_ref = None
        # Edge/face hovered while drawing, held as soft references
        # ("through point" / "perpendicular to face" acquisition). Cleared
        # when no segment is in progress.
        self._acquired_edge = None
        self._acquired_face_normal = None
        # Corner hovered while drawing, held as a soft reference ("from
        # point" / the axis lines that run off it). Cleared when no segment is
        # in progress.
        self._acquired_point: Optional[QVector3D] = None
        # Encouraged points: the last two points the cursor PAUSED on (a
        # corner, a circle's centre). The 'from point' dotted line runs from
        # them -- from both at once where their axis lines cross. Pausing, not
        # merely crossing: sweeping over a vertex on the way somewhere else
        # must not steal the reference.
        self._encouraged: list = []
        self._dwell_point: Optional[QVector3D] = None
        self._dwell_timer = QTimer(viewport)
        self._dwell_timer.setSingleShot(True)
        self._dwell_timer.setInterval(viewport.ENCOURAGE_MS)
        self._dwell_timer.timeout.connect(self._encourage_dwelt)
        # A direction reference needs a deliberate pause on an edge body.
        # Keep it separate from point encouragement and from the hover edge
        # used by highlighting and the explicit Down-arrow reference lock.
        self._edge_dwell_edge = None
        self._edge_dwell_key = None
        self._edge_dwell_anchor = None
        self._edge_cursor_px = None
        self._edge_context = None
        self._edge_reference_key = None
        self._edge_dwell_timer = QTimer(viewport)
        self._edge_dwell_timer.setSingleShot(True)
        self._edge_dwell_timer.setTimerType(Qt.PreciseTimer)
        self.set_parallel_edge_dwell_ms(getattr(viewport, "parallel_edge_dwell_ms", 500))
        self._edge_dwell_timer.timeout.connect(self._acquire_dwelt_edge)

    # ---- Picking the cursor's neighbourhood ---------------------------------
    def acquire(self, px: float, py: float) -> None:
        """Refresh the hover state :meth:`snap` reads: the edge under the
        cursor, the centre it may encourage, and the soft references held
        while a segment is being drawn.

        Called on every hover, before the tools see it. A tool that does not
        snap (Select, Push/Pull) still gets its hover edge (the highlight),
        but never pays for the centre fit; the drawing references are only
        refreshed while a segment is in progress, so they cannot go stale
        across separate draws."""
        vp = self.viewport
        tool = vp.active_tool
        self._edge_cursor_px = (px, py)
        if tool is not None and (tool.uses_snap
                                 or getattr(tool, "hover_group_edges", False)):
            self._hover_edge = vp.pick_edge_any(px, py)
        else:
            self._hover_edge = vp.pick_edge(px, py)
        if tool is not None and tool.uses_snap:
            # Only the tools that snap can use a centre; Select and Push/Pull
            # never pay for the fit. Hovering the rim ENCOURAGES the centre
            # like a corner: the dotted axis line then runs from it (Marco's
            # capture, 2026-09-14 -- a circle placed in line with another's
            # centre).
            self._hover_center = vp._update_center_ref(px, py)
        drawing = (tool is not None
                   and getattr(tool, "start_point", None) is not None)
        corner = None
        if drawing and tool.uses_snap:
            # Mid-segment: the corner under the cursor is a soft, instant
            # reference (through point / from point), as always.
            corner = vp.pick_vertex(px, py)
            if corner is not None:
                self._acquired_point = corner
        context = self._drawing_context()
        if context != self._edge_context:
            self._cancel_edge_dwell()
            self._acquired_edge = None
            self._edge_reference_key = None
            self._edge_context = context
        if context is None:
            self._acquired_edge = None
            self._acquired_face_normal = None
        else:
            edge = self._pick_reference(px, py, self._hover_edge)
            edge = self._interior_edge(edge, px, py, corner)
            self._dwell_on_edge(edge, px, py)
            face, _g = vp.pick_face_placement(px, py)
            if face is not None:
                from core.snap import face_plane_world
                self._acquired_face_normal = face_plane_world(
                    face, getattr(_g, "xform", None))[1]

    def set_parallel_edge_dwell_ms(self, delay_ms: int) -> None:
        """Apply a new edge dwell interval and cancel any unfinished pause."""
        try:
            delay = float(delay_ms)
            delay = round(delay) if math.isfinite(delay) else 500
        except (TypeError, ValueError, OverflowError):
            delay = 500
        delay = max(100, min(10000, delay))
        self.viewport.parallel_edge_dwell_ms = delay
        self._cancel_edge_dwell()
        self._edge_dwell_timer.setInterval(delay)

    def _drawing_context(self):
        """A soft reference belongs to this tool's current drawing step."""
        vp = self.viewport
        tool = getattr(vp, "active_tool", None)
        start = getattr(tool, "start_point", None)
        if start is None or not getattr(tool, "uses_snap", False):
            return None
        scene = vp.scene
        return (id(scene), id(scene.mesh), id(getattr(scene, "edit_group", None)),
                id(tool), (start.x(), start.y(), start.z()),
                getattr(getattr(vp, "history", None), "revision", None))

    @staticmethod
    def _edge_key(edge):
        if isinstance(edge, Guide):
            # Infinite construction lines have no real endpoints. Their
            # anchor and direction remain stable while the camera changes.
            return ("guide", id(edge),
                    (edge.point.x(), edge.point.y(), edge.point.z()),
                    (edge.direction.x(), edge.direction.y(), edge.direction.z()))
        # Group picks create fresh world-space proxies on every mouse event.
        # Their geometry and owner, rather than proxy identity, define a pause.
        a = (edge.a.x(), edge.a.y(), edge.a.z())
        b = (edge.b.x(), edge.b.y(), edge.b.z())
        return (tuple(sorted((a, b))), id(getattr(edge, "group", None)),
                getattr(edge, "context", None))

    def _pick_reference(self, px, py, edge):
        picker = getattr(self.viewport, "pick_parallel_reference", None)
        return picker(px, py, edge) if callable(picker) else edge

    def _interior_edge(self, edge, px, py, corner):
        if edge is None or corner is not None:
            return None
        if isinstance(edge, Guide):
            return edge if edge.is_line else None
        if (edge.b - edge.a).lengthSquared() < 1e-12:
            return None
        vp = self.viewport
        radius = getattr(vp, "snap_threshold_px", 9)
        for point in (edge.a, edge.b):
            pixel = vp._world_to_pixel(point)
            if pixel is not None and math.hypot(pixel[0] - px, pixel[1] - py) <= radius:
                return None
        return edge

    def _cancel_edge_dwell(self):
        self._edge_dwell_timer.stop()
        self._edge_dwell_edge = None
        self._edge_dwell_key = None
        self._edge_dwell_anchor = None

    def _dwell_on_edge(self, edge, px, py):
        if edge is None:
            self._cancel_edge_dwell()
            return
        key = self._edge_key(edge)
        if key == self._edge_reference_key:
            self._cancel_edge_dwell()
            return
        anchor = self._edge_dwell_anchor
        if (key != self._edge_dwell_key or anchor is None
                or math.hypot(px - anchor[0], py - anchor[1]) > 3):
            self._edge_dwell_key = key
            self._edge_dwell_anchor = (px, py)
            self._edge_dwell_timer.start()
        self._edge_dwell_edge = edge

    def _acquire_dwelt_edge(self):
        """Complete a stationary pause even when no new mouse event arrives."""
        if self._edge_dwell_edge is None:
            return
        context = self._drawing_context()
        if context is None or context != self._edge_context:
            self._cancel_edge_dwell()
            self._acquired_edge = None
            self._edge_reference_key = None
            self._edge_context = context
            return
        vp = self.viewport
        px, py = self._edge_cursor_px
        edge = self._pick_reference(px, py, vp.pick_edge_any(px, py))
        edge = self._interior_edge(edge, px, py, vp.pick_vertex(px, py))
        # A stale pick must not resurrect an edge deleted during the pause.
        # Real mesh edges retain their identity; world-space group proxies
        # are revalidated by picking again and comparing geometry and owner.
        from core.mesh import Edge
        if isinstance(edge, Edge) and edge not in vp.scene.mesh.edges:
            edge = None
        if edge is None or self._edge_key(edge) != self._edge_dwell_key:
            self._cancel_edge_dwell()
            return
        self._acquired_edge = edge
        self._edge_reference_key = self._edge_dwell_key
        self._cancel_edge_dwell()
        refresh = getattr(vp, "_refresh_snap", None)
        if callable(refresh):
            refresh()
        vp.update()

    # ---- The snap search -----------------------------------------------------
    def snap(self, px_x: float, px_y: float,
             modifiers) -> Optional[SnapResult]:
        """The snap engine's answer for the cursor at ``(px_x, px_y)``.

        THE one code path: both ``_build_ctx`` (mouse motion and clicks) and
        ``_refresh_snap`` (a modifier changing with the hand still) go through
        here, so the :func:`compute_snap` argument list lives in exactly one
        place. Returns ``None`` when the pixel casts no world point (the ray
        misses the plane / the point is behind the camera). A tool that does
        not snap (Select, Push/Pull) gets a ``"none"`` result instead - no
        snap engine, no occlusion raycasts, no marker."""
        vp = self.viewport
        world_raw = vp._world_from_pixel(px_x, px_y)
        if world_raw is None:
            return None
        tool = vp.active_tool
        if tool is not None and not tool.uses_snap:
            return SnapResult(world_raw, "none")
        chain_first = None
        start_pt = None
        if tool is not None:
            chain_first = getattr(tool, "chain_first_point", None)
            start_pt = getattr(tool, "start_point", None)
        snap = compute_snap(
            candidate_world=world_raw,
            candidate_pixel=(px_x, px_y),
            scene=vp._snap_scene(px_x, px_y),
            world_to_pixel=vp._world_to_pixel,
            threshold_px=vp.snap_threshold_px,
            project_onto_line=lambda s, d: vp._project_to_lock_line(
                s, d, px_x, px_y),
            chain_first_point=chain_first,
            start_point=start_pt,
            axis_lock=self.axis_lock,
            shift_held=bool(modifiers & Qt.ShiftModifier),
            reference_edge=self.reference_edge,
            reference_mode=self.reference_mode,
            inference_angle_deg=vp.inference_angle_deg,
            is_occluded=vp._is_occluded,
            are_occluded=None if _no_snap_fast() else vp._occluded_many,
            face_under_cursor=vp._still_face_under(px_x, px_y),
            edge_threshold_px=vp.edge_snap_threshold_px,
            magnetic_axis_deg=getattr(tool, "magnetic_axis_deg", None),
            screen_axis_px=getattr(tool, "screen_axis_px", None),
            acquired_edge=self._acquired_edge,
            acquired_point=self._acquired_point,
            acquired_face_normal=self._acquired_face_normal,
            acquired_points=self._encouraged,
            shift_lock_dir=self._shift_lock[0] if self._shift_lock else None,
            shift_lock_color=self._shift_lock[1] if self._shift_lock else None,
            linear_mode=vp.linear_inference_mode,
            work_plane_normal=vp._work_plane_normal(),
            radial_arm=bool(getattr(tool, "radial_arm", False)),
        )
        snap = self._axis_source_cue(snap, px_x, px_y)
        snap = self._extension_snap(snap, px_x, px_y)
        # A parallel landing is a point target, not an invitation to replace
        # its direction with the edge being landed on. Acquire runs BEFORE
        # this search, so cancel its pending pause using this frame's result.
        # Keep point encouragement: it must not steal the confirmed edge.
        if (self._acquired_edge is not None and start_pt is not None
                and snap.kind == "intersection" and snap.guide is not None
                and snap.guide_color == COLOR_REFERENCE
                and (snap.guide[0] - start_pt).length() < 1e-6):
            self._cancel_edge_dwell()
        return snap

    # ---- Post-processors (axis-source cue, extensions) ----------------------

    #: Built-in inferences an extension's may not override: a point with a
    #: name is the user's target, and the snap engine already ranked it.
    _NAMED_SNAPS = frozenset((
        "endpoint", "midpoint", "arc_midpoint", "center", "origin",
        "component_origin", "intersection", "close", "on_edge"))

    def _axis_source_cue(self, snap, px_x: float, px_y: float):
        """Before its first click, a tool that reads the model axes as a
        source (the Tape: ``axis_source``) shows the cursor is ON the red,
        green or blue axis — the classic small square on the axis line.
        Without the cue the axis looked ungrabbable (Marco, testing
        Rafael's guide from an axis, 2026-09-21): the pick worked, nothing
        said so. Only where the engine found nothing better.

        The pick itself stays on the viewport (``pick_axis`` is a general
        pick, the Tape reads it too): the engine calls it, the same shape as
        ``_snap_scene`` / ``pick_face_any``."""
        vp = self.viewport
        tool = vp.active_tool
        if (snap is None or not getattr(tool, "axis_source", False)
                or getattr(tool, "start_point", None) is not None
                or snap.kind not in ("none", "on_face")):
            return snap
        name = vp.pick_axis(px_x, px_y)
        if name is None:
            return snap
        from core.snap import AXIS_COLORS
        from core import axes as _axes
        axis = _axes.axis(name)
        o = _axes.origin()
        foot = o + axis * QVector3D.dotProduct(snap.point - o, axis)
        return SnapResult(foot, "on_axis", AXIS_COLORS[name], axis=name)

    def _extension_snap(self, snap, px_x: float, px_y: float):
        """Offer the snap engine's answer to each extension's provider
        (``ExtensionApp.add_snap_provider``); the first that returns a
        :class:`SnapResult` wins. A named point is never overridden, and a
        provider that raises is skipped — it cannot take the cursor away.

        The provider signature is unchanged: ``fn(viewport, snap, px, py)``.
        It is handed the viewport, not this engine, so no plugin has to know
        the snap search moved.

        Careful with the homonym: ``core.snap._extension_snap`` is the
        *geometric* extension inference inside ``compute_snap`` (step 5 of the
        search — an edge's dashed continuation, green connection points);
        this one is the *extension-API* provider hook."""
        vp = self.viewport
        providers = getattr(vp, "_ext_snap_providers", None)
        if not providers or snap is None or snap.kind in self._NAMED_SNAPS:
            return snap
        for fn in list(providers):
            try:
                got = fn(vp, snap, px_x, px_y)
            except Exception:  # noqa: BLE001 — a plugin never breaks input
                import logging
                logging.getLogger("ingetrazo.plugins").exception(
                    "extension snap provider failed")
                continue
            if got is not None:
                return got
        return snap

    # ---- Encouraged points --------------------------------------------------
    def _dwell_on(self, point: Optional[QVector3D]) -> None:
        """The cursor is over ``point`` (or nothing): (re)start the pause
        that turns it into an encouraged point."""
        if point is None:
            self._dwell_point = None
            self._dwell_timer.stop()
            return
        if (self._dwell_point is not None
                and (self._dwell_point - point).length() < 1e-6):
            return                                  # still resting on it
        self._dwell_point = QVector3D(point)
        self._dwell_timer.start()

    def _encourage_dwelt(self) -> None:
        if self._dwell_point is not None:
            self.encourage_point(self._dwell_point)

    def encourage_point(self, point: QVector3D) -> None:
        """Make ``point`` the newest encouraged point (two are kept, the
        older one drops), and the 'from point' reference."""
        pt = QVector3D(point)
        self._encouraged = [p for p in self._encouraged if (p - pt).length() > 1e-6]
        self._encouraged.append(pt)
        del self._encouraged[:-2]
        self._acquired_point = pt
        self.viewport.update()

    def clear_references(self) -> None:
        """Drop cursor-acquired and encouraged model references."""
        self._dwell_timer.stop()
        self._cancel_edge_dwell()
        self._edge_context = None
        self._edge_reference_key = None
        self._edge_cursor_px = None
        self._dwell_point = None
        self._hover_edge = None
        self._hover_center = None
        self._center_ref = None
        self._acquired_edge = None
        self._acquired_face_normal = None
        self._acquired_point = None
        self._encouraged = []
        self.last_snap = None

    def reset(self) -> None:
        """Forget every inference state tied to the current document."""
        self.clear_references()
        self.axis_lock = None
        self.reference_edge = None
        self.reference_mode = None
        self._shift_lock = None

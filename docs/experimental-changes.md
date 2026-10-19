# Experimental community changes (19 October 2026)

This is an **unofficial source-code preview**, published by `3A-robwan` for
others to try and review. It is based on upstream commit
`d8ee8c068f0b1a26fe1a84a8489d3facb3fa22bf` (13 October 2026), whose application
version is 0.5.8. It does not include every later upstream change and is not an
official IngeTrazo release. The application still reports 0.5.8.

IngeTrazo is created by Marco Sumari Tellez and its contributors. Original
attribution and the GPL-3.0-or-later license are preserved.

The [19 October source preview](https://github.com/3A-robwan/ingetrazo/releases/tag/robwan-experimental-2026-10-19)
includes the erase, inference, highlight, rounded-inset and occluded-edge fixes
below, plus `AGENTS.md` and `HANDOFF.md` for continued work. It follows the
18 October preview (`514ff84`), which contains only the earlier guide transforms,
numeric corrections and Shift navigation changes.

## Changes

- **Occluded edge picking:** the Eraser hover and stroke ignore edges hidden
  behind faces, including Shift-hide and Delete from hover. Select and Eraser
  now test the actual point under the cursor on perspective edges, including
  two-point perspective. Orthographic visibility follows parallel view rays
  in both single and batched checks, with stable on-face precision at large
  camera distances. Box selection, whole-curve expansion and X-ray/wireframe
  retain their existing rules.
- **Rounded inset corners on existing faces:** trimming a fillet also updates
  the surrounding face's hole boundary to follow the arc. The corner patch
  becomes part of that surrounding face, and the obsolete vertex is removed,
  preventing later moves from dragging or rebuilding invisible connections.
  Undo/Redo and post-operation radius/segment corrections preserve the shared
  boundary. Alt still keeps the corner stubs.
- **Perpendicular lines aligned with a remembered point:** hover the midpoint
  of an adjacent rectangle edge, then draw perpendicular from the starting
  edge's midpoint. The dotted reference remains and the endpoint snaps exactly
  to the rectangle centre. Acquired points can set length along active axes,
  perpendicular or parallel directions without pulling the line off them.
  Preview colours and Shift direction capture are retained at the point.
- **Edge highlight widths:** Preferences > General now has separate 1–3 px
  controls for the blue hovered edge and orange selected edges, both defaulting
  to 2. OK persists and applies them immediately; Cancel keeps the old values.
  Widths scale with the display and are drawn with depth-tested offset passes,
  so they also work on drivers which limit GL line widths. The blue hover keeps
  priority over orange selection; curves and group selection boxes follow the
  same drawing path. General preferences scroll on smaller screens.
- **Parallel edge inference:** pause on an edge interior for 0.5 seconds to
  remember its direction while drawing. Crossing another edge or vertex does
  not replace it immediately. A parallel line lands at the exact crossing with
  the target edge and keeps its magenta preview; Shift can lock that direction
  at the crossing too. Vertices do not acquire edge directions. Preferences >
  General > **Edge hover time for parallel inference** sets a persistent delay
  from 0.1 to 10 seconds, applied on OK. Small cursor jitter is tolerated;
  moving along the edge restarts the pause. Leaving the view or navigating it
  cancels an unfinished pause while preserving a confirmed reference.
  Pausing at a parallel crossing keeps the original direction reference,
  including after point encouragement; moving away and returning still snaps
  exactly to that crossing. A deliberate pause elsewhere on another edge can
  still replace the reference.
- **Parallel references from construction lines:** hovering a guide line uses
  the same delay setting as hovering an edge. Its stored direction supplies
  the parallel cue, exact edge crossings and Shift locking. Guide points and
  their drawn origin connectors do not supply directions; hidden, occluded or
  transform-excluded construction lines are ignored. Direction acquisition
  preserves the guide's coordinates and the existing model-edge hover picks.
- **Construction guide selection:** Ctrl+A includes guide lines and points.
- **Selected-segment deletion:** erasing one segment of a closed outline drawn
  on an existing face keeps every unselected hard segment as an open line on
  the healed face. Multiple selected segments, Undo/Redo and closing the outline
  again are supported. The default seam cleanup used by stitching is unchanged.
- **Guide transforms:** Move (M) and Rotate (Q) accept selected construction
  lines/points and can pick a guide directly. Live preview, axis constraints,
  Ctrl-copy, linear/polar copy arrays, cancellation and Undo/Redo work with them.
  A guide point's drawn origin travels with the point. Mixed selections of
  guides and geometry are supported, including the group preview path.
- **Numeric correction after completing an operation:** type another value and
  press Enter to rebuild the last result from its original parameters. Repeated
  corrections occupy one Undo step. Invalid input or a failed rebuild preserves
  the previous result and permits a valid retry. The correction window closes
  on Esc, tool changes, a new operation, Undo/Redo or an edit-context change.
- **Move and Rotate correction:** copies and arrays keep their count and layout
  when the distance or angle is corrected. Rotating a guide transforms its
  direction as well as its location; exact saved coordinates are used for
  cancellation and Undo instead of repeated inverse transforms.
- **Dynamic Orbit/Pan:** press or release Shift during a held navigation drag to
  switch modes without releasing the mouse button. This works with middle-button
  navigation and the Orbit tool's left-button drag. Preferences > General >
  **Switch Orbit/Pan with Shift during a drag** controls it, enabled by default.
  Disable the option to use Shift's state at the start of the drag. The setting
  is persistent and has Polish and Spanish translations.
- **Input details:** explicit radius units such as `25mmr` work in arc input;
  releasing an axis lock after creating a line does not accidentally redirect
  the next numeric correction to another segment. Moving/rotating guides are
  excluded from their own snap targets, while copy originals remain available.

## Try the tools

Stay in the same tool after committing, type the replacement value and press
Enter. Lengths without a suffix use the document's unit; `mm`, `cm` and `m`
are explicit length units. Angles are degrees.

| Tool | Input after completing the operation |
| --- | --- |
| Rectangle | `200mm;100mm` changes both sides while retaining the first corner or centre and drawing quadrant. |
| Rotated Rectangle | `100mm` changes width; `100mm;45` changes width and angle; `200mm;100mm;45` changes base length, width and angle. |
| Circle / Polygon | `25mm` changes radius; `48s` rebuilds the last shape with 48 segments/sides. |
| Line | `150mm` changes the last segment until the mouse moves to start the next segment. After moving the cursor, numeric input applies to the next segment. Three-component coordinate input remains available. |
| Move, including guides | `150mm` changes the original displacement along its original direction; `0;20mm;0` sets a displacement vector. |
| Rotate, including guides | `45` changes the original angle, keeping copy-array count and layout. Negative hot input reverses the initial rotation side. |
| Offset | `10mm` changes the distance from the original loop; a negative value reverses the side. |
| Tape | `30mm` changes the offset of the last guide actually created, for both guide lines and points. Measure-only mode does not create or move a guide. |
| 3D Bevel | `5mm` changes size; `12s` changes segments; `0.3p` changes profile, rebuilding the original solid. |
| Two-endpoint Arc | Change bulge length, use a radius such as `25mmr`, or change segment count with `24s`. |
| Three-point Arc | Change radius, optionally with `r`, or segment count with `24s`; endpoints, plane and sweep side remain fixed. |
| Center Arc / Pie | `45` changes angle, `25mmr` changes radius, `24s` changes segment count. |

For guides: select one or more, then M to translate, or Q to rotate around a
chosen centre and reference arm. Ctrl leaves copies. After a copy, `3x` makes
three copies at multiples of the distance/angle; `/3` divides that distance/angle
among three copies. Right/Left/Up constrain X/Y/Z in the corresponding tool.
Guides remain model-level scaffolding when a group is edited; this change does
not make them members of groups or component definitions.

## Run this source preview

Download this preview's source ZIP and extract it, or clone the feature branch:

```sh
git clone --branch codex/guide-transforms-and-numeric-corrections https://github.com/3A-robwan/ingetrazo.git
cd ingetrazo
```

Use Python 3.12+ and the project's dependencies. For Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py --new-window
```

On Linux/macOS:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py --new-window
```

`--new-window` opens this source copy even if another IngeTrazo instance is
running. No Windows installer or prebuilt executable accompanies this source
preview. DWG import needs the separate LibreDWG converter described in the
upstream installation documentation.

## Validation and limitations

An investigation on 19 October reproduced picking of edges occluded by solid
faces, followed by a local fix to the Eraser, orthographic visibility rays and
perspective edge interpolation. See
[`occluded-edge-investigation.md`](occluded-edge-investigation.md) for exact
reproductions, preserved box/curve selection rules and regression checks.
The earlier local diagnostic scripts deliberately assert the old bugs; use
the new versioned regression files to verify the corrected behaviour.

Focused Windows/Python 3.12/Qt 6.11.2 checks passed:

- Publication check on 19 October: 386 tests passed, 4 skipped in a newly
  selected set of 31 files, including all 57 occluded-edge regressions.
  Startup `main.py --check` and `git diff --check` passed. The local log is
  `../qa/github-release-2026-10-19-tests.log`. This is a separate scope from
  the preceding 462/2 run, whose log did not preserve the selected file list.
- Occluded edge picking: 462 tests passed, 2 skipped in one run of 31 files,
  including 57 new regressions for Eraser/Select in both camera projections,
  two-point perspective, partial occlusion, groups/edit contexts, layers,
  sections, near clipping, large-distance on-face precision, batched visibility,
  Shift/Esc/Delete and Undo/Redo. Initial regression runs reproduced 14 Eraser
  failures and 13 picking failures before the fixes. Startup `--check` passes;
  native interactive/OpenGL verification has not been performed for this fix.
- Handoff checkpoint: 333 tests passed in one run covering all 14 new regression
  files and existing arc, history, acquired-edge and erase-orientation cases.
  A versioned copy of the external Windows-only pytest exit helper is available
  in `scripts/windows_pytest_exit.py`; it preserves pytest's recorded status.
- Rounded inset corners: 228 tests passed, including 15 new regressions for
  XY/YZ and a populated plane in a 3D scene, real Arc/Rectangle tool input,
  out-of-plane moves, Undo/Redo, radius/segment replacement, Alt, host paint,
  opposite-facing neighboring faces and another intentional hole on that plane.
  Nine initial regression cases failed before the fix. Native Windows OpenGL
  images separately confirmed that the missing corner patch now renders as
  the surrounding face, and the obsolete vertex no longer exists.
- Remembered-point length along a direction: 381 tests passed, including 57
  new core and real-viewport cases. These check exact midpoint-to-centre
  geometry, XY/rotated/YZ and tilted planes, perspective/orthographic views,
  preview colour, Shift capture, both direction signs, named-point priority,
  the snap radius, occlusion, Alt modes and radial tools. The user scenario
  failed in all six initial viewport regression cases before the correction.
- Edge highlight widths: 148 tests passed, 3 GL-dependent tests skipped in the
  offscreen suite. The new drawing regressions failed before implementation.
  Native Windows OpenGL captures separately verified progressively thicker
  blue/orange strokes at settings 1, 2 and 3 at 100% and 200% display scaling.
  Preferences persistence, Cancel, live updates and scrolling at 520 × 600 px
  were checked, including saved values loaded by a new viewport.
- 202 numeric-correction/navigation/history/selection tests after the numeric changes.
- 27 guide-Move tests, 131 adjacent Move tests and 58 snapping tests (2 skipped).
- 44 guide-Rotate tests and 118 adjacent rotation/protractor/grip/input tests.
- Follow-up erase correction: 17 regression tests and 127 adjacent erase,
  coplanar merge, curve, hole, material and orientation tests passed. Before
  the fix, 14 of those regression cases failed because unselected edges vanished.
- Follow-up parallel inference: 139 tests passed for edge acquisition, exact
  boundary landing, real perspective/orthographic picking, magenta preview,
  Shift capture, navigation, document boundaries and preferences. The new
  acquisition tests and boundary regressions failed before the change.
- Parallel crossing revisit: 9 regression tests and 174 adjacent inference,
  navigation, history-boundary and preference tests passed. A pause at a landing
  no longer replaces the reference with its target edge. The regressions cover
  real Qt point/edge timers (250/500 ms and a configured 100 ms), perspective and
  orthographic views, rotated walls, midpoint crossings, repeated returns and
  intentional acquisition elsewhere. Four revisit cases failed before this fix.
- Construction-line parallel references: 286 tests passed for guide acquisition,
  inference, navigation, preferences and existing guide operations; 19 further
  picking and precision tests passed. These include visibility and transform
  exclusions, mesh/guide distance priority, guide anchors, point markers,
  camera clipping and large-coordinate direction precision. Four guide
  acquisition cases failed before this addition.

These are separate, partly overlapping runs, not one summed total. New regression
checks failed before the corresponding features were added. Syntax checks,
`git diff --check`, patch applicability and the source `--check` startup check pass.
Most automated interaction checks use Qt offscreen. Edge highlight and rounded
inset captures were also checked in native Windows OpenGL; full interactive use
of the preview has not been manually verified.

A full fast-suite attempt before the later guide-transform additions completed
with **4567 passed, 30 skipped and 5 failed**; another batch crashed in Qt's
composer items panel, so the entire project is **not verified green**.
Three failures concern 3D text shaping and two concern the extension manager.
The three text failures and one extension failure were reproduced on the
unmodified base sources. The other extension failure was not independently
reproduced on a clean base. The full suite was not rerun after the later guide
changes; their focused and adjacent tests are reported above.

The Windows test runner also required an external process-exit workaround for
a native Qt shutdown crash. It preserved pytest's real failure status and was
not added to the application or its tests. A native crash during a test remains
a failure. Please report reproducible issues and the Python/Qt/platform versions
when trying this preview.

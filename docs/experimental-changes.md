# Experimental community changes (18 October 2026)

This is an **unofficial source-code preview**, published by `3A-robwan` for
others to try and review. It is based on upstream commit
`d8ee8c068f0b1a26fe1a84a8489d3facb3fa22bf` (13 October 2026), whose application
version is 0.5.8. It does not include every later upstream change and is not an
official IngeTrazo release. The application still reports 0.5.8.

IngeTrazo is created by Marco Sumari Tellez and its contributors. Original
attribution and the GPL-3.0-or-later license are preserved.

## Changes

- **Construction guide selection:** Ctrl+A includes guide lines and points.
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

Focused Windows/Python 3.12/Qt 6.11.2 checks passed:

- 202 numeric-correction/navigation/history/selection tests after the numeric changes.
- 27 guide-Move tests, 131 adjacent Move tests and 58 snapping tests (2 skipped).
- 44 guide-Rotate tests and 118 adjacent rotation/protractor/grip/input tests.

These are separate, partly overlapping runs, not one summed total. New regression
checks failed before the corresponding features were added. Syntax checks,
`git diff --check`, patch applicability and the source `--check` startup check pass.
Automated interaction checks use Qt offscreen; interactive OpenGL rendering has
not been manually verified for this preview.

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

# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Which IngeTrazo this is: the stable one, or the Beta that tests the
native (Rust) engine next to it.

The Beta must live beside the stable install without touching it, so
everything that carries the app's name here takes it from this module:
the settings (QSettings application name → its own file / registry key,
and its own AppDataLocation: auto-save slots, user styles…), the log
folder, the plugin folder and the single-instance channel (otherwise
opening the Beta would hand the file to a running stable window).

A build is the Beta when its CI drops ``resources/edition.txt`` reading
``beta`` into the package; from source, ``INGETRAZO_EDITION=beta``. Nothing
in the repository says beta, so ``main`` stays the stable app."""
from __future__ import annotations

import os
from pathlib import Path


def _detect() -> str:
    env = os.environ.get("INGETRAZO_EDITION", "").strip().lower()
    if env:
        return "beta" if env == "beta" else "stable"
    try:
        from core.paths import app_root
        marker = Path(app_root()) / "resources" / "edition.txt"
        if marker.read_text(encoding="utf-8").strip().lower() == "beta":
            return "beta"
    except (OSError, ImportError):
        pass
    return "stable"


EDITION = _detect()
BETA = EDITION == "beta"

#: The name settings and data folders are filed under (QSettings
#: application name), and the one shown in the title bar.
APP_NAME = "IngeTrazo Beta" if BETA else "IngeTrazo"
#: Lower-case, for folders, the desktop entry and the instance channel.
SLUG = "ingetrazo-beta" if BETA else "ingetrazo"

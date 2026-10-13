# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""The Beta lives beside the stable IngeTrazo without touching it
(core/edition.py): its own settings file, data folder (auto-save, user
styles), plugin folder, log folder and single-instance channel. Each
edition is asked in a fresh process, as an installed copy would be."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_PROBE = r"""
import json, sys
sys.path.insert(0, %r)
from PySide6.QtCore import QCoreApplication, QSettings, QStandardPaths
from core.edition import APP_NAME, SLUG, BETA
app = QCoreApplication([])
QCoreApplication.setOrganizationName("IngeTrazo")
QCoreApplication.setApplicationName(APP_NAME)
from core.extensions import user_plugins_dir
from core.paths import user_log_dir
print(json.dumps({
    "beta": BETA, "name": APP_NAME, "socket": f"{SLUG}-single-instance",
    "settings": QSettings().fileName(),
    "data": QStandardPaths.writableLocation(QStandardPaths.AppDataLocation),
    "plugins": str(user_plugins_dir()),
    "logs": str(user_log_dir()),
}))
"""


def _ask(edition: str | None, tmp_path) -> dict:
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen",
               XDG_CONFIG_HOME=str(tmp_path / "config"),
               XDG_DATA_HOME=str(tmp_path / "data"),
               XDG_STATE_HOME=str(tmp_path / "state"))
    env.pop("INGETRAZO_EDITION", None)
    if edition:
        env["INGETRAZO_EDITION"] = edition
    out = subprocess.run([sys.executable, "-c", _PROBE % str(ROOT)],
                         env=env, capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_stable_is_the_default(tmp_path):
    s = _ask(None, tmp_path)
    assert s["beta"] is False and s["name"] == "IngeTrazo"
    assert s["socket"] == "ingetrazo-single-instance"
    assert s["plugins"].endswith(os.path.join("ingetrazo", "plugins"))


def test_the_beta_shares_nothing_with_the_stable(tmp_path):
    stable = _ask("stable", tmp_path)
    beta = _ask("beta", tmp_path)
    assert beta["beta"] is True and beta["name"] == "IngeTrazo Beta"
    for key in ("settings", "data", "plugins", "logs", "socket"):
        assert beta[key] != stable[key], key
        # and not nested inside the stable's either
        assert not beta[key].startswith(stable[key] + os.sep), key


def test_the_marker_file_makes_a_package_the_beta(tmp_path, monkeypatch):
    """A packaged Beta has no environment variable: the marker decides."""
    import core.edition as ed
    import core.paths
    (tmp_path / "resources").mkdir()
    (tmp_path / "resources" / "edition.txt").write_text("beta\n")
    monkeypatch.delenv("INGETRAZO_EDITION", raising=False)
    monkeypatch.setattr(core.paths, "app_root", lambda: tmp_path)
    assert ed._detect() == "beta"
    (tmp_path / "resources" / "edition.txt").write_text("stable\n")
    assert ed._detect() == "stable"

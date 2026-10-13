# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""The optional native kernels (``rust/ingetrazo_core``, built with maturin).

``native`` is the compiled module, or ``None`` when it is not built, does
not load on this machine, or ``INGETRAZO_RUST=0`` turns it off. Every caller
keeps its Python code and uses it whenever ``native`` is ``None``: the
kernels make things faster, never different."""
from __future__ import annotations

import logging
import os

log = logging.getLogger(__name__)

native = None
if os.environ.get("INGETRAZO_RUST", "1") != "0":
    try:
        import ingetrazo_core as native  # noqa: F401
    except Exception as exc:  # noqa: BLE001 — a missing module is the norm
        native = None
        if not isinstance(exc, ImportError):
            log.warning("native kernels failed to load, using Python: %s",
                        exc)


def engine() -> str:
    """«Rust» or «Python», for About and the logs."""
    return "Rust" if native is not None else "Python"

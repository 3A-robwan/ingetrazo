"""External Windows-only pytest exit workaround; application files stay untouched.

The pristine upstream suite can pass, then fault in Qt DLL detachment while
``os._exit`` calls Windows ExitProcess. Terminate only after session reporting,
using pytest's recorded result. This does not bypass test execution or teardown.
"""
from __future__ import annotations

import sys

import pytest


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session, exitstatus):
    session.config._windows_recorded_pytest_status = int(session.exitstatus)


@pytest.hookimpl(tryfirst=True)
def pytest_unconfigure(config):
    if sys.platform != "win32":
        return
    status = getattr(config, "_windows_recorded_pytest_status", None)
    if status is None:
        return
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.argtypes = []
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel.TerminateProcess.restype = wintypes.BOOL
    sys.stdout.flush()
    sys.stderr.flush()
    if not kernel.TerminateProcess(kernel.GetCurrentProcess(), status):
        raise ctypes.WinError(ctypes.get_last_error())

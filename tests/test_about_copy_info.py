"""Help ▸ About: "Copy to clipboard" puts what a bug report needs (#476)."""
from __future__ import annotations

import platform

from PySide6.QtWidgets import QApplication

from core.i18n import current_language, set_language
from views.about_dialog import AboutDialog, system_info

_app = QApplication.instance() or QApplication([])

_GL = "NVIDIA Corporation · RTX 9999/PCIe · OpenGL 4.6.0"


def test_the_info_names_program_system_python_qt_and_gl():
    text = system_info("9.8.7", _GL)
    assert text.splitlines()[0].startswith("IngeTrazo 9.8.7")
    assert f"OS: {platform.platform()}" in text
    assert f"Python: {platform.python_version()}" in text
    assert "Qt: " in text and "PySide6: " in text
    assert f"OpenGL: {_GL}" in text
    assert "Screen: " in text
    assert f"Language: {current_language()}" in text


def test_without_a_gl_line_there_is_no_empty_opengl_row():
    assert "OpenGL" not in system_info("9.8.7")


def test_the_info_stays_in_english_whatever_the_interface_language():
    before = current_language()
    try:
        set_language("es")
        text = system_info("9.8.7", _GL)
    finally:
        set_language(before)
    assert "Language: es" in text
    assert "OS: " in text and "Screen: " in text


def test_the_button_copies_the_info_to_the_clipboard():
    QApplication.clipboard().setText("something else")
    dlg = AboutDialog(None, "9.8.7", _GL)
    dlg.copy_button.click()
    assert QApplication.clipboard().text() == system_info("9.8.7", _GL)
    dlg.close()


def test_the_button_says_it_copied():
    dlg = AboutDialog(None, "9.8.7")
    label = dlg.copy_button.text()
    dlg.copy_button.click()
    assert dlg.copy_button.text() != label
    dlg.close()

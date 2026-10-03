import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from wiedan.apps.main_window import MainWindow


@pytest.fixture
def window(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    app = QApplication.instance() or QApplication([])
    app.setStyle("Fusion")
    return MainWindow()


def test_explorer_and_tabs(window):
    window.project_box.setCurrentText("xuzhou")
    assert window.explorer.topLevelItemCount() == 21  # Zentrale + 20 Fahrzeuge
    window.live_area.open_device(window._project.devices["fzg_03/inverter"])
    window.live_area.open_device(window._project.devices["fzg_03/inverter"])
    assert window.live_area.count() == 1


def test_theme_switch_is_saved(window, tmp_path):
    window.theme_box.setCurrentIndex(window.theme_box.findData("dunkel"))
    assert (tmp_path / "WieDAN" / "settings.json").exists()

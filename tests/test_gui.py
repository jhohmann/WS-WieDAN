import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFormLayout, QMessageBox

from wiedan.apps.main_window import MainWindow
from wiedan.core.project_database import database_path


@pytest.fixture
def window(storage):
    app = QApplication.instance() or QApplication([])
    app.setStyle("Fusion")
    widget = MainWindow()
    yield widget
    widget.close()
    app.processEvents()


def test_explorer_and_tabs(window):
    window.set_project("xuzhou")
    assert window.explorer.topLevelItemCount() == len(window._project.vehicles) + 1
    device = window._project.find(type="nidec_m700")[0]
    window.live_area.open_device(device)
    window.live_area.open_device(device)
    assert window.live_area.count() == 1


def test_theme_switch_is_saved(window, storage):
    window.set_theme("dark")
    assert (storage / "WieDAN" / "settings.json").exists()


@pytest.mark.parametrize("key", [Qt.Key.Key_Return, Qt.Key.Key_Enter])
def test_enter_in_project_property_does_not_start_new_project(window, monkeypatch, key):
    questions = []
    monkeypatch.setattr(QMessageBox, "question", lambda *args: questions.append(args) or QMessageBox.StandardButton.Discard)
    editor = window.project_editor
    uid = editor.draft.project["uid"]
    dialog = window.project_editor_dialog
    dialog.setModal(True)
    dialog.show()
    QApplication.processEvents()
    name = next(editor.form.itemAt(row, QFormLayout.ItemRole.FieldRole).widget()
                for row in range(editor.form.rowCount())
                if editor.form.itemAt(row, QFormLayout.ItemRole.LabelRole).widget().text() == "Kurzname")
    name.setFocus()
    name.selectAll()
    QTest.keyClicks(name, "Geaendertes Projekt")
    QTest.keyClick(name, key)
    QApplication.processEvents()
    dialog.hide()
    assert not questions
    assert editor.draft.project["uid"] == uid
    assert not editor.draft.is_new
    assert editor.draft.project["name"] == "Geaendertes Projekt"


def test_database_selection_preserves_project_and_updates_all_views(window, storage, database_release):
    window.set_project("CK Xuzhou")
    old_uid = window._project.uid
    release = storage / "neuer-datenstand.sqlite"
    database_release(release, data_version="2026.10")
    window._connect_database(release)
    assert window._project.uid == old_uid
    assert window._project.data_version == "2026.10"
    assert window._project.database_path == release
    assert len(window.project_menu.actions()) == len(window.projects_menu.actions())
    window.set_theme("dark")
    assert database_path() == release


def test_incompatible_database_shows_error_and_keeps_current_connection(window, storage, monkeypatch, database_release):
    import sqlite3

    original = window._project
    release = storage / "future.sqlite"
    database_release(release, data_version="Future")
    connection = sqlite3.connect(release)
    connection.execute("PRAGMA user_version=999")
    connection.close()
    messages = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: messages.append(args[2]))
    window._connect_database(release)
    assert window._project is original
    assert len(messages) == 1 and "neuere WieDAN-Version" in messages[0]

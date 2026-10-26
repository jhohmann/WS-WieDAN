"""Offline-Workflow: unabhängige Vorlagen, Entwürfe und Mehrfachbearbeitung."""

import copy
import os
from dataclasses import replace

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QInputDialog,
    QMessageBox,
    QTableWidgetSelectionRange,
)

from wiedan.core.model import list_projects, load_project
from wiedan.core.scalance_config import (
    W700,
    apply_template,
    blank_configuration,
    configuration_status,
    load_set,
    new_set,
    read_set,
    save_set,
    set_path,
)
from wiedan.features.scalance_config import ScalanceConfigGenerator, TemplateDialog


@pytest.fixture
def project():
    return load_project("CK Xuzhou")


def wireless_ids(project):
    return [key for key, device in project.devices.items() if device.type == W700]


def test_new_project_and_draft(project):
    data = new_set(project)
    assert data["devices"] == {}
    assert configuration_status(None) == "Keine Konfiguration"
    entry = blank_configuration(W700)
    assert configuration_status(entry) == "Entwurf"
    entry["parameters"]["role"] = "Access Point"
    assert configuration_status(entry) == "Konfiguration hinterlegt"
    entry["parameters"]["channel"] = ""
    assert configuration_status(entry) == "Entwurf"
    entry["parameters"].update(channel=165, role="Client")
    assert configuration_status(entry) == "Entwurf"
    del entry["parameters"]["channel"]
    assert configuration_status(entry) == "Konfiguration hinterlegt"


def test_template_copies_preserve_identity_and_independence(project):
    first, second = wireless_ids(project)[:2]
    original_ip = project.devices[first].connection["ip"]
    source = {"type": W700, "parameters": {"role": "Access Point", "channel": 165, "system_name": "Foreign"}}
    data = new_set(project)
    data["devices"][first] = {"type": W700, "parameters": {"system_name": "Local"}}
    apply_template(data, project, [first, second], source)
    assert data["devices"][first]["parameters"]["system_name"] == "Local"
    assert "system_name" not in data["devices"][second]["parameters"]
    data["devices"][first]["parameters"]["channel"] = 149
    assert data["devices"][second]["parameters"]["channel"] == source["parameters"]["channel"] == 165
    assert project.devices[first].connection["ip"] == original_ip
    assert "ip" not in data["devices"][first]["parameters"]


def test_sets_save_as_and_load_foreign_template(storage, project):
    first = wireless_ids(project)[0]
    data = new_set(project)
    data["devices"][first] = {"type": W700, "parameters": {"role": "Access Point", "channel": 165}}
    save_set(data, "Standard")
    data["devices"][first]["parameters"]["channel"] = 149
    save_set(data, "Alternative")
    assert load_set(project, "Standard")["devices"][first]["parameters"]["channel"] == 165
    assert load_set(project, "Alternative")["devices"][first]["parameters"]["channel"] == 149
    other = replace(project, id="other-project")
    other_data = new_set(other)
    source = read_set(set_path(project.id, "Standard"))["devices"][first]
    apply_template(other_data, other, [first], source)
    assert other_data["project"] == "other-project"
    assert other_data["devices"][first]["parameters"]["channel"] == 165


@pytest.mark.parametrize("name", ["../other", "CON", "a/b", "", "trailing."])
def test_invalid_names(name):
    with pytest.raises(ValueError):
        set_path("test", name)


def test_malformed_and_changed_project(storage, project):
    path = storage / "bad.yaml"
    path.write_text("devices: [", encoding="utf-8")
    with pytest.raises(ValueError, match="YAML"):
        read_set(path)
    data = new_set(project)
    first = wireless_ids(project)[0]
    data["devices"][first] = blank_configuration(W700)
    save_set(data, "Entwurf")
    reduced = replace(project, devices={})
    assert load_set(reduced, "Entwurf")["devices"][first] == data["devices"][first]
    changed_devices = dict(project.devices)
    changed_devices[first] = replace(changed_devices[first], type="siemens_scalance_xc206")
    with pytest.raises(ValueError, match="Gerätetyp"):
        load_set(replace(project, devices=changed_devices), "Entwurf")


@pytest.fixture
def page(storage, project):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    widget = ScalanceConfigGenerator()
    widget.set_project(project)
    yield widget
    widget.close()
    app.processEvents()


def select_cells(page, first_row, first_col, last_row=None, last_col=None):
    page.table.clearSelection()
    page.table.setCurrentCell(first_row, first_col)
    page.table.setRangeSelected(QTableWidgetSelectionRange(
        first_row, first_col, first_row if last_row is None else last_row,
        first_col if last_col is None else last_col), True)


def test_direct_edit_undo_and_empty_cells(page):
    key = page._devices[0].id
    role = page.column("role")
    page.table.item(0, role).setText("Access Point")
    assert page._data["devices"][key]["parameters"] == {"role": "Access Point"}
    assert page._dirty
    page.undo_stack.undo()
    assert key not in page._data["devices"] and not page._dirty
    page.undo_stack.redo()
    select_cells(page, 0, role)
    QTest.keyClick(page.table, Qt.Key.Key_Delete)
    assert key not in page._data["devices"]


def test_scalar_paste_and_bulk_undo(page):
    role = page.column("role")
    select_cells(page, 0, role, 2, role)
    QApplication.clipboard().setText("Access Point")
    QTest.keyClick(page.table, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
    assert len(page._data["devices"]) == 3
    assert all(entry["parameters"]["role"] == "Access Point" for entry in page._data["devices"].values())
    page.undo_stack.undo()
    assert page._data["devices"] == {}


def test_excel_rectangle_skips_hidden_columns_and_roundtrips(page):
    select_cells(page, 0, page.column("role"))
    text = 'Access Point\t"4099"\t165\r\nAccess Point\t"ssid\tquoted"\t149\r\n'
    QApplication.clipboard().setText(text)
    page._paste_cells()
    first, second = (page._data["devices"][d.id]["parameters"] for d in page._devices[:2])
    assert first == {"role": "Access Point", "ssid": "4099", "channel": 165}
    assert second["ssid"] == "ssid\tquoted" and second["channel"] == 149
    select_cells(page, 0, page.column("role"), 1, page.column("channel"))
    page._copy_cells()
    page.undo_stack.undo()
    page._paste_cells()
    assert page._data["devices"][page._devices[1].id]["parameters"] == second


def test_paste_rejects_wrong_shape_without_partial_changes(page):
    col = page.column("channel")
    select_cells(page, 0, col, 2, col)
    QApplication.clipboard().setText("149\n165\n")
    page._paste_cells()
    assert page._data["devices"] == {}
    assert page.status.property("error") is True
    select_cells(page, len(page._devices) - 1, col)
    QApplication.clipboard().setText("149\n165")
    page._paste_cells()
    assert page._data["devices"] == {}


def test_filter_paste_only_touches_visible_rows(page):
    page.search.setText("AP0")
    visible = [row for row in range(page.table.rowCount()) if not page.table.isRowHidden(row)]
    assert visible
    select_cells(page, visible[0], page.column("channel"))
    QApplication.clipboard().setText("149\n165")
    page._paste_cells()
    assert set(page._data["devices"]) == {page._devices[row].id for row in visible[:2]}


def test_bulk_value_and_validation(page, monkeypatch):
    channel = page.column("channel")
    select_cells(page, 0, channel, 1, channel)
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **kw: ("not-a-channel", True))
    page._bulk_value()
    for row in (0, 1):
        assert page.table.item(row, 2).text() == "Abweichung · Entwurf"
        assert "ungültig" in page.table.item(row, channel).toolTip()
        assert page.table.item(row, channel).data(Qt.ItemDataRole.UserRole + 1)
    page.undo_stack.undo()
    assert not page._data["devices"]


def test_switches_are_readonly_and_preserved(page, project):
    row = next(row for row, device in enumerate(page._devices) if device.type != W700)
    assert not page.table.item(row, page.column("role")).flags() & Qt.ItemFlag.ItemIsEditable
    assert page.table.item(row, 2).text() == "Noch nicht unterstützt"
    key = page._devices[row].id
    page._data["devices"][key] = {"type": "siemens_scalance_xc206", "parameters": {"system_name": "Existing"}}
    page._render_values()
    snapshot = copy.deepcopy(page._data)
    select_cells(page, row, page.column("role"))
    QApplication.clipboard().setText("Access Point")
    page._paste_cells()
    assert page._data == snapshot
    page._save()
    assert load_set(project, "Standard")["devices"][key]["parameters"]["system_name"] == "Existing"


def test_save_reload_and_guard(page, project, monkeypatch):
    page.table.item(0, page.column("role")).setText("Client")
    key = page._devices[0].id
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **kw: QMessageBox.StandardButton.Cancel)
    assert not page.can_leave()
    assert page._save()
    assert not page._dirty and page.can_leave()
    page.set_project(project)
    assert page._data["devices"][key]["parameters"]["role"] == "Client"
    assert not page.undo_stack.canUndo()


def test_template_picker_finds_saved_projects(page, project):
    first = wireless_ids(project)[0]
    data = new_set(replace(project, id="Vorlagenprojekt"))
    data["devices"][first] = {"type": W700, "parameters": {"role": "Access Point", "channel": 165}}
    save_set(data, "Funknetz")
    dialog = TemplateDialog(W700, page)
    group = dialog.tree.topLevelItem(0)
    assert group.text(0) == "Vorlagenprojekt / Funknetz"
    dialog.tree.setCurrentItem(group.child(0))
    assert dialog.source["parameters"]["channel"] == 165
    dialog.close()


def test_no_ssh_needed(page, project):
    devices = {key: replace(device, connection={"ip": device.connection["ip"], "protocol": "icmp"},
                            commissioning_connection=None) for key, device in project.devices.items()}
    page.set_project(replace(project, devices=devices))
    page.table.item(0, page.column("role")).setText("Client")
    assert page._data["devices"][page._devices[0].id]["parameters"]["role"] == "Client"


def test_main_window_project_switch_guard(storage, monkeypatch):
    from wiedan.apps.main_window import MainWindow

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.set_project("CK Xuzhou")
    window.commissioning_area.open_tool("scalance-config-generator")
    other_project = next(name for name in list_projects() if name != "CK Xuzhou")
    page = window.commissioning_area.currentWidget()
    page.table.item(0, page.column("role")).setText("Client")
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **kw: QMessageBox.StandardButton.Cancel)
    assert window.set_project(other_project) is False
    assert window._project.id == page._project.id == "xuzhou"
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **kw: QMessageBox.StandardButton.Discard)
    assert window.set_project(other_project) is True
    assert page._project.id == load_project(other_project).id
    window.close()
    app.processEvents()



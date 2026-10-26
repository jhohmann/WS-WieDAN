"""Offline-Planung von Scalance-Konfigurationen und benannten Alternativen."""

import copy
import csv
import io
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QColor, QKeySequence, QUndoCommand, QUndoStack
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wiedan.core.working_configuration import (
    DEVICE_TYPES,
    PARAMETERS,
    W700,
    apply_template,
    baseline,
    configuration_errors,
    configuration_status,
    effective_entry,
    list_sets,
    load_set,
    new_set,
    parse_value,
    project_devices,
    read_set,
    remove_redundant_overrides,
    save_set,
    set_path,
    user_directory,
)
from wiedan.features.master_data_editor import MasterDataEditor

USER_ROLE = Qt.ItemDataRole.UserRole


class TemplateDialog(QDialog):
    """Vorlagen nach Projekt/Satz wählen; externe Sätze lassen sich ergänzen."""

    def __init__(self, device_type, parent=None):
        super().__init__(parent)
        self.device_type = device_type
        self.source = None
        self.setWindowTitle("Vorlage auswählen")
        self.resize(600, 470)
        layout = QVBoxLayout(self)
        self.hint = QLabel("Vorlage auswählen. Gerätenamen und Projekt-IP werden nicht kopiert.")
        self.hint.setWordWrap(True)
        self.hint.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.hint)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Projekt / Satz / Gerät", "Status"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.itemSelectionChanged.connect(self._selection_changed)
        layout.addWidget(self.tree, 1)
        self.preview = QLabel()
        self.preview.setWordWrap(True)
        self.preview.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.preview)
        browse = QPushButton("Datei öffnen …")
        browse.clicked.connect(self._browse)
        layout.addWidget(browse)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        for path in sorted(user_directory().glob("*/*.yaml")):
            self._add_file(path)
        if not self.tree.topLevelItemCount():
            self.hint.setText("Noch keine gespeicherten Vorlagen. Einen Konfigurationssatz über „Datei öffnen“ laden.")

    def _add_file(self, path):
        try:
            data = read_set(path)
            entries = {key: entry for key, entry in data["devices"].items() if entry["type"] == self.device_type}
            if not entries:
                raise ValueError("Keine Konfiguration für diesen Gerätetyp")
        except (OSError, ValueError) as exc:
            group = QTreeWidgetItem([path.stem, "Nicht verfügbar"])
            group.setToolTip(0, str(exc))
            group.setDisabled(True)
            self.tree.addTopLevelItem(group)
            return
        group = QTreeWidgetItem([f"{data['project']} / {data['name']}"])
        group.setToolTip(0, str(path))
        self.tree.addTopLevelItem(group)
        for key, entry in entries.items():
            item = QTreeWidgetItem(group, [key, configuration_status(entry)])
            item.setData(0, USER_ROLE, entry)
        group.setExpanded(True)
        self.tree.scrollToItem(group)

    def _browse(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Konfigurationssatz öffnen", str(user_directory()),
                                                 "Konfigurationssätze (*.yaml *.yml)")
        if filename:
            self._add_file(Path(filename))

    def _selection_changed(self):
        item = self.tree.currentItem()
        self.source = item.data(0, USER_ROLE) if item else None
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(self.source is not None)
        values = self.source["parameters"] if self.source else {}
        self.preview.setText(" · ".join(f"{PARAMETERS[key].label}: {value}" for key, value in values.items()
                                        if key != "system_name"))


class ParameterDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        if index.data(USER_ROLE + 1):
            painter.save()
            painter.setPen(QColor("#c95454"))
            painter.drawLine(option.rect.bottomLeft(), option.rect.bottomRight())
            painter.restore()

    def createEditor(self, parent, option, index):
        key = index.data(USER_ROLE)
        if key and PARAMETERS[key].choices:
            editor = QComboBox(parent)
            editor.addItem("Bitte wählen", "")
            for choice in PARAMETERS[key].choices:
                editor.addItem(choice, choice)
            return editor
        return super().createEditor(parent, option, index)

    def setEditorData(self, editor, index):
        if isinstance(editor, QComboBox):
            editor.setCurrentIndex(max(0, editor.findData(index.data(Qt.ItemDataRole.EditRole))))
        else:
            super().setEditorData(editor, index)

    def setModelData(self, editor, model, index):
        if isinstance(editor, QComboBox):
            model.setData(index, editor.currentData(), Qt.ItemDataRole.EditRole)
        else:
            super().setModelData(editor, model, index)


class DeviceTable(QTableWidget):
    copy_requested = Signal()
    paste_requested = Signal()
    clear_requested = Signal()

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.StandardKey.Copy):
            self.copy_requested.emit()
        elif event.matches(QKeySequence.StandardKey.Paste):
            self.paste_requested.emit()
        elif event.key() == Qt.Key.Key_Delete:
            self.clear_requested.emit()
        else:
            super().keyPressEvent(event)


class TableChange(QUndoCommand):
    def __init__(self, page, before, after, title):
        super().__init__(title)
        self.page, self.before, self.after = page, before, after

    def redo(self):
        self.page._data["devices"] = copy.deepcopy(self.after)
        self.page._render_values()

    def undo(self):
        self.page._data["devices"] = copy.deepcopy(self.before)
        self.page._render_values()


class ScalanceConfigGenerator(QWidget):
    database_changed = Signal()
    before_database_edit = staticmethod(lambda: True)
    """Ein Gerät je Zeile; Vorgaben direkt in den Parameterzellen bearbeiten."""

    DEFAULT_COLUMNS = frozenset({"ip", "role", "ssid", "channel"})

    def __init__(self):
        super().__init__()
        self._project = self._data = None
        self._dirty = self._loading = self._saved = False
        self._devices = []
        self._keys = list(PARAMETERS)
        self.undo_stack = QUndoStack(self)
        self.undo_stack.cleanChanged.connect(self._clean_changed)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        self.title = QLabel("Scalance")
        self.title.setObjectName("scalanceTitle")
        layout.addWidget(self.title)
        toolbar = QHBoxLayout()
        self.family = QComboBox()
        self.family.addItems(["Alle Geräte", "WLAN-Geräte", "Switches"])
        self.family.currentIndexChanged.connect(self._filter)
        toolbar.addWidget(self.family)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Gerät oder IP suchen")
        self.search.textChanged.connect(self._filter)
        toolbar.addWidget(self.search, 1)
        self.sets = QComboBox()
        self.sets.setMinimumWidth(130)
        self.sets.setToolTip("Gespeicherte Konfiguration auswählen")
        self.sets.activated.connect(self._load)
        toolbar.addWidget(self.sets)
        self._button(toolbar, "Speichern", self._save)
        more = QToolButton()
        more.setText("…")
        more.setToolTip("Weitere Dateiaktionen")
        more.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(more)
        menu.addAction("Neue Konfiguration", self._new)
        menu.addAction("Speichern unter …", lambda: self._save(True))
        more.setMenu(menu)
        toolbar.addWidget(more)
        layout.addLayout(toolbar)

        actions = QHBoxLayout()
        self.bulk_button = self._button(actions, "Wert setzen …", self._bulk_value)
        self.bulk_button.setToolTip("Einen Wert in alle markierten Zellen einer Parameterspalte eintragen")
        self.template_button = self._button(actions, "Vorlage übernehmen …", self._template)
        columns = QToolButton()
        columns.setText("Spalten")
        columns.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        column_menu = QMenu(columns)
        self._column_actions = {}
        for key, spec in PARAMETERS.items():
            action = column_menu.addAction(spec.label)
            action.setCheckable(True)
            action.setChecked(key in self.DEFAULT_COLUMNS)
            action.toggled.connect(lambda visible, k=key: self.table.setColumnHidden(self.column(k), not visible))
            self._column_actions[key] = action
        columns.setMenu(column_menu)
        actions.addWidget(columns)
        actions.addStretch()
        for label, callback, enabled_signal, text_signal in (
            ("Rückgängig", self.undo_stack.undo, self.undo_stack.canUndoChanged, self.undo_stack.undoTextChanged),
            ("Wiederholen", self.undo_stack.redo, self.undo_stack.canRedoChanged, self.undo_stack.redoTextChanged),
        ):
            action = QAction(label, self)
            action.setEnabled(False)
            action.triggered.connect(callback)
            enabled_signal.connect(action.setEnabled)
            text_signal.connect(action.setToolTip)
            action.setShortcut(QKeySequence.StandardKey.Undo if label == "Rückgängig"
                               else QKeySequence.StandardKey.Redo)
            action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            self.addAction(action)
            button = QToolButton()
            button.setDefaultAction(action)
            actions.addWidget(button)
        layout.addLayout(actions)

        self.table = DeviceTable(0, 3 + len(self._keys))
        self.table.setObjectName("scalanceTable")
        self.table.setHorizontalHeaderLabels(["Projektgerät", "Projekt-IP", "Konfiguration"]
                                             + [PARAMETERS[key].label for key in self._keys])
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setItemDelegate(ParameterDelegate(self.table))
        self.table.verticalHeader().setDefaultSectionSize(30)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        for col, width in enumerate([190, 120, 155]):
            self.table.setColumnWidth(col, width)
        for key in self._keys:
            self.table.setColumnWidth(self.column(key), 130 if key == "role" else 110)
        self.table.cellChanged.connect(self._changed)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self.table.copy_requested.connect(self._copy_cells)
        self.table.paste_requested.connect(self._paste_cells)
        self.table.clear_requested.connect(self._clear_cells)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._context_menu)
        layout.addWidget(self.table, 1)
        self.summary = QLabel()
        layout.addWidget(self.summary)
        self.status = QLabel("Arbeitskonfiguration · Fett = eigene Abweichung · Entf = Stammwert verwenden · Strg+C / Strg+V für Excel")
        self.status.setObjectName("scalanceStatus")
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.status)

    @staticmethod
    def _button(layout, text, callback):
        button = QPushButton(text)
        button.clicked.connect(lambda _checked=False: callback())
        layout.addWidget(button)
        return button

    def column(self, key):
        return 3 + self._keys.index(key)

    def set_project(self, project):
        self._project = project
        self._data = new_set(project)
        self._data["name"] = "Standard"
        self._saved = False
        self.title.setText(f"Scalance · Arbeitskonfiguration · {project.name}")
        names = list_sets(project.id)
        preferred = "Standard" if "Standard" in names else names[0] if len(names) == 1 else None
        if preferred:
            try:
                self._data = load_set(project, preferred)
                self._saved = True
            except (OSError, ValueError) as exc:
                self._status(str(exc), True)
        self._reset_table()

    def _reset_table(self):
        self.undo_stack.clear()
        self._dirty = False
        self._loading = True
        self._devices = project_devices(self._project)
        self.table.setRowCount(len(self._devices))
        self.table.clearContents()
        for row, device in enumerate(self._devices):
            for col in range(self.table.columnCount()):
                item = QTableWidgetItem()
                if col < 3 or device.type != W700:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if col >= 3:
                    item.setData(USER_ROLE, self._keys[col - 3])
                self.table.setItem(row, col, item)
            self.table.item(row, 0).setText(device.id)
            self.table.item(row, 0).setToolTip(f"{device.label}\n{device.id}\n{DEVICE_TYPES.get(device.type, device.type)}")
            self.table.item(row, 1).setText(device.connection.get("ip", ""))
        used = set().union(*(entry["parameters"] for entry in self._data["devices"].values()),
                           *(device.parameters for device in self._devices))
        for key, action in self._column_actions.items():
            visible = key in self.DEFAULT_COLUMNS or key in used
            action.setChecked(visible)
            self.table.setColumnHidden(self.column(key), not visible)
        self._loading = False
        self._render_values()
        self._refresh_sets()
        self._filter()

    def _render_values(self):
        self._loading = True
        for row, device in enumerate(self._devices):
            entry = effective_entry(self._data, device)
            errors = configuration_errors(entry) if entry else []
            values = {**baseline(device), **(entry["parameters"] if entry else {})}
            overrides = self._data["devices"].get(device.id, {}).get("parameters", {})
            state = ("Abweichung · Entwurf" if errors else "Arbeitskonfiguration") if overrides else "Stammwerte"
            if device.type != W700:
                state = "Noch nicht unterstützt"
            self.table.item(row, 2).setText(state)
            self.table.item(row, 2).setToolTip("\n".join(errors) if device.type == W700 else "Switch-Konfiguration folgt später.")
            for key in self._keys:
                item = self.table.item(row, self.column(key))
                item.setText(str(values.get(key, "")))
                font = item.font()
                font.setBold(key in overrides)
                item.setFont(font)
                error = "\n".join(message for message in errors
                                  if message.startswith(PARAMETERS[key].label)
                                  or (key == "channel" and message.startswith("Kanal")))
                item.setData(USER_ROLE + 1, error if device.type == W700 else "")
                item.setToolTip(error or f"Stammwert: {baseline(device).get(key, 'nicht hinterlegt')}\n"
                                + ("Eigene Abweichung" if key in overrides else "Aus Stammdaten übernommen")
                                + f"\n{PARAMETERS[key].hint}")
        self._loading = False
        self._refresh_summary()
        self._selection_changed()

    def _filter(self, *_args):
        if not self._project:
            return
        self.table.clearSelection()
        query = self.search.text().casefold().strip()
        family = self.family.currentIndex()
        for row, device in enumerate(self._devices):
            matches = query in f"{device.id} {device.label} {device.connection.get('ip', '')}".casefold()
            matches &= family == 0 or (family == 1 and device.type == W700) or (family == 2 and device.type != W700)
            self.table.setRowHidden(row, not matches)
        self._refresh_summary()

    def _refresh_summary(self):
        if self._data is None:
            return
        wireless = [d for d in self._devices if d.type == W700]
        configured = [entry for d in wireless if (entry := effective_entry(self._data, d)) is not None]
        drafts = sum(bool(configuration_errors(entry)) for entry in configured)
        self.summary.setText(f"{self._data['name']} · {'Ungespeichert · ' if self._dirty else ''}"
                             f"{len(wireless) - len(configured)} ohne Konfiguration · {drafts} Entwürfe · "
                             f"{len(self._data['devices'])} Geräte mit eigenen Vorgaben")

    def _clean_changed(self, clean):
        self._dirty = not clean
        self._refresh_summary()

    def _editable(self, row, col):
        return (0 <= row < len(self._devices) and 3 <= col < self.table.columnCount()
                and self._devices[row].type == W700 and not self.table.isRowHidden(row)
                and not self.table.isColumnHidden(col))

    def _cells(self):
        return sorted((index.row(), index.column()) for index in self.table.selectedIndexes()
                      if self._editable(index.row(), index.column()))

    def _selected_devices(self):
        return sorted({self._devices[index.row()].id for index in self.table.selectedIndexes()
                       if not self.table.isRowHidden(index.row()) and self._devices[index.row()].type == W700})

    def _selection_changed(self):
        cells = self._cells()
        self.bulk_button.setEnabled(bool(cells) and len({col for _, col in cells}) == 1)
        self.template_button.setEnabled(bool(self._selected_devices()))

    def _push(self, after, title):
        remove_redundant_overrides(after, self._project)
        before = self._data["devices"]
        if before != after:
            self.undo_stack.push(TableChange(self, copy.deepcopy(before), after, title))
        else:
            self._render_values()

    def _apply_cells(self, updates, title):
        after = copy.deepcopy(self._data["devices"])
        for row, col, text in updates:
            if not self._editable(row, col):
                raise ValueError("Nur sichtbare WLAN-Parameterzellen können bearbeitet werden.")
            key = self._keys[col - 3]
            device = self._devices[row]
            if text == "":
                if device.id in after:
                    after[device.id]["parameters"].pop(key, None)
                    if not after[device.id]["parameters"]:
                        del after[device.id]
            else:
                entry = after.setdefault(device.id, {"type": device.type, "parameters": {}})
                entry["parameters"][key] = parse_value(key, text)
        self._push(after, title)

    def _changed(self, row, col):
        if not self._loading and self._editable(row, col):
            self._apply_cells([(row, col, self.table.item(row, col).text())], "Zelle ändern")

    def _bulk_value(self):
        cells = self._cells()
        if not cells or len({col for _, col in cells}) != 1:
            return
        key = self._keys[cells[0][1] - 3]
        spec = PARAMETERS[key]
        if spec.choices:
            value, ok = QInputDialog.getItem(self, "Wert setzen", f"{spec.label} für {len(cells)} Zellen", ["", *spec.choices], 0, False)
        else:
            value, ok = QInputDialog.getText(self, "Wert setzen", f"{spec.label} für {len(cells)} Zellen")
        if ok:
            self._apply_cells([(row, col, value) for row, col in cells], "Wert gemeinsam setzen")

    def _clear_cells(self):
        self._apply_cells([(row, col, "") for row, col in self._cells()], "Vorgaben entfernen")

    def _copy_cells(self):
        selected = {(i.row(), i.column()) for i in self.table.selectedIndexes()
                    if not self.table.isRowHidden(i.row()) and not self.table.isColumnHidden(i.column())}
        if not selected:
            return
        rows = sorted({row for row, _ in selected})
        cols = sorted({col for _, col in selected})
        output = io.StringIO()
        writer = csv.writer(output, delimiter="\t", lineterminator="\n")
        writer.writerows([[self.table.item(row, col).text() if (row, col) in selected else ""
                           for col in cols] for row in rows])
        QApplication.clipboard().setText(output.getvalue())

    def _paste_cells(self):
        text = QApplication.clipboard().text()
        if not text:
            return
        try:
            matrix = list(csv.reader(io.StringIO(text), delimiter="\t", strict=True))
            if not matrix or not matrix[0] or any(len(row) != len(matrix[0]) for row in matrix):
                raise ValueError("Bitte einen rechteckigen Zellbereich kopieren.")
            cells = self._cells()
            if len(matrix) == len(matrix[0]) == 1 and cells:
                if len({col for _, col in cells}) != 1:
                    raise ValueError("Einen gemeinsamen Wert bitte innerhalb einer Parameterspalte einfügen.")
                updates = [(row, col, matrix[0][0]) for row, col in cells]
            else:
                start_row, start_col = self.table.currentRow(), self.table.currentColumn()
                if not self._editable(start_row, start_col):
                    raise ValueError("Zum Einfügen zuerst eine WLAN-Parameterzelle auswählen.")
                if len(cells) > 1:
                    start_row, start_col = min(r for r, _ in cells), min(c for _, c in cells)
                rows = [r for r in range(start_row, self.table.rowCount()) if not self.table.isRowHidden(r)][:len(matrix)]
                cols = [c for c in range(start_col, self.table.columnCount()) if not self.table.isColumnHidden(c)][:len(matrix[0])]
                if len(rows) != len(matrix) or len(cols) != len(matrix[0]):
                    raise ValueError("Der kopierte Bereich passt nicht in die Tabelle.")
                if len(cells) > 1 and set(cells) != {(r, c) for r in rows for c in cols}:
                    raise ValueError("Auswahl und kopierter Bereich müssen gleich groß und rechteckig sein.")
                updates = [(row, col, matrix[y][x]) for y, row in enumerate(rows) for x, col in enumerate(cols)]
            self._apply_cells(updates, "Zellen einfügen")
        except (ValueError, csv.Error) as exc:
            self._status(str(exc), True)

    def _context_menu(self, position):
        menu = QMenu(self.table)
        menu.addAction("Kopieren", self._copy_cells)
        menu.addAction("Einfügen", self._paste_cells)
        menu.addAction("Vorgaben entfernen", self._clear_cells)
        menu.addAction("Wert setzen …", self._bulk_value).setEnabled(self.bulk_button.isEnabled())
        menu.exec(self.table.viewport().mapToGlobal(position))

    def _template(self):
        keys = self._selected_devices()
        if not keys:
            return
        dialog = TemplateDialog(W700, self)
        if dialog.exec() != QDialog.DialogCode.Accepted or dialog.source is None:
            return
        count = sum(key in self._data["devices"] for key in keys)
        if count and QMessageBox.question(self, "Vorlage übernehmen", f"{count} vorhandene Konfiguration(en) ersetzen?\n"
                                         "Individuelle Gerätenamen und Projekt-IP bleiben erhalten.") != QMessageBox.StandardButton.Yes:
            return
        after = copy.deepcopy(self._data)
        apply_template(after, self._project, keys, dialog.source)
        self._push(after["devices"], "Vorlage übernehmen")
        for key in dialog.source["parameters"]:
            self._column_actions[key].setChecked(True)

    def _refresh_sets(self):
        self.sets.clear()
        names = list_sets(self._project.id)
        if self._data["name"] not in names:
            names.insert(0, self._data["name"])
        self.sets.addItems(names)
        self.sets.setCurrentText(self._data["name"])

    def can_leave(self):
        if not self._dirty:
            return True
        answer = QMessageBox.question(self, "Konfiguration", "Änderungen speichern?",
                                      QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard
                                      | QMessageBox.StandardButton.Cancel)
        if answer == QMessageBox.StandardButton.Save:
            return self._save()
        return answer == QMessageBox.StandardButton.Discard

    def _new(self):
        if self.can_leave():
            self._data = new_set(self._project)
            self._saved = False
            self._reset_table()

    def _load(self, *_args):
        name = self.sets.currentText()
        if name == self._data["name"]:
            return
        if not self.can_leave():
            self.sets.setCurrentText(self._data["name"])
            return
        try:
            data = load_set(self._project, name)
        except (OSError, ValueError) as exc:
            self.sets.setCurrentText(self._data["name"])
            self._status(str(exc), True)
            return
        self._data, self._saved = data, True
        self._reset_table()

    def _save(self, save_as=False):
        name = self._data["name"]
        if save_as or name == "Neuer Satz":
            name, ok = QInputDialog.getText(self, "Konfiguration speichern", "Name", text=name)
            if not ok:
                return False
        name = name.strip()
        try:
            path = set_path(self._project.id, name)
            if (path.exists() and (not self._saved or name != self._data["name"])
                    and QMessageBox.question(self, "Konfiguration ersetzen", f"„{name}“ existiert. Überschreiben?")
                    != QMessageBox.StandardButton.Yes):
                return False
            save_set(self._data, name)
        except (OSError, ValueError) as exc:
            self._status(str(exc), True)
            return False
        self._saved = True
        self.undo_stack.setClean()
        self._refresh_sets()
        self._refresh_summary()
        self._status("Arbeitskonfiguration lokal gespeichert. Der Stammdatenstand bleibt unverändert.")
        return True

    def _promote(self):
        if not self._data["devices"]:
            self._status("Keine eigenen Abweichungen zum Übernehmen vorhanden.")
            return
        if self._dirty and not self._save():
            return
        project, working = self._project, copy.deepcopy(self._data)
        if not self.before_database_edit():
            return
        try:
            changed = []
            editor = MasterDataEditor(project.database_path, project.uid, working=working, parent=self)
            editor.saved.connect(lambda: changed.append(True))
            editor.exec()
            editor.deleteLater()
            if changed:
                self.database_changed.emit()
        except (OSError, ValueError) as exc:
            self._status(str(exc), True)

    def _status(self, text, error=False):
        self.status.setText(text)
        self.status.setProperty("error", error)
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)



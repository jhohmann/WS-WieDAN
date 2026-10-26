"""Gerätekatalog: technische Definitionen ansehen, Kategorien pflegen."""

import copy
import json
from uuid import uuid4

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QDialogButtonBox, QHBoxLayout, QInputDialog,
    QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout,
)

from wiedan.core.engineering import CatalogDraft
from wiedan.core.device_fields import FIELD_TYPES


class DevicePicker(QDialog):
    def __init__(self, definitions, categories, parent=None):
        super().__init__(parent)
        self.definitions = definitions
        self.setWindowTitle("Gerät aus dem Katalog hinzufügen")
        self.resize(700, 550)
        layout = QVBoxLayout(self)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Gerätetyp, Kategorie oder Protokoll suchen")
        layout.addWidget(self.search)
        self.table = QTableWidget(len(definitions), 3)
        self.table.setHorizontalHeaderLabels(["Gerätetyp", "Kategorie", "Protokoll"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        for index, (key, definition) in enumerate(definitions.items()):
            values = (definition["label"], categories.get(definition.get("category"), "Nicht zugeordnet"),
                      str(definition.get("connection", {}).get("protocol", "")))
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, key)
                self.table.setItem(index, col, item)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 300)
        layout.addWidget(self.table)
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setMaximumHeight(150)
        layout.addWidget(self.details)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Hinzufügen")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.search.textChanged.connect(self._filter)
        self.table.itemSelectionChanged.connect(self._selection)
        self.table.itemDoubleClicked.connect(lambda: self.accept())
        self._selection()

    def selected_type(self):
        row = self.table.currentRow()
        if row >= 0 and not self.table.isRowHidden(row):
            return self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        return None

    def _selection(self):
        key = self.selected_type()
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(key is not None)
        definition = self.definitions.get(key, {})
        points = definition.get("datapoints", {})
        self.details.setPlainText(json.dumps(points, ensure_ascii=False, indent=2) if points else "Keine Datenpunkte hinterlegt.")

    def _filter(self, query):
        for row in range(self.table.rowCount()):
            self.table.setRowHidden(row, not any(query.casefold() in self.table.item(row, col).text().casefold() for col in range(3)))
        self._selection()

    def accept(self):
        if self.selected_type() is not None:
            super().accept()


class DeviceCatalogEditor(QDialog):
    saved = Signal()

    def __init__(self, source, parent=None):
        super().__init__(parent)
        self.draft = CatalogDraft(source)
        self.setWindowTitle("Gerätekatalog und Kategorien")
        self.resize(750, 550)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Gerätetypen beschreiben Protokolle und Datenpunkte. Kategorien ordnen den Katalog."))
        row = QHBoxLayout()
        self.categories = QComboBox()
        row.addWidget(self.categories, 1)
        for title, action in (("Kategorie hinzufügen", self._add), ("Umbenennen", self._rename)):
            button = QPushButton(title)
            button.clicked.connect(action)
            row.addWidget(button)
        layout.addLayout(row)
        self.table = QTableWidget()
        layout.addWidget(self.table)
        fields_button = QPushButton("Dokumentationsfelder für ausgewählten Gerätetyp …")
        fields_button.clicked.connect(self._fields)
        layout.addWidget(fields_button)
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setMaximumHeight(150)
        self.table.itemSelectionChanged.connect(self._details)
        layout.addWidget(self.details)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Close)
        self.buttons.button(QDialogButtonBox.StandardButton.Save).clicked.connect(self._save)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self._populate()

    def _populate(self):
        self.categories.clear()
        for key, label in self.draft.categories.items():
            self.categories.addItem(label, key)
        self.table.setColumnCount(3)
        self.table.setRowCount(len(self.draft.types))
        self.table.setHorizontalHeaderLabels(["Gerätetyp", "Protokoll", "Kategorie"])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setColumnWidth(0, 320)
        self.table.horizontalHeader().setStretchLastSection(True)
        for row, (key, definition) in enumerate(self.draft.types.items()):
            for col, text in enumerate((definition["label"], str(definition.get("connection", {}).get("protocol", "")))):
                item = QTableWidgetItem(text)
                item.setData(Qt.ItemDataRole.UserRole, key)
                self.table.setItem(row, col, item)
            category = QComboBox()
            category.addItem("Nicht zugeordnet", None)
            for uid, label in self.draft.categories.items():
                category.addItem(label, uid)
            category.setCurrentIndex(category.findData(self.draft.assignments[key]))
            category.currentIndexChanged.connect(lambda _index, k=key, w=category: self.draft.assignments.update({k: w.currentData()}))
            self.table.setCellWidget(row, 2, category)

    def _fields(self):
        row = self.table.currentRow()
        item = self.table.item(row, 0) if row >= 0 else None
        if item is None:
            QMessageBox.information(self, "Dokumentationsfelder", "Bitte zuerst einen Gerätetyp in der Tabelle auswählen.")
            return
        key = item.data(Qt.ItemDataRole.UserRole)
        dialog = DocumentationFieldEditor(self.draft, key, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.draft.fields.update(dialog.fields)

    def _details(self):
        row = self.table.currentRow()
        item = self.table.item(row, 0) if row >= 0 else None
        definition = self.draft.types[item.data(Qt.ItemDataRole.UserRole)] if item else {}
        self.details.setPlainText(json.dumps(definition.get("datapoints", {}), ensure_ascii=False, indent=2))

    def _add(self):
        label, ok = QInputDialog.getText(self, "Kategorie", "Bezeichnung")
        if ok:
            try:
                uid = self.draft.add_category(label)
                self._populate()
                self.categories.setCurrentIndex(self.categories.findData(uid))
            except ValueError as exc:
                QMessageBox.warning(self, "Kategorie", str(exc))

    def _rename(self):
        uid = self.categories.currentData()
        if uid is None:
            return
        label, ok = QInputDialog.getText(self, "Kategorie", "Bezeichnung", text=self.draft.categories[uid])
        if ok and label.strip():
            self.draft.categories[uid] = label.strip()
            self._populate()

    def _save(self):
        try:
            if self.draft.dirty:
                self.draft.save()
                self.saved.emit()
            return True
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Gerätekatalog", str(exc))
            return False

    def reject(self):
        if self.draft.dirty:
            answer = QMessageBox.question(self, "Gerätekatalog", "Katalogänderungen speichern?",
                                          QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard |
                                          QMessageBox.StandardButton.Cancel)
            if answer == QMessageBox.StandardButton.Cancel:
                return
            if answer == QMessageBox.StandardButton.Save and not self._save():
                return
        super().reject()


class DocumentationFieldEditor(QDialog):
    def __init__(self, draft, type_id, parent=None):
        super().__init__(parent)
        self.type_id = type_id
        self.fields = copy.deepcopy({uid: field for uid, field in draft.fields.items() if field["type_id"] == type_id})
        self.existing = set(draft.original[2])
        self.setWindowTitle(f"Dokumentationsfelder · {draft.types[type_id]['label']}")
        self.resize(560, 360)
        layout = QVBoxLayout(self)
        hint = QLabel("Die Werte werden je Gerät im Projekteditor ausgefüllt. "
                      "Gespeichert werden die Felddefinitionen mit dem Gerätekatalog.")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Feldname", "Datentyp"])
        self.table.setColumnWidth(0, 320)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)
        add = QPushButton("Feld hinzufügen")
        add.clicked.connect(self._add)
        layout.addWidget(add)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Übernehmen")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        for uid, field in self.fields.items():
            self._append(uid, field)
        self.table.itemChanged.connect(self._name_changed)

    def _append(self, uid, field):
        row = self.table.rowCount()
        self.table.insertRow(row)
        item = QTableWidgetItem(field["name"])
        item.setData(Qt.ItemDataRole.UserRole, uid)
        self.table.setItem(row, 0, item)
        kind = QComboBox()
        for key, label in FIELD_TYPES.items():
            kind.addItem(label, key)
        kind.setCurrentIndex(kind.findData(field["value_type"]))
        kind.setEnabled(uid not in self.existing)
        if uid in self.existing:
            kind.setToolTip("Der Datentyp bleibt für bereits gespeicherte Werte unverändert.")
        kind.currentIndexChanged.connect(lambda: self.fields[uid].update(value_type=kind.currentData()))
        self.table.setCellWidget(row, 1, kind)

    def _name_changed(self, item):
        uid = item.data(Qt.ItemDataRole.UserRole)
        self.fields[uid]["name"] = item.text().strip()

    def _add(self):
        name, ok = QInputDialog.getText(self, "Dokumentationsfeld", "Feldname")
        if ok and name.strip():
            uid = str(uuid4())
            self.fields[uid] = dict(uid=uid, type_id=self.type_id, name=name.strip(), value_type="text")
            self._append(uid, self.fields[uid])

    def accept(self):
        names = [field["name"].strip().casefold() for field in self.fields.values()]
        if any(not name for name in names) or len(set(names)) != len(names):
            QMessageBox.warning(self, "Dokumentationsfelder", "Bitte eindeutige, nicht leere Feldnamen verwenden.")
            return
        super().accept()

"""Stammdateneditor mit Vergleich und direkter Speicherung."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
)

from wiedan.core.master_data import FIELDS, MasterDataDraft, device_field_available, parse_field
from wiedan.core.working_configuration import PARAMETERS, available_parameters

USER_ROLE = Qt.ItemDataRole.UserRole


def display(value):
    return "" if value is None else str(value)


class ChangeReview(QDialog):
    def __init__(self, draft, proposals, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Änderungen in Stammdaten übernehmen")
        self.resize(1050, 520)
        self.proposals = proposals
        layout = QVBoxLayout(self)
        hint = QLabel("Nur markierte Änderungen übernehmen. Abweichungen vom ursprünglichen Stamm sind zunächst abgewählt.")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.table = QTableWidget(len(proposals), 6)
        self.table.setHorizontalHeaderLabels(["Übernehmen", "Projekt / Gerät", "Eigenschaft", "Ursprünglich", "Stamm jetzt", "Neuer Wert"])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for index, (key, old, current, new, conflict) in enumerate(proposals):
            check = QTableWidgetItem("Prüfen" if conflict else "")
            check.setCheckState(Qt.CheckState.Unchecked if conflict else Qt.CheckState.Checked)
            self.table.setItem(index, 0, check)
            for col, value in enumerate((*draft.describe(*key), display(old), display(current), display(new)), 1):
                self.table.setItem(index, col, QTableWidgetItem(value))
        layout.addWidget(self.table)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Auswahl übernehmen")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Abbrechen")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected(self):
        return {key: value for index, (key, _old, _current, value, _conflict) in enumerate(self.proposals)
                if self.table.item(index, 0).checkState() == Qt.CheckState.Checked}


class MasterDataEditor(QDialog):
    saved = Signal()

    def __init__(self, source, project_uid=None, working=None, parent=None):
        super().__init__(parent)
        self.draft = MasterDataDraft(source)
        self.setWindowTitle("Stammdateneditor")
        self.resize(1150, 720)
        layout = QVBoxLayout(self)
        self.hint = QLabel()
        self.hint.setWordWrap(True)
        self.hint.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.hint)
        toolbar = QHBoxLayout()
        self.projects = QComboBox()
        self.projects.addItem("Alle Projekte", None)
        for uid, row in self.draft.rows["projects"].items():
            self.projects.addItem(row["display_name"], uid)
        self.projects.setCurrentIndex(max(0, self.projects.findData(project_uid)))
        self.projects.currentIndexChanged.connect(self._filter)
        toolbar.addWidget(self.projects)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Gerät, IP oder Bezeichnung suchen")
        self.search.textChanged.connect(self._filter)
        toolbar.addWidget(self.search, 1)
        reset = QPushButton("Änderungen verwerfen")
        reset.clicked.connect(self._discard)
        toolbar.addWidget(reset)
        layout.addLayout(toolbar)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)
        footer = QHBoxLayout()
        self.summary = QLabel()
        footer.addWidget(self.summary, 1)
        self.save_button = QPushButton("Änderungen speichern")
        self.save_button.clicked.connect(self._save)
        footer.addWidget(self.save_button)
        close = QPushButton("Schließen")
        close.clicked.connect(self.reject)
        footer.addWidget(close)
        layout.addLayout(footer)
        self._populate()
        if working is not None:
            proposals = self.draft.proposals(working)
            if proposals:
                review = ChangeReview(self.draft, proposals, self)
                if review.exec() == QDialog.DialogCode.Accepted:
                    for key, value in review.selected().items():
                        self.draft.change(*key, value)
                self._populate()
            else:
                QMessageBox.information(self, "Stammdaten", "Keine Abweichungen zum aktiven Stamm vorhanden.")

    def _populate(self):
        selected_tab = self.tabs.currentIndex()
        while self.tabs.count():
            widget = self.tabs.widget(0)
            self.tabs.removeTab(0)
            widget.deleteLater()
        self.tables = {}
        titles = {"projects": "Projekte", "vehicles": "Fahrzeuge", "nodes": "Gruppen", "devices": "Geräte"}
        for name, fields in FIELDS.items():
            columns = list(fields)
            if name == "devices":
                columns += [f"parameter:{key}" for key in PARAMETERS if key != "ip"]
            rows = list(self.draft.rows[name].values())
            table = QTableWidget(len(rows), 2 + len(columns))
            table.setAlternatingRowColors(True)
            table.setHorizontalHeaderLabels(["Projekt", "Gerät / Pfad" if name == "devices" else "Kennung"] + [
                PARAMETERS[field.split(":", 1)[1]].label if field.startswith("parameter:") else fields[field][0]
                for field in columns])
            table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
            table.setColumnWidth(0, 150)
            table.setColumnWidth(1, 210)
            for index, row in enumerate(rows):
                uid = row["uid"]
                project_uid = uid if name == "projects" else row["project_uid"]
                label = self.draft.rows["projects"][project_uid]["display_name"]
                for col, value in enumerate((label, row.get("path", row.get("project_id", uid)))):
                    item = QTableWidgetItem(value)
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    item.setData(USER_ROLE, project_uid)
                    table.setItem(index, col, item)
                for col, field in enumerate(columns, 2):
                    key = (name, uid, field)
                    item = QTableWidgetItem(display(self.draft.value(*key)))
                    item.setData(USER_ROLE, key)
                    editable = True
                    if field.startswith("parameter:"):
                        editable = field.split(":", 1)[1] in available_parameters(row["type_id"])
                    elif name == "devices":
                        editable = device_field_available(field, self.draft.value("devices", uid, "parameter:role"))
                    if not editable:
                        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                        item.setToolTip("Für diesen Gerätetyp nicht vorgesehen.")
                    else:
                        item.setToolTip(f"Stammwert: {display(self.draft.original(*key))}\n"
                                        "Leere Gerätebezeichnung / Pingbar: Typvorgabe; leere Parameter: keine Stammvorgabe.")
                    font = item.font()
                    font.setBold(key in self.draft.changes)
                    item.setFont(font)
                    table.setItem(index, col, item)
            table.itemChanged.connect(self._changed)
            self.tables[name] = table
            self.tabs.addTab(table, titles[name])
        self.tabs.setCurrentIndex(max(0, selected_tab))
        self.hint.setText(f"Ausgangsdatenstand: {self.draft.info['data_version']} · {self.draft.source}\n"
                          "Änderungen werden nach einem Vergleich in dieser Datenbank gespeichert.")
        self._filter()
        self._summary()

    def _changed(self, item):
        key = item.data(USER_ROLE)
        if not isinstance(key, (tuple, list)):
            return
        key = tuple(key)
        table = item.tableWidget()
        table.blockSignals(True)
        try:
            self.draft.change(*key, parse_field(key[0], key[2], item.text()))
        except ValueError as exc:
            QMessageBox.warning(self, "Eingabe", str(exc))
        finally:
            item.setText(display(self.draft.value(*key)))
            font = item.font()
            font.setBold(key in self.draft.changes)
            item.setFont(font)
            table.blockSignals(False)
        self._summary()
        if key[2] == "parameter:role":
            self._populate()

    def _filter(self, *_args):
        query = self.search.text().casefold().strip()
        project_uid = self.projects.currentData()
        for table in getattr(self, "tables", {}).values():
            for row in range(table.rowCount()):
                matches = project_uid is None or table.item(row, 0).data(USER_ROLE) == project_uid
                matches &= any(query in table.item(row, col).text().casefold() for col in range(table.columnCount()))
                table.setRowHidden(row, not matches)

    def _summary(self):
        self.summary.setText(f"{len(self.draft.changes)} ungespeicherte Änderungen · Fett = geändert")
        self.save_button.setEnabled(bool(self.draft.changes))

    def _discard(self):
        if self.draft.changes and QMessageBox.question(self, "Änderungen verwerfen", "Alle Änderungen im Editor verwerfen?") != QMessageBox.StandardButton.Yes:
            return
        self.draft.changes.clear()
        self._populate()

    def _save(self):
        proposals = [(key, self.draft.original(*key), self.draft.original(*key), value, False)
                     for key, value in self.draft.changes.items()]
        review = ChangeReview(self.draft, proposals, self)
        if review.exec() != QDialog.DialogCode.Accepted or not review.selected():
            return False
        changes = self.draft.changes.copy()
        self.draft.changes = review.selected()
        try:
            self.draft.save_current()
        except (OSError, ValueError) as exc:
            self.draft.changes = changes
            QMessageBox.warning(self, "Stammdaten", str(exc))
            return False
        remaining = {key: value for key, value in changes.items() if key not in self.draft.changes}
        self.draft = MasterDataDraft(self.draft.source)
        for key, value in remaining.items():
            self.draft.change(*key, value)
        self._populate()
        self.saved.emit()
        return not self.draft.changes

    def reject(self):
        if self.draft.changes:
            answer = QMessageBox.question(self, "Stammdateneditor", "Änderungen speichern?",
                                          QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard
                                          | QMessageBox.StandardButton.Cancel)
            if answer == QMessageBox.StandardButton.Cancel:
                return
            if answer == QMessageBox.StandardButton.Save and not self._save():
                return
        super().reject()

"""Lokale Einstellungen für die Verbindung zum Stammdatenbestand."""

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)


class SettingsDialog(QDialog):
    master_data_requested = Signal()
    project_editor_requested = Signal()
    catalog_requested = Signal()

    def __init__(self, database_path: Path, info: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Einstellungen")
        self.resize(640, 420)
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        label = QLabel("Lokale Stammdatenbank")
        self.path_edit = QLineEdit(str(database_path))
        self.path_edit.setPlaceholderText("Pfad zur SQLite-Datenbank")
        self.path_edit.setCursorPosition(0)
        label.setBuddy(self.path_edit)
        layout.addWidget(label)
        row = QHBoxLayout()
        row.addWidget(self.path_edit, 1)
        browse = QPushButton("Durchsuchen …")
        browse.clicked.connect(self._browse)
        row.addWidget(browse)
        layout.addLayout(row)
        current = QLabel(f"Aktiver Datenstand: {info['data_version']} · Format {info['schema_version']} · "
                         f"{info['project_count']} Projekte\n"
                         "Engineering-Änderungen werden direkt in dieser Arbeitsdatenbank gespeichert.")
        current.setWordWrap(True)
        layout.addWidget(current)
        engineering = QGroupBox("Engineering · aktive Datenbank bearbeiten")
        engineering_layout = QVBoxLayout(engineering)
        for title, signal in (("Projekteditor öffnen …", self.project_editor_requested),
                              ("Gerätekatalog bearbeiten …", self.catalog_requested),
                              ("Stammdaten tabellarisch bearbeiten …", self.master_data_requested)):
            button = QPushButton(title)
            button.clicked.connect(signal)
            engineering_layout.addWidget(button)
        layout.addWidget(engineering)
        layout.addStretch()
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Übernehmen")
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setDefault(True)
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Abbrechen")
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def _browse(self):
        filename, _ = QFileDialog.getOpenFileName(
            self, "Lokale Stammdatenbank auswählen", self.path_edit.text(),
            "WieDAN-Stammdatenbank (*.sqlite *.db)",
        )
        if filename:
            self.path_edit.setText(filename)


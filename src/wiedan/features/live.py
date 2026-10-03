"""Modus Live: Projekt-Explorer (Seitenleiste) und Geräte-Tabs (Hauptfenster)."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QTabWidget, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

from wiedan.core.model import Device, Project
from wiedan.ui.icons import icon

DEVICE_ROLE = Qt.ItemDataRole.UserRole


class ProjectExplorer(QTreeWidget):
    """Baum Zentrale/Fahrzeuge/Geräte. Doppelklick auf ein Gerät meldet seine ID."""

    device_opened = Signal(str)

    def __init__(self):
        super().__init__()
        self.setHeaderHidden(True)
        self.setIndentation(14)
        self.itemDoubleClicked.connect(self._on_double_click)
        self._project: Project | None = None
        self._color = "#6e6e6e"

    def set_project(self, project: Project, color: str):
        self._project = project
        self._color = color
        self._rebuild()

    def set_color(self, color: str):
        self._color = color
        self._rebuild()

    def _rebuild(self):
        self.clear()
        if self._project is None:
            return
        groups = {None: self._group("Zentrale", "central")}
        for vid, label in self._project.vehicles.items():
            groups[vid] = self._group(label, "vehicle")
        for device in self._project.devices.values():
            item = QTreeWidgetItem(groups[device.vehicle], [device.label])
            item.setIcon(0, icon("device", self._color))
            item.setData(0, DEVICE_ROLE, device.id)
    def _group(self, label: str, icon_name: str) -> QTreeWidgetItem:
        item = QTreeWidgetItem(self, [label])
        item.setIcon(0, icon(icon_name, self._color))
        return item

    def _on_double_click(self, item: QTreeWidgetItem, _column: int):
        device_id = item.data(0, DEVICE_ROLE)
        if device_id:
            self.device_opened.emit(device_id)


class DevicePage(QWidget):
    """Platzhalter der Datenseite. Inhalt legt der Nutzer fest."""

    def __init__(self, device: Device):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(QLabel(f"{device.label}  ({device.id})"))


class LiveArea(QTabWidget):
    """Tabs der geöffneten Geräte; ein Gerät hat höchstens einen Tab."""

    def __init__(self):
        super().__init__()
        self.setTabsClosable(True)
        self.setDocumentMode(True)
        self.tabCloseRequested.connect(self._close)
        self._tabs: dict[str, QWidget] = {}

    def open_device(self, device: Device):
        page = self._tabs.get(device.id)
        if page is None:
            page = DevicePage(device)
            self._tabs[device.id] = page
            self.addTab(page, device.label)
        self.setCurrentWidget(page)

    def close_all(self):
        self.clear()
        self._tabs.clear()

    def _close(self, index: int):
        page = self.widget(index)
        self._tabs = {k: v for k, v in self._tabs.items() if v is not page}
        self.removeTab(index)

"""Modus Live: Projekt-Explorer (Seitenleiste) und Geräte-Tabs (Hauptfenster)."""
import subprocess

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Qt, Signal, Slot
from PySide6.QtWidgets import QLabel, QTabWidget, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

from wiedan.core.model import Device, Project
from wiedan.core.ping import ping_devices
from wiedan.ui.icons import icon, pick

DEVICE_ROLE = Qt.ItemDataRole.UserRole


class _ReachabilitySignals(QObject):
    finished = Signal(int, object, object)


class _ReachabilityTask(QRunnable):
    def __init__(self, generation: int, addresses: dict[str, str]):
        super().__init__()
        self.setAutoDelete(False)
        self.generation = generation
        self.addresses = addresses
        self.signals = _ReachabilitySignals()

    def run(self):
        try:
            results = ping_devices(self.addresses)
        except (OSError, subprocess.SubprocessError) as exc:
            self.signals.finished.emit(self.generation, None, str(exc))
        else:
            self.signals.finished.emit(self.generation, results, None)


class ProjectExplorer(QTreeWidget):
    """Baum Zentrale/Fahrzeuge/Geräte. Doppelklick auf ein Gerät meldet seine ID."""

    device_opened = Signal(str)
    reachability_check_started = Signal()
    reachability_check_finished = Signal(object, object)

    def __init__(self):
        super().__init__()
        self.setHeaderHidden(True)
        self.setIndentation(14)
        self.itemDoubleClicked.connect(self._on_double_click)
        self._project: Project | None = None
        self._color = "#6e6e6e"
        self._reachable_color = "#218838"
        self._unreachable_color = "#c62828"
        self._reachability: dict[str, bool] = {}
        self._reachability_task: _ReachabilityTask | None = None
        self._project_generation = 0

    def set_project(self, project: Project):
        self._project_generation += 1
        self._project = project
        self._reachability.clear()
        self._rebuild()

    def set_status_colors(self, neutral: str, reachable: str, unreachable: str):
        self._color = neutral
        self._reachable_color = reachable
        self._unreachable_color = unreachable
        self._rebuild()

    @property
    def reachability_check_running(self) -> bool:
        return self._reachability_task is not None

    def check_reachability(self):
        if self._project is None or self._reachability_task is not None:
            return
        addresses = {
            device.id: device.connection["ip"]
            for device in self._project.devices.values()
            if device.pingable
        }
        if not addresses:
            return

        generation = self._project_generation
        task = _ReachabilityTask(generation, addresses)
        self._reachability_task = task
        task.signals.finished.connect(self._on_reachability_finished)
        self._reachability.clear()
        self._rebuild()
        self.reachability_check_started.emit()
        QThreadPool.globalInstance().start(task)

    @Slot(int, object, object)
    def _on_reachability_finished(self, generation: int, results, error):
        self._reachability_task = None
        is_current_project = generation == self._project_generation
        if is_current_project and error is None:
            self._reachability = results
            self._rebuild()
        self.reachability_check_finished.emit(
            results if is_current_project else None,
            error if is_current_project else None,
        )

    def _rebuild(self):
        self.clear()
        if self._project is None:
            return
        groups = {None: self._group("Zentrale", "central")}
        for vid, label in self._project.vehicles.items():
            groups[vid] = self._group(label, pick(self._project.vehicle_products[vid], "vehicle"))
        for device in self._project.devices.values():
            item = QTreeWidgetItem(groups[device.vehicle], [device.label])
            status = self._reachability.get(device.id)
            color = (
                self._reachable_color if status is True
                else self._unreachable_color if status is False
                else self._color
            )
            item.setIcon(0, icon(pick(device.category, "device"), color))
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

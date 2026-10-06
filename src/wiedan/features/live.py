"""Modus Live: Projekt-Explorer (Seitenleiste) und Geräte-Tabs (Hauptfenster)."""
import subprocess

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Qt, Signal, Slot
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QLabel, QMenu, QTabWidget, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from wiedan.core.model import Device, Node, Project
from wiedan.core.ping import ping_devices
from wiedan.ui.icons import icon, pick
from wiedan.ui.spinner import spinner_icon

DEVICE_ROLE = Qt.ItemDataRole.UserRole
VEHICLE_ROLE = Qt.ItemDataRole.UserRole + 1
NODE_ROLE = Qt.ItemDataRole.UserRole + 2


class _ReachabilitySignals(QObject):
    finished = Signal(int, object, object)
    progress = Signal(int, str, bool)


class _ReachabilityTask(QRunnable):
    def __init__(self, generation: int, addresses: dict[str, str]):
        super().__init__()
        self.setAutoDelete(False)
        self.generation = generation
        self.addresses = addresses
        self.signals = _ReachabilitySignals()

    def run(self):
        try:
            results = ping_devices(
                self.addresses,
                lambda device_id, ok: self.signals.progress.emit(
                    self.generation, device_id, ok
                ),
            )
        except (OSError, subprocess.SubprocessError) as exc:
            self.signals.finished.emit(self.generation, None, str(exc))
        else:
            self.signals.finished.emit(self.generation, results, None)


class ProjectExplorer(QTreeWidget):
    """Baum Zentrale/Fahrzeuge/Geräte. Doppelklick auf ein Gerät meldet seine ID."""

    device_opened = Signal(str)
    reachability_check_started = Signal()
    reachability_check_finished = Signal(object, object)
    vehicle_activity_changed = Signal()

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
        self._inactive_vehicles_by_project: dict[str, set[str]] = {}
        self._pending: set[str] = set()
        self._items: dict[str, QTreeWidgetItem] = {}
        self._groups: dict[str, QTreeWidgetItem] = {}
        self._nodes: dict[str, Node] = {}
        self._spin_angle = 0
        self._spin_timer = QTimer(self)
        self._spin_timer.timeout.connect(self._spin)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def set_project(self, project: Project):
        self._project_generation += 1
        self._project = project
        self._reachability.clear()
        self._pending.clear()
        self._rebuild()

    def set_status_colors(self, neutral: str, reachable: str, unreachable: str):
        self._color = neutral
        self._reachable_color = reachable
        self._unreachable_color = unreachable
        self._rebuild()

    @property
    def reachability_check_running(self) -> bool:
        return self._reachability_task is not None

    @property
    def active_devices(self) -> tuple[Device, ...]:
        if self._project is None:
            return ()
        inactive = self._inactive_vehicles_by_project.get(self._project.id, set())
        return tuple(
            device for device in self._project.devices.values()
            if device.vehicle not in inactive
        )

    def _pingable_addresses(self, scope: set[str] | None) -> dict[str, str]:
        return {
            device.id: device.connection["ip"]
            for device in self.active_devices
            if device.pingable and (scope is None or device.id in scope)
        }

    def _can_ping(self, scope: set[str] | None = None) -> bool:
        return (
            self._project is not None
            and self._reachability_task is None
            and bool(self._pingable_addresses(scope))
        )

    def check_reachability(self, scope: set[str] | None = None):
        """Pingt aktive, pingbare Geräte; scope=None: ganzes Projekt."""
        if not self._can_ping(scope):
            return
        addresses = self._pingable_addresses(scope)

        generation = self._project_generation
        task = _ReachabilityTask(generation, addresses)
        self._reachability_task = task
        task.signals.finished.connect(self._on_reachability_finished)
        task.signals.progress.connect(self._on_reachability_progress)
        for device_id in addresses:
            self._reachability.pop(device_id, None)
        self._pending = set(addresses)
        self._spin_timer.start(80)
        self._rebuild()
        self.reachability_check_started.emit()
        QThreadPool.globalInstance().start(task)

    @Slot(int, str, bool)
    def _on_reachability_progress(self, generation: int, device_id: str, ok: bool):
        if generation != self._project_generation:
            return
        self._pending.discard(device_id)
        self._reachability[device_id] = ok
        item = self._items.get(device_id)
        if item is None:
            return
        device = self._project.devices[device_id]
        self._style_device_item(item, device, ok, self._is_inactive(device))
        parent = item.parent()
        while parent is not None:
            self._style_group(parent)
            parent = parent.parent()

    def _spin(self):
        self._spin_angle = (self._spin_angle + 30) % 360
        frame = spinner_icon(self._color, self._spin_angle)
        for device_id in self._pending:
            item = self._items.get(device_id)
            if item is not None:
                item.setIcon(0, frame)

    def _is_inactive(self, device: Device) -> bool:
        return device.vehicle in self._inactive_vehicles_by_project.get(
            self._project.id, set()
        )

    @Slot(int, object, object)
    def _on_reachability_finished(self, generation: int, results, error):
        self._reachability_task = None
        self._pending.clear()
        self._spin_timer.stop()
        is_current_project = generation == self._project_generation
        if is_current_project and error is None:
            active_ids = {device.id for device in self.active_devices}
            results = {
                device_id: status for device_id, status in results.items()
                if device_id in active_ids
            }
            self._reachability.update(results)
            self._rebuild()
        self.reachability_check_finished.emit(
            results if is_current_project and error is None else None,
            error if is_current_project else None,
        )

    def _rebuild(self):
        expanded = {node_id for node_id, group in self._groups.items() if group.isExpanded()}
        was_empty = self.topLevelItemCount() == 0
        self.clear()
        self._items = {}
        self._groups = {}
        if self._project is None:
            return
        self._add_node(self, self._project.central, None)
        for vid, node in self._project.vehicle_nodes.items():
            self._add_node(self, node, vid)
        for node_id, group in self._groups.items():
            self._style_group(group)
            if not was_empty and node_id in expanded:
                group.setExpanded(True)

    def _add_node(self, parent, node: Node, vehicle_id: str | None):
        """Knoten samt Unterknoten und Geräten rekursiv in den Baum eintragen."""
        group = QTreeWidgetItem(parent, [node.label])
        group.setData(0, NODE_ROLE, node.id)
        group.setData(0, VEHICLE_ROLE, vehicle_id)
        self._groups[node.id] = group
        self._nodes[node.id] = node
        for child in node.children:
            self._add_node(group, child, vehicle_id)
        inactive = vehicle_id in self._inactive_vehicles_by_project.get(self._project.id, set())
        for device_id in node.devices:
            device = self._project.devices[device_id]
            item = QTreeWidgetItem(group, [device.label])
            item.setData(0, DEVICE_ROLE, device.id)
            self._items[device.id] = item
            self._style_device_item(item, device, self._reachability.get(device.id), inactive)

    def _group_icon_name(self, group: QTreeWidgetItem, vehicle_id: str | None) -> str:
        if group.parent() is not None:
            return "project"
        if vehicle_id is None:
            return "central"
        return pick(self._project.vehicle_products[vehicle_id], "vehicle")

    def _style_group(self, group: QTreeWidgetItem):
        """Gruppe grün, wenn alle pingbaren Geräte erreichbar; bei Fehler aufklappen bis zum Gerät."""
        node = self._nodes[group.data(0, NODE_ROLE)]
        vehicle_id = group.data(0, VEHICLE_ROLE)
        inactive = vehicle_id in self._inactive_vehicles_by_project.get(self._project.id, set())
        statuses = [
            self._reachability.get(device_id)
            for device_id in node.walk_devices()
            if self._project.devices[device_id].pingable
        ]
        all_ok = not inactive and bool(statuses) and all(s is True for s in statuses)
        any_failed = not inactive and any(s is False for s in statuses)
        color = (
            self._reachable_color if all_ok
            else self._unreachable_color if any_failed
            else self._color
        )
        group.setIcon(0, icon(self._group_icon_name(group, vehicle_id), color))
        if all_ok or any_failed or inactive:
            group.setForeground(0, QBrush(QColor(color)))
        else:
            group.setForeground(0, QBrush())
        if any_failed:
            group.setExpanded(True)

    def _show_context_menu(self, position):
        item = self.itemAt(position)
        if item is None or self._project is None:
            return
        menu = QMenu(self)
        device_id = item.data(0, DEVICE_ROLE)
        vehicle_id = item.data(0, VEHICLE_ROLE)
        if vehicle_id is not None and item.parent() is None:
            inactive = self._inactive_vehicles_by_project.setdefault(self._project.id, set())
            menu.addAction(
                "Aktiv setzen" if vehicle_id in inactive else "Inaktiv setzen"
            ).triggered.connect(lambda: self._toggle_vehicle_active(vehicle_id))
        if device_id:
            scope = {device_id}
            ping = menu.addAction("Gerät anpingen")
        else:
            scope = set(self._nodes[item.data(0, NODE_ROLE)].walk_devices())
            ping = menu.addAction("Alle Geräte anpingen")
        ping.triggered.connect(lambda: self.check_reachability(scope))
        ping.setEnabled(self._can_ping(scope))
        menu.exec(self.viewport().mapToGlobal(position))

    def _toggle_vehicle_active(self, vehicle_id: str):
        inactive = self._inactive_vehicles_by_project.setdefault(self._project.id, set())
        if vehicle_id in inactive:
            inactive.remove(vehicle_id)
        else:
            inactive.add(vehicle_id)
        self._refresh_vehicle_appearance(vehicle_id)
        self.vehicle_activity_changed.emit()

    def _refresh_vehicle_appearance(self, vehicle_id: str):
        inactive = vehicle_id in self._inactive_vehicles_by_project.get(self._project.id, set())
        node = self._project.vehicle_nodes.get(vehicle_id)
        if node is None:
            return
        for group in self._groups.values():
            if group.data(0, VEHICLE_ROLE) == vehicle_id:
                self._style_group(group)
        for device_id in node.walk_devices():
            device = self._project.devices[device_id]
            status = self._reachability.get(device_id)
            self._style_device_item(self._items[device_id], device, status, inactive)

    def _style_device_item(
        self, item: QTreeWidgetItem, device: Device, status: bool | None, inactive: bool
    ):
        color = self._device_color(status, inactive)
        if device.id in self._pending:
            item.setIcon(0, spinner_icon(self._color, self._spin_angle))
        else:
            item.setIcon(0, icon(pick(device.category, "device"), color))
        if inactive or status is not None:
            item.setForeground(0, QBrush(QColor(color)))
        else:
            item.setForeground(0, QBrush())

    def _device_color(self, status: bool | None, inactive: bool = False) -> str:
        if inactive:
            return self._color
        if status is True:
            return self._reachable_color
        if status is False:
            return self._unreachable_color
        return self._color

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

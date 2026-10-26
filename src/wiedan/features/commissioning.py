"""Inbetriebnahme: Tool-Kategorien und Bereich, in dem das gewählte Tool läuft.

Neues Tool hinzufügen: Widget-Modul unter features/ anlegen und einen Eintrag in TOOLS ergänzen.
"""
from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QLabel,
    QScrollArea,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from wiedan.features.modbus_browser import ModbusBrowser
from wiedan.features.hima_ringbuffer import HimaRingbuffer
from wiedan.features.scalance_config import ScalanceConfigGenerator
from wiedan.ui.tool_tile import ToolTile


@dataclass(frozen=True)
class ToolSpec:
    id: str
    title: str
    description: str
    icon: str  # Name einer SVG in ui/svg/
    category: str
    create: Callable[[], QWidget] | None  # None = vorbereiteter, noch nicht verfügbarer Eintrag
    requires_project: bool = False


TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec(
        "modbus-browser", "Modbus Browser", "schreiben und lesen über Modbus/TCP",
        "modbus", "Universal", ModbusBrowser,
    ),
    ToolSpec(
        "scalance-config-generator", "Scalance Config Generator",
        "Konfigurationen planen",
        "comms", "Siemens", ScalanceConfigGenerator, requires_project=True,
    ),
    ToolSpec(
        "hima-ringbuffer", "Ringbuffer", "1000 Samples auf 8 Kanälen auslesen",
        "plc", "HIMA", HimaRingbuffer,
    ),
)


class ToolBrowser(QScrollArea):
    tool_chosen = Signal(str)  # Tool-ID

    def __init__(self):
        super().__init__()
        self.setObjectName("toolbrowser")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._tiles: list[ToolTile] = []
        self._tiles_by_id: dict[str, ToolTile] = {}
        self._buttons = QButtonGroup(self)
        content = QWidget()
        content.setObjectName("toolbrowsercontent")
        self.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(8, 4, 8, 8)
        layout.setSpacing(12)
        for category in dict.fromkeys(spec.category for spec in TOOLS):
            heading = QToolButton()
            heading.setObjectName("toolcategory")
            heading.setText(category)
            heading.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            heading.setArrowType(Qt.ArrowType.DownArrow)
            heading.setCheckable(True)
            heading.setChecked(True)
            layout.addWidget(heading)

            category_tools = QWidget()
            category_layout = QVBoxLayout(category_tools)
            category_layout.setContentsMargins(0, 0, 0, 0)
            category_layout.setSpacing(12)
            for spec in TOOLS:
                if spec.category != category:
                    continue
                tile = ToolTile(spec.id, spec.title, spec.description, spec.icon)
                tile.setEnabled(spec.create is not None)
                if spec.create is None:
                    tile.setToolTip("In Vorbereitung")
                tile.activated.connect(self.tool_chosen)
                self._buttons.addButton(tile)
                self._tiles.append(tile)
                self._tiles_by_id[spec.id] = tile
                category_layout.addWidget(tile)
            heading.toggled.connect(
                lambda expanded, button=heading, group=category_tools:
                    self._toggle_category(button, group, expanded)
            )
            layout.addWidget(category_tools)
        layout.addStretch(1)
        self.set_project_available(False)

    def set_project_available(self, available: bool):
        for spec in TOOLS:
            tile = self._tiles_by_id[spec.id]
            enabled = spec.create is not None and (available or not spec.requires_project)
            tile.setEnabled(enabled)
            tile.setToolTip(spec.description if enabled else (
                "Bitte ein Projekt auswählen" if spec.requires_project else "In Vorbereitung"
            ))

    @staticmethod
    def _toggle_category(button: QToolButton, group: QWidget, expanded: bool):
        group.setVisible(expanded)
        button.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)

    def set_icon_color(self, color: str):
        for tile in self._tiles:
            tile.set_icon_color(color)


class CommissioningArea(QStackedWidget):
    """Eine Instanz pro Tool, damit der Zustand (z. B. Verbindung) beim Wechseln erhalten bleibt."""

    message = Signal(str)
    database_changed = Signal()

    def __init__(self):
        super().__init__()
        self._specs = {spec.id: spec for spec in TOOLS}
        self._pages: dict[str, QWidget] = {}
        self._project = None
        self.before_database_edit = lambda: True
        hint = QLabel("Tool im Tool-Browser auswählen")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.addWidget(hint)

    def open_tool(self, tool_id: str):
        spec = self._specs[tool_id]
        if spec.create is None or (spec.requires_project and self._project is None):
            return
        if tool_id not in self._pages:
            page = spec.create()
            if hasattr(page, "database_changed"):
                page.database_changed.connect(self.database_changed)
                page.before_database_edit = lambda: self.before_database_edit()
            if self._project is not None and hasattr(page, "set_project"):
                page.set_project(self._project)
            message = getattr(page, "message", None)
            if message is not None:
                message.connect(self.message)
            self._pages[tool_id] = page
            self.addWidget(page)
        self.setCurrentWidget(self._pages[tool_id])

    def set_project(self, project):
        self._project = project
        for tool_id, page in self._pages.items():
            available = project is not None or not self._specs[tool_id].requires_project
            page.setEnabled(available)
            if not available and self.currentWidget() is page:
                self.setCurrentIndex(0)
            if project is not None and hasattr(page, "set_project"):
                page.set_project(project)

    def can_leave_project(self) -> bool:
        return all(page.can_leave() for page in self._pages.values() if hasattr(page, "can_leave"))

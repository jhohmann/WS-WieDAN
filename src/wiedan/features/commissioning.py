"""Inbetriebnahme: Tool-Browser (Kachelliste) und Bereich, in dem das gewählte Tool läuft.

Neues Tool hinzufügen: Widget-Modul unter features/ anlegen und einen Eintrag in TOOLS ergänzen.
"""
from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QButtonGroup, QLabel, QStackedWidget, QVBoxLayout, QWidget

from wiedan.features.modbus_browser import ModbusBrowser
from wiedan.ui.tool_tile import ToolTile


@dataclass(frozen=True)
class ToolSpec:
    id: str
    title: str
    description: str
    icon: str  # Name einer SVG in ui/svg/
    create: Callable[[], QWidget]


TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec(
        "modbus-browser", "Modbus Browser", "schreiben und lesen über Modbus/TCP",
        "modbus", ModbusBrowser,
    ),
)


class ToolBrowser(QWidget):
    tool_chosen = Signal(str)  # Tool-ID

    def __init__(self):
        super().__init__()
        self._tiles: list[ToolTile] = []
        self._buttons = QButtonGroup(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 8)
        layout.setSpacing(12)
        for spec in TOOLS:
            tile = ToolTile(spec.id, spec.title, spec.description, spec.icon)
            tile.activated.connect(self.tool_chosen)
            self._buttons.addButton(tile)
            self._tiles.append(tile)
            layout.addWidget(tile)
        layout.addStretch(1)

    def set_icon_color(self, color: str):
        for tile in self._tiles:
            tile.set_icon_color(color)


class CommissioningArea(QStackedWidget):
    """Eine Instanz pro Tool, damit der Zustand (z. B. Verbindung) beim Wechseln erhalten bleibt."""

    message = Signal(str)

    def __init__(self):
        super().__init__()
        self._specs = {spec.id: spec for spec in TOOLS}
        self._pages: dict[str, QWidget] = {}
        hint = QLabel("Tool im Tool-Browser auswählen")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.addWidget(hint)

    def open_tool(self, tool_id: str):
        if tool_id not in self._pages:
            page = self._specs[tool_id].create()
            message = getattr(page, "message", None)
            if message is not None:
                message.connect(self.message)
            self._pages[tool_id] = page
            self.addWidget(page)
        self.setCurrentWidget(self._pages[tool_id])

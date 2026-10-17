"""App-Kachel für den Tool-Browser. Ohne Tool-Logik."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout

from wiedan.ui.icons import icon

ICON_SIZE = 40


class ToolTile(QPushButton):
    activated = Signal(str)  # Tool-ID

    def __init__(self, tool_id: str, title: str, description: str, icon_name: str):
        super().__init__()
        self.setObjectName("tooltile")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setCheckable(True)
        self.setAutoDefault(False)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumWidth(176)
        self.setMinimumHeight(92)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAccessibleName(title)
        self.setAccessibleDescription(description)
        self.setToolTip(description)
        self._tool_id = tool_id
        self._icon_name = icon_name

        self._icon = QLabel()
        self._icon.setObjectName("tooltileicon")
        self._icon.setFixedSize(60, 60)
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label = QLabel(title)
        title_label.setObjectName("tooltiletitle")
        title_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        title_label.setWordWrap(True)
        description_label = QLabel(description)
        description_label.setObjectName("tooltiledesc")
        description_label.setWordWrap(True)
        description_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        for label in (self._icon, title_label, description_label):
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        texts = QVBoxLayout()
        texts.setSpacing(4)
        texts.addWidget(title_label)
        texts.addWidget(description_label)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        layout.addWidget(self._icon, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(texts, 1)
        self.clicked.connect(lambda: self.activated.emit(self._tool_id))

    def set_icon_color(self, color: str):
        self._icon.setPixmap(icon(self._icon_name, color).pixmap(ICON_SIZE, ICON_SIZE))

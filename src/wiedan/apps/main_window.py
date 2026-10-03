"""Hauptfenster: Kopfzeile, Activity Bar, Seitenleiste, Hauptbereich, Statusleiste."""
import sys

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QComboBox, QFrame, QHBoxLayout, QLabel, QMainWindow,
    QSplitter, QStackedWidget, QToolButton, QVBoxLayout, QWidget,
)

from wiedan.core.model import list_projects, load_project
from wiedan.core.settings import load_settings, save_settings
from wiedan.features.live import LiveArea, ProjectExplorer
from wiedan.ui.icons import icon
from wiedan.ui.theme import DEFAULT_THEME, THEMES, stylesheet

# (Schlüssel, Name, Icon)
MODES = [
    ("live", "Live", "live"),
    ("commissioning", "Inbetriebnahme", "commissioning"),
    ("plotter", "Plotter", "plotter"),
]


def _placeholder(text: str) -> QLabel:
    label = QLabel(text)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return label


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("WieDAN")
        self.resize(1200, 750)
        self._settings = load_settings()
        self._project = None

        self.explorer = ProjectExplorer()
        self.live_area = LiveArea()
        self.explorer.device_opened.connect(
            lambda device_id: self.live_area.open_device(self._project.devices[device_id])
        )

        self.sidebar = QStackedWidget()
        self.content = QStackedWidget()
        self.content.setObjectName("content")
        self.sidebar.addWidget(self._sidebar_page("Projekt-Explorer", self.explorer))
        self.sidebar.addWidget(self._sidebar_page("Tool-Browser", _placeholder("folgt")))
        self.sidebar.addWidget(self._sidebar_page("Kanäle", _placeholder("folgt")))
        self.content.addWidget(self.live_area)
        self.content.addWidget(_placeholder("Inbetriebnahme folgt"))
        self.content.addWidget(_placeholder("Plotter folgt"))

        self.project_box = QComboBox()
        self.project_box.addItems(list_projects())
        self.theme_box = QComboBox()
        for key, colors in THEMES.items():
            self.theme_box.addItem(colors["label"], key)

        self.mode_buttons: list[QToolButton] = []
        self.setCentralWidget(self._build_layout())
        self.statusBar().showMessage("Bereit")

        theme = self._settings.get("theme", DEFAULT_THEME)
        self.theme_box.setCurrentIndex(max(self.theme_box.findData(theme), 0))
        self.theme_box.currentIndexChanged.connect(self._on_theme_changed)
        self.project_box.currentTextChanged.connect(self._load_project)
        self._apply_theme()
        self._load_project(self.project_box.currentText())

    def _build_layout(self) -> QWidget:
        header = QFrame()
        header.setObjectName("header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 6, 12, 6)
        header_layout.addWidget(QLabel("Projekt"))
        header_layout.addWidget(self.project_box)
        header_layout.addStretch()
        header_layout.addWidget(QLabel("Farbstil"))
        header_layout.addWidget(self.theme_box)

        activity = QFrame()
        activity.setObjectName("activitybar")
        activity.setFixedWidth(48)
        activity_layout = QVBoxLayout(activity)
        activity_layout.setContentsMargins(0, 4, 0, 4)
        activity_layout.setSpacing(0)
        group = QButtonGroup(self)
        for index, (_key, name, _icon) in enumerate(MODES):
            button = QToolButton()
            button.setCheckable(True)
            button.setToolTip(name)
            button.setIconSize(QSize(24, 24))
            button.setFixedSize(48, 44)
            group.addButton(button, index)
            activity_layout.addWidget(button)
            self.mode_buttons.append(button)
        activity_layout.addStretch()
        group.idClicked.connect(self._set_mode)
        self.mode_buttons[0].setChecked(True)

        splitter = QSplitter()
        splitter.addWidget(self.sidebar)
        splitter.addWidget(self.content)
        splitter.setCollapsible(1, False)
        splitter.setSizes([260, 940])

        body = QHBoxLayout()
        body.setSpacing(0)
        body.addWidget(activity)
        body.addWidget(splitter)

        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(header)
        layout.addLayout(body)
        return root

    @staticmethod
    def _sidebar_page(title: str, widget: QWidget) -> QFrame:
        page = QFrame()
        page.setObjectName("sidebar")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        heading = QLabel(title.upper())
        heading.setObjectName("sidebartitle")
        layout.addWidget(heading)
        layout.addWidget(widget)
        return page

    def _set_mode(self, index: int):
        self.sidebar.setCurrentIndex(index)
        self.content.setCurrentIndex(index)

    def _on_theme_changed(self):
        self._settings["theme"] = self.theme_box.currentData()
        save_settings(self._settings)
        self._apply_theme()

    def _apply_theme(self):
        colors = THEMES[self.theme_box.currentData()]
        QApplication.instance().setStyleSheet(stylesheet(colors))
        for button, (_key, _name, icon_name) in zip(self.mode_buttons, MODES):
            button.setIcon(icon(icon_name, colors["muted"], colors["accent"]))
        self.explorer.set_color(colors["muted"])

    def _load_project(self, project_id: str):
        self._project = load_project(project_id)
        self.live_area.close_all()
        self.explorer.set_project(self._project, THEMES[self.theme_box.currentData()]["muted"])
        live_button = self.mode_buttons[0]
        live_button.setEnabled(self._project.live)
        live_button.setToolTip("Live" if self._project.live else "Live: für dieses Projekt nicht verfügbar")
        if not self._project.live and live_button.isChecked():
            self.mode_buttons[1].click()
        self.statusBar().showMessage(f"Projekt: {self._project.name}")


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

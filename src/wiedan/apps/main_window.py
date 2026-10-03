"""Hauptfenster: Kopfzeile, Activity Bar, Seitenleiste, Hauptbereich, Statusleiste."""
import sys

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QActionGroup
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QFrame, QHBoxLayout, QLabel, QMainWindow, QMenu,
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

        self.project_button = QToolButton()
        self.project_button.setObjectName("projectbutton")
        self.project_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.project_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.project_menu = QMenu(self.project_button)
        self.project_button.setMenu(self.project_menu)
        for project_id in list_projects():
            info = load_project(project_id)
            suffix = "Live" if info.live else "nicht live"
            action = self.project_menu.addAction(
                f"{info.name}   ·   {len(info.vehicles)} Fahrzeuge   ·   {suffix}"
            )
            action.triggered.connect(lambda _checked=False, pid=project_id: self.set_project(pid))

        self.settings_button = QToolButton()
        self.settings_button.setObjectName("settingsbutton")
        self.settings_button.setToolTip("Einstellungen")
        self.settings_button.setIconSize(QSize(24, 24))
        self.settings_button.setFixedSize(48, 44)
        self.settings_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.settings_menu = QMenu(self.settings_button)
        self.settings_button.setMenu(self.settings_menu)
        self.theme_actions = {}
        theme_group = QActionGroup(self)
        for key, colors in THEMES.items():
            action = self.settings_menu.addAction(colors["label"])
            action.setCheckable(True)
            theme_group.addAction(action)
            action.triggered.connect(lambda _checked=False, k=key: self.set_theme(k))
            self.theme_actions[key] = action

        self.mode_buttons: list[QToolButton] = []
        self.setCentralWidget(self._build_layout())
        self.statusBar().showMessage("Bereit")

        theme = self._settings.get("theme", DEFAULT_THEME)
        self._theme = theme if theme in THEMES else DEFAULT_THEME
        self.theme_actions[self._theme].setChecked(True)
        self._apply_theme()
        self.set_project(list_projects()[0])

    def _build_layout(self) -> QWidget:
        header = QFrame()
        header.setObjectName("header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 4, 12, 4)
        header_layout.addWidget(self.project_button)
        header_layout.addStretch()

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
        activity_layout.addWidget(self.settings_button)
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

    def set_theme(self, key: str):
        self._theme = key
        self.theme_actions[key].setChecked(True)
        self._settings["theme"] = key
        save_settings(self._settings)
        self._apply_theme()

    def _apply_theme(self):
        colors = THEMES[self._theme]
        QApplication.instance().setStyleSheet(stylesheet(colors))
        for button, (_key, _name, icon_name) in zip(self.mode_buttons, MODES):
            button.setIcon(icon(icon_name, colors["muted"], colors["accent"]))
        self.settings_button.setIcon(icon("settings", colors["muted"]))
        self.project_button.setIcon(icon("vehicle", colors["muted"]))
        self.explorer.set_color(colors["muted"])

    def set_project(self, project_id: str):
        self._project = load_project(project_id)
        self.project_button.setText(f" {self._project.name}  ▾")
        self.live_area.close_all()
        self.explorer.set_project(self._project, THEMES[self._theme]["muted"])
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

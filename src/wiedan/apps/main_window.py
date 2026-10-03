"""Hauptfenster: Kopfzeile, Activity Bar, Seitenleiste, Hauptbereich, Statusleiste."""
import sys
from datetime import datetime

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QActionGroup
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QFrame, QHBoxLayout, QLabel, QMainWindow, QMenu,
    QMessageBox, QSizePolicy, QSplitter, QStackedWidget, QToolButton, QVBoxLayout, QWidget,
)

from wiedan.core.model import list_projects, load_project, project_photo
from wiedan.core.settings import load_settings, save_settings
from wiedan.features.live import LiveArea, ProjectExplorer
from wiedan.ui.icons import icon
from wiedan.ui.theme import DEFAULT_THEME, THEMES, stylesheet
from wiedan.ui.welcome import WelcomePage

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


class _ElidedLabel(QLabel):
    def __init__(self):
        super().__init__()
        self._full_text = ""

    def set_full_text(self, text: str):
        self._full_text = text
        self.setToolTip(text)
        self._update_text()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_text()

    def _update_text(self):
        self.setText(
            self.fontMetrics().elidedText(
                self._full_text, Qt.TextElideMode.ElideRight, self.contentsRect().width()
            )
        )


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
        self.welcome = WelcomePage()
        self.live_stack = QStackedWidget()
        self.live_stack.addWidget(self.welcome)
        self.live_stack.addWidget(self.live_area)
        self.live_area.currentChanged.connect(self._update_live_stack)
        self.live_actions_button = QToolButton()
        self.live_actions_button.setObjectName("sidebaractions")
        self.live_actions_button.setText("Aktionen")
        self.live_actions_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.live_actions_menu = QMenu(self.live_actions_button)
        self.live_actions_button.setMenu(self.live_actions_menu)
        parameter_action = self.live_actions_menu.addAction(
            "Parameter auf allen Umrichtern ändern"
        )
        parameter_action.setEnabled(False)
        parameter_action.setToolTip("Noch nicht verfügbar")
        report_action = self.live_actions_menu.addAction("Projektbericht erstellen")
        report_action.setEnabled(False)
        report_action.setToolTip("Noch nicht verfügbar")
        self.live_actions_menu.addSeparator()
        self.reachability_action = self.live_actions_menu.addAction(
            "Erreichbarkeit prüfen", self.explorer.check_reachability
        )
        self.explorer.reachability_check_started.connect(self._reachability_check_started)
        self.explorer.reachability_check_finished.connect(self._reachability_check_finished)
        self.sidebar.addWidget(
            self._sidebar_page("Projekt-Explorer", self.explorer, self.live_actions_button)
        )
        self.sidebar.addWidget(self._sidebar_page("Tool-Browser", _placeholder("folgt")))
        self.sidebar.addWidget(self._sidebar_page("Kanäle", _placeholder("folgt")))
        self.content.addWidget(self.live_stack)
        self.content.addWidget(_placeholder("Inbetriebnahme folgt"))
        self.content.addWidget(_placeholder("Plotter folgt"))

        self.project_button = QToolButton()
        self.project_button.setObjectName("projectbutton")
        self.project_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.project_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.project_button.setIconSize(QSize(16, 16))
        self.project_button.setToolTip("Projekt wechseln")
        self.project_menu = QMenu(self.project_button)
        self.project_button.setMenu(self.project_menu)
        project_ids = list_projects()
        for project_id in project_ids:
            action = self.project_menu.addAction(project_id)
            action.triggered.connect(lambda _checked=False, pid=project_id: self._switch_project(pid))

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
        self.info_label = _ElidedLabel()
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.info_label.setContentsMargins(0, 0, 12, 0)
        self.info_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.statusBar().setSizeGripEnabled(False)
        self.statusBar().addWidget(self.project_button)
        self.statusBar().addWidget(self.info_label, 1)
        self.welcome.switch_requested.connect(self.project_button.showMenu)
        self._build_menus()
        self.setCentralWidget(self._build_layout())

        theme = self._settings.get("theme", DEFAULT_THEME)
        self._theme = theme if theme in THEMES else DEFAULT_THEME
        self.theme_actions[self._theme].setChecked(True)
        self._apply_theme()
        self.set_project(project_ids[0])
        self.log(f"WieDAN im Projekt {self._project.name} gestartet")

    def _build_menus(self):
        bar = self.menuBar()
        file_menu = bar.addMenu("Datei")
        file_menu.addAction("Beenden", self.close)
        project_menu = bar.addMenu("Projekt")
        project_menu.addActions(self.project_menu.actions())
        help_menu = bar.addMenu("Hilfe")
        help_menu.addAction(
            "Über WieDAN", lambda: QMessageBox.about(self, "WieDAN", "WieDAN – Werkzeugkasten")
        )

    def log(self, text: str):
        self.info_label.set_full_text(f"{datetime.now():%d.%m.%Y %H:%M:%S} - {text}")

    def _build_layout(self) -> QWidget:
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
        splitter.setHandleWidth(6)

        body = QHBoxLayout()
        body.setContentsMargins(6, 6, 6, 6)
        body.setSpacing(6)
        body.addWidget(activity)
        body.addWidget(splitter)

        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addLayout(body)
        return root

    @staticmethod
    def _sidebar_page(title: str, widget: QWidget, actions: QWidget | None = None) -> QFrame:
        page = QFrame()
        page.setObjectName("sidebar")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        heading = QLabel(title.upper())
        heading.setObjectName("sidebartitle")
        if actions is None:
            layout.addWidget(heading)
        else:
            header = QWidget()
            header_layout = QHBoxLayout(header)
            header_layout.setContentsMargins(0, 0, 8, 0)
            header_layout.setSpacing(4)
            header_layout.addWidget(heading, 1)
            header_layout.addWidget(actions)
            layout.addWidget(header)
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
        self.project_button.setIcon(icon("project", colors["status_text"]))
        self.explorer.set_status_colors(
            colors["muted"], colors["reachable"], colors["unreachable"]
        )

    def _update_live_stack(self):
        self.live_stack.setCurrentWidget(self.live_area if self.live_area.count() else self.welcome)

    def _switch_project(self, project_id: str):
        self.set_project(project_id)
        self.log(f"Projekt {self._project.name} geöffnet")

    def set_project(self, project_id: str):
        self._project = load_project(project_id)
        self.project_button.setText(f" {project_id}  ▴")
        self.welcome.set_project(self._project.full_name, project_photo(project_id))
        self.live_area.close_all()
        self._update_live_stack()
        self.explorer.set_project(self._project)
        live_button = self.mode_buttons[0]
        live_button.setEnabled(self._project.live)
        live_button.setToolTip("Live" if self._project.live else "Live: für dieses Projekt nicht verfügbar")
        self._update_reachability_action()
        if not self._project.live and live_button.isChecked():
            self.mode_buttons[1].click()

    def _reachability_check_started(self):
        self.reachability_action.setText("Prüfung läuft …")
        self.reachability_action.setEnabled(False)

    def _reachability_check_finished(self, results, error):
        self.reachability_action.setText("Erreichbarkeit prüfen")
        self._update_reachability_action()
        if error:
            QMessageBox.warning(self, "Erreichbarkeitsprüfung fehlgeschlagen", error)
        elif results is not None:
            reachable = sum(results.values())
            self.log(
                f"Erreichbarkeit geprüft: {reachable}/{len(results)} Geräte erreichbar"
            )

    def _update_reachability_action(self):
        has_pingable_devices = self._project and any(
            device.pingable for device in self._project.devices.values()
        )
        self.reachability_action.setEnabled(
            bool(self._project and self._project.live and has_pingable_devices)
            and not self.explorer.reachability_check_running
        )


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

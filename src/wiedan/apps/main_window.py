"""Hauptfenster: Kopfzeile, Activity Bar, Seitenleiste, Hauptbereich, Statusleiste."""
import os
import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from wiedan.core.model import list_projects, load_project, project_photo
from wiedan.core.project_database import (
    ProjectDatabaseError,
    database_path,
    inspect_database,
    select_database,
)
from wiedan.core.project_database import (
    list_projects as database_projects,
)
from wiedan.core.project_database import (
    load_project as database_project,
)
from wiedan.core.settings import load_settings, save_settings
from wiedan.features.commissioning import CommissioningArea, ToolBrowser
from wiedan.features.live import LiveArea, ProjectExplorer
from wiedan.features.master_data_editor import MasterDataEditor
from wiedan.features.device_catalog import DeviceCatalogEditor
from wiedan.features.project_editor import ProjectEditor, ProjectEditorDialog
from wiedan.ui.icons import icon
from wiedan.ui.settings_dialog import SettingsDialog
from wiedan.ui.spinner import Spinner
from wiedan.ui.theme import DEFAULT_THEME, THEMES, palette, stylesheet
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
        self._database_info = inspect_database()

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
            "Alle Geräte anpingen", lambda: self.explorer.check_reachability()
        )
        self.explorer.reachability_check_started.connect(self._reachability_check_started)
        self.explorer.reachability_check_finished.connect(self._reachability_check_finished)
        self.explorer.vehicle_activity_changed.connect(self._update_reachability_action)
        self.explorer_spinner = Spinner()
        self.collapse_button = QToolButton()
        self.collapse_button.setObjectName("sidebaractions")
        self.collapse_button.setToolTip("Alles einklappen")
        self.collapse_button.clicked.connect(self.explorer.collapseAll)
        self.sidebar.addWidget(
            self._sidebar_page(
                "Projekt-Explorer", self.explorer,
                title_extras=(self.explorer_spinner,),
                actions=(self.collapse_button, self.live_actions_button),
            )
        )
        self.tool_browser = ToolBrowser()
        self.commissioning_area = CommissioningArea()
        self.commissioning_area.message.connect(self.log)
        self.tool_browser.tool_chosen.connect(self.commissioning_area.open_tool)
        self.sidebar.addWidget(self._sidebar_page("Tool-Browser", self.tool_browser))
        self.sidebar.addWidget(self._sidebar_page("Kanäle", _placeholder("folgt")))
        self.content.addWidget(self.live_stack)
        self.content.addWidget(self.commissioning_area)
        self.content.addWidget(_placeholder("Plotter folgt"))
        self.project_editor = ProjectEditor()
        self.project_editor.before_save = self.commissioning_area.can_leave_project
        self.project_editor.saved.connect(self._reload_database_views)
        self.commissioning_area.before_database_edit = self.project_editor.can_leave
        self.commissioning_area.database_changed.connect(lambda: self._reload_database_views())
        self.project_editor_dialog = ProjectEditorDialog(self.project_editor, self)
        self.project_editor_dialog.project_requested.connect(self._select_editor_project)

        self.project_button = QToolButton()
        self.project_button.setObjectName("projectbutton")
        self.project_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.project_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.project_button.setIconSize(QSize(16, 16))
        self.project_button.setToolTip("Projekt wechseln")
        self.project_menu = QMenu(self.project_button)
        self.project_button.setMenu(self.project_menu)
        project_ids = self._refresh_project_menu()

        self.theme_button = QToolButton()
        self.theme_button.setObjectName("themebutton")
        self.theme_button.setIconSize(QSize(24, 24))
        self.theme_button.setFixedSize(48, 44)
        self.theme_button.clicked.connect(self._toggle_theme)

        self.settings_button = QToolButton()
        self.settings_button.setObjectName("settingsbutton")
        self.settings_button.setToolTip("Einstellungen")
        self.settings_button.setIconSize(QSize(24, 24))
        self.settings_button.setFixedSize(48, 44)
        self.settings_button.setAccessibleName("Einstellungen")
        self.settings_button.clicked.connect(self._open_settings)

        self.mode_buttons: list[QToolButton] = []
        self.info_label = _ElidedLabel()
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.info_label.setContentsMargins(0, 0, 12, 0)
        self.info_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        
        self.ewon_link = QToolButton()
        self.ewon_link.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.ewon_link.setText("Ewon ECatcher")
        self.ewon_link.setToolTip("Ewon ECatcher starten")
        self.ewon_link.setIconSize(QSize(16, 16))
        self.ewon_link.clicked.connect(
            lambda: os.startfile(os.path.expandvars(r"%ProgramFiles(X86)%\eCatcher-Talk2M\ECatcher.exe"))
        )
        
        self.statusBar().setSizeGripEnabled(False)
        self.statusBar().addWidget(self.project_button)
        self.statusBar().addWidget(self.ewon_link)
        self.statusBar().addWidget(self.info_label, 1)
        self.welcome.switch_requested.connect(self.project_button.showMenu)
        self._build_menus()
        self.setCentralWidget(self._build_layout())

        theme = self._settings.get("theme", DEFAULT_THEME)
        self._theme = theme if theme in THEMES else DEFAULT_THEME
        self._apply_theme()
        for project_id in project_ids:
            if self.set_project(project_id):
                break
        if self._project is not None:
            self.log(f"WieDAN im Projekt {self._project.name} gestartet")
        else:
            self.tool_browser.set_project_available(False)
            self.log("Noch kein Projekt vorhanden. Projekte lassen sich unter Einstellungen → Projekteditor anlegen.")

    def _build_menus(self):
        bar = self.menuBar()
        file_menu = bar.addMenu("Datei")
        file_menu.addAction("Einstellungen …", self._open_settings)
        file_menu.addSeparator()
        file_menu.addAction("Beenden", self.close)
        self.projects_menu = bar.addMenu("Projekt")
        self.projects_menu.addActions(self.project_menu.actions())
        help_menu = bar.addMenu("Hilfe")
        help_menu.addAction(
            "Über WieDAN", lambda: QMessageBox.about(self, "WieDAN", "WieDAN - Werkzeugkasten")
        )

    def log(self, text: str):
        self.info_label.set_full_text(f"{datetime.now().astimezone():%d.%m.%Y %H:%M:%S} - {text}")

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
        activity_layout.addWidget(self.theme_button)
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
    def _sidebar_page(
        title: str, widget: QWidget, title_extras: tuple[QWidget, ...] = (),
        actions: tuple[QWidget, ...] = (),
    ) -> QFrame:
        page = QFrame()
        page.setObjectName("sidebar")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        heading = QLabel(title.upper())
        heading.setObjectName("sidebartitle")
        if not title_extras and not actions:
            layout.addWidget(heading)
        else:
            header = QWidget()
            header_layout = QHBoxLayout(header)
            header_layout.setContentsMargins(0, 0, 8, 0)
            header_layout.setSpacing(4)
            header_layout.addWidget(heading)
            for extra in title_extras:
                header_layout.addWidget(extra)
            header_layout.addStretch(1)
            for action in actions:
                header_layout.addWidget(action)
            layout.addWidget(header)
        layout.addWidget(widget)
        return page

    def _set_mode(self, index: int):
        self.sidebar.setCurrentIndex(index)
        self.content.setCurrentIndex(index)

    def _toggle_theme(self):
        self.set_theme("light" if self._theme == "dark" else "dark")

    def set_theme(self, key: str):
        self._theme = key
        self._settings["theme"] = key
        save_settings(self._settings)
        self._apply_theme()

    def _apply_theme(self):
        colors = THEMES[self._theme]
        app = QApplication.instance()
        app.setPalette(palette(colors))
        app.setStyleSheet(stylesheet(colors))
        for button, (_key, _name, icon_name) in zip(self.mode_buttons, MODES):
            button.setIcon(icon(icon_name, colors["muted"], colors["accent"]))
        self.settings_button.setIcon(icon("settings", colors["muted"]))
        dark = self._theme == "dark"
        self.theme_button.setIcon(icon("sun" if dark else "moon", colors["muted"]))
        theme_action = "Zum hellen Design wechseln" if dark else "Zum dunklen Design wechseln"
        self.theme_button.setToolTip(theme_action)
        self.theme_button.setAccessibleName(theme_action)
        self.project_button.setIcon(icon("project", colors["status_text"]))
        self.ewon_link.setIcon(icon("ewon", colors["status_text"]))
        self.collapse_button.setIcon(icon("collapse", colors["muted"]))
        self.tool_browser.set_icon_color(colors["accent"])
        self.explorer_spinner.set_color(colors["muted"])
        self.explorer.set_status_colors(
            colors["muted"], colors["reachable"], colors["unreachable"]
        )
        self.project_editor.set_icon_color(colors["muted"])

    def _update_live_stack(self):
        self.live_stack.setCurrentWidget(self.live_area if self.live_area.count() else self.welcome)

    def _switch_project(self, project_id: str):
        if self.set_project(project_id):
            self.log(f"Projekt {self._project.name} geöffnet")

    def _refresh_project_menu(self):
        project_ids = list_projects()
        if hasattr(self, "projects_menu"):
            self.projects_menu.clear()
        self.project_menu.clear()
        for project_id in project_ids:
            action = self.project_menu.addAction(project_id)
            action.triggered.connect(lambda _checked=False, pid=project_id: self._switch_project(pid))
        if hasattr(self, "projects_menu"):
            self.projects_menu.addActions(self.project_menu.actions())
        return project_ids

    def _open_settings(self):
        dialog = SettingsDialog(database_path(), self._database_info, self)
        dialog.master_data_requested.connect(lambda: self._open_master_data_editor(dialog))
        dialog.catalog_requested.connect(lambda: self._open_device_catalog(dialog))
        open_project_editor = []

        def open_editor():
            open_project_editor.append(True)
            dialog.accept()

        dialog.project_editor_requested.connect(open_editor)

        def apply():
            path = dialog.path_edit.text().strip()
            if not path:
                QMessageBox.warning(dialog, "Stammdatenbank", "Bitte einen Datenbankpfad angeben.")
                dialog.path_edit.setFocus()
                return
            if self._connect_database(Path(path), parent=dialog):
                dialog.accept()

        dialog.buttons.accepted.connect(apply)
        dialog.exec()
        dialog.deleteLater()
        if open_project_editor:
            self.project_editor_dialog.select_project(self._project.uid if self._project else None)
            self.project_editor_dialog.exec()

    def _open_master_data_editor(self, parent):
        if not self._can_leave_project():
            return
        try:
            editor = MasterDataEditor(database_path(), self._project.uid if self._project else None, parent=parent)
            editor.saved.connect(lambda: self._reload_database_views())
            editor.exec()
            editor.deleteLater()
        except (OSError, ValueError) as exc:
            QMessageBox.warning(parent, "Stammdateneditor", str(exc))

    def _select_editor_project(self, uid):
        if not self.set_project(uid):
            self.project_editor_dialog.select_project(self._project.uid if self._project else None)

    def _can_leave_project(self):
        return self.project_editor.can_leave() and self.commissioning_area.can_leave_project()

    def _reload_database_views(self, project_uid=None):
        self._database_info = inspect_database()
        identifiers = self._refresh_project_menu()
        uid = project_uid or (self._project.uid if self._project else None)
        if uid or identifiers:
            self.set_project(uid or identifiers[0], check_changes=False)
        self.log("Engineering-Daten gespeichert")

    def _open_device_catalog(self, parent=None):
        if not self._can_leave_project():
            return
        try:
            editor = DeviceCatalogEditor(database_path(), parent or self)
            editor.saved.connect(lambda: self._reload_database_views())
            editor.exec()
            editor.deleteLater()
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Gerätekatalog", str(exc))

    def _connect_database(self, candidate: Path, *, parent=None):
        try:
            candidate = candidate.expanduser().resolve()
            inspect_database(candidate)
            if candidate == database_path().resolve():
                return True
            if not self._can_leave_project():
                return False
            current = self._project.uid if self._project else None
            try:
                selected = database_project(current, path=candidate) if current else None
            except ProjectDatabaseError:
                selected = None
            if selected is None:
                projects = database_projects(path=candidate)
                selected = database_project(projects[0], path=candidate) if projects else None
            self._database_info = select_database(candidate)
            self._settings = load_settings()
            self._refresh_project_menu()
            if selected is None:
                self._project = None
                self.project_editor.set_project(None)
                self.project_editor_dialog.select_project(None)
                self.explorer.set_project(None)
                self.live_area.close_all()
                self.project_button.setText("Projekt auswählen")
                self.tool_browser.set_project_available(False)
                self.commissioning_area.set_project(None)
                self.mode_buttons[0].setEnabled(False)
                self._update_reachability_action()
                self.mode_buttons[1].click()
            elif not self.set_project(selected.uid, check_changes=False):
                return False
            self.log(f"Stammdatenbank verbunden · Datenstand {self._database_info['data_version']}")
            return True
        except (OSError, ValueError) as exc:
            QMessageBox.warning(parent or self, "Stammdatenbank", str(exc))
            return False

    def set_project(self, project_id: str, *, check_changes=True):
        if check_changes and not self._can_leave_project():
            return False
        try:
            project = load_project(project_id)
            photo = project_photo(project_id)
        except (OSError, ProjectDatabaseError) as exc:
            QMessageBox.warning(self, "Projekt kann nicht geöffnet werden", str(exc))
            return False
        self._project = project
        self.tool_browser.set_project_available(True)
        self.project_button.setText(f" {project.display_name}  ▴")
        self.project_button.setToolTip(f"{project.database_path}\nFormat {project.schema_version} · "
                                      f"Datenstand {project.data_version} · Lokale Arbeitsdatenbank")
        self.welcome.set_project(self._project.full_name, photo)
        self.live_area.close_all()
        self._update_live_stack()
        self.explorer.set_project(self._project)
        self.commissioning_area.set_project(self._project)
        self.project_editor.set_project(self._project)
        self.project_editor_dialog.select_project(self._project.uid)
        live_button = self.mode_buttons[0]
        live_button.setEnabled(self._project.live)
        live_button.setToolTip("Live" if self._project.live else "Live: für dieses Projekt nicht verfügbar")
        self._update_reachability_action()
        if not self._project.live and live_button.isChecked():
            self.mode_buttons[1].click()
        return True

    def closeEvent(self, event):
        if self._can_leave_project():
            super().closeEvent(event)
        else:
            event.ignore()

    def _reachability_check_started(self):
        self.reachability_action.setText("Prüfung läuft …")
        self.reachability_action.setEnabled(False)
        self.explorer_spinner.set_running(True)

    def _reachability_check_finished(self, results, error):
        self.explorer_spinner.set_running(False)
        self.reachability_action.setText("Alle Geräte anpingen")
        self._update_reachability_action()
        if error:
            QMessageBox.warning(self, "Ping fehlgeschlagen", error)
        elif results is not None:
            reachable = sum(results.values())
            self.log(
                f"Erreichbarkeit geprüft: {reachable}/{len(results)} Geräte erreichbar"
            )

    def _update_reachability_action(self):
        has_pingable_devices = any(
            device.pingable and device.connection.get("ip") for device in self.explorer.active_devices
        )
        self.reachability_action.setEnabled(
            bool(self._project and self._project.live and has_pingable_devices)
            and not self.explorer.reachability_check_running
        )


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    # Eine fehlende oder inkompatible Auswahl muss ohne Bearbeiten der settings.json behebbar sein.
    try:
        inspect_database()
    except (OSError, ValueError) as exc:
        error = str(exc)
        while True:
            QMessageBox.warning(None, "Stammdatenbank", f"{error}\n\nBitte eine kompatible lokale Stammdatenbank auswählen.")
            filename, _ = QFileDialog.getOpenFileName(None, "Lokale Stammdatenbank auswählen", "",
                                                      "WieDAN-Stammdatenbank (*.sqlite *.db)")
            if not filename:
                sys.exit(1)
            try:
                select_database(Path(filename))
                break
            except (OSError, ValueError) as exc:
                error = str(exc)
    try:
        window = MainWindow()
    except (OSError, ValueError) as exc:
        QMessageBox.critical(None, "Stammdatenbank konnte nicht geöffnet werden", str(exc))
        sys.exit(1)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

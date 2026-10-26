"""Farbstile (hell, dunkel, pastell) und das daraus erzeugte Stylesheet."""

from pathlib import Path

from PySide6.QtGui import QColor, QPalette

# Pastell färbt jeden Bereich anders: Hilfsmittel zum Debuggen des Layouts.
THEMES = {
    "light": {
        "label": "Hell",
        "window": "#e7eee9",
        "header": "#f2f6f3", "surface": "#e7eee9", "activity": "#dfe8e2", "sidebar": "#f2f6f3",
        "main": "#ffffff", "status": "#004F38", "status_text": "#ffffff",
        "text": "#202e26", "muted": "#59665f", "accent": "#50AF47",
        "reachable": "#004F38", "unreachable": "#b23a3a",
        "selection": "#d8ecda", "hover": "#e8f2e9", "border": "#aab9b0",
        "tab": "#edf3ef", "input": "#ffffff",
        "primary": "#004F38", "primary_text": "#ffffff",
    },
    "dark": {
        "label": "Dunkel",
        "window": "#121b16",
        "header": "#323233", "surface": "#181818", "activity": "#333333", "sidebar": "#252526",
        "main": "#1e1e1e",         "status": "#004F38", "status_text": "#ffffff",
                "text": "#dddddd", "muted": "#a0a0a0", "accent": "#50AF47",
        "reachable": "#50AF47", "unreachable": "#c98480",
                "selection": "#1f4a33", "hover": "#2a2d2e", "border": "#3c3c3c",
        "tab": "#2d2d2d", "input": "#252526",
        "primary": "#50AF47", "primary_text": "#121b16",
    },
}

DEFAULT_THEME = "light"


def palette(c: dict) -> QPalette:
    """Färbt auch native Qt-Bedienelemente unabhängig vom Windows-Farbstil."""
    result = QPalette()
    for role, key in (
        (QPalette.ColorRole.Window, "main"),
        (QPalette.ColorRole.WindowText, "text"),
        (QPalette.ColorRole.Base, "input"),
        (QPalette.ColorRole.AlternateBase, "sidebar"),
        (QPalette.ColorRole.Text, "text"),
        (QPalette.ColorRole.PlaceholderText, "muted"),
        (QPalette.ColorRole.Button, "tab"),
        (QPalette.ColorRole.ButtonText, "text"),
        (QPalette.ColorRole.BrightText, "primary_text"),
        (QPalette.ColorRole.Highlight, "selection"),
        (QPalette.ColorRole.HighlightedText, "text"),
        (QPalette.ColorRole.Link, "primary"),
        (QPalette.ColorRole.LinkVisited, "muted"),
        (QPalette.ColorRole.ToolTipBase, "main"),
        (QPalette.ColorRole.ToolTipText, "text"),
        (QPalette.ColorRole.Light, "main"),
        (QPalette.ColorRole.Midlight, "hover"),
        (QPalette.ColorRole.Mid, "border"),
        (QPalette.ColorRole.Dark, "border"),
        (QPalette.ColorRole.Shadow, "muted"),
    ):
        result.setColor(role, QColor(c[key]))
    for role in (
        QPalette.ColorRole.WindowText, QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText, QPalette.ColorRole.PlaceholderText,
    ):
        result.setColor(QPalette.ColorGroup.Disabled, role, QColor(c["muted"]))
    result.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Base, QColor(c["tab"]))
    return result


def stylesheet(c: dict) -> str:
    arrow_style = "light" if QColor(c["input"]).lightness() > 127 else "dark"
    svg_directory = Path(__file__).resolve().parent / "svg"
    arrow_up = (svg_directory / f"spin-up-{arrow_style}.svg").as_posix()
    arrow_down = (svg_directory / f"spin-down-{arrow_style}.svg").as_posix()
    return f"""
    QWidget {{ color: {c['text']}; font-size: 13px; }}
    QWidget:disabled {{ color: {c['muted']}; }}
    QMainWindow {{ background: {c['window']}; }}
    QLineEdit, QAbstractSpinBox, QComboBox, QTextEdit, QPlainTextEdit {{
        background: {c['input']}; color: {c['text']};
        border: 2px solid {c['border']}; border-radius: 4px; padding: 4px 6px;
        selection-background-color: {c['selection']}; selection-color: {c['text']};
    }}
    QLineEdit:hover, QAbstractSpinBox:hover, QComboBox:hover,
    QTextEdit:hover, QPlainTextEdit:hover {{ border-color: {c['muted']}; }}
    QLineEdit:focus, QAbstractSpinBox:focus, QComboBox:focus,
    QTextEdit:focus, QPlainTextEdit:focus {{ border-color: {c['accent']}; }}
    QLineEdit:disabled, QAbstractSpinBox:disabled, QComboBox:disabled,
    QTextEdit:disabled, QPlainTextEdit:disabled {{
        background: {c['tab']}; color: {c['muted']}; border-color: {c['border']};
    }}
    QAbstractSpinBox QLineEdit, QComboBox QLineEdit {{
        background: transparent; border: none; padding: 0px;
    }}
    QAbstractSpinBox {{ padding-right: 26px; }}
    QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {{
        subcontrol-origin: border; width: 22px;
        background: {c['tab']}; border: none;
        border-left: 1px solid {c['border']};
        margin-right: 2px;
    }}
    QAbstractSpinBox::up-button {{
        subcontrol-position: top right; margin-top: 2px;
        border-top-right-radius: 2px;
    }}
    QAbstractSpinBox::down-button {{
        subcontrol-position: bottom right; margin-bottom: 2px;
        border-bottom-right-radius: 2px;
    }}
    QAbstractSpinBox::up-button:hover, QAbstractSpinBox::down-button:hover {{
        background: {c['hover']};
    }}
    QAbstractSpinBox::up-button:pressed, QAbstractSpinBox::down-button:pressed {{
        background: {c['selection']};
    }}
    QAbstractSpinBox::up-button:disabled, QAbstractSpinBox::down-button:disabled,
    QAbstractSpinBox::up-button:off, QAbstractSpinBox::down-button:off {{
        background: {c['input']};
    }}
    QAbstractSpinBox::up-arrow {{ image: url("{arrow_up}"); width: 10px; height: 6px; }}
    QAbstractSpinBox::down-arrow {{ image: url("{arrow_down}"); width: 10px; height: 6px; }}
    QComboBox QAbstractItemView {{
        background: {c['input']}; color: {c['text']}; border: 1px solid {c['border']};
        selection-background-color: {c['selection']}; selection-color: {c['text']};
    }}
    QPushButton {{
        background: {c['tab']}; color: {c['text']};
        border: 2px solid {c['border']}; border-radius: 4px; padding: 4px 12px;
    }}
    QPushButton:hover {{ background: {c['hover']}; }}
    QPushButton:pressed {{ background: {c['selection']}; }}
    QPushButton:focus {{ border-color: {c['accent']}; }}
    QPushButton:disabled {{ background: {c['tab']}; color: {c['muted']}; }}
    QGroupBox {{
        border: 1px solid {c['border']}; border-radius: 6px;
        margin-top: 12px; padding: 12px 8px 8px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin; subcontrol-position: top left;
        left: 10px; padding: 0px 4px; color: {c['muted']};
    }}
    #activitybar {{ background: {c['activity']}; border-radius: 8px; }}
    #activitybar QToolButton {{
        background: transparent; border: none; border-left: 2px solid transparent;
        padding: 10px 0px;
    }}
    #activitybar QToolButton:hover {{ background: {c['hover']}; }}
    #activitybar QToolButton:checked {{ border-left: 2px solid {c['accent']}; }}
    #sidebar {{ background: {c['sidebar']}; border-radius: 8px; }}
    #sidebartitle {{ color: {c['muted']}; font-size: 11px; padding: 8px 12px; background: transparent; }}
    #sidebaractions {{
        background: transparent; border: none; border-radius: 3px;
        color: {c['muted']}; font-size: 11px; padding: 4px 6px;
    }}
    #sidebaractions:hover {{ background: {c['hover']}; }}
    #toolbrowser, #toolbrowsercontent {{ background: transparent; }}
    #toolcategory {{
        background: transparent;
        color: {c['muted']}; font-size: 11px; font-weight: 600;
        border: none; border-radius: 3px; padding: 4px 6px; text-align: left;
    }}
    #toolbrowser #toolcategory:hover {{ background: {c['hover']}; }}
    #toolbrowser #toolcategory:focus {{ color: {c['text']}; background: {c['hover']}; }}
    #tooltile {{
        background: {c['tab']}; color: {c['text']};
        border: 2px solid {c['border']}; border-radius: 12px; padding: 0px;
    }}
    #tooltile:hover {{ background: {c['hover']}; border-color: {c['accent']}; }}
    #tooltile:checked, #tooltile:pressed {{
        background: {c['selection']}; border-color: {c['accent']};
    }}
    #tooltile:focus {{ border-color: {c['accent']}; }}
    #tooltileicon {{
        background: {c['main']}; border: 1px solid {c['border']}; border-radius: 14px;
    }}
    #tooltiletitle {{
        color: {c['text']}; font-size: 15px; font-weight: bold;
        background: transparent; border: none;
    }}
    #tooltiledesc {{
        color: {c['muted']}; font-size: 12px; background: transparent; border: none;
    }}
    #tooltile:disabled #tooltiletitle, #tooltile:disabled #tooltiledesc {{ color: {c['muted']}; }}
    #content {{ background: {c['main']}; border-radius: 8px; }}
    #scalanceTitle {{ font-size: 17px; font-weight: 600; }}
    #scalanceTree {{ background: {c['sidebar']}; border-radius: 8px; padding: 4px; }}
    #scalanceTree QHeaderView::section {{
        background: {c['sidebar']}; color: {c['muted']}; border: none; padding: 6px;
    }}
    #scalanceStatus {{ background: {c['sidebar']}; border-radius: 4px; padding: 8px; }}
    #scalanceStatus[error="true"] {{ color: {c['unreachable']}; border: 1px solid {c['unreachable']}; }}
    #scalanceTable {{ background: {c['main']}; border: 1px solid {c['border']}; }}
    #scalanceTable::item {{ padding: 4px; }}
    #scalanceTable::item:selected {{ background: {c['selection']}; color: {c['text']}; }}
    #scalanceTable QHeaderView::section {{
        background: {c['sidebar']}; color: {c['muted']}; border: none; padding: 5px;
    }}
    #modbusTable {{ background: {c['main']}; border: 1px solid {c['border']}; border-radius: 6px; }}
    #modbusTable::item {{ padding: 6px 10px; border-bottom: 1px solid {c['border']}; }}
    #modbusTable::item:selected {{ background: {c['selection']}; color: {c['text']}; }}
    #modbusTable QHeaderView::section {{
        background: {c['header']}; color: {c['muted']}; border: none; padding: 8px 10px;
    }}
    #modbusConnectButton {{
        background: {c['tab']}; border: 2px solid {c['border']};
        border-radius: 3px; padding: 4px 12px;
    }}
    #modbusConnectButton:hover {{ background: {c['hover']}; }}
    #modbusConnectButton:pressed {{ background: {c['selection']}; }}
    #modbusConnectButton:disabled {{ color: {c['muted']}; }}
    #modbusConnectButton:focus {{ border-color: {c['accent']}; }}
    #modbusConnectButton[invalid="true"] {{ border-color: {c['unreachable']}; }}
    QLineEdit[invalid="true"] {{
        border-color: {c['unreachable']};
    }}
    #modbusWriteButton {{
        background: {c['primary']}; color: {c['primary_text']};
        border: 2px solid transparent; border-radius: 4px;
        padding: 5px 12px; font-weight: bold;
    }}
    #modbusWriteButton:hover {{ border-color: {c['accent']}; }}
    #modbusWriteButton:focus {{ border-color: {c['primary_text']}; }}
    #modbusWriteButton:pressed {{ border-color: {c['text']}; }}
    #modbusWriteButton:disabled {{ background: {c['tab']}; color: {c['muted']}; }}
    QTreeWidget {{ background: transparent; border: none; outline: 0; }}
    QTreeWidget::item {{ padding: 3px 2px; }}
    QTreeWidget::item:hover {{ background: {c['hover']}; }}
    QTreeWidget::item:selected {{ background: {c['selection']}; color: {c['text']}; }}
    QTabWidget::pane {{ border: none; background: transparent; }}
    QTabBar::tab:first {{ border-top-left-radius: 8px; }}
    QTabBar::tab {{
        background: {c['tab']}; color: {c['muted']}; padding: 7px 14px;
        border: none; border-right: 1px solid {c['border']};
    }}
    QTabBar::tab:selected {{
        background: {c['main']}; color: {c['text']}; border-top: 1px solid {c['accent']};
    }}
    QStatusBar {{ background: {c['status']}; color: {c['status_text']}; }}
    QStatusBar QLabel {{ color: {c['status_text']}; }}
    QStatusBar QToolButton {{
        background: transparent; border: none; border-radius: 3px;
        padding: 2px 10px; font-weight: 600; color: {c['status_text']};
    }}
    QStatusBar QToolButton:hover {{ background: rgba(255, 255, 255, 40); }}
    #settingsbutton:hover {{ background: {c['hover']}; }}
    #projectbutton::menu-indicator, #settingsbutton::menu-indicator {{ image: none; width: 0; }}
    #settingsbutton {{ background: transparent; border: none; }}
    #welcome {{ background: {c['main']}; border-radius: 8px; }}
    #welcometitle {{ font-size: 28px; font-weight: 600; background: transparent; }}
    #welcomehint {{ color: {c['muted']}; background: transparent; }}
    #link {{
        background: transparent; border: 2px solid transparent;
        color: {c['primary']}; padding: 2px 6px;
    }}
    #link:hover {{ background: {c['hover']}; border-radius: 3px; }}
    #link:focus {{ border-color: {c['accent']}; border-radius: 3px; }}
    QMenuBar {{ background: {c['header']}; padding: 2px 6px; }}
    QMenuBar::item {{ padding: 4px 10px; border-radius: 3px; background: transparent; }}
    QMenuBar::item:selected {{ background: {c['hover']}; }}
    QMenu {{
        background: {c['main']}; border: 1px solid {c['border']}; padding: 4px;
    }}
    QMenu::item {{ padding: 6px 24px 6px 12px; border-radius: 3px; }}
    QMenu::item:disabled {{ color: {c['muted']}; }}
    QMenu::item:disabled:selected {{ color: {c['muted']}; background: transparent; }}
    QMenu::item:selected {{ background: {c['selection']}; color: {c['text']}; }}
    QMenu::indicator:checked {{ background: {c['accent']}; border-radius: 3px; }}
    QSplitter::handle {{ background: transparent; }}
    QToolTip {{ background: {c['main']}; color: {c['text']}; border: 1px solid {c['border']}; }}
    """

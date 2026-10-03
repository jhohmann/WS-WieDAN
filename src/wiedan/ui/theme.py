"""Farbstile (hell, dunkel, pastell) und das daraus erzeugte Stylesheet."""

# Pastell färbt jeden Bereich anders: Hilfsmittel zum Debuggen des Layouts.
THEMES = {
    "hell": {
        "label": "Hell",
        "header": "#f3f3f3", "activity": "#ececec", "sidebar": "#f7f7f7",
        "main": "#ffffff", "status": "#0078d4", "status_text": "#ffffff",
        "text": "#1f1f1f", "muted": "#6e6e6e", "accent": "#0078d4",
        "selection": "#dbe9f7", "hover": "#e0e0e0", "border": "#d4d4d4",
        "tab": "#ececec",
    },
    "dunkel": {
        "label": "Dunkel",
        "header": "#323233", "activity": "#333333", "sidebar": "#252526",
        "main": "#1e1e1e", "status": "#007acc", "status_text": "#ffffff",
        "text": "#cccccc", "muted": "#858585", "accent": "#ffffff",
        "selection": "#094771", "hover": "#2a2d2e", "border": "#3c3c3c",
        "tab": "#2d2d2d",
    },
    "pastell": {
        "label": "Pastell (Debug)",
        "header": "#cfe8fc", "activity": "#e3d5f5", "sidebar": "#d5f5e3",
        "main": "#fdebd0", "status": "#fcf3cf", "status_text": "#333333",
        "text": "#2b2b2b", "muted": "#6b6b6b", "accent": "#2b2b2b",
        "selection": "#ffd6e0", "hover": "#f5c6d6", "border": "#b0b0b0",
        "tab": "#fad7a0",
    },
}

DEFAULT_THEME = "hell"


def stylesheet(c: dict) -> str:
    return f"""
    QWidget {{ color: {c['text']}; font-size: 13px; }}
    QMainWindow {{ background: {c['main']}; }}
    #header {{ background: {c['header']}; border-bottom: 1px solid {c['border']}; }}
    #activitybar {{ background: {c['activity']}; border-right: 1px solid {c['border']}; }}
    #activitybar QToolButton {{
        background: transparent; border: none; border-left: 2px solid transparent;
        padding: 10px 0px;
    }}
    #activitybar QToolButton:hover {{ background: {c['hover']}; }}
    #activitybar QToolButton:checked {{ border-left: 2px solid {c['accent']}; }}
    #sidebar {{ background: {c['sidebar']}; }}
    #sidebartitle {{ color: {c['muted']}; font-size: 11px; padding: 8px 12px; }}
    #content {{ background: {c['main']}; }}
    QTreeWidget {{ background: {c['sidebar']}; border: none; outline: 0; }}
    QTreeWidget::item {{ padding: 3px 2px; }}
    QTreeWidget::item:hover {{ background: {c['hover']}; }}
    QTreeWidget::item:selected {{ background: {c['selection']}; color: {c['text']}; }}
    QTabWidget::pane {{ border: none; background: {c['main']}; }}
    QTabBar::tab {{
        background: {c['tab']}; color: {c['muted']}; padding: 7px 14px;
        border: none; border-right: 1px solid {c['border']};
    }}
    QTabBar::tab:selected {{
        background: {c['main']}; color: {c['text']}; border-top: 1px solid {c['accent']};
    }}
    QStatusBar {{ background: {c['status']}; color: {c['status_text']}; }}
    QStatusBar QLabel {{ color: {c['status_text']}; }}
    QComboBox {{
        background: {c['main']}; border: 1px solid {c['border']};
        border-radius: 3px; padding: 3px 8px;
    }}
    QComboBox QAbstractItemView {{
        background: {c['main']}; selection-background-color: {c['selection']};
        selection-color: {c['text']};
    }}
    QSplitter::handle {{ background: {c['border']}; }}
    QToolTip {{ background: {c['main']}; color: {c['text']}; border: 1px solid {c['border']}; }}
    """

"""Farbstile (hell, dunkel, pastell) und das daraus erzeugte Stylesheet."""

# Pastell färbt jeden Bereich anders: Hilfsmittel zum Debuggen des Layouts.
THEMES = {
    "hell": {
        "label": "Hell",
        "header": "#f3f3f3", "surface": "#dcdcdc", "activity": "#ececec", "sidebar": "#f7f7f7",
        "main": "#ffffff",         "status": "#1b5e3a", "status_text": "#ffffff",
                "text": "#1f1f1f", "muted": "#6e6e6e", "accent": "#1b5e3a",
        "reachable": "#218838", "unreachable": "#c62828",
                "selection": "#d5eadd", "hover": "#e0e0e0", "border": "#d4d4d4",
        "tab": "#ececec",
    },
    "dunkel": {
        "label": "Dunkel",
        "header": "#323233", "surface": "#181818", "activity": "#333333", "sidebar": "#252526",
        "main": "#1e1e1e",         "status": "#1b5e3a", "status_text": "#ffffff",
                "text": "#cccccc", "muted": "#858585", "accent": "#3fa56b",
        "reachable": "#4ec982", "unreachable": "#f47067",
                "selection": "#1f4a33", "hover": "#2a2d2e", "border": "#3c3c3c",
        "tab": "#2d2d2d",
    },
    "pastell": {
        "label": "Pastell (Debug)",
        "header": "#cfe8fc", "surface": "#f0f0f0", "activity": "#e3d5f5", "sidebar": "#d5f5e3",
        "main": "#fdebd0", "status": "#fcf3cf", "status_text": "#333333",
        "text": "#2b2b2b", "muted": "#6b6b6b", "accent": "#2b2b2b",
        "reachable": "#2e7d32", "unreachable": "#c62828",
        "selection": "#ffd6e0", "hover": "#f5c6d6", "border": "#b0b0b0",
        "tab": "#fad7a0",
    },
}

DEFAULT_THEME = "dunkel"


def stylesheet(c: dict) -> str:
    return f"""
    QWidget {{ color: {c['text']}; font-size: 13px; }}
    QMainWindow {{ background: {c['surface']}; }}
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
    #content {{ background: {c['main']}; border-radius: 8px; }}
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
    #projectbutton {{
        background: transparent; border: none; border-radius: 3px;
        padding: 2px 10px; font-weight: 600; color: {c['status_text']};
    }}
    #projectbutton:hover {{ background: rgba(255, 255, 255, 40); }}
    #settingsbutton:hover {{ background: {c['hover']}; }}
    #projectbutton::menu-indicator, #settingsbutton::menu-indicator {{ image: none; width: 0; }}
    #settingsbutton {{ background: transparent; border: none; }}
    #welcome {{ background: {c['main']}; border-radius: 8px; }}
    #welcometitle {{ font-size: 28px; font-weight: 600; background: transparent; }}
    #welcomehint {{ color: {c['muted']}; background: transparent; }}
    #link {{
        background: transparent; border: none; color: {c['accent']}; padding: 4px 8px;
    }}
    #link:hover {{ background: {c['hover']}; border-radius: 3px; }}
    QMenuBar {{ background: {c['header']}; padding: 2px 6px; }}
    QMenuBar::item {{ padding: 4px 10px; border-radius: 3px; background: transparent; }}
    QMenuBar::item:selected {{ background: {c['hover']}; }}
    QMenu {{
        background: {c['main']}; border: 1px solid {c['border']}; padding: 4px;
    }}
    QMenu::item {{ padding: 6px 24px 6px 12px; border-radius: 3px; }}
    QMenu::item:selected {{ background: {c['selection']}; color: {c['text']}; }}
    QMenu::indicator:checked {{ background: {c['accent']}; border-radius: 3px; }}
    QSplitter::handle {{ background: transparent; }}
    QToolTip {{ background: {c['main']}; color: {c['text']}; border: 1px solid {c['border']}; }}
    """

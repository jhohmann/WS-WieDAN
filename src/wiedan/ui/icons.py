"""Linien-Icons als SVG, in beliebiger Farbe gerendert."""
from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

_SHAPES = {
    "live": '<polyline points="3 12 7 12 10 4 14 20 17 12 21 12"/>',
    "commissioning": (
        '<line x1="4" y1="6" x2="20" y2="6"/><circle cx="9" cy="6" r="2"/>'
        '<line x1="4" y1="12" x2="20" y2="12"/><circle cx="15" cy="12" r="2"/>'
        '<line x1="4" y1="18" x2="20" y2="18"/><circle cx="8" cy="18" r="2"/>'
    ),
    "plotter": (
        '<polyline points="3 3 3 21 21 21"/>'
        '<polyline points="7 16 11 11 14 14 20 7"/>'
    ),
    "device": (
        '<rect x="6" y="6" width="12" height="12" rx="2"/>'
        '<line x1="10" y1="2" x2="10" y2="6"/><line x1="14" y1="2" x2="14" y2="6"/>'
        '<line x1="10" y1="18" x2="10" y2="22"/><line x1="14" y1="18" x2="14" y2="22"/>'
    ),
    "vehicle": (
        '<rect x="5" y="3" width="14" height="14" rx="3"/>'
        '<line x1="5" y1="11" x2="19" y2="11"/>'
        '<line x1="8" y1="21" x2="10" y2="17"/><line x1="16" y1="21" x2="14" y2="17"/>'
    ),
    "settings": (
        '<circle cx="12" cy="12" r="3"/>'
        '<path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1'
        'M4.9 19.1L7 17M17 7l2.1-2.1"/>'
    ),
    "central": (
        '<rect x="3" y="4" width="18" height="6" rx="1"/>'
        '<rect x="3" y="14" width="18" height="6" rx="1"/>'
        '<line x1="7" y1="7" x2="7.01" y2="7"/><line x1="7" y1="17" x2="7.01" y2="17"/>'
    ),
}


def _pixmap(name: str, color: str) -> QPixmap:
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        f'stroke="{color}" stroke-width="1.75" stroke-linecap="round" '
        f'stroke-linejoin="round">{_SHAPES[name]}</svg>'
    )
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    QSvgRenderer(QByteArray(svg.encode())).render(painter)
    painter.end()
    return pixmap


def icon(name: str, color: str, color_checked: str | None = None) -> QIcon:
    result = QIcon()
    result.addPixmap(_pixmap(name, color), QIcon.Mode.Normal, QIcon.State.Off)
    if color_checked:
        result.addPixmap(_pixmap(name, color_checked), QIcon.Mode.Normal, QIcon.State.On)
    return result

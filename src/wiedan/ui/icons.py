"""Linien-Icons aus ui/svg/*.svg, beim Aufruf in beliebiger Farbe gerendert.

In den SVG-Dateien steht die Farbe als `currentColor`.
"""
from functools import cache
from importlib.resources import files

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer


@cache
def _source(name: str) -> str:
    return (files("wiedan.ui") / "svg" / f"{name}.svg").read_text(encoding="utf-8")


def pick(name: str | None, fallback: str) -> str:
    """Icon-Name, falls die SVG-Datei existiert, sonst der Ersatz."""
    if name and (files("wiedan.ui") / "svg" / f"{name.lower()}.svg").is_file():
        return name.lower()
    return fallback


@cache
def _pixmap(name: str, color: str) -> QPixmap:
    svg = _source(name).replace("currentColor", color)
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    QSvgRenderer(QByteArray(svg.encode())).render(painter)
    painter.end()
    return pixmap


@cache
def icon(name: str, color: str, color_checked: str | None = None) -> QIcon:
    result = QIcon()
    result.addPixmap(_pixmap(name, color), QIcon.Mode.Normal, QIcon.State.Off)
    if color_checked:
        result.addPixmap(_pixmap(name, color_checked), QIcon.Mode.Normal, QIcon.State.On)
    return result

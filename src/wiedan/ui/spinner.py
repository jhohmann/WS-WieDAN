"""Kleiner Ladekreis; dreht sich nur, solange er sichtbar ist."""
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QIcon, QPixmap, QTransform
from PySide6.QtWidgets import QLabel

from wiedan.ui.icons import icon

SIZE = 14


def spinner_pixmap(color: str, angle: int, size: int = SIZE) -> QPixmap:
    pixmap = icon("spinner", color).pixmap(size, size)
    rotated = pixmap.transformed(
        QTransform().rotate(angle), Qt.TransformationMode.SmoothTransformation
    )
    x = (rotated.width() - pixmap.width()) // 2
    y = (rotated.height() - pixmap.height()) // 2
    return rotated.copy(x, y, pixmap.width(), pixmap.height())


def spinner_icon(color: str, angle: int) -> QIcon:
    return QIcon(spinner_pixmap(color, angle, 64))


class Spinner(QLabel):
    def __init__(self):
        super().__init__()
        self.setFixedSize(SIZE, SIZE)
        self.setScaledContents(False)
        self._angle = 0
        self._color = "#6e6e6e"
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._step)
        self.hide()

    def set_color(self, color: str):
        self._color = color
        self._draw()

    def set_running(self, running: bool):
        self.setVisible(running)
        if running:
            self._timer.start(80)
        else:
            self._timer.stop()

    def _step(self):
        self._angle = (self._angle + 30) % 360
        self._draw()

    def _draw(self):
        self.setPixmap(spinner_pixmap(self._color, self._angle))

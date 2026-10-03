"""Leere Hauptfläche: dezentes Projektfoto, Projektname und Link zum Projektwechsel."""
from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

PHOTO_OPACITY = 0.15
RADIUS = 8


class WelcomePage(QFrame):
    switch_requested = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("welcome")
        self._photo = QPixmap()
        self._scaled = QPixmap()

        self._title = QLabel()
        self._title.setObjectName("welcometitle")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint = QLabel("Anderes Projekt?")
        hint.setObjectName("welcomehint")
        link = QPushButton("Projekt wechseln")
        link.setObjectName("link")
        link.setCursor(Qt.CursorShape.PointingHandCursor)
        link.clicked.connect(self.switch_requested)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(hint)
        row.addWidget(link)
        row.addStretch()

        layout = QVBoxLayout(self)
        layout.addStretch()
        layout.addWidget(self._title)
        layout.addLayout(row)
        layout.addStretch()

    def set_project(self, name: str, photo: bytes | None):
        self._title.setText(name)
        self._photo = QPixmap()
        if photo:
            self._photo.loadFromData(photo)
        self._rescale()
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rescale()

    def _rescale(self):
        if self._photo.isNull():
            self._scaled = QPixmap()
            return
        self._scaled = self._photo.scaled(
            self.size() * self.devicePixelRatioF(),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._scaled.isNull():
            return
        painter = QPainter(self)
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(self.rect()), RADIUS, RADIUS)
        painter.setClipPath(clip)
        painter.setOpacity(PHOTO_OPACITY)
        dpr = self.devicePixelRatioF()
        x = (self._scaled.width() - self.width() * dpr) / 2
        y = (self._scaled.height() - self.height() * dpr) / 2
        painter.drawPixmap(
            QRectF(self.rect()), self._scaled,
            QRectF(x, y, self.width() * dpr, self.height() * dpr),
        )

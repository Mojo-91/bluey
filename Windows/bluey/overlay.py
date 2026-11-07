"""On-screen output: a pointer (ring + mini Bluey + caption) and the research card."""
from __future__ import annotations

import html

from PyQt6.QtCore import QEasingCurve, QPoint, QPointF, QPropertyAnimation, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QCursor, QFont, QGuiApplication, QLinearGradient, QPainter, QPen
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QToolButton, QVBoxLayout, QWidget

TOP = (Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)


class PointerOverlay(QWidget):
    """Small click-through window that glides to whatever Bluey is pointing at."""
    W, H = 330, 150
    AX, AY = 22, 126          # where the target sits inside the window

    def __init__(self) -> None:
        super().__init__(None, TOP | Qt.WindowType.WindowTransparentForInput)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedSize(self.W, self.H)
        self._caption = ""
        self._anim = QPropertyAnimation(self, b"pos")
        self._anim.setDuration(450)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def show_at(self, x: int, y: int, caption: str | None = None) -> None:
        """x, y in Qt (logical) pixels."""
        if caption:
            self._caption = caption
        dest = QPoint(x - self.AX, y - self.AY)
        if not self.isVisible():
            self.move(dest)
            self.show()
        else:
            self._anim.stop()
            self._anim.setStartValue(self.pos())
            self._anim.setEndValue(dest)
            self._anim.start()
        self.update()

    def set_caption(self, text: str) -> None:
        self._caption = text
        if not self.isVisible():
            c = QCursor.pos()
            self.show_at(c.x(), c.y())
        self.update()

    def hide_now(self) -> None:
        self._caption = ""
        self.hide()

    def paintEvent(self, _) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor("#2f5bff"), 3))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(self.AX, self.AY), 17, 17)

        if self._caption:
            r = QRectF(44, 8, 276, 66)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("white"))
            p.drawRoundedRect(r, 14, 14)
            p.setPen(QColor("#111111"))
            f = QFont()
            f.setPointSize(10)
            p.setFont(f)
            p.drawText(r.adjusted(12, 6, -12, -6),
                       int(Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap), self._caption)

        c = QPointF(70, 108)
        g = QLinearGradient(c.x(), c.y() - 19, c.x(), c.y() + 19)
        g.setColorAt(0, QColor("#b8d8ff"))
        g.setColorAt(1, QColor("#1f40f2"))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(g))
        p.drawEllipse(c, 19, 19)
        for dx in (-7, 7):
            p.setBrush(QColor("white"))
            p.drawEllipse(QPointF(c.x() + dx, c.y() - 2), 6, 6)
            p.setBrush(QColor("#141f8c"))
            p.drawEllipse(QPointF(c.x() + dx + 0.5, c.y() - 1.5), 2.6, 2.6)
        p.end()


class CardOverlay(QWidget):
    """Top-right card: 'Doing some research…' > title + first lines + sources.
    Click it (or the blue arrow) to expand. The blue minus folds it back to the preview; minus again hides it."""
    PREVIEW = 180
    BTN = ("QToolButton{background:#2f5bff;color:white;border:0;border-radius:11px;font-weight:700;}"
           "QToolButton:hover{background:#4d74ff;}")

    def __init__(self) -> None:
        super().__init__(None, TOP)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedWidth(372)
        self._title, self._text, self._sources, self._expanded = "", "", [], False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 6, 6, 6)
        frame = QFrame()
        frame.setStyleSheet("QFrame{background:rgba(24,28,44,240);border-radius:16px;}"
                            "QLabel{background:transparent;color:#dfe6ff;}")
        outer.addWidget(frame)
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(14, 12, 14, 14)
        lay.setSpacing(8)

        head = QHBoxLayout()
        self.title_lbl = QLabel()
        self.title_lbl.setStyleSheet("font-size:15px;font-weight:700;color:white;")
        self.title_lbl.setWordWrap(True)
        self.up_btn = QToolButton()
        self.up_btn.setText("▲")
        self.min_btn = QToolButton()
        self.min_btn.setText("–")
        for b in (self.up_btn, self.min_btn):
            b.setFixedSize(22, 22)
            b.setStyleSheet(self.BTN)
        self.up_btn.clicked.connect(self.expand)
        self.min_btn.clicked.connect(self.minus)
        head.addWidget(self.title_lbl, 1)
        head.addWidget(self.up_btn)
        head.addWidget(self.min_btn)
        lay.addLayout(head)

        self.body_lbl = QLabel()
        self.body_lbl.setWordWrap(True)
        self.src_lbl = QLabel()
        self.src_lbl.setWordWrap(True)
        self.src_lbl.setOpenExternalLinks(True)
        lay.addWidget(self.body_lbl)
        lay.addWidget(self.src_lbl)

    def show_card(self, title: str, text: str, sources: list) -> None:
        self._title, self._text, self._sources, self._expanded = title, text, sources, False
        self._render()
        self.show()

    def expand(self) -> None:
        if self._text:
            self._expanded = True
            self._render()

    def minus(self) -> None:
        if self._expanded:
            self._expanded = False
            self._render()
        else:
            self.hide()

    def mousePressEvent(self, e) -> None:
        self.expand()

    def _render(self) -> None:
        self.title_lbl.setText(self._title)
        body = self._text
        if not self._expanded and len(body) > self.PREVIEW:
            body = body[: self.PREVIEW].rstrip() + "…"
        self.body_lbl.setText(body)
        self.body_lbl.setVisible(bool(body))
        links = [f'<a href="{html.escape(u, quote=True)}" style="color:#8fb4ff">{html.escape(t)}</a>'
                 for t, u in self._sources if u.startswith(("http://", "https://"))]
        self.src_lbl.setText("<br>".join(links))
        self.src_lbl.setVisible(self._expanded and bool(links))
        has_text = bool(self._text)
        self.up_btn.setVisible(has_text and not self._expanded)
        self.min_btn.setVisible(has_text)
        self.layout().activate()
        self.adjustSize()
        g = QGuiApplication.primaryScreen().availableGeometry()
        self.move(g.right() - self.width() - 12, g.top() + 12)

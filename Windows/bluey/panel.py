"""The Bluey window: pairing code, status, API key, pause. Closing it hides it to the tray."""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

STYLE = """
QWidget{background:#0f1424;color:#e8eefc;font-size:13px;}
QLabel#title{font-size:22px;font-weight:700;}
QLabel#code{font-size:46px;font-weight:700;letter-spacing:6px;color:white;background:#18203a;border-radius:14px;padding:10px;}
QLabel#hint{color:#8fa0d8;}
QLineEdit{background:#18203a;border:1px solid #2a3560;border-radius:8px;padding:7px;color:white;}
QPushButton{background:#2f5bff;border:0;border-radius:8px;padding:8px 14px;color:white;font-weight:600;}
QPushButton:hover{background:#4d74ff;}
QPushButton#quiet{background:#18203a;}
"""


class Panel(QWidget):
    key_saved = pyqtSignal(str)
    new_code_requested = pyqtSignal()
    paused_changed = pyqtSignal(bool)
    autostart_changed = pyqtSignal(bool)
    firewall_requested = pyqtSignal()

    def __init__(self, code: str, has_key: bool, autostart: bool) -> None:
        super().__init__()
        self.setWindowTitle("Bluey")
        self.setFixedWidth(430)
        self.setStyleSheet(STYLE)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 20)
        lay.setSpacing(10)

        t = QLabel("Bluey")
        t.setObjectName("title")
        lay.addWidget(t)
        lay.addWidget(self._hint("Pair your phone: open Bluey on it (same Wi-Fi as this PC) and type this code."))
        self.code_lbl = QLabel()
        self.code_lbl.setObjectName("code")
        self.code_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.code_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(self.code_lbl)
        self.set_code(code)
        self.status_lbl = QLabel("Starting…")
        lay.addWidget(self.status_lbl)

        lay.addSpacing(6)
        lay.addWidget(QLabel("Anthropic API key"))
        row = QHBoxLayout()
        self.key_edit = QLineEdit()
        self.key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_edit.setPlaceholderText("sk-ant-…")
        save = QPushButton("Save")
        save.clicked.connect(self._save_key)
        row.addWidget(self.key_edit, 1)
        row.addWidget(save)
        lay.addLayout(row)
        self.key_lbl = QLabel()
        lay.addWidget(self.key_lbl)
        self.set_key_state(has_key)

        lay.addSpacing(6)
        self.pause_cb = QCheckBox("Pause computer control (Bluey can't click or type)")
        self.pause_cb.toggled.connect(self.paused_changed)
        self.auto_cb = QCheckBox("Start Bluey when Windows starts")
        self.auto_cb.setChecked(autostart)
        self.auto_cb.toggled.connect(self.autostart_changed)
        lay.addWidget(self.pause_cb)
        lay.addWidget(self.auto_cb)

        fw = QPushButton("Phone can't connect? Fix Windows Firewall")
        fw.setObjectName("quiet")
        fw.clicked.connect(self.firewall_requested)
        lay.addWidget(fw)

        row2 = QHBoxLayout()
        newc = QPushButton("New code")
        newc.setObjectName("quiet")
        newc.clicked.connect(self.new_code_requested)
        hide = QPushButton("Hide")
        hide.setObjectName("quiet")
        hide.clicked.connect(self.hide)
        row2.addWidget(newc)
        row2.addStretch(1)
        row2.addWidget(hide)
        lay.addLayout(row2)
        lay.addWidget(self._hint("Closing this window keeps Bluey running. Find it in the tray, near the clock."))

    @staticmethod
    def _hint(text: str) -> QLabel:
        l = QLabel(text)
        l.setObjectName("hint")
        l.setWordWrap(True)
        return l

    def _save_key(self) -> None:
        k = self.key_edit.text().strip()
        if k:
            self.key_saved.emit(k)
            self.key_edit.clear()

    def set_code(self, code: str) -> None:
        self.code_lbl.setText(f"{code[:3]} {code[3:]}")

    def set_status(self, text: str, connected: bool) -> None:
        self.status_lbl.setText(f"<span style='color:{'#3ddc84' if connected else '#f5a623'}'>●</span> {text}")

    def set_key_state(self, ok: bool, err: str = "") -> None:
        if ok:
            self.key_lbl.setText("<span style='color:#3ddc84'>✓ API key saved</span>")
        else:
            self.key_lbl.setText(f"<span style='color:#ff8a8a'>{err or 'No API key yet. Get one at console.anthropic.com'}</span>")

    def set_paused(self, v: bool) -> None:
        self.pause_cb.blockSignals(True)
        self.pause_cb.setChecked(v)
        self.pause_cb.blockSignals(False)

    def closeEvent(self, e) -> None:
        e.ignore()
        self.hide()

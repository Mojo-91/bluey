"""Bluey for Windows: window + tray app that talks to the phone and drives the PC."""
from __future__ import annotations

import sys
import threading
import traceback

from PyQt6.QtCore import QObject, QPointF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QBrush, QColor, QCursor, QGuiApplication, QIcon, QLinearGradient, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from . import agent as agent_mod
from . import computer, config
from .link import PORT, Server, lan_ip
from .overlay import CardOverlay, PointerOverlay
from .panel import Panel


class Bridge(QObject):
    """Signals are how worker threads talk to the UI thread safely."""
    msg = pyqtSignal(dict)
    conn = pyqtSignal(bool)
    state = pyqtSignal(str)
    caption = pyqtSignal(str)
    point = pyqtSignal(int, int, str)
    card = pyqtSignal(str, str, list)
    report = pyqtSignal(str, str, list)
    say = pyqtSignal(str)
    done = pyqtSignal()


class AgentUI:
    """What the agent thread sees."""
    def __init__(self, bridge: Bridge) -> None:
        self.b = bridge
        self.paused = False

    def set_state(self, s: str) -> None: self.b.state.emit(s)
    def caption(self, t: str) -> None: self.b.caption.emit(t)
    def point(self, x: int, y: int, label) -> None: self.b.point.emit(int(x), int(y), label or "")
    def card(self, title: str, text: str, sources: list) -> None: self.b.card.emit(title, text, sources)
    def report(self, title: str, text: str, sources: list) -> None: self.b.report.emit(title, text, sources)
    def say(self, text: str) -> None: self.b.say.emit(text)


def make_icon() -> QIcon:
    pm = QPixmap(64, 64)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    g = QLinearGradient(0, 0, 0, 64)
    g.setColorAt(0, QColor("#b8d8ff"))
    g.setColorAt(1, QColor("#1f40f2"))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(g))
    p.drawEllipse(2, 2, 60, 60)
    for x in (20, 44):
        p.setBrush(QColor("white"))
        p.drawEllipse(QPointF(x, 28), 9, 9)
        p.setBrush(QColor("#141f8c"))
        p.drawEllipse(QPointF(x + 1, 29), 4, 4)
    p.end()
    return QIcon(pm)


class Brain(QObject):
    def __init__(self) -> None:
        super().__init__()
        self.state = "idle"
        self.busy = False
        self.look_override = None            # physical px
        self.last_look = (-1.0, -1.0)

        self.bridge = Bridge()
        self.ui = AgentUI(self.bridge)
        self.agent = agent_mod.Agent()
        self.pointer = PointerOverlay()
        self.card = CardOverlay()

        self.panel = Panel(config.pairing_code(), agent_mod.get_key() is not None, config.get_autostart())
        self.panel.setWindowIcon(make_icon())
        self.panel.key_saved.connect(self.save_key)
        self.panel.new_code_requested.connect(self.new_code)
        self.panel.paused_changed.connect(self.set_paused)
        self.panel.autostart_changed.connect(config.set_autostart)
        self.panel.firewall_requested.connect(self.fix_firewall)

        self.bridge.msg.connect(self.on_msg)
        self.bridge.conn.connect(self.on_conn)
        self.bridge.state.connect(self.set_state)
        self.bridge.caption.connect(self.on_caption)
        self.bridge.point.connect(self.on_point)
        self.bridge.card.connect(self.card.show_card)
        self.bridge.report.connect(self.on_report)
        self.bridge.say.connect(self.on_say)
        self.bridge.done.connect(self.on_done)

        self.server = Server(self.bridge.msg.emit, self.bridge.conn.emit, config.pairing_code)
        try:
            self.server.start()
        except OSError:
            QMessageBox.warning(None, "Bluey", "Bluey is already running (look in the tray near the clock).")
            QTimer.singleShot(0, QApplication.quit)
            return
        self._build_tray()
        self.set_status(self.waiting(), False)
        self.panel.show()

        self.tick = QTimer(self)
        self.tick.timeout.connect(self.send_look)
        self.tick.start(33)

    # ---- tray
    def _build_tray(self) -> None:
        self.tray = QSystemTrayIcon(make_icon())
        self.tray.setToolTip("Bluey")
        menu = QMenu()
        open_ = QAction("Open Bluey")
        open_.triggered.connect(self.show_panel)
        menu.addAction(open_)
        self.status = QAction("Starting…")
        self.status.setEnabled(False)
        menu.addAction(self.status)
        self.pause_act = QAction("Pause computer control")
        self.pause_act.setCheckable(True)
        self.pause_act.toggled.connect(self.set_paused)
        menu.addAction(self.pause_act)
        menu.addSeparator()
        quit_ = QAction("Quit")
        quit_.triggered.connect(self.quit)
        menu.addAction(quit_)
        self.menu = menu
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda r: self.show_panel() if r in (
            QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick) else None)
        self.tray.show()

    def show_panel(self) -> None:
        self.panel.show()
        self.panel.raise_()
        self.panel.activateWindow()

    def waiting(self) -> str:
        return f"Waiting for phone… ({lan_ip() or 'no Wi-Fi'}:{PORT})"

    def set_status(self, text: str, connected: bool) -> None:
        self.status.setText(text)
        self.panel.set_status(text, connected)

    def set_paused(self, v: bool) -> None:
        self.ui.paused = v
        self.pause_act.blockSignals(True)
        self.pause_act.setChecked(v)
        self.pause_act.blockSignals(False)
        self.panel.set_paused(v)

    def save_key(self, k: str) -> None:
        try:
            agent_mod.set_key(k)
            self.panel.set_key_state(True)
        except Exception as e:
            self.panel.set_key_state(False, f"Couldn't save the key: {e}")

    def fix_firewall(self) -> None:
        """One UAC prompt, then Windows lets the phone reach Bluey's port."""
        import ctypes
        args = f'advfirewall firewall add rule name="Bluey" dir=in action=allow protocol=TCP localport={PORT} profile=any'
        try:
            ctypes.windll.shell32.ShellExecuteW(None, "runas", "netsh", args, None, 0)
        except Exception as e:
            QMessageBox.warning(None, "Bluey", f"Couldn't open the firewall prompt: {e}")

    def new_code(self) -> None:
        self.panel.set_code(config.new_code())
        self.server.drop()                    # the old phone has to pair again

    def quit(self) -> None:
        self.server.stop()
        QApplication.quit()

    # ---- phone -> PC
    def on_conn(self, ok: bool) -> None:
        self.set_status("Phone connected" if ok else self.waiting(), ok)
        if ok:
            self.set_state("idle")

    def on_msg(self, m: dict) -> None:
        t = m.get("t")
        if t == "wake":
            if not self.busy:
                self.set_state("listening")
        elif t == "ask" and not self.busy:
            text = str(m.get("text", "")).strip()
            if not text:
                return
            self.busy = True
            self.look_override = None
            self.set_state("thinking")
            threading.Thread(target=self._run_agent, args=(text,), daemon=True).start()

    def _run_agent(self, text: str) -> None:
        try:
            self.agent.run(text, self.ui)
        finally:
            self.bridge.done.emit()

    def on_done(self) -> None:
        self.busy = False
        self.look_override = None
        if self.state != "sleeping":
            self.set_state("listening")      # awake: thick blue border until he's told to sleep
        QTimer.singleShot(4000, lambda: None if self.busy else self.pointer.hide_now())

    # ---- PC -> phone
    def set_state(self, s: str) -> None:
        self.state = s
        self.server.send({"t": "state", "s": s})

    def send_look(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if self.look_override is not None:
            w, h = computer.screen_size()
            nx, ny = self.look_override[0] / w, self.look_override[1] / h
        else:
            g, c = screen.geometry(), QCursor.pos()
            nx, ny = (c.x() - g.x()) / g.width(), (c.y() - g.y()) / g.height()
        nx, ny = min(max(nx, 0.0), 1.0), min(max(ny, 0.0), 1.0)
        if abs(nx - self.last_look[0]) > 0.002 or abs(ny - self.last_look[1]) > 0.002:
            self.last_look = (nx, ny)
            self.server.send({"t": "look", "x": round(nx, 4), "y": round(ny, 4)})

    # ---- on-screen output (physical px in, logical px for Qt)
    def on_point(self, x: int, y: int, label: str) -> None:
        self.look_override = (x, y)
        dpr = QGuiApplication.primaryScreen().devicePixelRatio()
        self.pointer.show_at(int(x / dpr), int(y / dpr), label or None)

    def on_caption(self, text: str) -> None:
        self.pointer.set_caption(text)

    def on_say(self, text: str) -> None:           # one-line takeaway: his bubble + the phone transcript
        self.pointer.set_caption(text)
        self.server.send({"t": "say", "text": text})

    def on_report(self, title: str, text: str, sources: list) -> None:
        self.server.send({"t": "report", "title": title, "text": text, "sources": sources})


def main() -> None:
    def hook(t, v, tb) -> None:
        try:
            config.log_path().write_text("".join(traceback.format_exception(t, v, tb)), encoding="utf-8")
        except Exception:
            pass

    sys.excepthook = hook
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app._bluey = Brain()   # keep a reference so it lives as long as the event loop
    sys.exit(app.exec())

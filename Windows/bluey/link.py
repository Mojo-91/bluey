"""TCP server the phone connects to. One JSON object per line. Advertised over Bonjour/mDNS."""
from __future__ import annotations

import hmac
import json
import queue
import socket
import threading
import time
from typing import Callable, Optional

PORT = 47474


def lan_ip() -> Optional[str]:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))   # no packet is sent; just picks the Wi-Fi interface
        return s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()


class Server:
    def __init__(self, on_msg: Callable[[dict], None], on_conn: Callable[[bool], None], get_code: Callable[[], str]):
        self.on_msg = on_msg
        self.on_conn = on_conn
        self.get_code = get_code
        self._fails: list = []
        self._locked_until = 0.0
        self._conn: Optional[socket.socket] = None
        self._lock = threading.Lock()
        self._out: "queue.Queue[bytes]" = queue.Queue(maxsize=300)
        self._srv: Optional[socket.socket] = None
        self._zc = None
        self._info = None

    def start(self) -> None:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("0.0.0.0", PORT))
        srv.listen(2)
        self._srv = srv
        threading.Thread(target=self._accept, daemon=True).start()
        threading.Thread(target=self._sender, daemon=True).start()
        threading.Thread(target=self._advertise, daemon=True).start()

    def stop(self) -> None:
        try:
            if self._zc and self._info:
                self._zc.unregister_service(self._info)
                self._zc.close()
        except Exception:
            pass
        try:
            if self._srv:
                self._srv.close()
        except OSError:
            pass

    def send(self, obj: dict) -> None:
        try:
            self._out.put_nowait((json.dumps(obj, separators=(",", ":")) + "\n").encode())
        except queue.Full:
            pass

    # -- internals
    def drop(self) -> None:
        """Disconnect the current phone (used when the pairing code is changed)."""
        with self._lock:
            c, self._conn = self._conn, None
        if c:
            try:
                c.close()
            except OSError:
                pass

    def _accept(self) -> None:
        while True:
            try:
                c, _ = self._srv.accept()
            except OSError:
                return
            threading.Thread(target=self._handshake, args=(c,), daemon=True).start()

    def _check(self, line: str) -> bool:
        now = time.time()
        if now < self._locked_until:
            return False
        ok = False
        try:
            j = json.loads(line)
            ok = j.get("t") == "hello" and hmac.compare_digest(str(j.get("code", "")), str(self.get_code()))
        except (ValueError, AttributeError, TypeError):
            ok = False
        if ok:
            self._fails = []
        else:                                   # 5 wrong tries in a minute = locked for a minute
            self._fails = [t for t in self._fails if now - t < 60] + [now]
            if len(self._fails) >= 5:
                self._locked_until = now + 60
                self._fails = []
        return ok

    def _handshake(self, c: socket.socket) -> None:
        """Nothing the phone says counts until it has sent the right code."""
        try:
            c.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            c.settimeout(8)
            f = c.makefile("r", encoding="utf-8", newline="\n")
            if not self._check(f.readline(512)):
                time.sleep(1.0)
                c.sendall(b'{"t":"denied"}\n')
                c.close()
                return
            c.settimeout(None)
            c.sendall(b'{"t":"ok"}\n')
        except (OSError, ValueError):
            try:
                c.close()
            except OSError:
                pass
            return
        with self._lock:
            old, self._conn = self._conn, c
        if old:
            try:
                old.close()
            except OSError:
                pass
        self._read(c, f)

    def _read(self, c: socket.socket, f) -> None:
        self.on_conn(True)
        try:
            with f:
                for line in f:
                    try:
                        self.on_msg(json.loads(line))
                    except ValueError:
                        pass
        except OSError:
            pass
        with self._lock:
            mine = self._conn is c
            if mine:
                self._conn = None
        try:
            c.close()
        except OSError:
            pass
        if mine:
            self.on_conn(False)

    def _sender(self) -> None:
        while True:
            data = self._out.get()
            with self._lock:
                c = self._conn
            if c:
                try:
                    c.sendall(data)
                except OSError:
                    pass

    def _advertise(self) -> None:
        try:
            from zeroconf import ServiceInfo, Zeroconf

            ip = lan_ip()
            if not ip:
                return
            self._info = ServiceInfo(
                "_bluey._tcp.local.", "Bluey._bluey._tcp.local.",
                addresses=[socket.inet_aton(ip)], port=PORT,
            )
            self._zc = Zeroconf()
            self._zc.register_service(self._info)
        except Exception as e:   # discovery is a convenience; typing the IP on the phone still works
            print("mDNS advertise failed:", e)

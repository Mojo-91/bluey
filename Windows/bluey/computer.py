"""Everything that touches the PC: screenshots, mouse, keyboard, launching apps (Windows, SendInput).

Claude sees a screenshot scaled to api_size(); coordinates it returns are mapped back to physical pixels.
Needs a per-monitor DPI-aware process (Qt 6 sets that up), so pixels here are real pixels.
"""
from __future__ import annotations

import base64
import ctypes
import io
import os
import time
from ctypes import wintypes
from dataclasses import dataclass
from typing import Any, Optional, Tuple

IS_WIN = os.name == "nt"
user32 = ctypes.windll.user32 if IS_WIN else None


@dataclass
class Outcome:
    text: Optional[str] = None
    image: Optional[str] = None
    target: Optional[Tuple[int, int]] = None      # physical pixels


def screen_size() -> Tuple[int, int]:
    return (user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)) if IS_WIN else (1920, 1080)


def api_size() -> Tuple[int, int]:
    w, h = screen_size()
    s = min(1.0, 1280 / w)
    return int(w * s), int(h * s)


def to_screen(x: float, y: float) -> Tuple[int, int]:
    w, h = screen_size()
    aw, ah = api_size()
    return round(x * w / aw), round(y * h / ah)


def _pt(v: Any) -> Optional[Tuple[int, int]]:
    if isinstance(v, (list, tuple)) and len(v) == 2:
        return to_screen(float(v[0]), float(v[1]))
    return None


# ---------------------------------------------------------------- screenshot
def screenshot() -> str:
    import mss
    from PIL import Image

    w, h = screen_size()
    aw, ah = api_size()
    with mss.mss() as sct:
        shot = sct.grab({"left": 0, "top": 0, "width": w, "height": h})
    img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
    if img.size != (aw, ah):
        img = img.resize((aw, ah), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode()


# ---------------------------------------------------------------- SendInput plumbing
ULONG_PTR = ctypes.c_size_t


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD)]


class _U(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _U)]


KEYUP, UNICODE, EXTENDED = 0x0002, 0x0004, 0x0001


def _send(*inputs: INPUT) -> None:
    arr = (INPUT * len(inputs))(*inputs)
    user32.SendInput(len(inputs), arr, ctypes.sizeof(INPUT))


def _kbd(vk: int = 0, scan: int = 0, flags: int = 0) -> INPUT:
    return INPUT(type=1, u=_U(ki=KEYBDINPUT(vk, scan, flags, 0, 0)))


VK = {
    "ctrl": 0x11, "control": 0x11, "cmd": 0x11, "command": 0x11, "shift": 0x10, "alt": 0x12, "option": 0x12,
    "win": 0x5B, "windows": 0x5B, "super": 0x5B, "meta": 0x5B,
    "enter": 0x0D, "return": 0x0D, "tab": 0x09, "esc": 0x1B, "escape": 0x1B, "backspace": 0x08,
    "delete": 0x2E, "del": 0x2E, "space": 0x20, "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "home": 0x24, "end": 0x23, "pageup": 0x21, "page_up": 0x21, "pagedown": 0x22, "page_down": 0x22, "insert": 0x2D,
}
for _i in range(1, 13):
    VK[f"f{_i}"] = 0x6F + _i
EXT_VKS = {0x26, 0x28, 0x25, 0x27, 0x24, 0x23, 0x21, 0x22, 0x2D, 0x2E, 0x5B}
MODS = {0x11, 0x10, 0x12, 0x5B}


def _vk_event(vk: int, up: bool = False) -> INPUT:
    flags = (EXTENDED if vk in EXT_VKS else 0) | (KEYUP if up else 0)
    return _kbd(vk=vk, flags=flags)


def press(combo: str) -> None:
    """'ctrl+l', 'enter', 'alt+tab', 'win', 'f5', 'ctrl+shift+t'."""
    mods, main = [], []
    for part in combo.split("+"):
        name = part.strip().lower()
        if name.endswith(("_l", "_r")) and name[:-2] in VK:
            name = name[:-2]
        if name in VK:
            (mods if VK[name] in MODS else main).append(VK[name])
        elif len(name) == 1:
            r = user32.VkKeyScanW(ord(name))
            if r == -1:
                type_text(name)
                continue
            if (r >> 8) & 1 and 0x10 not in mods:
                mods.append(0x10)
            main.append(r & 0xFF)
    for vk in mods:
        _send(_vk_event(vk))
    for vk in main:
        _send(_vk_event(vk), _vk_event(vk, up=True))
    for vk in reversed(mods):
        _send(_vk_event(vk, up=True))


def type_text(s: str) -> None:
    for ch in s:
        if ch == "\n":
            press("enter")
            continue
        if ch == "\t":
            press("tab")
            continue
        data = ch.encode("utf-16-le")
        for i in range(0, len(data), 2):
            unit = int.from_bytes(data[i:i + 2], "little")
            _send(_kbd(scan=unit, flags=UNICODE), _kbd(scan=unit, flags=UNICODE | KEYUP))
        time.sleep(0.008)


# mouse
LD, LU, RD, RU, WHEEL, HWHEEL = 0x0002, 0x0004, 0x0008, 0x0010, 0x0800, 0x1000


def move(p: Tuple[int, int]) -> None:
    user32.SetCursorPos(int(p[0]), int(p[1]))


def click(p: Tuple[int, int], right: bool = False, count: int = 1) -> None:
    move(p)
    time.sleep(0.08)
    for _ in range(count):
        user32.mouse_event(RD if right else LD, 0, 0, 0, 0)
        user32.mouse_event(RU if right else LU, 0, 0, 0, 0)
        time.sleep(0.04)


def drag(a: Tuple[int, int], b: Tuple[int, int]) -> None:
    move(a)
    time.sleep(0.08)
    user32.mouse_event(LD, 0, 0, 0, 0)
    for i in range(1, 9):
        move((a[0] + (b[0] - a[0]) * i // 8, a[1] + (b[1] - a[1]) * i // 8))
        time.sleep(0.02)
    time.sleep(0.05)
    user32.mouse_event(LU, 0, 0, 0, 0)


def scroll(direction: str, amount: int) -> None:
    n = 120 * amount
    if direction in ("up", "down"):
        user32.mouse_event(WHEEL, 0, 0, n if direction == "up" else -n, 0)
    else:
        user32.mouse_event(HWHEEL, 0, 0, n if direction == "right" else -n, 0)


# ---------------------------------------------------------------- the computer-use tool
def perform(a: dict) -> Outcome:
    if not IS_WIN:
        raise RuntimeError("Computer control only works on Windows")
    act = a.get("action", "")
    p = _pt(a.get("coordinate"))

    if act == "screenshot":
        return Outcome(image=screenshot())
    if act == "cursor_position":
        pt = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        w, h = screen_size()
        aw, ah = api_size()
        return Outcome(text=f"X={pt.x * aw // w},Y={pt.y * ah // h}")
    if act == "mouse_move":
        if p:
            move(p)
    elif act in ("left_click", "right_click", "double_click", "triple_click"):
        if not p:
            raise ValueError("coordinate required")
        click(p, right=act == "right_click", count={"double_click": 2, "triple_click": 3}.get(act, 1))
    elif act == "left_click_drag":
        start = _pt(a.get("start_coordinate"))
        if not (start and p):
            raise ValueError("start_coordinate and coordinate required")
        drag(start, p)
    elif act == "type":
        type_text(a.get("text", ""))
    elif act == "key":
        press(a.get("text", ""))
    elif act == "scroll":
        if p:
            move(p)
        scroll(a.get("scroll_direction", "down"), int(a.get("scroll_amount", 3)))
    elif act == "wait":
        time.sleep(float(a.get("duration", 1)))
    else:
        raise ValueError(f"Unsupported action: {act}")
    time.sleep(0.5)
    return Outcome(image=screenshot(), target=p)


APPS = {
    "google chrome": "chrome", "chrome": "chrome", "edge": "msedge", "microsoft edge": "msedge", "firefox": "firefox",
    "notepad": "notepad", "file explorer": "explorer", "explorer": "explorer", "calculator": "calc", "paint": "mspaint",
    "word": "winword", "excel": "excel", "powerpoint": "powerpnt", "terminal": "wt", "command prompt": "cmd",
    "task manager": "taskmgr", "settings": "ms-settings:", "vs code": "code", "visual studio code": "code",
    "spotify": "spotify", "discord": "discord", "steam": "steam",
}


def open_app(name: str) -> bool:
    if not IS_WIN:
        return False
    target = APPS.get(name.strip().lower(), name.strip())
    for t in (target, target + ".exe"):
        try:
            os.startfile(t)  # type: ignore[attr-defined]
            return True
        except OSError:
            continue
    return False

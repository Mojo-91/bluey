"""Small settings file (%APPDATA%\\Bluey\\config.json): the pairing code, plus start-with-Windows."""
from __future__ import annotations

import json
import os
import secrets
import sys
from pathlib import Path


def _dir() -> Path:
    d = Path(os.environ.get("APPDATA") or Path.home() / ".config") / "Bluey"
    d.mkdir(parents=True, exist_ok=True)
    return d


def log_path() -> Path:
    return _dir() / "bluey.log"


def _load() -> dict:
    try:
        return json.loads((_dir() / "config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save(d: dict) -> None:
    (_dir() / "config.json").write_text(json.dumps(d), encoding="utf-8")


def new_code() -> str:
    code = f"{secrets.randbelow(10**6):06d}"
    d = _load()
    d["code"] = code
    _save(d)
    return code


def pairing_code() -> str:
    return _load().get("code") or new_code()


_RUN = r"Software\Microsoft\Windows\CurrentVersion\Run"


def get_autostart() -> bool:
    if os.name != "nt":
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN) as k:
            winreg.QueryValueEx(k, "Bluey")
            return True
    except OSError:
        return False


def set_autostart(on: bool) -> None:
    if os.name != "nt" or not getattr(sys, "frozen", False):
        return
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, "Bluey", 0, winreg.REG_SZ, f'"{sys.executable}"')
        else:
            try:
                winreg.DeleteValue(k, "Bluey")
            except FileNotFoundError:
                pass

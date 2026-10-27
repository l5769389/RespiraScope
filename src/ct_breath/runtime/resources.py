"""Locate bundled resources identically in source, wheel and frozen installs."""
import sys
from pathlib import Path


def web_root() -> Path:
    if getattr(sys, 'frozen', False) and getattr(sys, '_MEIPASS', None):
        return Path(sys._MEIPASS) / 'ct_breath' / 'web'
    return Path(__file__).resolve().parents[1] / 'web'

"""CLI command groups for disco."""

from .ocd import ocd
from .cpu import cpu
from .mem import mem
from .flash import flash
from .serial import serial
from .repl import repl
from .doctor import doctor
from .quickstart import quickstart
from .cables import cables
from .check import check
from .power import power
from .ui import ui

__all__ = [
    "ocd", "cpu", "mem", "flash", "serial", "repl",
    "doctor", "quickstart", "cables", "check", "power", "ui",
]

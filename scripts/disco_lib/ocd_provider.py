"""Centralized OpenOCD instance provider with test support."""

from contextlib import contextmanager
from typing import Generator, Optional, Protocol, runtime_checkable


@runtime_checkable
class OCDProtocol(Protocol):
    """Protocol for OCD-like objects (real or mock)."""

    def send(self, cmd: str, timeout: float = 2.0) -> str: ...
    def is_running(self) -> bool: ...
    def ensure_running(self) -> Generator["OCDProtocol", None, None]: ...
    def start(self) -> bool: ...
    def stop(self) -> None: ...


_instance: Optional[OCDProtocol] = None


def get_ocd() -> OCDProtocol:
    """Get shared OpenOCD instance (lazy init)."""
    global _instance
    if _instance is None:
        from .openocd import OpenOCD
        _instance = OpenOCD()
    return _instance


def set_ocd(ocd: OCDProtocol) -> None:
    """Inject OCD instance (for testing)."""
    global _instance
    _instance = ocd


def reset_ocd() -> None:
    """Reset to None (test cleanup)."""
    global _instance
    _instance = None


@contextmanager
def with_ocd() -> Generator[OCDProtocol, None, None]:
    """Get OCD instance, ensuring it's running.

    Convenience function combining get_ocd() with ensure_running() context manager.
    Auto-starts OpenOCD if not running, stops it on exit if we started it.

    Usage:
        from disco_lib.ocd_provider import with_ocd

        with with_ocd() as ocd:
            result = ocd.send("reg pc")

    Yields:
        OCDProtocol instance ready to use.
    """
    ocd = get_ocd()
    with ocd.ensure_running():
        yield ocd

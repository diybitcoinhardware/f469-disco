"""Centralized OpenOCD instance provider with test support."""

from typing import Optional, Protocol, runtime_checkable


@runtime_checkable
class OCDProtocol(Protocol):
    """Protocol for OCD-like objects (real or mock)."""

    def send(self, cmd: str, timeout: float = 2.0) -> str: ...
    def is_running(self) -> bool: ...
    def require_running(self) -> None: ...
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

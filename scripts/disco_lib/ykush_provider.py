"""Centralized YKUSH instance provider with test support."""

from typing import Optional, Protocol, runtime_checkable


@runtime_checkable
class YkushProtocol(Protocol):
    """Protocol for YKUSH-like objects (real or mock)."""

    def list_devices(self) -> list[str]: ...
    def select_device(self) -> str: ...
    def get_port_status(self, port: int) -> bool: ...
    def power_up(self, port: int | str) -> str: ...
    def power_down(self, port: int | str) -> str: ...
    def power_cycle(self, port: int | str, delay: float) -> str: ...


_instance: Optional[YkushProtocol] = None


def get_ykush(serial: Optional[str] = None) -> YkushProtocol:
    """Get YKUSH instance.

    Unlike OCD provider, YKUSH instances may differ based on serial number.
    If a mock is injected, it takes precedence.

    Args:
        serial: Optional serial number to target specific device.

    Returns:
        YKUSH controller instance.
    """
    global _instance
    if _instance is not None:
        return _instance
    from .ykush import Ykush

    return Ykush(serial=serial)


def set_ykush(ykush: YkushProtocol) -> None:
    """Inject YKUSH instance (for testing)."""
    global _instance
    _instance = ykush


def reset_ykush() -> None:
    """Reset to None (test cleanup)."""
    global _instance
    _instance = None

"""Mock YKUSH for testing."""

from typing import Optional


class YkushMock:
    """Mock YKUSH that tracks commands and simulates port states.

    Usage:
        mock = YkushMock()
        mock.add_device("YK12345")
        set_ykush(mock)
        # ... run command ...
        assert mock.commands  # Check what was called
    """

    def __init__(self, serial: Optional[str] = None):
        """Initialize mock.

        Args:
            serial: Simulated serial number selection.
        """
        self._serial = serial
        self._devices: list[str] = []
        self._port_states: dict[int, bool] = {1: True, 2: True, 3: True}
        self._commands: list[str] = []
        self._raise_not_found = False
        self._raise_no_devices = False

    def add_device(self, serial: str) -> "YkushMock":
        """Add a simulated device."""
        self._devices.append(serial)
        return self

    def set_port_state(self, port: int, is_on: bool) -> "YkushMock":
        """Set simulated port state."""
        self._port_states[port] = is_on
        return self

    def raise_not_found(self) -> "YkushMock":
        """Simulate ykushcmd not installed."""
        self._raise_not_found = True
        return self

    def raise_no_devices(self) -> "YkushMock":
        """Simulate no devices connected."""
        self._raise_no_devices = True
        return self

    @property
    def commands(self) -> list[str]:
        """List of commands that were called."""
        return self._commands.copy()

    @property
    def port_states(self) -> dict[int, bool]:
        """Current simulated port states."""
        return self._port_states.copy()

    def list_devices(self) -> list[str]:
        """Return simulated device list."""
        self._commands.append("list_devices")
        if self._raise_not_found:
            from disco_lib.ykush import YkushNotFoundError

            raise YkushNotFoundError("ykushcmd not found")
        return self._devices.copy()

    def select_device(self) -> str:
        """Return simulated device selection."""
        self._commands.append("select_device")
        if self._raise_not_found:
            from disco_lib.ykush import YkushNotFoundError

            raise YkushNotFoundError("ykushcmd not found")
        if self._raise_no_devices or not self._devices:
            from disco_lib.ykush import YkushNoDevicesError

            raise YkushNoDevicesError("No YKUSH devices found")
        if self._serial and self._serial in self._devices:
            return self._serial
        if len(self._devices) > 1:
            from disco_lib.ykush import YkushError

            raise YkushError(
                f"Multiple YKUSH devices found: {', '.join(self._devices)}. "
                f"Use --serial to specify which one."
            )
        return self._devices[0]

    def get_port_status(self, port: int) -> bool:
        """Return simulated port status."""
        self._commands.append(f"get_port_status({port})")
        if self._raise_not_found:
            from disco_lib.ykush import YkushNotFoundError

            raise YkushNotFoundError("ykushcmd not found")
        return self._port_states.get(port, True)

    def get_all_status(self):
        """Return simulated status for all ports."""
        self._commands.append("get_all_status")
        if self._raise_not_found:
            from disco_lib.ykush import YkushNotFoundError

            raise YkushNotFoundError("ykushcmd not found")
        if self._raise_no_devices or not self._devices:
            from disco_lib.ykush import YkushNoDevicesError

            raise YkushNoDevicesError("No YKUSH devices found")

        from disco_lib.ykush import DeviceStatus, PortStatus

        serial = self._serial if self._serial in self._devices else self._devices[0]
        ports = [
            PortStatus(port=p, is_on=self._port_states.get(p, True)) for p in (1, 2, 3)
        ]
        return DeviceStatus(serial=serial, ports=ports)

    def power_up(self, port: int | str = "all") -> str:
        """Simulate power up."""
        self._commands.append(f"power_up({port})")
        if self._raise_not_found:
            from disco_lib.ykush import YkushNotFoundError

            raise YkushNotFoundError("ykushcmd not found")
        if port == "all":
            for p in (1, 2, 3):
                self._port_states[p] = True
        else:
            self._port_states[int(port)] = True
        return f"Port {port} powered up"

    def power_down(self, port: int | str = "all") -> str:
        """Simulate power down."""
        self._commands.append(f"power_down({port})")
        if self._raise_not_found:
            from disco_lib.ykush import YkushNotFoundError

            raise YkushNotFoundError("ykushcmd not found")
        if port == "all":
            for p in (1, 2, 3):
                self._port_states[p] = False
        else:
            self._port_states[int(port)] = False
        return f"Port {port} powered down"

    def power_cycle(self, port: int | str = "all", delay: float = 2.0) -> str:
        """Simulate power cycle."""
        self._commands.append(f"power_cycle({port}, {delay})")
        if self._raise_not_found:
            from disco_lib.ykush import YkushNotFoundError

            raise YkushNotFoundError("ykushcmd not found")
        # After cycle, ports should be on
        if port == "all":
            for p in (1, 2, 3):
                self._port_states[p] = True
        else:
            self._port_states[int(port)] = True
        return f"Port {port} power cycled"

    @staticmethod
    def is_available() -> bool:
        """Mock always returns True unless configured otherwise."""
        return True

    def reset_state(self) -> None:
        """Reset all tracking state."""
        self._commands.clear()
        self._port_states = {1: True, 2: True, 3: True}
        self._raise_not_found = False
        self._raise_no_devices = False

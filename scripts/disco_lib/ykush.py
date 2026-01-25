"""YKUSH USB power hub control backend."""

import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from typing import Optional


class YkushError(Exception):
    """Base exception for YKUSH operations."""

    pass


class YkushNotFoundError(YkushError):
    """Raised when ykushcmd is not installed."""

    pass


class YkushNoDevicesError(YkushError):
    """Raised when no YKUSH devices are found."""

    pass


class YkushInvalidPortError(YkushError):
    """Raised when an invalid port is specified."""

    pass


@dataclass
class PortStatus:
    """Status of a single YKUSH port."""

    port: int
    is_on: bool


@dataclass
class DeviceStatus:
    """Status of a YKUSH device with all its ports."""

    serial: str
    ports: list[PortStatus]


class Ykush:
    """Wrapper for ykushcmd subprocess calls.

    Provides control over YKUSH USB power hubs for power cycling
    connected USB devices like the STM32F469 Discovery board.
    """

    VALID_PORTS = (1, 2, 3, "all")
    DEFAULT_CYCLE_DELAY = 2.0  # seconds

    def __init__(self, serial: Optional[str] = None):
        """Initialize YKUSH controller.

        Args:
            serial: Target a specific YKUSH device by serial number.
                   If None, auto-detects (fails if multiple devices found).
        """
        self._serial = serial

    @staticmethod
    def is_available() -> bool:
        """Check if ykushcmd is installed and available."""
        return shutil.which("ykushcmd") is not None

    @staticmethod
    def _run_cmd(args: list[str], timeout: float = 5.0) -> str:
        """Run ykushcmd with given arguments.

        Returns:
            Command output (stdout + stderr combined).

        Raises:
            YkushNotFoundError: If ykushcmd is not installed.
            YkushError: If command fails.
        """
        if not Ykush.is_available():
            raise YkushNotFoundError(
                "ykushcmd not found. Install from https://www.yepkit.com/ "
                "or manually unplug/replug USB cables."
            )

        try:
            result = subprocess.run(
                ["ykushcmd"] + args,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            # Combine stdout and stderr - ykushcmd may output to either
            output = result.stdout + result.stderr
            return output.strip()
        except subprocess.TimeoutExpired as e:
            raise YkushError(f"ykushcmd timed out: {e}")
        except subprocess.SubprocessError as e:
            raise YkushError(f"ykushcmd failed: {e}")

    def list_devices(self) -> list[str]:
        """List all connected YKUSH device serial numbers.

        Returns:
            List of serial numbers.

        Raises:
            YkushNotFoundError: If ykushcmd is not installed.
        """
        output = self._run_cmd(["-l"])
        return self._parse_device_list(output)

    @staticmethod
    def _parse_device_list(output: str) -> list[str]:
        """Parse device serial numbers from 'ykushcmd -l' output.

        Expected output format:
            Attached YKUSH Boards:
            1. Board found with serial number: YK12345

        Or for no devices:
            No YKUSH boards found.
        """
        serials = []
        # Match serial number pattern - alphanumeric after "serial number:"
        for match in re.finditer(r"serial number:\s*(\S+)", output, re.IGNORECASE):
            serials.append(match.group(1))
        return serials

    def select_device(self) -> str:
        """Get the target device serial number.

        If serial was provided at init, validates it exists.
        If not provided, auto-detects single device.

        Returns:
            Serial number of target device.

        Raises:
            YkushNoDevicesError: If no devices found.
            YkushError: If multiple devices and no serial specified.
        """
        devices = self.list_devices()

        if not devices:
            raise YkushNoDevicesError(
                "No YKUSH devices found. Check USB connection or manually power cycle."
            )

        if self._serial:
            if self._serial not in devices:
                raise YkushError(
                    f"YKUSH device '{self._serial}' not found. "
                    f"Available devices: {', '.join(devices)}"
                )
            return self._serial

        if len(devices) == 1:
            return devices[0]

        raise YkushError(
            f"Multiple YKUSH devices found: {', '.join(devices)}. "
            f"Use --serial to specify which one."
        )

    def _validate_port(self, port: int | str) -> None:
        """Validate port argument.

        Raises:
            YkushInvalidPortError: If port is not 1, 2, 3, or 'all'.
        """
        if port not in self.VALID_PORTS:
            raise YkushInvalidPortError(
                f"Invalid port '{port}'. Must be 1, 2, 3, or 'all'."
            )

    def _get_serial_args(self) -> list[str]:
        """Get serial number args for ykushcmd if specified."""
        if self._serial:
            return ["-s", self._serial]
        return []

    def get_port_status(self, port: int) -> bool:
        """Get status of a specific port.

        Args:
            port: Port number (1, 2, or 3).

        Returns:
            True if port is ON, False if OFF.

        Raises:
            YkushInvalidPortError: If port is not 1, 2, or 3.
        """
        if port not in (1, 2, 3):
            raise YkushInvalidPortError(
                f"Invalid port '{port}'. Must be 1, 2, or 3."
            )

        args = self._get_serial_args() + ["-g", str(port)]
        output = self._run_cmd(args)
        return self._parse_port_status(output, port)

    @staticmethod
    def _parse_port_status(output: str, port: int) -> bool:
        """Parse port status from ykushcmd output.

        Expected format: "Downstream port N is ON" or "Downstream port N is OFF"
        """
        # Look for ON/OFF status for the specific port
        pattern = rf"port\s+{port}\s+is\s+(ON|OFF)"
        match = re.search(pattern, output, re.IGNORECASE)
        if match:
            return match.group(1).upper() == "ON"
        # Default to ON if we can't parse (safer assumption)
        return True

    def get_all_status(self) -> DeviceStatus:
        """Get status of all ports on the target device.

        Returns:
            DeviceStatus with serial and port states.
        """
        serial = self.select_device()
        ports = []
        for port_num in (1, 2, 3):
            is_on = self.get_port_status(port_num)
            ports.append(PortStatus(port=port_num, is_on=is_on))
        return DeviceStatus(serial=serial, ports=ports)

    def power_up(self, port: int | str = "all") -> str:
        """Power up port(s).

        Args:
            port: Port number (1, 2, 3) or 'all'.

        Returns:
            Command output.
        """
        self._validate_port(port)
        if port == "all":
            args = self._get_serial_args() + ["-u", "a"]
        else:
            args = self._get_serial_args() + ["-u", str(port)]
        return self._run_cmd(args)

    def power_down(self, port: int | str = "all") -> str:
        """Power down port(s).

        Args:
            port: Port number (1, 2, 3) or 'all'.

        Returns:
            Command output.
        """
        self._validate_port(port)
        if port == "all":
            args = self._get_serial_args() + ["-d", "a"]
        else:
            args = self._get_serial_args() + ["-d", str(port)]
        return self._run_cmd(args)

    def power_cycle(
        self, port: int | str = "all", delay: float = DEFAULT_CYCLE_DELAY
    ) -> str:
        """Power cycle port(s) with delay.

        Args:
            port: Port number (1, 2, 3) or 'all'.
            delay: Seconds to wait between power off and on.

        Returns:
            Combined command output.
        """
        self._validate_port(port)
        output_parts = []
        output_parts.append(self.power_down(port))
        time.sleep(delay)
        output_parts.append(self.power_up(port))
        return "\n".join(filter(None, output_parts))

"""Tests for YKUSH USB power hub control.

Tests cover:
  - Device listing and selection
  - Port status parsing
  - Power operations (up, down, cycle)
  - Error handling (not found, no devices, invalid port)
  - Provider pattern (get/set/reset)
"""

import pytest
from unittest.mock import patch, MagicMock

from disco_lib.ykush import (
    Ykush,
    YkushError,
    YkushNotFoundError,
    YkushNoDevicesError,
    YkushInvalidPortError,
    PortStatus,
    DeviceStatus,
)
from disco_lib.ykush_provider import (
    get_ykush,
    set_ykush,
    reset_ykush,
    YkushProtocol,
)
from disco_lib.tests.mocks import YkushMock


@pytest.fixture(autouse=True)
def reset_global_state():
    """Reset global YKUSH instance before and after each test."""
    reset_ykush()
    yield
    reset_ykush()


class TestYkushIsAvailable:
    """Tests for Ykush.is_available() - check if ykushcmd is installed."""

    def test_returns_true_when_found(self):
        """Should return True when ykushcmd is in PATH."""
        with patch("disco_lib.ykush.shutil.which") as mock_which:
            mock_which.return_value = "/usr/bin/ykushcmd"
            assert Ykush.is_available() is True

    def test_returns_false_when_not_found(self):
        """Should return False when ykushcmd is not in PATH."""
        with patch("disco_lib.ykush.shutil.which") as mock_which:
            mock_which.return_value = None
            assert Ykush.is_available() is False


class TestYkushListDevices:
    """Tests for Ykush.list_devices() - enumerate connected devices."""

    def test_parses_single_device(self):
        """Should parse single device serial number."""
        output = """Attached YKUSH Boards:
1. Board found with serial number: YK12345"""
        serials = Ykush._parse_device_list(output)
        assert serials == ["YK12345"]

    def test_parses_multiple_devices(self):
        """Should parse multiple device serial numbers."""
        output = """Attached YKUSH Boards:
1. Board found with serial number: YK12345
2. Board found with serial number: YK67890"""
        serials = Ykush._parse_device_list(output)
        assert serials == ["YK12345", "YK67890"]

    def test_parses_empty_list(self):
        """Should return empty list when no devices."""
        output = "No YKUSH boards found."
        serials = Ykush._parse_device_list(output)
        assert serials == []

    def test_handles_varied_output_format(self):
        """Should handle different output formats."""
        # Some versions may have different capitalization
        output = "Serial Number: ABC123"
        serials = Ykush._parse_device_list(output)
        assert serials == ["ABC123"]

    def test_raises_not_found_when_cmd_missing(self):
        """Should raise YkushNotFoundError when ykushcmd not installed."""
        with patch("disco_lib.ykush.shutil.which") as mock_which:
            mock_which.return_value = None
            ykush = Ykush()
            with pytest.raises(YkushNotFoundError) as exc_info:
                ykush.list_devices()
            assert "ykushcmd not found" in str(exc_info.value)
            assert "https://www.yepkit.com/" in str(exc_info.value)


class TestYkushSelectDevice:
    """Tests for Ykush.select_device() - device selection logic."""

    def test_auto_selects_single_device(self):
        """Should auto-select when only one device connected."""
        mock = YkushMock()
        mock.add_device("YK12345")
        set_ykush(mock)

        ykush = get_ykush()
        serial = ykush.select_device()
        assert serial == "YK12345"

    def test_raises_error_for_multiple_devices_without_serial(self):
        """Should require --serial when multiple devices present."""
        mock = YkushMock()
        mock.add_device("YK12345")
        mock.add_device("YK67890")
        set_ykush(mock)

        ykush = get_ykush()
        with pytest.raises(YkushError) as exc_info:
            ykush.select_device()
        assert "Multiple YKUSH devices" in str(exc_info.value)
        assert "--serial" in str(exc_info.value)

    def test_uses_specified_serial(self):
        """Should use serial number when provided."""
        mock = YkushMock(serial="YK67890")
        mock.add_device("YK12345")
        mock.add_device("YK67890")
        set_ykush(mock)

        ykush = get_ykush()
        serial = ykush.select_device()
        assert serial == "YK67890"

    def test_raises_no_devices_error(self):
        """Should raise clear error when no devices found."""
        mock = YkushMock()
        mock.raise_no_devices()
        set_ykush(mock)

        ykush = get_ykush()
        with pytest.raises(YkushNoDevicesError) as exc_info:
            ykush.select_device()
        assert "No YKUSH devices found" in str(exc_info.value)


class TestYkushPortStatus:
    """Tests for port status parsing and retrieval."""

    def test_parses_port_on(self):
        """Should parse 'Downstream port N is ON'."""
        output = "Downstream port 1 is ON"
        assert Ykush._parse_port_status(output, 1) is True

    def test_parses_port_off(self):
        """Should parse 'Downstream port N is OFF'."""
        output = "Downstream port 2 is OFF"
        assert Ykush._parse_port_status(output, 2) is False

    def test_case_insensitive(self):
        """Should handle case variations."""
        assert Ykush._parse_port_status("PORT 1 IS on", 1) is True
        assert Ykush._parse_port_status("port 1 is OFF", 1) is False

    def test_defaults_to_on_for_unknown(self):
        """Should default to ON for unparseable output (safer)."""
        output = "Some unexpected output"
        assert Ykush._parse_port_status(output, 1) is True

    def test_invalid_port_raises_error(self):
        """Should raise error for invalid port number."""
        mock = YkushMock()
        mock.add_device("YK12345")
        set_ykush(mock)

        ykush = get_ykush()
        # Mock doesn't validate ports, but real Ykush does
        # Test the validation method directly
        real_ykush = Ykush()
        with pytest.raises(YkushInvalidPortError):
            real_ykush._validate_port(4)
        with pytest.raises(YkushInvalidPortError):
            real_ykush._validate_port(0)
        with pytest.raises(YkushInvalidPortError):
            real_ykush._validate_port("invalid")


class TestYkushPowerOperations:
    """Tests for power up/down/cycle operations."""

    def test_power_up_single_port(self, ykush_mock):
        """Should call correct ykushcmd args for single port."""
        ykush = get_ykush()
        ykush.power_up(1)
        assert "power_up(1)" in ykush_mock.commands
        assert ykush_mock.port_states[1] is True

    def test_power_up_all_ports(self, ykush_mock):
        """Should call correct ykushcmd args for all ports."""
        ykush = get_ykush()
        ykush.power_up("all")
        assert "power_up(all)" in ykush_mock.commands

    def test_power_down_single_port(self, ykush_mock):
        """Should call correct ykushcmd args for power down."""
        ykush = get_ykush()
        ykush.power_down(2)
        assert "power_down(2)" in ykush_mock.commands
        assert ykush_mock.port_states[2] is False

    def test_power_down_all_ports(self, ykush_mock):
        """Should call correct ykushcmd args for all ports."""
        ykush = get_ykush()
        ykush.power_down("all")
        assert "power_down(all)" in ykush_mock.commands
        for port in (1, 2, 3):
            assert ykush_mock.port_states[port] is False

    def test_power_cycle_includes_delay(self, ykush_mock):
        """Should power down, wait, then power up."""
        ykush = get_ykush()
        ykush.power_cycle(1, delay=0.1)
        assert "power_cycle(1, 0.1)" in ykush_mock.commands
        # After cycle, port should be on
        assert ykush_mock.port_states[1] is True

    def test_power_cycle_default_all_ports(self, ykush_mock):
        """Should default to all ports."""
        ykush = get_ykush()
        ykush.power_cycle("all", delay=0.1)
        assert "power_cycle(all, 0.1)" in ykush_mock.commands

    def test_invalid_port_raises_error(self):
        """Should raise error for invalid port."""
        ykush = Ykush()
        with pytest.raises(YkushInvalidPortError) as exc_info:
            ykush._validate_port(5)
        assert "Invalid port" in str(exc_info.value)
        assert "1, 2, 3, or 'all'" in str(exc_info.value)


class TestYkushProvider:
    """Tests for ykush_provider module - dependency injection pattern."""

    def test_get_returns_real_instance_by_default(self):
        """get_ykush() should return Ykush instance when no mock set."""
        reset_ykush()
        ykush = get_ykush()
        # Can't use isinstance with Protocol directly, check for key method
        assert hasattr(ykush, "list_devices")
        assert hasattr(ykush, "power_up")

    def test_set_injects_mock(self):
        """set_ykush() should replace the singleton."""
        mock = YkushMock()
        set_ykush(mock)
        assert get_ykush() is mock

    def test_reset_clears_mock(self):
        """reset_ykush() should clear injected mock."""
        mock = YkushMock()
        set_ykush(mock)
        reset_ykush()
        # Next get should return a new real instance
        new_ykush = get_ykush()
        assert new_ykush is not mock

    def test_protocol_is_runtime_checkable(self):
        """YkushProtocol should be usable with isinstance()."""
        mock = YkushMock()
        assert isinstance(mock, YkushProtocol)


class TestYkushMock:
    """Tests for YkushMock test helper."""

    def test_tracks_commands(self):
        """Should track all commands called."""
        mock = YkushMock()
        mock.add_device("YK12345")
        mock.list_devices()
        mock.power_up(1)
        mock.power_down(2)

        assert "list_devices" in mock.commands
        assert "power_up(1)" in mock.commands
        assert "power_down(2)" in mock.commands

    def test_simulates_port_states(self):
        """Should update and track port states."""
        mock = YkushMock()
        mock.add_device("YK12345")
        mock.set_port_state(1, False)

        assert mock.port_states[1] is False
        mock.power_up(1)
        assert mock.port_states[1] is True

    def test_simulates_not_found(self):
        """Should simulate ykushcmd not installed."""
        mock = YkushMock()
        mock.raise_not_found()

        with pytest.raises(YkushNotFoundError):
            mock.list_devices()

    def test_simulates_no_devices(self):
        """Should simulate no devices connected."""
        mock = YkushMock()
        mock.raise_no_devices()

        with pytest.raises(YkushNoDevicesError):
            mock.select_device()

    def test_reset_state(self):
        """Should reset all tracking state."""
        mock = YkushMock()
        mock.add_device("YK12345")
        mock.power_down("all")
        mock.reset_state()

        assert mock.commands == []
        assert all(mock.port_states[p] is True for p in (1, 2, 3))


class TestYkushGetAllStatus:
    """Tests for getting status of all ports."""

    def test_returns_device_status(self, ykush_mock):
        """Should return DeviceStatus with all port states."""
        ykush_mock.set_port_state(1, True)
        ykush_mock.set_port_state(2, False)
        ykush_mock.set_port_state(3, True)

        ykush = get_ykush()
        status = ykush.get_all_status()

        assert status.serial == "YK12345"
        assert len(status.ports) == 3
        assert status.ports[0].port == 1
        assert status.ports[0].is_on is True
        assert status.ports[1].port == 2
        assert status.ports[1].is_on is False
        assert status.ports[2].port == 3
        assert status.ports[2].is_on is True


class TestYkushRunCmd:
    """Tests for ykushcmd subprocess execution."""

    def test_raises_not_found_when_cmd_missing(self):
        """Should raise clear error when ykushcmd not available."""
        with patch("disco_lib.ykush.shutil.which") as mock_which:
            mock_which.return_value = None
            with pytest.raises(YkushNotFoundError) as exc_info:
                Ykush._run_cmd(["-l"])
            assert "ykushcmd not found" in str(exc_info.value)
            assert "https://www.yepkit.com/" in str(exc_info.value)
            assert "manually unplug/replug" in str(exc_info.value)

    def test_returns_combined_output(self):
        """Should combine stdout and stderr."""
        with patch("disco_lib.ykush.shutil.which") as mock_which, \
             patch("disco_lib.ykush.subprocess.run") as mock_run:
            mock_which.return_value = "/usr/bin/ykushcmd"
            mock_run.return_value = MagicMock(
                stdout="stdout content",
                stderr="stderr content"
            )
            result = Ykush._run_cmd(["-l"])
            assert "stdout content" in result
            assert "stderr content" in result

    def test_handles_timeout(self):
        """Should raise YkushError on timeout."""
        import subprocess
        with patch("disco_lib.ykush.shutil.which") as mock_which, \
             patch("disco_lib.ykush.subprocess.run") as mock_run:
            mock_which.return_value = "/usr/bin/ykushcmd"
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="ykushcmd", timeout=5)
            with pytest.raises(YkushError) as exc_info:
                Ykush._run_cmd(["-l"])
            assert "timed out" in str(exc_info.value)

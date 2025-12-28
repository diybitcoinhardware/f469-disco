"""Tests for serial.py backend."""

from unittest.mock import MagicMock, patch

import click
import pytest
import serial

from disco_lib.serial import SerialDevice


class TestIsBlacklisted:
    """Tests for blacklist filtering."""

    def test_matches_pattern(self):
        ser = SerialDevice(blacklist=["004NTKF"])
        assert ser.is_blacklisted("/dev/tty.usbmodem004NTKF4H9492") is True

    def test_no_match(self):
        ser = SerialDevice(blacklist=["004NTKF"])
        assert ser.is_blacklisted("/dev/tty.usbmodem335D375F33382") is False

    def test_empty_blacklist(self):
        ser = SerialDevice(blacklist=[])
        # With empty blacklist, even default-blacklisted patterns should pass
        # Use a path that WOULD match default blacklist (004NTKF)
        assert ser.is_blacklisted("/dev/tty.usbmodem004NTKF4H9492") is False
        assert ser.blacklist == []  # Verify empty list is stored

    def test_multiple_patterns(self):
        ser = SerialDevice(blacklist=["004NTKF", "BADDEV"])
        assert ser.is_blacklisted("/dev/tty.usbmodemBADDEV123") is True
        assert ser.is_blacklisted("/dev/tty.usbmodem004NTKF123") is True
        assert ser.is_blacklisted("/dev/tty.usbmodemGOOD123") is False


class TestListDevices:
    """Tests for device listing."""

    def test_empty_when_no_devices(self, mock_glob):
        mock_glob.return_value = []
        ser = SerialDevice()
        devices = ser.list_devices()
        assert devices == []

    def test_only_tty_devices(self, mock_glob):
        """Should only glob tty.*, not cu.*"""
        mock_glob.return_value = []
        ser = SerialDevice()
        ser.list_devices()

        # Should only call glob once with tty pattern
        mock_glob.assert_called_once_with("/dev/tty.usbmodem*")

    def test_filters_blacklist(self, mock_glob):
        mock_glob.return_value = [
            "/dev/tty.usbmodem335D375F33382",
            "/dev/tty.usbmodem004NTKF4H9492",
            "/dev/tty.usbmodem21403",
        ]
        ser = SerialDevice(blacklist=["004NTKF"])
        devices = ser.list_devices()

        # Should have 3 devices, one marked as blacklisted
        assert len(devices) == 3
        blacklisted = [path for path, bl in devices if bl]
        assert len(blacklisted) == 1
        assert "004NTKF" in blacklisted[0]

    def test_sorted_by_length_descending(self, mock_glob):
        """Longer IDs (USB OTG) should come first."""
        mock_glob.return_value = [
            "/dev/tty.usbmodem21403",  # Short (ST-LINK)
            "/dev/tty.usbmodem335D375F33382",  # Long (USB OTG)
        ]
        ser = SerialDevice(blacklist=[])
        devices = ser.list_devices()

        # Longer path should be first
        assert "335D375F33382" in devices[0][0]
        assert "21403" in devices[1][0]


class TestAutoDetect:
    """Tests for auto device detection."""

    def test_env_override(self, mock_glob, monkeypatch):
        """SERIAL_DEV env should override auto-detection."""
        monkeypatch.setenv("SERIAL_DEV", "/dev/tty.custom")

        with patch("os.path.exists", return_value=True):
            ser = SerialDevice()
            result = ser.auto_detect()
            assert result == "/dev/tty.custom"

    def test_env_override_missing_file(self, mock_glob, monkeypatch, capsys):
        """SERIAL_DEV with non-existent file returns None."""
        monkeypatch.setenv("SERIAL_DEV", "/dev/tty.nonexistent")

        with patch("os.path.exists", return_value=False):
            ser = SerialDevice()
            result = ser.auto_detect()
            assert result is None

    def test_prefers_usb_otg(self, mock_glob, monkeypatch):
        """Should prefer USB OTG (longer ID) over ST-LINK."""
        monkeypatch.delenv("SERIAL_DEV", raising=False)
        mock_glob.return_value = [
            "/dev/tty.usbmodem21403",
            "/dev/tty.usbmodem335D375F33382",
        ]

        ser = SerialDevice(blacklist=[])
        result = ser.auto_detect()

        # Should pick the longer one (USB OTG)
        assert "335D375F33382" in result

    def test_skips_blacklisted(self, mock_glob, monkeypatch):
        """Should skip blacklisted devices."""
        monkeypatch.delenv("SERIAL_DEV", raising=False)
        mock_glob.return_value = [
            "/dev/tty.usbmodem004NTKF123",  # Blacklisted
            "/dev/tty.usbmodem21403",  # OK
        ]

        ser = SerialDevice(blacklist=["004NTKF"])
        result = ser.auto_detect()

        assert "21403" in result

    def test_returns_none_when_all_blacklisted(self, mock_glob, monkeypatch):
        """Returns None if all devices are blacklisted."""
        monkeypatch.delenv("SERIAL_DEV", raising=False)
        mock_glob.return_value = [
            "/dev/tty.usbmodem004NTKF123",
        ]

        ser = SerialDevice(blacklist=["004NTKF"])
        result = ser.auto_detect()

        assert result is None


class TestReplTest:
    """Tests for REPL wake and test."""

    def test_sends_wake_sequence(self, mock_serial):
        """Should send Ctrl-C and newlines."""
        mock_ser_instance = MagicMock()
        mock_serial.return_value.__enter__ = MagicMock(return_value=mock_ser_instance)
        mock_serial.return_value.__exit__ = MagicMock(return_value=False)
        mock_ser_instance.read.return_value = b">>> "

        ser = SerialDevice()
        ser.repl_test("/dev/tty.test", 3)

        # Check write calls
        writes = mock_ser_instance.write.call_args_list
        assert len(writes) >= 2

        # First write should be Ctrl-C
        assert b"\x03" in writes[0][0][0]

        # Should have newlines
        all_written = b"".join(call[0][0] for call in writes)
        assert b"\r\n" in all_written

    def test_keeps_connection_open(self, mock_serial):
        """Should use single connection for wake + read."""
        mock_ser_instance = MagicMock()
        mock_serial.return_value.__enter__ = MagicMock(return_value=mock_ser_instance)
        mock_serial.return_value.__exit__ = MagicMock(return_value=False)
        mock_ser_instance.read.return_value = b">>> "

        ser = SerialDevice()
        ser.repl_test("/dev/tty.test", 3)

        # Serial should only be opened once
        assert mock_serial.call_count == 1

    def test_returns_decoded_response(self, mock_serial):
        """Should return decoded string."""
        mock_ser_instance = MagicMock()
        mock_serial.return_value.__enter__ = MagicMock(return_value=mock_ser_instance)
        mock_serial.return_value.__exit__ = MagicMock(return_value=False)
        mock_ser_instance.read.return_value = b">>> hello\n"

        ser = SerialDevice()
        result = ser.repl_test("/dev/tty.test", 3)

        assert result == ">>> hello\n"

    def test_returns_none_on_empty(self, mock_serial):
        """Should return None if no data."""
        mock_ser_instance = MagicMock()
        mock_serial.return_value.__enter__ = MagicMock(return_value=mock_ser_instance)
        mock_serial.return_value.__exit__ = MagicMock(return_value=False)
        mock_ser_instance.read.return_value = b""

        ser = SerialDevice()
        result = ser.repl_test("/dev/tty.test", 3)

        assert result is None

    def test_handles_binary_response(self, mock_serial):
        """Should handle non-UTF8 bytes with replacement."""
        mock_ser_instance = MagicMock()
        mock_serial.return_value.__enter__ = MagicMock(return_value=mock_ser_instance)
        mock_serial.return_value.__exit__ = MagicMock(return_value=False)
        mock_ser_instance.read.return_value = b">>> \xff\xfe\x00"

        ser = SerialDevice()
        result = ser.repl_test("/dev/tty.test", 3)

        # Should not crash, uses errors="replace"
        assert result is not None
        assert ">>>" in result

    def test_raises_on_serial_exception(self, mock_serial):
        """Should raise ClickException on serial error."""
        mock_serial.side_effect = serial.SerialException("port busy")

        ser = SerialDevice()
        with pytest.raises(click.ClickException) as exc_info:
            ser.repl_test("/dev/tty.test", 3)

        assert "Serial error" in str(exc_info.value)


class TestRequireDevice:
    """Tests for require_device() - raises if no device found."""

    def test_returns_device_when_found(self, mock_glob, monkeypatch):
        """Should return device path when available."""
        monkeypatch.delenv("SERIAL_DEV", raising=False)
        mock_glob.return_value = ["/dev/tty.usbmodem12345"]

        ser = SerialDevice(blacklist=[])
        result = ser.require_device()

        assert result == "/dev/tty.usbmodem12345"

    def test_raises_when_no_device(self, mock_glob, monkeypatch):
        """Should raise ClickException when no device found."""
        monkeypatch.delenv("SERIAL_DEV", raising=False)
        mock_glob.return_value = []

        ser = SerialDevice()
        with pytest.raises(click.ClickException) as exc_info:
            ser.require_device()

        assert "No USB modem device found" in str(exc_info.value)

    def test_raises_when_all_blacklisted(self, mock_glob, monkeypatch):
        """Should raise when all devices are blacklisted."""
        monkeypatch.delenv("SERIAL_DEV", raising=False)
        mock_glob.return_value = ["/dev/tty.usbmodem004NTKF123"]

        ser = SerialDevice(blacklist=["004NTKF"])
        with pytest.raises(click.ClickException) as exc_info:
            ser.require_device()

        assert "blacklist" in str(exc_info.value).lower()


class TestReadTimeout:
    """Tests for read_timeout() - reads with timeout."""

    def test_returns_decoded_data(self, mock_serial):
        """Should return decoded string."""
        mock_ser_instance = MagicMock()
        mock_serial.return_value.__enter__ = MagicMock(return_value=mock_ser_instance)
        mock_serial.return_value.__exit__ = MagicMock(return_value=False)
        mock_ser_instance.read.return_value = b"test data"

        ser = SerialDevice()
        result = ser.read_timeout("/dev/tty.test", 1.0)

        assert result == "test data"

    def test_raises_on_serial_exception(self, mock_serial):
        """Should raise ClickException on serial error."""
        mock_serial.side_effect = serial.SerialException("device disconnected")

        ser = SerialDevice()
        with pytest.raises(click.ClickException) as exc_info:
            ser.read_timeout("/dev/tty.test", 1.0)

        assert "Serial error" in str(exc_info.value)


class TestIsBlacklistedEdgeCases:
    """Additional edge case tests for is_blacklisted()."""

    def test_case_sensitive_matching(self):
        """Blacklist matching should be case-sensitive."""
        ser = SerialDevice(blacklist=["NTKF"])
        # Uppercase in pattern, lowercase in path - should NOT match
        # (paths are typically consistent case from system)
        assert ser.is_blacklisted("/dev/tty.usbmodemNTKF123") is True
        assert ser.is_blacklisted("/dev/tty.usbmodemntkf123") is False

    def test_partial_match_anywhere(self):
        """Pattern should match anywhere in path."""
        ser = SerialDevice(blacklist=["BAD"])
        assert ser.is_blacklisted("/dev/tty.BADmodem") is True
        assert ser.is_blacklisted("/dev/tty.modemBAD") is True
        assert ser.is_blacklisted("/dev/tty.moBADem") is True

    def test_special_regex_chars_not_interpreted(self):
        """Blacklist patterns should be literal, not regex."""
        # If pattern were regex, ".*" would match everything
        ser = SerialDevice(blacklist=[".*"])
        assert ser.is_blacklisted("/dev/tty.usbmodem123") is False
        assert ser.is_blacklisted("/dev/tty.usbmodem.*456") is True


class TestAutoDetectEdgeCases:
    """Additional edge case tests for auto_detect()."""

    def test_empty_env_var(self, mock_glob, monkeypatch):
        """Empty SERIAL_DEV should fall back to auto-detect."""
        monkeypatch.setenv("SERIAL_DEV", "")
        mock_glob.return_value = ["/dev/tty.usbmodem12345"]

        ser = SerialDevice(blacklist=[])

        with patch("os.path.exists", return_value=False):
            result = ser.auto_detect()

        # Empty string doesn't exist, so should fall back
        # Actually let me check the code - it checks if env_dev is truthy
        # Empty string is falsy, so it should skip to auto-detect
        assert result == "/dev/tty.usbmodem12345"

    def test_no_devices_returns_none(self, mock_glob, monkeypatch):
        """Should return None when no devices available."""
        monkeypatch.delenv("SERIAL_DEV", raising=False)
        mock_glob.return_value = []

        ser = SerialDevice()
        result = ser.auto_detect()

        assert result is None

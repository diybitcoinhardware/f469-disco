"""Tests for openocd.py backend."""

import socket
import pytest
from unittest.mock import MagicMock, patch

import click

from disco_lib.openocd import OpenOCD


class TestIsRunning:
    """Tests for OpenOCD running detection."""

    def test_returns_true_when_connected(self, mock_socket):
        """Should return True when socket connects."""
        mock_socket.return_value.__enter__ = MagicMock()
        mock_socket.return_value.__exit__ = MagicMock(return_value=False)

        ocd = OpenOCD()
        assert ocd.is_running() is True

    def test_returns_false_on_connection_refused(self, mock_socket):
        """Should return False when connection refused."""
        mock_socket.side_effect = ConnectionRefusedError()

        ocd = OpenOCD()
        assert ocd.is_running() is False

    def test_returns_false_on_timeout(self, mock_socket):
        """Should return False on socket timeout."""
        mock_socket.side_effect = socket.timeout()

        ocd = OpenOCD()
        assert ocd.is_running() is False

    def test_returns_false_on_os_error(self, mock_socket):
        """Should return False on general OS error."""
        mock_socket.side_effect = OSError("Network unreachable")

        ocd = OpenOCD()
        assert ocd.is_running() is False

    def test_uses_correct_port(self, mock_socket):
        """Should connect to configured port."""
        mock_socket.return_value.__enter__ = MagicMock()
        mock_socket.return_value.__exit__ = MagicMock(return_value=False)

        ocd = OpenOCD(port=4444)
        ocd.is_running()

        mock_socket.assert_called_once()
        call_args = mock_socket.call_args[0]
        assert call_args[0] == ("localhost", 4444)


class TestSend:
    """Tests for sending commands to OpenOCD."""

    def _setup_mock_socket(self, mock_socket, response: bytes):
        """Helper to set up mock socket with response."""
        mock_sock = MagicMock()

        # Set up context manager
        mock_socket.return_value = mock_sock
        mock_sock.__enter__ = MagicMock(return_value=mock_sock)
        mock_sock.__exit__ = MagicMock(return_value=False)

        # First recv drains banner (BlockingIOError = no data), then response, then empty
        mock_sock.recv.side_effect = [BlockingIOError(), response, b""]
        return mock_sock

    def test_sends_command_with_exit(self, mock_socket):
        """Should append 'exit' to command."""
        mock_sock = self._setup_mock_socket(mock_socket, b"result\n")

        ocd = OpenOCD()
        ocd.send("reg pc")

        # Check sendall was called with command + exit
        sent = mock_sock.sendall.call_args[0][0].decode()
        assert "reg pc" in sent
        assert "exit" in sent

    def test_strips_openocd_banner(self, mock_socket):
        """Should remove 'Open On-Chip' lines."""
        response = b"Open On-Chip Debugger 0.11.0\npc (/32): 0x08000000\n"
        self._setup_mock_socket(mock_socket, response)

        ocd = OpenOCD()
        result = ocd.send("reg pc")

        assert "Open On-Chip" not in result
        assert "0x08000000" in result

    def test_strips_prompt_lines(self, mock_socket):
        """Should remove lines starting with '>'."""
        response = b"> \n> \npc (/32): 0x08000000\n> "
        self._setup_mock_socket(mock_socket, response)

        ocd = OpenOCD()
        result = ocd.send("reg pc")

        assert not any(line.startswith(">") for line in result.split("\n"))
        assert "0x08000000" in result

    def test_strips_command_echo(self, mock_socket):
        """Should remove command echo from response."""
        response = b"reg pc\npc (/32): 0x08000000\n"
        self._setup_mock_socket(mock_socket, response)

        ocd = OpenOCD()
        result = ocd.send("reg pc")

        lines = [l for l in result.split("\n") if l.strip()]
        # Should not have "reg pc" as its own line
        assert "reg pc" not in lines or "0x08000000" in lines[0]

    def test_raises_on_connection_error(self, mock_socket):
        """Should raise ClickException on connection failure."""
        mock_socket.side_effect = ConnectionRefusedError()

        ocd = OpenOCD()
        with pytest.raises(click.ClickException) as exc_info:
            ocd.send("reg pc")

        assert "connection failed" in str(exc_info.value).lower()

    def test_raises_on_timeout(self, mock_socket):
        """Should raise ClickException on timeout."""
        mock_socket.side_effect = socket.timeout()

        ocd = OpenOCD()
        with pytest.raises(click.ClickException) as exc_info:
            ocd.send("reg pc")

        assert "connection failed" in str(exc_info.value).lower()

    def test_handles_memory_dump_response(self, mock_socket):
        """Should correctly parse memory dump output."""
        response = b"0x08000000: 2004fff8 08050e59 08046dfb 08046de9\n"
        self._setup_mock_socket(mock_socket, response)

        ocd = OpenOCD()
        result = ocd.send("mdw 0x08000000 4")

        assert "0x08000000" in result
        assert "2004fff8" in result

    def test_handles_multiline_register_dump(self, mock_socket):
        """Should handle multi-line register output."""
        response = b"pc (/32): 0x08000000\nsp (/32): 0x20050000\n"
        self._setup_mock_socket(mock_socket, response)

        ocd = OpenOCD()
        result = ocd.send("reg pc sp")

        assert "0x08000000" in result
        assert "0x20050000" in result


class TestEnsureRunning:
    """Tests for ensure_running context manager."""

    def test_yields_ocd_when_running(self, mock_socket):
        """Should yield self when OpenOCD is already running."""
        mock_socket.return_value.__enter__ = MagicMock()
        mock_socket.return_value.__exit__ = MagicMock(return_value=False)

        ocd = OpenOCD()
        with ocd.ensure_running() as yielded:
            assert yielded is ocd

    def test_auto_starts_when_not_running(self, mock_socket, mock_subprocess):
        """Should auto-start OpenOCD when not running."""
        call_count = [0]

        def mock_connect(*args, **kwargs):
            call_count[0] += 1
            # First 2 calls fail (ensure_running check + start's check)
            if call_count[0] <= 2:
                raise ConnectionRefusedError()
            # Subsequent calls - running (after Popen started)
            mock_conn = MagicMock()
            mock_conn.__enter__ = MagicMock(return_value=mock_conn)
            mock_conn.__exit__ = MagicMock(return_value=False)
            mock_conn.recv.return_value = b""
            return mock_conn

        mock_socket.side_effect = mock_connect

        ocd = OpenOCD()
        with patch("disco_lib.openocd.time.sleep"):
            with patch("builtins.open", MagicMock()):
                with ocd.ensure_running():
                    # Should have called start() which calls Popen
                    assert mock_subprocess.Popen.called

    def test_raises_when_start_fails(self, mock_socket, mock_subprocess):
        """Should raise ClickException when start fails."""
        # Always return connection refused (start fails)
        mock_socket.side_effect = ConnectionRefusedError()

        ocd = OpenOCD()
        with pytest.raises(click.ClickException) as exc_info:
            with ocd.ensure_running():
                pass

        assert "failed" in str(exc_info.value).lower()


class TestStartStop:
    """Tests for start/stop functionality."""

    def test_start_launches_openocd(self, mock_subprocess):
        """Should launch openocd process."""
        with patch("disco_lib.openocd.socket.create_connection") as mock_sock:
            # Set up mock socket that works for multiple calls
            mock_conn = MagicMock()
            mock_conn.__enter__ = MagicMock(return_value=mock_conn)
            mock_conn.__exit__ = MagicMock(return_value=False)
            # Return timeout for banner, then data, then empty - repeat for each send
            mock_conn.recv.return_value = b""
            mock_conn.recv.side_effect = None  # Reset side_effect

            def create_conn_side_effect(*args, **kwargs):
                # First call fails (not running yet), rest succeed
                if mock_sock.call_count == 1:
                    raise ConnectionRefusedError()
                return mock_conn

            mock_sock.side_effect = create_conn_side_effect

            with patch("disco_lib.openocd.time.sleep"):
                with patch("builtins.open", MagicMock()):
                    ocd = OpenOCD()
                    ocd.start()

        mock_subprocess.Popen.assert_called_once()
        call_args = mock_subprocess.Popen.call_args
        assert "openocd" in call_args[0][0]

    def test_stop_kills_openocd(self):
        """Should call pkill to stop openocd."""
        with patch("disco_lib.openocd.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0

            ocd = OpenOCD()
            ocd.stop()

            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]
            assert "pkill" in call_args
            assert "openocd" in call_args

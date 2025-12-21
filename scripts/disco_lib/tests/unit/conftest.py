"""Shared fixtures for disco_lib tests."""

import pytest
from unittest.mock import patch, MagicMock

from disco_lib.ocd_provider import set_ocd, reset_ocd
from disco_lib.tests.mocks import OCDMock


@pytest.fixture
def ocd_mock():
    """OCD mock with auto resume check at teardown.

    Use this for commands that should resume CPU after halting.
    Test fails if CPU is left halted when fixture tears down.
    """
    mock = OCDMock()
    set_ocd(mock)
    yield mock
    reset_ocd()
    mock.assert_resumed()


@pytest.fixture
def ocd_mock_halted_ok():
    """OCD mock for commands that intentionally leave CPU halted.

    Use this for commands like `cpu halt` that are supposed to
    leave the CPU in halted state.
    """
    mock = OCDMock()
    set_ocd(mock)
    yield mock
    reset_ocd()
    # No assert_resumed() - halted state is expected


@pytest.fixture
def ocd_mock_raw():
    """OCD mock without any automatic assertions.

    Use when you need full control over assertions.
    """
    mock = OCDMock()
    set_ocd(mock)
    yield mock
    reset_ocd()


@pytest.fixture
def mock_glob():
    """Mock glob.glob for device listing tests."""
    with patch("disco_lib.serial.glob.glob") as mock:
        yield mock


@pytest.fixture
def mock_socket():
    """Mock socket for OpenOCD tests."""
    with patch("disco_lib.openocd.socket.create_connection") as mock:
        yield mock


@pytest.fixture
def mock_serial():
    """Mock pyserial for serial tests."""
    with patch("disco_lib.serial.serial.Serial") as mock:
        yield mock


@pytest.fixture
def mock_subprocess():
    """Mock subprocess for OpenOCD start/stop."""
    with patch("disco_lib.openocd.subprocess.Popen") as mock:
        yield mock

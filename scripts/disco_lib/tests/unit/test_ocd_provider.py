"""Tests for ocd_provider.py - centralized OpenOCD instance management.

The ocd_provider module provides:
  - get_ocd(): Lazy singleton for OpenOCD instance
  - set_ocd(): Dependency injection for testing
  - reset_ocd(): Clear singleton (test cleanup)
  - with_ocd(): Context manager for safe OCD access
  - OCDProtocol: Protocol class for type checking
"""

import pytest
from contextlib import contextmanager
from typing import Generator

from disco_lib import ocd_provider
from disco_lib.ocd_provider import (
    get_ocd,
    set_ocd,
    reset_ocd,
    with_ocd,
    OCDProtocol,
)


class MockOCD:
    """Minimal mock that satisfies OCDProtocol."""

    def __init__(self):
        self.started = False
        self.ensure_running_entered = False
        self.ensure_running_exited = False
        self._was_running_before = False

    def send(self, cmd: str, timeout: float = 2.0) -> str:
        return f"mock response for: {cmd}"

    def is_running(self) -> bool:
        return self.started

    def start(self) -> bool:
        self.started = True
        return True

    def stop(self) -> None:
        self.started = False

    @contextmanager
    def ensure_running(self) -> Generator["MockOCD", None, None]:
        self.ensure_running_entered = True
        self._was_running_before = self.started
        if not self.started:
            self.start()
        try:
            yield self
        finally:
            self.ensure_running_exited = True
            if not self._was_running_before:
                self.stop()


@pytest.fixture(autouse=True)
def reset_global_state():
    """Reset global OCD instance before and after each test."""
    reset_ocd()
    yield
    reset_ocd()


class TestOCDProtocol:
    """Tests for OCDProtocol - interface definition."""

    def test_mock_satisfies_protocol(self):
        """MockOCD should satisfy OCDProtocol."""
        mock = MockOCD()
        assert isinstance(mock, OCDProtocol)

    def test_protocol_is_runtime_checkable(self):
        """Protocol should be usable with isinstance()."""
        # This tests that @runtime_checkable decorator is applied
        mock = MockOCD()
        assert isinstance(mock, OCDProtocol)

    def test_non_conforming_object_fails_check(self):
        """Object missing methods should not satisfy protocol."""

        class Incomplete:
            def send(self, cmd: str) -> str:
                return ""

            # Missing other required methods

        obj = Incomplete()
        assert not isinstance(obj, OCDProtocol)


class TestGetOcd:
    """Tests for get_ocd() - lazy singleton access."""

    def test_returns_ocd_instance(self):
        """Should return an OCDProtocol-compatible instance."""
        ocd = get_ocd()
        assert isinstance(ocd, OCDProtocol)

    def test_returns_same_instance(self):
        """Should return same instance on multiple calls (singleton)."""
        ocd1 = get_ocd()
        ocd2 = get_ocd()
        assert ocd1 is ocd2

    def test_lazy_initialization(self):
        """Instance should not exist until first get_ocd() call."""
        # After reset, _instance should be None
        assert ocd_provider._instance is None
        get_ocd()
        assert ocd_provider._instance is not None


class TestSetOcd:
    """Tests for set_ocd() - dependency injection."""

    def test_injects_mock(self):
        """set_ocd() should replace the singleton."""
        mock = MockOCD()
        set_ocd(mock)
        assert get_ocd() is mock

    def test_subsequent_get_returns_injected(self):
        """After set_ocd(), get_ocd() should return injected instance."""
        mock = MockOCD()
        set_ocd(mock)

        # Multiple calls should return the injected mock
        assert get_ocd() is mock
        assert get_ocd() is mock

    def test_replaces_existing_instance(self):
        """set_ocd() should replace any existing instance."""
        # First, let lazy init create a real instance
        real = get_ocd()

        # Now inject mock
        mock = MockOCD()
        set_ocd(mock)

        assert get_ocd() is mock
        assert get_ocd() is not real


class TestResetOcd:
    """Tests for reset_ocd() - singleton cleanup."""

    def test_clears_instance(self):
        """reset_ocd() should set _instance to None."""
        get_ocd()  # Create instance
        assert ocd_provider._instance is not None

        reset_ocd()
        assert ocd_provider._instance is None

    def test_next_get_creates_new_instance(self):
        """After reset, get_ocd() should create fresh instance."""
        ocd1 = get_ocd()
        reset_ocd()
        ocd2 = get_ocd()

        # Should be different instances (though same type)
        assert ocd1 is not ocd2

    def test_clears_injected_mock(self):
        """reset_ocd() should clear injected mocks too."""
        mock = MockOCD()
        set_ocd(mock)
        reset_ocd()

        # Next get should NOT return the mock
        new_ocd = get_ocd()
        assert new_ocd is not mock


class TestWithOcd:
    """Tests for with_ocd() - context manager for OCD access."""

    def test_yields_ocd_instance(self):
        """Should yield an OCDProtocol instance."""
        mock = MockOCD()
        set_ocd(mock)

        with with_ocd() as ocd:
            assert isinstance(ocd, OCDProtocol)

    def test_yields_injected_mock(self):
        """Should yield the injected mock."""
        mock = MockOCD()
        set_ocd(mock)

        with with_ocd() as ocd:
            assert ocd is mock

    def test_calls_ensure_running_context_manager(self):
        """Should call ocd.ensure_running() context manager."""
        mock = MockOCD()
        set_ocd(mock)

        with with_ocd():
            assert mock.ensure_running_entered

        assert mock.ensure_running_exited

    def test_auto_starts_if_not_running(self):
        """Should auto-start OpenOCD if not running."""
        mock = MockOCD()
        mock.started = False
        set_ocd(mock)

        with with_ocd():
            assert mock.started

    def test_stops_if_we_started_it(self):
        """Should stop OpenOCD on exit if we started it."""
        mock = MockOCD()
        mock.started = False
        set_ocd(mock)

        with with_ocd():
            assert mock.started

        # Should have stopped since we started it
        assert not mock.started

    def test_keeps_running_if_already_started(self):
        """Should not stop OpenOCD if it was already running."""
        mock = MockOCD()
        mock.started = True
        set_ocd(mock)

        with with_ocd():
            assert mock.started

        # Should still be running since it was already started
        assert mock.started

    def test_can_send_commands_inside_context(self):
        """Should be able to use ocd.send() inside context."""
        mock = MockOCD()
        set_ocd(mock)

        with with_ocd() as ocd:
            result = ocd.send("test command")
            assert "test command" in result

    def test_cleans_up_on_exception(self):
        """ensure_running() exit should be called even on exception."""
        mock = MockOCD()
        set_ocd(mock)

        with pytest.raises(ValueError):
            with with_ocd():
                raise ValueError("test error")

        # ensure_running() should still have exited
        assert mock.ensure_running_exited

"""Mock OpenOCD for testing halt/resume balance."""

from contextlib import contextmanager
from typing import Dict, Generator, List


class OCDMock:
    """Mock OpenOCD that tracks halt/resume state.

    Usage:
        mock = OCDMock()
        set_ocd(mock)
        # ... run command ...
        mock.assert_resumed()  # fails if CPU left halted

    For commands that intentionally leave CPU halted (like `cpu halt`),
    use ocd_mock_halted_ok fixture or skip assert_resumed().
    """

    def __init__(self):
        self._halted = False
        self._halt_count = 0
        self._resume_count = 0
        self._commands: List[str] = []
        self._responses: Dict[str, str] = {}
        self._error_triggers: Dict[str, Exception] = {}
        self._default_responses = {
            "reg pc": "pc (/32): 0x08020000",
            "reg sp": "sp (/32): 0x20050000",
            "reg lr": "lr (/32): 0x08020100",
            "reg pc sp": "pc (/32): 0x08020000\nsp (/32): 0x20050000",
            "reg": "pc (/32): 0x08020000\nsp (/32): 0x20050000\nlr (/32): 0x08020100",
            "flash info 0": "Bank 0: stm32f4x at 0x08000000, size 0x200000",
            "mdw": "0x08000000: 2004fff8 08050e59 08046dfb 08046de9",
        }

    def send(self, cmd: str, timeout: float = 2.0) -> str:
        """Track command and return mock response."""
        self._commands.append(cmd)

        # Check error triggers first
        for pattern, error in self._error_triggers.items():
            if pattern in cmd:
                raise error

        # Track halt/resume state
        cmd_lower = cmd.lower().strip()
        if cmd_lower == "halt" or cmd_lower.startswith("halt "):
            self._halted = True
            self._halt_count += 1
        elif cmd_lower == "resume":
            self._halted = False
            self._resume_count += 1
        elif cmd_lower == "reset halt":
            self._halted = True
            self._halt_count += 1
        elif cmd_lower == "reset" or cmd_lower.startswith("reset "):
            # reset without "halt" resumes execution
            self._halted = False
            self._resume_count += 1

        # Return configured or default response
        if cmd in self._responses:
            return self._responses[cmd]

        # Check prefix matches for default responses
        for pattern, response in self._default_responses.items():
            if cmd.startswith(pattern):
                return response

        return ""

    def is_running(self) -> bool:
        """Always returns True for mock."""
        return True

    def require_running(self) -> None:
        """No-op for mock."""
        pass

    def start(self) -> bool:
        """Mock start - tracks halt like real implementation."""
        # Real OpenOCD.start() does halt at line 115
        self._halted = True
        self._halt_count += 1
        return True

    def stop(self) -> None:
        """Mock stop - no-op."""
        pass

    @contextmanager
    def running(self, auto_start: bool = True) -> Generator["OCDMock", None, None]:
        """Mock running context manager - always succeeds."""
        yield self

    # Configuration methods (chainable)
    def set_response(self, cmd: str, response: str) -> "OCDMock":
        """Set response for specific command."""
        self._responses[cmd] = response
        return self

    def set_error_on(self, pattern: str, error: Exception) -> "OCDMock":
        """Raise error when command contains pattern."""
        self._error_triggers[pattern] = error
        return self

    def clear_error_on(self, pattern: str) -> "OCDMock":
        """Remove error trigger."""
        self._error_triggers.pop(pattern, None)
        return self

    # Assertion methods
    def assert_resumed(self, msg: str = "") -> None:
        """Assert CPU is not left halted.

        Call this after running a command to verify it properly
        resumed the CPU. Most commands should halt, do work, then resume.
        """
        if self._halted:
            cmds = "\n  ".join(self._commands[-10:])
            raise AssertionError(
                f"CPU left halted! halts={self._halt_count} "
                f"resumes={self._resume_count}\n"
                f"Last commands:\n  {cmds}"
                + (f"\n{msg}" if msg else "")
            )

    def assert_balanced(self) -> None:
        """Assert halt count equals resume count.

        Stricter than assert_resumed() - catches cases where
        code does multiple halts without matching resumes.
        """
        if self._halt_count != self._resume_count:
            raise AssertionError(
                f"halt/resume imbalance: {self._halt_count} halts, "
                f"{self._resume_count} resumes"
            )

    def assert_halted(self, msg: str = "") -> None:
        """Assert CPU IS halted (for commands like `cpu halt`)."""
        if not self._halted:
            raise AssertionError(
                f"Expected CPU to be halted but it's running. "
                f"halts={self._halt_count} resumes={self._resume_count}"
                + (f"\n{msg}" if msg else "")
            )

    # State inspection
    @property
    def halted(self) -> bool:
        """Current halt state."""
        return self._halted

    @property
    def commands(self) -> List[str]:
        """Copy of all commands sent."""
        return self._commands.copy()

    @property
    def halt_count(self) -> int:
        return self._halt_count

    @property
    def resume_count(self) -> int:
        return self._resume_count

    def reset_state(self) -> None:
        """Reset all tracking state."""
        self._halted = False
        self._halt_count = 0
        self._resume_count = 0
        self._commands.clear()

"""Tests for cpu.py business logic.

The cpu module provides high-level CPU control functions:
  - halted(): Context manager for safe halt/resume
  - halt(), resume(): Direct CPU control
  - reset_halt(), reset_run(): Reset variants
  - step(): Single-step execution
  - read_pc(), read_sp(): Register reading with parsing
"""

import pytest

from disco_lib import cpu


class TestHaltedContextManager:
    """Tests for halted() context manager - critical for CPU state safety.

    The halted() context manager must ALWAYS resume the CPU, even when
    an exception occurs inside the with block. This prevents leaving
    the target in a halted state which breaks USB CDC/REPL.
    """

    def test_halts_on_entry(self, ocd_mock_raw):
        """CPU should be halted when entering the context."""
        with cpu.halted(ocd_mock_raw):
            assert ocd_mock_raw.halted
            assert ocd_mock_raw.halt_count == 1

    def test_resumes_on_normal_exit(self, ocd_mock_raw):
        """CPU should be resumed after normal context exit."""
        with cpu.halted(ocd_mock_raw):
            pass
        assert not ocd_mock_raw.halted
        assert ocd_mock_raw.resume_count == 1

    def test_resumes_on_exception(self, ocd_mock_raw):
        """CPU MUST be resumed even when exception occurs inside context.

        This is the critical safety behavior - if code inside the halted
        block raises an exception, we must still resume to avoid leaving
        the target stuck.
        """
        with pytest.raises(ValueError):
            with cpu.halted(ocd_mock_raw):
                raise ValueError("simulated error")

        # CPU must be resumed despite the exception
        assert not ocd_mock_raw.halted
        assert ocd_mock_raw.resume_count == 1

    def test_resumes_on_keyboard_interrupt(self, ocd_mock_raw):
        """CPU should resume even on KeyboardInterrupt (Ctrl-C)."""
        with pytest.raises(KeyboardInterrupt):
            with cpu.halted(ocd_mock_raw):
                raise KeyboardInterrupt()

        assert not ocd_mock_raw.halted

    def test_commands_in_correct_order(self, ocd_mock_raw):
        """halt should come before resume in command sequence."""
        with cpu.halted(ocd_mock_raw):
            ocd_mock_raw.send("reg pc")  # some work

        assert ocd_mock_raw.commands == ["halt", "reg pc", "resume"]

    def test_nested_halted_blocks(self, ocd_mock_raw):
        """Nested halted blocks should work (though unusual)."""
        with cpu.halted(ocd_mock_raw):
            with cpu.halted(ocd_mock_raw):
                pass
            # Inner resumed, but we're still in outer halt
            # Note: mock tracks state, not nesting depth
        assert ocd_mock_raw.halt_count == 2
        assert ocd_mock_raw.resume_count == 2


class TestHalt:
    """Tests for halt() function."""

    def test_sends_halt_command(self, ocd_mock_raw):
        """Should send 'halt' command to OpenOCD."""
        cpu.halt(ocd_mock_raw)
        assert "halt" in ocd_mock_raw.commands

    def test_returns_ocd_response(self, ocd_mock_raw):
        """Should return OpenOCD response string."""
        ocd_mock_raw.set_response("halt", "target halted")
        result = cpu.halt(ocd_mock_raw)
        assert result == "target halted"

    def test_sets_halted_state(self, ocd_mock_raw):
        """Should set CPU to halted state."""
        cpu.halt(ocd_mock_raw)
        assert ocd_mock_raw.halted


class TestResume:
    """Tests for resume() function."""

    def test_sends_resume_command(self, ocd_mock_raw):
        """Should send 'resume' command to OpenOCD."""
        cpu.resume(ocd_mock_raw)
        assert "resume" in ocd_mock_raw.commands

    def test_clears_halted_state(self, ocd_mock_raw):
        """Should clear halted state."""
        ocd_mock_raw.send("halt")  # First halt
        cpu.resume(ocd_mock_raw)
        assert not ocd_mock_raw.halted


class TestResetHalt:
    """Tests for reset_halt() function."""

    def test_sends_reset_halt_command(self, ocd_mock_raw):
        """Should send 'reset halt' command."""
        cpu.reset_halt(ocd_mock_raw)
        assert "reset halt" in ocd_mock_raw.commands

    def test_leaves_cpu_halted(self, ocd_mock_raw):
        """reset halt should leave CPU in halted state."""
        cpu.reset_halt(ocd_mock_raw)
        assert ocd_mock_raw.halted


class TestResetRun:
    """Tests for reset_run() function."""

    def test_sends_reset_run_command(self, ocd_mock_raw):
        """Should send 'reset run' command."""
        cpu.reset_run(ocd_mock_raw)
        # The mock treats any "reset " without "halt" as resume
        assert any("reset" in cmd for cmd in ocd_mock_raw.commands)

    def test_leaves_cpu_running(self, ocd_mock_raw):
        """reset run should leave CPU running."""
        ocd_mock_raw.send("halt")  # Start halted
        cpu.reset_run(ocd_mock_raw)
        assert not ocd_mock_raw.halted


class TestStep:
    """Tests for step() function."""

    def test_sends_step_command(self, ocd_mock_raw):
        """Should send 'step' command."""
        cpu.step(ocd_mock_raw)
        assert "step" in ocd_mock_raw.commands


class TestReadPc:
    """Tests for read_pc() - parses PC register value.

    OpenOCD returns register values like: 'pc (/32): 0x080dc37c'
    This function extracts the hex value as an integer.
    """

    def test_parses_standard_format(self, ocd_mock_raw):
        """Parse standard OpenOCD register output."""
        ocd_mock_raw.set_response("reg pc", "pc (/32): 0x08020000")
        assert cpu.read_pc(ocd_mock_raw) == 0x08020000

    def test_parses_lowercase_hex(self, ocd_mock_raw):
        """Lowercase hex digits should parse correctly."""
        ocd_mock_raw.set_response("reg pc", "pc (/32): 0x0800abcd")
        assert cpu.read_pc(ocd_mock_raw) == 0x0800abcd

    def test_parses_uppercase_hex(self, ocd_mock_raw):
        """Uppercase hex digits should parse correctly."""
        ocd_mock_raw.set_response("reg pc", "pc (/32): 0x0800ABCD")
        assert cpu.read_pc(ocd_mock_raw) == 0x0800ABCD

    def test_parses_mixed_case_hex(self, ocd_mock_raw):
        """Mixed case hex digits should parse correctly."""
        ocd_mock_raw.set_response("reg pc", "pc (/32): 0x080AbCdE")
        assert cpu.read_pc(ocd_mock_raw) == 0x080abcde

    def test_returns_none_on_error_response(self, ocd_mock_raw):
        """Should return None when OpenOCD returns error."""
        ocd_mock_raw.set_response("reg pc", "Error: target not responding")
        assert cpu.read_pc(ocd_mock_raw) is None

    def test_returns_none_on_empty_response(self, ocd_mock_raw):
        """Should return None on empty response."""
        ocd_mock_raw.set_response("reg pc", "")
        assert cpu.read_pc(ocd_mock_raw) is None

    def test_returns_none_on_no_hex(self, ocd_mock_raw):
        """Should return None when no hex value present."""
        ocd_mock_raw.set_response("reg pc", "pc: unknown")
        assert cpu.read_pc(ocd_mock_raw) is None

    def test_multiline_takes_first_hex(self, ocd_mock_raw):
        """When multiple hex values, should take first one."""
        ocd_mock_raw.set_response("reg pc", "pc (/32): 0x08000000\nsp (/32): 0x20050000")
        assert cpu.read_pc(ocd_mock_raw) == 0x08000000


class TestReadSp:
    """Tests for read_sp() - parses SP register value."""

    def test_parses_standard_format(self, ocd_mock_raw):
        """Parse standard OpenOCD register output."""
        ocd_mock_raw.set_response("reg sp", "sp (/32): 0x20050000")
        assert cpu.read_sp(ocd_mock_raw) == 0x20050000

    def test_returns_none_on_error(self, ocd_mock_raw):
        """Should return None on error response."""
        ocd_mock_raw.set_response("reg sp", "Error: cannot read register")
        assert cpu.read_sp(ocd_mock_raw) is None

    def test_typical_ram_address(self, ocd_mock_raw):
        """SP should typically be in RAM region."""
        ocd_mock_raw.set_response("reg sp", "sp (/32): 0x2004fff8")
        sp = cpu.read_sp(ocd_mock_raw)
        assert 0x20000000 <= sp < 0x20060000  # STM32F469 RAM range


class TestReadReg:
    """Tests for read_reg() - reads arbitrary register."""

    def test_reads_named_register(self, ocd_mock_raw):
        """Should send correct register name to OpenOCD."""
        ocd_mock_raw.set_response("reg lr", "lr (/32): 0x08020100")
        result = cpu.read_reg(ocd_mock_raw, "lr")
        assert "0x08020100" in result

    def test_passes_through_response(self, ocd_mock_raw):
        """Should return raw OpenOCD response."""
        ocd_mock_raw.set_response("reg r0", "r0 (/32): 0x00000042")
        result = cpu.read_reg(ocd_mock_raw, "r0")
        assert result == "r0 (/32): 0x00000042"


class TestReadRegs:
    """Tests for read_regs() - reads all registers."""

    def test_sends_reg_command(self, ocd_mock_raw):
        """Should send 'reg' command without arguments."""
        cpu.read_regs(ocd_mock_raw)
        assert "reg" in ocd_mock_raw.commands


class TestReadPcSp:
    """Tests for read_pc_sp() - reads PC and SP together."""

    def test_sends_combined_command(self, ocd_mock_raw):
        """Should send 'reg pc sp' command."""
        cpu.read_pc_sp(ocd_mock_raw)
        assert "reg pc sp" in ocd_mock_raw.commands

    def test_returns_combined_output(self, ocd_mock_raw):
        """Should return output containing both registers."""
        ocd_mock_raw.set_response("reg pc sp", "pc (/32): 0x08020000\nsp (/32): 0x20050000")
        result = cpu.read_pc_sp(ocd_mock_raw)
        assert "0x08020000" in result  # PC
        assert "0x20050000" in result  # SP

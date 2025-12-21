"""Tests for halt/resume balance in commands.

These tests verify that commands which halt the CPU properly resume it
before returning. This prevents leaving the target in a halted state
which disconnects USB CDC and breaks REPL access.

The ocd_mock fixture automatically checks assert_resumed() at teardown,
so tests fail if CPU is left halted.
"""

import os
import tempfile

import pytest
from click.testing import CliRunner

from disco_lib.commands.flash import flash, flash_info, flash_identify, flash_read, flash_verify, flash_erase
from disco_lib.commands.mem import mem, mem_read, mem_vectors, mem_dump, mem_save
from disco_lib.commands.cpu import cpu, cpu_halt, cpu_resume, cpu_reset, cpu_regs, cpu_pc, cpu_stack
from disco_lib.commands.check import check
from disco_lib.commands.cables import cables


class TestFlashCommandsResumesCPU:
    """Flash commands should resume CPU after halting."""

    def test_flash_info_no_halt(self, ocd_mock):
        """flash info doesn't halt - just queries flash bank."""
        ocd_mock.set_response("flash info 0", "Bank 0: stm32f4x")
        runner = CliRunner()
        result = runner.invoke(flash_info)
        # No halt called, so no resume needed
        assert ocd_mock.halt_count == 0

    def test_flash_identify_from_file_no_halt(self, ocd_mock):
        """flash identify with --file doesn't need OCD."""
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
            f.write(b"\x00" * 1000)
            f.write(b"<version:tag10>0100900001</version:tag10>")
            f.write(b"\x00" * 1000)
            tmp_path = f.name
        try:
            runner = CliRunner()
            result = runner.invoke(flash_identify, [tmp_path])
            assert ocd_mock.halt_count == 0
        finally:
            os.unlink(tmp_path)

    def test_flash_identify_from_device_resumes(self, ocd_mock):
        """flash identify without file should halt then resume."""
        ocd_mock.set_response(
            "dump_image /tmp/", "dumped 1572864 bytes"  # partial match
        )
        runner = CliRunner()
        # This will fail because dump_image creates a file we can't read,
        # but we're testing halt/resume behavior
        result = runner.invoke(flash_identify)
        # Currently FAILS - no resume after halt
        # Test will fail at fixture teardown due to assert_resumed()

    def test_flash_read_resumes(self, ocd_mock):
        """flash read should resume CPU after reading."""
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
            tmp_path = f.name

        try:
            runner = CliRunner()
            result = runner.invoke(flash_read, [tmp_path, "--size", "0x100"])
            # Currently FAILS - no resume after halt
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_flash_verify_resumes(self, ocd_mock):
        """flash verify should resume CPU after verification."""
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
            f.write(b"\xff" * 4096)
            tmp_path = f.name

        try:
            ocd_mock.set_response("verify_image", "verified OK")
            runner = CliRunner()
            result = runner.invoke(flash_verify, [tmp_path, "--full"])
            # Currently FAILS - no resume after halt
        finally:
            os.unlink(tmp_path)

    def test_flash_erase_resumes(self, ocd_mock):
        """flash erase should resume CPU after erasing."""
        runner = CliRunner()
        # Simulate 'y' confirmation
        result = runner.invoke(flash_erase, input="y\n")
        # Currently FAILS - no resume after halt


class TestMemCommandsResumesCPU:
    """Memory commands should resume CPU after halting."""

    def test_mem_read_resumes(self, ocd_mock):
        """mem read should resume CPU after reading memory."""
        ocd_mock.set_response("mdw 0x08000000 8", "0x08000000: 2004fff8 08050e59")
        runner = CliRunner()
        result = runner.invoke(mem_read, ["0x08000000", "8"])
        # Currently FAILS - no resume after halt

    def test_mem_vectors_resumes(self, ocd_mock):
        """mem vectors should resume CPU after reading vectors."""
        ocd_mock.set_response("mdw 0x08000000 8", "0x08000000: 2004fff8 08050e59 08046dfb 08046de9 08046df1 08046df5 08046df9 00000000")
        runner = CliRunner()
        result = runner.invoke(mem_vectors)
        # Currently FAILS - no resume after halt

    def test_mem_dump_resumes(self, ocd_mock):
        """mem dump should resume CPU after dumping memory."""
        ocd_mock.set_response("mdw 0x08000000 32", "0x08000000: 2004fff8 08050e59")
        runner = CliRunner()
        result = runner.invoke(mem_dump, ["32"])
        # Currently FAILS - no resume after halt

    def test_mem_save_resumes(self, ocd_mock):
        """mem save should resume CPU after saving memory to file."""
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
            tmp_path = f.name

        try:
            runner = CliRunner()
            result = runner.invoke(mem_save, [tmp_path, "0x08000000", "0x100"])
            # Currently FAILS - no resume after halt
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)


class TestCpuCommandsHaltResume:
    """CPU commands - some intentionally leave halted."""

    def test_cpu_halt_intentionally_halted(self, ocd_mock_halted_ok):
        """cpu halt command intentionally leaves CPU halted."""
        runner = CliRunner()
        result = runner.invoke(cpu_halt)
        assert ocd_mock_halted_ok.halted
        assert result.exit_code == 0

    def test_cpu_resume_resumes(self, ocd_mock_raw):
        """cpu resume command resumes CPU."""
        # Start in halted state
        ocd_mock_raw._halted = True
        runner = CliRunner()
        result = runner.invoke(cpu_resume)
        assert not ocd_mock_raw.halted
        assert result.exit_code == 0

    def test_cpu_reset_intentionally_halted(self, ocd_mock_halted_ok):
        """cpu reset (reset halt) intentionally leaves CPU halted."""
        runner = CliRunner()
        result = runner.invoke(cpu_reset)
        assert ocd_mock_halted_ok.halted  # reset halt leaves halted
        assert result.exit_code == 0

    def test_cpu_regs_resumes(self, ocd_mock):
        """cpu regs should resume CPU after showing registers."""
        ocd_mock.set_response("reg", "r0: 0x00000000\nr1: 0x00000001")
        runner = CliRunner()
        result = runner.invoke(cpu_regs)
        # Currently FAILS - no resume after halt

    def test_cpu_pc_resumes(self, ocd_mock):
        """cpu pc should resume CPU after showing PC."""
        ocd_mock.set_response("reg pc", "pc (/32): 0x08020000")
        ocd_mock.set_response("mdw 0x0801fff0 16", "0x0801fff0: 00000000")
        runner = CliRunner()
        result = runner.invoke(cpu_pc)
        # Currently FAILS - no resume after halt

    def test_cpu_stack_resumes(self, ocd_mock):
        """cpu stack should resume CPU after showing stack."""
        ocd_mock.set_response("reg sp", "sp (/32): 0x20050000")
        ocd_mock.set_response("mdw 0x20050000 16", "0x20050000: 00000000")
        runner = CliRunner()
        result = runner.invoke(cpu_stack, ["16"])
        # Currently FAILS - no resume after halt


class TestCheckCommandResumes:
    """Check command should resume CPU (unless --no-resume)."""

    def test_check_resumes_by_default(self, ocd_mock):
        """check command resumes CPU by default."""
        runner = CliRunner()
        result = runner.invoke(check)
        # This one SHOULD pass - check has resume logic
        # But needs try/finally for robustness

    def test_check_no_resume_intentionally_halted(self, ocd_mock_halted_ok):
        """check --no-resume intentionally leaves CPU halted."""
        runner = CliRunner()
        result = runner.invoke(check, ["--no-resume"])
        assert ocd_mock_halted_ok.halted

    def test_check_resumes_on_error(self, ocd_mock):
        """check should resume even if a command fails."""
        ocd_mock.set_error_on("mdw 0x08020000", Exception("read failed"))
        runner = CliRunner()
        result = runner.invoke(check)
        # Currently FAILS - no try/finally, so error skips resume


class TestCablesCommandResumes:
    """Cables command should resume CPU after JTAG check."""

    def test_cables_resumes_when_ocd_running(self, ocd_mock):
        """cables should resume CPU after JTAG check."""
        ocd_mock.set_response("reg pc", "pc (/32): 0x08020000")
        runner = CliRunner()
        result = runner.invoke(cables)
        # This one SHOULD pass - cables has halt/resume pair
        # But needs try/finally for robustness

    def test_cables_resumes_on_error(self, ocd_mock):
        """cables should resume even if reg pc fails."""
        ocd_mock.set_error_on("reg pc", Exception("target not responding"))
        runner = CliRunner()
        # Should still resume after error
        try:
            result = runner.invoke(cables)
        except Exception:
            pass
        # Currently FAILS - no try/finally


class TestOCDMockBehavior:
    """Tests for the OCDMock itself."""

    def test_halt_sets_halted_state(self, ocd_mock_raw):
        """Sending halt should set halted state."""
        ocd_mock_raw.send("halt")
        assert ocd_mock_raw.halted
        assert ocd_mock_raw.halt_count == 1

    def test_resume_clears_halted_state(self, ocd_mock_raw):
        """Sending resume should clear halted state."""
        ocd_mock_raw.send("halt")
        ocd_mock_raw.send("resume")
        assert not ocd_mock_raw.halted
        assert ocd_mock_raw.resume_count == 1

    def test_reset_halt_leaves_halted(self, ocd_mock_raw):
        """reset halt should leave CPU halted."""
        ocd_mock_raw.send("reset halt")
        assert ocd_mock_raw.halted

    def test_reset_run_leaves_running(self, ocd_mock_raw):
        """reset run should leave CPU running."""
        ocd_mock_raw.send("halt")
        ocd_mock_raw.send("reset run")
        assert not ocd_mock_raw.halted

    def test_assert_resumed_passes_when_not_halted(self, ocd_mock_raw):
        """assert_resumed should pass when CPU not halted."""
        ocd_mock_raw.assert_resumed()  # Should not raise

    def test_assert_resumed_fails_when_halted(self, ocd_mock_raw):
        """assert_resumed should fail when CPU is halted."""
        ocd_mock_raw.send("halt")
        with pytest.raises(AssertionError, match="CPU left halted"):
            ocd_mock_raw.assert_resumed()

    def test_error_trigger_works(self, ocd_mock_raw):
        """set_error_on should trigger errors."""
        ocd_mock_raw.set_error_on("dump_image", ValueError("test error"))
        with pytest.raises(ValueError, match="test error"):
            ocd_mock_raw.send("dump_image /tmp/x.bin 0x08000000 100")

    def test_commands_logged(self, ocd_mock_raw):
        """All commands should be logged."""
        ocd_mock_raw.send("halt")
        ocd_mock_raw.send("reg pc")
        ocd_mock_raw.send("resume")
        assert ocd_mock_raw.commands == ["halt", "reg pc", "resume"]

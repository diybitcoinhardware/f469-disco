"""Tests for diagnostics.py backend.

The diagnostics module parses OpenOCD output and generates board health reports.
Key functions:
  - _parse_reg: Extract hex values from "reg pc" output
  - _parse_mdw: Extract memory words from "mdw" output
  - _in_range: Check if address is within valid memory region
  - DiagnosticReport: Collect and summarize diagnostic findings
  - generate_markdown: Format report for logging
"""

import tempfile
from pathlib import Path

from disco_lib.diagnostics import (
    _parse_reg,
    _parse_mdw,
    _in_range,
    DiagnosticReport,
    Level,
    generate_markdown,
    save_log,
    check_target,
    capture_cpu_state,
    check_cpu_stuck,
    FLASH_START,
    FLASH_END,
    RAM_START,
    RAM_END,
    CFSR_NOCP,
    HFSR_FORCED,
)


class TestParseReg:
    """Tests for _parse_reg() - extracts register value from OpenOCD output.

    OpenOCD returns register values in format: "pc (/32): 0x080dc37c"
    We need to extract the hex value reliably for CPU state analysis.
    """

    def test_parses_standard_format(self):
        """Standard OpenOCD register output format."""
        assert _parse_reg("pc (/32): 0x080dc37c") == 0x080dc37c
        assert _parse_reg("sp (/32): 0x20050000") == 0x20050000
        assert _parse_reg("lr (/32): 0x0800abcd") == 0x0800abcd

    def test_handles_case_variations(self):
        """Hex digits can be upper/lower/mixed case."""
        assert _parse_reg("pc (/32): 0x0800ABCD") == 0x0800ABCD
        assert _parse_reg("pc (/32): 0x080AbCdE") == 0x080abcde

    def test_returns_none_on_invalid(self):
        """Returns None when no hex value found - caller must handle."""
        assert _parse_reg("no hex here") is None
        assert _parse_reg("") is None
        assert _parse_reg("Error: target not responding") is None

    def test_multiline_takes_first(self):
        """When multiple regs returned, take first (matches requested reg)."""
        output = "pc (/32): 0x08000000\nsp (/32): 0x20000000"
        assert _parse_reg(output) == 0x08000000


class TestParseMdw:
    """Tests for _parse_mdw() - parses memory dump output.

    OpenOCD "mdw" command returns: "0xADDRESS: WORD1 WORD2 WORD3..."
    Used to read vector table, fault registers, etc.

    Returns (words, skipped) tuple for diagnostic reporting.
    """

    def test_single_word(self):
        """Reading single 32-bit word."""
        words, skipped = _parse_mdw("0x08000000: 2004fff8")
        assert words == [0x2004fff8]
        assert skipped == []

    def test_multiple_words(self):
        """Reading multiple words (e.g., vector table SP + Reset)."""
        output = "0x08000000: 2004fff8 08050e59 08046dfb 08046de9"
        words, skipped = _parse_mdw(output)
        assert words == [0x2004fff8, 0x08050e59, 0x08046dfb, 0x08046de9]
        assert skipped == []

    def test_vector_table_read(self):
        """Common use case: read initial SP and Reset vector."""
        # Vector table at 0x08000000: [initial_sp, reset_handler, ...]
        output = "0x08000000: 20050000 08020001"
        words, skipped = _parse_mdw(output)
        assert words[0] == 0x20050000  # SP should be in RAM
        assert words[1] == 0x08020001  # Reset handler in Flash (thumb bit set)
        assert skipped == []

    def test_returns_empty_on_invalid(self):
        """Returns empty list on parse failure - caller checks len()."""
        assert _parse_mdw("no memory dump here") == ([], [])
        assert _parse_mdw("") == ([], [])
        assert _parse_mdw("Error: cannot read memory") == ([], [])

    def test_handles_extra_whitespace(self):
        """OpenOCD output may have inconsistent spacing."""
        output = "0x08000000:   2004fff8   08050e59  "
        words, skipped = _parse_mdw(output)
        assert words == [0x2004fff8, 0x08050e59]
        assert skipped == []

    def test_skipped_unreadable_memory(self):
        """Unreadable memory returns ???????? - should be captured."""
        output = "0x08000000: 2004fff8 ???????? 08046dfb"
        words, skipped = _parse_mdw(output)
        assert words == [0x2004fff8, 0x08046dfb]
        assert skipped == ["????????"]

    def test_skipped_multiple_bad_values(self):
        """Multiple bad values all captured."""
        output = "0x08000000: ???????? XXXXXXXX <error>"
        words, skipped = _parse_mdw(output)
        assert words == []
        assert skipped == ["????????", "XXXXXXXX", "<error>"]


class TestInRange:
    """Tests for _in_range() - validates addresses against memory regions.

    STM32F469 memory map:
      Flash: 0x08000000 - 0x08200000 (2MB)
      RAM:   0x20000000 - 0x20060000 (384KB)

    Used to validate vector table entries and detect invalid memory accesses.
    """

    def test_range_boundaries(self):
        """Start is inclusive, end is exclusive."""
        assert _in_range(0x08000000, 0x08000000, 0x08200000) is True   # start
        assert _in_range(0x081FFFFF, 0x08000000, 0x08200000) is True   # last valid
        assert _in_range(0x08200000, 0x08000000, 0x08200000) is False  # end (exclusive)

    def test_out_of_range(self):
        """Addresses outside region should return False."""
        assert _in_range(0x07FFFFFF, 0x08000000, 0x08200000) is False  # below
        assert _in_range(0x08200001, 0x08000000, 0x08200000) is False  # above

    def test_flash_validation(self):
        """Validate addresses are in Flash region."""
        assert _in_range(0x08020000, FLASH_START, FLASH_END) is True   # firmware
        assert _in_range(0x00000000, FLASH_START, FLASH_END) is False  # null ptr
        assert _in_range(0x20000000, FLASH_START, FLASH_END) is False  # RAM addr

    def test_ram_validation(self):
        """Validate addresses are in RAM region."""
        assert _in_range(0x20000000, RAM_START, RAM_END) is True   # RAM start
        assert _in_range(0x20050000, RAM_START, RAM_END) is True   # typical SP
        assert _in_range(0x08000000, RAM_START, RAM_END) is False  # Flash addr


class TestDiagnosticReport:
    """Tests for DiagnosticReport dataclass.

    Collects diagnostic findings with severity levels:
      ERROR - Critical issues (faults, invalid memory)
      WARN  - Non-critical issues (FPU disabled, no REPL)
      OK    - Passed checks (informational)
    """

    def test_empty_report_counts(self):
        """New report has zero errors/warnings."""
        report = DiagnosticReport()
        assert report.errors == 0
        assert report.warnings == 0

    def test_error_counting(self):
        """Errors increment error count only."""
        report = DiagnosticReport()
        report.add("CPU_STUCK", Level.ERROR, "PC not changing")
        report.add("HARDFAULT", Level.ERROR, "Fault detected")
        assert report.errors == 2
        assert report.warnings == 0

    def test_warning_counting(self):
        """Warnings increment warning count only."""
        report = DiagnosticReport()
        report.add("FPU_DISABLED", Level.WARN, "FPU not enabled")
        assert report.errors == 0
        assert report.warnings == 1

    def test_ok_not_counted(self):
        """OK level doesn't count as error or warning."""
        report = DiagnosticReport()
        report.add("VECTORS_OK", Level.OK, "Vector table valid")
        assert report.errors == 0
        assert report.warnings == 0

    def test_mixed_diagnostics(self):
        """Report can contain mix of levels."""
        report = DiagnosticReport()
        report.add("ERR1", Level.ERROR, "Error 1")
        report.add("ERR2", Level.ERROR, "Error 2")
        report.add("WARN1", Level.WARN, "Warning 1")
        report.add("OK1", Level.OK, "Check passed")
        assert report.errors == 2
        assert report.warnings == 1
        assert len(report.diagnostics) == 4

    def test_diagnostic_with_details(self):
        """Diagnostics can include extra detail string."""
        report = DiagnosticReport()
        report.add("BFAR_INVALID", Level.ERROR, "Bus fault", "BFAR=0xDEADBEEF")
        diag = report.diagnostics[0]
        assert diag.code == "BFAR_INVALID"
        assert diag.message == "Bus fault"
        assert diag.details == "BFAR=0xDEADBEEF"


class TestGenerateMarkdown:
    """Tests for generate_markdown() - formats report for logging.

    Generates human-readable markdown with:
      - Connection status (OpenOCD, target, USB)
      - CPU state (PC, SP, LR)
      - Fault register analysis
      - Configuration checks (FPU, vectors)
      - Summary with error/warning counts
    """

    def test_has_required_sections(self):
        """Report has title, connection, and summary sections."""
        report = DiagnosticReport()
        report.openocd_running = True
        md = generate_markdown(report)

        assert "# Board Diagnostic Report" in md
        assert "## Connection" in md
        assert "## Summary" in md

    def test_connection_status_display(self):
        """Connection section shows OpenOCD and target state."""
        report = DiagnosticReport()
        report.openocd_running = True
        report.target_responding = True
        report.pc = 0x08020000

        md = generate_markdown(report)
        assert "OpenOCD running" in md
        assert "Target responding" in md
        assert "0x08020000" in md

    def test_openocd_not_running(self):
        """Shows clear message when OpenOCD down."""
        report = DiagnosticReport()
        report.openocd_running = False

        md = generate_markdown(report)
        assert "OpenOCD not running" in md

    def test_usb_cdc_status(self):
        """Shows USB CDC and REPL connectivity."""
        report = DiagnosticReport()
        report.usb_cdc_present = True
        report.repl_responsive = True

        md = generate_markdown(report)
        assert "USB CDC + REPL working" in md

    def test_no_faults_message(self):
        """Shows 'no faults' when CFSR/HFSR are clear."""
        report = DiagnosticReport()
        report.openocd_running = True
        report.target_responding = True
        report.cfsr = 0
        report.hfsr = 0

        md = generate_markdown(report)
        assert "No active faults" in md

    def test_fault_registers_displayed(self):
        """Shows fault register values when set."""
        report = DiagnosticReport()
        report.openocd_running = True
        report.target_responding = True
        report.cfsr = CFSR_NOCP      # FPU instruction without FPU
        report.hfsr = HFSR_FORCED    # Escalated fault

        md = generate_markdown(report)
        assert "## Faults" in md
        assert "CFSR:" in md
        assert "HFSR:" in md

    def test_vector_table_validation(self):
        """Shows vector table check results."""
        report = DiagnosticReport()
        report.openocd_running = True
        report.target_responding = True
        report.vector_sp = 0x20050000     # Valid RAM
        report.vector_reset = 0x08020001  # Valid Flash + thumb bit

        md = generate_markdown(report)
        assert "valid RAM" in md
        assert "valid Flash" in md

    def test_invalid_vectors_flagged(self):
        """Flags invalid vector table entries."""
        report = DiagnosticReport()
        report.openocd_running = True
        report.target_responding = True
        report.vector_sp = 0x00000000     # Invalid - null
        report.vector_reset = 0x08020001

        md = generate_markdown(report)
        assert "invalid" in md.lower()

    def test_summary_counts(self):
        """Summary shows error and warning counts."""
        report = DiagnosticReport()
        report.add("ERR", Level.ERROR, "Error")
        report.add("WARN", Level.WARN, "Warning")

        md = generate_markdown(report)
        assert "1 errors, 1 warnings" in md

    def test_primary_issue_shown(self):
        """Summary highlights first error as primary issue."""
        report = DiagnosticReport()
        report.add("CPU_STUCK", Level.ERROR, "PC not changing")
        report.add("HARDFAULT", Level.ERROR, "Fault detected")

        md = generate_markdown(report)
        assert "Primary issue: CPU_STUCK" in md


class TestSaveLog:
    """Tests for save_log() - writes report to log file."""

    def test_creates_log_file(self):
        """Should create log file in temp directory."""
        report = DiagnosticReport()
        content = "# Test Report\nTest content"

        log_path = save_log(report, content)

        assert log_path.exists()
        assert log_path.read_text() == content
        # Cleanup
        log_path.unlink()

    def test_log_filename_format(self):
        """Log filename should contain timestamp."""
        report = DiagnosticReport()
        content = "# Test"

        log_path = save_log(report, content)

        # Format: YYYY-MM-DD_HH-MM-SS.md
        assert log_path.suffix == ".md"
        assert "_" in log_path.stem
        # Cleanup
        log_path.unlink()

    def test_creates_log_directory(self):
        """Should create disco_log directory if missing."""
        report = DiagnosticReport()
        content = "# Test"

        log_path = save_log(report, content)

        # disco_log directory should exist
        assert log_path.parent.name == "disco_log"
        assert log_path.parent.exists()
        # Cleanup
        log_path.unlink()


class TestCheckTarget:
    """Tests for check_target() - verifies target is responding."""

    def test_returns_true_when_target_responds(self, ocd_mock_raw):
        """Should return True when PC can be read."""
        ocd_mock_raw.set_response("reg pc", "pc (/32): 0x08020000")
        report = DiagnosticReport()

        result = check_target(ocd_mock_raw, report)

        assert result is True
        assert report.target_responding is True
        assert report.pc == 0x08020000

    def test_returns_false_when_no_response(self, ocd_mock_raw):
        """Should return False when target doesn't respond."""
        ocd_mock_raw.set_response("reg pc", "Error: target not responding")
        ocd_mock_raw.set_response("halt", "")
        report = DiagnosticReport()

        result = check_target(ocd_mock_raw, report)

        assert result is False
        assert report.target_responding is False

    def test_halts_if_first_read_fails(self, ocd_mock_raw):
        """Should try halt if initial PC read fails."""
        # First read fails, then halt, then read succeeds
        responses = iter([
            "Error: no response",  # First reg pc
            "",                     # halt
            "pc (/32): 0x08020000"  # Second reg pc
        ])
        ocd_mock_raw.set_response("reg pc", "")  # Will be overridden

        def mock_send(cmd, timeout=2.0):
            ocd_mock_raw._commands.append(cmd)
            if cmd == "halt":
                ocd_mock_raw._halted = True
                return ""
            if cmd == "resume":
                ocd_mock_raw._halted = False
                return ""
            return next(responses, "pc (/32): 0x08020000")

        ocd_mock_raw.send = mock_send
        report = DiagnosticReport()

        result = check_target(ocd_mock_raw, report)

        # Should have halted and resumed
        assert "halt" in ocd_mock_raw._commands
        assert "resume" in ocd_mock_raw._commands

    def test_adds_error_diagnostic_on_failure(self, ocd_mock_raw):
        """Should add TARGET_NOT_RESPONDING diagnostic on failure."""
        ocd_mock_raw.set_response("reg pc", "")
        ocd_mock_raw.set_response("halt", "")
        report = DiagnosticReport()

        check_target(ocd_mock_raw, report)

        assert report.errors >= 1
        codes = [d.code for d in report.diagnostics]
        assert "TARGET_NOT_RESPONDING" in codes


class TestCaptureCpuState:
    """Tests for capture_cpu_state() - captures PC, SP, LR."""

    def test_captures_all_registers(self, ocd_mock_raw):
        """Should capture PC, SP, and LR."""
        ocd_mock_raw.set_response("reg pc", "pc (/32): 0x08020000")
        ocd_mock_raw.set_response("reg sp", "sp (/32): 0x20050000")
        ocd_mock_raw.set_response("reg lr", "lr (/32): 0x08020100")
        report = DiagnosticReport()

        capture_cpu_state(ocd_mock_raw, report)

        assert report.pc == 0x08020000
        assert report.sp == 0x20050000
        assert report.lr == 0x08020100

    def test_handles_parse_failures(self, ocd_mock_raw):
        """Should handle failed register reads gracefully."""
        ocd_mock_raw.set_response("reg pc", "Error: cannot read")
        ocd_mock_raw.set_response("reg sp", "Error: cannot read")
        ocd_mock_raw.set_response("reg lr", "Error: cannot read")
        report = DiagnosticReport()

        # Should not raise
        capture_cpu_state(ocd_mock_raw, report)

        # Should be 0 (default) when parse fails
        assert report.pc == 0
        assert report.sp == 0
        assert report.lr == 0

    def test_detects_halted_state(self, ocd_mock_raw):
        """Should detect if CPU was already halted."""
        # If PC doesn't change between reads, CPU is halted
        ocd_mock_raw.set_response("reg pc", "pc (/32): 0x08020000")
        ocd_mock_raw.set_response("reg sp", "sp (/32): 0x20050000")
        ocd_mock_raw.set_response("reg lr", "lr (/32): 0x08020100")
        report = DiagnosticReport()

        capture_cpu_state(ocd_mock_raw, report)

        # was_halted should be set based on PC comparison
        # (both reads return same PC = was halted)
        assert report.was_halted is True


class TestCheckCpuStuck:
    """Tests for check_cpu_stuck() - detects infinite loops."""

    def test_detects_stuck_cpu(self, ocd_mock_raw):
        """Should detect when PC doesn't change after step."""
        # All PC reads return same value
        ocd_mock_raw.set_response("reg pc", "pc (/32): 0x08020000")
        report = DiagnosticReport()
        report.pc = 0x08020000

        check_cpu_stuck(ocd_mock_raw, report)

        assert report.cpu_stuck is True
        codes = [d.code for d in report.diagnostics]
        assert "CPU_STUCK" in codes

    def test_not_stuck_when_pc_changes(self, ocd_mock_raw):
        """Should not flag stuck when PC changes after step."""
        # PC changes after each step
        pc_values = iter([0x08020004, 0x08020008])

        def mock_send(cmd, timeout=2.0):
            ocd_mock_raw._commands.append(cmd)
            if cmd == "reg pc":
                return f"pc (/32): 0x{next(pc_values, 0x08020000):08x}"
            return ""

        ocd_mock_raw.send = mock_send
        report = DiagnosticReport()
        report.pc = 0x08020000

        check_cpu_stuck(ocd_mock_raw, report)

        assert report.cpu_stuck is False

    def test_adds_error_diagnostic_when_stuck(self, ocd_mock_raw):
        """Should add CPU_STUCK diagnostic with PC value."""
        ocd_mock_raw.set_response("reg pc", "pc (/32): 0xDEADBEEF")
        report = DiagnosticReport()
        report.pc = 0xDEADBEEF

        check_cpu_stuck(ocd_mock_raw, report)

        # Should have error diagnostic with PC in details
        errors = [d for d in report.diagnostics if d.level == Level.ERROR]
        assert len(errors) >= 1
        assert "DEADBEEF" in errors[0].details.upper()

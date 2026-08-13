"""Tests for memory.py business logic.

The memory module provides high-level memory operations:
  - read_words(): Read 32-bit words from memory
  - read_vectors(): Read and parse ARM Cortex-M vector table
  - dump_to_file(): Dump memory region to binary file
"""

import os
import tempfile

import pytest

from disco_lib import memory


class TestReadWords:
    """Tests for read_words() - reads memory words via mdw command."""

    def test_formats_address_with_0x_prefix(self, ocd_mock_raw):
        """Address should be formatted with 0x prefix."""
        memory.read_words(ocd_mock_raw, 0x08000000, 8)
        assert "0x08000000" in ocd_mock_raw.commands[0]

    def test_formats_address_as_8_digits(self, ocd_mock_raw):
        """Address should be zero-padded to 8 hex digits."""
        memory.read_words(ocd_mock_raw, 0x100, 4)
        assert "0x00000100" in ocd_mock_raw.commands[0]

    def test_includes_count_parameter(self, ocd_mock_raw):
        """Count should be included in command."""
        memory.read_words(ocd_mock_raw, 0x08000000, 16)
        assert "16" in ocd_mock_raw.commands[0]

    def test_sends_mdw_command(self, ocd_mock_raw):
        """Should use OpenOCD mdw command."""
        memory.read_words(ocd_mock_raw, 0x08000000, 8)
        assert ocd_mock_raw.commands[0].startswith("mdw")

    def test_returns_raw_response(self, ocd_mock_raw):
        """Should return OpenOCD response as-is."""
        ocd_mock_raw.set_response(
            "mdw 0x08000000 4",
            "0x08000000: deadbeef cafebabe 12345678 87654321"
        )
        result = memory.read_words(ocd_mock_raw, 0x08000000, 4)
        assert "deadbeef" in result
        assert "cafebabe" in result

    def test_flash_base_address(self, ocd_mock_raw):
        """Common case: reading from flash base."""
        memory.read_words(ocd_mock_raw, 0x08000000, 8)
        cmd = ocd_mock_raw.commands[0]
        assert cmd == "mdw 0x08000000 8"

    def test_ram_address(self, ocd_mock_raw):
        """Reading from RAM region."""
        memory.read_words(ocd_mock_raw, 0x20000000, 4)
        cmd = ocd_mock_raw.commands[0]
        assert cmd == "mdw 0x20000000 4"


class TestReadVectors:
    """Tests for read_vectors() - parses ARM Cortex-M vector table.

    Vector table layout (first 8 words):
      [0] Initial SP
      [1] Reset handler
      [2] NMI handler
      [3] HardFault handler
      [4] MemManage handler
      [5] BusFault handler
      [6] UsageFault handler
      [7] Reserved
    """

    def test_reads_8_words_from_default_address(self, ocd_mock_raw):
        """Should read 8 words from 0x08000000 by default."""
        memory.read_vectors(ocd_mock_raw)
        assert "mdw 0x08000000 8" in ocd_mock_raw.commands

    def test_custom_vector_table_address(self, ocd_mock_raw):
        """Should support custom vector table address."""
        memory.read_vectors(ocd_mock_raw, addr=0x08020000)
        assert "mdw 0x08020000 8" in ocd_mock_raw.commands

    def test_parses_all_vectors(self, ocd_mock_raw):
        """Should parse all 8 vector entries."""
        ocd_mock_raw.set_response(
            "mdw 0x08000000 8",
            "0x08000000: 20050000 08020001 08030001 08040001 "
            "08050001 08060001 08070001 08080001"
        )
        vectors = memory.read_vectors(ocd_mock_raw)

        assert vectors["initial_sp"] == 0x20050000
        assert vectors["reset"] == 0x08020001
        assert vectors["nmi"] == 0x08030001
        assert vectors["hardfault"] == 0x08040001
        assert vectors["memmanage"] == 0x08050001
        assert vectors["busfault"] == 0x08060001
        assert vectors["usagefault"] == 0x08070001
        assert vectors["reserved"] == 0x08080001

    def test_initial_sp_in_ram(self, ocd_mock_raw):
        """Initial SP should typically point to RAM."""
        ocd_mock_raw.set_response(
            "mdw 0x08000000 8",
            "0x08000000: 2004fff8 08050e59 08046dfb 08046de9 "
            "08046df1 08046df5 08046df9 00000000"
        )
        vectors = memory.read_vectors(ocd_mock_raw)
        sp = vectors["initial_sp"]
        # STM32F469 RAM: 0x20000000 - 0x20060000
        assert 0x20000000 <= sp < 0x20060000

    def test_reset_handler_in_flash(self, ocd_mock_raw):
        """Reset handler should point to flash (with thumb bit)."""
        ocd_mock_raw.set_response(
            "mdw 0x08000000 8",
            "0x08000000: 20050000 08020001 08030001 08040001 "
            "08050001 08060001 08070001 08080001"
        )
        vectors = memory.read_vectors(ocd_mock_raw)
        reset = vectors["reset"]
        # Should be in flash, thumb bit (LSB) set
        assert reset & 1 == 1  # Thumb bit
        assert 0x08000000 <= (reset & ~1) < 0x08200000  # Flash range

    def test_includes_raw_response(self, ocd_mock_raw):
        """Should include raw OpenOCD output."""
        ocd_mock_raw.set_response(
            "mdw 0x08000000 8",
            "0x08000000: 20050000 08020001"
        )
        vectors = memory.read_vectors(ocd_mock_raw)
        assert "raw" in vectors
        assert "20050000" in vectors["raw"]

    def test_handles_unreadable_memory(self, ocd_mock_raw):
        """Unreadable memory (????????) should be captured in skipped list."""
        ocd_mock_raw.set_response(
            "mdw 0x08000000 8",
            "0x08000000: 20050000 ???????? 08030001 ???????? "
            "08050001 08060001 08070001 08080001"
        )
        vectors = memory.read_vectors(ocd_mock_raw)

        # Parsed values should be present
        assert vectors["initial_sp"] == 0x20050000
        assert vectors["nmi"] == 0x08030001

        # Unreadable values should be None and tracked
        assert vectors["reset"] is None
        assert vectors["hardfault"] is None
        assert "????????" in vectors["skipped"]
        assert len(vectors["skipped"]) == 2

    def test_handles_error_response(self, ocd_mock_raw):
        """Error response should result in all None values."""
        ocd_mock_raw.set_response(
            "mdw 0x08000000 8",
            "Error: target not responding"
        )
        vectors = memory.read_vectors(ocd_mock_raw)

        assert vectors["initial_sp"] is None
        assert vectors["reset"] is None
        assert vectors["raw"] == "Error: target not responding"

    def test_handles_empty_response(self, ocd_mock_raw):
        """Empty response should result in all None values."""
        ocd_mock_raw.set_response("mdw 0x08000000 8", "")
        vectors = memory.read_vectors(ocd_mock_raw)

        assert vectors["initial_sp"] is None
        assert vectors["reset"] is None

    def test_handles_partial_response(self, ocd_mock_raw):
        """Partial response should parse available values."""
        ocd_mock_raw.set_response(
            "mdw 0x08000000 8",
            "0x08000000: 20050000 08020001 08030001"  # Only 3 words
        )
        vectors = memory.read_vectors(ocd_mock_raw)

        assert vectors["initial_sp"] == 0x20050000
        assert vectors["reset"] == 0x08020001
        assert vectors["nmi"] == 0x08030001
        assert vectors["hardfault"] is None  # Not in response
        assert vectors["skipped"] == []

    def test_skipped_list_initially_empty(self, ocd_mock_raw):
        """Skipped list should be empty when all values parse."""
        ocd_mock_raw.set_response(
            "mdw 0x08000000 8",
            "0x08000000: 20050000 08020001 08030001 08040001 "
            "08050001 08060001 08070001 08080001"
        )
        vectors = memory.read_vectors(ocd_mock_raw)
        assert vectors["skipped"] == []


class TestDumpToFile:
    """Tests for dump_to_file() - dumps memory to binary file."""

    def test_sends_dump_image_command(self, ocd_mock_raw):
        """Should send OpenOCD dump_image command."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            tmp_path = f.name

        try:
            memory.dump_to_file(ocd_mock_raw, tmp_path, 0x08000000, 1024)
            cmd = ocd_mock_raw.commands[0]
            assert cmd.startswith("dump_image")
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_uses_absolute_path(self, ocd_mock_raw):
        """Should convert filepath to absolute path."""
        # Use a relative path
        relative_path = "test_dump.bin"
        memory.dump_to_file(ocd_mock_raw, relative_path, 0x08000000, 1024)

        cmd = ocd_mock_raw.commands[0]
        # Should contain absolute path (starts with /)
        assert "/" in cmd or "\\" in cmd  # Unix or Windows path

    def test_formats_address(self, ocd_mock_raw):
        """Address should be formatted with 0x prefix."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            tmp_path = f.name

        try:
            memory.dump_to_file(ocd_mock_raw, tmp_path, 0x08020000, 1024)
            cmd = ocd_mock_raw.commands[0]
            assert "0x08020000" in cmd
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_includes_size(self, ocd_mock_raw):
        """Size should be included in command."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            tmp_path = f.name

        try:
            memory.dump_to_file(ocd_mock_raw, tmp_path, 0x08000000, 0x10000)
            cmd = ocd_mock_raw.commands[0]
            assert "65536" in cmd  # 0x10000 = 65536
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_returns_true_when_file_exists(self, ocd_mock_raw):
        """Should return True if file was created."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            tmp_path = f.name
            f.write(b"test")  # File exists

        try:
            result = memory.dump_to_file(ocd_mock_raw, tmp_path, 0x08000000, 1024)
            assert result is True
        finally:
            os.unlink(tmp_path)

    def test_returns_false_when_file_missing(self, ocd_mock_raw):
        """Should return False if file was not created."""
        # Use a path that won't exist after the command
        tmp_path = "/tmp/nonexistent_dump_test_12345.bin"
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

        result = memory.dump_to_file(ocd_mock_raw, tmp_path, 0x08000000, 1024)
        assert result is False

    def test_default_timeout(self, ocd_mock_raw):
        """Default timeout should be 60 seconds."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            tmp_path = f.name

        try:
            # Can't easily test timeout was passed, but verify no error
            memory.dump_to_file(ocd_mock_raw, tmp_path, 0x08000000, 1024)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_custom_timeout(self, ocd_mock_raw):
        """Should accept custom timeout."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            tmp_path = f.name

        try:
            # Should not raise with custom timeout
            memory.dump_to_file(ocd_mock_raw, tmp_path, 0x08000000, 1024, timeout=120.0)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_large_dump_size(self, ocd_mock_raw):
        """Should handle large dump sizes (full flash)."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            tmp_path = f.name

        try:
            # 2MB flash dump
            memory.dump_to_file(ocd_mock_raw, tmp_path, 0x08000000, 2 * 1024 * 1024)
            cmd = ocd_mock_raw.commands[0]
            assert "2097152" in cmd  # 2MB in bytes
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

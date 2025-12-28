"""Tests for flash.py backend.

The flash module analyzes firmware binary files to understand their layout:
  - Code regions (non-zero data)
  - Zero regions (padding or filesystem preservation areas)

MicroPython firmware often has zeros between code regions to preserve
the internal filesystem during OTA updates. Understanding this layout
helps with smart verification and user feedback during flashing.
"""

from pathlib import Path

import pytest

from disco_lib.flash import (
    analyze_firmware,
    has_internal_zeros,
    get_code_regions,
    calculate_code_bytes,
    extract_version_tag,
    get_build_type,
    detect_flash_address,
    parse_rdp_level,
    read_option_bytes,
    unlock_rdp,
    lock_rdp,
)


class TestAnalyzeFirmware:
    """Tests for analyze_firmware() - scans binary for code/zero regions.

    Chunks the file (default 4KB) and classifies each as:
      - has_data=True: Contains at least one non-zero byte (code/data)
      - has_data=False: All zeros (padding/preserved area)

    Returns list of (start, end, has_data) tuples.
    """

    def test_all_code(self, tmp_path: Path):
        """File with all non-zero data = single code region."""
        # 8KB of 0xFF (like erased flash with data)
        path = tmp_path / "test.bin"
        path.write_bytes(b"\xff" * 8192)
        regions = analyze_firmware(str(path), chunk_size=4096)
        assert len(regions) == 1
        assert regions[0] == (0, 8192, True)  # all code

    def test_all_zeros(self, tmp_path: Path):
        """File with all zeros = single zero region."""
        path = tmp_path / "test.bin"
        path.write_bytes(b"\x00" * 8192)
        regions = analyze_firmware(str(path), chunk_size=4096)
        assert len(regions) == 1
        assert regions[0] == (0, 8192, False)  # all zeros

    def test_code_then_zeros(self, tmp_path: Path):
        """Code followed by zeros (trailing padding)."""
        # 4KB code + 4KB zeros
        data = (b"\xff" * 4096) + (b"\x00" * 4096)
        path = tmp_path / "test.bin"
        path.write_bytes(data)
        regions = analyze_firmware(str(path), chunk_size=4096)
        assert len(regions) == 2
        assert regions[0] == (0, 4096, True)      # code
        assert regions[1] == (4096, 8192, False)  # zeros

    def test_zeros_then_code(self, tmp_path: Path):
        """Zeros followed by code (unusual but valid)."""
        data = (b"\x00" * 4096) + (b"\xff" * 4096)
        path = tmp_path / "test.bin"
        path.write_bytes(data)
        regions = analyze_firmware(str(path), chunk_size=4096)
        assert len(regions) == 2
        assert regions[0] == (0, 4096, False)     # zeros
        assert regions[1] == (4096, 8192, True)   # code

    def test_code_zeros_code_pattern(self, tmp_path: Path):
        """Code-zeros-code = filesystem preservation pattern.

        This is the key pattern for MicroPython firmware updates:
        bootloader | zeros (filesystem) | main firmware
        """
        # 4KB code + 8KB zeros + 4KB code
        data = (b"\xff" * 4096) + (b"\x00" * 8192) + (b"\xff" * 4096)
        path = tmp_path / "test.bin"
        path.write_bytes(data)
        regions = analyze_firmware(str(path), chunk_size=4096)
        assert len(regions) == 3
        assert regions[0] == (0, 4096, True)       # bootloader
        assert regions[1] == (4096, 12288, False)  # preserved area
        assert regions[2] == (12288, 16384, True)  # main firmware

    def test_single_nonzero_byte_counts_as_code(self, tmp_path: Path):
        """Chunk with even one non-zero byte is classified as code."""
        # 4KB zeros except last byte
        data = (b"\x00" * 4095) + b"\x01"
        path = tmp_path / "test.bin"
        path.write_bytes(data)
        regions = analyze_firmware(str(path), chunk_size=4096)
        assert len(regions) == 1
        assert regions[0][2] is True  # has_data

    def test_small_chunk_size(self, tmp_path: Path):
        """Smaller chunk size gives finer granularity."""
        # 2 bytes code + 2 bytes zeros
        data = b"\xff\xff\x00\x00"
        path = tmp_path / "test.bin"
        path.write_bytes(data)
        regions = analyze_firmware(str(path), chunk_size=2)
        assert len(regions) == 2
        assert regions[0] == (0, 2, True)   # code
        assert regions[1] == (2, 4, False)  # zeros

    def test_file_not_aligned_to_chunk(self, tmp_path: Path):
        """Handles files not evenly divisible by chunk size."""
        # 5000 bytes (not divisible by 4096)
        data = b"\xff" * 5000
        path = tmp_path / "test.bin"
        path.write_bytes(data)
        regions = analyze_firmware(str(path), chunk_size=4096)
        # Should still cover full file
        total = sum(end - start for start, end, _ in regions)
        assert total == 5000


class TestHasInternalZeros:
    """Tests for has_internal_zeros() - detects filesystem preservation.

    Returns True if there are zero regions BETWEEN code regions.
    This pattern indicates the firmware preserves existing flash data
    in the zero areas during programming.

    Important: Trailing zeros don't count (just padding).
    """

    def test_no_zeros(self):
        """All code = no internal zeros."""
        regions = [(0, 4096, True)]  # just code
        assert has_internal_zeros(regions) is False

    def test_trailing_zeros_only(self):
        """Code followed by zeros = NOT internal (just padding)."""
        regions = [
            (0, 4096, True),      # code
            (4096, 8192, False),  # trailing zeros
        ]
        assert has_internal_zeros(regions) is False

    def test_leading_zeros_only(self):
        """Zeros followed by code = NOT internal."""
        regions = [
            (0, 4096, False),     # leading zeros
            (4096, 8192, True),   # code
        ]
        assert has_internal_zeros(regions) is False

    def test_internal_zeros_detected(self):
        """Code-zeros-code = HAS internal zeros (preservation pattern)."""
        regions = [
            (0, 4096, True),       # bootloader
            (4096, 12288, False),  # filesystem area
            (12288, 16384, True),  # main firmware
        ]
        assert has_internal_zeros(regions) is True

    def test_multiple_code_regions(self):
        """Multiple code regions with zeros between any = True."""
        regions = [
            (0, 4096, True),       # code 1
            (4096, 8192, False),   # zeros
            (8192, 12288, True),   # code 2
            (12288, 16384, False), # trailing zeros
        ]
        assert has_internal_zeros(regions) is True

    def test_alternating_pattern(self):
        """Complex alternating pattern."""
        regions = [
            (0, 1024, True),
            (1024, 2048, False),
            (2048, 3072, True),
            (3072, 4096, False),
            (4096, 5120, True),
        ]
        assert has_internal_zeros(regions) is True


class TestGetCodeRegions:
    """Tests for get_code_regions() - extracts code-only regions."""

    def test_filters_zeros(self):
        """Returns only regions with has_data=True."""
        regions = [
            (0, 4096, True),
            (4096, 8192, False),
            (8192, 12288, True),
        ]
        code = get_code_regions(regions)
        assert code == [(0, 4096), (8192, 12288)]

    def test_empty_on_all_zeros(self):
        """All zeros = empty list."""
        regions = [(0, 4096, False)]
        assert get_code_regions(regions) == []

    def test_all_code(self):
        """All code = single region."""
        regions = [(0, 8192, True)]
        assert get_code_regions(regions) == [(0, 8192)]


class TestCalculateCodeBytes:
    """Tests for calculate_code_bytes() - sums code region sizes."""

    def test_single_region(self):
        """Single code region."""
        regions = [(0, 4096, True)]
        assert calculate_code_bytes(regions) == 4096

    def test_multiple_regions(self):
        """Sum of multiple code regions."""
        regions = [
            (0, 4096, True),       # 4KB
            (4096, 8192, False),   # zeros (ignored)
            (8192, 16384, True),   # 8KB
        ]
        assert calculate_code_bytes(regions) == 4096 + 8192

    def test_no_code(self):
        """All zeros = 0 bytes."""
        regions = [(0, 8192, False)]
        assert calculate_code_bytes(regions) == 0

    def test_realistic_firmware_size(self):
        """Realistic firmware: ~1MB code + 500KB preserved."""
        regions = [
            (0, 128 * 1024, True),           # 128KB bootloader
            (128 * 1024, 640 * 1024, False), # 512KB filesystem
            (640 * 1024, 1664 * 1024, True), # 1MB main firmware
        ]
        expected = 128 * 1024 + 1024 * 1024  # 128KB + 1MB
        assert calculate_code_bytes(regions) == expected


class TestAnalyzeFirmwareErrors:
    """Error path tests for analyze_firmware()."""

    def test_empty_file(self, tmp_path: Path):
        """Empty file should return empty regions list."""
        path = tmp_path / "empty.bin"
        path.write_bytes(b"")
        regions = analyze_firmware(str(path))
        assert regions == []

    def test_file_not_found(self):
        """Non-existent file should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            analyze_firmware("/nonexistent/path/firmware.bin")

    def test_tiny_file(self, tmp_path: Path):
        """Single byte file should still work."""
        path = tmp_path / "tiny.bin"
        path.write_bytes(b"\xff")
        regions = analyze_firmware(str(path))
        assert len(regions) == 1
        assert regions[0] == (0, 1, True)

    def test_single_zero_byte(self, tmp_path: Path):
        """Single zero byte should be classified as blank."""
        path = tmp_path / "zero.bin"
        path.write_bytes(b"\x00")
        regions = analyze_firmware(str(path))
        assert len(regions) == 1
        assert regions[0] == (0, 1, False)


class TestExtractVersionTag:
    """Tests for extract_version_tag() - parses version from firmware.

    Version tags are embedded in firmware like:
        <version:tag10>0100900099</version:tag10>
    """

    def test_extracts_production_tag(self):
        """Should extract production version tag."""
        data = b"prefix<version:tag10>0100900099</version:tag10>suffix"
        assert extract_version_tag(data) == "0100900099"

    def test_extracts_debug_tag(self):
        """Should extract debug version tag."""
        data = b"<version:tag10>0100900001</version:tag10>"
        assert extract_version_tag(data) == "0100900001"

    def test_returns_none_when_no_tag(self):
        """Should return None when no version tag present."""
        data = b"firmware data without version tag"
        assert extract_version_tag(data) is None

    def test_returns_none_on_empty_data(self):
        """Should return None on empty input."""
        assert extract_version_tag(b"") is None

    def test_malformed_tag_no_closing(self):
        """Malformed tag (no closing) should return None."""
        data = b"<version:tag10>0100900099"  # no closing tag
        assert extract_version_tag(data) is None

    def test_malformed_tag_wrong_name(self):
        """Wrong tag name should return None."""
        data = b"<version:tag11>0100900099</version:tag11>"
        assert extract_version_tag(data) is None

    def test_empty_tag_value(self):
        """Empty tag value should return empty string."""
        data = b"<version:tag10></version:tag10>"
        assert extract_version_tag(data) == ""

    def test_binary_in_tag_value(self):
        """Binary data in tag should be decoded with replacement."""
        data = b"<version:tag10>\xff\xfe\x00</version:tag10>"
        result = extract_version_tag(data)
        # Should not crash, uses errors="replace"
        assert result is not None
        assert "\ufffd" in result  # Replacement character

    def test_tag_in_large_firmware(self):
        """Should find tag even in large firmware."""
        # 1MB of zeros with tag in the middle
        prefix = b"\x00" * 500_000
        tag = b"<version:tag10>0100900099</version:tag10>"
        suffix = b"\x00" * 500_000
        data = prefix + tag + suffix
        assert extract_version_tag(data) == "0100900099"

    def test_first_tag_wins(self):
        """If multiple tags, first one should be returned."""
        data = b"<version:tag10>first</version:tag10><version:tag10>second</version:tag10>"
        assert extract_version_tag(data) == "first"


class TestGetBuildType:
    """Tests for get_build_type() - maps version tag to build type."""

    def test_production_tag(self):
        """Production version tag."""
        assert get_build_type("0100900099") == "production"

    def test_debug_tag(self):
        """Debug version tag."""
        assert get_build_type("0100900001") == "debug"

    def test_unknown_tag(self):
        """Unknown version tag."""
        assert get_build_type("9999999999") == "unknown"

    def test_none_tag(self):
        """None version tag."""
        assert get_build_type(None) == "unknown"

    def test_empty_string(self):
        """Empty string version tag."""
        assert get_build_type("") == "unknown"

    def test_similar_but_different_tag(self):
        """Similar but not exact match should be unknown."""
        assert get_build_type("0100900098") == "unknown"
        assert get_build_type("0100900002") == "unknown"


class TestDetectFlashAddress:
    """Tests for detect_flash_address() - determines correct flash address.

    Returns:
        0x08000000 for initial/full images (with bootloader)
        0x08020000 for upgrade images (main firmware only)
    """

    def test_single_code_region_no_fs(self):
        """Single code region without fs preservation = upgrade (0x08020000)."""
        regions = [(0, 1024 * 1024, True)]  # 1MB code
        assert detect_flash_address(regions, fs_preservation=False) == 0x08020000

    def test_fs_preservation_pattern(self):
        """Filesystem preservation pattern = initial (0x08000000)."""
        regions = [
            (0, 0x20000, True),           # Bootloader
            (0x20000, 0x100000, False),   # FS area
            (0x100000, 0x200000, True),   # Main firmware
        ]
        assert detect_flash_address(regions, fs_preservation=True) == 0x08000000

    def test_small_bootloader_region(self):
        """Small code region at start = initial (0x08000000)."""
        regions = [
            (0, 0x8000, True),            # 32KB bootloader
            (0x8000, 0x100000, True),     # Main code
        ]
        # Has small region at start < 0x20000 and <= 0x10000 in size
        assert detect_flash_address(regions, fs_preservation=False) == 0x08000000

    def test_no_code_regions(self):
        """No code regions (all zeros) = default 0x08020000."""
        regions = [(0, 0x100000, False)]  # All zeros
        assert detect_flash_address(regions, fs_preservation=False) == 0x08020000

    def test_empty_regions_list(self):
        """Empty regions list = default 0x08020000."""
        regions = []
        assert detect_flash_address(regions, fs_preservation=False) == 0x08020000

    def test_large_single_region_at_start(self):
        """Large code region at start (> 64KB) = upgrade firmware."""
        regions = [(0, 0x100000, True)]  # 1MB, starts at 0, but too large for bootloader
        # This doesn't match bootloader pattern (size > 0x10000)
        # And no fs_preservation, so should be upgrade
        assert detect_flash_address(regions, fs_preservation=False) == 0x08020000

    def test_multiple_regions_without_fs(self):
        """Multiple code regions but no fs preservation."""
        regions = [
            (0, 0x8000, True),      # Small first region
            (0x8000, 0x10000, True),  # Another code region
        ]
        # Small first region < 0x20000 and <= 0x10000 = initial
        assert detect_flash_address(regions, fs_preservation=False) == 0x08000000


class TestParseRdpLevel:
    """Tests for parse_rdp_level() - parses RDP level from options_read output.

    STM32F4 RDP levels:
      0 (0xAA): No protection
      1 (other): Flash protected
      2 (0xCC): Permanent lock
    """

    def test_rdp_level_0_from_byte(self):
        """RDP byte 0xAA = Level 0 (no protection)."""
        output = "Option bytes: RDP 0xAA nWRP 0x0FFF"
        assert parse_rdp_level(output) == 0

    def test_rdp_level_1_from_byte(self):
        """Any byte except 0xAA/0xCC = Level 1."""
        output = "Option bytes: RDP 0x00 nWRP 0x0FFF"
        assert parse_rdp_level(output) == 1

    def test_rdp_level_1_from_0xff(self):
        """RDP byte 0xFF = Level 1."""
        output = "Option bytes: RDP 0xFF nWRP 0x0FFF"
        assert parse_rdp_level(output) == 1

    def test_rdp_level_2_from_byte(self):
        """RDP byte 0xCC = Level 2 (permanent)."""
        output = "Option bytes: RDP 0xCC nWRP 0x0FFF"
        assert parse_rdp_level(output) == 2

    def test_alternate_format_level_0(self):
        """Alternate OpenOCD format: 'read protection: 0'."""
        output = "read protection: 0"
        assert parse_rdp_level(output) == 0

    def test_alternate_format_level_1(self):
        """Alternate OpenOCD format: 'read protection: 1'."""
        output = "Read Protection: 1"  # Case insensitive
        assert parse_rdp_level(output) == 1

    def test_alternate_format_level_2(self):
        """Alternate OpenOCD format: 'read protection: 2'."""
        output = "READ PROTECTION: 2"
        assert parse_rdp_level(output) == 2

    def test_returns_none_on_empty(self):
        """Empty string returns None."""
        assert parse_rdp_level("") is None

    def test_returns_none_on_error(self):
        """Error message returns None."""
        assert parse_rdp_level("Error: target not responding") is None

    def test_returns_none_on_garbage(self):
        """Garbage output returns None."""
        assert parse_rdp_level("some random text") is None

    def test_lowercase_rdp_byte(self):
        """Should handle lowercase hex."""
        output = "Option bytes: RDP 0xaa nWRP 0x0FFF"
        assert parse_rdp_level(output) == 0

    def test_mixed_case_rdp_byte(self):
        """Should handle mixed case hex."""
        output = "Option bytes: RDP 0xAa nWRP 0x0FFF"
        assert parse_rdp_level(output) == 0


class TestReadOptionBytes:
    """Tests for read_option_bytes() - sends options_read command."""

    def test_sends_correct_command(self, ocd_mock_raw):
        """Should send 'stm32f4x options_read 0'."""
        read_option_bytes(ocd_mock_raw)
        assert "stm32f4x options_read 0" in ocd_mock_raw.commands

    def test_returns_raw_output(self, ocd_mock_raw):
        """Should return raw OpenOCD output."""
        ocd_mock_raw.set_response(
            "stm32f4x options_read 0",
            "Option bytes: RDP 0xAA nWRP 0x0FFF"
        )
        result = read_option_bytes(ocd_mock_raw)
        assert "RDP 0xAA" in result


class TestUnlockRdp:
    """Tests for unlock_rdp() - sends unlock command."""

    def test_sends_correct_command(self, ocd_mock_raw):
        """Should send 'stm32f4x unlock 0'."""
        unlock_rdp(ocd_mock_raw)
        assert "stm32f4x unlock 0" in ocd_mock_raw.commands

    def test_returns_raw_output(self, ocd_mock_raw):
        """Should return raw OpenOCD output."""
        ocd_mock_raw.set_response(
            "stm32f4x unlock 0",
            "stm32f4x unlock succeeded"
        )
        result = unlock_rdp(ocd_mock_raw)
        assert "unlock succeeded" in result


class TestLockRdp:
    """Tests for lock_rdp() - sends lock command."""

    def test_sends_correct_command(self, ocd_mock_raw):
        """Should send 'stm32f4x lock 0'."""
        lock_rdp(ocd_mock_raw)
        assert "stm32f4x lock 0" in ocd_mock_raw.commands

    def test_returns_raw_output(self, ocd_mock_raw):
        """Should return raw OpenOCD output."""
        ocd_mock_raw.set_response(
            "stm32f4x lock 0",
            "stm32f4x lock succeeded"
        )
        result = lock_rdp(ocd_mock_raw)
        assert "lock succeeded" in result

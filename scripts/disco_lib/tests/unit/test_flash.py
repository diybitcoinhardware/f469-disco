"""Tests for flash.py backend.

The flash module analyzes firmware binary files to understand their layout:
  - Code regions (non-zero data)
  - Zero regions (padding or filesystem preservation areas)

MicroPython firmware often has zeros between code regions to preserve
the internal filesystem during OTA updates. Understanding this layout
helps with smart verification and user feedback during flashing.
"""

from pathlib import Path

from disco_lib.flash import (
    analyze_firmware,
    has_internal_zeros,
    get_code_regions,
    calculate_code_bytes,
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

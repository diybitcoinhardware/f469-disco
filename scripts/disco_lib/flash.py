"""Flash analysis backend."""

import hashlib
import os
import re
from typing import List, Tuple, Dict, Any

from . import diagnostics
from .openocd import OpenOCD
from .serial import SerialDevice


def _is_blank_chunk(chunk: bytes) -> bool:
    """Check if chunk is blank (all 0x00).

    Note: We check for 0x00 (zeros) rather than 0xFF (erased flash) because
    MicroPython firmware uses zeros as padding between code regions to preserve
    the internal filesystem. When flashed, zero bytes don't overwrite existing
    flash content in smart programming modes, while 0xFF would.
    """
    if not chunk:
        return True
    return all(b == 0x00 for b in chunk)


def analyze_firmware(filepath: str, chunk_size: int = 4096) -> List[Tuple[int, int, bool]]:
    """Analyze firmware file to find code vs blank regions.

    Returns list of (start, end, has_code) tuples.
    Blank regions are all 0x00 (zeros for filesystem preservation).
    """
    with open(filepath, "rb") as f:
        data = f.read()

    regions = []
    i = 0
    while i < len(data):
        chunk = data[i:i + chunk_size]
        has_code = not _is_blank_chunk(chunk)

        # Extend region while same type
        start = i
        while i < len(data):
            chunk = data[i:i + chunk_size]
            chunk_has_code = not _is_blank_chunk(chunk)
            if chunk_has_code != has_code:
                break
            i += chunk_size

        regions.append((start, min(i, len(data)), has_code))

    return regions


def has_internal_zeros(regions: List[Tuple[int, int, bool]]) -> bool:
    """Check if firmware has zero regions between code regions.

    This pattern indicates filesystem preservation - zeros between code
    regions won't overwrite existing flash data when programmed.
    """
    code_seen = False
    for start, end, has_data in regions:
        if has_data:
            code_seen = True
        elif code_seen and not has_data:
            # Zero region after code - check if more code follows
            idx = regions.index((start, end, has_data))
            if any(hd for _, _, hd in regions[idx + 1:]):
                return True
    return False


def get_code_regions(regions: List[Tuple[int, int, bool]]) -> List[Tuple[int, int]]:
    """Extract code regions (start, end) from analyzed regions."""
    return [(s, e) for s, e, has_data in regions if has_data]


def calculate_code_bytes(regions: List[Tuple[int, int, bool]]) -> int:
    """Calculate total code bytes from regions."""
    return sum(e - s for s, e, has_data in regions if has_data)


def extract_version_tag(data: bytes) -> str | None:
    """Extract version tag from firmware binary."""
    pattern = rb'<version:tag10>([^<]*)</version:tag10>'
    match = re.search(pattern, data)
    return match.group(1).decode("utf-8", errors="replace") if match else None


def get_build_type(version_tag: str | None) -> str:
    """Determine build type from version tag."""
    if version_tag is None:
        return "unknown"
    if version_tag == "0100900099":
        return "production"
    if version_tag == "0100900001":
        return "debug"
    return "unknown"


def detect_flash_address(regions: List[Tuple[int, int, bool]], fs_preservation: bool) -> int:
    """Auto-detect correct flash address based on firmware layout.

    Returns:
        0x08000000 for initial/full images (with bootloader)
        0x08020000 for upgrade images (main firmware only)
    """
    code_regions = [(s, e) for s, e, has_data in regions if has_data]

    # Single code region without fs preservation = upgrade firmware
    if len(code_regions) == 1 and not fs_preservation:
        return 0x08020000

    # Multiple regions with gaps = initial firmware
    if fs_preservation:
        return 0x08000000

    # Has small bootloader-like region at start = initial
    for start, end, has_data in regions:
        if has_data and start < 0x20000 and (end - start) <= 0x10000:
            return 0x08000000

    # Default to 0x08020000 (safer - won't overwrite bootloader)
    return 0x08020000


def generate_fingerprint(filepath: str) -> Dict[str, Any]:
    """Generate fingerprint dictionary for a firmware file."""
    filepath = os.path.abspath(filepath)
    filename = os.path.basename(filepath)
    dirname = os.path.basename(os.path.dirname(filepath))

    with open(filepath, "rb") as f:
        data = f.read()

    sha256 = hashlib.sha256(data).hexdigest()
    regions = analyze_firmware(filepath)
    version_tag = extract_version_tag(data)
    build_type = get_build_type(version_tag)
    fs_preservation = has_internal_zeros(regions)
    flash_addr = detect_flash_address(regions, fs_preservation)

    # Label regions with smarter logic
    code_regions = [(s, e, e - s) for s, e, has_data in regions if has_data]
    num_code_regions = len(code_regions)

    # Find the largest code region (main firmware)
    main_region = max(code_regions, key=lambda x: x[2]) if code_regions else None
    main_start = main_region[0] if main_region else None

    region_list = []
    for start, end, has_data in regions:
        size = end - start
        if has_data:
            if num_code_regions == 1:
                # Single code region - it's the full firmware
                label = "firmware"
            elif start == main_start:
                # Largest code region is main firmware
                label = "main"
            elif start < 0x20000 and size <= 0x10000:
                # Small code in bootloader area (< 64KB before 0x20000)
                label = "bootloader"
            elif size < 0x10000:
                # Small code regions elsewhere are metadata/integrity
                label = "metadata"
            else:
                label = "code"
            rtype = "code"
        else:
            # Blank regions
            if start >= 0x4000 and start < 0x20000:
                label = "flash_storage"
            else:
                label = "preserved"
            rtype = "blank"

        region_list.append({
            "start": f"0x{start:08x}",
            "end": f"0x{end:08x}",
            "size": end - start,
            "type": rtype,
            "label": label,
        })

    return {
        "name": dirname,
        "filename": filename,
        "static": {
            "size_bytes": len(data),
            "sha256": sha256,
            "regions": region_list,
            "version_tag": version_tag,
            "build_type": build_type,
            "filesystem_preservation": fs_preservation,
            "flash_address": f"0x{flash_addr:08x}",
        },
        "runtime": {
            "jtag_works": None,
            "cpu_runs": None,
            "usb_cdc": None,
            "repl_responsive": None,
        },
        "notes": "",
    }


def test_runtime(ocd: OpenOCD, ser: SerialDevice) -> Dict[str, bool | None]:
    """Run runtime tests and return results dict.

    Tests:
    - jtag_works: OpenOCD running and target responds
    - cpu_runs: PC is in firmware area
    - usb_cdc: USB OTG serial device present
    - repl_responsive: MicroPython REPL responds
    """
    report = diagnostics.DiagnosticReport()

    # Check JTAG/OpenOCD
    jtag_works = False
    cpu_runs = False

    if diagnostics.check_openocd(ocd, report):
        if diagnostics.check_target(ocd, report):
            jtag_works = True
            # Check PC is in firmware area - that's enough to say CPU runs
            cpu_runs = (diagnostics.FIRMWARE_START <= report.pc < diagnostics.FLASH_END)

    # Check USB/REPL
    diagnostics.check_usb(ser, report)

    return {
        "jtag_works": jtag_works,
        "cpu_runs": cpu_runs,
        "usb_cdc": report.usb_cdc_present,
        "repl_responsive": report.repl_responsive,
    }


def program_firmware(
    ocd: OpenOCD,
    filepath: str,
    addr: int = 0x08020000,
    verify: bool = False,
    reset: bool = True,
    timeout: int = 0,
) -> bool:
    """Program firmware to flash.

    Args:
        ocd: OpenOCD instance (must be running)
        filepath: Path to firmware file
        addr: Flash address (default 0x08020000)
        verify: Verify after programming
        reset: Reset after programming
        timeout: Timeout in seconds (0=auto)

    Returns:
        True if programming succeeded
    """
    import os

    filepath = os.path.abspath(filepath)
    size = os.path.getsize(filepath)

    if timeout == 0:
        size_mb = size / (1024 * 1024)
        timeout = int(30 + (size_mb * 40))
        if verify:
            timeout += int(size_mb * 20)

    ocd.send("halt")

    cmd = f"program {filepath} 0x{addr:08x}"
    if verify:
        cmd += " verify"
    if reset:
        cmd += " reset"

    result = ocd.send(cmd, timeout=timeout)
    result_lower = result.lower()

    if "error" in result_lower or "failed" in result_lower:
        return False
    return True


def verify_firmware(
    ocd: OpenOCD,
    filepath: str,
    addr: int = 0x08000000,
    smart: bool = True,
) -> bool:
    """Verify flash contents against firmware file.

    Args:
        ocd: OpenOCD instance (must be running)
        filepath: Path to firmware file
        addr: Flash base address
        smart: If True, only verify code regions (skip zeros)

    Returns:
        True if verification passed
    """
    import tempfile

    filepath = os.path.abspath(filepath)
    regions = analyze_firmware(filepath)
    code_regions = get_code_regions(regions)
    internal_zeros = has_internal_zeros(regions)

    # Use longer timeout for halt - target may be booting after reset
    ocd.send("halt", timeout=10)

    try:
        if smart and internal_zeros and len(code_regions) > 0:
            # Smart verify: only check code regions
            for region_start, region_end in code_regions:
                region_size = region_end - region_start
                flash_addr = addr + region_start

                with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as tmp:
                    tmp_path = tmp.name

                read_timeout = max(60, int(region_size / (50 * 1024)) + 30)
                ocd.send(f"dump_image {tmp_path} 0x{flash_addr:x} {region_size}", timeout=read_timeout)

                try:
                    with open(filepath, "rb") as f:
                        f.seek(region_start)
                        file_data = f.read(region_size)

                    with open(tmp_path, "rb") as f:
                        flash_data = f.read()

                    os.unlink(tmp_path)

                    if file_data != flash_data:
                        return False
                except Exception:
                    return False

            return True
        else:
            # Full verify via OpenOCD
            size = os.path.getsize(filepath)
            timeout = max(60, int(size / (50 * 1024)) + 30)
            result = ocd.send(f"verify_image {filepath} 0x{addr:08x}", timeout=timeout)
            result_lower = result.lower()
            return "verified" in result_lower and "error" not in result_lower
    finally:
        # Always resume CPU after verification
        ocd.send("resume")


def compare_fingerprints(
    fp1: Dict[str, Any],
    fp2: Dict[str, Any],
    static_only: bool = False,
) -> Dict[str, Any]:
    """Compare two fingerprints and return differences.

    Args:
        fp1: Expected fingerprint
        fp2: Actual fingerprint
        static_only: If True, skip runtime field comparison

    Returns dict with keys that differ. Empty dict means identical.
    """
    diffs = {}

    # Compare static fields
    for key in ["size_bytes", "sha256", "version_tag", "build_type", "filesystem_preservation", "flash_address"]:
        v1 = fp1.get("static", {}).get(key)
        v2 = fp2.get("static", {}).get(key)
        if v1 != v2:
            diffs[f"static.{key}"] = {"expected": v1, "actual": v2}

    # Compare regions count
    r1 = fp1.get("static", {}).get("regions", [])
    r2 = fp2.get("static", {}).get("regions", [])
    if len(r1) != len(r2):
        diffs["static.regions_count"] = {"expected": len(r1), "actual": len(r2)}

    # Compare runtime fields (unless static_only)
    if not static_only:
        for key in ["jtag_works", "cpu_runs", "usb_cdc", "repl_responsive"]:
            v1 = fp1.get("runtime", {}).get(key)
            v2 = fp2.get("runtime", {}).get(key)
            # Only compare if expected value is set (not None)
            if v1 is not None and v1 != v2:
                diffs[f"runtime.{key}"] = {"expected": v1, "actual": v2}

    return diffs


# ============================================================================
# Low-level flash operations (wrappers around OpenOCD commands)
# ============================================================================


def read_info(ocd: OpenOCD) -> str:
    """Get flash bank info from OpenOCD.

    Returns the raw OpenOCD 'flash info 0' output.
    """
    return ocd.send("flash info 0")


def erase_all(ocd: OpenOCD) -> str:
    """Erase all flash sectors.

    WARNING: This erases ALL flash including bootloader.
    CPU should be halted before calling.

    Returns the raw OpenOCD output.
    """
    return ocd.send("flash erase_sector 0 0 last")


def dump_image(
    ocd: OpenOCD,
    filepath: str,
    addr: int,
    size: int,
    timeout: float = 60.0,
) -> str:
    """Dump flash/memory region to binary file.

    Args:
        ocd: OpenOCD instance
        filepath: Output file path
        addr: Start address
        size: Number of bytes to dump
        timeout: Command timeout in seconds

    Returns:
        Raw OpenOCD output string
    """
    filepath = os.path.abspath(filepath)
    return ocd.send(f"dump_image {filepath} 0x{addr:08x} {size}", timeout=timeout)

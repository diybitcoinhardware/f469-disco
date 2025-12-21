"""Flash analysis backend."""

import hashlib
import os
import re
from typing import List, Tuple, Dict, Any

from . import diagnostics
from .openocd import OpenOCD
from .serial import SerialDevice


def analyze_firmware(filepath: str, chunk_size: int = 4096) -> List[Tuple[int, int, bool]]:
    """Analyze firmware file to find code vs zero regions.

    Returns list of (start, end, has_data) tuples.
    """
    with open(filepath, "rb") as f:
        data = f.read()

    regions = []
    i = 0
    while i < len(data):
        chunk = data[i:i + chunk_size]
        has_data = any(b != 0 for b in chunk)

        # Extend region while same type
        start = i
        while i < len(data):
            chunk = data[i:i + chunk_size]
            chunk_has_data = any(b != 0 for b in chunk)
            if chunk_has_data != has_data:
                break
            i += chunk_size

        regions.append((start, min(i, len(data)), has_data))

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

    # Label regions
    region_list = []
    code_idx = 0
    for start, end, has_data in regions:
        if has_data:
            if code_idx == 0 and start == 0:
                label = "bootloader"
            else:
                label = "main"
            code_idx += 1
            rtype = "code"
        else:
            label = "preserved"
            rtype = "zeros"

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


def compare_fingerprints(fp1: Dict[str, Any], fp2: Dict[str, Any]) -> Dict[str, Any]:
    """Compare two fingerprints and return differences.

    Returns dict with keys that differ. Empty dict means identical.
    """
    diffs = {}

    # Compare static fields
    for key in ["size_bytes", "sha256", "version_tag", "build_type", "filesystem_preservation"]:
        v1 = fp1.get("static", {}).get(key)
        v2 = fp2.get("static", {}).get(key)
        if v1 != v2:
            diffs[f"static.{key}"] = {"expected": v1, "actual": v2}

    # Compare regions count
    r1 = fp1.get("static", {}).get("regions", [])
    r2 = fp2.get("static", {}).get("regions", [])
    if len(r1) != len(r2):
        diffs["static.regions_count"] = {"expected": len(r1), "actual": len(r2)}

    # Compare runtime fields
    for key in ["jtag_works", "cpu_runs", "usb_cdc", "repl_responsive"]:
        v1 = fp1.get("runtime", {}).get(key)
        v2 = fp2.get("runtime", {}).get(key)
        # Only compare if expected value is set (not None)
        if v1 is not None and v1 != v2:
            diffs[f"runtime.{key}"] = {"expected": v1, "actual": v2}

    return diffs

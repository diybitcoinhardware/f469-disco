"""Integration tests for fingerprint static verification.

These tests run `disco flash fingerprint test --static-only` against
fingerprints in the fwbox directory. They verify firmware files match their
recorded fingerprints without requiring hardware.

Can run in CI.
"""

import subprocess
from pathlib import Path

import pytest


# Find all fingerprint.yaml files in fwbox
FWBOX_DIR = Path(__file__).parent.parent.parent.parent.parent / "tests" / "fwbox"
DISCO_SCRIPT = Path(__file__).parent.parent.parent.parent / "disco"


def find_fingerprints():
    """Find all fingerprint.yaml files in fwbox."""
    if not FWBOX_DIR.exists():
        return []
    return list(FWBOX_DIR.rglob("fingerprint.yaml"))


def fingerprint_id(fp_path: Path) -> str:
    """Generate test ID from fingerprint path."""
    # Get path relative to fwbox
    rel = fp_path.relative_to(FWBOX_DIR)
    # Remove fingerprint.yaml and join with /
    return str(rel.parent)


FINGERPRINTS = find_fingerprints()


@pytest.mark.parametrize("fingerprint_path", FINGERPRINTS, ids=fingerprint_id)
def test_fingerprint_static_match(fingerprint_path: Path):
    """Test that firmware matches its fingerprint (static only, no hardware)."""
    result = subprocess.run(
        [str(DISCO_SCRIPT), "flash", "fingerprint", "test", str(fingerprint_path), "--static-only"],
        capture_output=True,
        text=True,
        timeout=30,
    )

    # Check exit code
    assert result.returncode == 0, (
        f"Fingerprint test failed for {fingerprint_path}\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )

    # Verify success message
    assert "All tests passed" in result.stdout, (
        f"Expected success message not found\n"
        f"stdout: {result.stdout}"
    )


def test_fwbox_has_fingerprints():
    """Sanity check: fwbox should have fingerprint files."""
    assert len(FINGERPRINTS) > 0, f"No fingerprints found in {FWBOX_DIR}"
    # We expect the 6 non-release fingerprints
    # (new/debug, new/main, old/debug, old/main, spflashbug, upy-current)
    assert len(FINGERPRINTS) == 6, f"Expected 6 fingerprints, found {len(FINGERPRINTS)}: {[str(p.relative_to(FWBOX_DIR).parent) for p in FINGERPRINTS]}"

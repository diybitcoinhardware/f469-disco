"""Flash analysis backend."""

from typing import List, Tuple


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

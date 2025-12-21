"""Architecture violation tests.

These tests enforce that command handlers use business layer functions
instead of calling ocd.send() directly. This ensures proper separation
of concerns and makes the code more testable.
"""

import ast
from pathlib import Path

import pytest


COMMANDS_DIR = Path(__file__).parent.parent.parent / "commands"

# Commands that are ALLOWED to call ocd.send() directly
# ocd.py is the low-level OCD interface command
ALLOWED_DIRECT_OCD_CALLS = {"ocd.py"}


def _is_ocd_send_call(node: ast.Call) -> bool:
    """Check if AST node is a call to ocd.send() or get_ocd().send()."""
    # Pattern 1: get_ocd().send(...)
    if isinstance(node.func, ast.Attribute):
        if node.func.attr == "send":
            # Check if it's get_ocd().send()
            if isinstance(node.func.value, ast.Call):
                if isinstance(node.func.value.func, ast.Name):
                    if node.func.value.func.id == "get_ocd":
                        return True
            # Check if it's ocd.send() where ocd is a variable
            if isinstance(node.func.value, ast.Name):
                if node.func.value.id == "ocd":
                    return True
    return False


def _find_ocd_send_calls(filepath: Path) -> list[tuple[int, str]]:
    """Find all ocd.send() calls in a Python file.

    Returns list of (line_number, code_snippet) tuples.
    """
    violations = []
    try:
        source = filepath.read_text()
        tree = ast.parse(source)
        lines = source.splitlines()

        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and _is_ocd_send_call(node):
                line_num = node.lineno
                code = lines[line_num - 1].strip() if line_num <= len(lines) else ""
                violations.append((line_num, code))
    except SyntaxError:
        pass  # Skip files with syntax errors

    return violations


class TestArchitectureViolations:
    """Tests for architecture rule violations."""

    def test_commands_do_not_call_ocd_send_directly(self):
        """Command handlers must use business functions, not ocd.send().

        Commands should call functions from:
        - disco_lib.cpu (halt, resume, halted context manager, read_pc, etc.)
        - disco_lib.memory (read_words, dump_to_file, etc.)
        - disco_lib.flash (read_info, erase_all, program_firmware, etc.)

        NOT:
        - get_ocd().send("halt")
        - ocd.send("mdw 0x08000000 8")
        """
        all_violations = []

        for py_file in sorted(COMMANDS_DIR.glob("*.py")):
            if py_file.name in ALLOWED_DIRECT_OCD_CALLS:
                continue
            if py_file.name.startswith("__"):
                continue

            violations = _find_ocd_send_calls(py_file)
            for line_num, code in violations:
                all_violations.append(f"{py_file.name}:{line_num}: {code}")

        if all_violations:
            msg = (
                f"Found {len(all_violations)} direct ocd.send() calls in commands.\n"
                "Commands should use business layer functions instead:\n"
                "  - cpu.halt(ocd), cpu.resume(ocd), cpu.halted(ocd) context manager\n"
                "  - memory.read_words(ocd, addr, count)\n"
                "  - flash.read_info(ocd), flash.erase_all(ocd)\n"
                "\nViolations:\n" + "\n".join(f"  {v}" for v in all_violations)
            )
            pytest.fail(msg)

    def test_allowed_files_exist(self):
        """Verify that allowed files actually exist."""
        for allowed in ALLOWED_DIRECT_OCD_CALLS:
            assert (COMMANDS_DIR / allowed).exists(), f"Allowed file {allowed} not found"


class TestBusinessLayerExists:
    """Tests that business layer modules exist and have expected functions."""

    def test_cpu_module_exists(self):
        """disco_lib.cpu module should exist with key functions."""
        from disco_lib import cpu

        assert hasattr(cpu, "halted"), "cpu.halted context manager missing"
        assert hasattr(cpu, "halt"), "cpu.halt function missing"
        assert hasattr(cpu, "resume"), "cpu.resume function missing"
        assert hasattr(cpu, "reset_halt"), "cpu.reset_halt function missing"
        assert hasattr(cpu, "reset_run"), "cpu.reset_run function missing"
        assert hasattr(cpu, "read_pc"), "cpu.read_pc function missing"
        assert hasattr(cpu, "read_sp"), "cpu.read_sp function missing"
        assert hasattr(cpu, "read_regs"), "cpu.read_regs function missing"

    def test_memory_module_exists(self):
        """disco_lib.memory module should exist with key functions."""
        from disco_lib import memory

        assert hasattr(memory, "read_words"), "memory.read_words function missing"
        assert hasattr(memory, "read_vectors"), "memory.read_vectors function missing"
        assert hasattr(memory, "dump_to_file"), "memory.dump_to_file function missing"

    def test_flash_module_has_lowlevel_functions(self):
        """disco_lib.flash should have low-level wrapper functions."""
        from disco_lib import flash

        assert hasattr(flash, "read_info"), "flash.read_info function missing"
        assert hasattr(flash, "erase_all"), "flash.erase_all function missing"
        assert hasattr(flash, "dump_image"), "flash.dump_image function missing"
        assert hasattr(flash, "program_firmware"), "flash.program_firmware function missing"
        assert hasattr(flash, "verify_firmware"), "flash.verify_firmware function missing"

"""Tests for repl.py backend.

The repl module handles MicroPython REPL communication:
  - filter_repl_output: Clean up raw serial output to extract results
  - exec_code: Send code and get filtered response
  - soft_reset: Send Ctrl-D reset sequence

The key testable logic is in filter_repl_output, which must handle
the messy reality of serial REPL output (echoes, prompts, \r\n, etc).
"""

import pytest

from disco_lib.repl import filter_repl_output


class TestFilterReplOutput:
    """Tests for filter_repl_output() - cleans raw REPL response.

    MicroPython REPL output includes:
      - Command echo (what we typed)
      - Prompts (>>>, ...)
      - Carriage returns (\r)
      - The actual result we want

    This function strips everything except the result.
    """

    def test_simple_expression(self):
        """Simple expression like '1 + 1' returns just the result."""
        # Raw output: echo, result, prompt
        raw = "1 + 1\r\n2\r\n>>> "
        assert filter_repl_output(raw, "1 + 1") == "2"

    def test_strips_command_echo(self):
        """Command echo (what we sent) is removed."""
        raw = "print('hello')\r\nhello\r\n>>> "
        assert filter_repl_output(raw, "print('hello')") == "hello"

    def test_strips_prompt_prefix(self):
        """Lines starting with >>> have prefix removed."""
        raw = ">>> 42\r\n>>> "
        assert filter_repl_output(raw, "x") == "42"

    def test_strips_continuation_prefix(self):
        """Lines starting with ... (continuation) have prefix removed."""
        raw = "... something\r\n>>> "
        assert filter_repl_output(raw, "x") == "something"

    def test_removes_empty_prompts(self):
        """Standalone >>> or ... lines are removed entirely."""
        raw = ">>>\r\n...\r\n>>> \r\nresult\r\n>>> "
        assert filter_repl_output(raw, "x") == "result"

    def test_strips_carriage_returns(self):
        """Carriage returns are stripped from line endings."""
        raw = "value\r\n"
        assert filter_repl_output(raw, "x") == "value"
        assert "\r" not in filter_repl_output(raw, "x")

    def test_multiline_output(self):
        """Multi-line output is preserved (minus prompts/echo)."""
        raw = "help()\r\nLine 1\r\nLine 2\r\nLine 3\r\n>>> "
        result = filter_repl_output(raw, "help()")
        assert "Line 1" in result
        assert "Line 2" in result
        assert "Line 3" in result

    def test_empty_output(self):
        """Commands with no output return empty string."""
        raw = "x = 1\r\n>>> "
        assert filter_repl_output(raw, "x = 1") == ""

    def test_whitespace_in_code_matched(self):
        """Code matching ignores leading/trailing whitespace."""
        raw = "  print('hi')  \r\nhi\r\n>>> "
        # Code has extra spaces but should still match
        assert filter_repl_output(raw, "print('hi')") == "hi"

    # Real-world MicroPython output examples

    def test_sys_implementation(self):
        """Real output from 'import sys; print(sys.implementation)'."""
        code = "import sys; print(sys.implementation)"
        raw = (
            "import sys; print(sys.implementation)\r\n"
            "(name='micropython', version=(1, 19, 1))\r\n"
            ">>> "
        )
        result = filter_repl_output(raw, code)
        assert result == "(name='micropython', version=(1, 19, 1))"

    def test_gc_mem_free(self):
        """Real output from gc.mem_free()."""
        code = "import gc; gc.collect(); print(gc.mem_free())"
        raw = (
            "import gc; gc.collect(); print(gc.mem_free())\r\n"
            "123456\r\n"
            ">>> "
        )
        result = filter_repl_output(raw, code)
        assert result == "123456"

    def test_help_modules_multiline(self):
        """Real output from help('modules') - many lines."""
        code = "help('modules')"
        raw = (
            "help('modules')\r\n"
            "__main__          gc                sys               uos\r\n"
            "_thread           machine           time              ustruct\r\n"
            "builtins          micropython       uasyncio          \r\n"
            ">>> "
        )
        result = filter_repl_output(raw, code)
        lines = result.split("\n")
        assert len(lines) == 3
        assert "__main__" in lines[0]
        assert "machine" in lines[1]

    def test_error_traceback(self):
        """Tracebacks are preserved for debugging."""
        code = "1/0"
        raw = (
            "1/0\r\n"
            "Traceback (most recent call last):\r\n"
            "  File \"<stdin>\", line 1, in <module>\r\n"
            "ZeroDivisionError: divide by zero\r\n"
            ">>> "
        )
        result = filter_repl_output(raw, code)
        assert "Traceback" in result
        assert "ZeroDivisionError" in result

    def test_import_no_output(self):
        """Successful import with no print has no output."""
        code = "import machine"
        raw = "import machine\r\n>>> "
        assert filter_repl_output(raw, code) == ""

    def test_multiple_prompts_in_sequence(self):
        """Handle messy output with multiple prompt sequences."""
        raw = ">>> \r\n>>> \r\n>>> result\r\n>>> \r\n"
        assert filter_repl_output(raw, "x") == "result"

    def test_result_on_same_line_as_prompt(self):
        """Result immediately after prompt on same line."""
        raw = ">>> 123"
        assert filter_repl_output(raw, "x") == "123"

    def test_preserves_internal_whitespace(self):
        """Whitespace within output lines is preserved."""
        code = "print('a  b')"
        raw = "print('a  b')\r\na  b\r\n>>> "
        assert filter_repl_output(raw, code) == "a  b"

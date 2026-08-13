"""LVGL remote-control commands."""

import json as json_mod
import os
import struct
import tempfile

import click

from ..ocd_provider import get_ocd
from .. import cpu as cpu_backend
from .. import memory
from ..serial import SerialDevice
from .. import repl as repl_backend

_ser = SerialDevice()

# MicroPython script: check LVGL version (runs on device)
_LVGL_VERSION_CHECK = "import lvgl as lv; print('9' if hasattr(lv,'screen_active') else '8')"

# MicroPython script: walk widget tree and print it (runs on device)
_TREE_SCRIPT = """\
import lvgl as lv
import json

def _clsname(obj):
    c = obj.__class__.__name__
    return c if c != 'lv_obj' else 'obj'

def _text(obj):
    try:
        return obj.get_text()
    except Exception:
        return None

def _walk(obj, depth, idx, out, as_dict):
    cls = _clsname(obj)
    cc = obj.get_child_count()
    txt = _text(obj)
    if as_dict:
        node = {'type': cls, 'children': []}
        if txt is not None:
            node['text'] = txt
        for i in range(cc):
            _walk(obj.get_child(i), depth + 1, i, node['children'], True)
        out.append(node)
    else:
        indent = '  ' * depth
        if txt is not None:
            print('%s[%d] %s "%s"' % (indent, idx, cls, txt))
        else:
            print('%s[%d] %s cc=%d' % (indent, idx, cls, cc))
        for i in range(cc):
            _walk(obj.get_child(i), depth + 1, i, out, False)

scr = $ROOT
cc = scr.get_child_count()
AS_JSON = $AS_JSON
if AS_JSON:
    tree = []
    for i in range(cc):
        _walk(scr.get_child(i), 0, i, tree, True)
    print(json.dumps(tree))
else:
    for i in range(cc):
        _walk(scr.get_child(i), 0, i, [], False)
"""

# MicroPython script: find widget by label text and click it (runs on device)
_CLICK_SCRIPT = """\
import lvgl as lv

def _find_by_text(obj, target):
    try:
        if obj.get_text() == target:
            return obj
    except Exception:
        pass
    for i in range(obj.get_child_count()):
        r = _find_by_text(obj.get_child(i), target)
        if r is not None:
            return r
    return None

def _clickable(w):
    p = w.get_parent()
    while p is not None:
        if 'button' in p.__class__.__name__:
            return p
        p = p.get_parent()
    return w

scr = $ROOT
w = _find_by_text(scr, $TEXT)
if w is None:
    print('NOT_FOUND')
else:
    target = _clickable(w)
    target.send_event(lv.EVENT.CLICKED, None)
    print('OK')
    try:
        import udisplay
        udisplay.update(30)
    except Exception:
        pass
"""

# MicroPython script: click widget by tree index path (runs on device)
_CLICK_INDEX_SCRIPT = """\
import lvgl as lv
scr = $ROOT
path = $PATH
w = scr
for i in path:
    if i >= w.get_child_count():
        print('INDEX_ERROR:%d:%d' % (i, w.get_child_count()))
        w = None
        break
    w = w.get_child(i)
if w is not None:
    w.send_event(lv.EVENT.CLICKED, None)
    print('OK')
    try:
        import udisplay
        udisplay.update(30)
    except Exception:
        pass
"""

# MicroPython script: find textarea and set text (runs on device)
_WRITE_SCRIPT = """\
import lvgl as lv

def _find_textareas(obj, result):
    if 'textarea' in obj.__class__.__name__:
        result.append(obj)
    for i in range(obj.get_child_count()):
        _find_textareas(obj.get_child(i), result)

scr = lv.screen_active()
tas = []
_find_textareas(scr, tas)
idx = $TARGET
if not tas:
    print('NO_TEXTAREA')
elif idx >= len(tas):
    print('INDEX_OUT_OF_RANGE:%d' % len(tas))
else:
    tas[idx].set_text($TEXT)
    try:
        import udisplay
        udisplay.update(30)
    except Exception:
        pass
    print('OK')
"""


def _root_expr(layer: str) -> str:
    """Return the MicroPython expression for the root widget of *layer*.

    ``screen`` (default) → ``lv.screen_active()``
    ``top``              → ``lv.display_get_default().get_layer_top()``
    """
    if layer == "top":
        return "lv.display_get_default().get_layer_top()"
    return "lv.screen_active()"


def _check_lvgl_version(dev, baud):
    """Verify LVGL 9+ is available on the board."""
    try:
        ver = repl_backend.exec_raw(dev, _LVGL_VERSION_CHECK, baud)
    except RuntimeError as e:
        raise click.ClickException(f"Cannot detect LVGL: {e}")
    ver = ver.strip()
    if ver != "9":
        raise click.ClickException(
            f"Unsupported LVGL version {ver!r} \u2014 disco ui requires LVGL 9+")


@click.group()
def ui():
    """LVGL remote control.

    Low-level commands to inspect and interact with the LVGL widget tree
    running on the board. Requires LVGL 9+ firmware.

    \b
    Commands:
      disco ui screen           # dump widget tree
      disco ui screen --json    # dump as JSON
      disco ui click "1"        # click widget with label "1"
      disco ui write "hello"    # set text on a textarea
    """
    pass


@ui.command("screen")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON tree")
@click.option("--layer", "layer", default="screen",
              type=click.Choice(["screen", "top"]),
              help="Root layer: 'screen' (default) or 'top' (layer_top overlay)")
@click.option("--timeout", "-t", default=10, type=int, help="Response timeout in seconds")
def ui_screen(as_json: bool, layer: str, timeout: int):
    """Dump the LVGL widget tree.

    Shows each widget's index, type, child count, and text (for labels).
    Use --layer top to inspect overlay widgets (e.g. modal dialogs, tour).

    \b
    Examples:
      disco ui screen
      disco ui screen --json
      disco ui screen --layer top --json
    """
    dev = _ser.require_device()
    _check_lvgl_version(dev, _ser.baud)

    script = (
        _TREE_SCRIPT
        .replace("$ROOT", _root_expr(layer))
        .replace("$AS_JSON", "True" if as_json else "False")
    )
    try:
        output = repl_backend.exec_raw(dev, script, _ser.baud, timeout)
    except RuntimeError as e:
        raise click.ClickException(str(e))

    if as_json:
        try:
            tree = json_mod.loads(output)
            click.echo(json_mod.dumps(tree, indent=2))
        except json_mod.JSONDecodeError:
            click.echo(output)
    else:
        click.echo(output)


@ui.command("click")
@click.argument("text", required=False, default=None)
@click.option("--index", "-i", default=None, help="Dot-separated tree path (e.g. 1.0.1.5.2)")
@click.option("--layer", "layer", default="screen",
              type=click.Choice(["screen", "top"]),
              help="Root layer: 'screen' (default) or 'top' (layer_top overlay)")
@click.option("--timeout", "-t", default=10, type=int, help="Response timeout in seconds")
def ui_click(text: str, index: str, layer: str, timeout: int):
    """Click a widget by its label text or tree position.

    By default, searches depth-first for a widget whose label text matches.
    With --index, navigates the tree by child indices (dot-separated).
    Use --layer top to target overlay widgets (e.g. modal dialogs, tour).

    \b
    Examples:
      disco ui click "1"               # click by label text
      disco ui click "OK"
      disco ui click -i 1.0.1.5.2      # click by tree path
      disco ui click --layer top "Skip"  # click button in overlay
      disco ui click --layer top -i 0.2  # click overlay button by index
    """
    if text is None and index is None:
        raise click.ClickException("Provide TEXT or --index")
    if text is not None and index is not None:
        raise click.ClickException("Provide TEXT or --index, not both")

    dev = _ser.require_device()
    _check_lvgl_version(dev, _ser.baud)

    if index is not None:
        try:
            path = [int(x) for x in index.split(".")]
        except ValueError:
            raise click.ClickException(
                f"Invalid index path: {index!r} (expected dot-separated integers)")
        script = (
            _CLICK_INDEX_SCRIPT
            .replace("$ROOT", _root_expr(layer))
            .replace("$PATH", repr(path))
        )
        label = f"index {index}"
    else:
        script = (
            _CLICK_SCRIPT
            .replace("$ROOT", _root_expr(layer))
            .replace("$TEXT", repr(text))
        )
        label = f"text \"{text}\""

    try:
        output = repl_backend.exec_raw(dev, script, _ser.baud, timeout)
    except RuntimeError as e:
        raise click.ClickException(str(e))

    lines = output.strip().splitlines()
    result = lines[-1] if lines else ""
    if result == "OK":
        if len(lines) > 1:
            click.echo("\n".join(lines[:-1]))
        click.secho(f"Clicked widget at {label}", fg="green")
    elif result == "NOT_FOUND":
        raise click.ClickException(f"No widget found with {label}")
    elif result.startswith("INDEX_ERROR:"):
        parts = result.split(":")
        raise click.ClickException(
            f"Child index {parts[1]} out of range (parent has {parts[2]} children)")
    else:
        raise click.ClickException(f"Unexpected response: {output.strip()}")


@ui.command("write")
@click.argument("text")
@click.option("--target", "-n", default=0, type=int,
              help="Index of textarea to target (default: 0)")
@click.option("--timeout", "-t", default=10, type=int, help="Response timeout in seconds")
def ui_write(text: str, target: int, timeout: int):
    """Set text on a textarea widget.

    Finds textarea widgets on the active screen and sets the text on the
    one at the given index (default: first textarea found).

    \b
    Examples:
      disco ui write "hello"
      disco ui write "secret" --target 1
    """
    dev = _ser.require_device()
    _check_lvgl_version(dev, _ser.baud)

    script = _WRITE_SCRIPT.replace("$TARGET", str(target)).replace("$TEXT", repr(text))
    try:
        output = repl_backend.exec_raw(dev, script, _ser.baud, timeout)
    except RuntimeError as e:
        raise click.ClickException(str(e))

    result = output.strip()
    if result == "OK":
        click.secho(f"Set textarea[{target}] text to \"{text}\"", fg="green")
    elif result == "NO_TEXTAREA":
        raise click.ClickException("No textarea widget found on screen")
    elif result.startswith("INDEX_OUT_OF_RANGE:"):
        count = result.split(":")[1]
        raise click.ClickException(
            f"Textarea index {target} out of range (found {count} textareas)")
    else:
        raise click.ClickException(f"Unexpected response: {result}")


# --- Screenshot support ---

# Framebuffer constants
_FB_ADDR = 0xC0000000
_FB_WIDTH = 480
_FB_HEIGHT = 800
_FB_BPP = 4  # ARGB8888
_FB_SIZE = _FB_WIDTH * _FB_HEIGHT * _FB_BPP  # 1,536,000 bytes


def _raw_to_png(raw_path: str, png_path: str,
                width: int = _FB_WIDTH, height: int = _FB_HEIGHT) -> None:
    """Convert a raw ARGB8888 framebuffer dump to a PNG file.

    The STM32 LTDC stores ARGB8888 as 0xAARRGGBB words.  In little-endian
    memory that's bytes BB GG RR AA.  PNG RGBA expects RR GG BB AA, so we
    swap bytes 0 and 2 (B <-> R) in each pixel.

    Uses only stdlib (struct + zlib).
    """
    import zlib

    with open(raw_path, "rb") as f:
        raw = bytearray(f.read())

    # Swap B and R channels: memory is [B,G,R,A], PNG wants [R,G,B,A]
    raw[0::4], raw[2::4] = raw[2::4], raw[0::4]

    # Build PNG scanlines: filter byte (0 = None) + row pixels
    row_bytes = width * _FB_BPP
    scanlines = bytearray()
    for y in range(height):
        scanlines.append(0)
        offset = y * row_bytes
        scanlines.extend(raw[offset:offset + row_bytes])

    compressed = zlib.compress(bytes(scanlines))

    def _chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        crc = struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
        return struct.pack(">I", len(data)) + body + crc

    with open(png_path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        # IHDR: width, height, bit-depth=8, color-type=6 (RGBA)
        f.write(_chunk(b"IHDR", struct.pack(">IIBBBBB",
                                            width, height, 8, 6, 0, 0, 0)))
        f.write(_chunk(b"IDAT", compressed))
        f.write(_chunk(b"IEND", b""))


@ui.command("screenshot")
@click.argument("output", default="/tmp/screenshot.png", type=click.Path())
@click.option("--timeout", "-t", default=30, type=int,
              help="OpenOCD dump timeout in seconds")
def ui_screenshot(output: str, timeout: int):
    """Capture the display framebuffer and save as a PNG file.

    Halts the CPU, reads the LTDC framebuffer from SDRAM, converts the
    raw ARGB8888 data to a PNG, then resumes the CPU.

    \b
    Examples:
      disco ui screenshot
      disco ui screenshot ~/desktop/shot.png
    """
    output = os.path.abspath(output)

    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".bin")
    os.close(tmp_fd)

    try:
        ocd = get_ocd()
        with ocd.ensure_running(), cpu_backend.halted(ocd):
            click.echo(f"Dumping framebuffer (0x{_FB_ADDR:08x}, "
                       f"{_FB_SIZE:,} bytes)...")
            success = memory.dump_to_file(
                ocd, tmp_path, _FB_ADDR, _FB_SIZE, timeout=timeout)
            if not success:
                raise click.ClickException("Failed to dump framebuffer")

        actual = os.path.getsize(tmp_path)
        if actual != _FB_SIZE:
            raise click.ClickException(
                f"Unexpected dump size: {actual:,} bytes "
                f"(expected {_FB_SIZE:,})")

        _raw_to_png(tmp_path, output)
        click.secho(f"Screenshot saved to {output}", fg="green")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

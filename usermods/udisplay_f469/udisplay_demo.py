# udisplay_demo.py — platform-agnostic demo (LVGL 9.x)
import sys, time as _time
import lvgl as lv

# Font for all the controls
APP_FONT = lv.font_montserrat_16

# Detect use of simulator
SIMULATOR = sys.platform in ["linux", "darwin", "win32"]

# Resolve which display.py to use
_BASE_DIR = __file__.rsplit("/", 1)[0]
if SIMULATOR:
    sys.path.insert(0, _BASE_DIR + "/display_unixport")
else:
    sys.path.insert(0, _BASE_DIR + "/display_f469")

import display as platform_display  # platform-specific init()


class BottomKeyboard:
    """Mobile-like on-screen keyboard that overlaps UI and stays fixed at the bottom."""

    def __init__(self, height_ratio=30, font=None):
        """
        Initializes the keyboard display object.

        Args:
            height_ratio (int, optional): The height of the keyboard as a percentage
                of the screen height. Defaults to 30. For example, a value of 30
                means the keyboard will occupy 30% of the screen height. If set to 0
                or a negative value, the keyboard height defaults to one-third of
                the screen height.
            font (optional): LVGL font object to use for the keyboard. If None, font is not set.

        Attributes:
            disp (lv.display): The default display object.
            top_layer (lv.layer): The top layer of the display, ensuring the keyboard
                is always rendered above other screen contents.
            kb (lv.keyboard): The keyboard object, initialized with specific size,
                placement, and mode settings.

        Behavior:
            - The keyboard is initially hidden.
            - The keyboard is configured to hide itself when the user presses "OK/Enter".
        """
        self.disp = lv.display_get_default()
        # Parent on top layer so it always renders above the screen contents
        self.top_layer = self.disp.get_layer_top()
        self.kb = lv.keyboard(self.top_layer)
        if font is not None:
            self.kb.set_style_text_font(font, 0)

        # Size & placement: full width, fixed to bottom
        scr = lv.screen_active()
        scr_w = scr.get_width()
        scr_h = scr.get_height()
        kb_h = (scr_h * height_ratio) // 100 if height_ratio > 0 else scr_h // 3
        self.kb.set_size(scr_w, kb_h)
        self.kb.align(lv.ALIGN.BOTTOM_MID, 0, 0)
        self.kb.set_mode(lv.keyboard.MODE.TEXT_LOWER)

        # Start hidden
        self.kb.add_flag(lv.obj.FLAG.HIDDEN)

        # Hide keyboard when user presses "OK/Enter" on the keyboard
        self.kb.add_event_cb(self._on_kb_ready, lv.EVENT.READY, None)

    def _on_kb_ready(self, _e):
        self.kb.set_textarea(None)
        self.hide()

    def attach(self, ta: lv.textarea):
        """Make the keyboard handle this textarea and auto-show/hide on focus."""
        ta.add_event_cb(
            lambda e: (self.kb.set_textarea(ta), self.show()), lv.EVENT.FOCUSED, None
        )
        ta.add_event_cb(
            lambda e: (self.kb.set_textarea(None), self.hide()),
            lv.EVENT.DEFOCUSED,
            None,
        )

    def show(self):
        """Show keyboard"""
        self.kb.remove_flag(lv.obj.FLAG.HIDDEN)
        # keep in foreground among top-layer children
        self.kb.move_foreground()

    def hide(self):
        """Hide kayboard."""
        self.kb.add_flag(lv.obj.FLAG.HIDDEN)


def init_display(autoupdate=True):
    # Platform's display.py does lv.init() + display/inputs
    platform_display.init(autoupdate=autoupdate)
    scr = lv.obj()

    # Set default font
    scr.set_style_text_font(APP_FONT, 0)
    lv.display_get_default().get_layer_top().set_style_text_font(APP_FONT, 0)
    lv.display_get_default().get_layer_sys().set_style_text_font(APP_FONT, 0)

    lv.screen_load(scr)
    return scr


def make_ui(root):
    root.set_style_pad_all(16, 0)
    root.set_flex_flow(lv.FLEX_FLOW.COLUMN)
    root.set_flex_align(lv.FLEX_ALIGN.START, lv.FLEX_ALIGN.START, lv.FLEX_ALIGN.START)

    title = lv.label(root)
    title.set_text("LVGL Demo")

    # Row with a counter button
    row = lv.obj(root)
    row.set_width(lv.pct(100))
    row.set_flex_flow(lv.FLEX_FLOW.ROW)
    row.set_flex_align(lv.FLEX_ALIGN.START, lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER)

    counter_lbl = lv.label(row)
    counter_lbl.set_text("Clicks: 0")
    btn = lv.button(row)
    btn.set_width(lv.SIZE_CONTENT)
    lv.label(btn).set_text("Click me")

    _state = {"clicks": 0}

    def _on_btn(evt):
        if evt.get_code() == lv.EVENT.CLICKED:
            _state["clicks"] += 1
            counter_lbl.set_text("Clicks: {}".format(_state["clicks"]))

    btn.add_event_cb(_on_btn, lv.EVENT.ALL, None)

    # Slider + arc + label (keep both in sync)
    slider = lv.slider(root)
    slider.set_range(0, 100)
    slider.set_value(40, False)
    slider.set_width(lv.pct(100))

    arc = lv.arc(root)
    arc.set_size(120, 120)
    arc.set_range(0, 100)
    arc.set_value(slider.get_value())

    value_lbl = lv.label(root)
    value_lbl.set_text("Value: {}".format(slider.get_value()))

    def _on_slider(evt):
        if evt.get_code() == lv.EVENT.VALUE_CHANGED:
            v = slider.get_value()
            arc.set_value(v)
            value_lbl.set_text("Value: {}".format(v))

    slider.add_event_cb(_on_slider, lv.EVENT.ALL, None)

    def _on_arc(evt):
        if evt.get_code() == lv.EVENT.VALUE_CHANGED:
            v = arc.get_value()
            slider.set_value(v, False)
            value_lbl.set_text("Value: {}".format(v))

    arc.add_event_cb(_on_arc, lv.EVENT.ALL, None)

    # Text area + bottom overlay keyboard (same behavior on all platforms)
    ta = lv.textarea(root)
    ta.set_width(lv.pct(100))
    ta.set_placeholder_text("Type here…")
    ta.center()

    kb_overlay = BottomKeyboard(height_ratio=35, font=APP_FONT)
    kb_overlay.attach(ta)

    # "Show message" button: use Montserrat 16 only for this msgbox
    show_btn = lv.button(root)
    show_btn.set_width(lv.SIZE_CONTENT)
    lv.label(show_btn).set_text("Show message")

    def _show_msg(evt):
        if evt.get_code() == lv.EVENT.CLICKED:
            m = lv.msgbox(lv.screen_active())
            m.add_title("Hi!")
            m.add_text(
                "This is a portable demo running on {}.".format(
                    "Simulator" if SIMULATOR else "STM32"
                )
            )
            ok_btn = m.add_footer_button("OK")
            m.add_close_button()
            m.center()

            def _ok(_e):
                m.close()

            ok_btn.add_event_cb(_ok, lv.EVENT.CLICKED, None)

    show_btn.add_event_cb(_show_msg, lv.EVENT.ALL, None)

    # Clock label via LVGL timer
    clock_lbl = lv.label(root)
    clock_lbl.set_text("--:--:--")

    def _tick_timer(_):
        t = _time.localtime()
        clock_lbl.set_text("{:02d}:{:02d}:{:02d}".format(t[3], t[4], t[5]))

    lv.timer_create(_tick_timer, 1000, None)


def _run_loop(period_ms=16):
    # Manual LVGL drive loop (~60 Hz) for the simulator.
    last = _time.ticks_ms()
    while True:
        now = _time.ticks_ms()
        diff = _time.ticks_diff(now, last)
        last = now
        lv.tick_inc(diff)
        lv.timer_handler()
        _time.sleep_ms(1)


def main():
    # Simulator: drive manually for smoothness; Device: let HW/autoupdate handle it.
    scr = init_display(autoupdate=not SIMULATOR)
    make_ui(scr)
    try:
        if SIMULATOR:
            _run_loop(16)
        else:
            while True:
                _time.sleep(1)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

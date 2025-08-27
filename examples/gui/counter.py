import lvgl as lv
import display
import utime as time

styles = {}

PADDING = 30
BTN_HEIGHT = 80
BTN_WIDTH = 100
HOR_RES = 480
VER_RES = 800
ROW_MID = 150


def init():
    display.init()

    # Set up the default theme:
    # - disp: pointer to display (None uses the default display)
    # - color_primary: primary color of the theme (blue here)
    # - color_secondary: secondary color of the theme (red here)
    # - dark: True for dark mode, False for light mode (light mode here)
    # - font: font to use (Montserrat 22 here)
    th = lv.theme_default_init(
        None,
        lv.palette_main(lv.PALETTE.BLUE),
        lv.palette_main(lv.PALETTE.RED),
        False,
        lv.font_montserrat_22,
    )

    # Create a screen and load it
    # To access active screen use lv.screen_active()
    scr = lv.obj()
    lv.screen_load(scr)

    # Initialize the styles
    styles["title"] = lv.style_t()
    # Title style - just a default style with larger font
    styles["title"].init()
    styles["title"].set_text_font(lv.font_montserrat_28)


def create_title(text, y=PADDING, screen=None):
    """Helper functions that creates a title-styled label"""
    if screen is None:
        screen = lv.screen_active()
    lbl = lv.label(screen)
    lbl.add_style(styles["title"], 0)
    lbl.set_text(text)
    lbl.set_long_mode(lv.label.LONG_MODE.WRAP)
    lbl.set_width(HOR_RES-2*PADDING)
    lbl.set_x(PADDING)
    lbl.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
    lbl.set_y(y)
    return lbl


def create_button(
    text, callback=None, screen=None, y=0, x=PADDING, w=BTN_WIDTH, h=BTN_HEIGHT
):
    """Helper function that creates a button with a text label"""
    if screen is None:
        screen = lv.screen_active()
    btn = lv.button(screen)
    btn.set_size(w, h)
    btn.set_pos(x, y)

    lbl = lv.label(btn)
    lbl.set_text(text)
    lbl.center()

    if callback is not None:
        btn.add_event_cb(callback, lv.EVENT.CLICKED, None)
    return btn


def clear(screen=None):
    """Helper function that clears current screen"""
    if screen is None:
        screen = lv.screen_active()
    screen.clean()


def show_counter_screen():
    """A sample screen that has a counter and two buttons"""

    # Get and clear active screen
    clear()
    create_title("Here is the counter:")

    obj = {"counter": 0}

    # Create the counter label and center it vertically
    counter_lbl = create_title("%d" % obj["counter"])
    # Force layout update to get correct height
    lv.obj.update_layout(counter_lbl.get_parent())
    counter_lbl.set_y(ROW_MID-counter_lbl.get_height()//2)

    def plus_one(e):
        if e.get_code() == lv.EVENT.CLICKED:
            obj["counter"] += 1
            counter_lbl.set_text("%d" % obj["counter"])

    def minus_one(e):
        if e.get_code() == lv.EVENT.CLICKED:
            obj["counter"] -= 1
            counter_lbl.set_text("%d" % obj["counter"])

    # Create the buttons and position them horizontally centered
    btn_y = ROW_MID-BTN_HEIGHT//2
    create_button("-1", callback=minus_one, y=btn_y, x=PADDING)
    create_button("+1", callback=plus_one, y=btn_y, x=HOR_RES-PADDING-BTN_WIDTH)


def main():
    init()
    show_counter_screen()
    while True:
        time.sleep_ms(30)
        display.update(30)

if __name__ == '__main__':
    main()


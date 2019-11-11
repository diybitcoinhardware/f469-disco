import lvgl as lv
import SDL
import time

styles = {}

PADDING = 30
BTN_HEIGHT = 80
HOR_RES = 480
VER_RES = 800

def init():
    """
    GUI initialization function. 
    Should be called once in the very beginning.
    """

    # init the gui library
    lv.init()
    # init the hardware library
    SDL.init()

    # Register SDL display driver
    disp_buf1 = lv.disp_buf_t()
    buf1_1 = bytearray(HOR_RES*10)
    lv.disp_buf_init(disp_buf1,buf1_1, None, len(buf1_1)//4)
    disp_drv = lv.disp_drv_t()
    lv.disp_drv_init(disp_drv)
    disp_drv.buffer = disp_buf1
    disp_drv.flush_cb = SDL.monitor_flush
    disp_drv.hor_res = HOR_RES
    disp_drv.ver_res = VER_RES
    lv.disp_drv_register(disp_drv)

    # Regsiter SDL mouse driver
    indev_drv = lv.indev_drv_t()
    lv.indev_drv_init(indev_drv) 
    indev_drv.type = lv.INDEV_TYPE.POINTER;
    indev_drv.read_cb = SDL.mouse_read;
    lv.indev_drv_register(indev_drv);

    # Set up material theme
    # First argument (210) is a hue - theme color shift,
    # Second - default font to use. Builtin: roboto_16, roboto_28
    th = lv.theme_material_init(210, lv.font_roboto_22)
    lv.theme_set_current(th)

    # Create a screen and load it
    # To access active screen use lv.scr_act()
    scr = lv.obj()
    lv.scr_load(scr)

    # Initialize the styles
    styles["title"] = lv.style_t()
    # Title style - just a default style with larger font
    lv.style_copy(styles["title"], lv.style_plain)
    styles["title"].text.font = lv.font_roboto_28

def create_title(text, y=PADDING, screen=None):
    """Helper functions that creates a title-styled label"""
    if screen is None:
        screen = lv.scr_act()
    lbl = lv.label(screen)
    lbl.set_style(0, styles["title"])
    lbl.set_text(text)
    lbl.set_long_mode(lv.label.LONG.BREAK)
    lbl.set_width(HOR_RES-2*PADDING)
    lbl.set_x(PADDING)
    lbl.set_align(lv.label.ALIGN.CENTER)
    lbl.set_y(y)
    return lbl

def create_button(text, callback=None, screen=None, y=700):
    """Helper function that creates a button with a text label"""
    if screen is None:
        screen = lv.scr_act()
    btn = lv.btn(screen)
    btn.set_width(HOR_RES-2*PADDING);
    btn.set_height(BTN_HEIGHT);
    
    lbl = lv.label(btn)
    lbl.set_text(text)
    lbl.set_align(lv.label.ALIGN.CENTER)

    btn.align(screen, lv.ALIGN.IN_TOP_MID, 0, 0)
    btn.set_y(y)

    if callback is not None:
        btn.set_event_cb(callback)

    return btn

def clear(screen=None):
    """Helper function that clears current screen"""
    if screen is None:
        screen = lv.scr_act()
    screen.clean()

def show_counter_screen():
    """A sample screen that has a counter and two buttons"""

    # Get and clear active screen
    clear()
    create_title("Here is the counter:")

    obj = {"counter": 0}

    counter_lbl = create_title("%d" % obj["counter"])
    counter_lbl.set_y(150-counter_lbl.get_height()//2)

    def plus_one(btn, e):
        if e == lv.EVENT.RELEASED:
            obj["counter"] += 1
            counter_lbl.set_text("%d" % obj["counter"])

    def minus_one(btn, e):
        if e == lv.EVENT.RELEASED:
            obj["counter"] -= 1
            counter_lbl.set_text("%d" % obj["counter"])

    btn = create_button("+1", y=150-BTN_HEIGHT//2, callback=plus_one)
    btn.set_width(100)
    btn.set_x(HOR_RES-PADDING-100)

    btn = create_button("-1", y=150-BTN_HEIGHT//2, callback=minus_one)
    btn.set_width(100)
    btn.set_x(PADDING)

def main():
    init()
    show_counter_screen()
    while True:
        time.sleep_ms(30)

if __name__ == '__main__':
    main()


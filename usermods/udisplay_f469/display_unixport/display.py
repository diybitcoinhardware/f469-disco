from udisplay import update, on, off, set_rotation

def init(autoupdate=True):
    import lvgl as lv
    import SDL

    HOR_RES = 480
    VER_RES = 800
    """
    GUI initialization function.
    Should be called once in the very beginning.
    """

    # init the gui library
    lv.init()
    # init the hardware library
    SDL.init(
        HOR_RES,
        VER_RES,
        title="LVGL v9 (SDL)",
        resizable=True,
        mouse=True,
        mousewheel=True,
        keyboard=False,
        zoom=1.0,
    )

    scr = lv.obj()
    lv.screen_load(scr)

    if autoupdate:
        SDL.enable_autoupdate()
    else:
        SDL.disable_autoupdate()

    return True


def step(dt_ms=5):
    """
    Manual advance for LVGL when init(autoupdate=False) is used.
    """
    import lvgl as lv
    lv.tick_inc(dt_ms)
    lv.timer_handler()

from udisplay import update, on, off, set_rotation

def init(autoupdate=True):
    import udisplay
    udisplay.init()

    if autoupdate:
        import micropython
        import pyb
        def schedule(t):
            """Try to schedule an LED update"""
            try:
                micropython.schedule(udisplay.update, 30)
            except:
                pass
        timer = pyb.Timer(4) # timer 4
        timer.init(freq=30)  # 30Hz update rate
        timer.callback(schedule)
from udisplay import update

def init():
    import udisplay
    import micropython
    import pyb
    def schedule(t):
        """Try to schedule an LED update"""
        try:
            micropython.schedule(udisplay.update, 30)
        except:
            pass
    udisplay.init()
    timer = pyb.Timer(4) # timer 4
    timer.init(freq=30)  # 30Hz update rate
    timer.callback(schedule)
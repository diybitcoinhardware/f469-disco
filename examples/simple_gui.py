# main.py -- put your code here!
import display
import lvgl as lv
import time

# const() helps micropython to be more efficient
PADDING = const(30)
BTN_HEIGHT = const(80)
HOR_RES = const(480)
VER_RES = const(800)

class CounterScreen:
    display.init()

    def __init__(self):
        # counter to increase/decrease
        self.counter = 0
        # text we will use in label
        self.lbl_template = "Counter value is %d"

    def add_button(self, text, callback, y=500):
        """ function that creates a button """
        scr = lv.scr_act()
        btn = lv.btn(scr)
        btn.set_width(HOR_RES-2*PADDING);
        btn.set_height(BTN_HEIGHT);

        btn_lbl = lv.label(btn)
        btn_lbl.set_text(text)
        btn_lbl.set_align(lv.label.ALIGN.CENTER)

        btn.align(scr, lv.ALIGN.IN_TOP_MID, 0, 0)
        btn.set_y(y)

        btn.set_event_cb(callback)

    def draw(self):
        # active screen (created during display init)
        scr = lv.scr_act()
        # create a label
        self.lbl = lv.label(scr)
        self.lbl.set_text(self.lbl_template % self.counter)
        self.lbl.set_long_mode(lv.label.LONG.BREAK)
        self.lbl.set_width(HOR_RES-2*PADDING)
        self.lbl.set_x(PADDING)
        self.lbl.set_align(lv.label.ALIGN.CENTER)
        self.lbl.set_y(200)

        # callback for "increase" button
        def plus_one(btn, e):
            if e == lv.EVENT.RELEASED:
                self.counter += 1
                self.lbl.set_text(self.lbl_template % self.counter)

        # callback for "increase" button
        def minus_one(btn, e):
            if e == lv.EVENT.RELEASED:
                self.counter -= 1
                self.lbl.set_text(self.lbl_template % self.counter)

        self.add_button("Increase counter", plus_one, 600)
        self.add_button("Decrease counter", minus_one, 700)

def set_theme():
    # setup theme
    th = lv.theme_material_init(210, lv.font_roboto_22)
    lv.theme_set_current(th)

def ioloop(dt):
    while True:
        time.sleep(dt/1000)
        display.update(dt)

# in global scope such that it is accessible from REPL
counter_scr = CounterScreen()

def init():
    display.init()

def main():
    set_theme()
    counter_scr.draw()
    time.sleep(0.1)
    ioloop(30)

if __name__ == '__main__':
    init()
    time.sleep(0.1)
    main()



# that's it, now from REPL you can play with the gui if you want to.
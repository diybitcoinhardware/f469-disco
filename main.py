import display
import time
import lvgl as lv

def main():
    display.init()
    time.sleep(0.1)
    btn = lv.btn(lv.scr_act())
    btn.set_width(300)

    lbl = lv.label(btn)
    style = lv.style_t()
    lv.style_copy(style, lbl.get_style(0))
    style.text.font = lv.font_custom_symbols_16
    lbl.set_style(0, style)
    lbl.set_text('123456789')

    while True:
        time.sleep_ms(30)

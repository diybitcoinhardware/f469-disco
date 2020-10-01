import lvgl as lv
import qrcode
import math
import gc


class QRCode(lv.label):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_long_mode(lv.label.LONG.BREAK)
        self.set_align(lv.label.ALIGN.CENTER)
        self.set_text()

    def set_text(self, text="Text"):
        self._text = text
        qr = qrcode.encode_to_string(text)
        size = int(math.sqrt(len(qr)))
        width = self.get_width()
        scale = width // size
        sizes = range(1, 10)
        fontsize = [s for s in sizes if s < scale or s == 1][-1]
        font = getattr(lv, "square%d" % fontsize)
        style = lv.style_t()
        lv.style_copy(style, lv.style_plain)
        style.body.main_color = lv.color_make(0xFF, 0xFF, 0xFF)
        style.body.grad_color = lv.color_make(0xFF, 0xFF, 0xFF)
        style.body.opa = 255
        style.text.font = font
        style.text.line_space = 0
        style.text.letter_space = 0
        self.set_style(0, style)
        # self.set_body_draw(True)
        super().set_text(qr)
        del qr
        gc.collect()

    def get_text(self):
        return self._text

    def set_size(self, size):
        super().set_size(size, size)
        self.set_text(self._text)

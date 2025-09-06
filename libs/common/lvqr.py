import lvgl as lv

class QRCode(lv.qrcode):
    def set_text(self, text="Text"):
        self._text = text
        self.set_dark_color(lv.color_black())
        self.set_light_color(lv.color_white())
        self.set_mode(lv.qrcode.MODE.TEXT)
        self.set_ecc(lv.qrcode.ECC.L)
        super().update(self._text, len(self._text))


    def get_text(self):
        return self._text


    def set_size(self, size):
        super().set_size(size)

import lvgl as lv

class QRCode(lv.qrcode):
    def get_selected_version(self):
        return super().get_selected_version()


    def set_fixed_size(self, enable=False):
        super().set_fixed_size(enable)


    def get_fixed_size(self):
        return super().get_fixed_size()


    def lock_selected_version(self):
        version = self.get_selected_version()
        if version:
            self.set_version_range(version, version)


    def clear_version_range(self):
        self.set_version_range(0, 0)


    def set_text(self, text="Text"):
        self._text = text
        self.set_dark_color(lv.color_black())
        self.set_light_color(lv.color_white())
        self.set_mode(lv.qrcode.MODE.TEXT)
        self.set_ecc(lv.qrcode.ECC.L)
        return super().update(self._text, len(self._text))


    def get_text(self):
        return self._text


    def set_size(self, size):
        super().set_size(size)

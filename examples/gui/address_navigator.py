import display
import lvgl as lv
from lvqr import QRCode
from embit import bip39, bip32, script
from embit.networks import NETWORKS
import utime as time

display.init()

# example mnemonic
mnemonic = "poverty august total basket pool print promote august piece squirrel coil sting"
# seed with empty password
seed = bip39.mnemonic_to_seed(mnemonic)
# root key
root = bip32.HDKey.from_seed(seed)
# height of buttons
BTN_HEIGHT = 60
# width of buttons
BTN_WIDTH = 150

class AddressNavigator(lv.obj):
    def __init__(self, account, *args,
                script_fn=script.p2wpkh,
                network=NETWORKS["main"],
                **kwargs):
        super().__init__(*args, **kwargs)
        self.account = account
        self.script_fn = script_fn
        self.network = network
        self._index = 0
        # create title
        self.title = lv.label(self)
        self.title.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        self.title.align(lv.ALIGN.TOP_MID, 0, 50)
        # create qr code
        self.qr = QRCode(self)
        self.qr.set_size(400)
        self.qr.align_to(self.title, lv.ALIGN.OUT_BOTTOM_MID, 0, 20)
        self.lbl = lv.label(self)
        self.lbl.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        # create buttons
        self.next_btn = lv.button(self)
        nb = lv.label(self.next_btn)
        nb.set_text("Next")
        nb.center()
        self.next_btn.set_width(BTN_WIDTH)
        self.next_btn.set_height(BTN_HEIGHT)
        self.next_btn.add_event_cb(self.next_address, lv.EVENT.CLICKED, None)
        self.prev_btn = lv.button(self)
        self.prev_btn.set_width(BTN_WIDTH)
        self.prev_btn.set_height(BTN_HEIGHT)
        pb = lv.label(self.prev_btn)
        pb.set_text("Previous")
        pb.center()
        self.prev_btn.add_event_cb(self.prev_address, lv.EVENT.CLICKED, None)
        # finally show first address
        self.show_address(self._index)

    def show_address(self, idx: int, change=False):
        self.title.set_text("Address #%d" % (idx + 1))
        self.title.align(lv.ALIGN.TOP_MID, 0, 50)
        pub = self.account.derive([int(change), idx]).key
        addr = self.script_fn(pub).address(network=self.network)
        self.qr.set_text("bitcoin:" + addr)
        self.lbl.set_text(addr)
        self.lbl.align_to(self.qr, lv.ALIGN.OUT_BOTTOM_MID, 0, 20)

        if idx == 0:
            self.prev_btn.add_state(lv.STATE.DISABLED)
        else:
            self.prev_btn.remove_state(lv.STATE.DISABLED)

        self.next_btn.align_to(self.qr, lv.ALIGN.OUT_BOTTOM_MID, 90, 70)
        self.prev_btn.align_to(self.qr, lv.ALIGN.OUT_BOTTOM_MID, -90, 70)

    def next_address(self, e):
        if e.get_code() == lv.EVENT.CLICKED:
            self._index += 1
            self.show_address(self._index)

    def prev_address(self, e):
        if e.get_code() == lv.EVENT.CLICKED and self._index > 0:
            self._index -= 1
            self.show_address(self._index)


scr = AddressNavigator(root.derive("m/49h/1h/0h").to_public(),         # bip-49 account xpub
                script_fn=lambda pub: script.p2sh(script.p2wpkh(pub)), # p2sh-p2wpkh
                network=NETWORKS["test"]                               # testnet
                )


# Needed for LVGL task handling when loaded as main script
def main():
    # Set up the default theme:
    # - disp: pointer to display (None uses the default display)
    # - color_primary: primary color of the theme (blue here)
    # - color_secondary: secondary color of the theme (red here)
    # - dark: True for dark mode, False for light mode (light mode here)
    # - font: font to use (Montserrat 16 here)
    lv.theme_default_init(
        None,
        lv.palette_main(lv.PALETTE.BLUE),
        lv.palette_main(lv.PALETTE.RED),
        False,
        lv.font_montserrat_16,
    )

    lv.screen_load(scr)
    while True:
        time.sleep_ms(30)
        display.update(30)

if __name__ == '__main__':
    main()

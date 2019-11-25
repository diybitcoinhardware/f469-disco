import display
import lvgl as lv
from lvqr import QRCode
from bitcoin import bip39, bip32, script
from bitcoin.networks import NETWORKS

display.init()

mnemonic = "poverty august total basket pool print promote august piece squirrel coil sting"
# seed with empty password
seed = bip39.mnemonic_to_seed(mnemonic)
# root key
root = bip32.HDKey.from_seed(seed)
account = root.derive("m/49h/0h/0h").to_public()

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
        self.title.set_align(lv.label.ALIGN.CENTER)
        self.title.align(self, lv.ALIGN.IN_TOP_MID, 0, 50)
        # create qr code
        self.qr = QRCode(self)
        self.qr.set_size(400)
        self.qr.align(self.title,lv.ALIGN.OUT_BOTTOM_MID, 0, 20)
        self.lbl = lv.label(self)
        # create buttons
        self.next_btn = lv.btn(self)
        lbl = lv.label(self.next_btn)
        lbl.set_text("Next")
        self.next_btn.set_width(150)
        self.next_btn.set_event_cb(self.next_address)
        self.prev_btn = lv.btn(self)
        self.prev_btn.set_width(150)
        lbl = lv.label(self.prev_btn)
        lbl.set_text("Previous")
        self.prev_btn.set_event_cb(self.prev_address)
        # finally show first address
        self.show_address(self._index)

    def show_address(self, idx:int, change=False):
        self.title.set_text("Address #%d" % (idx+1))
        self.title.align(self, lv.ALIGN.IN_TOP_MID, 0, 50)
        pub = self.account.derive([int(change), idx]).key
        addr = self.script_fn(pub).address(network=self.network)
        self.qr.set_text("bitcoin:"+addr)
        self.lbl.set_text(addr)
        self.lbl.set_align(lv.label.ALIGN.CENTER)
        self.lbl.align(self.qr, lv.ALIGN.OUT_BOTTOM_MID, 0, 20)
        self.prev_btn.set_state(lv.btn.STATE.INA if idx == 0 else lv.btn.STATE.REL)
        self.next_btn.align(self.qr, lv.ALIGN.OUT_BOTTOM_MID, 90, 70)
        self.prev_btn.align(self.qr, lv.ALIGN.OUT_BOTTOM_MID, -90, 70)

    def next_address(self, obj, event):
        if event == lv.EVENT.RELEASED:
            self._index += 1
            self.show_address(self._index)
            
    def prev_address(self, obj, event):
        if event == lv.EVENT.RELEASED and self._index > 0:
            self._index -= 1
            self.show_address(self._index)

scr = AddressNavigator(account, 
                script_fn=lambda pub: script.p2sh(script.p2wpkh(pub)),
                network=NETWORKS["test"]
                )

lv.scr_load(scr)



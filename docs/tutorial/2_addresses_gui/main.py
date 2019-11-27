import display
import lvgl as lv
from lvqr import QRCode
from bitcoin import bip32, script
from bitcoin.networks import NETWORKS

# inherits from lv.obj class - any object, will be a screen in our case
class AddressNavigator(lv.obj):
    def __init__(self, account,           # account is the HDKey
                *args,                    # unknown args we will pass to the parent
                script_fn=script.p2wpkh,  # how to calculate scriptpubkey
                network=NETWORKS["main"], # what network to use to get an address
                **kwargs                  # unknown kwargs we will pass to the parent
                ):
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
        child = self.account.derive([int(change), idx])
        addr = self.script_fn(child).address(network=self.network)
        self.qr.set_text("bitcoin:"+addr)
        self.lbl.set_text(addr)
        self.lbl.set_align(lv.label.ALIGN.CENTER)
        self.lbl.align(self.qr, lv.ALIGN.OUT_BOTTOM_MID, 0, 20)
        # disable the previous button if child index is 0
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

# parse xpub
xpub = bip32.HDKey.from_base58("vpub5ZEy1ogdkmtEHB4kRUZ6o6r7RREFckx7Mh4df39FEDPYkyQYLDnTqV68z7Knnmj5eGT9res4JfQbXEMiPrnzRGKS62zQPa4uNsXM1aS8iyP")

display.init()
scr = AddressNavigator(xpub,                              # bip-49 account xpub
                script_fn=lambda pub: script.p2wpkh(pub), # p2sh-p2wpkh
                network=NETWORKS["test"]                  # testnet
                )

lv.scr_load(scr)

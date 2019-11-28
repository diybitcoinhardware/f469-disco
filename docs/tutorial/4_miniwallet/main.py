from bitcoin import bip32, bip39, psbt, script
from bitcoin.networks import NETWORKS
from ubinascii import hexlify, a2b_base64, b2a_base64

import display
import lvgl as lv
from lvqr import QRCode

######## Bitcoin stuff ###########

class KeyStore:
    def __init__(self, mnemonic, password="", network=NETWORKS["test"]):
        seed = bip39.mnemonic_to_seed(mnemonic, password)
        self.network = network
        # our root key
        self.root = bip32.HDKey.from_seed(seed, version=network["xprv"])
        # fingerprint
        self.fingerprint = self.root.child(0).fingerprint
        # makes sense to cache the account
        self.derivation = "m/84h/%dh/0h" % network["bip32"] # contains coin type - 0 for main, 1 for test
        self.account = self.root.derive(self.derivation).to_public()

    def xpub(self):
        return "[%s%s]%s" % (
                hexlify(self.fingerprint).decode('ascii'),
                self.derivation[1:], # remove leading m
                self.account.to_base58()
            )

    def address(self, idx, change=False):
        sc = script.p2wpkh(self.account.derive([int(change), idx]))
        return sc.address(self.network)

    def parse_psbt(self, tx):
        # our result will be a dict of the form:
        # {
        #   "total_in": amount_in_sat,
        #   "spending": amount_in_sat,
        #   "spending_outputs": [ (address, amount_in_sat), ... ],
        #   "fee": amount_in_sat
        # }
        res = {}
        # print how much we are spending and where
        total_in = 0
        for inp in tx.inputs:
            total_in += inp.witness_utxo.value
        res["total_in"] = total_in
        change_out = 0 # value that goes back to us
        send_outputs = []
        for i, out in enumerate(tx.outputs):
            # check if it is a change or not:
            change = False
            # should be one or zero for single-key addresses
            for pub in out.bip32_derivations:
                # check if it is our key
                if out.bip32_derivations[pub].fingerprint == self.fingerprint:
                    hdkey = self.root.derive(out.bip32_derivations[pub].derivation)
                    mypub = hdkey.key.get_public_key()
                    if mypub != pub:
                        raise ValueError("Derivation path doesn't look right")
                    # now check if provided scriptpubkey matches
                    sc = script.p2wpkh(mypub)
                    if sc == tx.tx.vout[i].script_pubkey:
                        change = True
                        continue
            if change:
                change_out += tx.tx.vout[i].value
            else:
                send_outputs.append(tx.tx.vout[i])
        res["spending"] = total_in-change_out
        res["spending_outputs"] = []
        fee = total_in-change_out
        for out in send_outputs:
            fee -= out.value
            res["spending_outputs"].append((out.script_pubkey.address(self.network), out.value))
        res["fee"] = fee
        return res

    def sign_psbt(self, psbt):
        psbt.sign_with(self.root)

######## GUI stuff ###########

# on_release decorator
def on_release(callback):
    def cb(obj, event):
        if event == lv.EVENT.RELEASED:
            callback()
    return cb

class PopupScreen(lv.obj):
    def __init__(self):
        super().__init__()
        # first we save the active screen
        self.old_screen = lv.scr_act()
        # add back button
        btn = lv.btn(self)
        lbl = lv.label(btn)
        lbl.set_text(lv.SYMBOL.LEFT+" Back")
        btn.set_width(380)
        btn.align(self, lv.ALIGN.IN_BOTTOM_MID, 0, -30)
        btn.set_event_cb(on_release(self.close))
        self.back_btn = btn
        # activate the screen
        lv.scr_load(self)

    def close(self):
        # activate old screen
        lv.scr_load(self.old_screen)
        # delete this screen
        self.del_async()

class QRScreen(PopupScreen):
    def __init__(self, title="Title", message="Text", qrmessage="Text"):
        super().__init__()
        # create title
        self.title = lv.label(self)
        self.title.set_text(title)
        self.title.set_align(lv.label.ALIGN.CENTER)
        self.title.align(self, lv.ALIGN.IN_TOP_MID, 0, 50)
        # create qr code
        self.qr = QRCode(self)
        self.qr.set_text(qrmessage)
        self.qr.set_size(400)
        self.qr.align(self.title,lv.ALIGN.OUT_BOTTOM_MID, 0, 20)
        self.lbl = lv.label(self)
        # make sure it is within the screen
        self.lbl.set_long_mode(lv.label.LONG.BREAK)
        self.lbl.set_width(400)
        self.lbl.set_text(message)
        self.lbl.set_align(lv.label.ALIGN.CENTER)
        self.lbl.align(self.qr, lv.ALIGN.OUT_BOTTOM_MID, 0, 20)

class AddressNavigator(QRScreen):
    def __init__(self, address_function):
        super().__init__()
        self.address_function = address_function
        self._index = 0
        # create buttons
        self.next_btn = lv.btn(self)
        lbl = lv.label(self.next_btn)
        lbl.set_text("Next")
        self.next_btn.set_width(150)
        self.next_btn.set_event_cb(on_release(self.next_address))
        self.prev_btn = lv.btn(self)
        self.prev_btn.set_width(150)
        lbl = lv.label(self.prev_btn)
        lbl.set_text("Previous")
        self.prev_btn.set_event_cb(on_release(self.prev_address))
        # finally show first address
        self.show_address(self._index)

    def show_address(self, idx:int, change=False):
        self.title.set_text("Address #%d" % (idx+1))
        self.title.align(self, lv.ALIGN.IN_TOP_MID, 0, 50)
        addr = self.address_function(idx, change)
        self.qr.set_text("bitcoin:"+addr)
        self.lbl.set_text(addr)
        self.lbl.set_align(lv.label.ALIGN.CENTER)
        self.lbl.align(self.qr, lv.ALIGN.OUT_BOTTOM_MID, 0, 20)
        # disable the previous button if child index is 0
        self.prev_btn.set_state(lv.btn.STATE.INA if idx == 0 else lv.btn.STATE.REL)
        self.next_btn.align(self.qr, lv.ALIGN.OUT_BOTTOM_MID, 90, 70)
        self.prev_btn.align(self.qr, lv.ALIGN.OUT_BOTTOM_MID, -90, 70)

    def next_address(self):
        self._index += 1
        self.show_address(self._index)
            
    def prev_address(self):
        if self._index > 0:
            self._index -= 1
            self.show_address(self._index)
            
def show_menu(buttons):
    scr = lv.obj()
    obj = lv.label(scr)
    obj.set_text("What do you want to do?\n\n")
    obj.align(scr, lv.ALIGN.IN_TOP_MID, 0, 50)
    for text, callback in buttons:
        btn = lv.btn(scr)
        lbl = lv.label(btn)
        lbl.set_text(text)
        btn.set_width(scr.get_width()-100)
        btn.align(obj, lv.ALIGN.OUT_BOTTOM_MID, 0, 20)
        if callback is not None:
            btn.set_event_cb(callback)
        obj = btn
    lv.scr_load(scr)

######## Main logic ###########

class MessageScreen(PopupScreen):
    def __init__(self, title="Title", message="Text"):
        super().__init__()
        self.title = lv.label(self)
        self.title.set_text(title)
        self.title.align(self, lv.ALIGN.IN_TOP_MID, 0, 50)
        self.lbl = lv.label(self)
        self.lbl.set_long_mode(lv.label.LONG.BREAK)
        self.lbl.set_width(400)
        self.lbl.set_text(message)
        self.lbl.align(self.title, lv.ALIGN.OUT_BOTTOM_MID, 0, 50)

class PromptScreen(MessageScreen):
    def __init__(self, title="Title", message="Text", ok_text="Confirm", ok_cb=None):
        super().__init__(title, message)
        # resize back button
        self.back_btn.set_width(200)
        # add ok button
        self.ok_btn = lv.btn(self)
        self.ok_btn.set_width(200)
        lbl = lv.label(self.ok_btn)
        lbl.set_text(ok_text)
        self.back_btn.align(self, lv.ALIGN.IN_BOTTOM_LEFT, 30, -30)
        self.ok_btn.align(self, lv.ALIGN.IN_BOTTOM_RIGHT, -30, -30)
        self.ok_cb = ok_cb
        self.ok_btn.set_event_cb(on_release(self.confirm))

    def confirm(self):
        # don't forget to close self
        self.close()
        if self.ok_cb is not None:
            self.ok_cb()

class Wallet:
    def __init__(self, mnemonic, password="", network=NETWORKS["test"]):
        self.keystore = KeyStore(mnemonic, password, network)
        self.user_input = None

    def start(self):
        self.show_menu([
            ("Show master key", on_release(self.show_master_key)),
            ("Show addresses", on_release(self.show_addresses)),
            ("Sign PSBT", on_release(self.parse_psbt))
        ])
    
    def show_menu(self, buttons):
        scr = lv.obj()
        obj = lv.label(scr)
        obj.set_text("What do you want to do?\n\n")
        obj.align(scr, lv.ALIGN.IN_TOP_MID, 0, 50)
        for text, callback in buttons:
            btn = lv.btn(scr)
            lbl = lv.label(btn)
            lbl.set_text(text)
            btn.set_width(scr.get_width()-100)
            btn.align(obj, lv.ALIGN.OUT_BOTTOM_MID, 0, 20)
            if callback is not None:
                btn.set_event_cb(callback)
            obj = btn
        lv.scr_load(scr)

    def show_master_key(self):
        # we will create a screen here
        xpub = self.keystore.xpub()
        scr = QRScreen("Your master public key", xpub, xpub)

    
    def show_addresses(self):
        # pass address function to the address navigator constructor
        scr = AddressNavigator(self.keystore.address)

    def show_error(self, msg):
        MessageScreen("Error!", msg)

    def parse_psbt(self):
        # if nothing to be signed - show error message
        # in reality here we could trigger a QR code scanner and
        # listen for data from the host
        if self.user_input is None:
            self.show_error("Nothing to sign. Assign user data to 'wallet.user_input'")
        else:
            try: # it can fail
                self.tx = psbt.PSBT.parse(a2b_base64(self.user_input))
                info = self.keystore.parse_psbt(self.tx)
                print(info)
                self.show_psbt(info)
            except Exception as e:
                self.show_error("Failed to parse PSBT transaction:\n%r" % e)

    def show_psbt(self, info):
        title_txt = "Spending %d satoshi" % info["spending"]
        msg_txt = ""
        for addr, amount in info["spending_outputs"]:
            msg_txt += "%d satoshi to\n%s\n\n" % (amount, addr)
        msg_txt += "\nfee: %u satoshi" % info["fee"]
        PromptScreen(title_txt, msg_txt, ok_text="Sign "+lv.SYMBOL.RIGHT, ok_cb=self.sign)

    def sign(self):
        self.keystore.sign_psbt(self.tx)
        signed_tx = b2a_base64(self.tx.serialize()).decode('ascii').strip()
        print(signed_tx)
        QRScreen("Transaction is signed", "Scan it with your wallet", signed_tx)

display.init()
wallet = Wallet("alien visual jealous source coral memory embark certain radar capable clip edit", 
                network=NETWORKS["regtest"])
wallet.start()

wallet.user_input = "cHNidP8BAHICAAAAAY3LB6teEH6qJHluFYG3AQe8n0HDUcUSEuw2WIJ1ECDUAAAAAAD/////AoDDyQEAAAAAF6kU882+nVMDKGj4rKzjDB6NjyJqSBCHaPMhCgAAAAAWABQUbW8/trQg4d3PKL8WLi2kUa1BqAAAAAAAAQEfAMLrCwAAAAAWABTR6Cr4flM2A0LMGjGiaZ+fhod37SIGAhHf737H1jCUjkJ1K5DqFkaY0keihxeWBQpm1kDtVZyxGLMX7IZUAACAAQAAgAAAAIAAAAAAAAAAAAAAIgIDPtTTi27VFw59jdmWDV8b1YciQzhYGO7m8zB9CvD0brcYsxfshlQAAIABAACAAAAAgAEAAAAAAAAAAA=="

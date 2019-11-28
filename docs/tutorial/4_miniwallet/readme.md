# Minimal hardware wallet

In the previous parts of the tutorial we've learned everything we need to make our own small hardware wallet. It will work with hardcoded recovery phrase, only for single-key signing and only for native segwit addreses, but you can extend it further to support multisig, nested segwit and any custom functionality you need.

I would also like to invite you to contribute to our [specter-diy](https://github.com/cryptoadvance/specter-diy) - airgapped hardware wallet using QR codes for communication that is based on this micropython build. It is still in development, but it already supports multisig and there are a few exciting features coming soon - secure element integration and a development kit.

## Bitcoin Keystore

It makes sense to write a class that will store our keys and provide functionality required by our app.

It should be able to give us the master public key with fingerprint and derivation, derive receiving addresses, parse PSBT transactions, detect change addresses and tell us what we are spending and where, and finally sign psbt transaction.

This class has nothing to do with the GUI, we will keep it bitcoin-only. Most of the code here is adapted from the previous parts of the tutorial.

```py
from bitcoin import bip32, bip39, psbt, script
from bitcoin.networks import NETWORKS

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

# our keystore instance
keystore = KeyStore("alien visual jealous source coral memory embark certain radar capable clip edit",
                        network=NETWORKS["regtest"])
```

## Main menu

The goal of this part of the tutorial is to make several screen and implement transitions between them.

Let's start with the main menu - we will create 3 buttons there that will spawn other screens.

```py
import display
import lvgl as lv

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

display.init()
show_menu([
    ("Show master key", None),
    ("Show addresses", None),
    ("Sign PSBT", None)
    ])
```

Now we can write a callback and component for every button we've created.

If you remember, button callbacks have two arguments - an object that called it and the event. We normally don't care about the object and we always compare if the event is `lv.EVENT.RELEASED`, so it makes sense to write a small decorator that will handle all that for us.

```py
# on_release decorator
def on_release(callback):
    def cb(obj, event):
        if event == lv.EVENT.RELEASED:
            callback()
    return cb

@on_release
def show_master_key():
    # we will create a screen here
    print(keystore.xpub())

@on_release
def show_addresses():
    # we will create an address navigator here
    print(keystore.address(0))

@on_release
def sign_psbt():
    print("nothing to sign")
```

And our `show_menu` becomes:

```py
show_menu([
    ("Show master key", show_master_key),
    ("Show addresses", show_addresses),
    ("Sign PSBT", sign_psbt)
    ])
```

## Screens

It's time to write screens. Let's make a `PopupScreen` class that will appear on top of our main menu and we could close it with `Back` button:

```py
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
        # align it to the bottom
        btn.align(self, lv.ALIGN.IN_BOTTOM_MID, 0, -30)
        btn.set_event_cb(on_release(self.close))
        self.back_btn = btn # keep it in self if we want to change it later
        # activate the screen
        lv.scr_load(self)

    def close(self):
        # activate old screen
        lv.scr_load(self.old_screen)
        # delete this screen
        self.del_async()
```

### QR code

Many screens we are planning to implement should be able to show something as QR code and as text. It includes master public key, signed transaction and addresses as well. Let's make a `QRScreen` class.

We will add a title, message and qrmessage as arguments so we could pass everything into the constructor right away.

```py
from lvqr import QRCode

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
```

And our `show_master_key` function will spawn this screen:

```py
def show_master_key():
    # we will create a screen here
    xpub = keystore.xpub()
    scr = QRScreen("Your master public key", xpub, xpub)
```

### Address navigator

We already created an address navigator before, so let's copy some functions from there:

```py
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
```

And our `show_addresses` becomes:

```py
@on_release
def show_addresses():
    # pass address function to the address navigator constructor
    scr = AddressNavigator(keystore.address)
```

## Getting PSBT

Online emulator doesn't support input from the user yet. On Unixport you can use `raw_psbt = input()` or read it from file. On the actuall hardware you can use UART that is connected to the QR code scanner or a computer, or any other communication channel.

For demo purposes we will use hardcoded PSBT that you can change from interactive terminal in the online emulator. It will also work on unix and real hardware.

Also let's take a change and refactor our wallet to a class.

We will also create a new popup screen with just title and a message.

```py
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
        self.lbl.align(self.title, lv.ALIGN.OUT_BOTTOM_MID, 0, 100)


class Wallet:
    def __init__(self, mnemonic, password="", network=NETWORKS["test"]):
        self.keystore = KeyStore(mnemonic, password, network)
        self.user_input = None
        self.tx = None # our psbt transaction will be stored here

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
            pass


display.init()
wallet = Wallet("alien visual jealous source coral memory embark certain radar capable clip edit", 
                network=NETWORKS["regtest"])
wallet.start()
```

Now let's assign user data to the wallet, parse and display PSBT:

```py
wallet.user_input = "cHNidP8BAHICAAAAAY3LB6teEH6qJHluFYG3AQe8n0HDUcUSEuw2WIJ1ECDUAAAAAAD/////AoDDyQEAAAAAF6kU882+nVMDKGj4rKzjDB6NjyJqSBCHaPMhCgAAAAAWABQUbW8/trQg4d3PKL8WLi2kUa1BqAAAAAAAAQEfAMLrCwAAAAAWABTR6Cr4flM2A0LMGjGiaZ+fhod37SIGAhHf737H1jCUjkJ1K5DqFkaY0keihxeWBQpm1kDtVZyxGLMX7IZUAACAAQAAgAAAAIAAAAAAAAAAAAAAIgIDPtTTi27VFw59jdmWDV8b1YciQzhYGO7m8zB9CvD0brcYsxfshlQAAIABAACAAAAAgAEAAAAAAAAAAA=="
```

Parsing and displaying PSBT transaction:

```py
class Wallet:
    # ...
    def parse_psbt(self):
        if self.user_input is None:
            self.show_error("Nothing to sign. Assign user data to 'wallet.user_input'")
        else:
            try: # it can fail
                self.tx = psbt.PSBT.parse(a2b_base64(self.user_input))
                info = self.keystore.parse_psbt(self.tx)
                self.show_psbt(info)
            except Exception as e:
                self.show_error("Failed to parse PSBT transaction:\n%r" % e)

    def show_psbt(self, info):
        title_txt = "Spending %d satoshi" % info["spending"]
        msg_txt = ""
        for addr, amount in info["spending_outputs"]:
            msg_txt += "%d satoshi to\n%s\n\n" % (amount, addr)
        msg_txt += "\nfee: %u satoshi" % info["fee"]
        MessageScreen(title_txt, msg_txt)
```

It shows all the transaction details now but we are missing a "Sign" button. Let's add it by extending MessageScreen to PromptScreen:

```py
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
        # then call the callback 
        # (maybe another screen will be spawned here)
        if self.ok_cb is not None:
            self.ok_cb()

class Wallet:
    # ...
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
```

Great, we are done. We wrote a lot, but now we have something very close to actual hardware wallet. Try it online [in the sumulator](https://diybitcoinhardware.com/f469-disco/simulator/?script=https://raw.githubusercontent.com/diybitcoinhardware/f469-disco/master/docs/tutorial/4_miniwallet/main.py).

From here it's time to refactor, split the code to modules and finalize some things. Have fun!
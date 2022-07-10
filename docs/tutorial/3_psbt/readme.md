# Working with PSBT transactions and Bitcoin Core

Partially Signed Bitcoin Transaction format is a standard for unsigned bitcoin transactions defined in [BIP-174](https://github.com/bitcoin/bips/blob/master/bip-0174.mediawiki). It was developed specifically for hardware wallets that have very limited resources and doesn't have enough knowledge about current state of the blockchain, UTXO set, used keys etc.

PSBT transaction is basically a raw bitcoin transaction with additional metadata that hardware wallet can use to sign the transaction and to display relevant information to the user. Normally it includes derivation pathes for all inputs and change outputs, scriptpubkeys and amounts of previous outputs we are spending, sometimes it may have redeem or witness script and so on. It is very well documented in the BIP so it makes sense to go through it and read.

## Importing keys to Bitcoin Core

We will create our PSBT transactions with Bitcoin Core. I strongly recommend using `regtest` as it allows you to create your own toy bitcoin blockchain and you have full control over blocks generation and all the funds. But `testnet` is fine as well.

There is also a python-based desktop app running on top of Bitcoin Core and providing a convenient GUI for watch-only functionality and PSBTs - [specter-desktop](https://github.com/cryptoadvance/specter-desktop), it might make sense to look at it. But here we will focus on pure Bitcoin Core without any extensions.

To create PSBT we first need to create a new watch-only wallet, import our master keys to it and receive some funds. Bitcoin Core uses a descriptor language to import new addresses to the wallet.

Descriptor for native segwit addresses looks like this: `wpkh([fingerprint/<derivation/path>]xpub/0/*)` for receiving addresses and `.../1/*` for change addresses. Let's get this descriptor from our wallet:

Fingerprint is a `hash160` of the root public key and works as an identifier of our root key.

```python
from embit import bip39, bip32
from embit.networks import NETWORKS
from ubinascii import hexlify

# convert bip-39 mnemonic to root HD key
mnemonic = "alien visual jealous source coral memory embark certain radar capable clip edit"
seed = bip39.mnemonic_to_seed(mnemonic)
root = bip32.HDKey.from_seed(seed, version=NETWORKS["test"]["xprv"])

# get bip84-xpub to import to Bitcoin Core:
# we will use the form [fingerprint/derivation]xpub
# to import to Bitcoin Core with descriptors

# first let's get the root fingerprint
# we can get it from any child of the root key
fingerprint = root.child(0).fingerprint
hardened_derivation = "m/84h/1h/0h"
# derive account according to bip84
bip84_xprv = root.derive(hardened_derivation)
# corresponding master public key:
bip84_xpub = bip84_xprv.to_public()
print("[%s%s]%s\n" % (
            hexlify(fingerprint).decode('utf-8'),
            hardened_derivation[1:],
            bip84_xpub.to_base58())
    )
# >> [b317ec86/84h/1h/0h]tpubDCKVXMvGq2YRczuCLcfcY8TaxHGjFTuhFrkRGpBk4DXmQeJ
#    XM3JAz8ijxTS59PZQBUtiq5wkstpzgvow7A25F4vDbmiAEy3rE4xHcR2XUUq
```

Now we can create a new wallet in Bitcoin Core with private keys disabled (watch-only):

```
bitcoin-cli -regtest createwallet myhardwarewallet true
```

To import keys to the wallet we need to add checksums to the descriptor. `getdescriptorinfo` will help us to do it.

```
bitcoin-cli -regtest getdescriptorinfo "wpkh([b317ec86/84h/1h/0h]tpubDCKVXMvGq2YRczuCLcfcY8TaxHGjFTuhFrkRGpBk4DXmQeJXM3JAz8ijxTS59PZQBUtiq5wkstpzgvow7A25F4vDbmiAEy3rE4xHcR2XUUq/0/*)"
```

From the result copy the checksums and add them after the descriptor like this: `wsh(.../0/*)#2e3mrc2y`

Great, now we can import 1000 receiving and change addresses to our wallet using descriptors with checksums:

```
bitcoin-cli -regtest -rpcwallet=myhardwarewallet importmulti '[{"desc":"wpkh([b317ec86/84h/1h/0h]tpubDCKVXMvGq2YRczuCLcfcY8TaxHGjFTuhFrkRGpBk4DXmQeJXM3JAz8ijxTS59PZQBUtiq5wkstpzgvow7A25F4vDbmiAEy3rE4xHcR2XUUq/0/*)#2e3mrc2y","timestamp":"now","range":[0,1000],"internal":false,"watchonly":true,"keypool":true},{"desc":"wpkh([b317ec86/84h/1h/0h]tpubDCKVXMvGq2YRczuCLcfcY8TaxHGjFTuhFrkRGpBk4DXmQeJXM3JAz8ijxTS59PZQBUtiq5wkstpzgvow7A25F4vDbmiAEy3rE4xHcR2XUUq/1/*)#md567d6u","timestamp":"now","range":[0,1000],"internal":true,"watchonly":true,"keypool":true}]' '{"rescan":false}'
```

Notice that first descriptor is marked as external (`"internal":false`) and second as internal. Also as it is a new wallet without any history we've set `rescan` option to `false`. 

Using bitcoin-cli is not super convenient, but doable.

## Getting some money to the wallet

We have two ways to generate addresses - on the hardware wallet or in bitcoin core.

On the hardware wallet we can use our address navigator from the previous part of the tutorial, or just write a small script:

```python
from embit import script

child = bip84_xpub.derive("m/0/0")
first_addr = script.p2wpkh(child).address(NETWORKS["regtest"])
print(first_addr)
```

With Bitcoin Core we can do the same using this command:

```
bitcoin-cli -regtest -rpcwallet=myhardwarewallet getnewaddress "" bech32
```

We explicitly tell Bitcoin Core that we want to get bech32 address (native segwit). 

Now we can send some funds to this address. Let's generate 101 blocks to this address:

```
bitcoin-cli -regtest generatetoaddress 101 bcrt1q685z47r72vmqxskvrgc6y6vln7rgwaldnuruwk
```

## Creating PSBT in Bitcoin Core

Let's create a PSBT that sends some money to some random address (for example `2MyMDviGxP8jkTBZiuLPwWfy2jKCTAoFoxP`). Don't forget to define that we want to use bech32 for change and that we want to include derivation information.

```
bitcoin-cli -regtest -rpcwallet=myhardwarewallet walletcreatefundedpsbt '[]' '[{"2MyMDviGxP8jkTBZiuLPwWfy2jKCTAoFoxP":1}]' 0 '{"includeWatching":true,"change_type":"bech32"}' true
```

We will get the psbt we can start working with:
```
cHNidP8BAHICAAAAAcAiqnT66whblrAy+sRnAxMqusYBCt5CObq1YdO7RDqUAAAAAAD+////AgAgECQBAAAAFgAU1wt1dfsk78kR1EeF4fPPzj6jTw0A4fUFAAAAABepFELzMvZSa13zYflKwHse4o/VbF/mhwAAAAAAAQEfGAwGKgEAAAAWABTR6Cr4flM2A0LMGjGiaZ+fhod37SIGAhHf737H1jCUjkJ1K5DqFkaY0keihxeWBQpm1kDtVZyxGLMX7IZUAACAAQAAgAAAAIAAAAAAAAAAAAAiAgI4QR+S6RWCsMCkH7+oe1/v4wH90b7rbx9hWWgwk2fXHBizF+yGVAAAgAEAAIAAAACAAQAAAAIAAAAAAA==
```

## Parsing PSBT in MicroPython

```python
from embit import psbt
from ubinascii import a2b_base64

# parse psbt transaction
b64_psbt = "cHNidP8BAHICAAAAAcAiqnT66whblrAy+sRnAxMqusYBCt5CObq1YdO7RDqUAAAAAAD+////AgAgECQBAAAAFgAU1wt1dfsk78kR1EeF4fPPzj6jTw0A4fUFAAAAABepFELzMvZSa13zYflKwHse4o/VbF/mhwAAAAAAAQEfGAwGKgEAAAAWABTR6Cr4flM2A0LMGjGiaZ+fhod37SIGAhHf737H1jCUjkJ1K5DqFkaY0keihxeWBQpm1kDtVZyxGLMX7IZUAACAAQAAgAAAAIAAAAAAAAAAAAAiAgI4QR+S6RWCsMCkH7+oe1/v4wH90b7rbx9hWWgwk2fXHBizF+yGVAAAgAEAAIAAAACAAQAAAAIAAAAAAA=="
# first convert it from base64 to raw bytes
raw = a2b_base64(b64_psbt)
# then parse
tx = psbt.PSBT.parse(raw)

# print how much we are spending and where
print("Parsing PSBT transaction...")
total_in = 0
for inp in tx.inputs:
    total_in += inp.witness_utxo.value
print("Inputs:", total_in, "satoshi")
change_out = 0 # value that goes back to us
send_outputs = []
for i, out in enumerate(tx.outputs):
    # check if it is a change or not:
    change = False
    # should be one or zero for single-key addresses
    for pub in out.bip32_derivations:
        # check if it is our key
        if out.bip32_derivations[pub].fingerprint == fingerprint:
            hdkey = root.derive(out.bip32_derivations[pub].derivation)
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
print("Spending", total_in-change_out, "satoshi")
fee = total_in-change_out
for out in send_outputs:
    fee -= out.value
    print(out.value,"to",out.script_pubkey.address(NETWORKS["test"]))
print("Fee:",fee,"satoshi")
```

## Signing PSBT

```python
# sign the transaction
tx.sign_with(root)
raw = tx.serialize()
# convert to base64
b64_psbt = b2a_base64(raw)
# somehow b2a ends with \n...
if b64_psbt[-1:] == b"\n":
    b64_psbt = b64_psbt[:-1]
# print
print("\nSigned transaction:")
print(b64_psbt.decode('utf-8'))
```

Transaction is ready to be finalized and broadcasted:

```
bitcoin-cli -regtest finalizepsbt cHNidP8BAHICAAAAAcAiqnT66whblrAy+sRnAxMqusYBCt5CObq1YdO7RDqUAAAAAAD+////AgAgECQBAAAAFgAU1wt1dfsk78kR1EeF4fPPzj6jTw0A4fUFAAAAABepFELzMvZSa13zYflKwHse4o/VbF/mhwAAAAAAAQEfGAwGKgEAAAAWABTR6Cr4flM2A0LMGjGiaZ+fhod37SICAhHf737H1jCUjkJ1K5DqFkaY0keihxeWBQpm1kDtVZyxRzBEAiARkaZfb7U3UzxTnmjrmIF82a/ky8eOegV/alKHTIa+eAIgSO45ZkAWoutrGoiHpfSTfR2RKzdXxmA9f06iIVVWNuoBIgYCEd/vfsfWMJSOQnUrkOoWRpjSR6KHF5YFCmbWQO1VnLEYsxfshlQAAIABAACAAAAAgAAAAAAAAAAAACICAjhBH5LpFYKwwKQfv6h7X+/jAf3RvutvH2FZaDCTZ9ccGLMX7IZUAACAAQAAgAAAAIABAAAAAgAAAAAA
```

```
bitcoin-cli -regtest sendrawtransaction 02000000000101c022aa74faeb085b96b032fac46703132abac6010ade4239bab561d3bb443a940000000000feffffff020020102401000000160014d70b7575fb24efc911d44785e1f3cfce3ea34f0d00e1f5050000000017a91442f332f6526b5df361f94ac07b1ee28fd56c5fe6870247304402201191a65f6fb537533c539e68eb98817cd9afe4cbc78e7a057f6a52874c86be78022048ee39664016a2eb6b1a8887a5f4937d1d912b3757c6603d7f4ea221555636ea01210211dfef7ec7d630948e42752b90ea164698d247a2871796050a66d640ed559cb100000000
```

Yey! We did it! Check it out in the [in the simulator](https://diybitcoinhardware.com/f469-disco/simulator/?script=https://raw.githubusercontent.com/diybitcoinhardware/f469-disco/master/docs/tutorial/3_psbt/main.py).

Let's put everything we learned together in a minimal hardware wallet in the [last part](../4_miniwallet) of the tutorial.
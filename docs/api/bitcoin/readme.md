# Bitcoin module for MicroPython

Most of the classes have `.serialize()` method and `.parse(bytes)` class method. `.serialize()` method returns a byte array, class method `.parse(bytes)` parses the array and creates an instance of corresponding class.

Examples:

```python
from ubinascii import unhexlify, hexlify
from bitcoin import ec, bip32, script

pubkey = ec.PublicKey.parse(unhexlify("03fa7024c13f5a71550237bec1d31c98f4e00acdff20a86f83c358f0cba43085ec"))
sig = ec.Signature.parse(unhexlify("3044022030c4962a980dee217de79f31f30bca8e1400f761165751012e8e989ce097559802200907e3eb97f8187b6e7597675196178579f6efe06e905a8b9692d1f7217dc940"))
hdkey = bip32.HDKey.parse(unhexlify("0488b21e0387b868958000000001fc720eba849d421f7b0e28a518e8b68c81d990a863473bad364c483b46cc60027b30a279c445ab978224b48a10a33acf89de4dbb649fef06b0797ff80f08f1f3"))
sc = script.Script.parse(unhexlify("1976a914182be9fb5788941a787b9f0927df2c74e6a0bf4088ac"))

print(pubkey.serialize())
# >> b'\x03\xfap$\xc1?ZqU\x027\xbe\xc1\xd3\x1c\x98\xf4\xe0\n\xcd\xff \xa8o\x83\xc3X\xf0\xcb\xa40\x85\xec'
print(sig.serialize())
# >> b'0D\x02 0\xc4\x96*\x98\r\xee!}\xe7\x9f1\xf3\x0b\xca\x8e\x14\x00\xf7a\x16WQ\x01.\x8e\x98\x9c\xe0\x97U\x98\x02 \t\x07\xe3\xeb\x97\xf8\x18{nu\x97gQ\x96\x17\x85y\xf6\xef\xe0n\x90Z\x8b\x96\x92\xd1\xf7!}\xc9@'
print(hdkey.serialize())
# >> b'\x04\x88\xb2\x1e\x03\x87\xb8h\x95\x80\x00\x00\x00\x01\xfcr\x0e\xba\x84\x9dB\x1f{\x0e(\xa5\x18\xe8\xb6\x8c\x81\xd9\x90\xa8cG;\xad6LH;F\xcc`\x02{0\xa2y\xc4E\xab\x97\x82$\xb4\x8a\x10\xa3:\xcf\x89\xdeM\xbbd\x9f\xef\x06\xb0y\x7f\xf8\x0f\x08\xf1\xf3'
print(sc.serialize())
# >> b"\x19v\xa9\x14\x18+\xe9\xfbW\x88\x94\x1ax{\x9f\t'\xdf,t\xe6\xa0\xbf@\x88\xac"
```

For some classes that have a human-readable form there is `.to_base58()` method and `.from_base58(str)` class method.

Examples:

```python
from bitcoin import ec, bip32

pk = ec.PrivateKey.from_base58("L1168XhX8EEdkLMD6rcnt15xuUJamedVME1ksHQGck2PFp6ovuhW")
hdprv = bip32.HDKey.from_base58("xprvA1eEfjteSrXB4PEcFnyZwQMcvZWKyJvBLEEgERF5u4C2KfGxMKfANB4HbSFHRnATsXXTe1L8CmkVx8tk1EccS8CP1RoJ14hZydzMv9ZLPjs")
hdpub = bip32.HDKey.from_base58("zpub6r3T7XHeHWiLAA61Pf2kz1qgCXzQKrcW4tyC8pShKDS3qX6E1sNFZ3sBZX2wrsQfC8cVgdSPNdxT13DrGPdNCuPJPyJKzzwThd4kVCmDsBz")

print(pk.to_base58())
# >> L1168XhX8EEdkLMD6rcnt15xuUJamedVME1ksHQGck2PFp6ovuhW
print(hdprv.to_base58())
# >> xprvA1eEfjteSrXB4PEcFnyZwQMcvZWKyJvBLEEgERF5u4C2KfGxMKfANB4HbSFHRnATsXXTe1L8CmkVx8tk1EccS8CP1RoJ14hZydzMv9ZLPjs
print(hdpub.to_base58())
# >> zpub6r3T7XHeHWiLAA61Pf2kz1qgCXzQKrcW4tyC8pShKDS3qX6E1sNFZ3sBZX2wrsQfC8cVgdSPNdxT13DrGPdNCuPJPyJKzzwThd4kVCmDsBz
```

## `bitcoin.ec` - elliptic curve stuff

For HD wallets scroll down to `bitcoin.bip32` section.

This module relies on the [bindings](../secp256k1) of `secp256k1` library from [Bitcoin Core](https://github.com/bitcoin-core/secp256k1).

In most cases you don't want to call constructors explicitly - use `.parse(bytes)` and `.from_base58(str)` class methods when possible.

Example:

```python
from bitcoin import ec
from ubinascii import hexlify, unhexlify
import hashlib

# create a 32-byte secret
secret = hashlib.sha256("my super secret").digest()
# create private key from a secret
pk = ec.PrivateKey(secret)
print(pk.to_base58())
# get public key from private key
pub = pk.get_public_key()

msg = "Hello!"
msg_hash = hashlib.sha256(msg).digest()

# sign a message
sig = pk.sign(msg_hash)
# verify a signature
if pub.verify(sig, msg_hash):
    print("Signature is valid")
```

### `ec.PrivateKey` - individual private key

### `ec.PublicKey` - individual public key

#### `ec.PublicKey(point, compressed=True)` - constructor

`point` is a C structure from `secp256k1` library representing a point on elliptic curve.

`compressed` is a boolean flag used in `sec()` and `serialize()` methods. It determines what format to use - 65-byte `04<x><y>` or 33-byte `<02 or 03><x>`. In most cases `compressed` flag should be `True`.

#### `ec.PublicKey.parse(bytes)` - class method to parse a public key

Parses a public key from byte array. Only 33 or 65-byte arrays are valid. 

Example:

```python
pub = ec.PublicKey.parse(unhexlify("026e1ef3bd2bc019574d99b9be251b4334113d16b1b60826505118cffd5112d22d"))
pub2 = ec.PublicKey.parse(unhexlify("046e1ef3bd2bc019574d99b9be251b4334113d16b1b60826505118cffd5112d22dce187696b60ad6bc6b9c443a7db5ad2628c1b181a835197fe12076241de5fca8"))
```

#### `.serialize()` and `.sec()`

Return a byte array with the public key serialized in SEC format. Length of the array is 33 bytes if `compressed` is `True`, otherwise 65 bytes.

#### `.verify(sig, msg_hash)`

Verifies ECDSA signature (`sig`) against the hash of the message `msg_hash`.

`sig` should be an instance of the `ec.Signature` class, `msg_hash` should be a 32-byte array (`sha256(msg)`)

Returns `True` if the signature is valid, otherwise `False`.

### `ec.Signature` - ECDSA signature

## `bitcoin.bip39` - recovery phrases

Functions to manage recovery phrases defined in [BIP-39](https://github.com/bitcoin/bips/blob/master/bip-0039.mediawiki)

Example:

```python
from bitcoin import bip39
from ubinascii import hexlify
import hashlib

# create initial entropy, 16 bytes for example
entropy = hashlib.sha256("my very random entropy").digest()[:16]

# convert it to bip39 mnemonic
phrase = bip39.mnemonic_from_bytes(entropy)
print(phrase)
# >> lab blade movie crater bulb only prize cloth unfold smile boring talent

# convert it to 64-byte seed
seed = bip39.mnemonic_to_seed(phrase, password="super secure password111")
print(hexlify(seed))
# >> d6aeb152aab2acb374299afe7058bc95ead89bad5daaae57d804dd10c926249f
#    1088778ee95e78a9caea4981b9459cb1048648a73387598606854fb4121bd610
```

#### `bip39.mnemonic_from_bytes(bytes)`

Converts a byte array with entropy to a recovery phrase (mnemonic). Minimal entropy length is 16 bytes that returns 12 words phrase. Every 4 extra bytes add 3 more words to the phrase, maximum is 32 bytes - 24 words.

#### `bip39.mnemonic_to_bytes(phrase)`

Converts the recovery phrase to entropy byte array. It will throw an error if recovery phrase is invalid.

#### `bip39.mnemonic_to_seed(phrase, password="")`

Converts a recovery phrase and a password to a 64-byte seed that can be used for HD keys (`bitcoin.bip32`)

#### `bip39.mnemonic_is_valid(phrase)`

Returns `True` if recovery phrase is valid according to BIP-39, otherwise - `False`

#### `bip39.find_candidates(word_part, nmax=5)`

Returns a list of words that start with `word_part`, maximum - `nmax`. Can be useful for autocomplete of words based on first letters.

## `bitcoin.bip32` - HD wallets

Classes for HD wallets defined in [BIP-32](https://github.com/bitcoin/bips/blob/master/bip-0039.mediawiki)

Both HD private key and HD master key share the same class - `bip32.HDKey`.

Example:

```python
from bitcoin import bip32, bip39
from bitcoin.networks import NETWORKS

seed = bip39.mnemonic_to_seed("lab blade movie crater bulb only prize cloth unfold smile boring talent")

root = bip32.HDKey.from_seed(seed)
print(root.to_base58())
# >> xprv9s21ZrQH143K3pq9NL6GJNTTwwRfqLy8ckXXbzki8yrKd1rad2UdYsNu9oftEZ
#    Gf2Hj9B5WAaZrwE4WqM3jp8fTrUQhifhq2t9BVRyqtQjV

print("\nBIP-84 - native segwit")
# derive account according to bip44
bip84_xprv = root.derive("m/84h/1h/0h")
# customize version if you want to
bip84_xprv.version = NETWORKS["test"]["zprv"]
print(bip84_xprv.to_base58())
# >> vprv9LMG32yessLFzJtt9VKN9oZZppxGyrrmZ8V81LyqXtYxvD2ncVHjUahwzqNmNM
#    8SwC7w81UZzqUTYbBvAXi1YJKmWNPK8sYRwTgXwELxbmS

# corresponding master public key:
bip84_xpub = bip84_xprv.to_public()
print(bip84_xpub.to_base58())
# >> vpub5ZLcSYWYiEtZCnyMFWrNWwWJNrnmPKacvMQiojPT6E5wo1MwA2bz2P2Rr8Zt9E
#    VrZtdZMM4kAyhyyWLryV9r4UpqAvYVzrDiB4CoheUwiou
```

## `bitcoin.script`

Example: [source code](../examples/addresses.py), [try online](https://diybitcoinhardware.com/f469-disco/simulator/index.html?script=https://raw.githubusercontent.com/diybitcoinhardware/f469-disco/master/examples/addresses.py)

## `bitcoin.transaction`

Example: [source code](../examples/transactions.py), [try online](https://diybitcoinhardware.com/f469-disco/simulator/index.html?script=https://raw.githubusercontent.com/diybitcoinhardware/f469-disco/master/examples/transactions.py)

## `bitcoin.psbt` - Partially Signed Bitcoin Transactions

Example: [source code](../examples/psbt.py), [try online](https://diybitcoinhardware.com/f469-disco/simulator/index.html?script=https://raw.githubusercontent.com/diybitcoinhardware/f469-disco/master/examples/psbt.py)

# Helpers

## `bitcoin.networks` - a few network constants

## `bitcoin.hashes` - one-line hash functions

## `bitcoin.base58`

## `bitcoin.bech32`

## `bitcoin.compact` - compact int tools

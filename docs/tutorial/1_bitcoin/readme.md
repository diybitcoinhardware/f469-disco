# Working with Bitcoin in MicroPython

Getting started with hardware can be pretty annoying. You need to buy a board, wait for delivery, figure out how to set up the environment, compile the firmware, upload it to the board... We will postpone all that for now and start with the [online simulator](https://diybitcoinhardware.com/f469-disco/simulator/index.html) instead.

It allows you to write programs in MicroPython and see how it will work on the board. It is not perfect and missing a few features, but it is pretty close to what you will experiense with the real hardware.

Let's start with the most interesting stuff right away - bitcoin.

In this part of the tutorial we will take our recovery phrase ([BIP-39](https://github.com/bitcoin/bips/blob/master/bip-0039.mediawiki)), convert it to HD key ([BIP-32](https://github.com/bitcoin/bips/blob/master/bip-0032.mediawiki)) and derive first 5 native segwit addresses from it ([bip84](https://github.com/bitcoin/bips/blob/master/bip-0084.mediawiki)). We can check that we did everything correctly using this [great tool from Ian Coleman](https://iancoleman.io/bip39/).

**TL;DR**: Check out the [result in the simulator](https://diybitcoinhardware.com/f469-disco/simulator/index.html?script=https://raw.githubusercontent.com/diybitcoinhardware/f469-disco/master/docs/tutorial/1_bitcoin/main.py).

## Recovery phrase: BIP-39

`gospel palace choice either lawsuit divorce manual turkey pink tuition fat pair` - you've seen phrases like this before. These recovery phrases became standards in the industry and almost every wallet uses them. We will stick to the standard ([BIP-39](https://github.com/bitcoin/bips/blob/master/bip-0039.mediawiki)) and use them as well.

Fundamentally it is just a convenient way of representing some random number in a human-readable form. It contains a checksum and uses a fixed dictionary so if you make a mistake while typing it the wallet will spot it. Then this recovery phrase together with the password can be converted to a 64-byte seed used for key derivation in [BIP-32](https://github.com/bitcoin/bips/blob/master/bip-0032.mediawiki).

`bitcoin.bip39` module provides all necessary functionality to convert bytes to recovery phrases and back as well as calculating the seed for the recovery phrase and the password.

Entropy corresponding to the recovery phrase above is `64d3e4a0a387e28021df55a51d454dcf`. We could generate it at random using TRNG on the board (`urandom.get_random_bytes`), mix some user entropy and environmental noise there to get good overall randomness. Initial entropy generation is the point where good random numbers are really important.

We will leave entropy generation for now and use predefined entropy. The code below converts entropy bytes to recovery phrase and then converts recovery phrase and a password `mysecurepassword` to the 64-byte seed:

```python
from bitcoin import bip39
from ubinascii import hexlify

entropy = b'\x64\xd3\xe4\xa0\xa3\x87\xe2\x80\x21\xdf\x55\xa5\x1d\x45\x4d\xcf'

recovery_phrase = bip39.mnemonic_from_bytes(entropy)
print("Your recovery phrase:\n%s\n" % recovery_phrase)

# uncomment this line to make invalid mnemonic:
# recovery_phrase += " satoshi"

# you can check if recovery phrase is valid or not:
if not bip39.mnemonic_is_valid(recovery_phrase):
    raise ValueError("Meh... Typo in the recovery?")

# convert mnemonic and password to bip-32 seed
seed = bip39.mnemonic_to_seed(recovery_phrase, password="mysecurepassword")
print("Seed:", hexlify(seed).decode("ascii"))
```

## HD wallets: BIP-32

Back in the days we were generating all private keys randomly. And it was awful - we had to make backups very often, backup size was growing, we had to reuse addresses... Dark times.

[BIP-32](https://github.com/bitcoin/bips/blob/master/bip-0032.mediawiki) solved this. Using small amount of initial entropy and magic of hash functions we are able to derive any amount of private keys. And even better, we can use master public keys to generate new public keys without any knowledge about private keys (only if non-hardened children are used).

Derivation paths are also kinda standartized. We have [BIP-44](https://github.com/bitcoin/bips/blob/master/bip-0044.mediawiki), [BIP-49](https://github.com/bitcoin/bips/blob/master/bip-0049.mediawiki) and [BIP-84](https://github.com/bitcoin/bips/blob/master/bip-0084.mediawiki) for that. Some of the wallets (i.e. Bitcoin Core, Green Wallet) don't use these standards for derivation, others do.

Let's use BIP-84 and generate an extended public key for testnet. We can import this extended public key to Bitcoin Core or Electrum and watch our addresses.

```python
from bitcoin import bip32
# NETWORKS contains all constants for HD keys and addresses
from bitcoin.networks import NETWORKS
# we will use testnet:
network = NETWORKS["test"]

# create HDKey from 64-byte seed
root_key = bip32.HDKey.from_seed(seed)
# generate an account child key:
# purpose: 84h - BIP-84
# coin type: 1h - Testnet
# account: 0h - first account
account = root_key.derive("m/84h/1h/0h")
# convert HD private key to HD public key
account_pub = account.to_public()
# for Bitcoin Core: pure BIP-32 serialization
print("Your xpub:", account_pub.to_base58(version=network["xpub"]))
# for Electrum and others who cares about SLIP-0132
# used for bip-84 by many wallets
print("Your zpub:", account_pub.to_base58(version=network["zpub"]))
```

## Addresses

Let's generate first 5 receiving addresses from our master public key. First we need to derive public keys, and then generate corresponding scripts and convert them to addresses. Address is not a feature of the public key, it's a feature of the output script. We have a few helper functions in `bitcoin.script` to build them.

Common single-key bitcoin scripts are:
- legacy pay-to-pubkey-hash
- modern pay-to-witness-pubkey-hash that use bech32 encoding for addresses
- modern pay-to-witness-pubkey-hash nested in legacy pay-to-script-hash for backward compatibility with legacy wallets

```python
from bitcoin import script

xpub_bip44 = root_key.derive("m/44h/1h/0h").to_public()
print("\nLegacy xpub:", xpub_bip44.to_base58(version=network["xpub"]))
print("Legacy addresses:")
for i in range(5):
    # m/0/i is used for receiving addresses and m/1/i for change addresses
    pub = xpub_bip44.derive("m/0/%d" % i)
    # get p2pkh script
    sc = script.p2pkh(pub)
    print("Address %i: %s" % (i, sc.address(network)))

xpub_bip84 = root_key.derive("m/84h/1h/0h").to_public()
print("\nSegwit zpub:", xpub_bip84.to_base58(version=network["zpub"]))
print("Segwit addresses:")
for i in range(5):
    pub = xpub_bip84.derive("m/0/%d" % i)
    # get p2wsh script
    sc = script.p2wpkh(pub)
    print("Address %i: %s" % (i, sc.address(network)))

xpub_bip49 = root_key.derive("m/49h/1h/0h").to_public()
print("\nNested Segwit ypub:", xpub_bip49.to_base58(version=network["ypub"]))
print("Nested segwit addresses:")
for i in range(5):
    pub = xpub_bip49.derive("m/0/%d" % i)
    # get p2sh(p2wpkh) script
    sc = script.p2sh(script.p2wpkh(pub))
    print("Address %i: %s" % (i, sc.address(network)))
```

Great! Enough for now, let's move on and make a GUI for what we just did: a simple screen where we could navigate between addresses and display them as QR codes.

Continue to the [next part](../2_addresses_gui)
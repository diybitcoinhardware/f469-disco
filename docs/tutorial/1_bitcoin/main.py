from ubinascii import hexlify
from bitcoin import bip32, bip39, script
# NETWORKS contains all constants for HD keys and addresses
from bitcoin.networks import NETWORKS
# we will use testnet:
network = NETWORKS["test"]

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
print("\nYour xpub:", account_pub.to_base58(version=NETWORKS["test"]["xpub"]))
# for Electrum and others who cares about SLIP-0132
# used for bip-84 by many wallets
print("\nYour zpub:", account_pub.to_base58(version=NETWORKS["test"]["zpub"]))

print("\nLegacy addresses:")
xpub_bip44 = root_key.derive("m/44h/1h/0h").to_public()
print("Legacy xpub:", xpub_bip44.to_base58(version=network["xpub"]))
for i in range(5):
    # m/0/i is used for receiving addresses and m/1/i for change addresses
    pub = xpub_bip44.derive("m/0/%d" % i)
    # get p2pkh script
    sc = script.p2pkh(pub)
    print("Address %i: %s" % (i, sc.address(network)))
    
print("\nSegwit addresses:")
xpub_bip84 = root_key.derive("m/84h/1h/0h").to_public()
print("Segwit zpub:", xpub_bip84.to_base58(version=network["zpub"]))
for i in range(5):
    pub = xpub_bip84.derive("m/0/%d" % i)
    # get p2wsh script
    sc = script.p2wpkh(pub)
    print("Address %i: %s" % (i, sc.address(network)))
    
print("\nNested segwit addresses:")
xpub_bip49 = root_key.derive("m/49h/1h/0h").to_public()
print("Nested Segwit ypub:", xpub_bip49.to_base58(version=network["ypub"]))
for i in range(5):
    pub = xpub_bip49.derive("m/0/%d" % i)
    # get p2sh(p2wpkh) script
    sc = script.p2sh(script.p2wpkh(pub))
    print("Address %i: %s" % (i, sc.address(network)))
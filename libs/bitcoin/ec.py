import secp256k1
from . import base58
from .networks import NETWORKS
from binascii import hexlify

class PublicKey:
    def __init__(self, point, compressed:bool=True):
        self._point = point[:]
        self.compressed = compressed

    @classmethod
    def parse(cls, sec):
        point = secp256k1.ec_pubkey_parse(sec)
        compressed = (sec[0]!=0x04)
        return cls(point, compressed)

    def sec(self):
        """Sec representation of the key"""
        flag = secp256k1.EC_COMPRESSED if self.compressed else secp256k1.EC_UNCOMPRESSED
        return secp256k1.ec_pubkey_serialize(self._point, flag)

    def _to_xonly(self):
        return secp256k1.xonly_pubkey_from_pubkey(self._point)

    def xonly(self):
        """x-only representation of the key"""
        return secp256k1.xonly_pubkey_serialize(self._to_xonly())

    @classmethod
    def from_xonly(self, xonly):
        return cls(secp256k1.xonly_pubkey_parse(xonly))

    def serialize(self):
        return self.sec()

    def verify(self, sig, msg_hash):
        return secp256k1.ecdsa_verify(sig._sig, msg_hash, self._point)

    def schnorr_verify(self, sig, msg_hash, tweak=None):
        # TODO: add tweak processing here
        return secp256k1.schnorrsig_verify(sig._sig, msg_hash, self._to_xonly())

    def __lt__(self, other):
        # for lexagraphic ordering
        return self.serialize() < other.serialize()

    def __gt__(self, other):
        # for lexagraphic ordering
        return self.serialize() > other.serialize()

    def __repr__(self):
        return "PublicKey(%s)" % hexlify(self.serialize()).decode('utf-8')

    def __eq__(self, other):
        return self._point == other._point

    def __ne__(self, other):
        return self._point != other._point

    def __hash__(self):
        return hash(self._point)

class PrivateKey:
    def __init__(self, secret, compressed:bool=True):
        """Creates a private key from 32-byte array"""
        if len(secret)!=32:
            raise ValueError("Secret should be 32-byte array")
        if not secp256k1.ec_seckey_verify(secret):
            raise ValueError("Secret is not valid (larger then N?)")
        self.compressed = compressed
        self._secret = secret[:]

    def wif(self, network=NETWORKS["main"]):
        """Export private key as Wallet Import Format string.
        Prefix 0x80 is used for mainnet, 0xEF for testnet.
        This class doesn't store this information though.
        """
        prefix = network["wif"]
        b = prefix+self._secret
        if self.compressed:
            b += bytes([0x01])
        return base58.encode_check(b)

    def sec(self):
        """Sec representation of the corresponding public key"""
        return self.get_public_key().sec()

    def xonly(self):
        """X-only representation of the corresponding public key"""
        return self.get_public_key().xonly()

    @classmethod
    def from_wif(cls, s):
        """Import private key from Wallet Import Format string."""
        b = base58.decode_check(s)
        secret = b[1:33]
        compressed = False
        if len(b) not in [33,34]:
            raise ValueError("Wrong WIF length")
        if len(b) == 34:
            if b[-1] == 0x01:
                compressed = True
            else:
                raise ValueError("Wrong WIF compressed flag")
        return cls(secret, compressed)

    # to unify API
    def to_base58(self, network=NETWORKS["main"]):
        return self.wif(network)

    @classmethod
    def from_base58(cls, s):
        return cls.from_wif(s)

    def get_public_key(self):
        return PublicKey(secp256k1.ec_pubkey_create(self._secret), self.compressed)

    def sign(self, msg_hash):
        return Signature(secp256k1.ecdsa_sign(msg_hash, self._secret))

    def schnorr_sign(self, msg_hash, tweak=None):
        # TODO: add tweak processing here
        return SchnorrSignature(secp256k1.schnorrsig_sign(msg_hash, self._secret))

    def serialize(self):
        # return a copy of the secret
        return self._secret[:]

    @classmethod
    def parse(cls, b):
        # just to unify the API (don't forget to copy)
        return cls(b)

    @classmethod
    def read_from(cls, stream):
        # just to unify the API
        return cls(stream.read(32))

class Signature:
    def __init__(self, sig):
        self._sig = sig[:1]+sig[1:] # ugly copy

    def serialize(self):
        return secp256k1.ecdsa_signature_serialize_der(self._sig)

    @classmethod
    def parse(cls, der):
        return cls(secp256k1.ecdsa_signature_parse_der(der))

class SchnorrSignature:
    def __init__(self, sig):
        self._sig = sig[:1]+sig[1:]

    def serialize(self):
        return secp256k1.schnorrsig_serialize(self._sig)

    @classmethod
    def parse(cls, data):
        return cls(secp256k1.schnorrsig_parse(data))

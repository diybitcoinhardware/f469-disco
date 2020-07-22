import secp256k1
from . import base58
from .networks import NETWORKS
from binascii import hexlify


class PublicKey:
    def __init__(self, point: bytes, compressed: bool = True):
        self._point = point[:]
        self.compressed = compressed

    @classmethod
    def parse(cls, sec: bytes) -> cls:
        point = secp256k1.ec_pubkey_parse(sec)
        compressed = (sec[0] != 0x04)
        return cls(point, compressed)

    def sec(self) -> bytes:
        """Sec representation of the key"""
        flag = (secp256k1.EC_COMPRESSED
                if self.compressed
                else secp256k1.EC_UNCOMPRESSED)
        return secp256k1.ec_pubkey_serialize(self._point, flag)

    def serialize(self) -> bytes:
        return self.sec()

    def verify(self, sig: Signature, msg_hash: bytes) -> bool:
        return secp256k1.ecdsa_verify(sig._sig, msg_hash, self._point)

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
    def __init__(self, secret: bytes, compressed: bool = True):
        """Creates a private key from 32-byte array"""
        if len(secret) != 32:
            raise ValueError("Secret should be 32-byte array")
        if not secp256k1.ec_seckey_verify(secret):
            raise ValueError("Secret is not valid (larger then N?)")
        self.compressed = compressed
        self._secret = secret[:]

    def wif(self, network=NETWORKS["main"]) -> str:
        """Export private key as Wallet Import Format string.
        Prefix 0x80 is used for mainnet, 0xEF for testnet.
        This class doesn't store this information though.
        """
        prefix = network["wif"]
        b = prefix+self._secret
        if self.compressed:
            b += bytes([0x01])
        return base58.encode_check(b)

    def sec(self) -> bytes:
        """Sec representation of the corresponding public key"""
        return self.get_public_key().sec()

    @classmethod
    def from_wif(cls, s: str) -> cls:
        """Import private key from Wallet Import Format string."""
        b = base58.decode_check(s)
        secret = b[1:33]
        compressed = False
        if len(b) not in [33, 34]:
            raise ValueError("Wrong WIF length")
        if len(b) == 34:
            if b[-1] == 0x01:
                compressed = True
            else:
                raise ValueError("Wrong WIF compressed flag")
        return cls(secret, compressed)

    # to unify API
    def to_base58(self, network=NETWORKS["main"]) -> str:
        return self.wif(network)

    @classmethod
    def from_base58(cls, s: str) -> cls:
        return cls.from_wif(s)

    def get_public_key(self) -> PublicKey:
        pub = secp256k1.ec_pubkey_create(self._secret)
        return PublicKey(pub, self.compressed)

    def sign(self, msg_hash: bytes) -> Signature:
        return Signature(secp256k1.ecdsa_sign(msg_hash, self._secret))

    def serialize(self) -> bytes:
        # return a copy of the secret
        return self._secret[:]

    @classmethod
    def parse(cls, b: bytes) -> cls:
        # just to unify the API (don't forget to copy)
        return cls(b)

    @classmethod
    def read_from(cls, stream) -> cls:
        # just to unify the API
        return cls(stream.read(32))


class Signature:
    def __init__(self, sig: bytes):
        self._sig = sig[:]

    def serialize(self) -> bytes:
        return secp256k1.ecdsa_signature_serialize_der(self._sig)

    @classmethod
    def parse(cls, der: bytes) -> Signature:
        return cls(secp256k1.ecdsa_signature_parse_der(der))

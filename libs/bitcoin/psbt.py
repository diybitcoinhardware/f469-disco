# ref: https://github.com/bitcoin-core/HWI/blob/master/hwilib/serializations.py

from .transaction import Transaction, _parse
from . import compact
from . import bip32

def ser_string(s):
    return compact.to_bytes(len(s))+s

def read_string(stream):
    l = compact.read_from(stream)
    s = stream.read(l)
    if len(s)!=l:
        raise ValueError("Failed to read %d bytes" % l)
    return s

class PSBT:
    def __init__(self, tx=None):
        if tx is not None:
            self.tx = tx
        else:
            self.tx = Transaction()
        self.inputs = []
        self.outputs = []
        self.unknown = {}
        self.xpubs = {}

    def serialize(self):
        # magic bytes
        r = b"psbt\xff"
        # unsigned tx flag
        r += b"\x01\x00"
        # write serialized tx
        tx = self.tx.serialize()
        r += ser_string(tx)
        # xpubs
        for xpub in self.xpubs:
            r += ser_string(b'\x01'+xpub.serialize())
            r += ser_string(self.xpubs[xpub].serialize())
        # unknown
        for key in self.unknown:
            r += ser_string(key)
            r += ser_string(self.unknown[key])
        # separator
        r += b"\x00"
        # inputs
        for inp in self.inputs:
            r += inp.serialize()
        # outputs
        for out in self.outputs:
            r += out.serialize()
        return r

    @classmethod
    def parse(cls, b):
        return _parse(cls, b)

    @classmethod
    def read_from(cls, stream):
        tx = None
        unknown = {}
        xpubs = {}
        # check magic
        if(stream.read(5)!=b'psbt\xff'):
            raise ValueError("Invalid PSBT")
        while True:
            key = read_string(stream)
            # separator
            if len(key) == 0:
                break
            value = read_string(stream)
            # tx
            if key == b'\x00':
                if tx is None:
                    tx = Transaction.parse(value)
                else:
                    raise ValueError("Failed to parse PSBT - duplicated transaction field")
            else:
                if key in unknown:
                    raise ValueError("Duplicated key")
                unknown[key] = value
        
        psbt = cls(tx)
        # now we can go through all the key-values and parse them
        for k in unknown:
            # xpub field
            if k[0] == 0x01:
                xpub = bip32.HDKey.parse(k[1:])
                xpubs[xpub] = DerivationPath.parse(unknown.pop(k))
        psbt.unknown = unknown
        psbt.xpubs = xpubs
        # input scopes
        for i in range(len(tx.vin)):
            psbt.inputs.append(InputScope.read_from(stream))
        # output scopes
        for i in range(len(tx.vout)):
            psbt.outputs.append(OutputScope.read_from(stream))
        return psbt

class DerivationPath:
    def __init__(self, fingerprint, derivation):
        self.fingerprint = fingerprint
        self.derivation = derivation

    def serialize(self):
        r = b''
        r += self.fingerprint
        for idx in self.derivation:
            r += idx.to_bytes(4, 'big')
        return r

    @classmethod
    def parse(cls, b):
        return _parse(cls, b)

    @classmethod
    def read_from(cls, stream):
        fingerprint = stream.read(4)
        derivation = []
        while True:
            r = stream.read(4)
            if len(r) == 0:
                break
            if len(r) < 4:
                raise ValueError("Invalid length")
            derivation.append(int.from_bytes(r, 'big'))
        return cls(fingerprint, derivation)

class PSBTScope:
    def __init__(self, unknown={}):
        self.unknown = unknown

    def serialize(self):
        # unknown
        r = b''
        for key in self.unknown:
            r += ser_string(key)
            r += ser_string(self.unknown[key])
        # separator
        r += b'\x00'
        return r

    @classmethod
    def parse(cls, b):
        return _parse(cls, b)

    @classmethod
    def read_from(cls, stream):
        unknown = {}
        while True:
            key = read_string(stream)
            # separator
            if len(key) == 0:
                break
            value = read_string(stream)
            if key in unknown:
                raise ValueError("Duplicated key")
            unknown[key] = value
        # now we can go through all the key-values and parse them
        return cls(unknown)

class InputScope(PSBTScope):
    def __init__(self, unknown={}):
        self.unknown = unknown
        self.parse_unknowns()

    def parse_unknowns(self):
        pass

class OutputScope(PSBTScope):
    def __init__(self, unknown={}):
        self.unknown = unknown
        self.parse_unknowns()

    def parse_unknowns(self):
        pass
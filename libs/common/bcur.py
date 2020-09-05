from bitcoin.bech32 import *
from io import BytesIO
import hashlib

def bc32encode(data: bytes)->str:
    """
    bc32 encoding 
    see https://github.com/BlockchainCommons/Research/blob/master/papers/bcr-2020-004-bc32.md
    """
    dd = convertbits(data, 8, 5)
    polymod = bech32_polymod([0] + dd + [0, 0, 0, 0, 0, 0]) ^ 0x3fffffff
    chk = [(polymod >> 5 * (5 - i)) & 31 for i in range(6)]
    return ''.join([CHARSET[d] for d in dd+chk])


def bc32decode(bc32: str)->bytes:
    """
    bc32 decoding 
    see https://github.com/BlockchainCommons/Research/blob/master/papers/bcr-2020-004-bc32.md
    """
    if (bc32.lower() != bc32 and bc32.upper() != bc32):
        return None
    bc32 = bc32.lower()
    if not all([x in CHARSET for x in bc32]):
        return None
    res = [CHARSET.find(c) for c in bc32.lower()]
    if bech32_polymod([0] + res) != 0x3fffffff:
        return None
    return bytes(convertbits(res[:-6], 5, 8, False))


def cbor_encode(data):
    l = len(data)
    if l<=23:
        prefix = bytes([0x40+l])
    elif l<=255:
        prefix = bytes([0x58, l])
    elif l<=65535:
        prefix = b'\x59'+l.to_bytes(2, 'big')
    else:
        prefix = b'\x60'+l.to_bytes(4, 'big')
    return prefix+data

def cbor_decode(data):
    s = BytesIO(data)
    b = s.read(1)[0]
    if b >= 0x40 and b < 0x58:
        l = b-0x40
        return s.read(l)
    if b == 0x58:
        l = s.read(1)[0]
        return s.read(l)
    if b == 0x59:
        l = int.from_bytes(s.read(2),'big')
        return s.read(l)
    if b == 0x60:
        l = int.from_bytes(s.read(4),'big')
        return s.read(l)
    return None

def bcur_encode(data):
    """Returns bcur encoded string and hash digest"""
    cbor = cbor_encode(data)
    enc = bc32encode(cbor)
    h = hashlib.sha256(cbor).digest()
    enc_hash = bc32encode(h)
    return enc, enc_hash

def bcur_decode(data, checksum=None):
    """Returns decoded data, verifies hash digest if provided"""
    cbor = bc32decode(data)
    if checksum is not None:
        h = bc32decode(checksum)
        assert h == hashlib.sha256(cbor).digest()
    return cbor_decode(cbor)

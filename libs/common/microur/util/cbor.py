CBOR_MASK = 0xe0
CBOR_LEN_MASK = 0x1c
CBOR_ARRAY = (1<<7)
CBOR_BYTES = (1<<6)

def read_len(stream, v=None):
    if v is None:
        v = stream.read(1)
        assert len(v) == 1
        v = v[0]
    else:
        assert v >= 0
    if v < 0x18:
        return v
    assert v <= 0x1b # not uint otherwise
    l = 1 << (v-0x18)
    b = stream.read(l)
    assert len(b) == l
    return int.from_bytes(b, 'big')

def read_uint(stream):
    return read_len(stream)

def read_bytes_len(stream):
    v = stream.read(1)
    assert len(v) == 1
    assert v[0] > CBOR_BYTES
    v = v[0] - CBOR_BYTES
    return read_len(stream, v)

def read_bytes(stream):
    l = read_bytes_len(stream)
    out = stream.read(l)
    assert len(out) == l
    return out

def encode_uint(v, extra=0):
    # assert (extra & 0x1C) == 0
    if v < 0:
        raise ValueError("Value must be positive")
    if v < 0x18:
        return bytes([v + extra])
    order = 0
    # TODO: can be done with math.ceil(math.log2(v)/8)-1
    while v >> (8 * (2 ** order)):
        order += 1
    if order > 3:
        raise ValueError("Integer %d is too large" % v)
    return bytes([0x18 + order + extra]) + v.to_bytes(2 ** order, "big")

def write_uint(v, stream, extra=0):
    return stream.write(encode_uint(v, extra))

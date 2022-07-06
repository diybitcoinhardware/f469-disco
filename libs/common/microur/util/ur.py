from . import bytewords, cbor
from .fountain import choose_fragments
from io import BytesIO

# ur:crypto-psbt/99999-99999/ + some extra
MAX_HRP_LEN = 30

def decode_hrp(stream):
    hrp = stream.read(30).decode().lower()
    assert hrp[:3] == "ur:"
    arr = hrp.split("/")
    stream.seek(-len(arr[-1]), 1)
    assert len(arr) > 1
    ur_type = arr[0].split(":")[1]
    if len(arr) == 2: # simple 1-1 part
        return ur_type, 1, 1
    assert arr[1].count("-") == 1
    seq_num, seq_len = [int(v) for v in arr[1].split("-")]
    return ur_type, seq_num, seq_len

def _read_header(b):
    assert b.read(1) == b"\x85"
    seq_num = cbor.read_uint(b)
    seq_len = cbor.read_uint(b)
    msg_len = cbor.read_uint(b)
    checksum = cbor.read_uint(b)
    payload_len = cbor.read_bytes_len(b)
    return seq_num, seq_len, msg_len, checksum, payload_len

def write_header(seq_num, seq_len, msg_len, checksum, payload_len, out):
    written = out.write(b"\x85")
    written += cbor.write_uint(seq_num, out)
    written += cbor.write_uint(seq_len, out)
    written += cbor.write_uint(msg_len, out)
    written += cbor.write_uint(checksum, out)
    written += cbor.write_uint(payload_len, out, extra=cbor.CBOR_BYTES)
    return written

def decode_header(stream):
    # max header len = 1 + 5 + 5 + 5 + 5 + 5 = 26
    # x2 because of the encoding
    payload = stream.read(52)
    stream.seek(-len(payload), 1)
    cbor_data = bytewords.decode(payload)
    b = BytesIO(cbor_data)
    seq_num, seq_len, msg_len, checksum, payload_len = _read_header(b)
    parts_set = choose_fragments(seq_num, seq_len, checksum)
    return frozenset(parts_set), seq_num, seq_len, msg_len, checksum, payload_len

def decode_write(stream, out):
    # TODO: optimize so we read in chunks?
    payload = stream.read()
    cbor_data = bytewords.decode(payload)
    b = BytesIO(cbor_data)
    seq_num, seq_len, msg_len, checksum, payload_len = _read_header(b)
    parts_set = choose_fragments(seq_num, seq_len, checksum)
    data = b.read(payload_len)
    assert len(data) == payload_len
    out.write(data)
    return frozenset(parts_set), seq_num, seq_len, msg_len, checksum, payload_len

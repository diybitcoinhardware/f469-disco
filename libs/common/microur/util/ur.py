from . import bytewords, cbor
from .fountain import choose_fragments
from io import BytesIO

# ur:crypto-psbt/99999-99999/ + some extra
MAX_HRP_LEN = 30
# size of the scratch space for header parsing
SCRATCH_SIZE = 52

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

def decode_header(stream, scratch=None):
    # max header len = 1 + 5 + 5 + 5 + 5 + 5 = 26
    # x2 because of the encoding
    scratch = scratch or bytearray(SCRATCH_SIZE)
    assert len(scratch) >= SCRATCH_SIZE
    l = stream.readinto(scratch)
    stream.seek(-l, 1)
    l = bytewords.decodeinto(scratch, scratch, l)
    b = BytesIO(scratch)
    seq_num, seq_len, msg_len, checksum, payload_len = _read_header(b)
    parts_set = choose_fragments(seq_num, seq_len, checksum)
    return parts_set, seq_num, seq_len, msg_len, checksum, payload_len

def decode_write(stream, out, scratch=None):
    scratch = scratch or bytearray(SCRATCH_SIZE)
    assert len(scratch) >= SCRATCH_SIZE
    parts_set, seq_num, seq_len, msg_len, checksum, payload_len = decode_header(stream, scratch)
    # TODO: optimize so we read in chunks?
    header_len = 1 + sum([cbor.len_uint(v) for v in [seq_num, seq_len, msg_len, checksum, payload_len]])
    stream.seek(header_len*2, 1)
    written = 0
    mv = memoryview(scratch)
    while True:
        l = stream.readinto(scratch)
        assert l%2 == 0
        if l == 0:
            break
        l = bytewords.decodeinto(scratch, scratch, l)
        if written + l > payload_len:
            written += out.write(mv[:(payload_len-written)])
            break
        written += out.write(mv[:l])
    return parts_set, seq_num, seq_len, msg_len, checksum, payload_len

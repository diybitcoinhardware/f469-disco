ALPHABET_LEN = 26
LOOKUP_TABLE = [4, 14, 29, 37, -1, -1, 73, -1, 99, -1, -1, 128, -1, -1, -1, 177, -1, -1, 194, 217, -1, 230, -1, -1, 248, -1, -1, 20, -1, -1, -1, -1, -1, -1, -1, -1, 126, 127, -1, 160, -1, -1, -1, -1, 203, 214, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 53, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 253, 1, 11, -1, -1, -1, 72, 80, 88, 98, -1, -1, 137, 149, 155, -1, 168, 179, 186, -1, 210, -1, 231, 234, -1, -1, -1, 0, 16, 28, 40, 52, 69, 74, 95, 100, 107, 124, 138, 145, 159, 162, 175, -1, 181, 193, 211, 222, 228, 237, -1, -1, 254, -1, -1, 25, -1, -1, -1, -1, 86, -1, -1, -1, 130, -1, -1, -1, 176, -1, 188, 204, -1, -1, -1, 243, -1, -1, -1, -1, 18, -1, -1, -1, 70, -1, 87, -1, -1, 123, 141, -1, -1, -1, -1, -1, -1, 202, -1, -1, -1, -1, -1, -1, -1, 5, -1, 23, -1, 49, 63, 84, 92, 101, -1, -1, -1, 144, -1, -1, -1, -1, 185, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 39, -1, -1, -1, -1, -1, -1, 125, -1, -1, -1, -1, -1, -1, -1, -1, 208, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 10, 30, 36, -1, -1, -1, 89, -1, 115, 121, 140, 152, -1, -1, 170, -1, 187, 197, 207, -1, -1, 244, -1, 245, -1, -1, -1, 33, 47, -1, 71, 78, 93, -1, 111, -1, -1, -1, 153, 166, 174, -1, 183, -1, 213, -1, 227, 233, -1, 247, -1, 6, -1, 22, 46, 55, 62, 82, -1, 106, -1, -1, -1, -1, -1, -1, 173, -1, -1, -1, -1, -1, -1, 235, -1, -1, 255, -1, 12, 35, 43, 54, 60, -1, 96, 105, 109, 122, 134, 142, 158, 165, -1, -1, 190, 205, 218, -1, -1, 241, -1, 246, -1, 2, -1, -1, -1, 51, -1, 85, -1, 103, 112, 118, 136, 146, -1, -1, -1, -1, 184, 201, 206, 220, 226, -1, -1, -1, 251, -1, -1, 34, 45, -1, 65, -1, 91, -1, 114, 117, 133, -1, -1, -1, -1, -1, 182, 200, 216, -1, -1, 236, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 42, -1, 59, 75, -1, -1, -1, -1, 132, -1, -1, -1, 178, -1, -1, 195, -1, 223, -1, -1, -1, -1, -1, 9, 15, 24, 38, 57, 61, 76, 97, 104, 113, 120, 131, 151, 156, 167, 172, -1, 191, 196, 215, -1, 232, 239, -1, -1, 250, 7, 13, 31, 41, 56, 58, 77, 90, -1, 110, 119, 135, 150, 157, 163, 169, -1, 192, 199, 209, 221, 224, 240, -1, 249, 252, -1, -1, -1, -1, -1, -1, 83, -1, -1, -1, -1, 139, 147, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 19, 27, 44, -1, 66, 79, -1, -1, -1, -1, -1, 148, -1, -1, -1, -1, -1, 198, -1, -1, 229, -1, -1, -1, -1, 3, -1, 32, -1, -1, 67, -1, -1, -1, -1, -1, -1, -1, -1, 164, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 8, 17, 26, 48, 50, 68, 81, 94, 102, 116, -1, 129, 143, 154, 161, 171, -1, 189, -1, 212, 219, 225, 238, -1, -1, -1, -1, 21, -1, -1, -1, 64, -1, -1, -1, 108, -1, -1, -1, -1, -1, -1, 180, -1, -1, -1, -1, -1, 242, -1, -1, -1]

from io import BytesIO
from binascii import crc32

def stream_pos(stream, scratch=None):
    """
    Returns a tuple: current position and total length of the readable stream.
    Works even with streams that don't have tell() method
    """
    if hasattr(stream, "tell"):
        cur = stream.tell()
        sz = stream.seek(0, 2)
        stream.seek(cur, 0)
        return cur, sz
    else:
        b = scratch or bytearray(32)
        n = stream.readinto(b)
        till_end = n
        while n > 0:
            n = stream.readinto(b)
            till_end += n
        sz = stream.seek(0, 2)
        cur = sz-till_end
        stream.seek(cur, 0)
        return cur, sz

def _minus_aA(b):
    # ord('A') = 65, ord('a') = 97
    return (b-65) if b < 97 else (b-97)

def stream_encode(fin, data_len, fout):
    written = 0
    while data_len > 0:
        b = fin.read(1)
        if not b:
            return written
        idx = LOOKUP_TABLE.index(b[0])
        c1 = idx % ALPHABET_LEN
        c2 = idx // ALPHABET_LEN
        written += fout.write(bytes([c1+65, c2+65]))
        data_len -= 1
    return written

def stream_decode(fin, fout, maxread=0, crc=0):
    """Negative maxread means to read everything except last maxread bytes"""
    if maxread <= 0:
        cur, sz = stream_pos(fin)
        maxread = sz - cur + maxread
    assert maxread % 2 == 0
    maxlen = maxread // 2
    assert maxlen > 0
    buf = bytearray(2)
    written = 0
    l = fin.readinto(buf)
    while l > 0:
        assert l % 2 == 0
        buf[0] = _minus_aA(buf[0])
        buf[1] = _minus_aA(buf[1])
        chunk = bytes([LOOKUP_TABLE[buf[1]*ALPHABET_LEN + buf[0]]])
        crc = crc32(chunk, crc)
        written += fout.write(chunk)
        if maxlen == written:
            return written, crc
        l = fin.readinto(buf)
    raise ValueError("End reached")

def stream_decode_check(fin, fout, maxread=0, crc=0):
    """
    Decodes from bytewords stream to normal bytes stream.
    Will raise an exception if failed.
    Stop after `maxread` bytes (0 to read everything).
    TODO: Checksum is currently ignored.
    """
    # check we don't flip from positive read to negative.
    # maxread between 0 and 8 is invalid anyways as checksum is 8 chars long
    assert maxread <= 0 or maxread > 8
    # read eveyrthing up to the checksum
    written, crc = stream_decode(fin, fout, maxread-8, crc)
    # read checksum but ignore it for now
    assert crc.to_bytes(4,'big') == decode(fin.read(8))
    return written

def decodeinto(bytewords, buf, length=None):
    if length is None:
        length = len(bytewords)
    assert length%2 == 0
    assert len(buf) >= length//2
    for i in range(length//2):
        buf[i] = LOOKUP_TABLE[_minus_aA(bytewords[2*i+1])*ALPHABET_LEN + _minus_aA(bytewords[2*i])]
    return length//2

def decode(bytewords):
    """Decodes bytes or string with bytewords to bytes"""
    if isinstance(bytewords, str):
        bytewords = bytewords.encode()
    out = BytesIO()
    inp = BytesIO(bytewords)
    stream_decode(inp, out)
    return out.getvalue()

def decode_check(bytewords):
    """Decodes bytes or string with bytewords to bytes"""
    if isinstance(bytewords, str):
        bytewords = bytewords.encode()
    out = BytesIO()
    inp = BytesIO(bytewords)
    stream_decode_check(inp, out)
    return out.getvalue()

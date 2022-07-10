from .util.bytewords import stream_pos
from .util import bytewords
from .util import cbor
from .util import ur
from .util.fountain import choose_fragments
import math
from binascii import crc32
from io import BytesIO

class UREncoder:
    CRYPTO_PSBT = "crypto-psbt"

    def __init__(self, ur_type, stream, part_len=100, data_len=None):
        if ur_type.lower() != self.CRYPTO_PSBT:
            raise NotImplementedError()
        self.stream = stream
        self.ur_type = ur_type
        self.part_len = part_len
        # detect data_len if not provided
        self.cur, sz = stream_pos(stream)
        if data_len is None:
            data_len = sz-self.cur
        self.data_len = data_len
        self.hrp = b"UR:"+(ur_type.upper().encode())+b"/"
        self.idx = 0
        self.cbor_prefix = cbor.encode_uint(data_len, cbor.CBOR_BYTES)
        self.msg_len = data_len + len(self.cbor_prefix)
        self.part_len = min(part_len, self.msg_len)
        self.seq_len = math.ceil(self.msg_len/part_len)
        self.payload_len = math.ceil(self.msg_len/self.seq_len)
        self.buf = bytearray(self.payload_len)
        crc = crc32(self.cbor_prefix)
        processed = 0
        while processed+self.payload_len < data_len:
            processed += stream.readinto(self.buf)
            crc = crc32(self.buf, crc)
        self.checksum = crc32(stream.read(data_len-processed), crc)
        # rewind back to start
        stream.seek(self.cur, 0)
        self._singlepart = None
        self._p1 = None
        if self.seq_len == 1:
            self._singlepart = self.get_part(0)
        else:
            self._p1 = BytesIO() # part one is special, it has cbor part
            self._p1.write(self.cbor_prefix)
            self._p1.write(self.stream.read(self.payload_len-len(self.cbor_prefix)))
            self.stream.seek(self.cur, 0)
            self._p1.seek(0, 0)

    def get_part_payload(self, idx, buf=None):
        buf = buf if buf is not None else self.buf
        # zero buffer if last part
        if idx == self.seq_len - 1:
            for i in range(len(buf)):
                buf[i] = 0
        if idx < self.seq_len:
            if idx == 0: # first one needs cbor part
                self._p1.readinto(buf)
                self._p1.seek(0,0)
                return buf
            self.stream.seek(self.cur+self.payload_len*idx-len(self.cbor_prefix))
            written = self.stream.readinto(buf)
        else:
            part_set = choose_fragments(idx+1, self.seq_len, self.checksum)
            barr = bytearray(self.payload_len)
            for i, s in enumerate(part_set):
                if i == 0:
                    self.get_part_payload(s, buf)
                else:
                    self.get_part_payload(s, barr)
                    for j in range(self.payload_len):
                        buf[j] ^= barr[j]
        return buf

    def write_header(self, idx, out, crc=0):
        b = BytesIO()
        written = ur.write_header(idx+1, self.seq_len, self.msg_len, self.checksum, self.payload_len, b)
        b.seek(0,0)
        return bytewords.stream_encode(b, written, out), crc32(b.getvalue())

    def get_part(self, idx):
        if self.seq_len == 1:
            if self._singlepart is None:
                b = BytesIO()
                b.write(self.hrp)
                bytewords.stream_encode(BytesIO(self.cbor_prefix), len(self.cbor_prefix), b)
                bytewords.stream_encode(self.stream, self.data_len, b)
                self.stream.seek(self.cur, 0)
                bytewords.stream_encode(BytesIO(self.checksum.to_bytes(4,'big')), 4, b)
                self._singlepart = b.getvalue().decode()
            return self._singlepart
        b = BytesIO()
        b.write(self.hrp)
        b.write(("%d-%d/" % (idx+1, self.seq_len)).encode())
        _, crc = self.write_header(idx, b)
        payload = self.get_part_payload(idx)
        bytewords.stream_encode(BytesIO(payload), len(self.buf), b)
        crc = crc32(payload, crc)
        bytewords.stream_encode(BytesIO(crc.to_bytes(4,'big')), 4, b)
        return b.getvalue().decode()

    def next_part(self):
        p = self.get_part(self.idx)
        if self.seq_len > 1:
            self.idx += 1
        return p

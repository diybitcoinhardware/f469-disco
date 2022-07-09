from .util import bytewords, cbor
from .util.fountain import part_sets_is_complete, part_sets_add, reduce_parts
from .util.ur import decode_header, decode_hrp, decode_write, SCRATCH_SIZE
from io import BytesIO
import os

class URDecoderBase:
    """
    Base class for URDecoders.
    Agnostic to storage implementation - the simplest one is a dict with BytesIO (URDecoder)
    but not as RAM-efficient as FileURDecoder that uses a tempdir for storage.
    Feel free to inherit according to your needs.
    """
    def __init__(self, scratch=None):
        self.scratch = scratch or bytearray(SCRATCH_SIZE)
        assert len(self.scratch) >= SCRATCH_SIZE
        self.part_sets = set()
        self.part_seq = []
        self.seq_len = None
        self.msg_len = None
        self.checksum = None
        self.payload_len = None
        self.ur_type = None
        self._is_complete = False
        self._b1 = None
        self._b2 = None

    def exists(self, part_set):
        """
        Override this function in your decoder.
        Check if stream with part exists.
        """
        raise NotImplementedError()

    def open(self, part_set, mode="r"):
        """
        Override this function in your decoder.
        Opens a stream for reading, writing or appending.
        `mode` can be "r", "w" or "a".
        Should be used in style `with decoder.open() as f:`
        """
        raise NotImplementedError()

    def read_part(self, stream) -> bool:
        ur_type, seq_num_hrp, seq_len_hrp = decode_hrp(stream)
        # check we get the same stuff, assign if None
        self.ur_type = self.ur_type or ur_type
        assert self.ur_type == ur_type
        if seq_len_hrp == 1: # single part thing
            self.seq_len = 1
            data = bytewords.decode_check(stream.read())
            self.payload_len = len(data)
            self.msg_len = len(data)
            with self.open(frozenset({0}), "w") as f:
                f.write(data)
            with self.open(frozenset({1}), "w") as f:
                f.write(data)
            self._is_complete = True
        else:
            newset, seq_num, seq_len, msg_len, checksum, payload_len = decode_header(stream, scratch=self.scratch)
            assert seq_num == seq_num_hrp
            assert seq_len == seq_len_hrp
            self.seq_len = self.seq_len or seq_len
            assert self.seq_len == seq_len
            self.msg_len = self.msg_len or msg_len
            assert self.msg_len == msg_len
            self.checksum = self.checksum or checksum
            assert self.checksum == checksum
            self.payload_len = self.payload_len or payload_len
            assert self.payload_len == payload_len
            # write part to storage
            self.decode_write(newset, stream)
            # update received sequence so we can go through parts in the same order
            # otherwise there is no guarantee that it will work
            self.part_seq.append(newset)
            part_sets_add(self.part_sets, newset)
            self._is_complete = part_sets_is_complete(self.part_sets, self.seq_len)
        return self.is_complete

    def process_part(self, part) -> bool:
        if self.is_complete:
            return True
        # part can be a stream, bytes or string
        if isinstance(part, str):
            part = part.encode()
        stream = BytesIO(part)
        return self.read_part(stream)

    def _reduce(self, p1, p2):
        newp = p1.difference(p2)
        b1 = self._b1 or bytearray(self.payload_len)
        b2 = self._b2 or bytearray(self.payload_len)
        with self.open(p1) as in1:
            assert in1.readinto(b1) == self.payload_len
        with self.open(p2) as in2:
            assert in2.readinto(b2) == self.payload_len
        # xor
        for i in range(self.payload_len):
            b1[i] ^= b2[i]
        with self.open(newp, "w") as out:
            out.write(b1)

    @property
    def is_complete(self):
        """Returns True if enough parts were received"""
        return self._is_complete

    def _combine(self):
        if not self.is_complete:
            return 0
        part_sets = set()
        for newset in self.part_seq:
            part_sets_add(part_sets, newset, reduce_callback=self._reduce)
        assert part_sets_is_complete(part_sets, self.seq_len)
        b = bytearray(self.payload_len)
        with self.open(frozenset({self.seq_len}), "w") as out:
            written = 0
            for i in range(self.seq_len):
                with self.open(frozenset({i})) as stream:
                    stream.readinto(b)
                if written+self.payload_len <= self.msg_len:
                    written += out.write(b)
                else:
                    written += out.write(b[:self.msg_len-written-self.payload_len])
        return written

    @property
    def is_combined(self):
        return self.exists(frozenset({self.seq_len}))

    @property
    def progress(self):
        if self.is_complete:
            return 1
        if self.seq_len is None:
            return 0
        return round(
            min(0.99,
                max(
                    sum([0.8 if len(p) == 1 else 0.1 for p in self.part_sets])/self.seq_len,
                    len(self.part_seq)/self.seq_len/1.3
                )
            ), 2)

    def exists(self, part_set) -> bool:
        # check if element is in storage
        raise NotImplementedError()

    def result(self):
        if not self.is_complete:
            raise RuntimeError("Decoding is not complete")
        if not self.is_combined:
            self._combine()
        return self.open(frozenset({self.seq_len}))

    def decode_write(self, part_set, in_stream) -> int:
        """Optionally overwrite this as well"""
        if self.exists(part_set):
            return 0
        with self.open(part_set, "w") as out:
            *otherstuff, payload_len = decode_write(in_stream, out, self.scratch)
        return payload_len


class URDecoder(URDecoderBase):
    class PartStreamer:
        def __init__(self, b, mode="r"):
            # if append - move to end, otherwise - start
            b.seek(0, 2 if "a" in mode else 0)
            self.b = b

        def __enter__(self):
            return self.b

        def __exit__(self, *args):
            self.b.seek(0, 0)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.streams = {}

    def exists(self, part_set):
        """Checks if stream exists"""
        return part_set in self.streams

    def open(self, part_set, mode="r"):
        """
        Opens a stream for reading, writing or appending.
        `mode` can be "r", "w" or "a".
        Should be used in style `with decoder.open() as f:`
        """
        # create new stream if it doesn't exist or if write mode
        if (part_set not in self.streams) or ("w" in mode):
            self.streams[part_set] = BytesIO()
        return type(self).PartStreamer(self.streams[part_set], mode)

class FileURDecoder(URDecoderBase):
    class FilePart:
        def __init__(self, path, mode="r"):
            self.path = path
            if "b" not in mode: # r -> rb, w ->wb etc
                mode += "b"
            self.mode = mode
            self.f = None

        def __enter__(self):
            if self.f:
                raise RuntimeError()
            self.f = open(self.path, self.mode)
            return self.f

        def __exit__(self, *args):
            if self.f is None:
                return
            self.f.close()
            self.f = None

    def __init__(self, tmpdir, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if tmpdir.endswith("/"):
            tmpdir = tmpdir[:-1]
        self.tmpdir = tmpdir
        # cleanup the dir
        if hasattr(os, "listdir"):
            files = os.listdir(tmpdir)
        else:
            files = [f for f, *_ in os.ilistdir(tmpdir)]
        for f in files:
            if f.endswith(".tmp"):
                os.remove(self._join(f))

    def _join(self, fname):
        # micropython doesn't have os.path
        if hasattr(os, "path") and hasattr(os.path, "join"):
            return os.path.join(self.tmpdir, fname)
        else:
            return self.tmpdir + "/" + fname

    def _fname(self, part_set):
        fname = "-".join([str(el) for el in sorted(list(part_set))]) + ".tmp"
        return self._join(fname)

    def exists(self, part_set):
        if hasattr(os, "path") and hasattr(os.path, "isfile"):
            return os.path.isfile(self._fname(part_set))
        else:
            # micropython doesn't have os.path so we need to try opening the file
            try:
                with open(self._fname(part_set), "rb") as f:
                    pass
            except:
                return False
            return True

    def open(self, part_set, mode="r"):
        return FileURDecoder.FilePart(self._fname(part_set), mode)

# The MIT License (MIT)

# Copyright (c) 2021 Tom J. Sun
# Copyright (c) 2015 Sokolov Yura
# Copyright (c) 2013 Fritz Grimpen

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
# coding: utf-8

import struct

_str_type = type("")
_bytes_type = type(b"")

from .data import Tagging, Mapping, Undefined


class EncoderError(Exception):
    pass


class Encoder(object):
    def __init__(self, output):
        self.output = output

    def encode(self, val):
        if isinstance(val, _bytes_type):
            self.encode_bytestring(val)
        elif isinstance(val, _str_type):
            self.encode_textstring(val)
        elif isinstance(val, float):
            self.encode_float(val)
        elif isinstance(val, bool):
            self.encode_boolean(val)
        elif isinstance(val, int):
            self.encode_integer(val)
        elif isinstance(val, list):
            self.encode_list(val)
        elif isinstance(val, dict):
            self.encode_dict(val)
        elif isinstance(val, Tagging):
            self.encode_tagging(val)
        elif val is Undefined:
            self.encode_undefined()
        elif val is None:
            self.encode_null()
        elif isinstance(val, Mapping):
            val = val.map
            self.encode(val)
        else:
            raise EncoderError("val of type {} is not serializable".format(type(val)))

    def encode_list(self, list):
        self._write(_encode_ibyte(4, len(list)))
        for elem in list:
            self.encode(elem)

    def encode_dict(self, dict):
        self._write(_encode_ibyte(5, len(dict)))
        for key, value in dict.items():
            self.encode(key)
            self.encode(value)

    def encode_bytestring(self, bytestring):
        self._write(_encode_ibyte(2, len(bytestring)))
        self._write(bytestring)

    def encode_textstring(self, textstring):
        string_ = textstring.encode("utf-8")
        self._write(_encode_ibyte(3, len(string_)))
        self._write(string_)

    def encode_float(self, float):
        self._write(b"\xfb")
        self._write(struct.pack(">d", float))

    def encode_integer(self, integer):
        if integer < 0:
            integer = -integer - 1
            try:
                self._write(_encode_ibyte(1, integer))
            except TypeError:
                raise EncoderError(
                    "Encoding integers lower than -18446744073709551616 is not supported"
                )
        else:
            try:
                self._write(_encode_ibyte(0, integer))
            except TypeError:
                raise EncoderError(
                    "Encoding integers larger than 18446744073709551615 is not supported"
                )

    def encode_tagging(self, tagging):
        try:
            self._write(_encode_ibyte(6, tagging.tag))
        except TypeError:
            raise EncoderError(
                "Encoding tag larger than 18446744073709551615 is not supported"
            )
        self.encode(tagging.obj)

    def encode_boolean(self, boolean):
        if boolean is True:
            self._write(_encode_ibyte(7, 21))
        elif boolean is False:
            self._write(_encode_ibyte(7, 20))

    def encode_null(self):
        self._write(_encode_ibyte(7, 22))

    def encode_undefined(self):
        self._write(b"\xf7")

    def _write(self, val):
        self.output.write(val)


def _encode_ibyte(major, length):
    if length < 24:
        return struct.pack(">B", (major << 5) | length)
    elif length < 256:
        return struct.pack(">BB", (major << 5) | 24, length)
    elif length < 65536:
        return struct.pack(">BH", (major << 5) | 25, length)
    elif length < 4294967296:
        return struct.pack(">BI", (major << 5) | 26, length)
    elif length < 18446744073709551616:
        return struct.pack(">BQ", (major << 5) | 27, length)
    else:
        return None


__all__ = ["Encoder", "EncoderError"]

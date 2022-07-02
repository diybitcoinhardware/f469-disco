# The MIT License (MIT)

# Copyright (c) 2021 Tom J. Sun

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

import io
from urtypes.cbor import decoder, encoder, DataItem


class RegistryType:
    def __init__(self, type, tag):
        self.type = type
        self.tag = tag


class RegistryItem:
    @classmethod
    def registry_type(cls):
        raise NotImplementedError()

    @classmethod
    def mapping(cls, item):
        if isinstance(item, DataItem):
            registry_type = cls.registry_type()
            if (registry_type is None and item.tag is None) or (
                registry_type is not None and registry_type.tag == item.tag
            ):
                return item.map
        return item

    @classmethod
    def from_data_item(cls, item):
        raise NotImplementedError()

    def to_data_item(self):
        raise NotImplementedError()

    @classmethod
    def from_cbor(cls, cbor_payload):
        cbor_decoder = decoder.Decoder(io.BytesIO(cbor_payload))
        return cls.from_data_item(cbor_decoder.decode())

    def to_cbor(self):
        cbor_encoder = encoder.Encoder(io.BytesIO())
        cbor_encoder.encode(self.to_data_item())
        v = cbor_encoder.output.getvalue()
        cbor_encoder.output.close()
        return bytearray(v)

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

from urtypes import RegistryItem
from urtypes.cbor import DataItem
from .hd_key import HDKey, CRYPTO_HDKEY
from .ec_key import ECKey, CRYPTO_ECKEY


class MultiKey(RegistryItem):
    def __init__(self, threshold, ec_keys, hd_keys):
        super().__init__()
        self.threshold = threshold
        self.ec_keys = ec_keys
        self.hd_keys = hd_keys

    def __eq__(self, o):
        return (
            self.threshold == o.threshold
            and self.ec_keys == o.ec_keys
            and self.hd_keys == o.hd_keys
        )

    @classmethod
    def registry_type(cls):
        return None

    def to_data_item(self):
        map = {}
        map[1] = self.threshold
        combined_keys = self.ec_keys[:] + self.hd_keys[:]
        keys = []
        for key in combined_keys:
            keys.append(DataItem(key.registry_type().tag, key.to_data_item()))
        map[2] = keys
        return map

    @classmethod
    def from_data_item(cls, item):
        map = item.map
        threshold = map[1]
        keys = map[2]
        ec_keys = []
        hd_keys = []
        for key in keys:
            if key.tag == CRYPTO_HDKEY.tag:
                hd_keys.append(HDKey.from_data_item(key))
            elif key.tag == CRYPTO_ECKEY.tag:
                ec_keys.append(ECKey.from_data_item(key))
        return cls(threshold, ec_keys, hd_keys)

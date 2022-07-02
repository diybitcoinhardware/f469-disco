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

from urtypes import RegistryType, RegistryItem

CRYPTO_BIP39 = RegistryType("crypto-bip39", 301)


class BIP39(RegistryItem):
    def __init__(self, words, lang):
        super().__init__()
        self.words = words
        self.lang = lang

    def __eq__(self, o):
        return self.words == o.words and self.lang == o.lang

    @classmethod
    def registry_type(cls):
        return CRYPTO_BIP39

    def to_data_item(self):
        map = {1: self.words}
        if self.lang is not None:
            map[2] = self.lang
        return map

    @classmethod
    def from_data_item(cls, item):
        map = cls.mapping(item)
        words = map[1]
        lang = map[2] if 2 in map else None
        return cls(words, lang)

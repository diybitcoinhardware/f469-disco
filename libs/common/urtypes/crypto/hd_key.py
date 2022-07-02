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

import binascii
import hashlib
from urtypes import RegistryType, RegistryItem
from urtypes.cbor import DataItem
from .coin_info import CoinInfo
from .keypath import Keypath

CRYPTO_HDKEY = RegistryType("crypto-hdkey", 303)


class HDKey(RegistryItem):
    def __init__(self, props):
        super().__init__()
        self.master = None
        self.key = None
        self.chain_code = None
        self.private_key = None
        self.use_info = None
        self.origin = None
        self.children = None
        self.parent_fingerprint = None
        self.name = None
        self.note = None
        if "master" in props and props["master"]:
            self.setup_master_key(props)
        else:
            self.setup_derive_key(props)

    def __eq__(self, o):
        return (
            self.master == o.master
            and self.key == o.key
            and self.chain_code == o.chain_code
            and self.private_key == o.private_key
            and self.use_info == o.use_info
            and self.origin == o.origin
            and self.children == o.children
            and self.parent_fingerprint == o.parent_fingerprint
            and self.name == o.name
            and self.note == o.note
        )

    @classmethod
    def registry_type(cls):
        return CRYPTO_HDKEY

    def setup_master_key(self, props):
        self.master = True
        self.key = props["key"] if "key" in props else None
        self.chain_code = props["chain_code"] if "chain_code" in props else None

    def setup_derive_key(self, props):
        self.master = False
        self.key = props["key"] if "key" in props else None
        self.chain_code = props["chain_code"] if "chain_code" in props else None
        self.private_key = props["private_key"] if "private_key" in props else None
        self.use_info = props["use_info"] if "use_info" in props else None
        self.origin = props["origin"] if "origin" in props else None
        self.children = props["children"] if "children" in props else None
        self.parent_fingerprint = (
            props["parent_fingerprint"] if "parent_fingerprint" in props else None
        )
        self.name = props["name"] if "name" in props else None
        self.note = props["note"] if "note" in props else None

    def bip32_key(self, include_derivation_path=False):
        parent_fingerprint = (0).to_bytes(4, "big")
        source_is_parent = False
        chain_code = (
            self.chain_code if self.chain_code is not None else (0).to_bytes(32, "big")
        )
        key = self.key
        if len(key) == 32:
            key = 0x00 + key
        depth = 0
        index = 0
        if self.master:
            version = binascii.unhexlify(
                "0488ADE4"
                if not self.use_info or self.use_info.network == 0
                else "04358394"
            )
        else:
            if self.private_key:
                version = binascii.unhexlify(
                    "0488ADE4"
                    if not self.use_info or self.use_info.network == 0
                    else "04358394"
                )
            else:
                version = binascii.unhexlify(
                    "0488B21E"
                    if not self.use_info or self.use_info.network == 0
                    else "043587CF"
                )
            if self.parent_fingerprint is not None:
                parent_fingerprint = self.parent_fingerprint
            depth = (
                self.origin.depth
                if self.origin.depth is not None
                else len(self.origin.components)
            )
            paths = self.origin.components
            if len(paths) > 0:
                last_path = paths[len(paths) - 1]
                index = last_path.index
                if last_path.hardened:
                    index += 0x80000000
                if (
                    self.parent_fingerprint is None
                    and self.origin.source_fingerprint is not None
                    and len(paths) == 1
                ):
                    parent_fingerprint = self.origin.source_fingerprint
                    source_is_parent = True
        depth = depth.to_bytes(1, "big")
        index = index.to_bytes(4, "big")
        key = encode_check(
            version + depth + parent_fingerprint + index + chain_code + key
        )
        if include_derivation_path:
            derivation = ""
            if (
                self.origin
                and self.origin.path()
                and self.origin.source_fingerprint
                and not source_is_parent
            ):
                derivation = "[%s/%s]" % (
                    binascii.hexlify(self.origin.source_fingerprint).decode("utf-8"),
                    self.origin.path(),
                )

            child_derivation = ""
            if self.children and self.children.path():
                child_derivation = "/" + self.children.path()

            return "%s%s%s" % (derivation, key, child_derivation)
        return key

    def descriptor_key(self):
        return self.bip32_key(True)

    def to_data_item(self):
        map = {}
        if self.master:
            map[1] = True
            map[3] = self.key
            map[4] = self.chain_code
        else:
            if self.private_key is not None:
                map[2] = self.private_key
            map[3] = self.key
            if self.chain_code is not None:
                map[4] = self.chain_code
            if self.use_info is not None:
                map[5] = DataItem(
                    self.use_info.registry_type().tag, self.use_info.to_data_item()
                )
            if self.origin is not None:
                map[6] = DataItem(
                    self.origin.registry_type().tag, self.origin.to_data_item()
                )
            if self.children is not None:
                map[7] = DataItem(
                    self.children.registry_type().tag, self.children.to_data_item()
                )
            if self.parent_fingerprint is not None:
                map[8] = int.from_bytes(self.parent_fingerprint, "big")
            if self.name is not None:
                map[9] = self.name
            if self.note is not None:
                map[10] = self.note
        return map

    @classmethod
    def from_data_item(cls, item):
        map = cls.mapping(item)
        master = 1 in map and map[1]
        private_key = map[2] if 2 in map else None
        key = map[3] if 3 in map else None
        chain_code = map[4] if 4 in map else None
        use_info = CoinInfo.from_data_item(map[5]) if 5 in map else None
        origin = Keypath.from_data_item(map[6]) if 6 in map else None
        children = Keypath.from_data_item(map[7]) if 7 in map else None
        parent_fingerprint = map[8].to_bytes(4, "big") if 8 in map else None
        name = map[9] if 9 in map else None
        note = map[10] if 10 in map else None
        return cls(
            {
                "master": master,
                "private_key": private_key,
                "key": key,
                "chain_code": chain_code,
                "use_info": use_info,
                "origin": origin,
                "children": children,
                "parent_fingerprint": parent_fingerprint,
                "name": name,
                "note": note,
            }
        )


B58_DIGITS = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def double_sha256(msg):
    """sha256(sha256(msg)) -> bytes"""
    return hashlib.sha256(hashlib.sha256(msg).digest()).digest()


def encode(b):
    """Encode bytes to a base58-encoded string"""

    # Convert big-endian bytes to integer
    n = int("0x0" + binascii.hexlify(b).decode("utf8"), 16)

    # Divide that integer into bas58
    res = []
    while n > 0:
        n, r = divmod(n, 58)
        res.append(B58_DIGITS[r])
    res = "".join(res[::-1])

    pad = 0
    for c in b:
        if c == 0:
            pad += 1
        else:
            break
    return B58_DIGITS[0] * pad + res


def encode_check(b):
    """Encode bytes to a base58-encoded string with a checksum"""
    return encode(b + double_sha256(b)[0:4])

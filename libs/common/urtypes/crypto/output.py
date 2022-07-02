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
from urtypes import RegistryType, RegistryItem
from urtypes.cbor import DataItem
from .multi_key import MultiKey
from .hd_key import HDKey, CRYPTO_HDKEY
from .ec_key import ECKey


class ScriptExpression:
    def __init__(self, tag, expression):
        self.tag = tag
        self.expression = expression

    def __eq__(self, o):
        return self.tag == o.tag and self.expression == o.expression


SCRIPT_EXPRESSION_TAG_MAP = {
    307: ScriptExpression(307, "addr"),
    400: ScriptExpression(400, "sh"),
    401: ScriptExpression(401, "wsh"),
    402: ScriptExpression(402, "pk"),
    403: ScriptExpression(403, "pkh"),
    404: ScriptExpression(404, "wpkh"),
    405: ScriptExpression(405, "combo"),
    406: ScriptExpression(406, "multi"),
    407: ScriptExpression(407, "sortedmulti"),
    408: ScriptExpression(408, "raw"),
    409: ScriptExpression(409, "tr"),
    410: ScriptExpression(410, "cosigner"),
}

CRYPTO_OUTPUT = RegistryType("crypto-output", 308)


class Output(RegistryItem):
    def __init__(self, script_expressions, crypto_key):
        super().__init__()
        self.script_expressions = script_expressions
        self.crypto_key = crypto_key

    def __eq__(self, o):
        return (
            self.script_expressions == o.script_expressions
            and self.crypto_key == o.crypto_key
        )

    @classmethod
    def registry_type(cls):
        return CRYPTO_OUTPUT

    def descriptor(self, include_checksum=True):
        descriptor = io.StringIO()

        for script_expression in self.script_expressions:
            descriptor.write(script_expression.expression + "(")

        if isinstance(self.crypto_key, MultiKey):
            descriptor.write(str(self.crypto_key.threshold) + ",")

        keys = (
            self.crypto_key.ec_keys[:] + self.crypto_key.hd_keys[:]
            if isinstance(self.crypto_key, MultiKey)
            else [self.crypto_key]
        )
        descriptor.write(",".join([key.descriptor_key() for key in keys]))

        for _ in self.script_expressions:
            descriptor.write(")")

        d = descriptor.getvalue()
        descriptor.close()

        if include_checksum:
            return d + "#" + descriptor_checksum(d)
        return d

    def hd_key(self):
        if isinstance(self.crypto_key, HDKey):
            return self.crypto_key
        return None

    def ec_key(self):
        if isinstance(self.crypto_key, ECKey):
            return self.crypto_key
        return None

    def multi_key(self):
        if isinstance(self.crypto_key, MultiKey):
            return self.crypto_key
        return None

    def to_data_item(self):
        item = DataItem(None, self.crypto_key.to_data_item())
        if self.crypto_key.registry_type() is not None:
            item.tag = self.crypto_key.registry_type().tag
        i = len(self.script_expressions) - 1
        while i >= 0:
            expression = self.script_expressions[i]
            if item.tag is None:
                item.tag = expression.tag
            else:
                item = DataItem(expression.tag, item)
            i -= 1
        return item

    @classmethod
    def from_data_item(cls, item):
        tmp_item = cls.mapping(item)
        script_expressions = []
        while True:
            tag = tmp_item.tag
            if tag in SCRIPT_EXPRESSION_TAG_MAP:
                script_expressions.append(SCRIPT_EXPRESSION_TAG_MAP[tag])
                if isinstance(tmp_item.map, DataItem):
                    tmp_item = tmp_item.map
                else:
                    break
            else:
                break
        exp_len = len(script_expressions)
        is_multi_key = exp_len > 0 and (
            script_expressions[exp_len - 1].expression == "multi"
            or script_expressions[exp_len - 1].expression == "sortedmulti"
        )
        if is_multi_key:
            return cls(script_expressions, MultiKey.from_data_item(tmp_item))

        if tmp_item.tag == CRYPTO_HDKEY.tag:
            return cls(script_expressions, HDKey.from_data_item(tmp_item))
        else:
            return cls(script_expressions, ECKey.from_data_item(tmp_item))


def polymod(c, val):
    c0 = c >> 35
    c = ((c & 0x7FFFFFFFF) << 5) ^ val
    if c0 & 1:
        c ^= 0xF5DEE51989
    if c0 & 2:
        c ^= 0xA9FDCA3312
    if c0 & 4:
        c ^= 0x1BAB10E32D
    if c0 & 8:
        c ^= 0x3706B1677A
    if c0 & 16:
        c ^= 0x644D626FFD
    return c


INPUT_CHARSET = "0123456789()[],'/*abcdefgh@:$%{}IJKLMNOPQRSTUVWXYZ&+-.;<=>?!^_|~ijklmnopqrstuvwxyzABCDEFGH`#\"\\ "
CHECKSUM_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"


def descriptor_checksum(descriptor):
    c = 1
    cls = 0
    clscount = 0
    for ch in descriptor:
        pos = INPUT_CHARSET.find(ch)
        if pos == -1:
            return ""
        c = polymod(c, pos & 31)
        cls = cls * 3 + (pos >> 5)
        clscount += 1
        if clscount == 3:
            c = polymod(c, cls)
            cls = 0
            clscount = 0
    if clscount > 0:
        c = polymod(c, cls)
    for _ in range(8):
        c = polymod(c, 0)
    c ^= 1
    checksum = ""
    for i in range(8):
        checksum += CHECKSUM_CHARSET[(c >> (5 * (7 - i))) & 31]
    return checksum

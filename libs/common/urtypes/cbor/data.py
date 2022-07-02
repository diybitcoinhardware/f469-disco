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


class Tagging(object):
    __slots__ = ("tag", "obj")

    def __init__(self, tag, obj):
        self.tag = tag
        self.obj = obj

    def __eq__(self, other):
        return (
            isinstance(other, Tagging)
            and self.tag == other.tag
            and self.obj == other.obj
        )


class Mapping(object):
    __slots__ = "map"

    def __init__(self, map):
        self.map = map

    def mapping(obj):
        return Mapping(obj)


class DataItem(Tagging):
    def __init__(self, tag, map):
        super().__init__(tag, Mapping(map))
        self.tag = tag
        self.map = map


class _Undefined(object):
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not isinstance(cls._instance, cls):
            cls._instance = object.__new__(cls, *args, **kwargs)
        return cls._instance

    def __str__(self):
        return "Undefined"

    def __repr__(self):
        return "Undefined"


Undefined = _Undefined()

__all__ = ["Tagging", "Mapping", "DataItem"]

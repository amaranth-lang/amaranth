from enum import Enum
from collections import OrderedDict

from .. import tracer
from ..tools import union
from .ast import *


__all__ = ["Direction", "DIR_NONE", "DIR_FANOUT", "DIR_FANIN", "Layout", "Record"]


Direction = Enum('Direction', ('NONE', 'FANOUT', 'FANIN'))

DIR_NONE   = Direction.NONE
DIR_FANOUT = Direction.FANOUT
DIR_FANIN  = Direction.FANIN


class Layout:
    @staticmethod
    def wrap(obj):
        if isinstance(obj, Layout):
            return obj
        return Layout(obj)

    def __init__(self, fields):
        self.fields = OrderedDict()
        for field in fields:
            if not isinstance(field, tuple) or len(field) not in (2, 3):
                raise TypeError("Field {!r} has invalid layout: should be either "
                                "(name, shape) or (name, shape, direction)"
                                .format(field))
            if len(field) == 2:
                name, shape = field
                direction = DIR_NONE
                if isinstance(shape, list):
                    shape = Layout.wrap(shape)
            else:
                name, shape, direction = field
                if not isinstance(direction, Direction):
                    raise TypeError("Field {!r} has invalid direction: should be a Direction "
                                    "instance like DIR_FANIN"
                                    .format(field))
            if not isinstance(name, str):
                raise TypeError("Field {!r} has invalid name: should be a string"
                                .format(field))
            if not isinstance(shape, (int, tuple, Layout)):
                raise TypeError("Field {!r} has invalid shape: should be an int, tuple, or list "
                                "of fields of a nested record"
                                .format(field))
            if name in self.fields:
                raise NameError("Field {!r} has a name that is already present in the layout"
                                .format(field))
            self.fields[name] = (shape, direction)

    def __getitem__(self, name):
        return self.fields[name]

    def __iter__(self):
        for name, (shape, dir) in self.fields.items():
            yield (name, shape, dir)


class Record(Value):
    __slots__ = ("fields",)

    def __init__(self, layout, name=None):
        if name is None:
            try:
                name = tracer.get_var_name()
            except tracer.NameNotFound:
                pass
        self.name    = name
        self.src_loc = tracer.get_src_loc()

        def concat(a, b):
            if a is None:
                return b
            return "{}_{}".format(a, b)

        self.layout = Layout.wrap(layout)
        self.fields = OrderedDict()
        for field_name, field_shape, field_dir in self.layout:
            if isinstance(field_shape, Layout):
                self.fields[field_name] = Record(field_shape, name=concat(name, field_name))
            else:
                self.fields[field_name] = Signal(field_shape, name=concat(name, field_name))

    def __getattr__(self, name):
        return self[name]

    def __getitem__(self, name):
        try:
            return self.fields[name]
        except KeyError:
            if self.name is None:
                reference = "Unnamed record"
            else:
                reference = "Record '{}'".format(self.name)
            raise NameError("{} does not have a field '{}'. Did you mean one of: {}?"
                            .format(reference, name, ", ".join(self.fields))) from None

    def shape(self):
        return sum(len(f) for f in self.fields.values()), False

    def _lhs_signals(self):
        return union((f._lhs_signals() for f in self.fields.values()), start=SignalSet())

    def _rhs_signals(self):
        return union((f._rhs_signals() for f in self.fields.values()), start=SignalSet())

    def __repr__(self):
        fields = []
        for field_name, field in self.fields.items():
            if isinstance(field, Signal):
                fields.append(field_name)
            else:
                fields.append(repr(field))
        name = self.name
        if name is None:
            name = "<unnamed>"
        return "(rec {} {})".format(name, " ".join(fields))

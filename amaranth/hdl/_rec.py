# TODO(amaranth-0.6): remove module

from enum import Enum
from collections import OrderedDict
from functools import reduce, wraps

from .. import tracer
from .._utils import union
from ._ast import *
from ..lib import wiring


__all__ = ["Direction", "DIR_NONE", "DIR_FANOUT", "DIR_FANIN", "Layout", "Record"]


Direction = Enum('Direction', ('NONE', 'FANOUT', 'FANIN'))

DIR_NONE   = Direction.NONE
DIR_FANOUT = Direction.FANOUT
DIR_FANIN  = Direction.FANIN


class Layout:
    @staticmethod
    def cast(obj, *, src_loc_at=0):
        if isinstance(obj, Layout):
            return obj
        return Layout(obj, src_loc_at=1 + src_loc_at)

    def __init__(self, fields, *, src_loc_at=0):
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
                    shape = Layout.cast(shape)
            else:
                name, shape, direction = field
                if not isinstance(direction, Direction):
                    raise TypeError("Field {!r} has invalid direction: should be a Direction "
                                    "instance like DIR_FANIN"
                                    .format(field))
            if not isinstance(name, str):
                raise TypeError("Field {!r} has invalid name: should be a string"
                                .format(field))
            if not isinstance(shape, Layout):
                try:
                    # Check provided shape by calling Shape.cast and checking for exception
                    Shape.cast(shape, src_loc_at=1 + src_loc_at)
                except Exception:
                    raise TypeError("Field {!r} has invalid shape: should be castable to Shape "
                                    "or a list of fields of a nested record"
                                    .format(field))
            if name in self.fields:
                raise NameError("Field {!r} has a name that is already present in the layout"
                                .format(field))
            self.fields[name] = (shape, direction)

    def __getitem__(self, item):
        if isinstance(item, tuple):
            return Layout([
                (name, shape, dir)
                for (name, (shape, dir)) in self.fields.items()
                if name in item
            ])

        return self.fields[item]

    def __iter__(self):
        for name, (shape, dir) in self.fields.items():
            yield (name, shape, dir)

    def __eq__(self, other):
        return self.fields == other.fields

    def __repr__(self):
        field_reprs = []
        for name, shape, dir in self:
            if dir == DIR_NONE:
                field_reprs.append(f"({name!r}, {shape!r})")
            else:
                field_reprs.append(f"({name!r}, {shape!r}, Direction.{dir.name})")
        return "Layout([{}])".format(", ".join(field_reprs))


class Record(ValueCastable):
    @staticmethod
    def like(other, *, name=None, name_suffix=None, src_loc_at=0):
        if name is not None:
            new_name = str(name)
        elif name_suffix is not None:
            new_name = other.name + str(name_suffix)
        else:
            new_name = tracer.get_var_name(depth=2 + src_loc_at, default=None)

        def concat(a, b):
            if a is None:
                return b
            return f"{a}__{b}"

        fields = {}
        for field_name in other.fields:
            field = other[field_name]
            if isinstance(field, Record):
                fields[field_name] = Record.like(field, name=concat(new_name, field_name),
                                                 src_loc_at=1 + src_loc_at)
            else:
                fields[field_name] = Signal.like(field, name=concat(new_name, field_name),
                                                 src_loc_at=1 + src_loc_at)

        return Record(other.layout, name=new_name, fields=fields, src_loc_at=1)

    def __init__(self, layout, *, name=None, fields=None, src_loc_at=0):
        if name is None:
            name = tracer.get_var_name(depth=2 + src_loc_at, default=None)

        self.name    = name
        self.src_loc = tracer.get_src_loc(src_loc_at)

        def concat(a, b):
            if a is None:
                return b
            return f"{a}__{b}"

        self.layout = Layout.cast(layout, src_loc_at=1 + src_loc_at)
        self.fields = OrderedDict()
        for field_name, field_shape, field_dir in self.layout:
            if fields is not None and field_name in fields:
                field = fields[field_name]
                if isinstance(field_shape, Layout):
                    if isinstance(field, wiring.FlippedInterface):
                        field = wiring.flipped(field)
                    assert isinstance(field, Record) and field_shape == field.layout
                else:
                    assert isinstance(field, Signal) and Shape.cast(field_shape) == field.shape()
                self.fields[field_name] = field
            else:
                if isinstance(field_shape, Layout):
                    self.fields[field_name] = Record(field_shape, name=concat(name, field_name),
                                                     src_loc_at=1 + src_loc_at)
                else:
                    self.fields[field_name] = Signal(field_shape, name=concat(name, field_name),
                                                     src_loc_at=1 + src_loc_at)

    def __getattr__(self, name):
        return self[name]

    def __getitem__(self, item):
        if isinstance(item, str):
            try:
                return self.fields[item]
            except KeyError:
                if self.name is None:
                    reference = "Unnamed record"
                else:
                    reference = f"Record '{self.name}'"
                raise AttributeError("{} does not have a field '{}'. Did you mean one of: {}?"
                                     .format(reference, item, ", ".join(self.fields))) from None
        elif isinstance(item, tuple):
            return Record(self.layout[item], fields={
                field_name: field_value
                for field_name, field_value in self.fields.items()
                if field_name in item
            })
        else:
            try:
                return Value.__getitem__(self, item)
            except KeyError:
                if self.name is None:
                    reference = "Unnamed record"
                else:
                    reference = f"Record '{self.name}'"
                raise AttributeError("{} does not have a field '{}'. Did you mean one of: {}?"
                                     .format(reference, item, ", ".join(self.fields))) from None

    def as_value(self):
        return Cat(self.fields.values())

    def __len__(self):
        return len(self.as_value())

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

    def shape(self):
        return self.as_value().shape()

    def connect(self, *subordinates, include=None, exclude=None):
        def rec_name(record):
            if record.name is None:
                return "unnamed record"
            else:
                return f"record '{record.name}'"

        for field in include or {}:
            if field not in self.fields:
                raise AttributeError("Cannot include field '{}' because it is not present in {}"
                                     .format(field, rec_name(self)))
        for field in exclude or {}:
            if field not in self.fields:
                raise AttributeError("Cannot exclude field '{}' because it is not present in {}"
                                     .format(field, rec_name(self)))

        stmts = []
        for field in self.fields:
            if include is not None and field not in include:
                continue
            if exclude is not None and field in exclude:
                continue

            shape, direction = self.layout[field]
            if not isinstance(shape, Layout) and direction == DIR_NONE:
                raise TypeError("Cannot connect field '{}' of {} because it does not have "
                                "a direction"
                                .format(field, rec_name(self)))

            item = self.fields[field]
            subord_items = []
            for subord in subordinates:
                if field not in subord.fields:
                    raise AttributeError("Cannot connect field '{}' of {} to subordinate {} "
                                         "because the subordinate record does not have this field"
                                         .format(field, rec_name(self), rec_name(subord)))
                subord_items.append(subord.fields[field])

            if isinstance(shape, Layout):
                sub_include = include[field] if include and field in include else None
                sub_exclude = exclude[field] if exclude and field in exclude else None
                stmts += item.connect(*subord_items, include=sub_include, exclude=sub_exclude)
            else:
                if direction == DIR_FANOUT:
                    stmts += [sub_item.eq(item) for sub_item in subord_items]
                if direction == DIR_FANIN:
                    stmts += [item.eq(reduce(lambda a, b: a | b, subord_items))]

        return stmts

def _valueproxy(name):
    value_func = getattr(Value, name)
    @wraps(value_func)
    def _wrapper(self, *args, **kwargs):
        return value_func(Value.cast(self), *args, **kwargs)
    return _wrapper

for name in [
        "__bool__",
        "__invert__", "__neg__",
        "__add__", "__radd__", "__sub__", "__rsub__",
        "__mul__", "__rmul__",
        "__mod__", "__rmod__", "__floordiv__", "__rfloordiv__",
        "__lshift__", "__rlshift__", "__rshift__", "__rrshift__",
        "__and__", "__rand__", "__xor__", "__rxor__", "__or__", "__ror__",
        "__eq__", "__ne__", "__lt__", "__le__", "__gt__", "__ge__",
        "__abs__", "__len__",
        "as_unsigned", "as_signed", "bool", "any", "all", "xor", "implies",
        "bit_select", "word_select", "matches",
        "shift_left", "shift_right", "rotate_left", "rotate_right", "eq"
        ]:
    setattr(Record, name, _valueproxy(name))

del _valueproxy
del name

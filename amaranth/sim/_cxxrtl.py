import sys
from enum import IntEnum, IntFlag
from ctypes import (cdll, Structure, POINTER, CFUNCTYPE,
                    c_int, c_size_t, c_uint32, c_uint64, c_void_p, c_char_p,
                    pointer, byref, string_at)


__all__ = []


class _cxxrtl_toplevel(Structure):
    pass


cxxrtl_toplevel = POINTER(_cxxrtl_toplevel)


class _cxxrtl_handle(Structure):
    pass


cxxrtl_handle = POINTER(_cxxrtl_handle)


class cxxrtl_type(IntEnum):
    VALUE   = 0
    WIRE    = 1
    MEMORY  = 2
    ALIAS   = 3
    OUTLINE = 4


class cxxrtl_flag(IntFlag):
    INPUT  = 1 << 0
    OUTPUT = 1 << 1
    INOUT  = (INPUT|OUTPUT)
    DRIVEN_SYNC = 1 << 2
    DRIVEN_COMB = 1 << 3
    UNDRIVEN    = 1 << 4


class cxxrtl_object(Structure):
    _fields_ = [
        ("_type",   c_uint32),
        ("_flags",  c_uint32),
        ("width",   c_size_t),
        ("lsb_at",  c_size_t),
        ("depth",   c_size_t),
        ("zero_at", c_size_t),
        ("_curr",   POINTER(c_uint32)),
        ("_next",   POINTER(c_uint32)),
    ]

    @classmethod
    def create(cls, type, width, *, lsb_at=0, depth=1, zero_at=0, flags=cxxrtl_flag(0)):
        assert isinstance(type, cxxrtl_type) and isinstance(flags, cxxrtl_flag)

        obj = cls(
            _type=type, _flags=flags,
            width=width, lsb_at=lsb_at,
            depth=depth, zero_at=zero_at
        )
        obj._curr = (c_uint32 * (obj.chunks * depth))()
        if type == cxxrtl_type.VALUE:
            obj._next = obj._curr
        elif type == cxxrtl_type.WIRE:
            obj._next = (c_uint32 * (obj.chunks * depth))()
        else:
            assert False
        return obj

    @classmethod
    def create_shadow(cls, source):
        assert isinstance(source, cxxrtl_object) and source.type == cxxrtl_type.VALUE

        obj = cls(
            _type=cxxrtl_type.WIRE, _flags=cxxrtl_flag(0),
            width=source.width, lsb_at=source.lsb_at,
            depth=source.depth, zero_at=source.zero_at
        )
        obj._curr = source._curr
        obj._next = (c_uint32 * (obj.chunks * obj.depth))()
        return obj

    @property
    def type(self):
        return cxxrtl_type(self._type)

    @property
    def flags(self):
        return cxxrtl_flag(self._flags)

    @property
    def chunks(self):
        return ((self.width + 31) // 32) * self.depth

    @property
    def curr(self):
        value = 0
        for chunk in range(self.chunks)[::-1]:
            value <<= 32
            value |= self._curr[chunk]
        return value << self.lsb_at

    @curr.setter
    def curr(self, value):
        value = (value >> self.lsb_at) & ((1 << self.width) - 1)
        for chunk in range(self.chunks):
            self._curr[chunk] = value & 0xffffffff
            value >>= 32

    @property
    def next(self):
        value = 0
        for chunk in range(self.chunks)[::-1]:
            value <<= 32
            value |= self._next[chunk]
        return value << self.lsb_at

    @next.setter
    def next(self, value):
        value = (value >> self.lsb_at) & ((1 << self.width) - 1)
        for chunk in range(self.chunks):
            self._next[chunk] = value & 0xffffffff
            value >>= 32


cxxrtl_object_p = POINTER(cxxrtl_object)
cxxrtl_enum_callback_fn = CFUNCTYPE(c_void_p, cxxrtl_object_p, c_size_t)


class _cxxrtl_vcd(Structure):
    pass


cxxrtl_vcd = POINTER(_cxxrtl_vcd)
cxxrtl_vcd_filter_fn = CFUNCTYPE(c_void_p, c_char_p, cxxrtl_object_p)


class cxxrtl_library:
    def __init__(self, filename, *, design_name="cxxrtl_design"):
        self._library = library = cdll.LoadLibrary(filename)

        self.design_create = getattr(library, f"{design_name}_create")
        self.design_create.argtypes = []
        self.design_create.restype = cxxrtl_toplevel

        self.create = library.cxxrtl_create
        self.create.argtypes = [cxxrtl_toplevel]
        self.create.restype = cxxrtl_handle

        self.create_at = library.cxxrtl_create_at
        self.create_at.argtypes = [cxxrtl_toplevel, c_char_p]
        self.create_at.restype = cxxrtl_handle

        self.destroy = library.cxxrtl_destroy
        self.destroy.argtypes = [cxxrtl_handle]
        self.destroy.restype = None

        self.reset = library.cxxrtl_reset
        self.reset.argtypes = [cxxrtl_handle]
        self.reset.restype = None

        self.eval = library.cxxrtl_eval
        self.eval.argtypes = [cxxrtl_handle]
        self.eval.restype = c_int

        self.commit = library.cxxrtl_commit
        self.commit.argtypes = [cxxrtl_handle]
        self.commit.restype = c_int

        self.step = library.cxxrtl_step
        self.step.argtypes = [cxxrtl_handle]
        self.step.restype = None

        _get_parts = library.cxxrtl_get_parts
        _get_parts.argtypes = [cxxrtl_handle, c_char_p, POINTER(c_size_t)]
        _get_parts.restype = cxxrtl_object_p
        def get_parts(handle, name):
            count = c_size_t()
            parts = _get_parts(handle, name, byref(count))
            if parts:
                return [parts[n] for n in range(count.value)]
        self.get_parts = get_parts

        self.enum = library.cxxrtl_enum
        self.enum.argtypes = [cxxrtl_handle, c_void_p, cxxrtl_enum_callback_fn]
        self.enum.restype = None

        self.vcd_create = library.cxxrtl_vcd_create
        self.vcd_create.argtypes = []
        self.vcd_create.restype = cxxrtl_vcd

        self.vcd_destroy = library.cxxrtl_vcd_destroy
        self.vcd_destroy.argtypes = [cxxrtl_vcd]
        self.vcd_destroy.restype = None

        self.vcd_timescale = library.cxxrtl_vcd_timescale
        self.vcd_timescale.argtypes = [cxxrtl_vcd, c_int, c_char_p]
        self.vcd_timescale.restype = None

        self.vcd_add = library.cxxrtl_vcd_add
        self.vcd_add.argtypes = [cxxrtl_vcd, c_char_p, cxxrtl_object_p]
        self.vcd_add.restype = None

        self.vcd_add_from = library.cxxrtl_vcd_add_from
        self.vcd_add_from.argtypes = [cxxrtl_vcd, cxxrtl_handle]
        self.vcd_add_from.restype = None

        self.vcd_add_from_if = library.cxxrtl_vcd_add_from_if
        self.vcd_add_from_if.argtypes = [cxxrtl_vcd, cxxrtl_handle, c_void_p, cxxrtl_vcd_filter_fn]
        self.vcd_add_from_if.restype = None

        self.vcd_add_from_without_memories = library.cxxrtl_vcd_add_from_without_memories
        self.vcd_add_from_without_memories.argtypes = [cxxrtl_vcd, cxxrtl_handle]
        self.vcd_add_from_without_memories.restype = None

        self.vcd_sample = library.cxxrtl_vcd_sample
        self.vcd_sample.argtypes = [cxxrtl_vcd, c_uint64]
        self.vcd_sample.restype = None

        _vcd_read = library.cxxrtl_vcd_read
        _vcd_read.argtypes = [cxxrtl_vcd, POINTER(c_char_p), POINTER(c_size_t)]
        _vcd_read.restype = None
        def vcd_read(vcd):
            data = c_char_p()
            size = c_size_t()
            _vcd_read(vcd, byref(data), byref(size))
            return string_at(data.value, size.value)
        self.vcd_read = vcd_read


class cxxrtl_trace_library:
    def __init__(self, *args, **kwargs):
        self._library = cxxrtl_library(*args, **kwargs)

    def __getattr__(self, attr_name):
        if attr_name.startswith("_"):
            return super().__getattr__(attr_name)

        method = getattr(self._library, attr_name)
        def wrapper(*args):
            args_repr = ", ".join(map(repr, args))
            result = method(*args)
            print("cxxrtl_{}({})->{!r}".format(attr_name, args_repr, result), file=sys.stderr)
            return result

        setattr(self, attr_name, wrapper)
        return wrapper

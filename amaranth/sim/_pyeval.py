from amaranth.hdl._ast import *
from amaranth.hdl._mem import MemoryData
from amaranth.hdl._ir import DriverConflict


__all__ = ["eval_value", "eval_format", "eval_assign"]


def _eval_matches(test, patterns):
    if patterns is None:
        return True
    for pattern in patterns:
        if isinstance(pattern, str):
            mask  = int("".join("0" if b == "-" else "1" for b in pattern), 2)
            value = int("".join("0" if b == "-" else  b  for b in pattern), 2)
            if value == (mask & test):
                return True
        else:
            if pattern == test:
                return True
    return False


def eval_value(sim, value):
    if isinstance(value, Const):
        return value.value
    elif isinstance(value, Operator):
        if len(value.operands) == 1:
            op_a = eval_value(sim, value.operands[0])
            if value.operator in ("u", "s"):
                width = value.shape().width
                res = op_a
                res &= (1 << width) - 1
                if value.operator == "s" and res & (1 << (width - 1)):
                    res |= -1 << (width - 1)
                return res
            elif value.operator == "-":
                return -op_a
            elif value.operator == "~":
                shape = value.shape()
                if shape.signed:
                    return ~op_a
                else:
                    return ~op_a & ((1 << shape.width) - 1)
            elif value.operator in ("b", "r|"):
                return int(op_a != 0)
            elif value.operator == "r&":
                width = value.operands[0].shape().width
                mask = (1 << width) - 1
                return int((op_a & mask) == mask)
            elif value.operator == "r^":
                width = value.operands[0].shape().width
                mask = (1 << width) - 1
                # Believe it or not, this is the fastest way to compute a sideways XOR in Python.
                return format(op_a & mask, 'b').count('1') % 2
        elif len(value.operands) == 2:
            op_a = eval_value(sim, value.operands[0])
            op_b = eval_value(sim, value.operands[1])
            if value.operator == "|":
                return op_a | op_b
            elif value.operator == "&":
                return op_a & op_b
            elif value.operator == "^":
                return op_a ^ op_b
            elif value.operator == "+":
                return op_a + op_b
            elif value.operator == "-":
                return op_a - op_b
            elif value.operator == "*":
                return op_a * op_b
            elif value.operator == "//":
                if op_b == 0:
                    return 0
                return op_a // op_b
            elif value.operator == "%":
                if op_b == 0:
                    return 0
                return op_a % op_b
            elif value.operator == "<<":
                return op_a << op_b
            elif value.operator == ">>":
                return op_a >> op_b
            elif value.operator == "==":
                return int(op_a == op_b)
            elif value.operator == "!=":
                return int(op_a != op_b)
            elif value.operator == "<":
                return int(op_a < op_b)
            elif value.operator == "<=":
                return int(op_a <= op_b)
            elif value.operator == ">":
                return int(op_a > op_b)
            elif value.operator == ">=":
                return int(op_a >= op_b)
        assert False # :nocov:
    elif isinstance(value, Slice):
        res = eval_value(sim, value.value)
        res >>= value.start
        width = value.stop - value.start
        return res & ((1 << width) - 1)
    elif isinstance(value, Part):
        res = eval_value(sim, value.value)
        offset = eval_value(sim, value.offset)
        offset *= value.stride
        res >>= offset
        return res & ((1 << value.width) - 1)
    elif isinstance(value, Concat):
        res = 0
        pos = 0
        for part in value.parts:
            width = len(part)
            part = eval_value(sim, part)
            part &= (1 << width) - 1
            res |= part << pos
            pos += width
        return res
    elif isinstance(value, SwitchValue):
        test = eval_value(sim, value.test)
        for patterns, val in value.cases:
            if _eval_matches(test, patterns):
                return eval_value(sim, val)
        return 0
    elif isinstance(value, Signal):
        slot = sim.get_signal(value)
        return sim.slots[slot].curr
    elif isinstance(value, MemoryData._Row):
        slot = sim.get_memory(value._memory)
        return sim.slots[slot].read(value._index)
    elif isinstance(value, (ResetSignal, ClockSignal, AnyValue, Initial)):
        raise ValueError(f"Value {value!r} cannot be used in simulation")
    else:
        assert False # :nocov:


def value_to_string(value):
    """Unpack a Verilog-like (but LSB-first) string of unknown width from an integer."""
    msg = bytearray()
    while value:
        byte = value & 0xff
        value >>= 8
        if byte:
            msg.append(byte)
    return msg.decode()


def eval_format(sim, fmt):
    fmt = Format("{}", fmt)
    chunks = []
    for chunk in fmt._chunks:
        if isinstance(chunk, str):
            chunks.append(chunk)
        else:
            value, spec = chunk
            value = eval_value(sim, value)
            if spec.endswith("s"):
                chunks.append(format(value_to_string(value), spec[:-1]))
            else:
                chunks.append(format(value, spec))
    return "".join(chunks)


def _eval_assign_inner(sim, lhs, lhs_start, rhs, rhs_len):
    if isinstance(lhs, Operator) and lhs.operator in ("u", "s"):
        _eval_assign_inner(sim, lhs.operands[0], lhs_start, rhs, rhs_len)
    elif isinstance(lhs, Signal):
        lhs_stop = lhs_start + rhs_len
        if lhs_stop > len(lhs):
            lhs_stop = len(lhs)
        if lhs_start >= len(lhs):
            return
        slot = sim.get_signal(lhs)
        if sim.slots[slot].is_comb:
            raise DriverConflict("Combinationally driven signals cannot be overriden by testbenches")
        value = sim.slots[slot].next
        mask = (1 << lhs_stop) - (1 << lhs_start)
        value &= ~mask
        value |= (rhs << lhs_start) & mask
        value &= (1 << len(lhs)) - 1
        if lhs._signed and (value & (1 << (len(lhs) - 1))):
            value |= -1 << (len(lhs) - 1)
        sim.slots[slot].update(value)
    elif isinstance(lhs, MemoryData._Row):
        lhs_stop = lhs_start + rhs_len
        if lhs_stop > len(lhs):
            lhs_stop = len(lhs)
        if lhs_start >= len(lhs):
            return
        slot = sim.get_memory(lhs._memory)
        mask = (1 << lhs_stop) - (1 << lhs_start)
        sim.slots[slot].write(lhs._index, rhs << lhs_start, mask)
    elif isinstance(lhs, Slice):
        _eval_assign_inner(sim, lhs.value, lhs_start + lhs.start, rhs, rhs_len)
    elif isinstance(lhs, Concat):
        part_stop = 0
        for part in lhs.parts:
            part_start = part_stop
            part_len = len(part)
            part_stop = part_start + part_len
            if lhs_start >= part_stop:
                continue
            if lhs_start + rhs_len <= part_start:
                continue
            if lhs_start < part_start:
                part_lhs_start = 0
                part_rhs_start = part_start - lhs_start
            else:
                part_lhs_start = lhs_start - part_start
                part_rhs_start = 0
            if lhs_start + rhs_len >= part_stop:
                part_rhs_len = part_stop - lhs_start - part_rhs_start
            else:
                part_rhs_len = rhs_len - part_rhs_start
            part_rhs = rhs >> part_rhs_start
            part_rhs &= (1 << part_rhs_len) - 1
            _eval_assign_inner(sim, part, part_lhs_start, part_rhs, part_rhs_len)
    elif isinstance(lhs, Part):
        offset = eval_value(sim, lhs.offset)
        offset *= lhs.stride
        _eval_assign_inner(sim, lhs.value, lhs_start + offset, rhs, rhs_len)
    elif isinstance(lhs, SwitchValue):
        test = eval_value(sim, lhs.test)
        for patterns, val in lhs.cases:
            if _eval_matches(test, patterns):
                _eval_assign_inner(sim, val, lhs_start, rhs, rhs_len)
                return
    else:
        raise ValueError(f"Value {lhs!r} cannot be assigned")


def eval_assign(sim, lhs, value):
    _eval_assign_inner(sim, lhs, 0, value, len(lhs))

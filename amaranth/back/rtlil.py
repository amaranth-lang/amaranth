import io
from collections import OrderedDict
from contextlib import contextmanager
import warnings

from .._utils import bits_for, flatten
from ..hdl import ast, ir, mem, xfrm


__all__ = ["convert", "convert_fragment"]


_escape_map = str.maketrans({
    "\"": "\\\"",
    "\\": "\\\\",
    "\t": "\\t",
    "\r": "\\r",
    "\n": "\\n",
})


def _signed(value):
    if isinstance(value, str):
        return False
    elif isinstance(value, int):
        return value < 0
    elif isinstance(value, ast.Const):
        return value.signed
    else:
        assert False, "Invalid constant {!r}".format(value)


def _const(value):
    if isinstance(value, str):
        return "\"{}\"".format(value.translate(_escape_map))
    elif isinstance(value, int):
        if value in range(0, 2**31-1):
            return "{:d}".format(value)
        else:
            # This code path is only used for Instances, where Verilog-like behavior is desirable.
            # Verilog ensures that integers with unspecified width are 32 bits wide or more.
            width = max(32, bits_for(value))
            return _const(ast.Const(value, width))
    elif isinstance(value, ast.Const):
        value_twos_compl = value.value & ((1 << value.width) - 1)
        return "{}'{:0{}b}".format(value.width, value_twos_compl, value.width)
    else:
        assert False, "Invalid constant {!r}".format(value)


class _Namer:
    def __init__(self):
        super().__init__()
        self._anon  = 0
        self._index = 0
        self._names = set()

    def anonymous(self):
        name = "U$${}".format(self._anon)
        assert name not in self._names
        self._anon += 1
        return name

    def _make_name(self, name, local):
        if name is None:
            self._index += 1
            name = "${}".format(self._index)
        elif not local and name[0] not in "\\$":
            name = "\\{}".format(name)
        while name in self._names:
            self._index += 1
            name = "{}${}".format(name, self._index)
        self._names.add(name)
        return name


class _BufferedBuilder:
    def __init__(self):
        super().__init__()
        self._buffer = io.StringIO()

    def __str__(self):
        return self._buffer.getvalue()

    def _append(self, fmt, *args, **kwargs):
        self._buffer.write(fmt.format(*args, **kwargs))


class _ProxiedBuilder:
    def _append(self, *args, **kwargs):
        self.rtlil._append(*args, **kwargs)


class _AttrBuilder:
    def __init__(self, emit_src, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.emit_src = emit_src

    def _attribute(self, name, value, *, indent=0):
        self._append("{}attribute \\{} {}\n",
                     "  " * indent, name, _const(value))

    def _attributes(self, attrs, *, src=None, **kwargs):
        for name, value in attrs.items():
            self._attribute(name, value, **kwargs)
        if src and self.emit_src:
            self._attribute("src", src, **kwargs)


class _Builder(_BufferedBuilder, _Namer):
    def __init__(self, emit_src):
        super().__init__()
        self.emit_src = emit_src

    def module(self, name=None, attrs={}):
        name = self._make_name(name, local=False)
        return _ModuleBuilder(self, name, attrs)


class _ModuleBuilder(_AttrBuilder, _BufferedBuilder, _Namer):
    def __init__(self, rtlil, name, attrs):
        super().__init__(emit_src=rtlil.emit_src)
        self.rtlil = rtlil
        self.name  = name
        self.attrs = {"generator": "Amaranth"}
        self.attrs.update(attrs)

    def __enter__(self):
        self._attributes(self.attrs)
        self._append("module {}\n", self.name)
        return self

    def __exit__(self, *args):
        self._append("end\n")
        self.rtlil._buffer.write(str(self))

    def wire(self, width, port_id=None, port_kind=None, name=None, attrs={}, src=""):
        # Very large wires are unlikely to work. Verilog 1364-2005 requires the limit on vectors
        # to be at least 2**16 bits, and Yosys 0.9 cannot read RTLIL with wires larger than 2**32
        # bits. In practice, wires larger than 2**16 bits, although accepted, cause performance
        # problems without an immediately visible cause, so conservatively limit wire size.
        if width > 2 ** 16:
            raise OverflowError("Wire created at {} is {} bits wide, which is unlikely to "
                                "synthesize correctly"
                                .format(src or "unknown location", width))

        self._attributes(attrs, src=src, indent=1)
        name = self._make_name(name, local=False)
        if port_id is None:
            self._append("  wire width {} {}\n", width, name)
        else:
            assert port_kind in ("input", "output", "inout")
            self._append("  wire width {} {} {} {}\n", width, port_kind, port_id, name)
        return name

    def connect(self, lhs, rhs):
        self._append("  connect {} {}\n", lhs, rhs)

    def memory(self, width, size, name=None, attrs={}, src=""):
        self._attributes(attrs, src=src, indent=1)
        name = self._make_name(name, local=False)
        self._append("  memory width {} size {} {}\n", width, size, name)
        return name

    def cell(self, kind, name=None, params={}, ports={}, attrs={}, src=""):
        self._attributes(attrs, src=src, indent=1)
        name = self._make_name(name, local=False)
        self._append("  cell {} {}\n", kind, name)
        for param, value in params.items():
            if isinstance(value, float):
                self._append("    parameter real \\{} \"{!r}\"\n",
                             param, value)
            elif _signed(value):
                self._append("    parameter signed \\{} {}\n",
                             param, _const(value))
            else:
                self._append("    parameter \\{} {}\n",
                             param, _const(value))
        for port, wire in ports.items():
            self._append("    connect {} {}\n", port, wire)
        self._append("  end\n")
        return name

    def process(self, name=None, attrs={}, src=""):
        name = self._make_name(name, local=True)
        return _ProcessBuilder(self, name, attrs, src)


class _ProcessBuilder(_AttrBuilder, _BufferedBuilder):
    def __init__(self, rtlil, name, attrs, src):
        super().__init__(emit_src=rtlil.emit_src)
        self.rtlil = rtlil
        self.name  = name
        self.attrs = {}
        self.src   = src

    def __enter__(self):
        self._attributes(self.attrs, src=self.src, indent=1)
        self._append("  process {}\n", self.name)
        return self

    def __exit__(self, *args):
        self._append("  end\n")
        self.rtlil._buffer.write(str(self))

    def case(self):
        return _CaseBuilder(self, indent=2)

    def sync(self, kind, cond=None):
        return _SyncBuilder(self, kind, cond)


class _CaseBuilder(_ProxiedBuilder):
    def __init__(self, rtlil, indent):
        self.rtlil  = rtlil
        self.indent = indent

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def assign(self, lhs, rhs):
        self._append("{}assign {} {}\n", "  " * self.indent, lhs, rhs)

    def switch(self, cond, attrs={}, src=""):
        return _SwitchBuilder(self.rtlil, cond, attrs, src, self.indent)


class _SwitchBuilder(_AttrBuilder, _ProxiedBuilder):
    def __init__(self, rtlil, cond, attrs, src, indent):
        super().__init__(emit_src=rtlil.emit_src)
        self.rtlil  = rtlil
        self.cond   = cond
        self.attrs  = attrs
        self.src    = src
        self.indent = indent

    def __enter__(self):
        self._attributes(self.attrs, src=self.src, indent=self.indent)
        self._append("{}switch {}\n", "  " * self.indent, self.cond)
        return self

    def __exit__(self, *args):
        self._append("{}end\n", "  " * self.indent)

    def case(self, *values, attrs={}, src=""):
        self._attributes(attrs, src=src, indent=self.indent + 1)
        if values == ():
            self._append("{}case\n", "  " * (self.indent + 1))
        else:
            self._append("{}case {}\n", "  " * (self.indent + 1),
                         ", ".join("{}'{}".format(len(value), value) for value in values))
        return _CaseBuilder(self.rtlil, self.indent + 2)


class _SyncBuilder(_ProxiedBuilder):
    def __init__(self, rtlil, kind, cond):
        self.rtlil = rtlil
        self.kind  = kind
        self.cond  = cond

    def __enter__(self):
        if self.cond is None:
            self._append("    sync {}\n", self.kind)
        else:
            self._append("    sync {} {}\n", self.kind, self.cond)
        return self

    def __exit__(self, *args):
        pass

    def update(self, lhs, rhs):
        self._append("      update {} {}\n", lhs, rhs)


def _src(src_loc):
    if src_loc is None:
        return None
    file, line = src_loc
    return "{}:{}".format(file, line)


class _LegalizeValue(Exception):
    def __init__(self, value, branches, src_loc):
        self.value    = value
        self.branches = list(branches)
        self.src_loc  = src_loc


class _ValueCompilerState:
    def __init__(self, rtlil):
        self.rtlil  = rtlil
        self.wires  = ast.SignalDict()
        self.driven = ast.SignalDict()
        self.ports  = ast.SignalDict()
        self.anys   = ast.ValueDict()

        self.expansions = ast.ValueDict()

    def add_driven(self, signal, sync):
        self.driven[signal] = sync

    def add_port(self, signal, kind):
        assert kind in ("i", "o", "io")
        if kind == "i":
            kind = "input"
        elif kind == "o":
            kind = "output"
        elif kind == "io":
            kind = "inout"
        self.ports[signal] = (len(self.ports), kind)

    def resolve(self, signal, prefix=None):
        if len(signal) == 0:
            return "{ }", "{ }"

        if signal in self.wires:
            return self.wires[signal]

        if signal in self.ports:
            port_id, port_kind = self.ports[signal]
        else:
            port_id = port_kind = None
        if prefix is not None:
            wire_name = "{}_{}".format(prefix, signal.name)
        else:
            wire_name = signal.name

        is_sync_driven = signal in self.driven and self.driven[signal]
        
        attrs = dict(signal.attrs)
        if signal._enum_class is not None:
            attrs["enum_base_type"] = signal._enum_class.__name__
            for value in signal._enum_class:
                attrs["enum_value_{:0{}b}".format(value.value, signal.width)] = value.name

        # For every signal in the sync domain, assign \sig's initial value (using the \init reg
        # attribute) to the reset value.
        if is_sync_driven:
            attrs["init"] = ast.Const(signal.reset, signal.width)

        wire_curr = self.rtlil.wire(width=signal.width, name=wire_name,
                                    port_id=port_id, port_kind=port_kind,
                                    attrs=attrs, src=_src(signal.src_loc))
        if is_sync_driven:
            wire_next = self.rtlil.wire(width=signal.width, name=wire_curr + "$next",
                                        src=_src(signal.src_loc))
        else:
            wire_next = None
        self.wires[signal] = (wire_curr, wire_next)

        return wire_curr, wire_next

    def resolve_curr(self, signal, prefix=None):
        wire_curr, wire_next = self.resolve(signal, prefix)
        return wire_curr

    def expand(self, value):
        if not self.expansions:
            return value
        return self.expansions.get(value, value)

    @contextmanager
    def expand_to(self, value, expansion):
        try:
            assert value not in self.expansions
            self.expansions[value] = expansion
            yield
        finally:
            del self.expansions[value]


class _ValueCompiler(xfrm.ValueVisitor):
    def __init__(self, state):
        self.s = state

    def on_unknown(self, value):
        if value is None:
            return None
        else:
            super().on_unknown(value)

    def on_ClockSignal(self, value):
        raise NotImplementedError # :nocov:

    def on_ResetSignal(self, value):
        raise NotImplementedError # :nocov:

    def on_Sample(self, value):
        raise NotImplementedError # :nocov:

    def on_Initial(self, value):
        raise NotImplementedError # :nocov:

    def on_Cat(self, value):
        return "{{ {} }}".format(" ".join(reversed([self(o) for o in value.parts])))

    def _prepare_value_for_Slice(self, value):
        raise NotImplementedError # :nocov:

    def on_Slice(self, value):
        if value.start == 0 and value.stop == len(value.value):
            return self(value.value)

        if isinstance(value.value, ast.UserValue):
            sigspec = self._prepare_value_for_Slice(value.value._lazy_lower())
        else:
            sigspec = self._prepare_value_for_Slice(value.value)

        if value.start == value.stop:
            return "{}"
        elif value.start + 1 == value.stop:
            return "{} [{}]".format(sigspec, value.start)
        else:
            return "{} [{}:{}]".format(sigspec, value.stop - 1, value.start)

    def on_ArrayProxy(self, value):
        index = self.s.expand(value.index)
        if isinstance(index, ast.Const):
            if index.value < len(value.elems):
                elem = value.elems[index.value]
            else:
                elem = value.elems[-1]
            return self.match_shape(elem, *value.shape())
        else:
            max_index = 1 << len(value.index)
            max_elem  = len(value.elems)
            raise _LegalizeValue(value.index, range(min(max_index, max_elem)), value.src_loc)


class _RHSValueCompiler(_ValueCompiler):
    operator_map = {
        (1, "~"):    "$not",
        (1, "-"):    "$neg",
        (1, "b"):    "$reduce_bool",
        (1, "r|"):   "$reduce_or",
        (1, "r&"):   "$reduce_and",
        (1, "r^"):   "$reduce_xor",
        (2, "+"):    "$add",
        (2, "-"):    "$sub",
        (2, "*"):    "$mul",
        (2, "//"):   "$divfloor",
        (2, "%"):    "$modfloor",
        (2, "**"):   "$pow",
        (2, "<<"):   "$sshl",
        (2, ">>"):   "$sshr",
        (2, "&"):    "$and",
        (2, "^"):    "$xor",
        (2, "|"):    "$or",
        (2, "=="):   "$eq",
        (2, "!="):   "$ne",
        (2, "<"):    "$lt",
        (2, "<="):   "$le",
        (2, ">"):    "$gt",
        (2, ">="):   "$ge",
        (3, "m"):    "$mux",
    }

    def on_value(self, value):
        return super().on_value(self.s.expand(value))

    def on_Const(self, value):
        return _const(value)

    def on_AnyConst(self, value):
        if value in self.s.anys:
            return self.s.anys[value]

        res_bits, res_sign = value.shape()
        res = self.s.rtlil.wire(width=res_bits, src=_src(value.src_loc))
        self.s.rtlil.cell("$anyconst", ports={
            "\\Y": res,
        }, params={
            "WIDTH": res_bits,
        }, src=_src(value.src_loc))
        self.s.anys[value] = res
        return res

    def on_AnySeq(self, value):
        if value in self.s.anys:
            return self.s.anys[value]

        res_bits, res_sign = value.shape()
        res = self.s.rtlil.wire(width=res_bits, src=_src(value.src_loc))
        self.s.rtlil.cell("$anyseq", ports={
            "\\Y": res,
        }, params={
            "WIDTH": res_bits,
        }, src=_src(value.src_loc))
        self.s.anys[value] = res
        return res

    def on_Signal(self, value):
        wire_curr, wire_next = self.s.resolve(value)
        return wire_curr

    def on_Operator_unary(self, value):
        arg, = value.operands
        if value.operator in ("u", "s"):
            # These operators don't change the bit pattern, only its interpretation.
            return self(arg)

        arg_bits, arg_sign = arg.shape()
        res_bits, res_sign = value.shape()
        res = self.s.rtlil.wire(width=res_bits, src=_src(value.src_loc))
        self.s.rtlil.cell(self.operator_map[(1, value.operator)], ports={
            "\\A": self(arg),
            "\\Y": res,
        }, params={
            "A_SIGNED": arg_sign,
            "A_WIDTH": arg_bits,
            "Y_WIDTH": res_bits,
        }, src=_src(value.src_loc))
        return res

    def match_shape(self, value, new_bits, new_sign):
        if isinstance(value, ast.Const):
            return self(ast.Const(value.value, ast.Shape(new_bits, new_sign)))

        value_bits, value_sign = value.shape()
        if new_bits <= value_bits:
            return self(ast.Slice(value, 0, new_bits))

        res = self.s.rtlil.wire(width=new_bits, src=_src(value.src_loc))
        self.s.rtlil.cell("$pos", ports={
            "\\A": self(value),
            "\\Y": res,
        }, params={
            "A_SIGNED": value_sign,
            "A_WIDTH": value_bits,
            "Y_WIDTH": new_bits,
        }, src=_src(value.src_loc))
        return res

    def on_Operator_binary(self, value):
        lhs, rhs = value.operands
        lhs_bits, lhs_sign = lhs.shape()
        rhs_bits, rhs_sign = rhs.shape()
        if lhs_sign == rhs_sign or value.operator in ("<<", ">>", "**"):
            lhs_wire = self(lhs)
            rhs_wire = self(rhs)
        else:
            lhs_bits = rhs_bits = max(lhs_bits + rhs_sign, rhs_bits + lhs_sign)
            lhs_sign = rhs_sign = True
            lhs_wire = self.match_shape(lhs, lhs_bits, lhs_sign)
            rhs_wire = self.match_shape(rhs, rhs_bits, rhs_sign)
        res_bits, res_sign = value.shape()
        res = self.s.rtlil.wire(width=res_bits, src=_src(value.src_loc))
        self.s.rtlil.cell(self.operator_map[(2, value.operator)], ports={
            "\\A": lhs_wire,
            "\\B": rhs_wire,
            "\\Y": res,
        }, params={
            "A_SIGNED": lhs_sign,
            "A_WIDTH": lhs_bits,
            "B_SIGNED": rhs_sign,
            "B_WIDTH": rhs_bits,
            "Y_WIDTH": res_bits,
        }, src=_src(value.src_loc))
        if value.operator in ("//", "%"):
            # RTLIL leaves division by zero undefined, but we require it to return zero.
            divmod_res = res
            res = self.s.rtlil.wire(width=res_bits, src=_src(value.src_loc))
            self.s.rtlil.cell("$mux", ports={
                "\\A": divmod_res,
                "\\B": self(ast.Const(0, ast.Shape(res_bits, res_sign))),
                "\\S": self(rhs == 0),
                "\\Y": res,
            }, params={
                "WIDTH": res_bits
            }, src=_src(value.src_loc))
        return res

    def on_Operator_mux(self, value):
        sel, val1, val0 = value.operands
        if len(sel) != 1:
            sel = sel.bool()
        val1_bits, val1_sign = val1.shape()
        val0_bits, val0_sign = val0.shape()
        res_bits, res_sign = value.shape()
        val1_bits = val0_bits = res_bits = max(val1_bits, val0_bits, res_bits)
        val1_wire = self.match_shape(val1, val1_bits, val1_sign)
        val0_wire = self.match_shape(val0, val0_bits, val0_sign)
        res = self.s.rtlil.wire(width=res_bits, src=_src(value.src_loc))
        self.s.rtlil.cell("$mux", ports={
            "\\A": val0_wire,
            "\\B": val1_wire,
            "\\S": self(sel),
            "\\Y": res,
        }, params={
            "WIDTH": res_bits
        }, src=_src(value.src_loc))
        return res

    def on_Operator(self, value):
        if len(value.operands) == 1:
            return self.on_Operator_unary(value)
        elif len(value.operands) == 2:
            return self.on_Operator_binary(value)
        elif len(value.operands) == 3:
            assert value.operator == "m"
            return self.on_Operator_mux(value)
        else:
            raise TypeError # :nocov:

    def _prepare_value_for_Slice(self, value):
        if isinstance(value, (ast.Signal, ast.Slice, ast.Cat)):
            sigspec = self(value)
        else:
            sigspec = self.s.rtlil.wire(len(value), src=_src(value.src_loc))
            self.s.rtlil.connect(sigspec, self(value))
        return sigspec

    def on_Part(self, value):
        lhs, rhs = value.value, value.offset
        if value.stride != 1:
            rhs *= value.stride
        lhs_bits, lhs_sign = lhs.shape()
        rhs_bits, rhs_sign = rhs.shape()
        res_bits, res_sign = value.shape()
        res = self.s.rtlil.wire(width=res_bits, src=_src(value.src_loc))
        # Note: Verilog's x[o+:w] construct produces a $shiftx cell, not a $shift cell.
        # However, Amaranth's semantics defines the out-of-range bits to be zero, so it is correct
        # to use a $shift cell here instead, even though it produces less idiomatic Verilog.
        self.s.rtlil.cell("$shift", ports={
            "\\A": self(lhs),
            "\\B": self(rhs),
            "\\Y": res,
        }, params={
            "A_SIGNED": lhs_sign,
            "A_WIDTH": lhs_bits,
            "B_SIGNED": rhs_sign,
            "B_WIDTH": rhs_bits,
            "Y_WIDTH": res_bits,
        }, src=_src(value.src_loc))
        return res

    def on_Repl(self, value):
        return "{{ {} }}".format(" ".join(self(value.value) for _ in range(value.count)))


class _LHSValueCompiler(_ValueCompiler):
    def on_Const(self, value):
        raise TypeError # :nocov:

    def on_AnyConst(self, value):
        raise TypeError # :nocov:

    def on_AnySeq(self, value):
        raise TypeError # :nocov:

    def on_Operator(self, value):
        raise TypeError # :nocov:

    def match_shape(self, value, new_bits, new_sign):
        value_bits, value_sign = value.shape()
        if new_bits == value_bits:
            return self(value)
        elif new_bits < value_bits:
            return self(ast.Slice(value, 0, new_bits))
        else: # new_bits > value_bits
            dummy_bits = new_bits - value_bits
            dummy_wire = self.s.rtlil.wire(dummy_bits)
            return "{{ {} {} }}".format(dummy_wire, self(value))

    def on_Signal(self, value):
        if value not in self.s.driven:
            raise ValueError("No LHS wire for non-driven signal {}".format(repr(value)))
        wire_curr, wire_next = self.s.resolve(value)
        return wire_next or wire_curr

    def _prepare_value_for_Slice(self, value):
        assert isinstance(value, (ast.Signal, ast.Slice, ast.Cat, ast.Part))
        return self(value)

    def on_Part(self, value):
        offset = self.s.expand(value.offset)
        if isinstance(offset, ast.Const):
            start = offset.value * value.stride
            stop  = start + value.width
            slice = self(ast.Slice(value.value, start, min(len(value.value), stop)))
            if len(value.value) >= stop:
                return slice
            else:
                dummy_wire = self.s.rtlil.wire(stop - len(value.value))
                return "{{ {} {} }}".format(dummy_wire, slice)
        else:
            # Only so many possible parts. The amount of branches is exponential; if value.offset
            # is large (e.g. 32-bit wide), trying to naively legalize it is likely to exhaust
            # system resources.
            max_branches = len(value.value) // value.stride + 1
            raise _LegalizeValue(value.offset,
                                 range(1 << len(value.offset))[:max_branches],
                                 value.src_loc)

    def on_Repl(self, value):
        raise TypeError # :nocov:


class _StatementCompiler(xfrm.StatementVisitor):
    def __init__(self, state, rhs_compiler, lhs_compiler):
        self.state        = state
        self.rhs_compiler = rhs_compiler
        self.lhs_compiler = lhs_compiler

        self._case        = None
        self._test_cache  = {}
        self._has_rhs     = False
        self._wrap_assign = False

    @contextmanager
    def case(self, switch, values, attrs={}, src=""):
        try:
            old_case = self._case
            with switch.case(*values, attrs=attrs, src=src) as self._case:
                yield
        finally:
            self._case = old_case

    def _check_rhs(self, value):
        if self._has_rhs or next(iter(value._rhs_signals()), None) is not None:
            self._has_rhs = True

    def on_Assign(self, stmt):
        self._check_rhs(stmt.rhs)

        lhs_bits, lhs_sign = stmt.lhs.shape()
        rhs_bits, rhs_sign = stmt.rhs.shape()
        if lhs_bits == rhs_bits:
            rhs_sigspec = self.rhs_compiler(stmt.rhs)
        else:
            # In RTLIL, LHS and RHS of assignment must have exactly same width.
            rhs_sigspec = self.rhs_compiler.match_shape(
                stmt.rhs, lhs_bits, lhs_sign)
        if self._wrap_assign:
            # In RTLIL, all assigns are logically sequenced before all switches, even if they are
            # interleaved in the source. In Amaranth, the source ordering is used. To handle this
            # mismatch, we wrap all assigns following a switch in a dummy switch.
            with self._case.switch("{ }") as wrap_switch:
                with wrap_switch.case() as wrap_case:
                    wrap_case.assign(self.lhs_compiler(stmt.lhs), rhs_sigspec)
        else:
            self._case.assign(self.lhs_compiler(stmt.lhs), rhs_sigspec)

    def on_property(self, stmt):
        self(stmt._check.eq(stmt.test))
        self(stmt._en.eq(1))

        en_wire = self.rhs_compiler(stmt._en)
        check_wire = self.rhs_compiler(stmt._check)
        self.state.rtlil.cell("$" + stmt._kind, ports={
            "\\A": check_wire,
            "\\EN": en_wire,
        }, src=_src(stmt.src_loc))

    on_Assert = on_property
    on_Assume = on_property
    on_Cover  = on_property

    def on_Switch(self, stmt):
        self._check_rhs(stmt.test)

        if not self.state.expansions:
            # We repeatedly translate the same switches over and over (see the LHSGroupAnalyzer
            # related code below), and translating the switch test only once helps readability.
            if stmt not in self._test_cache:
                self._test_cache[stmt] = self.rhs_compiler(stmt.test)
            test_sigspec = self._test_cache[stmt]
        else:
            # However, if the switch test contains an illegal value, then it may not be cached
            # (since the illegal value will be repeatedly replaced with different constants), so
            # don't cache anything in that case.
            test_sigspec = self.rhs_compiler(stmt.test)

        with self._case.switch(test_sigspec, src=_src(stmt.src_loc)) as switch:
            for values, stmts in stmt.cases.items():
                case_attrs = {}
                if values in stmt.case_src_locs:
                    case_attrs["src"] = _src(stmt.case_src_locs[values])
                if isinstance(stmt.test, ast.Signal) and stmt.test.decoder:
                    decoded_values = []
                    for value in values:
                        if "-" in value:
                            decoded_values.append("<multiple>")
                        else:
                            decoded_values.append(stmt.test.decoder(int(value, 2)))
                    case_attrs["amaranth.decoding"] = "|".join(decoded_values)
                with self.case(switch, values, attrs=case_attrs):
                    self._wrap_assign = False
                    self.on_statements(stmts)
        self._wrap_assign = True

    def on_statement(self, stmt):
        try:
            super().on_statement(stmt)
        except _LegalizeValue as legalize:
            with self._case.switch(self.rhs_compiler(legalize.value),
                                   src=_src(legalize.src_loc)) as switch:
                shape = legalize.value.shape()
                tests = ["{:0{}b}".format(v, shape.width) for v in legalize.branches]
                if tests:
                    tests[-1] = "-" * shape.width
                for branch, test in zip(legalize.branches, tests):
                    with self.case(switch, (test,)):
                        self._wrap_assign = False
                        branch_value = ast.Const(branch, shape)
                        with self.state.expand_to(legalize.value, branch_value):
                            self.on_statement(stmt)
            self._wrap_assign = True

    def on_statements(self, stmts):
        for stmt in stmts:
            self.on_statement(stmt)


def _convert_fragment(builder, fragment, name_map, hierarchy):
    if isinstance(fragment, ir.Instance):
        port_map = OrderedDict()
        for port_name, (value, dir) in fragment.named_ports.items():
            port_map["\\{}".format(port_name)] = value

        if fragment.type[0] == "$":
            return fragment.type, port_map
        else:
            return "\\{}".format(fragment.type), port_map

    module_name  = hierarchy[-1] or "anonymous"
    module_attrs = OrderedDict()
    if len(hierarchy) == 1:
        module_attrs["top"] = 1
    module_attrs["amaranth.hierarchy"] = ".".join(name or "anonymous" for name in hierarchy)

    with builder.module(module_name, attrs=module_attrs) as module:
        compiler_state = _ValueCompilerState(module)
        rhs_compiler   = _RHSValueCompiler(compiler_state)
        lhs_compiler   = _LHSValueCompiler(compiler_state)
        stmt_compiler  = _StatementCompiler(compiler_state, rhs_compiler, lhs_compiler)

        # If the fragment is completely empty, add a dummy wire to it, or Yosys will interpret
        # it as a black box by default (when read as Verilog).
        if not fragment.ports and not fragment.statements and not fragment.subfragments:
            module.wire(1, name="$empty_module_filler")

        # Register all signals driven in the current fragment. This must be done first, as it
        # affects further codegen; e.g. whether \sig$next signals will be generated and used.
        for domain, signal in fragment.iter_drivers():
            compiler_state.add_driven(signal, sync=domain is not None)

        # Transform all signals used as ports in the current fragment eagerly and outside of
        # any hierarchy, to make sure they get sensible (non-prefixed) names.
        for signal in fragment.ports:
            compiler_state.add_port(signal, fragment.ports[signal])
            compiler_state.resolve_curr(signal)

        # Transform all clocks clocks and resets eagerly and outside of any hierarchy, to make
        # sure they get sensible (non-prefixed) names. This does not affect semantics.
        for domain, _ in fragment.iter_sync():
            cd = fragment.domains[domain]
            compiler_state.resolve_curr(cd.clk)
            if cd.rst is not None:
                compiler_state.resolve_curr(cd.rst)

        # Transform all subfragments to their respective cells. Transforming signals connected
        # to their ports into wires eagerly makes sure they get sensible (prefixed with submodule
        # name) names.
        memories = OrderedDict()
        for subfragment, sub_name in fragment.subfragments:
            if sub_name is None:
                sub_name = module.anonymous()

            sub_params = OrderedDict()
            if hasattr(subfragment, "parameters"):
                for param_name, param_value in subfragment.parameters.items():
                    if isinstance(param_value, mem.Memory):
                        memory = param_value
                        if memory not in memories:
                            memories[memory] = module.memory(width=memory.width, size=memory.depth,
                                                             name=memory.name, attrs=memory.attrs)
                            addr_bits = bits_for(memory.depth)
                            data_parts = []
                            data_mask = (1 << memory.width) - 1
                            for addr in range(memory.depth):
                                if addr < len(memory.init):
                                    data = memory.init[addr] & data_mask
                                else:
                                    data = 0
                                data_parts.append("{:0{}b}".format(data, memory.width))
                            module.cell("$meminit", ports={
                                "\\ADDR": rhs_compiler(ast.Const(0, addr_bits)),
                                "\\DATA": "{}'".format(memory.width * memory.depth) +
                                          "".join(reversed(data_parts)),
                            }, params={
                                "MEMID": memories[memory],
                                "ABITS": addr_bits,
                                "WIDTH": memory.width,
                                "WORDS": memory.depth,
                                "PRIORITY": 0,
                            })

                        param_value = memories[memory]

                    sub_params[param_name] = param_value

            sub_type, sub_port_map = \
                _convert_fragment(builder, subfragment, name_map,
                                  hierarchy=hierarchy + (sub_name,))

            sub_ports = OrderedDict()
            for port, value in sub_port_map.items():
                if not isinstance(subfragment, ir.Instance):
                    for signal in value._rhs_signals():
                        compiler_state.resolve_curr(signal, prefix=sub_name)
                if len(value) > 0:
                    sub_ports[port] = rhs_compiler(value)

            module.cell(sub_type, name=sub_name, ports=sub_ports, params=sub_params,
                        attrs=subfragment.attrs)

        # If we emit all of our combinatorial logic into a single RTLIL process, Verilog
        # simulators will break horribly, because Yosys write_verilog transforms RTLIL processes
        # into always @* blocks with blocking assignment, and that does not create delta cycles.
        #
        # Therefore, we translate the fragment as many times as there are independent groups
        # of signals (a group is a transitive closure of signals that appear together on LHS),
        # splitting them into many RTLIL (and thus Verilog) processes.
        lhs_grouper = xfrm.LHSGroupAnalyzer()
        lhs_grouper.on_statements(fragment.statements)

        for group, group_signals in lhs_grouper.groups().items():
            lhs_group_filter = xfrm.LHSGroupFilter(group_signals)
            group_stmts = lhs_group_filter(fragment.statements)

            with module.process(name="$group_{}".format(group)) as process:
                with process.case() as case:
                    # For every signal in comb domain, assign \sig$next to the reset value.
                    # For every signal in sync domains, assign \sig$next to the current
                    # value (\sig).
                    for domain, signal in fragment.iter_drivers():
                        if signal not in group_signals:
                            continue
                        if domain is None:
                            prev_value = ast.Const(signal.reset, signal.width)
                        else:
                            prev_value = signal
                        case.assign(lhs_compiler(signal), rhs_compiler(prev_value))

                    # Convert statements into decision trees.
                    stmt_compiler._case = case
                    stmt_compiler._has_rhs = False
                    stmt_compiler._wrap_assign = False
                    stmt_compiler(group_stmts)
        
        # For every driven signal in the sync domain, create a flop of appropriate type. Which type
        # is appropriate depends on the domain: for domains with sync reset, it is a $dff, for
        # domains with async reset it is an $adff. The latter is directly provided with the reset
        # value as a parameter to the cell, which is directly assigned during reset.
        for domain, signal in fragment.iter_sync():
            cd = fragment.domains[domain]

            wire_clk = compiler_state.resolve_curr(cd.clk)
            wire_rst = compiler_state.resolve_curr(cd.rst) if cd.rst is not None else None
            wire_curr, wire_next = compiler_state.resolve(signal)

            if not cd.async_reset:
                # For sync reset flops, the reset value comes from logic inserted by 
                # `hdl.xfrm.DomainLowerer`.
                module.cell("$dff", ports={
                    "\\CLK": wire_clk,
                    "\\D": wire_next,
                    "\\Q": wire_curr
                }, params={
                    "CLK_POLARITY": int(cd.clk_edge == "pos"),
                    "WIDTH": signal.width
                })
            else:
                # For async reset flops, the reset value is provided directly to the cell.
                module.cell("$adff", ports={
                    "\\ARST": wire_rst,
                    "\\CLK": wire_clk,
                    "\\D": wire_next,
                    "\\Q": wire_curr
                }, params={
                    "ARST_POLARITY": ast.Const(1),
                    "ARST_VALUE": ast.Const(signal.reset, signal.width),
                    "CLK_POLARITY": int(cd.clk_edge == "pos"),
                    "WIDTH": signal.width
                })

        # Any signals that are used but neither driven nor connected to an input port always
        # assume their reset values. We need to assign the reset value explicitly, since only
        # driven sync signals are handled by the logic above.
        #
        # Because this assignment is done at a late stage, a single Signal object can get assigned
        # many times, once in each module it is used. This is a deliberate decision; the possible
        # alternatives are to add ports for undriven signals (which requires choosing one module
        # to drive it to reset value arbitrarily) or to replace them with their reset value (which
        # removes valuable source location information).
        driven = ast.SignalSet()
        for domain, signals in fragment.iter_drivers():
            driven.update(flatten(signal._lhs_signals() for signal in signals))
        driven.update(fragment.iter_ports(dir="i"))
        driven.update(fragment.iter_ports(dir="io"))
        for subfragment, sub_name in fragment.subfragments:
            driven.update(subfragment.iter_ports(dir="o"))
            driven.update(subfragment.iter_ports(dir="io"))

        for wire in compiler_state.wires:
            if wire in driven:
                continue
            wire_curr, _ = compiler_state.wires[wire]
            module.connect(wire_curr, rhs_compiler(ast.Const(wire.reset, wire.width)))

    # Collect the names we've given to our ports in RTLIL, and correlate these with the signals
    # represented by these ports. If we are a submodule, this will be necessary to create a cell
    # for us in the parent module.
    port_map = OrderedDict()
    for signal in fragment.ports:
        port_map[compiler_state.resolve_curr(signal)] = signal

    # Finally, collect the names we've given to each wire in RTLIL, and provide these to
    # the caller, to allow manipulating them in the toolchain.
    for signal in compiler_state.wires:
        wire_name = compiler_state.resolve_curr(signal)
        if wire_name.startswith("\\"):
            wire_name = wire_name[1:]
        name_map[signal] = hierarchy + (wire_name,)

    return module.name, port_map


def convert_fragment(fragment, name="top", *, emit_src=True):
    assert isinstance(fragment, ir.Fragment)
    builder = _Builder(emit_src=emit_src)
    name_map = ast.SignalDict()
    _convert_fragment(builder, fragment, name_map, hierarchy=(name,))
    return str(builder), name_map


def convert(elaboratable, name="top", platform=None, ports=None, *, emit_src=True, **kwargs):
    # TODO(amaranth-0.4): remove
    if ports is None:
        warnings.warn("Implicit port determination is deprecated, specify ports explictly",
                      DeprecationWarning, stacklevel=2)
    fragment = ir.Fragment.get(elaboratable, platform).prepare(ports=ports, **kwargs)
    il_text, name_map = convert_fragment(fragment, name, emit_src=emit_src)
    return il_text

import io
import textwrap
from collections import defaultdict, OrderedDict
from contextlib import contextmanager

from ..tools import bits_for
from ..hdl import ast, ir, mem, xfrm


__all__ = ["convert"]


class _Namer:
    def __init__(self):
        super().__init__()
        self._index = 0
        self._names = set()

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


class _Bufferer:
    _escape_map = str.maketrans({
        "\"": "\\\"",
        "\\": "\\\\",
        "\t": "\\t",
        "\r": "\\r",
        "\n": "\\n",
    })
    def __init__(self):
        super().__init__()
        self._buffer = io.StringIO()

    def __str__(self):
        return self._buffer.getvalue()

    def _append(self, fmt, *args, **kwargs):
        self._buffer.write(fmt.format(*args, **kwargs))

    def attribute(self, name, value, indent=0):
        if isinstance(value, str):
            self._append("{}attribute \\{} \"{}\"\n",
                         "  " * indent, name, value.translate(self._escape_map))
        else:
            self._append("{}attribute \\{} {}\n",
                         "  " * indent, name, int(value))

    def _src(self, src):
        if src:
            self.attribute("src", src)


class _Builder(_Namer, _Bufferer):
    def module(self, name=None, attrs={}):
        name = self._make_name(name, local=False)
        return _ModuleBuilder(self, name, attrs)


class _ModuleBuilder(_Namer, _Bufferer):
    def __init__(self, rtlil, name, attrs):
        super().__init__()
        self.rtlil = rtlil
        self.name  = name
        self.attrs = {"generator": "nMigen"}
        self.attrs.update(attrs)

    def __enter__(self):
        for name, value in self.attrs.items():
            self.attribute(name, value, indent=0)
        self._append("module {}\n", self.name)
        return self

    def __exit__(self, *args):
        self._append("end\n")
        self.rtlil._buffer.write(str(self))

    def attribute(self, name, value, indent=1):
        super().attribute(name, value, indent)

    def wire(self, width, port_id=None, port_kind=None, name=None, src=""):
        self._src(src)
        name = self._make_name(name, local=False)
        if port_id is None:
            self._append("  wire width {} {}\n", width, name)
        else:
            assert port_kind in ("input", "output", "inout")
            self._append("  wire width {} {} {} {}\n", width, port_kind, port_id, name)
        return name

    def connect(self, lhs, rhs):
        self._append("  connect {} {}\n", lhs, rhs)

    def memory(self, width, size, name=None, src=""):
        self._src(src)
        name = self._make_name(name, local=False)
        self._append("  memory width {} size {} {}\n", width, size, name)
        return name

    def cell(self, kind, name=None, params={}, ports={}, src=""):
        self._src(src)
        name = self._make_name(name, local=False)
        self._append("  cell {} {}\n", kind, name)
        for param, value in params.items():
            if isinstance(value, str):
                self._append("    parameter \\{} \"{}\"\n",
                             param, value.translate(self._escape_map))
            elif isinstance(value, int):
                self._append("    parameter \\{} {:d}\n",
                             param, value)
            elif isinstance(value, ast.Const):
                self._append("    parameter \\{} {}'{:b}\n",
                             param, len(value), value.value)
            else:
                assert False
        for port, wire in ports.items():
            self._append("    connect {} {}\n", port, wire)
        self._append("  end\n")
        return name

    def process(self, name=None, src=""):
        name = self._make_name(name, local=True)
        return _ProcessBuilder(self, name, src)


class _ProcessBuilder(_Bufferer):
    def __init__(self, rtlil, name, src):
        super().__init__()
        self.rtlil = rtlil
        self.name  = name
        self.src   = src

    def __enter__(self):
        self._src(self.src)
        self._append("  process {}\n", self.name)
        return self

    def __exit__(self, *args):
        self._append("  end\n")
        self.rtlil._buffer.write(str(self))

    def case(self):
        return _CaseBuilder(self, indent=2)

    def sync(self, kind, cond=None):
        return _SyncBuilder(self, kind, cond)


class _CaseBuilder:
    def __init__(self, rtlil, indent):
        self.rtlil  = rtlil
        self.indent = indent

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def assign(self, lhs, rhs):
        self.rtlil._append("{}assign {} {}\n", "  " * self.indent, lhs, rhs)

    def switch(self, cond):
        return _SwitchBuilder(self.rtlil, cond, self.indent)


class _SwitchBuilder:
    def __init__(self, rtlil, cond, indent):
        self.rtlil  = rtlil
        self.cond   = cond
        self.indent = indent

    def __enter__(self):
        self.rtlil._append("{}switch {}\n", "  " * self.indent, self.cond)
        return self

    def __exit__(self, *args):
        self.rtlil._append("{}end\n", "  " * self.indent)

    def case(self, value=None):
        if value is None:
            self.rtlil._append("{}case\n", "  " * (self.indent + 1))
        else:
            self.rtlil._append("{}case {}'{}\n", "  " * (self.indent + 1),
                               len(value), value)
        return _CaseBuilder(self.rtlil, self.indent + 2)


class _SyncBuilder:
    def __init__(self, rtlil, kind, cond):
        self.rtlil = rtlil
        self.kind  = kind
        self.cond  = cond

    def __enter__(self):
        if self.cond is None:
            self.rtlil._append("    sync {}\n", self.kind)
        else:
            self.rtlil._append("    sync {} {}\n", self.kind, self.cond)
        return self

    def __exit__(self, *args):
        pass

    def update(self, lhs, rhs):
        self.rtlil._append("      update {} {}\n", lhs, rhs)


def src(src_loc):
    file, line = src_loc
    return "{}:{}".format(file, line)


class LegalizeValue(Exception):
    def __init__(self, value, branches):
        self.value    = value
        self.branches = list(branches)


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

        for attr_name, attr_signal in signal.attrs.items():
            self.rtlil.attribute(attr_name, attr_signal)
        wire_curr = self.rtlil.wire(width=signal.nbits, name=wire_name,
                                    port_id=port_id, port_kind=port_kind,
                                    src=src(signal.src_loc))
        if signal in self.driven:
            wire_next = self.rtlil.wire(width=signal.nbits, name="$next" + wire_curr,
                                        src=src(signal.src_loc))
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

    def on_value(self, value):
        return super().on_value(self.s.expand(value))

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

    def on_Record(self, value):
        return self(ast.Cat(value.fields.values()))

    def on_Cat(self, value):
        return "{{ {} }}".format(" ".join(reversed([self(o) for o in value.parts])))

    def _prepare_value_for_Slice(self, value):
        raise NotImplementedError # :nocov:

    def on_Slice(self, value):
        if value.start == 0 and value.end == len(value.value):
            return self(value.value)

        sigspec = self._prepare_value_for_Slice(value.value)
        if value.start == value.end:
            return "{}"
        elif value.start + 1 == value.end:
            return "{} [{}]".format(sigspec, value.start)
        else:
            return "{} [{}:{}]".format(sigspec, value.end - 1, value.start)

    def on_ArrayProxy(self, value):
        index = self.s.expand(value.index)
        if isinstance(index, ast.Const):
            if index.value < len(value.elems):
                elem = value.elems[index.value]
            else:
                elem = value.elems[-1]
            return self.match_shape(elem, *value.shape())
        else:
            raise LegalizeValue(value.index, range(len(value.elems)))


class _RHSValueCompiler(_ValueCompiler):
    operator_map = {
        (1, "~"):    "$not",
        (1, "-"):    "$neg",
        (1, "b"):    "$reduce_bool",
        (2, "+"):    "$add",
        (2, "-"):    "$sub",
        (2, "*"):    "$mul",
        (2, "/"):    "$div",
        (2, "%"):    "$mod",
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

    def on_Const(self, value):
        if isinstance(value.value, str):
            return "{}'{}".format(value.nbits, value.value)
        else:
            value_twos_compl = value.value & ((1 << value.nbits) - 1)
            return "{}'{:0{}b}".format(value.nbits, value_twos_compl, value.nbits)

    def on_AnyConst(self, value):
        if value in self.s.anys:
            return self.s.anys[value]

        res_bits, res_sign = value.shape()
        res = self.s.rtlil.wire(width=res_bits)
        self.s.rtlil.cell("$anyconst", ports={
            "\\Y": res,
        }, params={
            "WIDTH": res_bits,
        }, src=src(value.src_loc))
        self.s.anys[value] = res
        return res

    def on_AnySeq(self, value):
        if value in self.s.anys:
            return self.s.anys[value]

        res_bits, res_sign = value.shape()
        res = self.s.rtlil.wire(width=res_bits)
        self.s.rtlil.cell("$anyseq", ports={
            "\\Y": res,
        }, params={
            "WIDTH": res_bits,
        }, src=src(value.src_loc))
        self.s.anys[value] = res
        return res

    def on_Signal(self, value):
        wire_curr, wire_next = self.s.resolve(value)
        return wire_curr

    def on_Operator_unary(self, value):
        arg, = value.operands
        arg_bits, arg_sign = arg.shape()
        res_bits, res_sign = value.shape()
        res = self.s.rtlil.wire(width=res_bits)
        self.s.rtlil.cell(self.operator_map[(1, value.op)], ports={
            "\\A": self(arg),
            "\\Y": res,
        }, params={
            "A_SIGNED": arg_sign,
            "A_WIDTH": arg_bits,
            "Y_WIDTH": res_bits,
        }, src=src(value.src_loc))
        return res

    def match_shape(self, value, new_bits, new_sign):
        if isinstance(value, ast.Const):
            return self(ast.Const(value.value, (new_bits, new_sign)))

        value_bits, value_sign = value.shape()
        if new_bits <= value_bits:
            return self(ast.Slice(value, 0, new_bits))

        res = self.s.rtlil.wire(width=new_bits)
        self.s.rtlil.cell("$pos", ports={
            "\\A": self(value),
            "\\Y": res,
        }, params={
            "A_SIGNED": value_sign,
            "A_WIDTH": value_bits,
            "Y_WIDTH": new_bits,
        }, src=src(value.src_loc))
        return res

    def on_Operator_binary(self, value):
        lhs, rhs = value.operands
        lhs_bits, lhs_sign = lhs.shape()
        rhs_bits, rhs_sign = rhs.shape()
        if lhs_sign == rhs_sign:
            lhs_wire = self(lhs)
            rhs_wire = self(rhs)
        else:
            lhs_sign = rhs_sign = True
            lhs_bits = rhs_bits = max(lhs_bits, rhs_bits)
            lhs_wire = self.match_shape(lhs, lhs_bits, lhs_sign)
            rhs_wire = self.match_shape(rhs, rhs_bits, rhs_sign)
        res_bits, res_sign = value.shape()
        res = self.s.rtlil.wire(width=res_bits)
        self.s.rtlil.cell(self.operator_map[(2, value.op)], ports={
            "\\A": lhs_wire,
            "\\B": rhs_wire,
            "\\Y": res,
        }, params={
            "A_SIGNED": lhs_sign,
            "A_WIDTH": lhs_bits,
            "B_SIGNED": rhs_sign,
            "B_WIDTH": rhs_bits,
            "Y_WIDTH": res_bits,
        }, src=src(value.src_loc))
        return res

    def on_Operator_mux(self, value):
        sel, val1, val0 = value.operands
        val1_bits, val1_sign = val1.shape()
        val0_bits, val0_sign = val0.shape()
        res_bits, res_sign = value.shape()
        val1_bits = val0_bits = res_bits = max(val1_bits, val0_bits, res_bits)
        val1_wire = self.match_shape(val1, val1_bits, val1_sign)
        val0_wire = self.match_shape(val0, val0_bits, val0_sign)
        res = self.s.rtlil.wire(width=res_bits)
        self.s.rtlil.cell("$mux", ports={
            "\\A": val0_wire,
            "\\B": val1_wire,
            "\\S": self(sel),
            "\\Y": res,
        }, params={
            "WIDTH": res_bits
        }, src=src(value.src_loc))
        return res

    def on_Operator(self, value):
        if len(value.operands) == 1:
            return self.on_Operator_unary(value)
        elif len(value.operands) == 2:
            return self.on_Operator_binary(value)
        elif len(value.operands) == 3:
            assert value.op == "m"
            return self.on_Operator_mux(value)
        else:
            raise TypeError # :nocov:

    def _prepare_value_for_Slice(self, value):
        if isinstance(value, (ast.Signal, ast.Slice, ast.Cat)):
            sigspec = self(value)
        else:
            sigspec = self.s.rtlil.wire(len(value))
            self.s.rtlil.connect(sigspec, self(value))
        return sigspec

    def on_Part(self, value):
        lhs, rhs = value.value, value.offset
        lhs_bits, lhs_sign = lhs.shape()
        rhs_bits, rhs_sign = rhs.shape()
        res_bits, res_sign = value.shape()
        res = self.s.rtlil.wire(width=res_bits)
        # Note: Verilog's x[o+:w] construct produces a $shiftx cell, not a $shift cell.
        # However, Migen's semantics defines the out-of-range bits to be zero, so it is correct
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
        }, src=src(value.src_loc))
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
        assert value.shape() == (new_bits, new_sign)
        return self(value)

    def on_Signal(self, value):
        wire_curr, wire_next = self.s.resolve(value)
        if wire_next is None:
            raise ValueError("No LHS wire for non-driven signal {}".format(repr(value)))
        return wire_next

    def _prepare_value_for_Slice(self, value):
        assert isinstance(value, (ast.Signal, ast.Slice, ast.Cat))
        return self(value)

    def on_Part(self, value):
        offset = self.s.expand(value.offset)
        if isinstance(offset, ast.Const):
            return self(ast.Slice(value.value, offset.value, offset.value + value.width))
        else:
            raise LegalizeValue(value.offset, range((1 << len(value.offset)) - 1))

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

    @contextmanager
    def case(self, switch, value):
        try:
            old_case = self._case
            with switch.case(value) as self._case:
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
        self._case.assign(self.lhs_compiler(stmt.lhs), rhs_sigspec)

    def on_Assert(self, stmt):
        self(stmt._check.eq(stmt.test))
        self(stmt._en.eq(1))

        en_wire = self.rhs_compiler(stmt._en)
        check_wire = self.rhs_compiler(stmt._check)
        self.state.rtlil.cell("$assert", ports={
            "\\A": check_wire,
            "\\EN": en_wire,
        }, src=src(stmt.src_loc))

    def on_Assume(self, stmt):
        self(stmt._check.eq(stmt.test))
        self(stmt._en.eq(1))

        en_wire = self.rhs_compiler(stmt._en)
        check_wire = self.rhs_compiler(stmt._check)
        self.state.rtlil.cell("$assume", ports={
            "\\A": check_wire,
            "\\EN": en_wire,
        }, src=src(stmt.src_loc))

    def on_Switch(self, stmt):
        self._check_rhs(stmt.test)

        if stmt not in self._test_cache:
            self._test_cache[stmt] = self.rhs_compiler(stmt.test)
        test_sigspec = self._test_cache[stmt]

        with self._case.switch(test_sigspec) as switch:
            for value, stmts in stmt.cases.items():
                with self.case(switch, value):
                    self.on_statements(stmts)

    def on_statement(self, stmt):
        try:
            super().on_statement(stmt)
        except LegalizeValue as legalize:
            with self._case.switch(self.rhs_compiler(legalize.value)) as switch:
                bits, sign = legalize.value.shape()
                tests = ["{:0{}b}".format(v, bits) for v in legalize.branches]
                tests[-1] = "-" * bits
                for branch, test in zip(legalize.branches, tests):
                    with self.case(switch, test):
                        branch_value = ast.Const(branch, (bits, sign))
                        with self.state.expand_to(legalize.value, branch_value):
                            super().on_statement(stmt)

    def on_statements(self, stmts):
        for stmt in stmts:
            self.on_statement(stmt)


def convert_fragment(builder, fragment, name, top):
    if isinstance(fragment, ir.Instance):
        port_map = OrderedDict()
        for port_name, value in fragment.named_ports.items():
            port_map["\\{}".format(port_name)] = value

        if fragment.type[0] == "$":
            return fragment.type, port_map
        else:
            return "\\{}".format(fragment.type), port_map

    with builder.module(name or "anonymous", attrs={"top": 1} if top else {}) as module:
        compiler_state = _ValueCompilerState(module)
        rhs_compiler   = _RHSValueCompiler(compiler_state)
        lhs_compiler   = _LHSValueCompiler(compiler_state)
        stmt_compiler  = _StatementCompiler(compiler_state, rhs_compiler, lhs_compiler)

        verilog_trigger = None
        verilog_trigger_sync_emitted = False

        # Register all signals driven in the current fragment. This must be done first, as it
        # affects further codegen; e.g. whether $next\sig signals will be generated and used.
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
            if not subfragment.ports:
                continue

            sub_params = OrderedDict()
            if hasattr(subfragment, "parameters"):
                for param_name, param_value in subfragment.parameters.items():
                    if isinstance(param_value, mem.Memory):
                        memory = param_value
                        if memory not in memories:
                            memories[memory] = module.memory(width=memory.width, size=memory.depth,
                                                             name=memory.name)
                            addr_bits = bits_for(memory.depth)
                            data_parts = []
                            for addr in range(memory.depth):
                                if addr < len(memory.init):
                                    data = memory.init[addr]
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
                convert_fragment(builder, subfragment, top=False, name=sub_name)

            sub_ports = OrderedDict()
            for port, value in sub_port_map.items():
                for signal in value._rhs_signals():
                    compiler_state.resolve_curr(signal, prefix=sub_name)
                sub_ports[port] = rhs_compiler(value)

            module.cell(sub_type, name=sub_name, ports=sub_ports, params=sub_params)

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

            with module.process(name="$group_{}".format(group)) as process:
                with process.case() as case:
                    # For every signal in comb domain, assign $next\sig to the reset value.
                    # For every signal in sync domains, assign $next\sig to the current
                    # value (\sig).
                    for domain, signal in fragment.iter_drivers():
                        if signal not in group_signals:
                            continue
                        if domain is None:
                            prev_value = ast.Const(signal.reset, signal.nbits)
                        else:
                            prev_value = signal
                        case.assign(lhs_compiler(signal), rhs_compiler(prev_value))

                    # Convert statements into decision trees.
                    stmt_compiler._case = case
                    stmt_compiler._has_rhs = False
                    stmt_compiler(lhs_group_filter(fragment.statements))

                    # Verilog `always @*` blocks will not run if `*` does not match anything, i.e.
                    # if the implicit sensitivity list is empty. We check this while translating,
                    # by looking for any signals on RHS. If there aren't any, we add some logic
                    # whose only purpose is to trigger Verilog simulators when it converts
                    # through RTLIL and to Verilog, by populating the sensitivity list.
                    if not stmt_compiler._has_rhs:
                        if verilog_trigger is None:
                            verilog_trigger = \
                                module.wire(1, name="$verilog_initial_trigger")
                        case.assign(verilog_trigger, verilog_trigger)

                # For every signal in the sync domain, assign \sig's initial value (which will
                # end up as the \init reg attribute) to the reset value.
                with process.sync("init") as sync:
                    for domain, signal in fragment.iter_sync():
                        if signal not in group_signals:
                            continue
                        wire_curr, wire_next = compiler_state.resolve(signal)
                        sync.update(wire_curr, rhs_compiler(ast.Const(signal.reset, signal.nbits)))

                    # The Verilog simulator trigger needs to change at time 0, so if we haven't
                    # yet done that in some process, do it.
                    if verilog_trigger and not verilog_trigger_sync_emitted:
                        sync.update(verilog_trigger, "1'0")
                        verilog_trigger_sync_emitted = True

                # For every signal in every domain, assign \sig to $next\sig. The sensitivity list,
                # however, differs between domains: for comb domains, it is `always`, for sync
                # domains with sync reset, it is `posedge clk`, for sync domains with async reset
                # it is `posedge clk or posedge rst`.
                for domain, signals in fragment.drivers.items():
                    signals = signals & group_signals
                    if not signals:
                        continue

                    triggers = []
                    if domain is None:
                        triggers.append(("always",))
                    else:
                        cd = fragment.domains[domain]
                        triggers.append(("posedge", compiler_state.resolve_curr(cd.clk)))
                        if cd.async_reset:
                            triggers.append(("posedge", compiler_state.resolve_curr(cd.rst)))

                    for trigger in triggers:
                        with process.sync(*trigger) as sync:
                            for signal in signals:
                                wire_curr, wire_next = compiler_state.resolve(signal)
                                sync.update(wire_curr, wire_next)

    # Finally, collect the names we've given to our ports in RTLIL, and correlate these with
    # the signals represented by these ports. If we are a submodule, this will be necessary
    # to create a cell for us in the parent module.
    port_map = OrderedDict()
    for signal in fragment.ports:
        port_map[compiler_state.resolve_curr(signal)] = signal

    return module.name, port_map


def convert(fragment, name="top", **kwargs):
    fragment = ir.Fragment.get(fragment, platform=None).prepare(**kwargs)
    builder = _Builder()
    convert_fragment(builder, fragment, name=name, top=True)
    return str(builder)

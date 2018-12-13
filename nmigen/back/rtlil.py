import io
import textwrap
from collections import defaultdict, OrderedDict
from contextlib import contextmanager

from ..fhdl import ast, ir, xfrm


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
    def __init__(self):
        super().__init__()
        self._buffer = io.StringIO()

    def __str__(self):
        return self._buffer.getvalue()

    def _append(self, fmt, *args, **kwargs):
        self._buffer.write(fmt.format(*args, **kwargs))

    def _src(self, src):
        if src:
            self._append("  attribute \\src {}", repr(src))


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
            if isinstance(value, str):
                self._append("attribute \\{} \"{}\"\n", name, value.replace("\"", "\\\""))
            else:
                self._append("attribute \\{} {}\n", name, int(value))
        self._append("module {}\n", self.name)
        return self

    def __exit__(self, *args):
        self._append("end\n")
        self.rtlil._buffer.write(str(self))

    def attribute(self, name, value):
        if isinstance(value, str):
            self._append("attribute \\{} \"{}\"\n", name, value.replace("\"", "\\\""))
        else:
            self._append("attribute \\{} {}\n", name, int(value))

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

    def cell(self, kind, name=None, params={}, ports={}, src=""):
        self._src(src)
        name = self._make_name(name, local=True)
        self._append("  cell {} {}\n", kind, name)
        for param, value in params.items():
            if isinstance(value, str):
                value = repr(value)
            else:
                value = int(value)
            self._append("    parameter \\{} {}\n", param, value)
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


class _ValueTransformer(xfrm.ValueTransformer):
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
        (2, "<<<"):  "$sshl",
        (2, ">>>"):  "$sshr",
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

    def __init__(self, rtlil):
        self.rtlil  = rtlil
        self.wires  = ast.ValueDict()
        self.driven = ast.ValueDict()
        self.ports  = ast.ValueDict()
        self.is_lhs   = False
        self.sub_name = None

    def add_driven(self, signal, sync):
        self.driven[signal] = sync

    def add_port(self, signal, kind=None):
        if signal in self.driven:
            self.ports[signal] = (len(self.ports), "output")
        else:
            self.ports[signal] = (len(self.ports), "input")

    @contextmanager
    def lhs(self):
        try:
            self.is_lhs = True
            yield
        finally:
            self.is_lhs = False

    @contextmanager
    def hierarchy(self, sub_name):
        try:
            self.sub_name = sub_name
            yield
        finally:
            self.sub_name = None

    def on_unknown(self, node):
        if node is None:
            return None
        else:
            super().visit_unknown(node)

    def on_Const(self, node):
        if isinstance(node.value, str):
            return "{}'{}".format(node.nbits, node.value)
        else:
            return "{}'{:b}".format(node.nbits, node.value)

    def on_Signal(self, node):
        if node in self.wires:
            wire_curr, wire_next = self.wires[node]
        else:
            if node in self.ports:
                port_id, port_kind = self.ports[node]
            else:
                port_id = port_kind = None
            if self.sub_name:
                wire_name = "{}_{}".format(self.sub_name, node.name)
            else:
                wire_name = node.name
            for attr_name, attr_value in node.attrs.items():
                self.rtlil.attribute(attr_name, attr_value)
            wire_curr = self.rtlil.wire(width=node.nbits, name=wire_name,
                                        port_id=port_id, port_kind=port_kind)
            if node in self.driven:
                wire_next = self.rtlil.wire(width=node.nbits, name=wire_curr + "$next")
            else:
                wire_next = None
            self.wires[node] = (wire_curr, wire_next)

        if self.is_lhs:
            if wire_next is None:
                raise ValueError("Cannot return lhs for non-driven signal {}".format(repr(node)))
            return wire_next
        else:
            return wire_curr

    def on_Operator_unary(self, node):
        arg, = node.operands
        arg_bits, arg_sign = arg.shape()
        res_bits, res_sign = node.shape()
        res = self.rtlil.wire(width=res_bits)
        self.rtlil.cell(self.operator_map[(1, node.op)], ports={
            "\\A": self(arg),
            "\\Y": res,
        }, params={
            "A_SIGNED": arg_sign,
            "A_WIDTH": arg_bits,
            "Y_WIDTH": res_bits,
        })
        return res

    def match_shape(self, node, new_bits, new_sign):
        if isinstance(node, ast.Const):
            return self(ast.Const(node.value, (new_bits, new_sign)))

        node_bits, node_sign = node.shape()
        if new_bits > node_bits:
            res = self.rtlil.wire(width=new_bits)
            self.rtlil.cell("$pos", ports={
                "\\A": self(node),
                "\\Y": res,
            }, params={
                "A_SIGNED": node_sign,
                "A_WIDTH": node_bits,
                "Y_WIDTH": new_bits,
            })
            return res
        else:
            return "{} [{}:0]".format(self(node), new_bits - 1)

    def on_Operator_binary(self, node):
        lhs, rhs = node.operands
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
        res_bits, res_sign = node.shape()
        res = self.rtlil.wire(width=res_bits)
        self.rtlil.cell(self.operator_map[(2, node.op)], ports={
            "\\A": lhs_wire,
            "\\B": rhs_wire,
            "\\Y": res,
        }, params={
            "A_SIGNED": lhs_sign,
            "A_WIDTH": lhs_bits,
            "B_SIGNED": rhs_sign,
            "B_WIDTH": rhs_bits,
            "Y_WIDTH": res_bits,
        })
        return res

    def on_Operator_mux(self, node):
        sel, lhs, rhs = node.operands
        lhs_bits, lhs_sign = lhs.shape()
        rhs_bits, rhs_sign = rhs.shape()
        res_bits, res_sign = node.shape()
        lhs_bits = rhs_bits = res_bits = max(lhs_bits, rhs_bits, res_bits)
        lhs_wire = self.match_shape(lhs, lhs_bits, lhs_sign)
        rhs_wire = self.match_shape(rhs, rhs_bits, rhs_sign)
        res = self.rtlil.wire(width=res_bits)
        self.rtlil.cell("$mux", ports={
            "\\A": lhs_wire,
            "\\B": rhs_wire,
            "\\S": self(sel),
            "\\Y": res,
        }, params={
            "WIDTH": res_bits
        })
        return res

    def on_Operator(self, node):
        if len(node.operands) == 1:
            return self.on_Operator_unary(node)
        elif len(node.operands) == 2:
            return self.on_Operator_binary(node)
        elif len(node.operands) == 3:
            assert node.op == "m"
            return self.on_Operator_mux(node)
        else:
            raise TypeError

    def on_Slice(self, node):
        if node.end == node.start + 1:
            return "{} [{}]".format(self(node.value), node.start)
        else:
            return "{} [{}:{}]".format(self(node.value), node.end - 1, node.start)

    # def on_Part(self, node):
    #     return _Part(self(node.value), self(node.offset), node.width)

    def on_Cat(self, node):
        return "{{ {} }}".format(" ".join(reversed([self(o) for o in node.operands])))

    def on_Repl(self, node):
        return "{{ {} }}".format(" ".join(self(node.value) for _ in range(node.count)))


def convert_fragment(builder, fragment, name, top, clock_domains):
    with builder.module(name, attrs={"top": 1} if top else {}) as module:
        xformer = _ValueTransformer(module)

        # Register all signals driven in the current fragment. This must be done first, as it
        # affects further codegen; e.g. whether sig$next signals will be generated and used.
        for cd_name, signal in fragment.iter_drivers():
            xformer.add_driven(signal, sync=cd_name is not None)

        # Register all signals used as ports in the current fragment. The wires are lazily
        # generated, so registering ports eagerly ensures they get correct direction qualifiers.
        for signal in fragment.ports:
            xformer.add_port(signal)

        # Transform all clocks clocks and resets eagerly and outside of any hierarchy, to make
        # sure they get sensible (non-prefixed) names. This does not affect semantics.
        for cd_name, _ in fragment.iter_sync():
            cd = clock_domains[cd_name]
            xformer(cd.clk)
            xformer(cd.reset)

        # Transform all subfragments to their respective cells. Transforming signals connected
        # to their ports into wires eagerly makes sure they get sensible (prefixed with submodule
        # name) names.
        for subfragment, sub_name in fragment.subfragments:
            sub_name, sub_port_map = \
                convert_fragment(builder, subfragment, top=False, name=sub_name,
                                 clock_domains=clock_domains)
            with xformer.hierarchy(sub_name):
                module.cell(sub_name, name=sub_name, ports={
                    p: xformer(s) for p, s in sub_port_map.items()
                })

        with module.process() as process:
            with process.case() as case:
                # For every signal in comb domain, assign \sig$next to the reset value.
                # For every signal in sync domains, assign \sig$next to the current value (\sig).
                for cd_name, signal in fragment.iter_drivers():
                    if cd_name is None:
                        prev_value = xformer(ast.Const(signal.reset, signal.nbits))
                    else:
                        prev_value = xformer(signal)
                    with xformer.lhs():
                        case.assign(xformer(signal), prev_value)

                # Convert statements into decision trees.
                def _convert_stmts(case, stmts):
                    for stmt in stmts:
                        if isinstance(stmt, ast.Assign):
                            lhs_bits, lhs_sign = stmt.lhs.shape()
                            rhs_bits, rhs_sign = stmt.rhs.shape()
                            if lhs_bits == rhs_bits:
                                rhs_sigspec = xformer(stmt.rhs)
                            else:
                                # In RTLIL, LHS and RHS of assignment must have exactly same width.
                                rhs_sigspec = xformer.match_shape(
                                    stmt.rhs, lhs_bits, rhs_sign)
                            with xformer.lhs():
                                lhs_sigspec = xformer(stmt.lhs)
                            case.assign(lhs_sigspec, rhs_sigspec)

                        elif isinstance(stmt, ast.Switch):
                            with case.switch(xformer(stmt.test)) as switch:
                                for value, nested_stmts in stmt.cases.items():
                                    with switch.case(value) as nested_case:
                                        _convert_stmts(nested_case, nested_stmts)

                        else:
                            raise TypeError

                _convert_stmts(case, fragment.statements)

            # For every signal in the sync domain, assign \sig's initial value (which will end up
            # as the \init reg attribute) to the reset value. Note that this assigns \sig,
            # not \sig$next.
            with process.sync("init") as sync:
                for cd_name, signal in fragment.iter_sync():
                    sync.update(xformer(signal),
                                xformer(ast.Const(signal.reset, signal.nbits)))

            # For every signal in every domain, assign \sig to \sig$next. The sensitivity list,
            # however, differs between domains: for comb domains, it is `always`, for sync domains
            # with sync reset, it is `posedge clk`, for sync domains with async rest it is
            # `posedge clk or posedge rst`.
            for cd_name, signals in fragment.iter_domains():
                triggers = []
                if cd_name is None:
                    triggers.append(("always",))
                elif cd_name in clock_domains:
                    cd = clock_domains[cd_name]
                    triggers.append(("posedge", xformer(cd.clk)))
                    if cd.async_reset:
                        triggers.append(("posedge", xformer(cd.reset)))
                else:
                    raise ValueError("Clock domain {} not found in design".format(cd_name))

                for trigger in triggers:
                    with process.sync(*trigger) as sync:
                        for signal in signals:
                            rhs_sigspec = xformer(signal)
                            with xformer.lhs():
                                sync.update(xformer(signal), rhs_sigspec)

    # Finally, collect the names we've given to our ports in RTLIL, and correlate these with
    # the signals represented by these ports. If we are a submodule, this will be necessary
    # to create a cell for us in the parent module.
    port_map = OrderedDict()
    for signal in fragment.ports:
        port_map[xformer(signal)] = signal

    return module.name, port_map


def convert(fragment, ports=[], clock_domains={}):
    fragment = xfrm.ResetInserter({
        cd.name: cd.reset for cd in clock_domains.values() if cd.reset is not None
    })(fragment)

    ins, outs = fragment._propagate_ports(ports, clock_domains)

    builder = _Builder()
    convert_fragment(builder, fragment, name="top", top=True, clock_domains=clock_domains)
    return str(builder)

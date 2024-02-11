from typing import Iterable
import io

from ..utils import bits_for
from ..lib import wiring
from ..hdl import _repr, _ast, _ir, _nir


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
    elif isinstance(value, _ast.Const):
        return value.signed
    else:
        assert False, f"Invalid constant {value!r}"


def _const(value):
    if isinstance(value, str):
        return f"\"{value.translate(_escape_map)}\""
    elif isinstance(value, int):
        if value in range(0, 2**31-1):
            return f"{value:d}"
        else:
            # This code path is only used for Instances, where Verilog-like behavior is desirable.
            # Verilog ensures that integers with unspecified width are 32 bits wide or more.
            width = max(32, bits_for(value))
            return _const(_ast.Const(value, width))
    elif isinstance(value, _ast.Const):
        value_twos_compl = value.value & ((1 << value.width) - 1)
        return "{}'{:0{}b}".format(value.width, value_twos_compl, value.width)
    else:
        assert False, f"Invalid constant {value!r}"


class _Namer:
    def __init__(self):
        super().__init__()
        self._anon  = 0
        self._index = 0
        self._names = set()

    def anonymous(self):
        name = f"U$${self._anon}"
        assert name not in self._names
        self._anon += 1
        return name

    def _make_name(self, name, local):
        if name is None:
            self._index += 1
            name = f"${self._index}"
        elif not local and name[0] not in "\\$":
            name = f"\\{name}"
        while name in self._names:
            self._index += 1
            name = f"{name}${self._index}"
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

    def module(self, name=None, attrs={}, *, src=None):
        name = self._make_name(name, local=False)
        return _ModuleBuilder(self, name, attrs, src=src)


class _ModuleBuilder(_AttrBuilder, _BufferedBuilder, _Namer):
    def __init__(self, rtlil, name, attrs, *, src=None):
        super().__init__(emit_src=rtlil.emit_src)
        self.rtlil = rtlil
        self.name  = name
        self.src   = src
        self.attrs = {"generator": "Amaranth"}
        self.attrs.update(attrs)

    def __enter__(self):
        self._attributes(self.attrs, src=self.src)
        self._append("module {}\n", self.name)
        return self

    def __exit__(self, *args):
        self._append("end\n")
        self.rtlil._buffer.write(str(self))

    def wire(self, width, port_id=None, port_kind=None, name=None, attrs={}, src="", signed=False):
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
        signed = " signed" if signed else ""
        if port_id is None:
            self._append("  wire width {}{} {}\n", width, signed, name)
        else:
            assert port_kind in ("input", "output", "inout")
            # By convention, Yosys ports named $\d+ are positional, so there is no way to use
            # a port with such a name. See amaranth-lang/amaranth#733.
            assert port_id is not None
            self._append("  wire width {} {} {}{} {}\n", width, port_kind, port_id, signed, name)
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
            self._append("    connect \\{} {}\n", port, wire)
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


class _CaseBuilder:
    def __init__(self, rtlil, indent):
        self.rtlil  = rtlil
        self.indent = indent

    def _append(self, *args, **kwargs):
        self.rtlil._append(*args, **kwargs)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def assign(self, lhs, rhs):
        self._append("{}assign {} {}\n", "  " * self.indent, lhs, rhs)

    def switch(self, cond, attrs={}, src=""):
        return _SwitchBuilder(self.rtlil, cond, attrs, src, self.indent)


class _SwitchBuilder(_AttrBuilder):
    def __init__(self, rtlil, cond, attrs, src, indent):
        super().__init__(emit_src=rtlil.emit_src)
        self.rtlil  = rtlil
        self.cond   = cond
        self.attrs  = attrs
        self.src    = src
        self.indent = indent

    def _append(self, *args, **kwargs):
        self.rtlil._append(*args, **kwargs)

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
                         ", ".join(f"{len(value)}'{value}" for value in values))
        return _CaseBuilder(self.rtlil, self.indent + 2)


def _src(src_loc):
    if src_loc is None:
        return None
    file, line = src_loc
    return f"{file}:{line}"


class MemoryInfo:
    def __init__(self, memid):
        self.memid = memid
        self.num_write_ports = 0
        self.write_port_ids = {}


class ModuleEmitter:
    def __init__(self, builder, netlist, module, name_map, empty_checker):
        self.builder = builder
        self.netlist = netlist
        self.module = module
        self.name_map = name_map
        self.empty_checker = empty_checker

        # Internal state of the emitter. This conceptually consists of three parts:
        # (1) memory information;
        # (2) name and attribute preferences for wires corresponding to signals;
        # (3) mapping of Amaranth netlist entities to RTLIL netlist entities.
        # Value names are preferences: they are candidate names for values that may or may not get
        # used for cell outputs. Attributes are mandatory: they are always emitted, but can be
        # squashed if several signals end up aliasing the same driven wire.
        self.memories = {} # cell idx -> MemoryInfo
        self.value_names = {} # value -> signal or port name
        self.value_attrs = {} # value -> dict
        self.sigport_wires = {} # signal or port name -> (wire, value)
        self.driven_sigports = set() # set of signal or port name
        self.nets = {} # net -> (wire name, bit idx)
        self.cell_wires = {} # cell idx -> wire name
        self.instance_wires = {} # (cell idx, output name) -> wire name

    def emit(self):
        self.collect_memory_info()
        self.assign_value_names()
        self.collect_init_attrs()
        self.emit_signal_wires()
        self.emit_port_wires()
        self.emit_cell_wires()
        self.emit_submodule_wires()
        self.emit_connects()
        self.emit_submodules()
        self.emit_cells()

    def collect_memory_info(self):
        for cell_idx in self.module.cells:
            cell = self.netlist.cells[cell_idx]
            if isinstance(cell, _nir.Memory):
                self.memories[cell_idx] = MemoryInfo(
                    self.builder.memory(cell.width, cell.depth, name=cell.name,
                                       attrs=cell.attributes, src=_src(cell.src_loc)))

        for cell_idx in self.module.cells:
            cell = self.netlist.cells[cell_idx]
            if isinstance(cell, _nir.SyncWritePort):
                memory_info = self.memories[cell.memory]
                memory_info.write_port_ids[cell_idx] = memory_info.num_write_ports
                memory_info.num_write_ports += 1

    def assign_value_names(self):
        for signal, name in self.module.signal_names.items():
            value = self.netlist.signals[signal]
            if value not in self.value_names:
                self.value_names[value] = name

    def collect_init_attrs(self):
        # Flip-flops are special in Yosys; the initial value is stored not as a cell parameter but
        # as an attribute of a wire connected to the output of the flip-flop. The claimed benefit
        # of this arrangement is that fine cells, which cannot have parameters (so that certain
        # backends, like BLIF, which cannot represent parameters--or attributes--can be used to
        # emit these cells), then do not need to have 3x more variants (one for initialized to 0,
        # one for 1, one for X).
        #
        # At the time of writing, 2024-02-11, Yosys has 125 (one hundred twenty five) fine FF cells,
        # which are generated by a Python script because they have gotten completely out of hand
        # long ago and no one could keep track of them manually. This list features such beauties
        # as $_DFFSRE_PPPN_ and its other 7 cousins.
        #
        # These are real cells, used by real Yosys developers! Look at what they have done for us,
        # with all the subtly unsynthesizable Verilog we sent them and all of the incompatibilities
        # with vendor toolchains we reported!
        #
        # Nothing is fine about these cells. The decision to have `init` as a wire attribute is
        # quite possibly the single worst design decision in Yosys, and not having to dealing with
        # that bullshit again is enough of a reason to implement an FPGA toolchain from scratch.
        #
        # Just have 375 fine cells, bro. Trust me bro. You will certainly not regret having 375
        # fine cells in your toolchain. Or at least you will be able to process netlists without
        # having to special-case this one godforsaken attribute every time you look at a wire.
        #
        # -- @whitequark
        for cell_idx in self.module.cells:
            cell = self.netlist.cells[cell_idx]
            if isinstance(cell, _nir.FlipFlop):
                width = len(cell.data)
                attrs = {"init": _ast.Const(cell.init, width), **cell.attributes}
                value = _nir.Value(_nir.Net.from_cell(cell_idx, bit) for bit in range(width))
                self.value_attrs[value] = attrs

    def emit_signal_wires(self):
        for signal, name in self.module.signal_names.items():
            value = self.netlist.signals[signal]

            # One of: (1) empty and created here, (2) `init` filled in by `collect_init_attrs`,
            # (3) populated by some other signal aliasing the same nets. In the last case, we will
            # glue attributes for these signals together, but synthesizers (including Yosys, when
            # the design is flattened) will do that anyway, so it doesn't matter.
            attrs = self.value_attrs.setdefault(value, {})
            attrs.update(signal.attrs)

            for repr in signal._value_repr:
                if repr.path == () and isinstance(repr.format, _repr.FormatEnum):
                    enum = repr.format.enum
                    attrs["enum_base_type"] = enum.__name__
                    for enum_value in enum:
                        attrs["enum_value_{:0{}b}".format(enum_value.value, signal.width)] = enum_value.name

            if name in self.module.ports:
                port_value, _flow = self.module.ports[name]
                assert value == port_value
                self.name_map[signal] = (*self.module.name, f"\\{name}")
            else:
                wire = self.builder.wire(width=signal.width, signed=signal.signed,
                                         name=name, attrs=attrs,
                                         src=_src(signal.src_loc))
                self.sigport_wires[name] = (wire, value)
                self.name_map[signal] = (*self.module.name, wire)

    def emit_port_wires(self):
        named_signals = {name: signal for signal, name in self.module.signal_names.items()}
        for port_id, (name, (value, flow)) in enumerate(self.module.ports.items()):
            signed = False
            if name in named_signals:
                signed = named_signals[name].signed
            wire = self.builder.wire(width=len(value), signed=signed,
                                     port_id=port_id, port_kind=flow.value,
                                     name=name, attrs=self.value_attrs.get(value, {}))
            self.sigport_wires[name] = (wire, value)
            if flow == _nir.ModuleNetFlow.Output:
                continue
            # If we just emitted an input or inout port, it is driving the value.
            self.driven_sigports.add(name)
            for bit, net in enumerate(value):
                self.nets[net] = (wire, bit)

    def emit_driven_wire(self, value):
        # Emits a wire for a value, in preparation for driving it.
        if value in self.value_names:
            # If there is a signal or port matching this value, reuse its wire as the canonical
            # wire of the nets involved.
            name = self.value_names[value]
            wire, named_value = self.sigport_wires[name]
            assert value == named_value, \
                f"Inconsistent values {value!r}, {named_value!r} for wire {name!r}"
            self.driven_sigports.add(name)
        else:
            # Otherwise, make an anonymous wire.
            wire = self.builder.wire(len(value), attrs=self.value_attrs.get(value, {}))
        for bit, net in enumerate(value):
            self.nets[net] = (wire, bit)
        return wire

    def emit_cell_wires(self):
        for cell_idx in self.module.cells:
            cell = self.netlist.cells[cell_idx]
            if isinstance(cell, _nir.Top):
                continue
            elif isinstance(cell, _nir.Instance):
                for name, (start, width) in cell.ports_o.items():
                    nets = [_nir.Net.from_cell(cell_idx, start + bit) for bit in range(width)]
                    wire = self.emit_driven_wire(_nir.Value(nets))
                    self.instance_wires[cell_idx, name] = wire
                continue # Instances use one wire per output, not per cell.
            elif isinstance(cell, (_nir.PriorityMatch, _nir.Matches)):
                continue # Inlined into assignment lists.
            elif isinstance(cell, (_nir.SyncProperty, _nir.AsyncProperty, _nir.Memory,
                                   _nir.SyncWritePort)):
                continue # No outputs.
            elif isinstance(cell, _nir.AssignmentList):
                width = len(cell.default)
            elif isinstance(cell, (_nir.Operator, _nir.Part, _nir.ArrayMux, _nir.AnyValue,
                                   _nir.SyncReadPort, _nir.AsyncReadPort)):
                width = cell.width
            elif isinstance(cell, _nir.FlipFlop):
                width = len(cell.data)
            elif isinstance(cell, _nir.Initial):
                width = 1
            elif isinstance(cell, _nir.IOBuffer):
                width = len(cell.pad)
            else:
                assert False # :nocov:
            # Single output cell connected to a wire.
            nets = [_nir.Net.from_cell(cell_idx, bit) for bit in range(width)]
            wire = self.emit_driven_wire(_nir.Value(nets))
            self.cell_wires[cell_idx] = wire

    def emit_submodule_wires(self):
        for submodule_idx in self.module.submodules:
            submodule = self.netlist.modules[submodule_idx]
            for _name, (value, flow) in submodule.ports.items():
                if flow == _nir.ModuleNetFlow.Output:
                    self.emit_driven_wire(value)

    def sigspec(self, *parts: '_nir.Net | Iterable[_nir.Net]'):
        value = _nir.Value()
        for part in parts:
            value += _nir.Value(part)

        chunks = []
        begin_pos = 0
        while begin_pos < len(value):
            end_pos = begin_pos
            if value[begin_pos].is_const:
                while end_pos < len(value) and value[end_pos].is_const:
                    end_pos += 1
                width = end_pos - begin_pos
                bits = "".join(str(net.const) for net in value[begin_pos:end_pos])
                chunks.append(f"{width}'{bits[::-1]}")
            else:
                wire, start_bit = self.nets[value[begin_pos]]
                bit = start_bit
                while (end_pos < len(value) and
                        not value[end_pos].is_const and
                        self.nets[value[end_pos]] == (wire, bit)):
                    end_pos += 1
                    bit += 1
                width = end_pos - begin_pos
                if width == 1:
                    chunks.append(f"{wire} [{start_bit}]")
                else:
                    chunks.append(f"{wire} [{start_bit + width - 1}:{start_bit}]")
            begin_pos = end_pos

        if len(chunks) == 1:
            return chunks[0]
        return "{ " + " ".join(reversed(chunks)) + " }"

    def emit_connects(self):
        for name, (wire, value) in self.sigport_wires.items():
            if name not in self.driven_sigports:
                self.builder.connect(wire, self.sigspec(value))

    def emit_submodules(self):
        for submodule_idx in self.module.submodules:
            submodule = self.netlist.modules[submodule_idx]
            if not self.empty_checker.is_empty(submodule_idx):
                dotted_name = ".".join(submodule.name)
                self.builder.cell(f"\\{dotted_name}", submodule.name[-1], ports={
                    name: self.sigspec(value)
                    for name, (value, _flow) in submodule.ports.items()
                }, src=_src(submodule.cell_src_loc))

    def emit_assignment_list(self, cell_idx, cell):
        def emit_assignments(case, cond):
            # Emits assignments from the assignment list into the given case.
            # ``cond`` is the net which is the condition for ``case`` being active.
            # Returns once it hits an assignment whose condition is not nested within ``cond``,
            # letting parent invocation take care of the remaining assignments.
            nonlocal pos

            emitted_switch = False
            while pos < len(cell.assignments):
                assign = cell.assignments[pos]
                if assign.cond == cond and not emitted_switch:
                    # Not nested, and we didn't emit a switch yet, so emit the assignment.
                    case.assign(self.sigspec(lhs[assign.start:assign.start + len(assign.value)]),
                                self.sigspec(assign.value))
                    pos += 1
                elif assign.cond == cond:
                    # Not nested, but we emitted a subswitch. Wrap the assignments in a dummy
                    # switch. This is necessary because Yosys executes all assignments before all
                    # subswitches (but allows you to mix asssignments and switches in RTLIL, for
                    # maximum confusion).
                    with case.switch("{ }") as switch:
                        with switch.case("") as subcase:
                            while pos < len(cell.assignments):
                                assign = cell.assignments[pos]
                                if assign.cond == cond:
                                    subcase.assign(self.sigspec(lhs[assign.start:assign.start +
                                                                    len(assign.value)]),
                                                   self.sigspec(assign.value))
                                    pos += 1
                                else:
                                    break
                else:
                    # Condition doesn't match this case's condition — either we encountered
                    # a nested condition, or we should break out.  Try to find out exactly
                    # how we are nested.
                    search_cond = assign.cond
                    while True:
                        if search_cond == cond:
                            # We have found the PriorityMatch cell that we should enter.
                            break
                        if search_cond == _nir.Net.from_const(1):
                            # If this isn't nested condition, go back to parent invocation.
                            return
                        # Grab the PriorityMatch cell that is on the next level of nesting.
                        priority_cell_idx = search_cond.cell
                        priority_cell = self.netlist.cells[priority_cell_idx]
                        assert isinstance(priority_cell, _nir.PriorityMatch)
                        search_cond = priority_cell.en
                    # We assume that:
                    # 1. PriorityMatch inputs can only be Match cell outputs, or constant 1.
                    # 2. All Match cells driving a given PriorityMatch cell test the same value.
                    # Grab the tested value from a random Match cell.
                    test = _nir.Value()
                    for net in priority_cell.inputs:
                        if net != _nir.Net.from_const(1):
                            matches_cell = self.netlist.cells[net.cell]
                            assert isinstance(matches_cell, _nir.Matches)
                            test = matches_cell.value
                            break
                    # Now emit cases for all PriorityMatch inputs, in sequence. Consume as many
                    # assignments as possible along the way.
                    with case.switch(self.sigspec(test)) as switch:
                        for bit, net in enumerate(priority_cell.inputs):
                            subcond = _nir.Net.from_cell(priority_cell_idx, bit)
                            if net == _nir.Net.from_const(1):
                                patterns = ()
                            else:
                                # Validate the above assumptions.
                                matches_cell = self.netlist.cells[net.cell]
                                assert isinstance(matches_cell, _nir.Matches)
                                assert test == matches_cell.value
                                patterns = matches_cell.patterns
                            with switch.case(*patterns) as subcase:
                                emit_assignments(subcase, subcond)
                    emitted_switch = True

        lhs = _nir.Value(_nir.Net.from_cell(cell_idx, bit) for bit in range(len(cell.default)))
        with self.builder.process(src=_src(cell.src_loc)) as proc:
            with proc.case() as root_case:
                root_case.assign(self.sigspec(lhs), self.sigspec(cell.default))

                pos = 0 # nonlocally used in `emit_assignments`
                emit_assignments(root_case, _nir.Net.from_const(1))
                assert pos == len(cell.assignments)

    def emit_operator(self, cell_idx, cell):
        UNARY_OPERATORS = {
            "-":    "$neg",
            "~":    "$not",
            "b":    "$reduce_bool",
            "r|":   "$reduce_or",
            "r&":   "$reduce_and",
            "r^":   "$reduce_xor",
        }
        BINARY_OPERATORS = {
            #                    A_SIGNED, B_SIGNED
            "+":   ("$add",      False,    False),
            "-":   ("$sub",      False,    False),
            "*":   ("$mul",      False,    False),
            "u//": ("$divfloor", False,    False),
            "s//": ("$divfloor", True,     True),
            "u%":  ("$modfloor", False,    False),
            "s%":  ("$modfloor", True,     True),
            "<<":  ("$shl",      False,    False),
            "u>>": ("$shr",      False,    False),
            "s>>": ("$sshr",     True,     False),
            "&":   ("$and",      False,    False),
            "|":   ("$or",       False,    False),
            "^":   ("$xor",      False,    False),
            "==":  ("$eq",       False,    False),
            "!=":  ("$ne",       False,    False),
            "u<":  ("$lt",       False,    False),
            "u>":  ("$gt",       False,    False),
            "u<=": ("$le",       False,    False),
            "u>=": ("$ge",       False,    False),
            "s<":  ("$lt",       True,     True),
            "s>":  ("$gt",       True,     True),
            "s<=": ("$le",       True,     True),
            "s>=": ("$ge",       True,     True),
        }
        if len(cell.inputs) == 1:
            cell_type = UNARY_OPERATORS[cell.operator]
            operand, = cell.inputs
            self.builder.cell(cell_type, ports={
                "A": self.sigspec(operand),
                "Y": self.cell_wires[cell_idx]
            }, params={
                "A_SIGNED": False,
                "A_WIDTH": len(operand),
                "Y_WIDTH": cell.width,
            }, src=_src(cell.src_loc))
        elif len(cell.inputs) == 2:
            cell_type, a_signed, b_signed = BINARY_OPERATORS[cell.operator]
            operand_a, operand_b = cell.inputs
            if cell.operator in ("u//", "s//", "u%", "s%"):
                result = self.builder.wire(cell.width)
                self.builder.cell(cell_type, ports={
                    "A": self.sigspec(operand_a),
                    "B": self.sigspec(operand_b),
                    "Y": result,
                }, params={
                    "A_SIGNED": a_signed,
                    "B_SIGNED": b_signed,
                    "A_WIDTH": len(operand_a),
                    "B_WIDTH": len(operand_b),
                    "Y_WIDTH": cell.width,
                }, src=_src(cell.src_loc))
                nonzero = self.builder.wire(1)
                self.builder.cell("$reduce_bool", ports={
                    "A": self.sigspec(operand_b),
                    "Y": nonzero,
                }, params={
                    "A_SIGNED": False,
                    "A_WIDTH": len(operand_b),
                    "Y_WIDTH": 1,
                }, src=_src(cell.src_loc))
                self.builder.cell("$mux", ports={
                    "S": nonzero,
                    "A": self.sigspec(_nir.Value.zeros(cell.width)),
                    "B": result,
                    "Y": self.cell_wires[cell_idx]
                }, params={
                    "WIDTH": cell.width,
                }, src=_src(cell.src_loc))
            else:
                self.builder.cell(cell_type, ports={
                    "A": self.sigspec(operand_a),
                    "B": self.sigspec(operand_b),
                    "Y": self.cell_wires[cell_idx],
                }, params={
                    "A_SIGNED": a_signed,
                    "B_SIGNED": b_signed,
                    "A_WIDTH": len(operand_a),
                    "B_WIDTH": len(operand_b),
                    "Y_WIDTH": cell.width,
                }, src=_src(cell.src_loc))
        else:
            assert cell.operator == "m"
            condition, if_true, if_false = cell.inputs
            self.builder.cell("$mux", ports={
                "S": self.sigspec(condition),
                "A": self.sigspec(if_false),
                "B": self.sigspec(if_true),
                "Y": self.cell_wires[cell_idx]
            }, params={
                "WIDTH": cell.width,
            }, src=_src(cell.src_loc))

    def emit_part(self, cell_idx, cell):
        if cell.stride == 1:
            offset = self.sigspec(cell.offset)
            offset_width = len(cell.offset)
        else:
            stride = _ast.Const(cell.stride)
            offset_width = len(cell.offset) + stride.width
            offset = self.builder.wire(offset_width)
            self.builder.cell("$mul", ports={
                "A": self.sigspec(cell.offset),
                "B": _const(stride),
                "Y": offset,
            }, params={
                "A_SIGNED": False,
                "B_SIGNED": False,
                "A_WIDTH": len(cell.offset),
                "B_WIDTH": stride.width,
                "Y_WIDTH": offset_width,
            }, src=_src(cell.src_loc))
        self.builder.cell("$shift", ports={
            "A": self.sigspec(cell.value),
            "B": offset,
            "Y": self.cell_wires[cell_idx],
        }, params={
            "A_SIGNED": cell.value_signed,
            "B_SIGNED": False,
            "A_WIDTH": len(cell.value),
            "B_WIDTH": offset_width,
            "Y_WIDTH": cell.width,
        }, src=_src(cell.src_loc))

    def emit_array_mux(self, cell_idx, cell):
        wire = self.cell_wires[cell_idx]
        with self.builder.process(src=_src(cell.src_loc)) as proc:
            with proc.case() as root_case:
                with root_case.switch(self.sigspec(cell.index)) as switch:
                    for index, elem in enumerate(cell.elems):
                        if len(cell.index) > 0:
                            pattern = "{:0{}b}".format(index, len(cell.index))
                        else:
                            pattern = ""
                        with switch.case(pattern) as case:
                            case.assign(wire, self.sigspec(elem))
                    with switch.case() as case:
                        case.assign(wire, self.sigspec(cell.elems[0]))

    def emit_flip_flop(self, cell_idx, cell):
        ports = {
            "D": self.sigspec(cell.data),
            "CLK": self.sigspec(cell.clk),
            "Q": self.cell_wires[cell_idx]
        }
        params = {
            "WIDTH": len(cell.data),
            "CLK_POLARITY": {
                "pos": True,
                "neg": False,
            }[cell.clk_edge]
        }
        if cell.arst == _nir.Net.from_const(0):
            cell_type = "$dff"
        else:
            cell_type = "$adff"
            ports["ARST"] = self.sigspec(cell.arst)
            params["ARST_POLARITY"] = True
            params["ARST_VALUE"] = _ast.Const(cell.init, len(cell.data))
        self.builder.cell(cell_type, ports=ports, params=params, src=_src(cell.src_loc))

    def emit_io_buffer(self, cell_idx, cell):
        self.builder.cell("$tribuf", ports={
            "Y": self.sigspec(cell.pad),
            "A": self.sigspec(cell.o),
            "EN": self.sigspec(cell.oe),
        }, params={
            "WIDTH": len(cell.pad),
        }, src=_src(cell.src_loc))
        self.builder.connect(self.cell_wires[cell_idx], self.sigspec(cell.pad))

    def emit_memory(self, cell_idx, cell):
        memory_info = self.memories[cell_idx]
        self.builder.cell("$meminit_v2", ports={
            "ADDR": self.sigspec(),
            "DATA": self.sigspec(
                _nir.Net.from_const((row >> bit) & 1)
                for row in cell.init
                for bit in range(cell.width)
            ),
            "EN": self.sigspec(_nir.Value.ones(cell.width)),
        }, params={
            "MEMID": memory_info.memid,
            "ABITS": 0,
            "WIDTH": cell.width,
            "WORDS": cell.depth,
            "PRIORITY": 0,
        }, src=_src(cell.src_loc))

    def emit_write_port(self, cell_idx, cell):
        memory_info = self.memories[cell.memory]
        ports = {
            "ADDR": self.sigspec(cell.addr),
            "DATA": self.sigspec(cell.data),
            "EN": self.sigspec(cell.en),
            "CLK": self.sigspec(cell.clk),
        }
        params = {
            "MEMID": memory_info.memid,
            "ABITS": len(cell.addr),
            "WIDTH": len(cell.data),
            "CLK_ENABLE": True,
            "CLK_POLARITY": {
                "pos": True,
                "neg": False,
            }[cell.clk_edge],
            "PORTID": memory_info.write_port_ids[cell_idx],
            "PRIORITY_MASK": 0,
        }
        self.builder.cell(f"$memwr_v2", ports=ports, params=params, src=_src(cell.src_loc))

    def emit_read_port(self, cell_idx, cell):
        memory_info = self.memories[cell.memory]
        ports = {
            "ADDR": self.sigspec(cell.addr),
            "DATA": self.cell_wires[cell_idx],
            "ARST": self.sigspec(_nir.Net.from_const(0)),
            "SRST": self.sigspec(_nir.Net.from_const(0)),
        }
        if isinstance(cell, _nir.AsyncReadPort):
            transparency_mask = 0
        if isinstance(cell, _nir.SyncReadPort):
            transparency_mask = sum(
                1 << memory_info.write_port_ids[write_port_cell_index]
                for write_port_cell_index in cell.transparent_for
            )
        params = {
            "MEMID": memory_info.memid,
            "ABITS": len(cell.addr),
            "WIDTH": cell.width,
            "TRANSPARENCY_MASK": _ast.Const(transparency_mask, memory_info.num_write_ports),
            "COLLISION_X_MASK": _ast.Const(0, memory_info.num_write_ports),
            "ARST_VALUE": _ast.Const(0, cell.width),
            "SRST_VALUE": _ast.Const(0, cell.width),
            "INIT_VALUE": _ast.Const(0, cell.width),
            "CE_OVER_SRST": False,
        }
        if isinstance(cell, _nir.AsyncReadPort):
            ports.update({
                "EN": self.sigspec(_nir.Net.from_const(1)),
                "CLK": self.sigspec(_nir.Net.from_const(0)),
            })
            params.update({
                "CLK_ENABLE": False,
                "CLK_POLARITY": True,
            })
        if isinstance(cell, _nir.SyncReadPort):
            ports.update({
                "EN": self.sigspec(cell.en),
                "CLK": self.sigspec(cell.clk),
            })
            params.update({
                "CLK_ENABLE": True,
                "CLK_POLARITY": {
                    "pos": True,
                    "neg": False,
                }[cell.clk_edge],
            })
        self.builder.cell(f"$memrd_v2", ports=ports, params=params, src=_src(cell.src_loc))

    def emit_property(self, cell_idx, cell):
        if isinstance(cell, _nir.AsyncProperty):
            ports = {
                "A": self.sigspec(cell.test),
                "EN": self.sigspec(cell.en),
            }
        if isinstance(cell, _nir.SyncProperty):
            test = self.builder.wire(1, attrs={"init": _ast.Const(0, 1)})
            en = self.builder.wire(1, attrs={"init": _ast.Const(0, 1)})
            for (d, q) in [
                (cell.test, test),
                (cell.en, en),
            ]:
                ports = {
                    "D": self.sigspec(d),
                    "Q": q,
                    "CLK": self.sigspec(cell.clk),
                }
                params = {
                    "WIDTH": 1,
                    "CLK_POLARITY": {
                        "pos": True,
                        "neg": False,
                    }[cell.clk_edge],
                }
                self.builder.cell(f"$dff", ports=ports, params=params, src=_src(cell.src_loc))
            ports = {
                "A": test,
                "EN": en,
            }
        self.builder.cell(f"${cell.kind}", name=cell.name, ports=ports, src=_src(cell.src_loc))

    def emit_any_value(self, cell_idx, cell):
        self.builder.cell(f"${cell.kind}", ports={
            "Y": self.cell_wires[cell_idx],
        }, params={
            "WIDTH": cell.width,
        }, src=_src(cell.src_loc))

    def emit_initial(self, cell_idx, cell):
        self.builder.cell("$initstate", ports={
            "Y": self.cell_wires[cell_idx],
        }, src=_src(cell.src_loc))

    def emit_instance(self, cell_idx, cell):
        ports = {}
        for name, nets in cell.ports_i.items():
            ports[name] = self.sigspec(nets)
        for name in cell.ports_o:
            ports[name] = self.instance_wires[cell_idx, name]
        for name, nets in cell.ports_io.items():
            ports[name] = self.sigspec(nets)
        if cell.type.startswith("$"):
            type = cell.type
        else:
            type = "\\" + cell.type
        self.builder.cell(type, cell.name, ports=ports, params=cell.parameters,
                         attrs=cell.attributes, src=_src(cell.src_loc))

    def emit_cells(self):
        for cell_idx in self.module.cells:
            cell = self.netlist.cells[cell_idx]
            if isinstance(cell, _nir.Top):
                pass
            elif isinstance(cell, _nir.Matches):
                pass # Matches is only referenced from PriorityMatch cells and inlined there
            elif isinstance(cell, _nir.PriorityMatch):
                pass # PriorityMatch is only referenced from AssignmentList cells and inlined there
            elif isinstance(cell, _nir.AssignmentList):
                self.emit_assignment_list(cell_idx, cell)
            elif isinstance(cell, _nir.Operator):
                self.emit_operator(cell_idx, cell)
            elif isinstance(cell, _nir.Part):
                self.emit_part(cell_idx, cell)
            elif isinstance(cell, _nir.ArrayMux):
                self.emit_array_mux(cell_idx, cell)
            elif isinstance(cell, _nir.FlipFlop):
                self.emit_flip_flop(cell_idx, cell)
            elif isinstance(cell, _nir.IOBuffer):
                self.emit_io_buffer(cell_idx, cell)
            elif isinstance(cell, _nir.Memory):
                self.emit_memory(cell_idx, cell)
            elif isinstance(cell, _nir.SyncWritePort):
                self.emit_write_port(cell_idx, cell)
            elif isinstance(cell, (_nir.AsyncReadPort, _nir.SyncReadPort)):
                self.emit_read_port(cell_idx, cell)
            elif isinstance(cell, (_nir.AsyncProperty, _nir.SyncProperty)):
                self.emit_property(cell_idx, cell)
            elif isinstance(cell, _nir.AnyValue):
                self.emit_any_value(cell_idx, cell)
            elif isinstance(cell, _nir.Initial):
                self.emit_initial(cell_idx, cell)
            elif isinstance(cell, _nir.Instance):
                self.emit_instance(cell_idx, cell)
            else:
                assert False # :nocov:


# Empty modules are interpreted by some toolchains (Yosys, Xilinx, ...) as black boxes, and
# must not be emitted.
class EmptyModuleChecker:
    def __init__(self, netlist):
        self.netlist = netlist
        self.empty = set()
        self.check(0)

    def check(self, module_idx):
        is_empty = not self.netlist.modules[module_idx].cells
        for submodule in self.netlist.modules[module_idx].submodules:
            is_empty &= self.check(submodule)
        if is_empty:
            self.empty.add(module_idx)
        return is_empty

    def is_empty(self, module_idx):
        return module_idx in self.empty


def convert_fragment(fragment, ports, name="top", *, emit_src=True, **kwargs):
    assert isinstance(fragment, _ir.Fragment)
    name_map = _ast.SignalDict()
    netlist = _ir.build_netlist(fragment, ports=ports, name=name, **kwargs)
    empty_checker = EmptyModuleChecker(netlist)
    builder = _Builder(emit_src=emit_src)
    for module_idx, module in enumerate(netlist.modules):
        if empty_checker.is_empty(module_idx):
            continue
        attrs = {}
        if module_idx == 0:
            attrs["top"] = 1
        with builder.module(".".join(module.name), attrs=attrs, src=_src(module.src_loc)) as module_builder:
            ModuleEmitter(module_builder, netlist, module, name_map,
                          empty_checker=empty_checker).emit()
    return str(builder), name_map


def convert(elaboratable, name="top", platform=None, *, ports=None, emit_src=True, **kwargs):
    if (ports is None and
            hasattr(elaboratable, "signature") and
            isinstance(elaboratable.signature, wiring.Signature)):
        ports = {}
        for path, member, value in elaboratable.signature.flatten(elaboratable):
            if isinstance(value, _ast.ValueCastable):
                value = value.as_value()
            if isinstance(value, _ast.Value):
                if member.flow == wiring.In:
                    dir = _ir.PortDirection.Input
                else:
                    dir = _ir.PortDirection.Output
                ports["__".join(path)] = (value, dir)
    elif ports is None:
        raise TypeError("The `convert()` function requires a `ports=` argument")
    fragment = _ir.Fragment.get(elaboratable, platform)
    il_text, _name_map = convert_fragment(fragment, ports, name, emit_src=emit_src, **kwargs)
    return il_text

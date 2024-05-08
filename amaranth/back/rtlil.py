from typing import Iterable
from contextlib import contextmanager
import io

from ..utils import bits_for
from .._utils import to_binary
from ..lib import wiring
from ..hdl import _ast, _ir, _nir


__all__ = ["convert", "convert_fragment"]


_escape_map = str.maketrans({
    "\"": "\\\"",
    "\\": "\\\\",
    "\t": "\\t",
    "\r": "\\r",
    "\n": "\\n",
})


# Special hack to emit 'x consts for memory read port init.
class Undef:
    def __init__(self, width):
        self.width = width


def _signed(value):
    if isinstance(value, str):
        return False
    elif isinstance(value, int):
        return value < 0
    elif isinstance(value, _ast.Const):
        return value.shape().signed
    elif isinstance(value, Undef):
        return False
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
        value_twos_compl = value.value & ((1 << len(value)) - 1)
        return "{}'{:0{}b}".format(len(value), value_twos_compl, len(value))
    elif isinstance(value, Undef):
        return f"{value.width}'" + "x" * value.width
    else:
        assert False, f"Invalid constant {value!r}"


def _src(src_loc):
    if src_loc is None:
        return None
    file, line = src_loc
    return f"{file}:{line}"


class Emitter:
    def __init__(self):
        self._indent = ""
        self._lines = []
        self.port_id = 0

    def __call__(self, line=None):
        if line is not None:
            self._lines.append(f"{self._indent}{line}\n")
        else:
            self._lines.append("\n")

    @contextmanager
    def indent(self):
        orig = self._indent
        self._indent += "  "
        yield
        self._indent = orig

    def __str__(self):
        return "".join(self._lines)


class Design:
    def __init__(self, emit_src=True):
        self.modules = {}
        self.emit_src = emit_src

    def module(self, name, **kwargs):
        assert name not in self.modules
        self.modules[name] = res = Module(name, emit_src=self.emit_src, **kwargs)
        return res

    def __str__(self):
        emitter = Emitter()
        for module in self.modules.values():
            module.emit(emitter)
        return str(emitter)


class Module:
    def __init__(self, name, src_loc=None, attrs=None, emit_src=True):
        self.name = name
        self._auto_index = 0
        self.contents = {}
        self.connections = []
        self.attributes = {"generator": "Amaranth"}
        self.emit_src = emit_src
        if src_loc is not None and emit_src:
            self.attributes["src"] = _src(src_loc)
        if attrs is not None:
            self.attributes.update(attrs)

    def _auto_name(self):
        self._auto_index += 1
        return f"${self._auto_index}"

    def _name(self, name):
        if name is None:
            name = self._auto_name()
        else:
            name = f"\\{name}"
        assert name not in self.contents
        return name

    def wire(self, width, *, name=None, **kwargs):
        name = self._name(name)
        if not self.emit_src and "src_loc" in kwargs:
            del kwargs["src_loc"]
        self.contents[name] = res = Wire(width, name=name, **kwargs)
        return res

    def cell(self, kind, name=None, **kwargs):
        name = self._name(name)
        if not self.emit_src and "src_loc" in kwargs:
            del kwargs["src_loc"]
        self.contents[name] = res = Cell(kind, name=name, **kwargs)
        return res

    def memory(self, width, depth, name=None, **kwargs):
        name = self._name(name)
        if not self.emit_src and "src_loc" in kwargs:
            del kwargs["src_loc"]
        self.contents[name] = res = Memory(width, depth, name=name, **kwargs)
        return res

    def process(self, *, name=None, **kwargs):
        name = self._name(name)
        if not self.emit_src and "src_loc" in kwargs:
            del kwargs["src_loc"]
        self.contents[name] = res = Process(name=name, **kwargs)
        return res

    def connect(self, lhs, rhs):
        self.connections.append((lhs, rhs))

    def attribute(self, name, value):
        assert name not in self.attributes
        self.attributes[name] = value

    def emit(self, line):
        line.port_id = 0
        for name, value in self.attributes.items():
            line(f"attribute \\{name} {_const(value)}")
        line(f"module \\{self.name}")
        line()
        with line.indent():
            for item in self.contents.values():
                item.emit(line)
        for (lhs, rhs) in self.connections:
            line(f"connect {lhs} {rhs}")
        if self.connections:
            line()
        line("end")
        line()


def _make_attributes(attrs, src_loc):
    res = {}
    if src_loc is not None:
        res["src"] = _src(src_loc)
    if attrs is not None:
        res.update(attrs)
    return res


class Wire:
    def __init__(self, width, *, name, src_loc=None, attrs=None, signed=False, port_kind=None):
        # Very large wires are unlikely to work. Verilog 1364-2005 requires the limit on vectors
        # to be at least 2**16 bits, and Yosys 0.9 cannot read RTLIL with wires larger than 2**32
        # bits. In practice, wires larger than 2**16 bits, although accepted, cause performance
        # problems without an immediately visible cause, so conservatively limit wire size.
        if width > 2 ** 16:
            raise OverflowError("Wire created at {} is {} bits wide, which is unlikely to "
                                "synthesize correctly"
                                .format(_src(src_loc) or "unknown location", width))
        self.name = name
        self.width = width
        self.signed = signed
        self.port_kind = port_kind
        self.attributes = _make_attributes(attrs, src_loc)

    def attribute(self, name, value):
        assert name not in self.attributes
        self.attributes[name] = value

    def emit(self, line):
        for name, value in self.attributes.items():
            line(f"attribute \\{name} {_const(value)}")
        signed = " signed" if self.signed else ""
        if self.port_kind is None:
            line(f"wire width {self.width}{signed} {self.name}")
        else:
            line(f"wire width {self.width} {self.port_kind} {line.port_id} {signed} {self.name}")
            line.port_id += 1
        line()


class Cell:
    def __init__(self, kind, *, name, ports=None, parameters=None, attrs=None, src_loc=None):
        self.kind = kind
        self.name = name
        self.parameters = parameters or {}
        self.ports = ports or {}
        self.attributes = _make_attributes(attrs, src_loc)

    def port(self, name, value):
        assert name not in self.ports
        self.ports[name] = value

    def parameter(self, name, value):
        assert name not in self.parameters
        self.parameters[name] = value

    def attribute(self, name, value):
        assert name not in self.attributes
        self.attributes[name] = value

    def emit(self, line):
        for name, value in self.attributes.items():
            line(f"attribute \\{name} {_const(value)}")
        line(f"cell {self.kind} {self.name}")
        with line.indent():
            for name, value in self.parameters.items():
                if isinstance(value, float):
                    line(f"parameter real \\{name} \"{value!r}\"")
                elif _signed(value):
                    line(f"parameter signed \\{name} {_const(value)}")
                else:
                    line(f"parameter \\{name} {_const(value)}")
            for name, value in self.ports.items():
                line(f"connect \\{name} {value}")
        line(f"end")
        line()


class Memory:
    def __init__(self, width, depth, *, name, attrs=None, src_loc=None):
        self.width = width
        self.depth = depth
        self.name = name
        self.attributes = _make_attributes(attrs, src_loc)

    def attribute(self, name, value):
        assert name not in self.attributes
        self.attributes[name] = value

    def emit(self, line):
        for name, value in self.attributes.items():
            line(f"attribute \\{name} {_const(value)}")
        line(f"memory width {self.width} size {self.depth} {self.name}")
        line()


def _emit_process_contents(contents, emit):
    index = 0
    while index < len(contents) and isinstance(contents[index], Assignment):
        contents[index].emit(emit)
        index += 1
    while index < len(contents):
        if isinstance(contents[index], Assignment):
            emit(f"switch {{}}")
            with emit.indent():
                emit(f"case")
                with emit.indent():
                    while index < len(contents) and isinstance(contents[index], Assignment):
                        contents[index].emit(emit)
                        index += 1
            emit(f"end")
        else:
            contents[index].emit(emit)
            index += 1


class Process:
    def __init__(self, *, name, attrs=None, src_loc=None):
        self.name = name
        self.contents = []
        self.attributes = _make_attributes(attrs, src_loc)

    def attribute(self, name, value):
        assert name not in self.attributes
        self.attributes[name] = value

    def assign(self, lhs, rhs):
        self.contents.append(Assignment(lhs, rhs))

    def switch(self, sel):
        res = Switch(sel)
        self.contents.append(res)
        return res

    def emit(self, line):
        for name, value in self.attributes.items():
            line(f"attribute \\{name} {_const(value)}")
        line(f"process {self.name}")
        with line.indent():
            _emit_process_contents(self.contents, line)
        line(f"end")
        line()


class Assignment:
    def __init__(self, lhs, rhs):
        self.lhs = lhs
        self.rhs = rhs

    def emit(self, line):
        line(f"assign {self.lhs} {self.rhs}")


class Switch:
    def __init__(self, sel):
        self.sel = sel
        self.cases = []

    def case(self, patterns):
        res = Case(patterns)
        if patterns:
            # RTLIL doesn't support cases with empty pattern list (they get interpreted
            # as a default case instead, which is batshit and the exact opposite of
            # what we want). When such a case is requested, return a case so that
            # the caller can emit stuff into it, but don't actually include it in
            # the switch.
            self.cases.append(res)
        return res

    def default(self):
        res = Case(())
        self.cases.append(res)
        return res

    def emit(self, line):
        line(f"switch {self.sel}")
        with line.indent():
            for case in self.cases:
                case.emit(line)
        line("end")


class Case:
    def __init__(self, patterns):
        self.patterns = patterns
        self.contents = []

    def assign(self, lhs, rhs):
        self.contents.append(Assignment(lhs, rhs))

    def switch(self, sel):
        res = Switch(sel)
        self.contents.append(res)
        return res

    def emit(self, line):
        if self.patterns:
            patterns = ", ".join(f"{len(pattern)}'{pattern}" for pattern in self.patterns)
            line(f"case {patterns}")
        else:
            line(f"case")
        with line.indent():
            _emit_process_contents(self.contents, line)


class MemoryInfo:
    def __init__(self, memid):
        self.memid = memid
        self.num_write_ports = 0
        self.write_port_ids = {}


class ModuleEmitter:
    def __init__(self, builder, netlist: _nir.Netlist, module: _nir.Module, name_map, empty_checker):
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
        self.value_src_loc = {} # value -> source location
        self.sigport_wires = {} # signal or port name -> (wire, value)
        self.driven_sigports = set() # set of signal or port name
        self.nets = {} # net -> (wire name, bit idx)
        self.ionets = {} # ionet -> (wire name, bit idx)
        self.cell_wires = {} # cell idx -> wire name
        self.instance_wires = {} # (cell idx, output name) -> wire name

    def emit(self):
        self.collect_memory_info()
        self.assign_value_names()
        self.collect_init_attrs()
        self.emit_signal_wires()
        self.emit_port_wires()
        self.emit_io_port_wires()
        self.emit_cell_wires()
        self.emit_submodule_wires()
        self.emit_connects()
        self.emit_signal_fields()
        self.emit_submodules()
        self.emit_cells()

    def collect_memory_info(self):
        for cell_idx in self.module.cells:
            cell = self.netlist.cells[cell_idx]
            if isinstance(cell, _nir.Memory):
                self.memories[cell_idx] = MemoryInfo(
                    self.builder.memory(cell.width, cell.depth, name=cell.name,
                                        attrs=cell.attributes, src_loc=cell.src_loc).name)

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
            self.value_src_loc[value] = signal.src_loc

            field = self.netlist.signal_fields[signal][()]
            if field.enum_name is not None:
                attrs["enum_base_type"] = field.enum_name
            if field.enum_variants is not None:
                for var_val, var_name in field.enum_variants.items():
                    attrs["enum_value_" + to_binary(var_val, len(signal))] = var_name

            if name in self.module.ports:
                port_value, _flow = self.module.ports[name]
                assert value == port_value
                self.name_map[signal] = (*self.module.name, name)
            else:
                shape = signal.shape()
                wire  = self.builder.wire(width=shape.width, signed=shape.signed,
                                          name=name, attrs=attrs,
                                          src_loc=signal.src_loc)
                self.sigport_wires[name] = (wire, value)
                self.name_map[signal] = (*self.module.name, wire.name[1:])

    def emit_port_wires(self):
        named_signals = {name: signal for signal, name in self.module.signal_names.items()}
        for port_id, (name, (value, flow)) in enumerate(self.module.ports.items()):
            signed = False
            if name in named_signals:
                signed = named_signals[name].shape().signed
            wire = self.builder.wire(width=len(value), signed=signed,
                                     port_kind=flow.value,
                                     name=name, attrs=self.value_attrs.get(value, {}),
                                     src_loc=self.value_src_loc.get(value))
            self.sigport_wires[name] = (wire, value)
            if flow == _nir.ModuleNetFlow.Output:
                continue
            # If we just emitted an input port, it is driving the value.
            self.driven_sigports.add(name)
            for bit, net in enumerate(value):
                self.nets[net] = (wire, bit)

    def emit_io_port_wires(self):
        for idx, (name, (value, dir)) in enumerate(self.module.io_ports.items()):
            port_id = idx + len(self.module.ports)
            if self.module.parent is None:
                port = self.netlist.io_ports[value[0].port]
                attrs = port.attrs
                src_loc = port.src_loc
            else:
                attrs = {}
                src_loc = None
            wire = self.builder.wire(width=len(value),
                                     port_kind=dir.value,
                                     name=name, attrs=attrs,
                                     src_loc=src_loc)
            for bit, net in enumerate(value):
                self.ionets[net] = (wire, bit)

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
            elif isinstance(cell, (_nir.SyncPrint, _nir.AsyncPrint, _nir.SyncProperty,
                                   _nir.AsyncProperty, _nir.Memory, _nir.SyncWritePort)):
                continue # No outputs.
            elif isinstance(cell, _nir.AssignmentList):
                width = len(cell.default)
            elif isinstance(cell, (_nir.Operator, _nir.Part, _nir.AnyValue,
                                   _nir.SyncReadPort, _nir.AsyncReadPort)):
                width = cell.width
            elif isinstance(cell, _nir.FlipFlop):
                width = len(cell.data)
            elif isinstance(cell, _nir.Initial):
                width = 1
            elif isinstance(cell, _nir.IOBuffer):
                if cell.dir is _nir.IODirection.Output:
                    continue # No outputs.
                width = len(cell.port)
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
                    chunks.append(f"{wire.name} [{start_bit}]")
                else:
                    chunks.append(f"{wire.name} [{start_bit + width - 1}:{start_bit}]")
            begin_pos = end_pos

        if len(chunks) == 1:
            return chunks[0]
        return "{ " + " ".join(reversed(chunks)) + " }"

    def io_sigspec(self, value: _nir.IOValue):
        chunks = []
        begin_pos = 0
        while begin_pos < len(value):
            end_pos = begin_pos
            wire, start_bit = self.ionets[value[begin_pos]]
            bit = start_bit
            while (end_pos < len(value) and
                    self.ionets[value[end_pos]] == (wire, bit)):
                end_pos += 1
                bit += 1
            width = end_pos - begin_pos
            if width == 1:
                chunks.append(f"{wire.name} [{start_bit}]")
            else:
                chunks.append(f"{wire.name} [{start_bit + width - 1}:{start_bit}]")
            begin_pos = end_pos

        if len(chunks) == 1:
            return chunks[0]
        return "{ " + " ".join(reversed(chunks)) + " }"

    def emit_connects(self):
        for name, (wire, value) in self.sigport_wires.items():
            if name not in self.driven_sigports:
                self.builder.connect(wire.name, self.sigspec(value))

    def emit_signal_fields(self):
        for signal, name in self.module.signal_names.items():
            fields = self.netlist.signal_fields[signal]
            for path, field in fields.items():
                if path == ():
                    continue
                name_parts = [name]
                for component in path:
                    if isinstance(component, str):
                        name_parts.append(f".{component}")
                    elif isinstance(component, int):
                        name_parts.append(f"[{component}]")
                    else:
                        assert False # :nocov:
                attrs = {}
                if field.enum_name is not None:
                    attrs["enum_base_type"] = field.enum_name
                if field.enum_variants is not None:
                    for var_val, var_name in field.enum_variants.items():
                        attrs["enum_value_" + to_binary(var_val, len(field.value))] = var_name
                wire = self.builder.wire(width=len(field.value), signed=field.signed, attrs=attrs,
                                         name="".join(name_parts), src_loc=signal.src_loc)
                self.builder.connect(wire.name, self.sigspec(field.value))

    def emit_submodules(self):
        for submodule_idx in self.module.submodules:
            submodule = self.netlist.modules[submodule_idx]
            if not self.empty_checker.is_empty(submodule_idx):
                dotted_name = ".".join(submodule.name)
                ports = {}
                for name, (value, _flow) in submodule.ports.items():
                    ports[name] = self.sigspec(value)
                for name, (value, _dir) in submodule.io_ports.items():
                    ports[name] = self.io_sigspec(value)
                self.builder.cell(f"\\{dotted_name}", submodule.name[-1], ports=ports,
                                  src_loc=submodule.cell_src_loc)

    def emit_assignment_list(self, cell_idx, cell):
        def emit_assignments(case, cond):
            # Emits assignments from the assignment list into the given case.
            # ``cond`` is the net which is the condition for ``case`` being active.
            # Returns once it hits an assignment whose condition is not nested within ``cond``,
            # letting parent invocation take care of the remaining assignments.
            nonlocal pos

            while pos < len(cell.assignments):
                assign = cell.assignments[pos]
                if assign.cond == cond:
                    # Not nested, so emit the assignment.
                    case.assign(self.sigspec(lhs[assign.start:assign.start + len(assign.value)]),
                                self.sigspec(assign.value))
                    pos += 1
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
                    switch = case.switch(self.sigspec(test))
                    for bit, net in enumerate(priority_cell.inputs):
                        subcond = _nir.Net.from_cell(priority_cell_idx, bit)
                        if net == _nir.Net.from_const(1):
                            emit_assignments(switch.default(), subcond)
                        else:
                            # Validate the above assumptions.
                            matches_cell = self.netlist.cells[net.cell]
                            assert isinstance(matches_cell, _nir.Matches)
                            assert test == matches_cell.value
                            patterns = matches_cell.patterns
                            emit_assignments(switch.case(patterns), subcond)

        lhs = _nir.Value(_nir.Net.from_cell(cell_idx, bit) for bit in range(len(cell.default)))
        proc = self.builder.process(src_loc=cell.src_loc)
        proc.assign(self.sigspec(lhs), self.sigspec(cell.default))
        pos = 0 # nonlocally used in `emit_assignments`
        emit_assignments(proc, _nir.Net.from_const(1))
        assert pos == len(cell.assignments)

    def shorten_operand(self, value, *, signed):
        value = list(value)
        if signed:
            while len(value) > 1 and value[-1] == value[-2]:
                value.pop()
        else:
            while len(value) > 0 and value[-1] == _nir.Net.from_const(0):
                value.pop()
        return _nir.Value(value)

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
            signed = False
            if cell.operator == "-":
                # For arithmetic operands, we trim the extra sign or zero extension on the operands
                # to make the output prettier, and to fix inference problems in some not very smart
                # synthesis tools.
                operand_u = self.shorten_operand(operand, signed=False)
                operand_s = self.shorten_operand(operand, signed=True)
                # The operator will work when lowered with either signedness.  Pick whichever
                # is prettier.
                if len(operand_s) < len(operand_u):
                    signed = True
                    operand = operand_s
                else:
                    signed = False
                    operand = operand_u
            self.builder.cell(cell_type, ports={
                "A": self.sigspec(operand),
                "Y": self.cell_wires[cell_idx].name
            }, parameters={
                "A_SIGNED": signed,
                "A_WIDTH": len(operand),
                "Y_WIDTH": cell.width,
            }, src_loc=cell.src_loc)
        elif len(cell.inputs) == 2:
            cell_type, a_signed, b_signed = BINARY_OPERATORS[cell.operator]
            operand_a, operand_b = cell.inputs
            if cell.operator in ("+", "-", "*", "==", "!="):
                # Arithmetic operators that will work with any signedness, but we have to choose
                # a common one for both operands. Prefer signed in case of mixed signedness.
                operand_a_u = self.shorten_operand(operand_a, signed=False)
                operand_b_u = self.shorten_operand(operand_b, signed=False)
                operand_a_s = self.shorten_operand(operand_a, signed=True)
                operand_b_s = self.shorten_operand(operand_b, signed=True)
                if operand_a.is_const:
                    # In case of constant operand, choose whichever shortens the other one better.
                    signed = len(operand_b_s) < len(operand_b_u)
                elif operand_b.is_const:
                    signed = len(operand_a_s) < len(operand_a_u)
                elif (len(operand_a_s) < len(operand_a) and len(operand_a_u) == len(operand_a)):
                    # Operand A can only be shortened by signed. Pick it.
                    signed = True
                elif (len(operand_b_s) < len(operand_b) and len(operand_b_u) == len(operand_b)):
                    # Operand B can only be shortened by signed. Pick it.
                    signed = True
                else:
                    # Otherwise, use unsigned shortening.
                    signed = False
                if signed:
                    operand_a = operand_a_s
                    operand_b = operand_b_s
                else:
                    operand_a = operand_a_u
                    operand_b = operand_b_u
                a_signed = b_signed = signed
            if cell.operator[0] in "us":
                # Signedness forced, just shorten.
                operand_a = self.shorten_operand(operand_a, signed=a_signed)
                operand_b = self.shorten_operand(operand_b, signed=b_signed)
            if cell.operator == "<<":
                # We can pick the signedness for left operand, but right is fixed.
                operand_a_u = self.shorten_operand(operand_a, signed=False)
                operand_a_s = self.shorten_operand(operand_a, signed=True)
                if len(operand_a_s) < len(operand_a_u):
                    a_signed = True
                    operand_a = operand_a_s
                else:
                    a_signed = False
                    operand_a = operand_a_u
                operand_b = self.shorten_operand(operand_b, signed=b_signed)
            if cell.operator in ("u//", "s//", "u%", "s%"):
                result = self.builder.wire(cell.width)
                self.builder.cell(cell_type, ports={
                    "A": self.sigspec(operand_a),
                    "B": self.sigspec(operand_b),
                    "Y": result.name,
                }, parameters={
                    "A_SIGNED": a_signed,
                    "B_SIGNED": b_signed,
                    "A_WIDTH": len(operand_a),
                    "B_WIDTH": len(operand_b),
                    "Y_WIDTH": cell.width,
                }, src_loc=cell.src_loc)
                nonzero = self.builder.wire(1)
                self.builder.cell("$reduce_bool", ports={
                    "A": self.sigspec(operand_b),
                    "Y": nonzero.name,
                }, parameters={
                    "A_SIGNED": False,
                    "A_WIDTH": len(operand_b),
                    "Y_WIDTH": 1,
                }, src_loc=cell.src_loc)
                self.builder.cell("$mux", ports={
                    "S": nonzero.name,
                    "A": self.sigspec(_nir.Value.zeros(cell.width)),
                    "B": result.name,
                    "Y": self.cell_wires[cell_idx].name
                }, parameters={
                    "WIDTH": cell.width,
                }, src_loc=cell.src_loc)
            else:
                self.builder.cell(cell_type, ports={
                    "A": self.sigspec(operand_a),
                    "B": self.sigspec(operand_b),
                    "Y": self.cell_wires[cell_idx].name,
                }, parameters={
                    "A_SIGNED": a_signed,
                    "B_SIGNED": b_signed,
                    "A_WIDTH": len(operand_a),
                    "B_WIDTH": len(operand_b),
                    "Y_WIDTH": cell.width,
                }, src_loc=cell.src_loc)
        else:
            assert cell.operator == "m"
            condition, if_true, if_false = cell.inputs
            self.builder.cell("$mux", ports={
                "S": self.sigspec(condition),
                "A": self.sigspec(if_false),
                "B": self.sigspec(if_true),
                "Y": self.cell_wires[cell_idx].name
            }, parameters={
                "WIDTH": cell.width,
            }, src_loc=cell.src_loc)

    def emit_part(self, cell_idx, cell):
        if cell.stride == 1:
            offset = self.sigspec(cell.offset)
            offset_width = len(cell.offset)
        else:
            stride = _ast.Const(cell.stride)
            offset_width = len(cell.offset) + len(stride)
            offset = self.builder.wire(offset_width).name
            self.builder.cell("$mul", ports={
                "A": self.sigspec(cell.offset),
                "B": _const(stride),
                "Y": offset,
            }, parameters={
                "A_SIGNED": False,
                "B_SIGNED": False,
                "A_WIDTH": len(cell.offset),
                "B_WIDTH": len(stride),
                "Y_WIDTH": offset_width,
            }, src_loc=cell.src_loc)
        self.builder.cell("$shift", ports={
            "A": self.sigspec(cell.value),
            "B": offset,
            "Y": self.cell_wires[cell_idx].name,
        }, parameters={
            "A_SIGNED": cell.value_signed,
            "B_SIGNED": False,
            "A_WIDTH": len(cell.value),
            "B_WIDTH": offset_width,
            "Y_WIDTH": cell.width,
        }, src_loc=cell.src_loc)

    def emit_flip_flop(self, cell_idx, cell):
        ports = {
            "D": self.sigspec(cell.data),
            "CLK": self.sigspec(cell.clk),
            "Q": self.cell_wires[cell_idx].name
        }
        parameters = {
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
            parameters["ARST_POLARITY"] = True
            parameters["ARST_VALUE"] = _ast.Const(cell.init, len(cell.data))
        self.builder.cell(cell_type, ports=ports, parameters=parameters, src_loc=cell.src_loc)

    def emit_io_buffer(self, cell_idx, cell):
        if cell.dir is not _nir.IODirection.Input:
            if cell.dir is _nir.IODirection.Output and cell.oe == _nir.Net.from_const(1):
                self.builder.connect(self.io_sigspec(cell.port), self.sigspec(cell.o))
            else:
                self.builder.cell("$tribuf", ports={
                    "Y": self.io_sigspec(cell.port),
                    "A": self.sigspec(cell.o),
                    "EN": self.sigspec(cell.oe),
                }, parameters={
                    "WIDTH": len(cell.port),
                }, src_loc=cell.src_loc)
        if cell.dir is not _nir.IODirection.Output:
            self.builder.connect(self.cell_wires[cell_idx].name, self.io_sigspec(cell.port))

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
        }, parameters={
            "MEMID": memory_info.memid,
            "ABITS": 0,
            "WIDTH": cell.width,
            "WORDS": cell.depth,
            "PRIORITY": 0,
        }, src_loc=cell.src_loc)

    def emit_write_port(self, cell_idx, cell):
        memory_info = self.memories[cell.memory]
        ports = {
            "ADDR": self.sigspec(cell.addr),
            "DATA": self.sigspec(cell.data),
            "EN": self.sigspec(cell.en),
            "CLK": self.sigspec(cell.clk),
        }
        parameters = {
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
        self.builder.cell(f"$memwr_v2", ports=ports, parameters=parameters, src_loc=cell.src_loc)

    def emit_read_port(self, cell_idx, cell):
        memory_info = self.memories[cell.memory]
        ports = {
            "ADDR": self.sigspec(cell.addr),
            "DATA": self.cell_wires[cell_idx].name,
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
        parameters = {
            "MEMID": memory_info.memid,
            "ABITS": len(cell.addr),
            "WIDTH": cell.width,
            "TRANSPARENCY_MASK": _ast.Const(transparency_mask, memory_info.num_write_ports),
            "COLLISION_X_MASK": _ast.Const(0, memory_info.num_write_ports),
            # Horrible hack alert: Yosys has two different Verilog code patterns it can emit for
            # transparent synchronous read ports — the old, limitted one and the generic new one.
            # The old one essentially consists of a combinational read port with a register added
            # on the *address* input. It has several limitations:
            #
            # - can only express read ports transparent wrt *all* write ports
            # - cannot support initial values
            # - cannot support reset
            # - cannot support clock enable
            #
            # The new pattern can express any supported read port, but is not widely recognized
            # by other toolchains, leading to memory inference failures. Thus, Yosys will use
            # the old pattern whenever possible.
            #
            # In order to enable Yosys to use the old pattern and avoid memory inference regressions
            # with non-Yosys synthesis, we need to emit undefined initial value here. This is in
            # direct conflict with RFC 54, and will have to be revisited before 0.6, possibly
            # requiring a large-scale design change in Amaranth memory support.
            "ARST_VALUE": Undef(cell.width),
            "SRST_VALUE": Undef(cell.width),
            "INIT_VALUE": Undef(cell.width),
            "CE_OVER_SRST": False,
        }
        if isinstance(cell, _nir.AsyncReadPort):
            ports.update({
                "EN": self.sigspec(_nir.Net.from_const(1)),
                "CLK": self.sigspec(_nir.Net.from_const(0)),
            })
            parameters.update({
                "CLK_ENABLE": False,
                "CLK_POLARITY": True,
            })
        if isinstance(cell, _nir.SyncReadPort):
            ports.update({
                "EN": self.sigspec(cell.en),
                "CLK": self.sigspec(cell.clk),
            })
            parameters.update({
                "CLK_ENABLE": True,
                "CLK_POLARITY": {
                    "pos": True,
                    "neg": False,
                }[cell.clk_edge],
            })
        self.builder.cell(f"$memrd_v2", ports=ports, parameters=parameters, src_loc=cell.src_loc)

    def emit_print(self, cell_idx, cell):
        args = []
        format = []
        if cell.format is not None:
            for chunk in cell.format.chunks:
                if isinstance(chunk, str):
                    format.append(chunk)
                else:
                    spec = _ast.Format._parse_format_spec(chunk.format_desc, _ast.Shape(len(chunk.value), chunk.signed))
                    type = spec["type"]
                    if type == "s":
                        assert len(chunk.value) % 8 == 0
                        for bit in reversed(range(0, len(chunk.value), 8)):
                            args += chunk.value[bit:bit+8]
                    else:
                        args += chunk.value
                    if type is None:
                        type = "d"
                    elif type == "x":
                        type = "h"
                    elif type == "X":
                        type = "H"
                    elif type == "c":
                        type = "U"
                    elif type == "s":
                        type = "c"
                    width = spec["width"]
                    align = spec["align"]
                    if align is None:
                        align = "<" if type in ("c", "U") else ">"
                    fill = spec["fill"]
                    if fill is None:
                        fill = ' '
                    if ord(fill) >= 0x80:
                        raise NotImplementedError(f"non-ASCII fill character {fill!r} is not supported in RTLIL")
                    sign = spec["sign"]
                    if sign is None:
                        sign = ""
                    if type in ("c", "U"):
                        signed = ""
                    elif chunk.signed:
                        signed = "s"
                    else:
                        signed = "u"
                    show_base = "#" if spec["show_base"] and type != "d" else ""
                    grouping = spec["grouping"] or ""
                    if type == "U":
                        if align != "<" and width != 0:
                            format.append(fill * (width - 1))
                        format.append(f"{{{len(chunk.value)}:U}}")
                        if align == "<" and width != 0:
                            format.append(fill * (width - 1))
                    else:
                        format.append(f"{{{len(chunk.value)}:{align}{fill}{width or ''}{type}{sign}{show_base}{grouping}{signed}}}")
        ports = {
            "EN": self.sigspec(cell.en),
            "ARGS": self.sigspec(_nir.Value(args)),
        }
        parameters = {
            "FORMAT": "".join(format),
            "ARGS_WIDTH": len(args),
            "PRIORITY": -cell_idx,
        }
        if isinstance(cell, (_nir.AsyncPrint, _nir.AsyncProperty)):
            ports["TRG"] = self.sigspec(_nir.Value())
            parameters["TRG_ENABLE"] = False
            parameters["TRG_WIDTH"] = 0
            parameters["TRG_POLARITY"] = 0
        if isinstance(cell, (_nir.SyncPrint, _nir.SyncProperty)):
            ports["TRG"] = self.sigspec(cell.clk)
            parameters["TRG_ENABLE"] = True
            parameters["TRG_WIDTH"] = 1
            parameters["TRG_POLARITY"] = cell.clk_edge == "pos"
        if isinstance(cell, (_nir.AsyncPrint, _nir.SyncPrint)):
            self.builder.cell(f"$print", parameters=parameters, ports=ports, src_loc=cell.src_loc)
        if isinstance(cell, (_nir.AsyncProperty, _nir.SyncProperty)):
            parameters["FLAVOR"] = cell.kind
            ports["A"] = self.sigspec(cell.test)
            self.builder.cell(f"$check", parameters=parameters, ports=ports, src_loc=cell.src_loc)

    def emit_any_value(self, cell_idx, cell):
        self.builder.cell(f"${cell.kind}", ports={
            "Y": self.cell_wires[cell_idx].name,
        }, parameters={
            "WIDTH": cell.width,
        }, src_loc=cell.src_loc)

    def emit_initial(self, cell_idx, cell):
        self.builder.cell("$initstate", ports={
            "Y": self.cell_wires[cell_idx].name,
        }, src_loc=cell.src_loc)

    def emit_instance(self, cell_idx, cell):
        ports = {}
        for name, nets in cell.ports_i.items():
            ports[name] = self.sigspec(nets)
        for name in cell.ports_o:
            ports[name] = self.instance_wires[cell_idx, name].name
        for name, (ionets, _dir) in cell.ports_io.items():
            ports[name] = self.io_sigspec(ionets)
        self.builder.cell(f"\\{cell.type}", cell.name, ports=ports,
                          parameters=cell.parameters, attrs=cell.attributes,
                          src_loc=cell.src_loc)

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
            elif isinstance(cell, (_nir.AsyncPrint, _nir.SyncPrint, _nir.AsyncProperty, _nir.SyncProperty)):
                self.emit_print(cell_idx, cell)
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


def convert_fragment(fragment, ports=(), name="top", *, emit_src=True, **kwargs):
    assert isinstance(fragment, (_ir.Fragment, _ir.Design))
    name_map = _ast.SignalDict()
    netlist = _ir.build_netlist(fragment, ports=ports, name=name, **kwargs)
    empty_checker = EmptyModuleChecker(netlist)
    builder = Design(emit_src=emit_src)
    for module_idx, module in enumerate(netlist.modules):
        if empty_checker.is_empty(module_idx):
            continue
        module_builder = builder.module(".".join(module.name), src_loc=module.src_loc)
        if module_idx == 0:
            module_builder.attribute("top", 1)
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
                ports["__".join(map(str, path))] = (value, dir)
    elif ports is None:
        raise TypeError("The `convert()` function requires a `ports=` argument")
    fragment = _ir.Fragment.get(elaboratable, platform)
    il_text, _name_map = convert_fragment(fragment, ports, name, emit_src=emit_src, **kwargs)
    return il_text

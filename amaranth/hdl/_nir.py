from typing import Any
from collections.abc import Iterable
import enum

from ._ast import SignalDict
from . import _ast


__all__ = [
    # Netlist core
    "CombinationalCycle",
    "Net", "Value", "IONet", "IOValue",
    "FormatValue", "Format", "SignalField",
    "Netlist", "ModuleNetFlow", "IODirection", "Module", "Cell", "Top",
    # Computation cells
    "Operator", "Part",
    # Decision tree cells
    "Match", "Assignment", "AssignmentList",
    # Storage cells
    "FlipFlop", "Memory", "SyncWritePort", "AsyncReadPort", "SyncReadPort",
    # Print cells
    "AsyncPrint", "SyncPrint",
    # Formal verification cells
    "Initial", "AnyValue", "AsyncProperty", "SyncProperty",
    # Foreign interface cells
    "Instance", "IOBuffer",
]


class CombinationalCycle(Exception):
    pass


class Net(int):
    __slots__ = ()

    @classmethod
    def from_cell(cls, cell: int, bit: int):
        assert bit in range(1 << 16)
        assert cell >= 0
        if cell == 0:
            assert bit >= 2
        return cls((cell << 16) | bit)

    @classmethod
    def from_const(cls, val: int):
        assert val in (0, 1)
        return cls(val)

    @classmethod
    def from_late(cls, val: int):
        assert val < 0
        return cls(val)

    @property
    def is_const(self):
        return self in (0, 1)

    @property
    def const(self):
        assert self in (0, 1)
        return int(self)

    @property
    def is_late(self):
        return self < 0

    @property
    def is_cell(self):
        return self >= 2

    @property
    def cell(self):
        assert self >= 2
        return self >> 16

    @property
    def bit(self):
        assert self >= 2
        return self & 0xffff

    @classmethod
    def ensure(cls, value: 'Net'):
        assert isinstance(value, cls)
        return value

    def __repr__(self):
        if self.is_late:
            return f"(late {int(self)})"
        elif self.is_const:
            return f"{int(self)}"
        else:
            return f"{self.cell}.{self.bit}"

    __str__ = __repr__


class Value(tuple):
    __slots__ = ()

    def __new__(cls, nets: 'Net | Iterable[Net]' = ()):
        if isinstance(nets, Net):
            return super().__new__(cls, (nets,))
        return super().__new__(cls, (Net.ensure(net) for net in nets))

    @classmethod
    def from_const(cls, value, width):
        return cls(Net.from_const((value >> bit) & 1) for bit in range(width))

    @classmethod
    def zeros(cls, digits=1):
        return cls.from_const(0, digits)

    @classmethod
    def ones(cls, digits=1):
        return cls.from_const(-1, digits)

    def __getitem__(self, index):
        if isinstance(index, slice):
            return type(self)(super().__getitem__(index))
        else:
            return super().__getitem__(index)

    def __repr__(self):
        pos = 0
        chunks = []
        while pos < len(self):
            next_pos = pos
            if self[pos].is_const:
                value = 0
                while next_pos < len(self) and self[next_pos].is_const:
                    value |= self[next_pos].const << (next_pos - pos)
                    next_pos += 1
                width = next_pos - pos
                chunks.append(f"{width}'d{value}")
            elif self[pos].is_late:
                while (next_pos < len(self) and
                       self[next_pos].is_late and
                       self[next_pos] == self[pos] + (next_pos - pos)):
                    next_pos += 1
                width = next_pos - pos
                start = int(self[pos])
                end = start + width
                if width == 1:
                    chunks.append(f"(late {start})")
                else:
                    chunks.append(f"(late {start}:{end})")
            else:
                cell = self[pos].cell
                start_bit = self[pos].bit
                while (next_pos < len(self) and
                       self[next_pos].is_cell and
                       self[next_pos].cell == cell and
                       self[next_pos].bit == start_bit + (next_pos - pos)):
                    next_pos += 1
                width = next_pos - pos
                end_bit = start_bit + width
                if width == 1:
                    chunks.append(f"{cell}.{start_bit}")
                else:
                    chunks.append(f"{cell}.{start_bit}:{end_bit}")
            pos = next_pos
        if len(chunks) == 0:
            return "()"
        elif len(chunks) == 1:
            return chunks[0]
        else:
            return f"(cat {' '.join(chunks)})"

    @property
    def is_const(self):
        return all(net.is_const for net in self)

    __str__ = __repr__


class IONet(int):
    __slots__ = ()

    @classmethod
    def from_port(cls, port: int, bit: int):
        assert bit in range(1 << 16)
        assert port >= 0
        return cls((port << 16) | bit)

    @property
    def port(self):
        return self >> 16

    @property
    def bit(self):
        return self & 0xffff

    @classmethod
    def ensure(cls, value: 'IONet'):
        assert isinstance(value, cls)
        return value

    def __repr__(self):
        return f"{self.port}.{self.bit}"

    __str__ = __repr__


class IOValue(tuple):
    __slots__ = ()

    def __new__(cls, nets: 'IONet | Iterable[IONet]' = ()):
        if isinstance(nets, IONet):
            return super().__new__(cls, (nets,))
        return super().__new__(cls, (IONet.ensure(net) for net in nets))

    def __getitem__(self, index):
        if isinstance(index, slice):
            return type(self)(super().__getitem__(index))
        else:
            return super().__getitem__(index)

    def __repr__(self):
        pos = 0
        chunks = []
        while pos < len(self):
            next_pos = pos
            port = self[pos].port
            start_bit = self[pos].bit
            while (next_pos < len(self) and
                    self[next_pos].port == port and
                    self[next_pos].bit == start_bit + (next_pos - pos)):
                next_pos += 1
            width = next_pos - pos
            end_bit = start_bit + width
            if width == 1:
                chunks.append(f"{port}.{start_bit}")
            else:
                chunks.append(f"{port}.{start_bit}:{end_bit}")
            pos = next_pos
        if len(chunks) == 0:
            return "()"
        elif len(chunks) == 1:
            return chunks[0]
        else:
            return f"(io-cat {' '.join(chunks)})"

    __str__ = __repr__


class FormatValue:
    """A single formatted value within ``Format``.

    Attributes
    ----------

    value: Value
    format_desc: str
    signed: bool
    """
    def __init__(self, value, format_desc, *, signed):
        assert isinstance(format_desc, str)
        assert isinstance(signed, bool)
        self.value = Value(value)
        self.format_desc = format_desc
        self.signed = signed

    def __repr__(self):
        sign = "s" if self.signed else "u"
        return f"({sign} {self.value!r} {self.format_desc!r})"


class Format:
    """Like _ast.Format, but for NIR.

    Attributes
    ----------

    chunks: tuple of str and FormatValue
    """
    def __init__(self, chunks):
        self.chunks = tuple(chunks)
        for chunk in self.chunks:
            assert isinstance(chunk, (str, FormatValue))

    def __repr__(self):
        return f"({' '.join(repr(chunk) for chunk in self.chunks)})"

    def input_nets(self):
        nets = set()
        for chunk in self.chunks:
            if isinstance(chunk, FormatValue):
                nets |= set(chunk.value)
        return nets

    def resolve_nets(self, netlist: "Netlist"):
        for chunk in self.chunks:
            if isinstance(chunk, FormatValue):
                chunk.value = netlist.resolve_value(chunk.value)


class SignalField:
    """Describes a single field of a signal."""
    def __init__(self, value, *, signed, enum_name=None, enum_variants=None):
        self.value = Value(value)
        self.signed = bool(signed)
        self.enum_name = enum_name
        self.enum_variants = enum_variants

    def __eq__(self, other):
        return (type(self) is type(other) and
            self.value == other.value and
            self.signed == other.signed and
            self.enum_name == other.enum_name and
            self.enum_variants == other.enum_variants)


class Netlist:
    """A fine netlist. Consists of:

    - a flat array of cells
    - a dictionary of connections for late-bound nets
    - a map of hierarchical names to nets
    - a map of signals to nets

    The nets are virtual: a list of nets is not materialized anywhere in the netlist.
    A net is a single bit wide and represented as a single int. The int is encoded as follows:

    - A negative number means a late-bound net. The net should be looked up in the ``connections``
      dictionary to find its driver.
    - Non-negative numbers are cell outputs, and are split into bitfields as follows:

      - bits 0-15: output bit index within a cell (exact meaning is cell-dependent)
      - bits 16-...: index of cell in ``netlist.cells``

    Cell 0 is always ``Top``.  The first two output bits of ``Top`` are considered to be constants
    ``0`` and ``1``, which effectively means that net encoded as ``0`` is always a constant ``0`` and
    net encoded as ``1`` is always a constant ``1``.

    Multi-bit values are represented as tuples of int.

    Attributes
    ----------

    modules : list of ``Module``
    cells : list of ``Cell``
    connections : dict of (negative) int to int
    late_to_signal : dict of (late) Net to its Signal and bit number
    io_ports : list of ``IOPort``
    signals : dict of Signal to ``Value``
    signal_fields: dict of Signal to dict of tuple[str | int] to SignalField
    last_late_net: int
    """
    def __init__(self):
        self.modules: list[Module] = []
        self.cells: list[Cell] = [Top()]
        self.connections: dict[Net, Net] = {}
        self.late_to_signal: dict[Net, (_ast.Signal, int)] = {}
        self.io_ports: list[_ast.IOPort] = []
        self.signals = SignalDict()
        self.signal_fields = SignalDict()
        self.last_late_net = 0

    def resolve_net(self, net: Net):
        assert isinstance(net, Net)
        while net.is_late:
            net = self.connections[net]
        return net

    def resolve_value(self, value: Value):
        return Value(self.resolve_net(net) for net in value)

    def resolve_all_nets(self):
        for cell in self.cells:
            cell.resolve_nets(self)
        for sig in self.signals:
            self.signals[sig] = self.resolve_value(self.signals[sig])
        for fields in self.signal_fields.values():
            for field in fields.values():
                field.value = self.resolve_value(field.value)

    def __repr__(self):
        result = ["("]
        for module_idx, module in enumerate(self.modules):
            name = " ".join(repr(name) for name in module.name)
            ports = [
                f"({flow.value} {name!r} {val})"
                for name, (val, flow) in module.ports.items()
            ]
            io_ports = [
                f"(io {dir.value} {name!r} {val})"
                for name, (val, dir) in module.io_ports.items()
            ]
            ports = "".join(" " + port for port in ports + io_ports)
            result.append(f"(module {module_idx} {module.parent} ({name}){ports})")
        for cell_idx, cell in enumerate(self.cells):
            result.append(f"(cell {cell_idx} {cell.module_idx} {cell!r})")
        result.append(")")
        return "\n".join(result)

    def add_module(self, parent, name: str, *, src_loc=None, cell_src_loc=None):
        module_idx = len(self.modules)
        self.modules.append(Module(parent, name, src_loc=src_loc, cell_src_loc=cell_src_loc))
        if module_idx == 0:
            self.modules[0].cells.append(0)
        if parent is not None:
            self.modules[parent].submodules.append(module_idx)
        return module_idx

    def add_cell(self, cell):
        idx = len(self.cells)
        self.cells.append(cell)
        self.modules[cell.module_idx].cells.append(idx)
        return idx

    def add_value_cell(self, width: int, cell):
        cell_idx = self.add_cell(cell)
        return Value(Net.from_cell(cell_idx, bit) for bit in range(width))

    def alloc_late_value(self, signal: _ast.Signal):
        self.last_late_net -= len(signal)
        value = Value(Net.from_late(self.last_late_net + bit) for bit in range(len(signal)))
        for bit, net in enumerate(value):
            self.late_to_signal[net] = signal, bit
        return value

    @property
    def top(self):
        top = self.cells[0]
        assert isinstance(top, Top)
        return top

    def check_comb_cycles(self):
        class Cycle:
            def __init__(self, start):
                self.start = start
                self.path = []

        checked = set()
        busy = set()

        def traverse(net):
            if net in checked:
                return None

            if net in busy:
                return Cycle(net)
            busy.add(net)

            cycle = None
            if net.is_const:
                pass
            elif net.is_late:
                cycle = traverse(self.connections[net])
                if cycle is not None:
                    sig, bit = self.late_to_signal[net]
                    cycle.path.append((sig, bit, sig.src_loc))
            else:
                for src, src_loc in self.cells[net.cell].comb_edges_to(net.bit):
                    cycle = traverse(src)
                    if cycle is not None:
                        cycle.path.append((self.cells[net.cell], net.bit, src_loc))
                        break

            if cycle is not None and cycle.start == net:
                msg = ["Combinational cycle detected, path:\n"]
                for obj, bit, src_loc in reversed(cycle.path):
                    if isinstance(obj, _ast.Signal):
                        obj = f"signal {obj.name}"
                    elif isinstance(obj, Operator):
                        obj = f"operator {obj.operator}"
                    else:
                        obj = f"cell {obj.__class__.__qualname__}"
                    src_loc = "<unknown>:0" if src_loc is None else f"{src_loc[0]}:{src_loc[1]}"
                    msg.append(f"  {src_loc}: {obj} bit {bit}\n")
                raise CombinationalCycle("".join(msg))

            busy.remove(net)
            checked.add(net)
            return cycle

        for cell_idx, cell in enumerate(self.cells):
            for net in cell.output_nets(cell_idx):
                assert traverse(net) is None
        for value in self.signals.values():
            for net in value:
                assert traverse(net) is None


class ModuleNetFlow(enum.Enum):
    """Describes how a given Net flows into or out of a Module.

    The net can also be none of these (not present in the dictionary at all),
    when it is not present in the module at all.
    """

    #: The net is present in the module (used in the module or needs
    #: to be routed through it between its submodules), but is not
    #: present outside its subtree and thus is not a port of this module.
    Internal = "internal"

    #: The net is present in the module, and is not driven from
    #: the module or any of its submodules.  It is thus an input
    #: port of this module.
    Input    = "input"

    #: The net is present in the module, is driven from the module or
    #: one of its submodules, and is also used outside of its subtree.
    #: It is thus an output port of this module.
    Output   = "output"


class IODirection(enum.Enum):
    Input  = "input"
    Output = "output"
    Bidir  = "inout"

    def __or__(self, other):
        assert isinstance(other, IODirection)
        if self == other:
            return self
        else:
            return IODirection.Bidir


class Module:
    """A module within the netlist.

    Attributes
    ----------

    parent: index of parent module, or ``None`` for top module
    name: a tuple of str, hierarchical name of this module (top has empty tuple)
    src_loc: str
    submodules: a list of nested module indices
    signal_names: a SignalDict from Signal to str, signal names visible in this module
    net_flow: a dict from Net to NetFlow, describes how a net is used within this module
    ports: a dict from port name to (Value, ModuleNetFlow) pair
    io_ports: a dict from port name to (IOValue, IODirection) pair
    cells: a list of cell indices that belong to this module
    """
    def __init__(self, parent, name, *, src_loc, cell_src_loc):
        self.parent = parent
        self.name = name
        self.src_loc = src_loc
        self.cell_src_loc = cell_src_loc
        self.submodules = []
        self.signal_names = SignalDict()
        self.io_port_names = {}
        self.net_flow: dict[Net, ModuleNetFlow] = {}
        self.ionet_dir: dict[IONet, IODirection] = {}
        self.ports = {}
        self.io_ports = {}
        self.cells = []


class Cell:
    """A base class for all cell types.

    Attributes
    ----------

    src_loc: str
    module: int, index of the module this cell belongs to (within Netlist.modules)
    """

    def __init__(self, module_idx: int, *, src_loc):
        self.module_idx = module_idx
        self.src_loc = src_loc

    def input_nets(self):
        raise NotImplementedError

    def output_nets(self, self_idx: int):
        raise NotImplementedError

    def io_nets(self):
        return set()

    def resolve_nets(self, netlist: Netlist):
        raise NotImplementedError

    def comb_edges_to(self, bit: int) -> "Iterable[(Net, Any)]":
        raise NotImplementedError


class Top(Cell):
    """A special cell type representing top-level non-IO ports. Must be present in the netlist exactly
    once, at index 0.

    Top-level outputs are stored as a dict of names to their assigned values.

    Top-level inputs are effectively the output of this cell. They are stored
    as a dict of names to a (start bit index, width) tuple. Output bit indices 0 and 1 are reserved
    for constant nets, so the lowest bit index that can be assigned to a port is 2.

    Attributes
    ----------

    ports_o: dict of str to Value
    ports_i: dict of str to (int, int)
    """
    def __init__(self):
        super().__init__(module_idx=0, src_loc=None)

        self.ports_o = {}
        self.ports_i = {}

    def input_nets(self):
        nets = set()
        for value in self.ports_o.values():
            nets |= set(value)
        return nets

    def output_nets(self, self_idx: int):
        nets = set()
        for start, width in self.ports_i.values():
            for bit in range(start, start + width):
                nets.add(Net.from_cell(self_idx, bit))
        return nets

    def resolve_nets(self, netlist: Netlist):
        for port in self.ports_o:
            self.ports_o[port] = netlist.resolve_value(self.ports_o[port])

    def __repr__(self):
        ports = []
        for (name, (start, width)) in self.ports_i.items():
            ports.append(f" (input {name!r} {start}:{start+width})")
        for (name, val) in self.ports_o.items():
            ports.append(f" (output {name!r} {val})")
        ports = "".join(ports)
        return f"(top{ports})"

    def comb_edges_to(self, bit):
        return []


class Operator(Cell):
    """Roughly corresponds to ``hdl.ast.Operator``.

    The available operators are roughly the same as in AST, with some changes:

    - '<', '>', '<=', '>=', '//', '%', '>>' have signed and unsigned variants that are selected
      by prepending 'u' or 's' to operator name
    - 's', 'u', and unary '+' are redundant and do not exist
    - many operators restrict input widths to be the same as output width,
      and/or to be the same as each other

    The unary operators are:

    - '-', '~': like AST, input same width as output
    - 'b', 'r|', 'r&', 'r^': like AST, 1-bit output

    The binary operators are:

    - '+', '-', '*', '&', '^', '|', 'u//', 's//', 'u%', 's%': like AST, both inputs same width as output
    - '<<', 'u>>', 's>>': like AST, first input same width as output
    - '==', '!=', 'u<', 's<', 'u>', 's>', 'u<=', 's<=', 'u>=', 's>=': like AST, both inputs need to have
      the same width, 1-bit output

    The ternary operators are:

    - 'm': multiplexer, first input needs to have width of 1, second and third operand need to have
      the same width as output; implements arg0 ? arg1 : arg2

    Attributes
    ----------

    operator: str, symbol of the operator (from the above list)
    inputs: tuple of Value
    """

    def __init__(self, module_idx, *, operator: str, inputs, src_loc):
        super().__init__(module_idx, src_loc=src_loc)

        self.operator = operator
        self.inputs = tuple(Value(input) for input in inputs)

    @property
    def width(self):
        if self.operator in ('~', '-', '+', '*', '&', '^', '|', 'u//', 's//', 'u%', 's%', '<<', 'u>>', 's>>'):
            return len(self.inputs[0])
        elif self.operator in ('b', 'r&', 'r^', 'r|', '==', '!=', 'u<', 's<', 'u>', 's>', 'u<=', 's<=', 'u>=', 's>='):
            return 1
        elif self.operator == 'm':
            return len(self.inputs[1])
        else:
            assert False # :nocov:

    def input_nets(self):
        nets = set()
        for value in self.inputs:
            nets |= set(value)
        return nets

    def output_nets(self, self_idx: int):
        return {Net.from_cell(self_idx, bit) for bit in range(self.width)}

    def resolve_nets(self, netlist: Netlist):
        self.inputs = tuple(netlist.resolve_value(val) for val in self.inputs)

    def __repr__(self):
        inputs = " ".join(repr(input) for input in self.inputs)
        return f"({self.operator} {inputs})"

    def comb_edges_to(self, bit):
        if len(self.inputs) == 1:
            if self.operator == "~":
                yield (self.inputs[0][bit], self.src_loc)
            else:
                for net in self.inputs[0]:
                    yield (net, self.src_loc)
        elif len(self.inputs) == 2:
            if self.operator in ("&", "|", "^"):
                yield (self.inputs[0][bit], self.src_loc)
                yield (self.inputs[1][bit], self.src_loc)
            else:
                for net in self.inputs[0]:
                    yield (net, self.src_loc)
                for net in self.inputs[1]:
                    yield (net, self.src_loc)
        else:
            assert self.operator == "m"
            yield (self.inputs[0][0], self.src_loc)
            yield (self.inputs[1][bit], self.src_loc)
            yield (self.inputs[2][bit], self.src_loc)


class Part(Cell):
    """Corresponds to ``hdl.ast.Part``.

    Attributes
    ----------

    value: Value, the data input
    value_signed: bool
    offset: Value, the offset input
    width: int
    stride: int
    """
    def __init__(self, module_idx, *, value, value_signed, offset, width, stride, src_loc):
        super().__init__(module_idx, src_loc=src_loc)

        assert type(width) is int
        assert type(stride) is int

        self.value = Value(value)
        self.value_signed = value_signed
        self.offset = Value(offset)
        self.width = width
        self.stride = stride

    def input_nets(self):
        return set(self.value) | set(self.offset)

    def output_nets(self, self_idx: int):
        return {Net.from_cell(self_idx, bit) for bit in range(self.width)}

    def resolve_nets(self, netlist: Netlist):
        self.value = netlist.resolve_value(self.value)
        self.offset = netlist.resolve_value(self.offset)

    def __repr__(self):
        value_signed = "signed" if self.value_signed else "unsigned"
        return f"(part {self.value} {value_signed} {self.offset} {self.width} {self.stride})"

    def comb_edges_to(self, bit):
        for net in self.value:
            yield (net, self.src_loc)
        for net in self.offset:
            yield (net, self.src_loc)


class Match(Cell):
    """Used to represent a single switch on the control plane of processes.

    The output is the same length as ``patterns``. If ``en`` is ``0``, the output
    is all-0. Otherwise, the ``value`` is matched against all pattern sets
    in ``patterns``. The output has a ``1`` bit for the first pattern set that
    matches ``value``, and ``0`` for all other bits. If no pattern set matches
    the value, the output is all-``0``.

    Attributes
    ----------
    en: Net
    value: Value
    patterns: tuple of tuple of str, each str contains '0', '1', '-'
    """
    def __init__(self, module_idx, *, en, value, patterns, src_loc):
        super().__init__(module_idx, src_loc=src_loc)

        for pattern_list in patterns:
            for pattern in pattern_list:
                assert len(pattern) == len(value)
        self.en = Net.ensure(en)
        self.value = Value(value)
        self.patterns = patterns

    def input_nets(self):
        return set(self.value) | {self.en}

    def output_nets(self, self_idx: int):
        return {Net.from_cell(self_idx, bit) for bit in range(len(self.patterns))}

    def resolve_nets(self, netlist: Netlist):
        self.en = netlist.resolve_net(self.en)
        self.value = netlist.resolve_value(self.value)

    def __repr__(self):
        patterns = " ".join("{" + " ".join(pattern_list) + "}" if len(pattern_list) != 1 else pattern_list[0] for pattern_list in self.patterns)
        return f"(match {self.en} {self.value} {patterns})"

    def comb_edges_to(self, bit):
        yield (self.en, self.src_loc)
        for net in self.value:
            yield (net, self.src_loc)


class Assignment:
    """A single assignment in an ``AssignmentList``.

    The assignment is executed iff ``cond`` is true. When the assignment
    is executed, ``len(value)`` bits starting at position `offset` are set
    to the value ``value``, and the remaining bits are unchanged.
    Assignments to out-of-bounds bit indices are ignored.

    Attributes
    ----------

    cond: Net
    start: int
    value: Value
    src_loc: str
    """
    def __init__(self, *, cond, start, value, src_loc):
        assert isinstance(start, int)
        self.cond = Net.ensure(cond)
        self.start = start
        self.value = Value(value)
        self.src_loc = src_loc

    def resolve_nets(self, netlist: Netlist):
        self.cond = netlist.resolve_net(self.cond)
        self.value = netlist.resolve_value(self.value)

    def __repr__(self):
        end = self.start + len(self.value)
        return f"({self.cond} {self.start}:{end} {self.value})"


class AssignmentList(Cell):
    """Used to represent a single assigned signal on the data plane of processes.

    The output of this cell is determined by starting with the ``default`` value,
    then executing each assignment in sequence.

    Note: the RTLIL backend requires all ``cond`` inputs of assignments to be driven
    by a ``Match`` cell within the same module.

    Attributes
    ----------
    default: Value
    assignments: tuple of ``Assignment``
    """
    def __init__(self, module_idx, *, default, assignments, src_loc):
        super().__init__(module_idx, src_loc=src_loc)

        assignments = tuple(assignments)
        for assign in assignments:
            assert isinstance(assign, Assignment)

        self.default = Value(default)
        self.assignments: tuple[Assignment, ...] = assignments

    def input_nets(self):
        nets = set(self.default)
        for assign in self.assignments:
            nets.add(assign.cond)
            nets |= set(assign.value)
        return nets

    def output_nets(self, self_idx: int):
        return {Net.from_cell(self_idx, bit) for bit in range(len(self.default))}

    def resolve_nets(self, netlist: Netlist):
        for assign in self.assignments:
            assign.resolve_nets(netlist)
        self.default = netlist.resolve_value(self.default)

    def __repr__(self):
        assignments = " ".join(repr(assign) for assign in self.assignments)
        return f"(assignment_list {self.default} {assignments})"

    def comb_edges_to(self, bit):
        yield (self.default[bit], self.src_loc)
        for assign in self.assignments:
            if bit >= assign.start and bit < assign.start + len(assign.value):
                yield (assign.cond, assign.src_loc)
                yield (assign.value[bit - assign.start], assign.src_loc)


class FlipFlop(Cell):
    """A flip-flop. ``data`` is the data input. ``init`` is the initial and async reset value.
    ``clk`` and ``clk_edge`` work as in a ``ClockDomain``. ``arst`` is the async reset signal,
    or ``0`` if async reset is not used.

    Attributes
    ----------

    data: Value
    init: int
    clk: Net
    clk_edge: str, either 'pos' or 'neg'
    arst: Net
    attributes: dict from str to int, Const, or str
    """
    def __init__(self, module_idx, *, data, init, clk, clk_edge, arst, attributes, src_loc):
        super().__init__(module_idx, src_loc=src_loc)

        assert clk_edge in ('pos', 'neg')
        assert type(init) is int

        self.data = Value(data)
        self.init = init
        self.clk = Net.ensure(clk)
        self.clk_edge = clk_edge
        self.arst = Net.ensure(arst)
        self.attributes = attributes

    def input_nets(self):
        return set(self.data) | {self.clk, self.arst}

    def output_nets(self, self_idx: int):
        return {Net.from_cell(self_idx, bit) for bit in range(len(self.data))}

    def resolve_nets(self, netlist: Netlist):
        self.data = netlist.resolve_value(self.data)
        self.clk = netlist.resolve_net(self.clk)
        self.arst = netlist.resolve_net(self.arst)

    def __repr__(self):
        attributes = "".join(f" (attr {key} {val!r})" for key, val in self.attributes.items())
        return f"(flipflop {self.data} {self.init} {self.clk_edge} {self.clk} {self.arst}{attributes})"

    def comb_edges_to(self, bit):
        yield (self.clk, self.src_loc)
        yield (self.arst, self.src_loc)


class Memory(Cell):
    """Corresponds to ``Memory``.  ``init`` must have length equal to ``depth``.
    Read and write ports are separate cells.

    Attributes
    ----------

    width: int
    depth: int
    init: tuple of int
    name: str
    attributes: dict from str to int, Const, or str
    """
    def __init__(self, module_idx, *, width, depth, init, name, attributes, src_loc):
        super().__init__(module_idx, src_loc=src_loc)

        self.width = width
        self.depth = depth
        self.init = tuple(init)
        self.name = name
        self.attributes = attributes

    def input_nets(self):
        return set()

    def output_nets(self, self_idx: int):
        return set()

    def resolve_nets(self, netlist: Netlist):
        pass

    def __repr__(self):
        init = " ".join(str(x) for x in self.init)
        attributes = "".join(f" (attr {key} {val!r})" for key, val in self.attributes.items())
        return f"(memory {self.name!r} {self.width} {self.depth} ({init}) {attributes})"


class SyncWritePort(Cell):
    """A single write port of a memory.  This cell has no output.

    Attributes
    ----------

    memory: cell index of ``Memory``
    data: Value
    addr: Value
    en: Value
    clk: Net
    clk_edge: str, either 'pos' or 'neg'
    """
    def __init__(self, module_idx, memory, *, data, addr, en, clk, clk_edge, src_loc):
        super().__init__(module_idx, src_loc=src_loc)

        assert clk_edge in ('pos', 'neg')
        self.memory = memory
        self.data = Value(data)
        self.addr = Value(addr)
        self.en = Value(en)
        self.clk = Net.ensure(clk)
        self.clk_edge = clk_edge

    def input_nets(self):
        return set(self.data) | set(self.addr) | set(self.en) | {self.clk}

    def output_nets(self, self_idx: int):
        return set()

    def resolve_nets(self, netlist: Netlist):
        self.data = netlist.resolve_value(self.data)
        self.addr = netlist.resolve_value(self.addr)
        self.en = netlist.resolve_value(self.en)
        self.clk = netlist.resolve_net(self.clk)

    def __repr__(self):
        return f"(write_port {self.memory} {self.data} {self.addr} {self.en} {self.clk_edge} {self.clk})"


class AsyncReadPort(Cell):
    """A single asynchronous read port of a memory.

    Attributes
    ----------

    memory: cell index of ``Memory``
    width: int
    addr: Value
    """
    def __init__(self, module_idx, memory, *, width, addr, src_loc):
        super().__init__(module_idx, src_loc=src_loc)

        self.memory = memory
        self.width = width
        self.addr = Value(addr)

    def input_nets(self):
        return set(self.addr)

    def output_nets(self, self_idx: int):
        return {Net.from_cell(self_idx, bit) for bit in range(self.width)}

    def resolve_nets(self, netlist: Netlist):
        self.addr = netlist.resolve_value(self.addr)

    def __repr__(self):
        return f"(read_port {self.memory} {self.width} {self.addr})"

    def comb_edges_to(self, bit):
        for net in self.addr:
            yield (net, self.src_loc)


class SyncReadPort(Cell):
    """A single synchronous read port of a memory.  The cell output is the data port.
    ``transparent_for`` is the set of write ports (identified by cell index) that this
    read port is transparent with.

    Attributes
    ----------

    memory: cell index of ``Memory``
    width: int
    addr: Value
    en: Net
    clk: Net
    clk_edge: str, either 'pos' or 'neg'
    transparent_for: tuple of int
    """
    def __init__(self, module_idx, memory, *, width, addr, en, clk, clk_edge, transparent_for, src_loc):
        super().__init__(module_idx, src_loc=src_loc)

        assert clk_edge in ('pos', 'neg')
        self.memory = memory
        self.width = width
        self.addr = Value(addr)
        self.en = Net.ensure(en)
        self.clk = Net.ensure(clk)
        self.clk_edge = clk_edge
        self.transparent_for = tuple(transparent_for)

    def input_nets(self):
        return set(self.addr) | {self.en, self.clk}

    def output_nets(self, self_idx: int):
        return {Net.from_cell(self_idx, bit) for bit in range(self.width)}

    def resolve_nets(self, netlist: Netlist):
        self.addr = netlist.resolve_value(self.addr)
        self.en = netlist.resolve_net(self.en)
        self.clk = netlist.resolve_net(self.clk)

    def __repr__(self):
        transparent_for = " ".join(str(port) for port in self.transparent_for)
        return f"(read_port {self.memory} {self.width} {self.addr} {self.en} {self.clk_edge} {self.clk} ({transparent_for}))"

    def comb_edges_to(self, bit):
        return []


class AsyncPrint(Cell):
    """Corresponds to ``Print`` in the "comb" domain.

    Attributes
    ----------

    en: Net
    format: Format
    """
    def __init__(self, module_idx, *, en, format, src_loc):
        super().__init__(module_idx, src_loc=src_loc)

        assert isinstance(format, Format)
        self.en = Net.ensure(en)
        self.format = format

    def input_nets(self):
        return {self.en} | self.format.input_nets()

    def output_nets(self, self_idx: int):
        return set()

    def resolve_nets(self, netlist: Netlist):
        self.en = netlist.resolve_net(self.en)
        self.format.resolve_nets(netlist)

    def __repr__(self):
        return f"(print {self.en} {self.format!r})"


class SyncPrint(Cell):
    """Corresponds to ``Print`` in domains other than "comb".

    Attributes
    ----------

    en: Net
    clk: Net
    clk_edge: str, either 'pos' or 'neg'
    format: Format
    """

    def __init__(self, module_idx, *, en, clk, clk_edge, format, src_loc):
        super().__init__(module_idx, src_loc=src_loc)

        assert clk_edge in ('pos', 'neg')
        assert isinstance(format, Format)
        self.en = Net.ensure(en)
        self.clk = Net.ensure(clk)
        self.clk_edge = clk_edge
        self.format = format

    def input_nets(self):
        return {self.en, self.clk} | self.format.input_nets()

    def output_nets(self, self_idx: int):
        return set()

    def resolve_nets(self, netlist: Netlist):
        self.en = netlist.resolve_net(self.en)
        self.clk = netlist.resolve_net(self.clk)
        self.format.resolve_nets(netlist)

    def __repr__(self):
        return f"(print {self.en} {self.clk_edge} {self.clk} {self.format!r})"


class Initial(Cell):
    """Corresponds to ``Initial`` value."""

    def input_nets(self):
        return set()

    def output_nets(self, self_idx: int):
        return {Net.from_cell(self_idx, 0)}

    def resolve_nets(self, netlist: Netlist):
        pass

    def __repr__(self):
        return f"(initial)"

    def comb_edges_to(self, bit):
        return []


class AnyValue(Cell):
    """Corresponds to ``AnyConst`` or ``AnySeq``. ``kind`` must be either ``'anyconst'``
    or ``'anyseq'``.

    Attributes
    ----------

    kind: str, 'anyconst' or 'anyseq'
    width: int
    """
    def __init__(self, module_idx, *, kind, width, src_loc):
        super().__init__(module_idx, src_loc=src_loc)

        assert kind in ('anyconst', 'anyseq')
        self.kind = kind
        self.width = width

    def input_nets(self):
        return set()

    def output_nets(self, self_idx: int):
        return {Net.from_cell(self_idx, bit) for bit in range(self.width)}

    def resolve_nets(self, netlist: Netlist):
        pass

    def __repr__(self):
        return f"({self.kind} {self.width})"

    def comb_edges_to(self, bit):
        return []


class AsyncProperty(Cell):
    """Corresponds to ``Assert``, ``Assume``, or ``Cover`` in the "comb" domain.

    Attributes
    ----------

    kind: str, either 'assert', 'assume', or 'cover'
    test: Net
    en: Net
    format: Format or None
    """
    def __init__(self, module_idx, *, kind, test, en, format, src_loc):
        super().__init__(module_idx, src_loc=src_loc)

        assert format is None or isinstance(format, Format)
        assert kind in ('assert', 'assume', 'cover')
        self.kind = kind
        self.test = Net.ensure(test)
        self.en = Net.ensure(en)
        self.format = format

    def input_nets(self):
        if self.format is None:
            return {self.test, self.en}
        else:
            return {self.test, self.en} | self.format.input_nets()

    def output_nets(self, self_idx: int):
        return set()

    def resolve_nets(self, netlist: Netlist):
        self.test = netlist.resolve_net(self.test)
        self.en = netlist.resolve_net(self.en)
        if self.format is not None:
            self.format.resolve_nets(netlist)

    def __repr__(self):
        return f"({self.kind} {self.test} {self.en} {self.format!r})"


class SyncProperty(Cell):
    """Corresponds to ``Assert``, ``Assume``, or ``Cover`` in domains other than "comb".

    Attributes
    ----------

    kind: str, either 'assert', 'assume', or 'cover'
    test: Net
    en: Net
    clk: Net
    clk_edge: str, either 'pos' or 'neg'
    format: Format or None
    """

    def __init__(self, module_idx, *, kind, test, en, clk, clk_edge, format, src_loc):
        super().__init__(module_idx, src_loc=src_loc)

        assert format is None or isinstance(format, Format)
        assert kind in ('assert', 'assume', 'cover')
        assert clk_edge in ('pos', 'neg')
        self.kind = kind
        self.test = Net.ensure(test)
        self.en = Net.ensure(en)
        self.clk = Net.ensure(clk)
        self.clk_edge = clk_edge
        self.format = format

    def input_nets(self):
        if self.format is None:
            return {self.test, self.en, self.clk}
        else:
            return {self.test, self.en, self.clk} | self.format.input_nets()

    def output_nets(self, self_idx: int):
        return set()

    def resolve_nets(self, netlist: Netlist):
        self.test = netlist.resolve_net(self.test)
        self.en = netlist.resolve_net(self.en)
        self.clk = netlist.resolve_net(self.clk)
        if self.format is not None:
            self.format.resolve_nets(netlist)

    def __repr__(self):
        return f"({self.kind} {self.test} {self.en} {self.clk_edge} {self.clk} {self.format!r})"


class Instance(Cell):
    """Corresponds to ``Instance``. ``type``, ``parameters`` and ``attributes`` work the same as in
    ``Instance``. Input and inout ports are represented as a dict of port names to values.
    Inout ports must be connected to nets corresponding to an IO port of the ``Top`` cell.

    Output ports are represented as a dict of port names to (start bit index, width) describing
    their position in the virtual "output" of this cell.

    Attributes
    ----------

    type: str
    name: str
    parameters: dict of str to Const, int, or str
    attributes: dict of str to Const, int, or str
    ports_i: dict of str to Value
    ports_o: dict of str to pair of int (index start, width)
    ports_io: dict of str to (IOValue, IODirection)
    """

    def __init__(self, module_idx, *, type, name, parameters, attributes, ports_i, ports_o, ports_io, src_loc):
        super().__init__(module_idx, src_loc=src_loc)

        self.type = type
        self.name = name
        self.parameters = parameters
        self.attributes = attributes
        self.ports_i = {name: Value(val) for name, val in ports_i.items()}
        self.ports_o = ports_o
        self.ports_io = {name: (IOValue(val), IODirection(dir)) for name, (val, dir) in ports_io.items()}

    def input_nets(self):
        nets = set()
        for val in self.ports_i.values():
            nets |= set(val)
        return nets

    def output_nets(self, self_idx: int):
        nets = set()
        for start, width in self.ports_o.values():
            for bit in range(start, start + width):
                nets.add(Net.from_cell(self_idx, bit))
        return nets

    def io_nets(self):
        nets = set()
        for val, dir in self.ports_io.values():
            nets |= {(net, dir) for net in val}
        return nets

    def resolve_nets(self, netlist: Netlist):
        for port in self.ports_i:
            self.ports_i[port] = netlist.resolve_value(self.ports_i[port])

    def __repr__(self):
        items = []
        for name, val in self.parameters.items():
            items.append(f"(param {name!r} {val!r})")
        for name, val in self.attributes.items():
            items.append(f"(attr {name!r} {val!r})")
        for name, val in self.ports_i.items():
            items.append(f"(input {name!r} {val})")
        for name, (start, width) in self.ports_o.items():
            items.append(f"(output {name!r} {start}:{start+width})")
        for name, (val, dir) in self.ports_io.items():
            items.append(f"(io {dir.value} {name!r} {val})")
        items = " ".join(items)
        return f"(instance {self.type!r} {self.name!r} {items})"

    def comb_edges_to(self, bit):
        # don't ask me, I'm a housecat
        return []


class IOBuffer(Cell):
    """An IO buffer cell. This cell does two things:

    - a tristate buffer is inserted driving ``port`` based on ``o`` and ``oe`` nets (output buffer)
    - the value of ``port`` is sampled and made available as output of this cell (input buffer)

    Attributes
    ----------

    port: IOValue
    dir: IODirection
    o: Value or None
    oe: Net or None
    """
    def __init__(self, module_idx, *, port, dir, o=None, oe=None, src_loc):
        super().__init__(module_idx, src_loc=src_loc)

        self.port = IOValue(port)
        self.dir = IODirection(dir)
        if self.dir is IODirection.Input:
            assert o is None
            assert oe is None
            self.o = None
            self.oe = None
        else:
            self.o = Value(o)
            self.oe = Net.ensure(oe)

    def input_nets(self):
        if self.dir is IODirection.Input:
            return set()
        else:
            return set(self.o) | {self.oe}

    def output_nets(self, self_idx: int):
        if self.dir is IODirection.Output:
            return set()
        else:
            return {Net.from_cell(self_idx, bit) for bit in range(len(self.port))}

    def io_nets(self):
        return {(net, self.dir) for net in self.port}

    def resolve_nets(self, netlist: Netlist):
        if self.dir is not IODirection.Input:
            self.o = netlist.resolve_value(self.o)
            self.oe = netlist.resolve_net(self.oe)

    def __repr__(self):
        if self.dir is IODirection.Input:
            return f"(iob {self.dir.value} {self.port})"
        else:
            return f"(iob {self.dir.value} {self.port} {self.o} {self.oe})"

    def comb_edges_to(self, bit):
        if self.dir is not IODirection.Input:
            yield (self.o[bit], self.src_loc)
            yield (self.oe, self.src_loc)

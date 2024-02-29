from typing import Iterable
import enum

from ._ast import SignalDict


__all__ = [
    # Netlist core
    "Net", "Value", "Netlist", "ModuleNetFlow", "Module", "Cell", "Top",
    # Computation cells
    "Operator", "Part", "ArrayMux",
    # Decision tree cells
    "Matches", "PriorityMatch", "Assignment", "AssignmentList",
    # Storage cells
    "FlipFlop", "Memory", "SyncWritePort", "AsyncReadPort", "SyncReadPort",
    # Formal verification cells
    "Initial", "AnyValue", "AsyncProperty", "SyncProperty",
    # Foreign interface cells
    "Instance", "IOBuffer",
]


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
            return "(0'd0)"
        elif len(chunks) == 1:
            return chunks[0]
        else:
            return f"(cat {' '.join(chunks)})"

    __str__ = __repr__


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

    cells : list of ``Cell``
    connections : dict of (negative) int to int
    signals : dict of Signal to ``Value``
    """
    def __init__(self):
        self.modules: list[Module] = []
        self.cells: list[Cell] = [Top()]
        self.connections: dict[Net, Net] = {}
        self.signals = SignalDict()
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

    def __repr__(self):
        result = ["("]
        for module_idx, module in enumerate(self.modules):
            name = " ".join(repr(name) for name in module.name)
            ports = " ".join(
                f"({flow.value} {name!r} {val})"
                for name, (val, flow) in module.ports.items()
            )
            result.append(f"(module {module_idx} {module.parent} ({name}) {ports})")
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

    def alloc_late_value(self, width: int):
        self.last_late_net -= width
        return Value(Net.from_late(self.last_late_net + bit) for bit in range(width))

    @property
    def top(self):
        top = self.cells[0]
        assert isinstance(top, Top)
        return top


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

    #: The net is a special top-level inout net that is used within
    #: this module or its submodules.  It is an inout port of this module.
    Inout    = "inout"


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
    ports: a dict from port name to (Value, NetFlow) pair
    cells: a list of cell indices that belong to this module
    """
    def __init__(self, parent, name, *, src_loc, cell_src_loc):
        self.parent = parent
        self.name = name
        self.src_loc = src_loc
        self.cell_src_loc = cell_src_loc
        self.submodules = []
        self.signal_names = SignalDict()
        self.net_flow = {}
        self.ports = {}
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

    def resolve_nets(self, netlist: Netlist):
        raise NotImplementedError


class Top(Cell):
    """A special cell type representing top-level ports. Must be present in the netlist exactly
    once, at index 0.

    Top-level outputs are stored as a dict of names to their assigned values.

    Top-level inputs and inouts are effectively the output of this cell. They are both stored
    as a dict of names to a (start bit index, width) tuple. Output bit indices 0 and 1 are reserved
    for constant nets, so the lowest bit index that can be assigned to a port is 2.

    Top-level inouts are special and can only be used by inout ports of instances, or in the pad
    value of an ``IoBuf`` cell.

    Attributes
    ----------

    ports_o: dict of str to Value
    ports_i: dict of str to (int, int)
    ports_io: dict of str to (int, int)
    """
    def __init__(self):
        super().__init__(module_idx=0, src_loc=None)

        self.ports_o = {}
        self.ports_i = {}
        self.ports_io = {}

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
        for start, width in self.ports_io.values():
            for bit in range(start, start + width):
                nets.add(Net.from_cell(self_idx, bit))
        return nets

    def resolve_nets(self, netlist: Netlist):
        for port in self.ports_o:
            self.ports_o[port] = netlist.resolve_value(self.ports_o[port])

    def __repr__(self):
        ports = []
        for (name, (start, width)) in self.ports_i.items():
            ports.append(f"(input {name!r} {start}:{start+width})")
        for (name, val) in self.ports_o.items():
            ports.append(f"(output {name!r} {val})")
        for (name, (start, width)) in self.ports_io.items():
            ports.append(f"(inout {name!r} {start}:{start+width})")
        ports = " ".join(ports)
        return f"(top {ports})"


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

    - 'm': like AST, first input needs to have width of 1, second and third operand need to have the same
      width as output

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


class ArrayMux(Cell):
    """Corresponds to ``hdl.ast.ArrayProxy``. All values in the ``elems`` array need to have
    the same width as the output.

    Attributes
    ----------

    width: int (width of output and all inputs)
    elems: tuple of Value
    index: Value
    """
    def __init__(self, module_idx, *, width, elems, index, src_loc):
        super().__init__(module_idx, src_loc=src_loc)

        self.width = width
        self.elems = tuple(Value(val) for val in elems)
        self.index = Value(index)

    def input_nets(self):
        nets = set(self.index)
        for value in self.elems:
            nets |= set(value)
        return nets

    def output_nets(self, self_idx: int):
        return {Net.from_cell(self_idx, bit) for bit in range(self.width)}

    def resolve_nets(self, netlist: Netlist):
        self.elems = tuple(netlist.resolve_value(val) for val in self.elems)
        self.index = netlist.resolve_value(self.index)

    def __repr__(self):
        elems = " ".join(repr(elem) for elem in self.elems)
        return f"(array_mux {self.width} {self.index} ({elems}))"


class Matches(Cell):
    """A combinatorial cell performing a comparison like ``Value.matches``
    (or, equivalently, a case condition).

    Attributes
    ----------

    value: Value
    patterns: tuple of str, each str contains '0', '1', '-'
    """
    def __init__(self, module_idx, *, value, patterns, src_loc):
        super().__init__(module_idx, src_loc=src_loc)

        self.value = Value(value)
        self.patterns = tuple(patterns)

    def input_nets(self):
        return set(self.value)

    def output_nets(self, self_idx: int):
        return {Net.from_cell(self_idx, 0)}

    def resolve_nets(self, netlist: Netlist):
        self.value = netlist.resolve_value(self.value)

    def __repr__(self):
        patterns = " ".join(self.patterns)
        return f"(matches {self.value} {patterns})"


class PriorityMatch(Cell):
    """Used to represent a single switch on the control plane of processes.

    The output is the same length as ``inputs``. If ``en`` is ``0``, the output
    is all-0. Otherwise, output keeps the lowest-numbered ``1`` bit in the input
    (if any) and masks all other bits to ``0``.

    Note: the RTLIL backend requires all bits of ``inputs`` to be driven
    by a ``Match`` cell within the same module.

    Attributes
    ----------
    en: Net
    inputs: Value
    """
    def __init__(self, module_idx, *, en, inputs, src_loc):
        super().__init__(module_idx, src_loc=src_loc)

        self.en = Net.ensure(en)
        self.inputs = Value(inputs)

    def input_nets(self):
        return set(self.inputs) | {self.en}

    def output_nets(self, self_idx: int):
        return {Net.from_cell(self_idx, bit) for bit in range(len(self.inputs))}

    def resolve_nets(self, netlist: Netlist):
        self.en = netlist.resolve_net(self.en)
        self.inputs = netlist.resolve_value(self.inputs)

    def __repr__(self):
        return f"(priority_match {self.en} {self.inputs})"


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
    by a ``PriorityMatch`` cell within the same module.

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


class AsyncProperty(Cell):
    """Corresponds to ``Assert``, ``Assume``, or ``Cover`` in the "comb" domain.

    Attributes
    ----------

    kind: str, either 'assert', 'assume', or 'cover'
    test: Net
    en: Net
    name: str
    """
    def __init__(self, module_idx, *, kind, test, en, name, src_loc):
        super().__init__(module_idx, src_loc=src_loc)

        assert kind in ('assert', 'assume', 'cover')
        self.kind = kind
        self.test = Net.ensure(test)
        self.en = Net.ensure(en)
        self.name = name

    def input_nets(self):
        return {self.test, self.en}

    def output_nets(self, self_idx: int):
        return set()

    def resolve_nets(self, netlist: Netlist):
        self.test = netlist.resolve_net(self.test)
        self.en = netlist.resolve_net(self.en)

    def __repr__(self):
        return f"({self.kind} {self.name!r} {self.test} {self.en})"


class SyncProperty(Cell):
    """Corresponds to ``Assert``, ``Assume``, or ``Cover`` in domains other than "comb".

    Attributes
    ----------

    kind: str, either 'assert', 'assume', or 'cover'
    test: Net
    en: Net
    clk: Net
    clk_edge: str, either 'pos' or 'neg'
    name: str
    """

    def __init__(self, module_idx, *, kind, test, en, clk, clk_edge, name, src_loc):
        super().__init__(module_idx, src_loc=src_loc)

        assert kind in ('assert', 'assume', 'cover')
        assert clk_edge in ('pos', 'neg')
        self.kind = kind
        self.test = Net.ensure(test)
        self.en = Net.ensure(en)
        self.clk = Net.ensure(clk)
        self.clk_edge = clk_edge
        self.name = name

    def input_nets(self):
        return {self.test, self.en, self.clk}

    def output_nets(self, self_idx: int):
        return set()

    def resolve_nets(self, netlist: Netlist):
        self.test = netlist.resolve_net(self.test)
        self.en = netlist.resolve_net(self.en)
        self.clk = netlist.resolve_net(self.clk)

    def __repr__(self):
        return f"({self.kind} {self.name!r} {self.test} {self.en} {self.clk_edge} {self.clk})"


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
    ports_io: dict of str to Value
    """

    def __init__(self, module_idx, *, type, name, parameters, attributes, ports_i, ports_o, ports_io, src_loc):
        super().__init__(module_idx, src_loc=src_loc)

        self.type = type
        self.name = name
        self.parameters = parameters
        self.attributes = attributes
        self.ports_i = {name: Value(val) for name, val in ports_i.items()}
        self.ports_o = ports_o
        self.ports_io = {name: Value(val) for name, val in ports_io.items()}

    def input_nets(self):
        nets = set()
        for val in self.ports_i.values():
            nets |= set(val)
        for val in self.ports_io.values():
            nets |= set(val)
        return nets

    def output_nets(self, self_idx: int):
        nets = set()
        for start, width in self.ports_o.values():
            for bit in range(start, start + width):
                nets.add(Net.from_cell(self_idx, bit))
        return nets

    def resolve_nets(self, netlist: Netlist):
        for port in self.ports_i:
            self.ports_i[port] = netlist.resolve_value(self.ports_i[port])
        for port in self.ports_io:
            self.ports_io[port] = netlist.resolve_value(self.ports_io[port])

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
        for name, val in self.ports_io.items():
            items.append(f"(inout {name!r} {val})")
        items = " ".join(items)
        return f"(instance {self.type!r} {self.name!r} {items})"


class IOBuffer(Cell):
    """An IO buffer cell. ``pad`` must be connected to nets corresponding to an IO port
    of the ``Top`` cell. This cell does two things:

    - a tristate buffer is inserted driving ``pad`` based on ``o`` and ``oe`` nets (output buffer)
    - the value of ``pad`` is sampled and made available as output of this cell (input buffer)

    Attributes
    ----------

    pad: Value
    o: Value
    oe: Net
    """
    def __init__(self, module_idx, *, pad, o, oe, src_loc):
        super().__init__(module_idx, src_loc=src_loc)

        self.pad = Value(pad)
        self.o = Value(o)
        self.oe = Net.ensure(oe)

    def input_nets(self):
        return set(self.pad) | set(self.o) | {self.oe}

    def output_nets(self, self_idx: int):
        return {Net.from_cell(self_idx, bit) for bit in range(len(self.pad))}

    def resolve_nets(self, netlist: Netlist):
        self.pad = netlist.resolve_value(self.pad)
        self.o = netlist.resolve_value(self.o)
        self.oe = netlist.resolve_net(self.oe)

    def __repr__(self):
        return f"(iob {self.pad} {self.o} {self.oe})"

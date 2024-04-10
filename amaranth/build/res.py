from collections import OrderedDict

from ..hdl import *
from ..hdl._ast import SignalDict
from ..lib import wiring, io

from .dsl import *


__all__ = ["ResourceError", "ResourceManager"]


class ResourceError(Exception):
    pass


class PortGroup:
    pass


class PortMetadata:
    def __init__(self, name, attrs):
        self.name = name
        self.attrs = attrs


class PinBuffer(Elaboratable):
    def __init__(self, pin, port):
        if pin.xdr not in (0, 1, 2):
            raise ValueError(f"Unsupported 'xdr' value {pin.xdr}")
        self.pin = pin
        self.port = port

    def elaborate(self, platform):
        m = Module()

        if self.pin.dir == "i":
            if self.pin.xdr == 0:
                m.submodules.buf = buf = io.Buffer(io.Direction.Input, self.port)
                m.d.comb += self.pin.i.eq(buf.i)
            elif self.pin.xdr == 1:
                m.domains.input = cd_input = ClockDomain(reset_less=True)
                m.submodules.buf = buf = io.FFBuffer(io.Direction.Input, self.port, i_domain="input")
                m.d.comb += self.pin.i.eq(buf.i)
                m.d.comb += cd_input.clk.eq(self.pin.i_clk)
            elif self.pin.xdr == 2:
                m.domains.input = cd_input = ClockDomain(reset_less=True)
                m.submodules.buf = buf = io.DDRBuffer(io.Direction.Input, self.port, i_domain="input")
                m.d.comb += self.pin.i0.eq(buf.i[0])
                m.d.comb += self.pin.i1.eq(buf.i[1])
                m.d.comb += cd_input.clk.eq(self.pin.i_clk)
        if self.pin.dir in ("o", "oe"):
            if self.pin.xdr == 0:
                m.submodules.buf = buf = io.Buffer(io.Direction.Output, self.port)
                m.d.comb += buf.o.eq(self.pin.o)
            elif self.pin.xdr == 1:
                m.domains.output = cd_output = ClockDomain(reset_less=True)
                m.submodules.buf = buf = io.FFBuffer(io.Direction.Output, self.port, o_domain="output")
                m.d.comb += buf.o.eq(self.pin.o)
                m.d.comb += cd_output.clk.eq(self.pin.o_clk)
            elif self.pin.xdr == 2:
                m.domains.output = cd_output = ClockDomain(reset_less=True)
                m.submodules.buf = buf = io.DDRBuffer(io.Direction.Output, self.port, o_domain="output")
                m.d.comb += buf.o[0].eq(self.pin.o0)
                m.d.comb += buf.o[1].eq(self.pin.o1)
                m.d.comb += cd_output.clk.eq(self.pin.o_clk)
            if self.pin.dir == "oe":
                m.d.comb += buf.oe.eq(self.pin.oe)
        if self.pin.dir == "io":
            if self.pin.xdr == 0:
                m.submodules.buf = buf = io.Buffer(io.Direction.Bidir, self.port)
                m.d.comb += self.pin.i.eq(buf.i)
                m.d.comb += buf.o.eq(self.pin.o)
                m.d.comb += buf.oe.eq(self.pin.oe)
            elif self.pin.xdr == 1:
                m.domains.input = cd_input = ClockDomain(reset_less=True)
                m.domains.output = cd_output = ClockDomain(reset_less=True)
                m.submodules.buf = buf = io.FFBuffer(io.Direction.Bidir, self.port, i_domain="input", o_domain="output")
                m.d.comb += self.pin.i.eq(buf.i)
                m.d.comb += buf.o.eq(self.pin.o)
                m.d.comb += buf.oe.eq(self.pin.oe)
                m.d.comb += cd_input.clk.eq(self.pin.i_clk)
                m.d.comb += cd_output.clk.eq(self.pin.o_clk)
            elif self.pin.xdr == 2:
                m.domains.input = cd_input = ClockDomain(reset_less=True)
                m.domains.output = cd_output = ClockDomain(reset_less=True)
                m.submodules.buf = buf = io.DDRBuffer(io.Direction.Bidir, self.port, i_domain="input", o_domain="output")
                m.d.comb += self.pin.i0.eq(buf.i[0])
                m.d.comb += self.pin.i1.eq(buf.i[1])
                m.d.comb += buf.o[0].eq(self.pin.o0)
                m.d.comb += buf.o[1].eq(self.pin.o1)
                m.d.comb += buf.oe.eq(self.pin.oe)
                m.d.comb += cd_input.clk.eq(self.pin.i_clk)
                m.d.comb += cd_output.clk.eq(self.pin.o_clk)

        return m


class ResourceManager:
    def __init__(self, resources, connectors):
        self.resources  = OrderedDict()
        self._requested = OrderedDict()
        self._phys_reqd = OrderedDict()

        self.connectors = OrderedDict()
        self._conn_pins = OrderedDict()

        # List of all IOPort instances created
        self._ports     = []
        # List of (pin, port, buffer) pairs for non-dir="-" requests.
        self._pins      = []
        # Constraint list
        self._clocks    = SignalDict()

        self.add_resources(resources)
        self.add_connectors(connectors)

    def add_resources(self, resources):
        for res in resources:
            if not isinstance(res, Resource):
                raise TypeError(f"Object {res!r} is not a Resource")
            if (res.name, res.number) in self.resources:
                raise NameError("Trying to add {!r}, but {!r} has the same name and number"
                                .format(res, self.resources[res.name, res.number]))
            self.resources[res.name, res.number] = res

    def add_connectors(self, connectors):
        for conn in connectors:
            if not isinstance(conn, Connector):
                raise TypeError(f"Object {conn!r} is not a Connector")
            if (conn.name, conn.number) in self.connectors:
                raise NameError("Trying to add {!r}, but {!r} has the same name and number"
                                .format(conn, self.connectors[conn.name, conn.number]))
            self.connectors[conn.name, conn.number] = conn

            for conn_pin, plat_pin in conn:
                assert conn_pin not in self._conn_pins
                self._conn_pins[conn_pin] = plat_pin

    def lookup(self, name, number=0):
        if (name, number) not in self.resources:
            raise ResourceError("Resource {}#{} does not exist"
                                  .format(name, number))
        return self.resources[name, number]

    def request(self, name, number=0, *, dir=None, xdr=None):
        resource = self.lookup(name, number)
        if (resource.name, resource.number) in self._requested:
            raise ResourceError("Resource {}#{} has already been requested"
                                .format(name, number))

        def merge_options(subsignal, dir, xdr):
            if isinstance(subsignal.ios[0], Subsignal):
                if dir is None:
                    dir = dict()
                if xdr is None:
                    xdr = dict()
                if not isinstance(dir, dict):
                    raise TypeError("Directions must be a dict, not {!r}, because {!r} "
                                    "has subsignals"
                                    .format(dir, subsignal))
                if not isinstance(xdr, dict):
                    raise TypeError("Data rate must be a dict, not {!r}, because {!r} "
                                    "has subsignals"
                                    .format(xdr, subsignal))
                for sub in subsignal.ios:
                    sub_dir = dir.get(sub.name, None)
                    sub_xdr = xdr.get(sub.name, None)
                    dir[sub.name], xdr[sub.name] = merge_options(sub, sub_dir, sub_xdr)
            else:
                if dir is None:
                    dir = subsignal.ios[0].dir
                if xdr is None:
                    xdr = 0
                if dir not in ("i", "o", "oe", "io", "-"):
                    raise TypeError("Direction must be one of \"i\", \"o\", \"oe\", \"io\", "
                                    "or \"-\", not {!r}"
                                    .format(dir))
                if dir != subsignal.ios[0].dir and \
                        not (subsignal.ios[0].dir == "io" or dir == "-"):
                    raise ValueError("Direction of {!r} cannot be changed from \"{}\" to \"{}\"; "
                                     "direction can be changed from \"io\" to \"i\", \"o\", or "
                                     "\"oe\", or from anything to \"-\""
                                     .format(subsignal.ios[0], subsignal.ios[0].dir, dir))
                if not isinstance(xdr, int) or xdr < 0:
                    raise ValueError("Data rate of {!r} must be a non-negative integer, not {!r}"
                                     .format(subsignal.ios[0], xdr))
            return dir, xdr

        def resolve(resource, dir, xdr, path, attrs):
            for attr_key, attr_value in attrs.items():
                if hasattr(attr_value, "__call__"):
                    attr_value = attr_value(self)
                    assert attr_value is None or isinstance(attr_value, str)
                if attr_value is None:
                    del attrs[attr_key]
                else:
                    attrs[attr_key] = attr_value

            if isinstance(resource.ios[0], Subsignal):
                res = PortGroup()
                for sub in resource.ios:
                    member = resolve(sub, dir[sub.name], xdr[sub.name],
                                               path=path + (sub.name,),
                                               attrs={**attrs, **sub.attrs})
                    setattr(res, sub.name, member)
                return res

            elif isinstance(resource.ios[0], (Pins, DiffPairs)):
                phys = resource.ios[0]
                if phys.dir == "oe":
                    direction = "o"
                else:
                    direction = phys.dir
                if isinstance(phys, Pins):
                    phys_names = phys.map_names(self._conn_pins, resource)
                    iop = IOPort(len(phys), name="__".join(path) + "__io", metadata=[
                        PortMetadata(name, attrs)
                        for name in phys_names
                    ])
                    self._ports.append(iop)
                    port = io.SingleEndedPort(iop, invert=phys.invert, direction=direction)
                if isinstance(phys, DiffPairs):
                    phys_names_p = phys.p.map_names(self._conn_pins, resource)
                    phys_names_n = phys.n.map_names(self._conn_pins, resource)
                    phys_names = phys_names_p + phys_names_n
                    p = IOPort(len(phys), name="__".join(path) + "__p", metadata=[
                        PortMetadata(name, attrs)
                        for name in phys_names_p
                    ])
                    n = IOPort(len(phys), name="__".join(path) + "__n", metadata=[
                        PortMetadata(name, attrs)
                        for name in phys_names_n
                    ])
                    self._ports += [p, n]
                    port = io.DifferentialPort(p, n, invert=phys.invert, direction=direction)

                for phys_name in phys_names:
                    if phys_name in self._phys_reqd:
                        raise ResourceError("Resource component {} uses physical pin {}, but it "
                                            "is already used by resource component {} that was "
                                            "requested earlier"
                                            .format(".".join(path), phys_name,
                                                    ".".join(self._phys_reqd[phys_name])))
                    self._phys_reqd[phys_name] = path

                if dir == "-":
                    return port
                else:
                    pin = wiring.flipped(io.Pin(len(phys), dir, xdr=xdr, path=path))
                    buffer = PinBuffer(pin, port)
                    self._pins.append((pin, port, buffer))

                    if resource.clock is not None:
                        self.add_clock_constraint(pin.i, resource.clock.frequency)
                    return pin

            else:
                assert False # :nocov:

        value = resolve(resource,
            *merge_options(resource, dir, xdr),
            path=(f"{resource.name}_{resource.number}",),
            attrs=resource.attrs)
        self._requested[resource.name, resource.number] = value
        return value

    def iter_pins(self):
        yield from self._pins

    def iter_ports(self):
        yield from self._ports

    def iter_port_constraints_bits(self):
        for port in self._ports:
            if len(port) == 1:
                yield port.name, port.metadata[0].name, port.metadata[0].attrs
            else:
                for bit, meta in enumerate(port.metadata):
                    yield f"{port.name}[{bit}]", meta.name, meta.attrs

    def add_clock_constraint(self, clock, frequency):
        if isinstance(clock, ClockSignal):
            raise TypeError(f"A clock constraint can only be applied to a Signal, but a "
                            f"ClockSignal is provided; assign the ClockSignal to an "
                            f"intermediate signal and constrain the latter instead.")
        elif not isinstance(clock, Signal):
            raise TypeError(f"Object {clock!r} is not a Signal")
        if not isinstance(frequency, (int, float)):
            raise TypeError(f"Frequency must be a number, not {frequency!r}")

        if clock in self._clocks:
            raise ValueError("Cannot add clock constraint on {!r}, which is already constrained "
                             "to {} Hz"
                             .format(clock, self._clocks[clock]))
        else:
            self._clocks[clock] = float(frequency)

    def iter_clock_constraints(self):
        # Back-propagate constraints through the input buffer. For clock constraints on pins
        # (the majority of cases), toolchains work better if the constraint is defined on the pin
        # and not on the buffered internal net; and if the toolchain is advanced enough that
        # it considers clock phase and delay of the input buffer, it is *necessary* to define
        # the constraint on the pin to match the designer's expectation of phase being referenced
        # to the pin.
        #
        # Constraints on nets with no corresponding input pin (e.g. PLL or SERDES outputs) are not
        # affected.
        pin_i_to_port = SignalDict()
        for pin, port, _fragment in self._pins:
            if hasattr(pin, "i"):
                if isinstance(port, io.SingleEndedPort):
                    pin_i_to_port[pin.i] = port.io
                elif isinstance(port, io.DifferentialPort):
                    pin_i_to_port[pin.i] = port.p
                else:
                    assert False

        for net_signal, frequency in self._clocks.items():
            port_signal = pin_i_to_port.get(net_signal)
            yield net_signal, port_signal, frequency

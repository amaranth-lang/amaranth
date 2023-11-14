from collections import OrderedDict
import warnings

from ..hdl.ast import *
with warnings.catch_warnings():
    warnings.filterwarnings(action="ignore", category=DeprecationWarning)
    from ..hdl.rec import *
from ..lib.io import *
from ..lib import wiring

from .dsl import *


__all__ = ["ResourceError", "ResourceManager"]


class ResourceError(Exception):
    pass


class ResourceManager:
    def __init__(self, resources, connectors):
        self.resources  = OrderedDict()
        self._requested = OrderedDict()
        self._phys_reqd = OrderedDict()

        self.connectors = OrderedDict()
        self._conn_pins = OrderedDict()

        # Constraint lists
        self._ports     = []
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

        def resolve(resource, dir, xdr, name, attrs):
            for attr_key, attr_value in attrs.items():
                if hasattr(attr_value, "__call__"):
                    attr_value = attr_value(self)
                    assert attr_value is None or isinstance(attr_value, str)
                if attr_value is None:
                    del attrs[attr_key]
                else:
                    attrs[attr_key] = attr_value

            if isinstance(resource.ios[0], Subsignal):
                fields = OrderedDict()
                for sub in resource.ios:
                    fields[sub.name] = resolve(sub, dir[sub.name], xdr[sub.name],
                                               name=f"{name}__{sub.name}",
                                               attrs={**attrs, **sub.attrs})
                rec = Record([
                    (f_name, f.layout) for (f_name, f) in fields.items()
                ], fields=fields, name=name)
                rec.signature = wiring.Signature({
                    f_name: wiring.Out(f.signature) for (f_name, f) in fields.items()
                })
                return rec

            elif isinstance(resource.ios[0], (Pins, DiffPairs)):
                phys = resource.ios[0]
                # The flow is `In` below regardless of requested pin direction. The flow should
                # never be used as it's not used internally and anyone using `dir="-"` should
                # ignore it as well.
                if isinstance(phys, Pins):
                    phys_names = phys.names
                    port = Record([("io", len(phys))], name=name)
                    port.signature = wiring.Signature({"io": wiring.In(len(phys))})
                if isinstance(phys, DiffPairs):
                    phys_names = []
                    rec_members = []
                    sig_members = {}
                    if not self.should_skip_port_component(None, attrs, "p"):
                        phys_names += phys.p.names
                        rec_members.append(("p", len(phys)))
                        sig_members["p"] = wiring.In(len(phys))
                    if not self.should_skip_port_component(None, attrs, "n"):
                        phys_names += phys.n.names
                        rec_members.append(("n", len(phys)))
                        sig_members["n"] = wiring.In(len(phys))
                    port = Record(rec_members, name=name)
                    port.signature = wiring.Signature(sig_members)
                if dir == "-":
                    pin = None
                else:
                    pin = wiring.flipped(Pin(len(phys), dir, xdr=xdr, name=name))

                for phys_name in phys_names:
                    if phys_name in self._phys_reqd:
                        raise ResourceError("Resource component {} uses physical pin {}, but it "
                                            "is already used by resource component {} that was "
                                            "requested earlier"
                                            .format(name, phys_name, self._phys_reqd[phys_name]))
                    self._phys_reqd[phys_name] = name

                self._ports.append((resource, pin, port, attrs))

                if pin is not None and resource.clock is not None:
                    self.add_clock_constraint(pin.i, resource.clock.frequency)

                return pin if pin is not None else port

            else:
                assert False # :nocov:

        value = resolve(resource,
            *merge_options(resource, dir, xdr),
            name=f"{resource.name}_{resource.number}",
            attrs=resource.attrs)
        self._requested[resource.name, resource.number] = value
        return value

    def iter_single_ended_pins(self):
        for res, pin, port, attrs in self._ports:
            if pin is None:
                continue
            if isinstance(res.ios[0], Pins):
                yield pin, port, attrs, res.ios[0].invert

    def iter_differential_pins(self):
        for res, pin, port, attrs in self._ports:
            if pin is None:
                continue
            if isinstance(res.ios[0], DiffPairs):
                yield pin, port, attrs, res.ios[0].invert

    def should_skip_port_component(self, port, attrs, component):
        return False

    def iter_ports(self):
        for res, pin, port, attrs in self._ports:
            if isinstance(res.ios[0], Pins):
                if not self.should_skip_port_component(port, attrs, "io"):
                    yield port.io
            elif isinstance(res.ios[0], DiffPairs):
                if not self.should_skip_port_component(port, attrs, "p"):
                    yield port.p
                if not self.should_skip_port_component(port, attrs, "n"):
                    yield port.n
            else:
                assert False

    def iter_port_constraints(self):
        for res, pin, port, attrs in self._ports:
            if isinstance(res.ios[0], Pins):
                if not self.should_skip_port_component(port, attrs, "io"):
                    yield port.io.name, res.ios[0].map_names(self._conn_pins, res), attrs
            elif isinstance(res.ios[0], DiffPairs):
                if not self.should_skip_port_component(port, attrs, "p"):
                    yield port.p.name, res.ios[0].p.map_names(self._conn_pins, res), attrs
                if not self.should_skip_port_component(port, attrs, "n"):
                    yield port.n.name, res.ios[0].n.map_names(self._conn_pins, res), attrs
            else:
                assert False

    def iter_port_constraints_bits(self):
        for port_name, pin_names, attrs in self.iter_port_constraints():
            if len(pin_names) == 1:
                yield port_name, pin_names[0], attrs
            else:
                for bit, pin_name in enumerate(pin_names):
                    yield f"{port_name}[{bit}]", pin_name, attrs

    def add_clock_constraint(self, clock, frequency):
        if not isinstance(clock, Signal):
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
        for res, pin, port, attrs in self._ports:
            if hasattr(pin, "i"):
                if isinstance(res.ios[0], Pins):
                    pin_i_to_port[pin.i] = port.io
                elif isinstance(res.ios[0], DiffPairs):
                    pin_i_to_port[pin.i] = port.p
                else:
                    assert False

        for net_signal, frequency in self._clocks.items():
            port_signal = pin_i_to_port.get(net_signal)
            yield net_signal, port_signal, frequency

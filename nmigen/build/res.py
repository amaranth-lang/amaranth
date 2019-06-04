from collections import OrderedDict

from .. import *
from ..hdl.rec import *
from ..lib.io import *

from .dsl import *


__all__ = ["ConstraintError", "ConstraintManager"]


class ConstraintError(Exception):
    pass


class ConstraintManager:
    def __init__(self, resources, connectors, clocks):
        self.resources  = OrderedDict()
        self.connectors = OrderedDict()
        self.clocks     = OrderedDict()

        self._mapping   = OrderedDict()
        self._requested = OrderedDict()
        self._ports     = []

        self.add_resources(resources)
        self.add_connectors(connectors)
        for name_number, frequency in clocks:
            if not isinstance(name_number, tuple):
                name_number = (name_number, 0)
            self.add_clock(*name_number, frequency)

    def add_resources(self, resources):
        for res in resources:
            if not isinstance(res, Resource):
                raise TypeError("Object {!r} is not a Resource".format(res))
            if (res.name, res.number) in self.resources:
                raise NameError("Trying to add {!r}, but {!r} has the same name and number"
                                .format(res, self.resources[res.name, res.number]))
            self.resources[res.name, res.number] = res

    def add_connectors(self, connectors):
        for conn in connectors:
            if not isinstance(conn, Connector):
                raise TypeError("Object {!r} is not a Connector".format(conn))
            if (conn.name, conn.number) in self.connectors:
                raise NameError("Trying to add {!r}, but {!r} has the same name and number"
                                .format(conn, self.connectors[conn.name, conn.number]))
            self.connectors[conn.name, conn.number] = conn

            for conn_pin, plat_pin in conn:
                assert conn_pin not in self._mapping
                self._mapping[conn_pin] = plat_pin

    def add_clock(self, name, number, frequency):
        resource = self.lookup(name, number)
        if isinstance(resource.io[0], Subsignal):
            raise ConstraintError("Cannot constrain frequency of resource {}#{} because it has "
                                  "subsignals"
                                  .format(resource.name, resource.number, frequency))
        if (resource.name, resource.number) in self.clocks:
            other = self.clocks[resource.name, resource.number]
            raise ConstraintError("Resource {}#{} is already constrained to a frequency of "
                                  "{:f} MHz"
                                  .format(resource.name, resource.number, other / 1e6))
        self.clocks[resource.name, resource.number] = frequency

    def lookup(self, name, number=0):
        if (name, number) not in self.resources:
            raise NameError("Resource {}#{} does not exist"
                            .format(name, number))
        return self.resources[name, number]

    def request(self, name, number=0, *, dir=None, xdr=None):
        resource = self.lookup(name, number)
        if (resource.name, resource.number) in self._requested:
            raise ConstraintError("Resource {}#{} has already been requested"
                                  .format(name, number))

        def merge_options(subsignal, dir, xdr):
            if isinstance(subsignal.io[0], Subsignal):
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
                for sub in subsignal.io:
                    sub_dir = dir.get(sub.name, None)
                    sub_xdr = xdr.get(sub.name, None)
                    dir[sub.name], xdr[sub.name] = merge_options(sub, sub_dir, sub_xdr)
            else:
                if dir is None:
                    dir = subsignal.io[0].dir
                if xdr is None:
                    xdr = 0
                if dir not in ("i", "o", "oe", "io", "-"):
                    raise TypeError("Direction must be one of \"i\", \"o\", \"oe\", \"io\", "
                                    "or \"-\", not {!r}"
                                    .format(dir))
                if dir != subsignal.io[0].dir and not (subsignal.io[0].dir == "io" or dir == "-"):
                    raise ValueError("Direction of {!r} cannot be changed from \"{}\" to \"{}\"; "
                                     "direction can be changed from \"io\" to \"i\", \"o\", or "
                                     "\"oe\", or from anything to \"-\""
                                     .format(subsignal.io[0], subsignal.io[0].dir, dir))
                if not isinstance(xdr, int) or xdr < 0:
                    raise ValueError("Data rate of {!r} must be a non-negative integer, not {!r}"
                                     .format(subsignal.io[0], xdr))
            return dir, xdr

        def resolve(subsignal, dir, xdr, name):
            if isinstance(subsignal.io[0], Subsignal):
                fields = OrderedDict()
                for sub in subsignal.io:
                    fields[sub.name] = resolve(sub, dir[sub.name], xdr[sub.name],
                                                 name="{}__{}".format(name, sub.name))
                return Record([
                    (f_name, f.layout) for (f_name, f) in fields.items()
                ], fields=fields, name=name)

            elif isinstance(subsignal.io[0], (Pins, DiffPairs)):
                phys = subsignal.io[0]
                if isinstance(phys, Pins):
                    port = Record([("io", len(phys))], name=name)
                if isinstance(phys, DiffPairs):
                    port = Record([("p", len(phys)),
                                   ("n", len(phys))], name=name)
                if dir == "-":
                    self._ports.append((subsignal, None, port))
                    return port
                else:
                    pin  = Pin(len(phys), dir, xdr, name=name)
                    self._ports.append((subsignal, pin, port))
                    return pin

            else:
                assert False # :nocov:

        value = resolve(resource,
            *merge_options(resource, dir, xdr),
            name="{}_{}".format(resource.name, resource.number))
        self._requested[resource.name, resource.number] = value
        return value

    def iter_single_ended_pins(self):
        for res, pin, port in self._ports:
            if pin is None:
                continue
            if isinstance(res.io[0], Pins):
                yield pin, port.io, res.extras

    def iter_differential_pins(self):
        for res, pin, port in self._ports:
            if pin is None:
                continue
            if isinstance(res.io[0], DiffPairs):
                yield pin, port.p, port.n, res.extras

    def iter_ports(self):
        for res, pin, port in self._ports:
            if isinstance(res.io[0], Pins):
                yield port.io
            elif isinstance(res.io[0], DiffPairs):
                yield port.p
                yield port.n
            else:
                assert False

    def iter_port_constraints(self):
        for res, pin, port in self._ports:
            if isinstance(res.io[0], Pins):
                yield port.io.name, list(res.io[0].map_names(self._mapping, res)), res.extras
            elif isinstance(res.io[0], DiffPairs):
                yield port.p.name, list(res.io[0].p.map_names(self._mapping, res)), res.extras
                yield port.n.name, list(res.io[0].n.map_names(self._mapping, res)), res.extras
            else:
                assert False

    def iter_port_constraints_bits(self):
        for port_name, pin_names, extras in self.iter_port_constraints():
            if len(pin_names) == 1:
                yield port_name, pin_names[0], extras
            else:
                for bit, pin_name in enumerate(pin_names):
                    yield "{}[{}]".format(port_name, bit), pin_name, extras

    def iter_clock_constraints(self):
        for name, number in self.clocks.keys() & self._requested.keys():
            resource = self.resources[name, number]
            period   = self.clocks[name, number]
            pin      = self._requested[name, number]
            if pin.dir == "io":
                raise ConstraintError("Cannot constrain frequency of resource {}#{} because "
                                      "it has been requested as a tristate buffer"
                                      .format(name, number))
            if isinstance(resource.io[0], Pins):
                port_name = "{}__io".format(pin.name)
            elif isinstance(resource.io[0], DiffPairs):
                port_name = "{}__p".format(pin.name)
            else:
                assert False
            yield (port_name, period)

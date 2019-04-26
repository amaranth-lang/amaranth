from collections import OrderedDict

from .. import *
from ..hdl.rec import *
from ..lib.io import *

from .dsl import *


__all__ = ["ConstraintError", "ConstraintManager"]


class ConstraintError(Exception):
    pass


class ConstraintManager:
    def __init__(self, resources):
        self.resources  = OrderedDict()
        self.requested  = OrderedDict()
        self.clocks     = OrderedDict()

        self._ports     = []
        self._tristates = []
        self._diffpairs = []

        self.add_resources(resources)

    def add_resources(self, resources):
        for r in resources:
            if not isinstance(r, Resource):
                raise TypeError("Object {!r} is not a Resource".format(r))
            if (r.name, r.number) in self.resources:
                raise NameError("Trying to add {!r}, but {!r} has the same name and number"
                                .format(r, self.resources[r.name, r.number]))
            self.resources[r.name, r.number] = r

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

    def lookup(self, name, number):
        if (name, number) not in self.resources:
            raise NameError("Resource {}#{} does not exist"
                            .format(name, number))
        return self.resources[name, number]

    def request(self, name, number, dir=None, xdr=None):
        resource = self.lookup(name, number)
        if (resource.name, resource.number) in self.requested:
            raise ConstraintError("Resource {}#{} has already been requested"
                                  .format(name, number))

        def resolve_dir_xdr(subsignal, dir, xdr):
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
                    dir[sub.name], xdr[sub.name] = resolve_dir_xdr(sub, sub_dir, sub_xdr)
            else:
                if dir is None:
                    dir = subsignal.io[0].dir
                if xdr is None:
                    xdr = 1
                if dir not in ("i", "o", "io"):
                    raise TypeError("Direction must be one of \"i\", \"o\" or \"io\", not {!r}"
                                    .format(dir))
                if subsignal.io[0].dir != "io" and dir != subsignal.io[0].dir:
                    raise ValueError("Direction of {!r} cannot be changed from \"{}\" to \"{}\"; "
                                     "direction can be changed from \"io\" to \"i\" or from \"io\""
                                     "to \"o\""
                                     .format(subsignal.io[0], subsignal.io[0].dir, dir))
                if not isinstance(xdr, int) or xdr < 1:
                    raise ValueError("Data rate of {!r} must be a positive integer, not {!r}"
                                     .format(subsignal.io[0], xdr))
            return dir, xdr

        dir, xdr = resolve_dir_xdr(resource, dir, xdr)

        def get_value(subsignal, dir, xdr, name):
            if isinstance(subsignal.io[0], Subsignal):
                fields = OrderedDict()
                for sub in subsignal.io:
                    fields[sub.name] = get_value(sub, dir[sub.name], xdr[sub.name],
                                                 "{}__{}".format(name, sub.name))
                rec = Record([
                    (f_name, f.layout) for (f_name, f) in fields.items()
                ], fields=fields, name=name)
                return rec
            elif isinstance(subsignal.io[0], DiffPairs):
                pairs = subsignal.io[0]
                return Pin(len(pairs), dir, xdr, name=name)
            elif isinstance(subsignal.io[0], Pins):
                pins = subsignal.io[0]
                return Pin(len(pins), dir, xdr, name=name)
            else:
                assert False # :nocov:

        value_name = "{}_{}".format(resource.name, resource.number)
        value = get_value(resource, dir, xdr, value_name)

        def match_constraints(value, subsignal):
            if isinstance(subsignal.io[0], Subsignal):
                for sub in subsignal.io:
                    yield from match_constraints(value[sub.name], sub)
            else:
                assert isinstance(value, Pin)
                yield (value, subsignal.io[0], subsignal.extras)

        for (pin, io, extras) in match_constraints(value, resource):
            if isinstance(io, DiffPairs):
                p = Signal(pin.width, name="{}_p".format(pin.name))
                n = Signal(pin.width, name="{}_n".format(pin.name))
                self._diffpairs.append((pin, p, n))
                self._ports.append((p, io.p.names, extras))
                self._ports.append((n, io.n.names, extras))
            elif isinstance(io, Pins):
                if pin.dir == "io":
                    port = Signal(pin.width, name="{}_io".format(pin.name))
                    self._tristates.append((pin, port))
                else:
                    port = getattr(pin, pin.dir)
                self._ports.append((port, io.names, extras))
            else:
                assert False # :nocov:

        self.requested[resource.name, resource.number] = value
        return value

    def iter_ports(self):
        for port, pins, extras in self._ports:
            yield port

    def iter_port_constraints(self):
        for port, pins, extras in self._ports:
            yield (port.name, pins, extras)

    def iter_clock_constraints(self):
        for name, number in self.clocks.keys() & self.requested.keys():
            resource = self.resources[name, number]
            pin      = self.requested[name, number]
            period   = self.clocks[name, number]
            if pin.dir == "io":
                raise ConstraintError("Cannot constrain frequency of resource {}#{} because "
                                      "it has been requested as a tristate buffer"
                                      .format(name, number))
            if isinstance(resource.io[0], DiffPairs):
                port_name = "{}_p".format(pin.name)
            else:
                port_name = getattr(pin, pin.dir).name
            yield (port_name, period)

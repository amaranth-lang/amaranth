from collections import OrderedDict

from .. import *
from ..hdl.rec import *
from ..lib.io import *

from .dsl import *


__all__ = ["ConstraintError", "ConstraintManager"]


class ConstraintError(Exception):
    pass


class ConstraintManager:
    def __init__(self, resources, clocks):
        self.resources  = OrderedDict()
        self.requested  = OrderedDict()
        self.clocks     = OrderedDict()
        self._ports     = []

        self.add_resources(resources)
        for name_number, frequency in clocks:
            if not isinstance(name_number, tuple):
                name_number = (name_number, 0)
            self.add_clock(*name_number, frequency)

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

    def lookup(self, name, number=0):
        if (name, number) not in self.resources:
            raise NameError("Resource {}#{} does not exist"
                            .format(name, number))
        return self.resources[name, number]

    def request(self, name, number=0, *, dir=None, xdr=None):
        resource = self.lookup(name, number)
        if (resource.name, resource.number) in self.requested:
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
                if dir not in ("i", "o", "io", "-"):
                    raise TypeError("Direction must be one of \"i\", \"o\", \"io\", or \"-\", "
                                    "not {!r}"
                                    .format(dir))
                if dir != subsignal.io[0].dir and not (subsignal.io[0].dir == "io" or dir == "-"):
                    raise ValueError("Direction of {!r} cannot be changed from \"{}\" to \"{}\"; "
                                     "direction can be changed from \"io\" to \"i\", from \"io\""
                                     "to \"o\", or from anything to \"-\""
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
        self.requested[resource.name, resource.number] = value
        return value

    def iter_single_ended_pins(self):
        for resource, pin, port in self._ports:
            if pin is None:
                continue
            if isinstance(resource.io[0], Pins):
                yield pin, port.io, resource.extras

    def iter_differential_pins(self):
        for resource, pin, port in self._ports:
            if pin is None:
                continue
            if isinstance(resource.io[0], DiffPairs):
                yield pin, port.p, port.n, resource.extras

    def iter_ports(self):
        for resource, pin, port in self._ports:
            if isinstance(resource.io[0], Pins):
                yield port.io
            elif isinstance(resource.io[0], DiffPairs):
                yield port.p
                yield port.n
            else:
                assert False

    def iter_port_constraints(self, diff_pins="pn"):
        for resource, pin, port in self._ports:
            if isinstance(resource.io[0], Pins):
                yield port.io.name, resource.io[0].names, resource.extras
            elif isinstance(resource.io[0], DiffPairs):
                # On some FPGAs like iCE40, only one pin out of two in a differential pair may be
                # constrained. The other has to be completely disconnected.
                if "p" in diff_pins:
                    yield port.p.name, resource.io[0].p.names, resource.extras
                if "n" in diff_pins:
                    yield port.n.name, resource.io[0].n.names, resource.extras
            else:
                assert False

    def iter_clock_constraints(self):
        for name, number in self.clocks.keys() & self.requested.keys():
            resource = self.resources[name, number]
            pin      = self.requested[name, number]
            period   = self.clocks[name, number]
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

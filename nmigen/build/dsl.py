from collections import OrderedDict


__all__ = ["Pins", "DiffPairs", "Subsignal", "Resource", "Connector"]


class Pins:
    def __init__(self, names, *, dir="io", conn=None):
        if not isinstance(names, str):
            raise TypeError("Names must be a whitespace-separated string, not {!r}"
                            .format(names))
        names = names.split()

        if conn is not None:
            conn_name, conn_number = conn
            if not (isinstance(conn_name, str) and isinstance(conn_number, int)):
                raise TypeError("Connector must be None or a pair of string and integer, not {!r}"
                                .format(conn))
            names = ["{}_{}:{}".format(conn_name, conn_number, name) for name in names]

        if dir not in ("i", "o", "io"):
            raise TypeError("Direction must be one of \"i\", \"o\", \"oe\", or \"io\", not {!r}"
                            .format(dir))

        self.names = names
        self.dir   = dir

    def __len__(self):
        return len(self.names)

    def __iter__(self):
        return iter(self.names)

    def map_names(self, mapping, resource):
        for name in self.names:
            while ":" in name:
                if name not in mapping:
                    raise NameError("Resource {!r} refers to nonexistent connector pin {}"
                                    .format(resource, name))
                name = mapping[name]
            yield name

    def __repr__(self):
        return "(pins {} {})".format(self.dir, " ".join(self.names))


class DiffPairs:
    def __init__(self, p, n, *, dir="io", conn=None):
        self.p = Pins(p, dir=dir, conn=conn)
        self.n = Pins(n, dir=dir, conn=conn)

        if len(self.p.names) != len(self.n.names):
            raise TypeError("Positive and negative pins must have the same width, but {!r} "
                            "and {!r} do not"
                            .format(self.p, self.n))

        self.dir = dir

    def __len__(self):
        return len(self.p.names)

    def __iter__(self):
        return zip(self.p.names, self.n.names)

    def __repr__(self):
        return "(diffpairs {} (p {}) (n {}))".format(
            self.dir, " ".join(self.p.names), " ".join(self.n.names))


class Subsignal:
    def __init__(self, name, *io, extras=None):
        self.name = name

        if not io:
            raise TypeError("Missing I/O constraints")
        for c in io:
            if not isinstance(c, (Pins, DiffPairs, Subsignal)):
                raise TypeError("I/O constraint must be one of Pins, DiffPairs or Subsignal, "
                                "not {!r}"
                                .format(c))
        if isinstance(io[0], (Pins, DiffPairs)) and len(io) > 1:
            raise TypeError("Pins and DiffPairs cannot be followed by more I/O constraints, but "
                            "{!r} is followed by {!r}"
                            .format(io[0], io[1]))
        if isinstance(io[0], Subsignal):
            for c in io[1:]:
                if not isinstance(c, Subsignal):
                    raise TypeError("A Subsignal can only be followed by more Subsignals, but "
                                    "{!r} is followed by {!r}"
                                    .format(io[0], c))
        self.io     = io
        self.extras = {}

        if extras is not None:
            if not isinstance(extras, dict):
                raise TypeError("Extra constraints must be a dict, not {!r}"
                                .format(extras))
            for extra_key, extra_value in extras.items():
                if not isinstance(extra_key, str):
                    raise TypeError("Extra constraint key must be a string, not {!r}"
                                    .format(extra_key))
                if not isinstance(extra_value, str):
                    raise TypeError("Extra constraint value must be a string, not {!r}"
                                    .format(extra_value))
                self.extras[extra_key] = extra_value

        if isinstance(self.io[0], Subsignal):
            for sub in self.io:
                sub.extras.update(self.extras)

    def __repr__(self):
        return "(subsignal {} {} {})".format(self.name,
                                             " ".join(map(repr, self.io)),
                                             " ".join("{}={}".format(k, v)
                                                      for k, v in self.extras.items()))


class Resource(Subsignal):
    def __init__(self, name, number, *io, extras=None):
        super().__init__(name, *io, extras=extras)

        self.number = number

    def __repr__(self):
        return "(resource {} {} {} {})".format(self.name, self.number,
                                               " ".join(map(repr, self.io)),
                                               " ".join("{}={}".format(k, v)
                                                        for k, v in self.extras.items()))


class Connector:
    def __init__(self, name, number, io):
        self.name    = name
        self.number  = number
        self.mapping = OrderedDict()

        if isinstance(io, dict):
            for conn_pin, plat_pin in io.items():
                if not isinstance(conn_pin, str):
                    raise TypeError("Connector pin name must be a string, not {!r}"
                                    .format(conn_pin))
                if not isinstance(plat_pin, str):
                    raise TypeError("Platform pin name must be a string, not {!r}"
                                    .format(plat_pin))
                self.mapping[conn_pin] = plat_pin

        elif isinstance(io, str):
            for conn_pin, plat_pin in enumerate(io.split(), start=1):
                if plat_pin == "-":
                    continue
                self.mapping[str(conn_pin)] = plat_pin

        else:
            raise TypeError("Connector I/Os must be a dictionary or a string, not {!r}"
                            .format(io))

    def __repr__(self):
        return "(connector {} {} {})".format(self.name, self.number,
                                             " ".join("{}=>{}".format(conn, plat)
                                                      for conn, plat in self.mapping.items()))

    def __len__(self):
        return len(self.mapping)

    def __iter__(self):
        for conn_pin, plat_pin in self.mapping.items():
            yield "{}_{}:{}".format(self.name, self.number, conn_pin), plat_pin

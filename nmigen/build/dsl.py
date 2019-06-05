from collections import OrderedDict


__all__ = ["Pins", "DiffPairs", "Attrs", "Clock", "Subsignal", "Resource", "Connector"]


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
        mapped_names = []
        for name in self.names:
            while ":" in name:
                if name not in mapping:
                    raise NameError("Resource {!r} refers to nonexistent connector pin {}"
                                    .format(resource, name))
                name = mapping[name]
            mapped_names.append(name)
        return mapped_names

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


class Attrs(OrderedDict):
    def __init__(self, **attrs):
        for attr_key, attr_value in attrs.items():
            if not isinstance(attr_value, str):
                raise TypeError("Attribute value must be a string, not {!r}"
                                .format(attr_value))

        super().__init__(**attrs)

    def __repr__(self):
        return "(attrs {})".format(" ".join("{}={}".format(k, v)
                                    for k, v in self.items()))


class Clock:
    def __init__(self, frequency):
        if not isinstance(frequency, (float, int)):
            raise TypeError("Clock frequency must be a number")

        self.frequency = float(frequency)

    @property
    def period(self):
        return 1 / self.frequency

    def __repr__(self):
        return "(clock {})".format(self.frequency)


class Subsignal:
    def __init__(self, name, *args):
        self.name  = name
        self.ios   = []
        self.attrs = Attrs()
        self.clock = None

        if not args:
            raise ValueError("Missing I/O constraints")
        for arg in args:
            if isinstance(arg, (Pins, DiffPairs)):
                if not self.ios:
                    self.ios.append(arg)
                else:
                    raise TypeError("Pins and DiffPairs are incompatible with other location or "
                                    "subsignal constraints, but {!r} appears after {!r}"
                                    .format(arg, self.ios[-1]))
            elif isinstance(arg, Subsignal):
                if not self.ios or isinstance(self.ios[-1], Subsignal):
                    self.ios.append(arg)
                else:
                    raise TypeError("Subsignal is incompatible with location constraints, but "
                                    "{!r} appears after {!r}"
                                    .format(arg, self.ios[-1]))
            elif isinstance(arg, Attrs):
                self.attrs.update(arg)
            elif isinstance(arg, Clock):
                if self.ios and isinstance(self.ios[-1], (Pins, DiffPairs)):
                    if self.clock is None:
                        self.clock = arg
                    else:
                        raise ValueError("Clock constraint can be applied only once")
                else:
                    raise TypeError("Clock constraint can only be applied to Pins or DiffPairs, "
                                    "not {!r}"
                                    .format(self.ios[-1]))
            else:
                raise TypeError("Constraint must be one of Pins, DiffPairs, Subsignal, Attrs, "
                                "or Clock, not {!r}"
                                .format(arg))

    def _content_repr(self):
        parts = []
        for io in self.ios:
            parts.append(repr(io))
        if self.clock is not None:
            parts.append(repr(self.clock))
        if self.attrs:
            parts.append(repr(self.attrs))
        return " ".join(parts)

    def __repr__(self):
        return "(subsignal {} {})".format(self.name, self._content_repr())


class Resource(Subsignal):
    def __init__(self, name, number, *args):
        super().__init__(name, *args)

        self.number = number

    def __repr__(self):
        return "(resource {} {} {})".format(self.name, self.number, self._content_repr())


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

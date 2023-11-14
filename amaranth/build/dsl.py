from collections import OrderedDict


__all__ = ["Pins", "PinsN", "DiffPairs", "DiffPairsN",
           "Attrs", "Clock", "Subsignal", "Resource", "Connector"]


class Pins:
    def __init__(self, names, *, dir="io", invert=False, conn=None, assert_width=None):
        if not isinstance(names, str):
            raise TypeError("Names must be a whitespace-separated string, not {!r}"
                            .format(names))
        names = names.split()

        if conn is not None:
            conn_name, conn_number = conn
            if not (isinstance(conn_name, str) and isinstance(conn_number, (int, str))):
                raise TypeError("Connector must be None or a pair of string (connector name) and "
                                "integer/string (connector number), not {!r}"
                                .format(conn))
            names = [f"{conn_name}_{conn_number}:{name}" for name in names]

        if dir not in ("i", "o", "io", "oe"):
            raise TypeError("Direction must be one of \"i\", \"o\", \"oe\", or \"io\", not {!r}"
                            .format(dir))

        if assert_width is not None and len(names) != assert_width:
            raise AssertionError("{} names are specified ({}), but {} names are expected"
                                 .format(len(names), " ".join(names), assert_width))

        self.names  = names
        self.dir    = dir
        self.invert = bool(invert)

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
        return "(pins{} {} {})".format("-n" if self.invert else "",
            self.dir, " ".join(self.names))


def PinsN(*args, **kwargs):
    return Pins(*args, invert=True, **kwargs)


class DiffPairs:
    def __init__(self, p, n, *, dir="io", invert=False, conn=None, assert_width=None):
        self.p = Pins(p, dir=dir, conn=conn, assert_width=assert_width)
        self.n = Pins(n, dir=dir, conn=conn, assert_width=assert_width)

        if len(self.p.names) != len(self.n.names):
            raise TypeError("Positive and negative pins must have the same width, but {!r} "
                            "and {!r} do not"
                            .format(self.p, self.n))

        self.dir    = dir
        self.invert = bool(invert)

    def __len__(self):
        return len(self.p.names)

    def __iter__(self):
        return zip(self.p.names, self.n.names)

    def __repr__(self):
        return "(diffpairs{} {} (p {}) (n {}))".format("-n" if self.invert else "",
            self.dir, " ".join(self.p.names), " ".join(self.n.names))


def DiffPairsN(*args, **kwargs):
    return DiffPairs(*args, invert=True, **kwargs)


class Attrs(OrderedDict):
    def __init__(self, **attrs):
        for key, value in attrs.items():
            if not (value is None or isinstance(value, (str, int)) or hasattr(value, "__call__")):
                raise TypeError("Value of attribute {} must be None, int, str, or callable, "
                                "not {!r}"
                                .format(key, value))

        super().__init__(**attrs)

    def __repr__(self):
        items = []
        for key, value in self.items():
            if value is None:
                items.append("!" + key)
            else:
                items.append(key + "=" + repr(value))
        return "(attrs {})".format(" ".join(items))


class Clock:
    def __init__(self, frequency):
        if not isinstance(frequency, (float, int)):
            raise TypeError("Clock frequency must be a number")

        self.frequency = float(frequency)

    @property
    def period(self):
        return 1 / self.frequency

    def __repr__(self):
        return f"(clock {self.frequency})"


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
        return f"(subsignal {self.name} {self._content_repr()})"


class Resource(Subsignal):
    @classmethod
    def family(cls, name_or_number, number=None, *, ios, default_name, name_suffix=""):
        # This constructor accepts two different forms:
        #  1. Number-only form:
        #       Resource.family(0, default_name="name", ios=[Pins("A0 A1")])
        #  2. Name-and-number (name override) form:
        #       Resource.family("override", 0, default_name="name", ios=...)
        # This makes it easier to build abstractions for resources, e.g. an SPIResource abstraction
        # could simply delegate to `Resource.family(*args, default_name="spi", ios=ios)`.
        # The name_suffix argument is meant to support creating resources with
        # similar names, such as spi_flash, spi_flash_2x, etc.
        if name_suffix:  # Only add "_" if we actually have a suffix.
            name_suffix = "_" + name_suffix

        if number is None: # name_or_number is number
            return cls(default_name + name_suffix, name_or_number, *ios)
        else: # name_or_number is name
            return cls(name_or_number + name_suffix, number, *ios)

    def __init__(self, name, number, *args):
        if not isinstance(number, int):
            raise TypeError("Resource number must be an integer, not {!r}"
                            .format(number))

        super().__init__(name, *args)
        self.number = number

    def __repr__(self):
        return f"(resource {self.name} {self.number} {self._content_repr()})"


class Connector:
    def __init__(self, name, number, io, *, conn=None):
        self.name    = name
        self.number  = number
        mapping = OrderedDict()

        if isinstance(io, dict):
            for conn_pin, plat_pin in io.items():
                if not isinstance(conn_pin, str):
                    raise TypeError("Connector pin name must be a string, not {!r}"
                                    .format(conn_pin))
                if not isinstance(plat_pin, str):
                    raise TypeError("Platform pin name must be a string, not {!r}"
                                    .format(plat_pin))
                mapping[conn_pin] = plat_pin

        elif isinstance(io, str):
            for conn_pin, plat_pin in enumerate(io.split(), start=1):
                if plat_pin == "-":
                    continue

                mapping[str(conn_pin)] = plat_pin
        else:
            raise TypeError("Connector I/Os must be a dictionary or a string, not {!r}"
                            .format(io))

        if conn is not None:
            conn_name, conn_number = conn
            if not (isinstance(conn_name, str) and isinstance(conn_number, (int, str))):
                raise TypeError("Connector must be None or a pair of string (connector name) and "
                                "integer/string (connector number), not {!r}"
                                .format(conn))

            for conn_pin, plat_pin in mapping.items():
                mapping[conn_pin] = f"{conn_name}_{conn_number}:{plat_pin}"

        self.mapping = mapping

    def __repr__(self):
        return "(connector {} {} {})".format(self.name, self.number,
                                             " ".join(f"{conn}=>{plat}"
                                                      for conn, plat in self.mapping.items()))

    def __len__(self):
        return len(self.mapping)

    def __iter__(self):
        for conn_pin, plat_pin in self.mapping.items():
            yield f"{self.name}_{self.number}:{conn_pin}", plat_pin

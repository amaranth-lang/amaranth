from collections import OrderedDict


__all__ = ["Pins", "PinsN", "DiffPairs", "DiffPairsN",
           "Attrs", "Clock", "Subsignal", "Resource", "Connector"]


class Pins:
    """A list of :class:`Pin` defining one or more pairs of single-ended I/O pins
    with the same direction, polarity and connector.

    Parameters
    ----------
    names : str
       Space-separated pin names. If ``conn`` is defined these are aliased when requested using
       the :class:`Connector` ``conn`` for the mappings.
    dir : ``"i"``, ``"o"``, ``"io"``, ``"oe"``
        Direction of the buffers. If ``"i"`` is specified, only the ``i``/``iN`` signals are
        present. If ``"o"`` is specified, only the ``o``/``oN`` signals are present. If ``"oe"`` is
        specified, the ``o``/``oN`` signals are present, and an ``oe`` signal is present.
        If ``"io"`` is specified, both the ``i``/``iN`` and ``o``/``oN`` signals are present, and
        an ``oe`` signal is present.
    invert : bool
        Swap the polarity of the I/O pins.
    conn : tuple[str, int | str] - (name, number)
        :class:`Connector` that will be used to resolve output pin names on this instance to names
        defined by the referenced :class:`Connector`.
    assert_width : None | int
        Exact number of pins that should be defined in ``names``. Ignored if set to ``None``.

    Attributes
    ----------
    names : str
    dir : ``"i"``, ``"o"``, ``"io"``, ``"oe"``
    invert : bool
    """
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
            names = ["{}_{}:{}".format(conn_name, conn_number, name) for name in names]

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
    """An inverted :class:`Pins`."""
    return Pins(*args, invert=True, **kwargs)


class DiffPairs:
    """A pair of :class:`Pins` defining one or more pairs of differential I/O pins
    with the same direction, polarity and connector.

    Parameters
    ----------
    p : str
       Space-separated pin names for the P side of one or more differential pairs.
    n : str
       Space-separated pin names for the N side of one or more differential pairs.
    dir : ``"i"``, ``"o"``, ``"io"``, ``"oe"``
        Direction of the buffers. If ``"i"`` is specified, only the ``i``/``iN`` signals are
        present. If ``"o"`` is specified, only the ``o``/``oN`` signals are present. If ``"oe"`` is
        specified, the ``o``/``oN`` signals are present, and an ``oe`` signal is present.
        If ``"io"`` is specified, both the ``i``/``iN`` and ``o``/``oN`` signals are present, and
        an ``oe`` signal is present.
    invert : bool
        Swap the polarity of the P and N inputs.
    conn : tuple[str, int | str] - (name, number)
        :class:`Connector` that will be used to resolve output pin names on this instance to names
        defined by the referenced :class:`Connector`.
    assert_width : None | int
        Exact number of differential pairs that should be defined in ``p`` and ``n``. Ignored if set
        to ``None``.

    Attributes
    ----------
    p : Pins
    n : Pins
    dir : ``"i"``, ``"o"``, ``"io"``, ``"oe"``
    invert : bool
    """
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
    """An inverted :class:`DiffPairs`."""
    return DiffPairs(*args, invert=True, **kwargs)


class Attrs(OrderedDict):
    """Defined platform attributes. Applied to a :class:`Subsignal`.

    Inherits from :class:`collections.OrderedDict`.
    """
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
    """An indicator for pins connected to a clock source.

    Parameters
    ----------
    frequency : float
        Frequency of the connected clock in Hz.

    Attributes
    ----------
    frequency : float
        Frequency of the connected clock in Hz.
    period : float
        Clock period in seconds.
    """
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
    """Collection of I/O resources sharing the same platform attributes.

    Groups related signals together with a name.

    Multiple I/O :class:`Pins` or :class:`DiffPairs` can be defined.
    They will all share a common set of attributes defined by :class:`Attrs` instance(s) in
    the arguments list.

    A clock can be defined by including :class:`Clock` in the list after the :class:`Pins`
    or :class:`DiffPairs` representing the clock I/O pin/pair.

    Alternatively, one or more child :class:`Subsignal` instances can be
    grouped together. Allowing for hierarchy under a parent :class:`Resource`
    these will not use the attributes defined on their parent :class:`Subsignal`
    instance.

    Parameters
    ----------
    *args : typing.Sequence[Pins | DiffPairs | Clock | Attrs] | typing.Sequence[Subsignal]
        Components to construct a :class:`Subsignal`.  Either a :class:`Sequence` that can
        contain :class:`Pins` and :class:`DiffPairs` along with a :class:`Clock` constraint
        and zero or more :class:`Attrs` or a list containing one or more child :class:`Subsignal` s.

    Attributes
    ----------
    name : str
        Subsignal name.
    ios : list[Pins, DiffPairs] | list[Subsignal]
        Defined I/O. Either a :class:`list` that can contain :class:`Pins` and :class:`DiffPairs`
        or a list containing one or more child :class:`Subsignal` s.
    attrs : Attrs
        Platform attributes. Overall combination of all provided :class:`Attrs`
    clock : None | Clock
        Applied clock constraint.
    """
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
    """Platform resource definition.

    :class:`Resource` is used to define resources that can be requested from :class:`Platform`
    instances. :class:`Resource` s can have multiple distinct entries for the same name; this
    name typically represents a shared category of functionality, such as LEDs.

    The name and number are used as parameters to :func:`Platform.request` and must be a unique
    combination.

    See :class:`Subsignal` for details.

    Parameters
    ----------
    name : str
        Resource name to define on the attached platform.
    number : int
        Resource index under that name to define.
    *args : list[Pins | DiffPairs | Subsignal | Attrs | Clock]
        See :class:`Subsignal` .
    """
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
        return "(resource {} {} {})".format(self.name, self.number, self._content_repr())


class Connector:
    """ Defines mappings between pin aliases and an underlying pin name.

    This underlying pin name can also be an alias when connectors are given a reference to
    another :class:`Connector` instance. This is helpful to define a layer of connectors with
    unique intermediate naming conventions.

    The mapping is defined in one of two ways:

        * A string, defining a space-separated list of the target pin names. The source
          mapping for the pins is an incrementing integer starting at ``1``. To skip an
          entry, ``-`` can be used instead of a pin name.

        * A dict, containing mappings from source pin name to target pin name.

    The first type of mapping definition is primarily useful for defining a connector that
    visually matches the layout of the physical pinout for the connector. The second mapping
    is useful to map between established naming schemes for the connector pins.

    Parameters
    ----------
    name : str
        Name for this family of connector.
    number : int | str
        Number identifying this specific connector instance. Can also be an alphanumeric string.
    io : str or dict[str, str]
        String or dictionary defining a mapping from one pin to another.
    conn : tuple[str, int | str] - (name, number)
        Reference another :class:`Connector` that will be used to define another mapping
        from the output pins on this instance to names defined by the referenced
        :class:`Connector`.

    Attributes
    ----------
    name : str
    number : int | str
    mapping : dict[str, str]
        Defined mapping. Mapping between pin alias names and underlying pin names. Might produce
        another alias name if multiple layers of connectors used.
    """
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
                mapping[conn_pin] = "{}_{}:{}".format(conn_name, conn_number, plat_pin)

        self.mapping = mapping

    def __repr__(self):
        return "(connector {} {} {})".format(self.name, self.number,
                                             " ".join("{}=>{}".format(conn, plat)
                                                      for conn, plat in self.mapping.items()))

    def __len__(self):
        return len(self.mapping)

    def __iter__(self):
        for conn_pin, plat_pin in self.mapping.items():
            yield "{}_{}:{}".format(self.name, self.number, conn_pin), plat_pin

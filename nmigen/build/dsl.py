__all__ = ["Pins", "DiffPairs", "Subsignal", "Resource"]


class Pins:
    def __init__(self, names, dir="io"):
        if not isinstance(names, str):
            raise TypeError("Names must be a whitespace-separated string, not {!r}"
                            .format(names))
        self.names = names.split()

        if dir not in ("i", "o", "io"):
            raise TypeError("Direction must be one of \"i\", \"o\" or \"io\", not {!r}"
                            .format(dir))
        self.dir = dir

    def __len__(self):
        return len(self.names)

    def __iter__(self):
        return iter(self.names)

    def __repr__(self):
        return "(pins {} {})".format(self.dir, " ".join(self.names))


class DiffPairs:
    def __init__(self, p, n, dir="io"):
        self.p = Pins(p, dir=dir)
        self.n = Pins(n, dir=dir)

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
    def __init__(self, name, *io, extras=()):
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
        self.io = io

        for c in extras:
            if not isinstance(c, str):
                raise TypeError("Extra constraint must be a string, not {!r}".format(c))
        self.extras = list(extras)

        if isinstance(self.io[0], Subsignal):
            for sub in self.io:
                sub.extras += self.extras

    def __repr__(self):
        return "(subsignal {} {} {})".format(self.name,
                                             " ".join(map(repr, self.io)),
                                             " ".join(self.extras))


class Resource(Subsignal):
    def __init__(self, name, number, *io, extras=()):
        super().__init__(name, *io, extras=extras)

        self.number = number

    def __repr__(self):
        return "(resource {} {} {} {})".format(self.name, self.number,
                                               " ".join(map(repr, self.io)),
                                               " ".join(self.extras))

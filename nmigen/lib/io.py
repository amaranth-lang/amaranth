from .. import *


__all__ = ["TSTriple"]


class TSTriple:
    def __init__(self, shape=None, min=None, max=None, reset_o=0, reset_oe=0, reset_i=0,
                 name=None):
        self.o  = Signal(shape, min=min, max=max, reset=reset_o,
                         name=None if name is None else name + "_o")
        self.oe = Signal(reset=reset_oe,
                         name=None if name is None else name + "_oe")
        self.i  = Signal(shape, min=min, max=max, reset=reset_i,
                         name=None if name is None else name + "_i")

    def __len__(self):
        return len(self.o)

    def get_fragment(self, platform):
        return Fragment()

from ...genlib.io import TSTriple as NativeTSTriple


__all__ = ["TSTriple"]


class CompatTSTriple(NativeTSTriple):
    def __init__(self, bits_sign=None, min=None, max=None, reset_o=0, reset_oe=0, reset_i=0,
                 name=None):
        super().__init__(shape=bits_sign, min=min, max=max,
                         reset_o=reset_o, reset_oe=reset_oe, reset_i=reset_i,
                         name=name)

    def get_tristate(self, target):
        raise NotImplementedError("TODO")


TSTriple = CompatTSTriple

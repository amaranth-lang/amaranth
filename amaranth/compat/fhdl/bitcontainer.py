from ... import utils
from ...hdl import ast
from ..._utils import deprecated


__all__ = ["log2_int", "bits_for", "value_bits_sign"]


@deprecated("instead of `log2_int`, use `amaranth.utils.log2_int`")
def log2_int(n, need_pow2=True):
    return utils.log2_int(n, need_pow2)


@deprecated("instead of `bits_for`, use `amaranth.utils.bits_for`")
def bits_for(n, require_sign_bit=False):
    return utils.bits_for(n, require_sign_bit)


@deprecated("instead of `value_bits_sign(v)`, use `v.shape()`")
def value_bits_sign(v):
    return tuple(ast.Value.cast(v).shape())

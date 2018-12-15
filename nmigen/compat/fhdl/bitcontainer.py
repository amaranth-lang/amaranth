from ... import tools
from ...hdl import ast
from ...tools import deprecated


__all__ = ["log2_int", "bits_for", "value_bits_sign"]


@deprecated("instead of `log2_int`, use `nmigen.tools.log2_int`")
def log2_int(n, need_pow2=True):
    return tools.log2_int(n, need_pow2)


@deprecated("instead of `bits_for`, use `nmigen.tools.bits_for`")
def bits_for(n, require_sign_bit=False):
    return tools.bits_for(n, require_sign_bit)


@deprecated("instead of `value_bits_sign(v)`, use `v.shape()`")
def value_bits_sign(v):
    return ast.Value.wrap(v).shape()

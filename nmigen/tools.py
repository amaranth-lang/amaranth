from collections import Iterable


__all__ = ["flatten", "union", "log2_int", "bits_for"]


def flatten(i):
    for e in i:
        if isinstance(e, Iterable):
            yield from flatten(e)
        else:
            yield e


def union(i):
    r = None
    for e in i:
        if r is None:
            r = e
        else:
            r |= e
    return r


def log2_int(n, need_pow2=True):
    if n == 0:
        return 0
    r = (n - 1).bit_length()
    if need_pow2 and (1 << r) != n:
        raise ValueError("{} is not a power of 2".format(n))
    return r


def bits_for(n, require_sign_bit=False):
    if n > 0:
        r = log2_int(n + 1, False)
    else:
        require_sign_bit = True
        r = log2_int(-n, False)
    if require_sign_bit:
        r += 1
    return r

import operator

__all__ = ["ceil_log2", "exact_log2", "log2_int", "bits_for"]


def ceil_log2(n):
    """Returns the integer log2 of the smallest power-of-2 greater than or equal to `n`.

    Raises a `ValueError` for negative inputs."""
    n = operator.index(n)
    if n < 0:
        raise ValueError(f"{n} is negative")
    if n == 0:
        return 0
    return (n - 1).bit_length()


def exact_log2(n):
    """Returns the integer log2 of `n`, which must be an exact power of two.

    Raises a `ValueError` if `n` is not a power of two."""
    n = operator.index(n)
    if n <= 0 or (n & (n - 1)):
        raise ValueError(f"{n} is not a power of 2")
    return (n - 1).bit_length()

def log2_int(n, need_pow2=True):
    if n == 0:
        return 0
    r = (n - 1).bit_length()
    if need_pow2 and (1 << r) != n:
        raise ValueError(f"{n} is not a power of 2")
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

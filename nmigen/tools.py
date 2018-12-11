from collections import Iterable


__all__ = ["flatten", "union"]


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

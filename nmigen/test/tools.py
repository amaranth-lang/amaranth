import re
import unittest
import warnings
from contextlib import contextmanager

from ..fhdl.ast import *


__all__ = ["FHDLTestCase"]


class FHDLTestCase(unittest.TestCase):
    def assertRepr(self, obj, repr_str):
        obj = Statement.wrap(obj)
        repr_str = re.sub(r"\s+",   " ",  repr_str)
        repr_str = re.sub(r"\( (?=\()", "(", repr_str)
        repr_str = re.sub(r"\) (?=\))", ")", repr_str)
        self.assertEqual(repr(obj), repr_str.strip())

    @contextmanager
    def assertRaises(self, exception, msg=None):
        with super().assertRaises(exception) as cm:
            yield
        if msg is not None:
            # WTF? unittest.assertRaises is completely broken.
            self.assertEqual(str(cm.exception), msg)

    @contextmanager
    def assertWarns(self, category, msg=None):
        with warnings.catch_warnings(record=True) as warns:
            yield
        self.assertEqual(len(warns), 1)
        self.assertEqual(warns[0].category, category)
        if msg is not None:
            self.assertEqual(str(warns[0].message), msg)

from nmigen.hdl.ir import Fragment
from nmigen.compat import *

from .utils import *


class CompatTestCase(FHDLTestCase):
    def test_fragment_get(self):
        m = Module()
        f = Fragment.get(m, platform=None)

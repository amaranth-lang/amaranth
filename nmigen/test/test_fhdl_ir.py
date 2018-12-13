from ..fhdl.ast import *
from ..fhdl.ir import *
from .tools import *


class FragmentPortsTestCase(FHDLTestCase):
    def setUp(self):
        self.s1 = Signal()
        self.s2 = Signal()
        self.s3 = Signal()
        self.c1 = Signal()
        self.c2 = Signal()
        self.c3 = Signal()

    def test_self_contained(self):
        f = Fragment()
        f.add_statements(
            self.c1.eq(self.s1),
            self.s1.eq(self.c1)
        )
        ins, outs = f._propagate_ports(ports=())
        self.assertEqual(ins, ValueSet())
        self.assertEqual(outs, ValueSet())
        self.assertEqual(f.ports, ValueSet())

    def test_infer_input(self):
        f = Fragment()
        f.add_statements(
            self.c1.eq(self.s1)
        )
        ins, outs = f._propagate_ports(ports=())
        self.assertEqual(ins, ValueSet((self.s1,)))
        self.assertEqual(outs, ValueSet())
        self.assertEqual(f.ports, ValueSet((self.s1,)))

    def test_request_output(self):
        f = Fragment()
        f.add_statements(
            self.c1.eq(self.s1)
        )
        ins, outs = f._propagate_ports(ports=(self.c1,))
        self.assertEqual(ins, ValueSet((self.s1,)))
        self.assertEqual(outs, ValueSet((self.c1,)))
        self.assertEqual(f.ports, ValueSet((self.s1, self.c1)))

    def test_input_in_subfragment(self):
        f1 = Fragment()
        f1.add_statements(
            self.c1.eq(self.s1)
        )
        f2 = Fragment()
        f2.add_statements(
            self.s1.eq(0)
        )
        f1.add_subfragment(f2)
        ins, outs = f1._propagate_ports(ports=())
        self.assertEqual(ins, ValueSet())
        self.assertEqual(outs, ValueSet())
        self.assertEqual(f1.ports, ValueSet())
        self.assertEqual(f2.ports, ValueSet((self.s1,)))

    def test_output_from_subfragment(self):
        f1 = Fragment()
        f1.add_statements(
            self.c1.eq(0)
        )
        f2 = Fragment()
        f2.add_statements(
            self.c2.eq(1)
        )
        f1.add_subfragment(f2)
        ins, outs = f1._propagate_ports(ports=(self.c2,))
        self.assertEqual(ins, ValueSet())
        self.assertEqual(outs, ValueSet((self.c2,)))
        self.assertEqual(f1.ports, ValueSet((self.c2,)))
        self.assertEqual(f2.ports, ValueSet((self.c2,)))

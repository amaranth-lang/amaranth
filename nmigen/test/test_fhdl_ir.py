from ..fhdl.ast import *
from ..fhdl.cd import *
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

    def test_input_cd(self):
        sync = ClockDomain()
        f = Fragment()
        f.add_statements(
            self.c1.eq(self.s1)
        )
        f.add_domains(sync)
        f.drive(self.c1, "sync")

        ins, outs = f._propagate_ports(ports=())
        self.assertEqual(ins, ValueSet((self.s1, sync.clk, sync.rst)))
        self.assertEqual(outs, ValueSet(()))
        self.assertEqual(f.ports, ValueSet((self.s1, sync.clk, sync.rst)))

    def test_input_cd_reset_less(self):
        sync = ClockDomain(reset_less=True)
        f = Fragment()
        f.add_statements(
            self.c1.eq(self.s1)
        )
        f.add_domains(sync)
        f.drive(self.c1, "sync")

        ins, outs = f._propagate_ports(ports=())
        self.assertEqual(ins, ValueSet((self.s1, sync.clk)))
        self.assertEqual(outs, ValueSet(()))
        self.assertEqual(f.ports, ValueSet((self.s1, sync.clk)))


class FragmentDomainsTestCase(FHDLTestCase):
    def test_propagate_up(self):
        cd = ClockDomain()

        f1 = Fragment()
        f2 = Fragment()
        f1.add_subfragment(f2)
        f2.add_domains(cd)

        f1._propagate_domains_up()
        self.assertEqual(f1.domains, {"cd": cd})

    def test_domain_conflict(self):
        cda = ClockDomain("sync")
        cdb = ClockDomain("sync")

        fa = Fragment()
        fa.add_domains(cda)
        fb = Fragment()
        fb.add_domains(cdb)
        f = Fragment()
        f.add_subfragment(fa, "a")
        f.add_subfragment(fb, "b")

        f._propagate_domains_up()
        self.assertEqual(f.domains, {"a_sync": cda, "b_sync": cdb})
        (fa, _), (fb, _) = f.subfragments
        self.assertEqual(fa.domains, {"a_sync": cda})
        self.assertEqual(fb.domains, {"b_sync": cdb})

    def test_domain_conflict_anon(self):
        cda = ClockDomain("sync")
        cdb = ClockDomain("sync")

        fa = Fragment()
        fa.add_domains(cda)
        fb = Fragment()
        fb.add_domains(cdb)
        f = Fragment()
        f.add_subfragment(fa, "a")
        f.add_subfragment(fb)

        with self.assertRaises(DomainError,
                msg="Domain 'sync' is defined by subfragments 'a', <unnamed #1> of fragment "
                    "'top'; it is necessary to either rename subfragment domains explicitly, "
                    "or give names to subfragments"):
            f._propagate_domains_up()

    def test_domain_conflict_name(self):
        cda = ClockDomain("sync")
        cdb = ClockDomain("sync")

        fa = Fragment()
        fa.add_domains(cda)
        fb = Fragment()
        fb.add_domains(cdb)
        f = Fragment()
        f.add_subfragment(fa, "x")
        f.add_subfragment(fb, "x")

        with self.assertRaises(DomainError,
                msg="Domain 'sync' is defined by subfragments #0, #1 of fragment 'top', some "
                    "of which have identical names; it is necessary to either rename subfragment "
                    "domains explicitly, or give distinct names to subfragments"):
            f._propagate_domains_up()

    def test_propagate_down(self):
        cd = ClockDomain()

        f1 = Fragment()
        f2 = Fragment()
        f1.add_domains(cd)
        f1.add_subfragment(f2)

        f1._propagate_domains_down()
        self.assertEqual(f2.domains, {"cd": cd})

    def test_propagate_down_idempotent(self):
        cd = ClockDomain()

        f1 = Fragment()
        f1.add_domains(cd)
        f2 = Fragment()
        f2.add_domains(cd)
        f1.add_subfragment(f2)

        f1._propagate_domains_down()
        self.assertEqual(f1.domains, {"cd": cd})
        self.assertEqual(f2.domains, {"cd": cd})

    def test_propagate(self):
        cd = ClockDomain()

        f1 = Fragment()
        f2 = Fragment()
        f1.add_domains(cd)
        f1.add_subfragment(f2)

        f1._propagate_domains()
        self.assertEqual(f1.domains, {"cd": cd})
        self.assertEqual(f2.domains, {"cd": cd})

    def test_propagate_default(self):
        f1 = Fragment()
        f2 = Fragment()
        f1.add_subfragment(f2)

        f1._propagate_domains(ensure_sync_exists=True)
        self.assertEqual(f1.domains.keys(), {"sync"})
        self.assertEqual(f2.domains.keys(), {"sync"})
        self.assertEqual(f1.domains["sync"], f2.domains["sync"])

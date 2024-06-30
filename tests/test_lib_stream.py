from amaranth.hdl import *
from amaranth.lib import stream, wiring, fifo
from amaranth.lib.wiring import In, Out

from .utils import *


class StreamTestCase(FHDLTestCase):
    def test_nav_nar(self):
        sig = stream.Signature(2)
        self.assertRepr(sig, f"stream.Signature(2)")
        self.assertEqual(sig.always_valid, False)
        self.assertEqual(sig.always_ready, False)
        self.assertEqual(sig.members, wiring.SignatureMembers({
            "payload": Out(2),
            "valid": Out(1),
            "ready": In(1)
        }))
        intf = sig.create()
        self.assertRepr(intf,
            f"stream.Interface(payload=(sig intf__payload), valid=(sig intf__valid), "
            f"ready=(sig intf__ready))")
        self.assertIs(intf.signature, sig)
        self.assertIsInstance(intf.payload, Signal)
        self.assertIs(intf.p, intf.payload)
        self.assertIsInstance(intf.valid, Signal)
        self.assertIsInstance(intf.ready, Signal)

    def test_av_nar(self):
        sig = stream.Signature(2, always_valid=True)
        self.assertRepr(sig, f"stream.Signature(2, always_valid=True)")
        self.assertEqual(sig.always_valid, True)
        self.assertEqual(sig.always_ready, False)
        self.assertEqual(sig.members, wiring.SignatureMembers({
            "payload": Out(2),
            "valid": Out(1),
            "ready": In(1)
        }))
        intf = sig.create()
        self.assertRepr(intf,
            f"stream.Interface(payload=(sig intf__payload), valid=(const 1'd1), "
            f"ready=(sig intf__ready))")
        self.assertIs(intf.signature, sig)
        self.assertIsInstance(intf.payload, Signal)
        self.assertIs(intf.p, intf.payload)
        self.assertIsInstance(intf.valid, Const)
        self.assertEqual(intf.valid.value, 1)
        self.assertIsInstance(intf.ready, Signal)

    def test_nav_ar(self):
        sig = stream.Signature(2, always_ready=True)
        self.assertRepr(sig, f"stream.Signature(2, always_ready=True)")
        self.assertEqual(sig.always_valid, False)
        self.assertEqual(sig.always_ready, True)
        self.assertEqual(sig.members, wiring.SignatureMembers({
            "payload": Out(2),
            "valid": Out(1),
            "ready": In(1)
        }))
        intf = sig.create()
        self.assertRepr(intf,
            f"stream.Interface(payload=(sig intf__payload), valid=(sig intf__valid), "
            f"ready=(const 1'd1))")
        self.assertIs(intf.signature, sig)
        self.assertIsInstance(intf.payload, Signal)
        self.assertIs(intf.p, intf.payload)
        self.assertIsInstance(intf.valid, Signal)
        self.assertIsInstance(intf.ready, Const)
        self.assertEqual(intf.ready.value, 1)

    def test_av_ar(self):
        sig = stream.Signature(2, always_valid=True, always_ready=True)
        self.assertRepr(sig, f"stream.Signature(2, always_valid=True, always_ready=True)")
        self.assertEqual(sig.always_valid, True)
        self.assertEqual(sig.always_ready, True)
        self.assertEqual(sig.members, wiring.SignatureMembers({
            "payload": Out(2),
            "valid": Out(1),
            "ready": In(1)
        }))
        intf = sig.create()
        self.assertRepr(intf,
            f"stream.Interface(payload=(sig intf__payload), valid=(const 1'd1), "
            f"ready=(const 1'd1))")
        self.assertIs(intf.signature, sig)
        self.assertIsInstance(intf.payload, Signal)
        self.assertIs(intf.p, intf.payload)
        self.assertIsInstance(intf.valid, Const)
        self.assertEqual(intf.valid.value, 1)
        self.assertIsInstance(intf.ready, Const)
        self.assertEqual(intf.ready.value, 1)

    def test_eq(self):
        sig_nav_nar = stream.Signature(2)
        sig_av_nar  = stream.Signature(2, always_valid=True)
        sig_nav_ar  = stream.Signature(2, always_ready=True)
        sig_av_ar   = stream.Signature(2, always_valid=True, always_ready=True)
        sig_av_ar2  = stream.Signature(3, always_valid=True, always_ready=True)
        self.assertNotEqual(sig_nav_nar, None)
        self.assertEqual(sig_nav_nar, sig_nav_nar)
        self.assertEqual(sig_av_nar,  sig_av_nar)
        self.assertEqual(sig_nav_ar,  sig_nav_ar)
        self.assertEqual(sig_av_ar,   sig_av_ar)
        self.assertEqual(sig_av_ar2,  sig_av_ar2)
        self.assertNotEqual(sig_nav_nar, sig_av_nar)
        self.assertNotEqual(sig_av_nar,  sig_nav_ar)
        self.assertNotEqual(sig_nav_ar,  sig_av_ar)
        self.assertNotEqual(sig_av_ar,   sig_nav_nar)
        self.assertNotEqual(sig_av_ar,   sig_av_ar2)

    def test_payload_init(self):
        sig = stream.Signature(2, payload_init=0b10)
        intf = sig.create()
        self.assertEqual(intf.payload.init, 0b10)

    def test_interface_create_bad(self):
        with self.assertRaisesRegex(TypeError,
                r"^Signature of stream\.Interface must be a stream\.Signature, not "
                r"Signature\(\{\}\)$"):
            stream.Interface(wiring.Signature({}))


class FIFOStreamCompatTestCase(FHDLTestCase):
    def test_r_stream(self):
        queue = fifo.SyncFIFOBuffered(width=4, depth=16)
        r = queue.r_stream
        self.assertFalse(r.signature.always_valid)
        self.assertFalse(r.signature.always_ready)
        self.assertIs(r.payload, queue.r_data)
        self.assertIs(r.valid, queue.r_rdy)
        self.assertIs(r.ready, queue.r_en)

    def test_w_stream(self):
        queue = fifo.SyncFIFOBuffered(width=4, depth=16)
        w = queue.w_stream
        self.assertFalse(w.signature.always_valid)
        self.assertFalse(w.signature.always_ready)
        self.assertIs(w.payload, queue.w_data)
        self.assertIs(w.valid, queue.w_en)
        self.assertIs(w.ready, queue.w_rdy)

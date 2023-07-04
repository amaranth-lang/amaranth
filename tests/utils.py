import os
import re
import shutil
import subprocess
import textwrap
import traceback
import unittest
from unittest.util import safe_repr

from amaranth.hdl.ast import *
from amaranth.hdl.ir import *
from amaranth.back import rtlil
from amaranth._toolchain import require_tool


__all__ = ["FHDLTestCase"]


class FHDLTestCase(unittest.TestCase):
    def assertRepr(self, obj, repr_str):
        if isinstance(obj, list):
            obj = Statement.cast(obj)
        def prepare_repr(repr_str):
            repr_str = re.sub(r"\s+",   " ",  repr_str)
            repr_str = re.sub(r"\( (?=\()", "(", repr_str)
            repr_str = re.sub(r"\) (?=\))", ")", repr_str)
            return repr_str.strip()
        self.assertEqual(prepare_repr(repr(obj)), prepare_repr(repr_str))

    def assertFormal(self, spec, mode="bmc", depth=1):
        stack = traceback.extract_stack()
        for frame in reversed(stack):
            if os.path.dirname(__file__) not in frame.filename:
                break
            caller = frame

        spec_root, _ = os.path.splitext(caller.filename)
        spec_dir = os.path.dirname(spec_root)
        spec_name = "{}_{}".format(
            os.path.basename(spec_root).replace("test_", "spec_"),
            caller.name.replace("test_", "")
        )

        # The sby -f switch seems not fully functional when sby is reading from stdin.
        if os.path.exists(os.path.join(spec_dir, spec_name)):
            shutil.rmtree(os.path.join(spec_dir, spec_name))

        if mode == "hybrid":
            # A mix of BMC and k-induction, as per personal communication with Claire Wolf.
            script = "setattr -unset init w:* a:amaranth.sample_reg %d"
            mode   = "bmc"
        else:
            script = ""

        config = textwrap.dedent("""\
        [options]
        mode {mode}
        depth {depth}
        wait on
        multiclock on

        [engines]
        smtbmc

        [script]
        read_ilang top.il
        prep
        {script}

        [file top.il]
        {rtlil}
        """).format(
            mode=mode,
            depth=depth,
            script=script,
            rtlil=rtlil.convert_fragment(Fragment.get(spec, platform="formal").prepare())[0]
        )
        with subprocess.Popen(
                [require_tool("sby"), "-f", "-d", spec_name],
                cwd=spec_dir, env={**os.environ, "PYTHONWARNINGS":"ignore"},
                universal_newlines=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE) as proc:
            stdout, stderr = proc.communicate(config)
            if proc.returncode != 0:
                self.fail("Formal verification failed:\n" + stdout)

    def assertIsSubclass(self, obj, cls, msg=None):
        if not issubclass(obj, cls):
            standardMsg = '%s is not a subclass of %r' % (safe_repr(obj), cls)
            self.fail(self._formatMessage(msg, standardMsg))

    def assertNotIsSubclass(self, obj, cls, msg=None):
        if issubclass(obj, cls):
            standardMsg = '%s is a subclass of %r' % (safe_repr(obj), cls)
            self.fail(self._formatMessage(msg, standardMsg))

    def assertShapeCastable(self, obj):
        self.assertIsInstance(obj, ShapeCastable)
        self.assertIsSubclass(type(obj), ShapeCastable)
        try:
            Shape.cast(obj)
        except TypeError:
            raise AssertionError(f"{obj} failed Shape.cast")

    def assertNotShapeCastable(self, obj, *, but_is_subclass=False):
        """
        Ideally, for any object that is considered an instance of
        :class:`ShapeCastable`, its type is also considered a subclass of
        :class:`ShapeCastable`, such as the relationship between ``1``
        (shape-castable) and ``int`` (subclass of :class:`ShapeCastable`).

        This relationship is uneven because the reverse is not always true in
        every cast: ``-1`` is not shape-castable. An enum with
        non-constant-castable member values is not shape-castable.
        """
        self.assertNotIsInstance(obj, ShapeCastable)
        if but_is_subclass:
            self.assertIsSubclass(type(obj), ShapeCastable)
        else:
            self.assertNotIsSubclass(type(obj), ShapeCastable)
        with self.assertRaises(TypeError):
            Shape.cast(obj)

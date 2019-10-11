import os
import re
import shutil
import subprocess
import textwrap
import traceback
import unittest
import warnings
from contextlib import contextmanager

from ..hdl.ast import *
from ..hdl.ir import *
from ..back import rtlil
from .._toolchain import require_tool


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

    @contextmanager
    def assertRaises(self, exception, msg=None):
        with super().assertRaises(exception) as cm:
            yield
        if msg is not None:
            # WTF? unittest.assertRaises is completely broken.
            self.assertEqual(str(cm.exception), msg)

    @contextmanager
    def assertRaisesRegex(self, exception, regex=None):
        with super().assertRaises(exception) as cm:
            yield
        if regex is not None:
            # unittest.assertRaisesRegex also seems broken...
            self.assertRegex(str(cm.exception), regex)

    @contextmanager
    def assertWarns(self, category, msg=None):
        with warnings.catch_warnings(record=True) as warns:
            yield
        self.assertEqual(len(warns), 1)
        self.assertEqual(warns[0].category, category)
        if msg is not None:
            self.assertEqual(str(warns[0].message), msg)

    def assertFormal(self, spec, mode="bmc", depth=1):
        caller, *_ = traceback.extract_stack(limit=2)
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
            # A mix of BMC and k-induction, as per personal communication with Clifford Wolf.
            script = "setattr -unset init w:* a:nmigen.sample_reg %d"
            mode   = "bmc"
        else:
            script = ""

        config = textwrap.dedent("""\
        [options]
        mode {mode}
        depth {depth}
        wait on

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
            rtlil=rtlil.convert(Fragment.get(spec, platform="formal"))
        )
        with subprocess.Popen([require_tool("sby"), "-f", "-d", spec_name], cwd=spec_dir,
                              universal_newlines=True,
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE) as proc:
            stdout, stderr = proc.communicate(config)
            if proc.returncode != 0:
                self.fail("Formal verification failed:\n" + stdout)

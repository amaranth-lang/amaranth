import os
import platform
import re
import shutil
import subprocess
import sys
import textwrap
import traceback
import unittest

from amaranth.hdl._ast import *
from amaranth.hdl._ir import *
from amaranth.back import rtlil
from amaranth._toolchain import require_tool


__all__ = ["FHDLTestCase"]


class FHDLTestCase(unittest.TestCase):
    maxDiff = None

    def assertRepr(self, obj, repr_str):
        if isinstance(obj, list):
            obj = Statement.cast(obj)
        def squish_repr(repr_str):
            repr_str = re.sub(r"\s+",   " ",  repr_str)
            repr_str = re.sub(r"\( (?=\()", "(", repr_str)
            repr_str = re.sub(r"\) (?=\))", ")", repr_str)
            return repr_str.strip()
        def format_repr(input_repr, *, indent="    "):
            output_repr = []
            prefix = "\n"
            name = None
            index = 0
            stack = []
            current = ""
            for char in input_repr:
                if char == "(":
                    stack.append((prefix, name, index))
                    name, index = None, 0
                    output_repr.append(char)
                    if len(stack) == 1:
                        prefix += indent
                        output_repr.append(prefix)
                elif char == ")":
                    indented = (len(stack) == 1 or name in ("module", "top"))
                    prefix, name, index = stack.pop()
                    if indented:
                        output_repr.append(prefix)
                    output_repr.append(char)
                elif char == " ":
                    if name is None:
                        name = current
                        if name in ("module", "top"):
                            prefix += indent
                    else:
                        index += 1
                    current = ""
                    if len(stack) == 1 or name == "module" and index >= 3 or name == "top":
                        output_repr.append(prefix)
                    else:
                        output_repr.append(char)
                elif name is None:
                    current += char
                    output_repr.append(char)
                else:
                    output_repr.append(char)
            return "".join(output_repr)
        # print("\n" + format_repr(squish_repr(repr(obj))))
        self.assertEqual(format_repr(squish_repr(repr(obj))), format_repr(squish_repr(repr_str)))

    def assertFormal(self, spec, ports=None, mode="bmc", depth=1):
        if sys.version_info >= (3, 11) and platform.python_implementation() == 'PyPy':
            self.skipTest("sby is broken with pypy-3.11 without https://github.com/YosysHQ/sby/pull/323")

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
        read_rtlil top.il
        prep
        {script}

        [file top.il]
        {rtlil}
        """).format(
            mode=mode,
            depth=depth,
            script=script,
            rtlil=rtlil.convert(spec, ports=ports, platform="formal"),
        )
        with subprocess.Popen(
                [require_tool("sby"), "-f", "-d", spec_name],
                cwd=spec_dir, env={**os.environ, "PYTHONWARNINGS":"ignore"},
                universal_newlines=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE) as proc:
            stdout, stderr = proc.communicate(config)
            if proc.returncode != 0:
                self.fail("Formal verification failed:\n" + stdout)

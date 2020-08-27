import sys
import subprocess
from pathlib import Path

from .utils import *


def example_test(name):
    path = (Path(__file__).parent / ".." / "examples" / name).resolve()
    def test_function(self):
        subprocess.check_call([sys.executable, str(path), "generate", "-t", "v"],
                              stdout=subprocess.DEVNULL)
    return test_function


class ExamplesTestCase(FHDLTestCase):
    test_alu        = example_test("basic/alu.py")
    test_alu_hier   = example_test("basic/alu_hier.py")
    test_arst       = example_test("basic/arst.py")
    test_cdc        = example_test("basic/cdc.py")
    test_ctr        = example_test("basic/ctr.py")
    test_ctr_en     = example_test("basic/ctr_en.py")
    test_fsm        = example_test("basic/fsm.py")
    test_gpio       = example_test("basic/gpio.py")
    test_inst       = example_test("basic/inst.py")
    test_mem        = example_test("basic/mem.py")
    test_pmux       = example_test("basic/pmux.py")
    test_por        = example_test("basic/por.py")

    def test_uart(self):
        path = (Path(__file__).parent / ".." / "examples" / "basic" / "uart.py").resolve()
        subprocess.check_call([sys.executable, str(path), "generate"],
                              stdout=subprocess.DEVNULL)

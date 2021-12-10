import os
import ctypes
import tempfile
import unittest

from amaranth._toolchain.cxx import *


class ToolchainCxxTestCase(unittest.TestCase):
    def setUp(self):
        self.include_dir = None
        self.build_dir = None

    def tearDown(self):
        if self.include_dir:
            self.include_dir.cleanup()
        if self.build_dir:
            self.build_dir.cleanup()

    def test_filename(self):
        self.build_dir, filename = build_cxx(
            cxx_sources={"test.cc": ""},
            output_name="answer",
            include_dirs=[],
            macros=[],
        )
        self.assertTrue(filename.startswith("answer"))

    def test_simple(self):
        self.build_dir, filename = build_cxx(
            cxx_sources={"test.cc": """
                extern "C" int answer() { return 42; }
            """},
            output_name="answer",
            include_dirs=[],
            macros=[],
        )
        library = ctypes.cdll.LoadLibrary(os.path.join(self.build_dir.name, filename))
        self.assertEqual(library.answer(), 42)

    def test_macro(self):
        self.build_dir, filename = build_cxx(
            cxx_sources={"test.cc": """
                extern "C" int answer() { return ANSWER; }
            """},
            output_name="answer",
            include_dirs=[],
            macros=["ANSWER=42"],
        )
        library = ctypes.cdll.LoadLibrary(os.path.join(self.build_dir.name, filename))
        self.assertEqual(library.answer(), 42)

    def test_include(self):
        self.include_dir = tempfile.TemporaryDirectory(prefix="amaranth_hxx_")
        with open(os.path.join(self.include_dir.name, "answer.h"), "w") as f:
            f.write("#define ANSWER 42")

        self.build_dir, filename = build_cxx(
            cxx_sources={"test.cc": """
                #include <answer.h>
                extern "C" int answer() { return ANSWER; }
            """},
            output_name="answer",
            include_dirs=[self.include_dir.name],
            macros=[],
        )
        library = ctypes.cdll.LoadLibrary(os.path.join(self.build_dir.name, filename))
        self.assertEqual(library.answer(), 42)

import unittest

from amaranth.utils import *
from amaranth._utils import _ignore_deprecated


class Log2TestCase(unittest.TestCase):
    def test_ceil_log2(self):
        self.assertEqual(ceil_log2(0), 0)
        self.assertEqual(ceil_log2(1), 0)
        self.assertEqual(ceil_log2(2), 1)
        self.assertEqual(ceil_log2(3), 2)
        self.assertEqual(ceil_log2(4), 2)
        self.assertEqual(ceil_log2(5), 3)
        self.assertEqual(ceil_log2(8), 3)
        self.assertEqual(ceil_log2(9), 4)
        with self.assertRaises(TypeError):
            ceil_log2(1.5)
        with self.assertRaisesRegex(ValueError, r"^-1 is negative$"):
            ceil_log2(-1)

    def test_exact_log2(self):
        self.assertEqual(exact_log2(1), 0)
        self.assertEqual(exact_log2(2), 1)
        self.assertEqual(exact_log2(4), 2)
        self.assertEqual(exact_log2(8), 3)
        for val in [-1, 0, 3, 5, 6, 7, 9]:
            with self.assertRaisesRegex(ValueError, (f"^{val} is not a power of 2$")):
                exact_log2(val)
        with self.assertRaises(TypeError):
            exact_log2(1.5)

    def test_bits_for(self):
        self.assertEqual(bits_for(-4), 3)
        self.assertEqual(bits_for(-3), 3)
        self.assertEqual(bits_for(-2), 2)
        self.assertEqual(bits_for(-1), 1)
        self.assertEqual(bits_for(0), 1)
        self.assertEqual(bits_for(1), 1)
        self.assertEqual(bits_for(2), 2)
        self.assertEqual(bits_for(3), 2)
        self.assertEqual(bits_for(4), 3)
        self.assertEqual(bits_for(5), 3)
        self.assertEqual(bits_for(-4, True), 3)
        self.assertEqual(bits_for(-3, True), 3)
        self.assertEqual(bits_for(-2, True), 2)
        self.assertEqual(bits_for(-1, True), 1)
        self.assertEqual(bits_for(0, True), 1)
        self.assertEqual(bits_for(1, True), 2)
        self.assertEqual(bits_for(2, True), 3)
        self.assertEqual(bits_for(3, True), 3)
        self.assertEqual(bits_for(4, True), 4)
        self.assertEqual(bits_for(5, True), 4)
        with self.assertRaises(TypeError):
            bits_for(1.5)

import unittest

from amaranth.compat import *


class PassiveCase(unittest.TestCase):
    def test_terminates_correctly(self):
        n = 5

        count = 0
        @passive
        def counter():
            nonlocal count
            while True:
                yield
                count += 1

        def terminator():
            for i in range(n):
                yield

        run_simulation(Module(), [counter(), terminator()])
        self.assertEqual(count, n)

from ..hdl.ir import Elaboratable


# The nMigen testsuite creates a lot of elaboratables that are intentionally unused.
# Disable the unused elaboratable check, as in our case it provides nothing but noise.
del Elaboratable.__del__

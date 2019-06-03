# Reference: https://www.digilentinc.com/Pmods/Digilent-Pmod_%20Interface_Specification.pdf

from ...build import *


__all__ = [
    "PmodGPIOType1Resource",
    "PmodSPIType2Resource",
    "PmodSPIType2AResource",
    "PmodUARTType3Resource",
    "PmodUARTType4Resource",
    "PmodUARTType4AResource",
    "PmodHBridgeType5Resource",
    "PmodDualHBridgeType6Resource",
]


def PmodGPIOType1Resource(name, number, *, pmod, extras=None):
    return Resource(name, number,
        Pins("1 2 3 4", dir="io", conn=("pmod", pmod)),
        extras=extras
    )


def PmodSPIType2Resource(name, number, *, pmod, extras=None):
    return Resource(name, number,
        Subsignal("cs_n",  Pins("1", dir="o", conn=("pmod", pmod))),
        Subsignal("clk",   Pins("2", dir="o", conn=("pmod", pmod))),
        Subsignal("mosi",  Pins("3", dir="o", conn=("pmod", pmod))),
        Subsignal("miso",  Pins("4", dir="i", conn=("pmod", pmod))),
        extras=extras
    )


def PmodSPIType2AResource(name, number, *, pmod, extras=None):
    return Resource(name, number,
        Subsignal("cs_n",  Pins("1", dir="o", conn=("pmod", pmod))),
        Subsignal("clk",   Pins("2", dir="o", conn=("pmod", pmod))),
        Subsignal("mosi",  Pins("3", dir="o", conn=("pmod", pmod))),
        Subsignal("miso",  Pins("4", dir="i", conn=("pmod", pmod))),
        Subsignal("int",   Pins("7", dir="i", conn=("pmod", pmod))),
        Subsignal("reset", Pins("8", dir="o", conn=("pmod", pmod))),
        extras=extras
        )


def PmodUARTType3Resource(name, number, *, pmod, extras=None):
    return Resource(name, number,
        Subsignal("cts",   Pins("1", dir="o", conn=("pmod", pmod))),
        Subsignal("rts",   Pins("2", dir="i", conn=("pmod", pmod))),
        Subsignal("rx",    Pins("3", dir="i", conn=("pmod", pmod))),
        Subsignal("tx",    Pins("4", dir="o", conn=("pmod", pmod))),
        extras=extras
    )


def PmodUARTType4Resource(name, number, *, pmod, extras=None):
    return Resource(name, number,
        Subsignal("cts",   Pins("1", dir="i", conn=("pmod", pmod))),
        Subsignal("tx",    Pins("2", dir="o", conn=("pmod", pmod))),
        Subsignal("rx",    Pins("3", dir="i", conn=("pmod", pmod))),
        Subsignal("rts",   Pins("4", dir="o", conn=("pmod", pmod))),
        extras=extras
    )


def PmodUARTType4AResource(name, number, *, pmod, extras=None):
    return Resource(name, number,
        Subsignal("cts",   Pins("1", dir="i", conn=("pmod", pmod))),
        Subsignal("tx",    Pins("2", dir="o", conn=("pmod", pmod))),
        Subsignal("rx",    Pins("3", dir="i", conn=("pmod", pmod))),
        Subsignal("rts",   Pins("4", dir="o", conn=("pmod", pmod))),
        Subsignal("int",   Pins("7", dir="i", conn=("pmod", pmod))),
        Subsignal("reset", Pins("8", dir="o", conn=("pmod", pmod))),
        extras=extras
    )


def PmodHBridgeType5Resource(name, number, *, pmod, extras=None):
    return Resource(name, number,
        Subsignal("dir",   Pins("1", dir="o", conn=("pmod", pmod))),
        Subsignal("en",    Pins("2", dir="o", conn=("pmod", pmod))),
        Subsignal("sa",    Pins("3", dir="i", conn=("pmod", pmod))),
        Subsignal("sb",    Pins("4", dir="i", conn=("pmod", pmod))),
        extras=extras
    )


def PmodDualHBridgeType6Resource(name, number, *, pmod, extras=None):
    return Resource(name, number,
        Subsignal("dir",   Pins("1 3", dir="o", conn=("pmod", pmod))),
        Subsignal("en",    Pins("2 4", dir="o", conn=("pmod", pmod))),
        extras=extras
    )

try:
    from importlib import metadata as importlib_metadata # py3.8+ stdlib
except ImportError:
    import importlib_metadata # py3.7- shim
__version__ = importlib_metadata.version(__package__)


from .hdl import *


__all__ = [
    "Shape", "unsigned", "signed",
    "Value", "Const", "C", "Mux", "Cat", "Repl", "Array", "Signal", "ClockSignal", "ResetSignal",
    "Module",
    "ClockDomain",
    "Elaboratable", "Fragment", "Instance",
    "Memory",
    "Record",
    "DomainRenamer", "ResetInserter", "EnableInserter",
]

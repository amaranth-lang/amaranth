import pkg_resources
try:
    __version__ = pkg_resources.get_distribution(__name__).version
except pkg_resources.DistributionNotFound:
    pass


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

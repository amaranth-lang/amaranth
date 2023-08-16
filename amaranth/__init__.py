# Extract version for this package from the environment package metadata. This used to be a lot
# more difficult in earlier Python versions, and the `__version__` field is a legacy of that time.
import importlib.metadata
try:
    __version__ = importlib.metadata.version(__package__)
except importlib.metadata.PackageNotFoundError:
    # No importlib metadata for this package. This shouldn't normally happen, but some people
    # prefer not installing packages via pip at all. Although not recommended we still support it.
    __version__ = "unknown" # :nocov:
del importlib


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

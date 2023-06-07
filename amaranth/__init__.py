try:
    from importlib import metadata as importlib_metadata
    __version__ = importlib_metadata.version(__package__)
    del importlib_metadata
except ImportError:
    # No importlib_metadata. This shouldn't normally happen, but some people prefer not installing
    # packages via pip at all, instead using PYTHONPATH directly or copying the package files into
    # `lib/pythonX.Y/site-packages`. Although not a recommended way, we still try to support it.
    __version__ = "unknown" # :nocov:


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

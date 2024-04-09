# The machinery in this module is PEP 562 compliant.
# See https://peps.python.org/pep-0562/ for details.


# Keep this list sorted alphabetically.
__all__ = [
    "AlteraPlatform",
    "GowinPlatform",
    "IntelPlatform",
    "LatticeECP5Platform",
    "LatticeICE40Platform",
    "LatticeMachXO2Platform",
    "LatticeMachXO3LPlatform",
    "QuicklogicPlatform",
    "SiliconBluePlatform",
    "XilinxPlatform",
]


def __dir__():
    return list({*globals(), *__all__})


def __getattr__(name):
    if name in ("AlteraPlatform", "IntelPlatform"):
        from ._altera import AlteraPlatform
        return AlteraPlatform
    if name == "GowinPlatform":
        from ._gowin import GowinPlatform
        return GowinPlatform
    if name == "LatticeECP5Platform":
        from ._lattice_ecp5 import LatticeECP5Platform
        return LatticeECP5Platform
    if name in ("LatticeMachXO2Platform", "LatticeMachXO3LPlatform"):
        from ._lattice_machxo_2_3l import LatticeMachXO2Or3LPlatform
        return LatticeMachXO2Or3LPlatform
    if name == "QuicklogicPlatform":
        from ._quicklogic import QuicklogicPlatform
        return QuicklogicPlatform
    if name in ("SiliconBluePlatform", "LatticeICE40Platform"):
        from ._siliconblue import SiliconBluePlatform
        return SiliconBluePlatform
    if name == "XilinxPlatform":
        from ._xilinx import XilinxPlatform
        return XilinxPlatform
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

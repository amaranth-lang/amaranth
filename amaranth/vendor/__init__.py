# The machinery in this module is PEP 562 compliant.
# See https://peps.python.org/pep-0562/ for details.


# Keep this list sorted alphabetically.
__all__ = [
    "AlteraPlatform",
    "AMDPlatform",
    "GowinPlatform",
    "IntelPlatform",
    "LatticeECP5Platform",
    "LatticeICE40Platform",
    "LatticeMachXO2Platform",
    "LatticeMachXO3LPlatform",
    "LatticePlatform",
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
    if name in ("LatticePlatform", "LatticeECP5Platform", "LatticeMachXO2Platform",
                "LatticeMachXO3LPlatform"):
        from ._lattice import LatticePlatform
        return LatticePlatform
    if name == "QuicklogicPlatform":
        from ._quicklogic import QuicklogicPlatform
        return QuicklogicPlatform
    if name in ("SiliconBluePlatform", "LatticeICE40Platform"):
        from ._siliconblue import SiliconBluePlatform
        return SiliconBluePlatform
    if name in ("XilinxPlatform", "AMDPlatform"):
        from ._xilinx import XilinxPlatform
        return XilinxPlatform
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

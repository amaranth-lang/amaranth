import sys
import warnings

from ._utils import get_linter_option


__all__ = ["UnusedMustUse", "MustUse"]


class UnusedMustUse(Warning):
    pass


class MustUse:
    _MustUse__silence = False
    _MustUse__warning = UnusedMustUse

    def __new__(cls, *args, src_loc_at=0, **kwargs):
        frame = sys._getframe(1 + src_loc_at)
        self = super().__new__(cls)
        self._MustUse__used    = False
        self._MustUse__context = dict(
            filename=frame.f_code.co_filename,
            lineno=frame.f_lineno,
            source=self)
        return self

    def __del__(self):
        if self._MustUse__silence:
            return
        if getattr(self._MustUse__warning, "_MustUse__silence", False):
            return
        if hasattr(self, "_MustUse__used") and not self._MustUse__used:
            if get_linter_option(self._MustUse__context["filename"],
                                 self._MustUse__warning.__qualname__, bool, True):
                warnings.warn_explicit(
                    f"{self!r} created but never used", self._MustUse__warning,
                    **self._MustUse__context)


_old_excepthook = sys.excepthook
def _silence_elaboratable(type, value, traceback):
    # Don't show anything if the interpreter crashed; that'd just obscure the exception
    # traceback instead of helping.
    MustUse._MustUse__silence = True
    _old_excepthook(type, value, traceback)
sys.excepthook = _silence_elaboratable

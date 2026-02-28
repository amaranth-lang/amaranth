import sys
from typing import Any
import warnings

from ._utils import get_linter_option


__all__ = ["UnusedMustUse", "MustUse"]


class UnusedMustUse(Warning):
    pass


class MustUse:
    _MustUse__silence = False
    _MustUse__warning = UnusedMustUse

    _MustUse__used: bool
    _MustUse__context: dict[str, Any]
    _MustUse__stack_summary: traceback.StackSummary

    def __new__(cls, *_args: list[Any], src_loc_at: int = 0, **_kwargs: dict[str, Any]):
        # capture and ignore arbitrary args/kwargs to prevent errors with mixins

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
            # allow suppression via amaranth file level linter option
            if get_linter_option(
                self._MustUse__context["filename"],
                self._MustUse__warning.__qualname__,
                type=bool,
                default=True,
            ):
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

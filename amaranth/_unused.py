import sys
from typing import Any
import warnings
import traceback
import re
import os

from ._utils import get_linter_option


__all__ = ["UnusedMustUse", "MustUse"]


class UnusedMustUse(Warning):
    pass


class MustUse:
    _MustUse__silence = False
    _MustUse__warning = UnusedMustUse
    _MustUse__should_trace = os.environ.get("AMARANTH_TRACE_UNUSED", "").lower() in [
        "1",
        "true",
        "yes",
        "enable",
        "full",
    ]
    _MustUse__should_trace_full = (
        os.environ.get("AMARANTH_TRACE_UNUSED", "").lower() == "full"
    )
    # Ignore stack frames from code in files that are likely to be unhelpful
    _MustUse__ignored_paths_re = re.compile(
        r"(?:^<frozen runpy>$|python[^/]*/(?:unittest|_pyrepl)/)"
    )

    _MustUse__used: bool
    _MustUse__context: dict[str, Any]
    _MustUse__stack_summary: traceback.StackSummary

    @classmethod
    def __filter_stack(
        cls, stack_summary: traceback.StackSummary
    ) -> traceback.StackSummary:
        return traceback.StackSummary(
            filter(
                lambda f: cls._MustUse__ignored_paths_re.search(f.filename) is None,
                stack_summary,
            )
        )

    def __new__(cls, *_args: list[Any], src_loc_at: int = 0, **_kwargs: dict[str, Any]):
        # capture and ignore arbitrary args/kwargs to prevent errors with mixins

        frame = sys._getframe(1 + src_loc_at)

        self = super().__new__(cls)
        self._MustUse__used = False
        self._MustUse__context = dict(
            filename=frame.f_code.co_filename,
            lineno=frame.f_lineno,
            source=self,
        )

        if cls._MustUse__should_trace:
            self._MustUse__stack_summary = traceback.extract_stack(f=frame)

            if not cls._MustUse__should_trace_full:
                self._MustUse__stack_summary = cls.__filter_stack(
                    self._MustUse__stack_summary
                )

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
                trace: str
                if self._MustUse__should_trace:
                    if self._MustUse__should_trace_full:
                        trace = f"Full trace of {type(self).__qualname__} (MustUse) creation:\n"
                    else:
                        trace = (
                            f"Filtered trace of {type(self).__qualname__} (MustUse) creation "
                            "(set AMARANTH_TRACE_UNUSED=full for unfiltered):\n"
                        )

                    trace += "\n".join(traceback.format_list(self._MustUse__stack_summary))
                else:
                    trace = (
                        f"Trace of {type(self).__qualname__} (MustUse) creation not available, "
                        "set AMARANTH_TRACE_UNUSED=1 (or =full for unfiltered) and rerun"
                    )

                warnings.warn_explicit(
                    f"{self!r} created but never used\n{trace}",
                    self._MustUse__warning,
                    **self._MustUse__context,
                )


_old_excepthook = sys.excepthook
def _silence_elaboratable(type, value, traceback):
    # Don't show anything if the interpreter crashed; that'd just obscure the exception
    # traceback instead of helping.
    MustUse._MustUse__silence = True
    _old_excepthook(type, value, traceback)
sys.excepthook = _silence_elaboratable

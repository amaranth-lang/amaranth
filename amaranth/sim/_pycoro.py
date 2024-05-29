import inspect

from .._utils import deprecated
from ..hdl import *
from ..hdl._ast import Assign, ValueCastable


__all__ = ["Command", "Settle", "Delay", "Tick", "Passive", "Active", "PyCoroProcess"]


class Command:
    pass


class Settle(Command):
    @deprecated("The `Settle` command is deprecated per RFC 27. Use `add_testbench` to write "
                "testbenches; there, an equivalent of `yield Settle()` is performed "
                "automatically after each `ctx.set()`.")
    def __init__(self):
        pass

    def __repr__(self):
        return "(settle)"


class Delay(Command):
    def __init__(self, interval=None):
        self.interval = None if interval is None else float(interval)

    def __repr__(self):
        if self.interval is None:
            return "(delay ε)"
        else:
            return f"(delay {self.interval * 1e6:.3}us)"


class Tick(Command):
    def __init__(self, domain="sync"):
        if not isinstance(domain, (str, ClockDomain)):
            raise TypeError(f"Domain must be a string or a ClockDomain instance, not {domain!r}")
        assert domain != "comb"
        self.domain = domain

    def __repr__(self):
        return f"(tick {self.domain})"


class Passive(Command):
    def __repr__(self):
        return "(passive)"


class Active(Command):
    def __repr__(self):
        return "(active)"


def coro_wrapper(process, *, testbench, default_cmd=None):
    async def inner(context):
        def src_loc(coroutine):
            if coroutine is None:
                return None
            while coroutine.gi_yieldfrom is not None and inspect.isgenerator(coroutine.gi_yieldfrom):
                coroutine = coroutine.gi_yieldfrom
            if inspect.isgenerator(coroutine):
                frame = coroutine.gi_frame
            if inspect.iscoroutine(coroutine):
                frame = coroutine.cr_frame
            return f"{inspect.getfile(frame)}:{inspect.getlineno(frame)}"

        coroutine = process()

        response = None
        exception = None
        while True:
            try:
                if exception is None:
                    command = coroutine.send(response)
                else:
                    command = coroutine.throw(exception)
            except StopIteration:
                return

            try:
                if command is None:
                    command = default_cmd
                response = None
                exception = None

                if isinstance(command, ValueCastable):
                    command = Value.cast(command)
                if isinstance(command, Value):
                    response = context._engine.get_value(command)

                elif isinstance(command, Assign):
                    context.set(command.lhs, context._engine.get_value(command.rhs))

                elif type(command) is Tick:
                    await context.tick(command.domain)

                elif testbench and (command is None or isinstance(command, Settle)):
                    raise TypeError(f"Command {command!r} is not allowed in testbenches")

                elif type(command) is Settle:
                    await context.delay(0)

                elif type(command) is Delay:
                    await context.delay(command.interval or 0)

                elif type(command) is Passive:
                    context._process.critical = False

                elif type(command) is Active:
                    context._process.critical = True

                elif command is None: # only possible if self.default_cmd is None
                    raise TypeError("Received default command from process {!r} that was added "
                                    "with add_process(); did you mean to use Tick() instead?"
                                    .format(src_loc(coroutine)))

                else:
                    raise TypeError("Received unsupported command {!r} from process {!r}"
                                    .format(command, src_loc(coroutine)))

            except Exception as exn:
                response = None
                exception = exn

    return inner

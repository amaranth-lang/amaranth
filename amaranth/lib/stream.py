from ..hdl import *
from .._utils import final
from . import wiring
from .wiring import In, Out


@final
class Signature(wiring.Signature):
    """Signature of a unidirectional data stream.

    .. note::

        "Minimal streams" as defined in `RFC 61`_ lack support for complex payloads, such as
        multiple lanes or packetization, as well as introspection of the payload. This limitation
        will be lifted in a later release.

        .. _RFC 61: https://amaranth-lang.org/rfcs/0061-minimal-streams.html

    Parameters
    ----------
    payload_shape : :class:`~.hdl.ShapeLike`
        Shape of the payload member.
    payload_init : :ref:`constant-castable <lang-constcasting>` object
        Initial value of the payload member.
    always_valid : :class:`bool`
        Whether the stream has a payload available each cycle.
    always_ready : :class:`bool`
        Whether the stream has its payload accepted whenever it is available (i.e. whether it lacks
        support for backpressure).

    Members
    -------
    payload : :py:`Out(payload_shape)`
        Payload.
    valid : :py:`Out(1)`
        Whether a payload is available. If the stream is :py:`always_valid`, :py:`Const(1)`.
    ready : :py:`In(1)`
        Whether a payload is accepted. If the stream is :py:`always_ready`, :py:`Const(1)`.
    """
    def __init__(self, payload_shape: ShapeLike, *, payload_init=None,
                 always_valid=False, always_ready=False):
        Shape.cast(payload_shape)
        self._payload_shape = payload_shape
        self._always_valid = bool(always_valid)
        self._always_ready = bool(always_ready)

        super().__init__({
            "payload": Out(payload_shape, init=payload_init),
            "valid": Out(1),
            "ready": In(1)
        })

    # payload_shape intentionally not introspectable (for now)

    @property
    def always_valid(self):
        return self._always_valid

    @property
    def always_ready(self):
        return self._always_ready

    def __eq__(self, other):
        return (type(other) is type(self) and
            other._payload_shape == self._payload_shape and
            other.always_valid == self.always_valid and
            other.always_ready == self.always_ready)

    def create(self, *, path=None, src_loc_at=0):
        return Interface(self, path=path, src_loc_at=1 + src_loc_at)

    def __repr__(self):
        always_valid_repr = "" if not self._always_valid else ", always_valid=True"
        always_ready_repr = "" if not self._always_ready else ", always_ready=True"
        return f"stream.Signature({self._payload_shape!r}{always_valid_repr}{always_ready_repr})"


@final
class Interface:
    """A unidirectional data stream.

    Attributes
    ----------
    signature : :class:`Signature`
        Signature of this data stream.
    """

    payload: Signal
    valid: 'Signal | Const'
    ready: 'Signal | Const'

    def __init__(self, signature: Signature, *, path=None, src_loc_at=0):
        if not isinstance(signature, Signature):
            raise TypeError(f"Signature of stream.Interface must be a stream.Signature, not "
                            f"{signature!r}")
        self._signature = signature
        self.__dict__.update(signature.members.create(path=path, src_loc_at=1 + src_loc_at))
        if signature.always_valid:
            self.valid = Const(1)
        if signature.always_ready:
            self.ready = Const(1)

    @property
    def signature(self):
        return self._signature

    @property
    def p(self):
        """Shortcut for :py:`self.payload`.

        This shortcut reduces repetition when manipulating the payload, for example:

        .. code::

            m.d.comb += [
                self.o_stream.p.result.eq(self.i_stream.p.first + self.i_stream.p.second),
                self.o_stream.valid.eq(self.i_stream.valid),
                self.i_stream.ready.eq(self.o_stream.ready),
            ]
        """
        return self.payload

    def __repr__(self):
        return (f"stream.Interface(payload={self.payload!r}, valid={self.valid!r}, "
                f"ready={self.ready!r})")

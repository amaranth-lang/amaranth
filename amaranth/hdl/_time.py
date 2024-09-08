import numbers
import re


__all__ = ["Period"]


_TIME_UNITS = {
    "s":  1_000_000_000_000_000,
    "ms": 1_000_000_000_000,
    "us": 1_000_000_000,
    "ns": 1_000_000,
    "ps": 1_000,
    "fs": 1,
}


_FREQUENCY_UNITS = {
    "Hz":  1_000_000_000_000_000,
    "kHz": 1_000_000_000_000,
    "MHz": 1_000_000_000,
    "GHz": 1_000_000,
}


class Period:
    def __init__(self, **kwargs):
        if not kwargs:
            self._femtoseconds = 0
            return

        if len(kwargs) > 1:
            raise TypeError("Period accepts at most one argument")

        (unit, value), = kwargs.items()

        if not isinstance(value, numbers.Real):
            raise TypeError(f"{unit} value must be a real number")

        if unit in _TIME_UNITS:
            self._femtoseconds = round(value * _TIME_UNITS[unit])

        elif unit in _FREQUENCY_UNITS:
            if value == 0:
                raise ZeroDivisionError("Frequency can't be zero")
            elif value < 0:
                raise ValueError("Frequency can't be negative")

            self._femtoseconds = round(_FREQUENCY_UNITS[unit] / value)

        else:
            raise TypeError(f"{unit} is not a valid unit")

    @property
    def seconds(self):
        return self._femtoseconds / 1_000_000_000_000_000

    @property
    def milliseconds(self):
        return self._femtoseconds / 1_000_000_000_000

    @property
    def microseconds(self):
        return self._femtoseconds / 1_000_000_000

    @property
    def nanoseconds(self):
        return self._femtoseconds / 1_000_000

    @property
    def picoseconds(self):
        return self._femtoseconds / 1_000

    @property
    def femtoseconds(self):
        return self._femtoseconds

    def _check_reciprocal(self):
        if self._femtoseconds == 0:
            raise ZeroDivisionError("Can't calculate the frequency of a zero period")
        elif self._femtoseconds < 0:
            raise ValueError("Can't calculate the frequency of a negative period")

    @property
    def hertz(self):
        self._check_reciprocal()
        return 1_000_000_000_000_000 / self._femtoseconds

    @property
    def kilohertz(self):
        self._check_reciprocal()
        return 1_000_000_000_000 / self._femtoseconds

    @property
    def megahertz(self):
        self._check_reciprocal()
        return 1_000_000_000 / self._femtoseconds

    @property
    def gigahertz(self):
        self._check_reciprocal()
        return 1_000_000 / self._femtoseconds

    def __lt__(self, other):
        if not isinstance(other, Period):
            return NotImplemented
        return self._femtoseconds < other._femtoseconds

    def __le__(self, other):
        if not isinstance(other, Period):
            return NotImplemented
        return self._femtoseconds <= other._femtoseconds

    def __eq__(self, other):
        if not isinstance(other, Period):
            return NotImplemented
        return self._femtoseconds == other._femtoseconds

    def __ne__(self, other):
        if not isinstance(other, Period):
            return NotImplemented
        return self._femtoseconds != other._femtoseconds

    def __gt__(self, other):
        if not isinstance(other, Period):
            return NotImplemented
        return self._femtoseconds > other._femtoseconds

    def __ge__(self, other):
        if not isinstance(other, Period):
            return NotImplemented
        return self._femtoseconds >= other._femtoseconds

    def __hash__(self):
        return hash(self._femtoseconds)

    def __bool__(self):
        return bool(self._femtoseconds)

    def __neg__(self):
        return Period(fs=-self._femtoseconds)

    def __pos__(self):
        return self

    def __abs__(self):
        return Period(fs=abs(self._femtoseconds))

    def __add__(self, other):
        if not isinstance(other, Period):
            return NotImplemented
        return Period(fs=self._femtoseconds + other._femtoseconds)

    def __sub__(self, other):
        if not isinstance(other, Period):
            return NotImplemented
        return Period(fs=self._femtoseconds - other._femtoseconds)

    def __mul__(self, other):
        if not isinstance(other, numbers.Real):
            return NotImplemented
        return Period(fs=self._femtoseconds * other)

    __rmul__ = __mul__

    def __truediv__(self, other):
        if isinstance(other, Period):
            return self._femtoseconds / other._femtoseconds
        elif isinstance(other, numbers.Real):
            return Period(fs=self._femtoseconds / other)
        else:
            return NotImplemented

    def __floordiv__(self, other):
        if not isinstance(other, Period):
            return NotImplemented
        return self._femtoseconds // other._femtoseconds

    def __mod__(self, other):
        if not isinstance(other, Period):
            return NotImplemented
        return Period(fs=self._femtoseconds % other._femtoseconds)

    def __str__(self):
        return self.__format__("")

    def __format__(self, format_spec):
        m = re.match(r"^([1-9]\d*)?(\.\d+)?( ?)(([munpf]?)s|([kMG]?)Hz)?$", format_spec)

        if m is None:
            raise ValueError(f"Invalid format specifier '{format_spec}' for object of type 'Period'")

        width, precision, space, unit, s_unit, hz_unit = m.groups()

        if unit is None:
            if abs(self._femtoseconds) >= 1_000_000_000_000_000:
                s_unit = ""
            elif abs(self._femtoseconds) >= 1_000_000_000_000:
                s_unit = "m"
            elif abs(self._femtoseconds) >= 1_000_000_000:
                s_unit = "u"
            elif abs(self._femtoseconds) >= 1_000_000:
                s_unit = "n"
            elif abs(self._femtoseconds) >= 1_000:
                s_unit = "p"
            else:
                s_unit = "f"

            unit = f"{s_unit}s"

        if s_unit is not None:
            div, digits = {
                "":  (1_000_000_000_000_000, 15),
                "m": (1_000_000_000_000, 12),
                "u": (1_000_000_000, 9),
                "n": (1_000_000, 6),
                "p": (1_000, 3),
                "f": (1, 0),
            }[s_unit]
            integer, decimal = divmod(self._femtoseconds, div)

            if precision:
                precision = int(precision[1:])
                decimal = round(decimal * 10**(precision - digits))
                digits = precision

            value = f"{integer}.{decimal:0{digits}}"

            if not precision:
                value = value.rstrip('0')
            value = value.rstrip('.')

        else:
            if hz_unit == "":
                value = f"{self.hertz:{precision or ''}f}"
            elif hz_unit == "k":
                value = f"{self.kilohertz:{precision or ''}f}"
            elif hz_unit == "M":
                value = f"{self.megahertz:{precision or ''}f}"
            elif hz_unit == "G":
                value = f"{self.gigahertz:{precision or ''}f}"

        str = f"{value}{space}{unit}"
        if width:
            str = f"{str:>{width}}"

        return str

    def __repr__(self):
        for unit, div in _TIME_UNITS.items():
            if self._femtoseconds % div == 0:
                return f"Period({unit}={self._femtoseconds // div})"

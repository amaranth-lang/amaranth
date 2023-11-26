from abc import ABCMeta, abstractmethod


__all__ = ["Format", "FormatInt", "FormatEnum", "FormatCustom", "Repr"]


class Format(metaclass=ABCMeta):
    @abstractmethod
    def format(self, value):
        raise NotImplementedError


class FormatInt(Format):
    def format(self, value):
        return f"{value:d}"


class FormatEnum(Format):
    def __init__(self, enum):
        self.enum = enum

    def format(self, value):
        try:
            return f"{self.enum(value).name}/{value:d}"
        except ValueError:
            return f"?/{value:d}"


class FormatCustom(Format):
    def __init__(self, formatter):
        self.formatter = formatter

    def format(self, value):
        return self.formatter(value)


class Repr:
    def __init__(self, format, value, *, path=()):
        from .ast import Value # avoid a circular dependency
        assert isinstance(format, Format)
        assert isinstance(value, Value)
        assert isinstance(path, tuple) and all(isinstance(part, (str, int)) for part in path)

        self.format = format
        self.value  = value
        self.path   = path

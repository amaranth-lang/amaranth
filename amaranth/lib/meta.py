from abc import abstractmethod, ABCMeta
from collections.abc import Mapping
from urllib.parse import urlparse

import jsonschema


__all__ = ["Annotation"]


class Annotation(metaclass=ABCMeta):
    """Signature annotation.

    A container for metadata that can be retrieved from a :class:`~amaranth.lib.wiring.Signature`
    object. Annotation instances can be exported as JSON objects, whose structure is defined using
    the `JSON Schema <https://json-schema.org>`_ language.

    Schema URLs
    -----------

    An ``Annotation`` schema must have a ``"$id"`` property, which holds an URL that serves as its
    unique identifier. The suggested format of this URL is:

        <protocol>://<domain>/schema/<package>/<version>/<path>.json

    where:
      * ``<domain>`` is a domain name registered to the person or entity defining the annotation;
      * ``<package>`` is the name of the Python package providing the ``Annotation`` subclass;
      * ``<version>`` is the version of the aforementioned package;
      * ``<path>`` is a non-empty string specific to the annotation.

    Attributes
    ----------
    schema : :class`Mapping`
        Annotation schema.
    """

    schema = property(abstractmethod(lambda: None)) # :nocov:

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if not isinstance(cls.schema, Mapping):
            raise TypeError(f"Annotation schema must be a dict, not {cls.schema!r}")

        # The '$id' keyword is optional in JSON schemas, but we require it.
        if "$id" not in cls.schema:
            raise ValueError(f"'$id' keyword is missing from Annotation schema: {cls.schema}")
        jsonschema.Draft202012Validator.check_schema(cls.schema)

    @property
    @abstractmethod
    def origin(self):
        """Annotation origin.

        The Python object described by this :class:`Annotation` instance.
        """
        pass # :nocov:

    @abstractmethod
    def as_json(self):
        """Translate to JSON.

        Returns
        -------
        :class:`Mapping`
            A JSON representation of this :class:`Annotation` instance.
        """
        pass # :nocov:

    @classmethod
    def validate(cls, instance):
        """Validate a JSON object.

        Parameters
        ----------
        instance : :class:`Mapping`
            The JSON object to validate.

        Raises
        ------
        :exc:`jsonschema.exceptions.ValidationError`
            If `instance` doesn't comply with :attr:`Annotation.schema`.
        """
        jsonschema.validate(instance, schema=cls.schema)

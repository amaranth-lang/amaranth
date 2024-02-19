from abc import abstractmethod, ABCMeta


__all__ = ["Annotation"]


class Annotation(metaclass=ABCMeta):
    """Signature annotation.

    A container for metadata that can be retrieved from a :class:`~amaranth.lib.wiring.Signature`
    object. Annotation instances can be exported as JSON objects, whose structure is defined using
    the `JSON Schema`_ language.
    """

    #: :class:`dict`: Schema of this annotation, expressed in the `JSON Schema`_ language.
    #:
    #: Subclasses of :class:`Annotation` must implement this class attribute.
    schema = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        if not isinstance(cls.schema, dict):
            raise TypeError(f"Annotation schema must be a dict, not {cls.schema!r}")

        # The '$id' keyword is optional in JSON schemas, but we require it.
        if "$id" not in cls.schema:
            raise ValueError(f"'$id' keyword is missing from Annotation schema: {cls.schema}")

        try:
            import jsonschema
            jsonschema.Draft202012Validator.check_schema(cls.schema)
        except ImportError:
            # Amaranth was installed in some weird way and doesn't have jsonschema installed,
            # despite it being a mandatory dependency. The schema will eventually get checked
            # by the CI, so ignore the error here.
            pass # :nocov:

    @property
    @abstractmethod
    def origin(self):
        """The Python object described by this :class:`Annotation` instance.

        Subclasses of :class:`Annotation` must implement this property.
        """
        pass # :nocov:

    @abstractmethod
    def as_json(self):
        """Convert to a JSON representation.

        Subclasses of :class:`Annotation` must implement this property.

        The JSON representation returned by this method must adhere to :data:`schema` and pass
        validation by :meth:`validate`.

        Returns
        -------
        :class:`dict`
            JSON representation of this annotation, expressed in Python primitive types
            (:class:`dict`, :class:`list`, :class:`str`, :class:`int`, :class:`bool`).
        """
        pass # :nocov:

    @classmethod
    def validate(cls, instance):
        """Validate a JSON representation against :attr:`schema`.

        Arguments
        ---------
        instance : :class:`dict`
            The JSON representation to validate, either previously returned by :meth:`as_json`
            or retrieved from an external source.

        Raises
        ------
        :exc:`jsonschema.exceptions.ValidationError`
            If :py:`instance` doesn't comply with :attr:`Annotation.schema`.
        """
        import jsonschema
        jsonschema.validate(instance, schema=cls.schema)

    def __repr__(self):
        return f"<{type(self).__module__}.{type(self).__qualname__} for {self.origin!r}>"
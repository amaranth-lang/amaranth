import jschon
import pprint
import warnings
from abc import abstractmethod, ABCMeta


__all__ = ["InvalidSchema", "InvalidAnnotation", "Annotation"]


class InvalidSchema(Exception):
    """Exception raised when a subclass of :class:`Annotation` is defined with a non-conformant
    :data:`~Annotation.schema`."""


class InvalidAnnotation(Exception):
    """Exception raised by :meth:`Annotation.validate` when the JSON representation of
    an annotation does not conform to its schema."""


class Annotation(metaclass=ABCMeta):
    """Interface annotation.

    Annotations are containers for metadata that can be retrieved from an interface object using
    the :meth:`Signature.annotations <.wiring.Signature.annotations>` method.

    Annotations have a JSON representation whose structure is defined by the `JSON Schema`_
    language.
    """

    #: :class:`dict`: Schema of this annotation, expressed in the `JSON Schema`_ language.
    #:
    #: Subclasses of :class:`Annotation` must define this class attribute.
    schema = {}

    @classmethod
    def __jschon_schema(cls):
        catalog = jschon.create_catalog("2020-12")
        return jschon.JSONSchema(cls.schema, catalog=catalog)

    def __init_subclass__(cls, **kwargs):
        """
        Defining a subclass of :class:`Annotation` causes its :data:`schema` to be validated.

        Raises
        ------
        :exc:`InvalidSchema`
            If :data:`schema` doesn't conform to the `2020-12` draft of `JSON Schema`_.
        :exc:`InvalidSchema`
            If :data:`schema` doesn't have a  `"$id" keyword`_ at its root. This requirement is
            specific to :class:`Annotation` schemas.
        """
        super().__init_subclass__(**kwargs)

        if not isinstance(cls.schema, dict):
            raise TypeError(f"Annotation schema must be a dict, not {cls.schema!r}")

        if "$id" not in cls.schema:
            raise InvalidSchema(f"'$id' keyword is missing from Annotation schema: {cls.schema}")

        try:
            # TODO: Remove this. Ignore a deprecation warning from jschon's rfc3986 dependency.
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=DeprecationWarning)
                result = cls.__jschon_schema().validate()
        except jschon.JSONSchemaError as e:
            raise InvalidSchema(e) from e

        if not result.valid:
            raise InvalidSchema("Invalid Annotation schema:\n" +
                                pprint.pformat(result.output("basic")["errors"],
                                               sort_dicts=False))

    @property
    @abstractmethod
    def origin(self):
        """Python object described by this :class:`Annotation` instance.

        Subclasses of :class:`Annotation` must implement this property.
        """
        pass # :nocov:

    @abstractmethod
    def as_json(self):
        """Convert to a JSON representation.

        Subclasses of :class:`Annotation` must implement this method.

        JSON representation returned by this method must adhere to :data:`schema` and pass
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
            JSON representation to validate, either previously returned by :meth:`as_json`
            or retrieved from an external source.

        Raises
        ------
        :exc:`InvalidAnnotation`
            If :py:`instance` doesn't conform to :attr:`schema`.
        """
        # TODO: Remove this. Ignore a deprecation warning from jschon's rfc3986 dependency.
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=DeprecationWarning)
            result = cls.__jschon_schema().evaluate(jschon.JSON(instance))

        if not result.valid:
            raise InvalidAnnotation("Invalid instance:\n" +
                                    pprint.pformat(result.output("basic")["errors"],
                                                   sort_dicts=False))

    def __repr__(self):
        return f"<{type(self).__module__}.{type(self).__qualname__} for {self.origin!r}>"


# For internal use only; we may consider exporting this function in the future.
def _extract_schemas(package, *, base_uri, path="schema/"):
    import sys
    import json
    import pathlib
    from importlib.metadata import distribution

    entry_points = distribution(package).entry_points
    for entry_point in entry_points.select(group="amaranth.lib.meta"):
        schema = entry_point.load().schema
        relative_path = entry_point.name # "0.5/component.json"
        schema_filename = pathlib.Path(path) / relative_path
        assert schema["$id"] == f"{base_uri}/{relative_path}", \
            f"Schema $id {schema['$id']} must be {base_uri}/{relative_path}"

        schema_filename.parent.mkdir(parents=True, exist_ok=True)
        with open(pathlib.Path(path) / relative_path, "wt") as schema_file:
            json.dump(schema, schema_file, indent=2)
        print(f"Extracted {schema['$id']} to {schema_filename}")

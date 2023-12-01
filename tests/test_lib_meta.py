import unittest
import jsonschema

from amaranth import *
from amaranth.lib.meta import *


class AnnotationTestCase(unittest.TestCase):
    def test_init_subclass(self):
        class MyAnnotation(Annotation):
            schema = {
                "$id": "https://example.com/schema/test/0.1/my-annotation.json",
            }

    def test_init_subclass_wrong_schema(self):
        with self.assertRaisesRegex(TypeError, r"Annotation schema must be a dict, not 'foo'"):
            class MyAnnotation(Annotation):
                schema = "foo"

    def test_init_subclass_schema_missing_id(self):
        with self.assertRaisesRegex(ValueError, r"'\$id' keyword is missing from Annotation schema: {}"):
            class MyAnnotation(Annotation):
                schema = {}

    def test_validate(self):
        class MyAnnotation(Annotation):
            schema = {
                "$id": "https://example.com/schema/test/0.1/my-annotation.json",
                "type": "object",
                "properties": {
                    "foo": {
                        "enum": [ "bar" ],
                    },
                },
                "additionalProperties": False,
                "required": [
                    "foo",
                ],
            }
        MyAnnotation.validate({"foo": "bar"})

    def test_validate_error(self):
        class MyAnnotation(Annotation):
            schema = {
                "$id": "https://example.com/schema/test/0.1/my-annotation.json",
                "type": "object",
                "properties": {
                    "foo": {
                        "enum": [ "bar" ],
                    },
                },
                "additionalProperties": False,
                "required": [
                    "foo",
                ],
            }
        with self.assertRaises(jsonschema.exceptions.ValidationError):
            MyAnnotation.validate({"foo": "baz"})

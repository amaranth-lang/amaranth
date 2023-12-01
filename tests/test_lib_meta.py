import unittest

from amaranth import *
from amaranth.lib.meta import *


class AnnotationTestCase(unittest.TestCase):
    def test_init_subclass(self):
        class MyAnnotation(Annotation):
            schema = {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "$id": "https://example.com/schema/test/0.1/my-annotation.json",
                "type": "string",
            }

            @property
            def origin(self):
                return "foo"

            @property
            def as_json(self):
                return "foo"

        self.assertRegex(repr(MyAnnotation()), r"<.+\.MyAnnotation for 'foo'>")

    def test_init_subclass_wrong_schema(self):
        with self.assertRaisesRegex(TypeError, r"Annotation schema must be a dict, not 'foo'"):
            class MyAnnotation(Annotation):
                schema = "foo"

    def test_init_subclass_schema_missing_id(self):
        with self.assertRaisesRegex(InvalidSchema, r"'\$id' keyword is missing from Annotation schema: {}"):
            class MyAnnotation(Annotation):
                schema = {}

    def test_init_subclass_schema_missing_schema(self):
        with self.assertRaises(InvalidSchema):
            class MyAnnotation(Annotation):
                schema = {
                    "$id": "https://example.com/schema/test/0.1/my-annotation.json",
                }

    def test_init_subclass_schema_error(self):
        with self.assertRaises(InvalidSchema):
            class MyAnnotation(Annotation):
                schema = {
                    "$schema": "https://json-schema.org/draft/2020-12/schema",
                    "$id": "https://example.com/schema/test/0.1/my-annotation.json",
                    "type": "foo",
                }

    def test_validate(self):
        class MyAnnotation(Annotation):
            schema = {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
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
                "$schema": "https://json-schema.org/draft/2020-12/schema",
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
        with self.assertRaises(InvalidAnnotation):
            MyAnnotation.validate({"foo": "baz"})

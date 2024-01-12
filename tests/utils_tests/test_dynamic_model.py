from django.test import TestCase
from django.db import models
from django_schema_sprout.apps import SchemaSproutAppConfig
from django_schema_sprout.models import DynamicDbModel
from django_schema_sprout.utils.dynamic_model import create_model


class DynamicModelTestCase(TestCase):
    def test_create_model(self):
        # Define attributes for the model
        attrs = {
            "field1": models.CharField(max_length=100),
            "field2": models.IntegerField(),
        }

        # Create a model using the create_model function
        model = create_model("my_database", "my_table", attrs, "my_schema")

        # Assert that the model is a subclass of DynamicDbModel
        self.assertTrue(issubclass(model, DynamicDbModel))

        # Assert that the model has the correct Meta attributes

        self.assertEqual(model._meta.db_table, '"my_schema"."my_table"')
        self.assertFalse(model._meta.managed)
        self.assertEqual(model.Meta._schema_sprout_db, "my_database")
        self.assertEqual(model.Meta.app_label, SchemaSproutAppConfig.name)

        # Assert that the model has the correct fields
        self.assertIsInstance(model.field1.field, models.CharField)
        self.assertIsInstance(model.field2.field, models.IntegerField)

        # Assert that the model has the correct name
        self.assertEqual(model.__name__, "my_schema_my_table")

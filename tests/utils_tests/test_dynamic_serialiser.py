from django.test import TestCase
from django.test.utils import isolate_apps
from django.db import models

from django_schema_sprout.utils.dynamic_serializer import create_serializer


class DynamicSerializerTestCase(TestCase):
    @isolate_apps("test")
    def test_create_serializer(self):
        # Create a test model
        class TestModel(models.Model):
            class Meta:
                app_label = "test"

            username = models.CharField(max_length=100, primary_key=True)
            name = models.CharField(max_length=100)
            age = models.IntegerField()

        # # Create a serializer for the test model
        model_serializer = create_serializer(TestModel)

        # # Create an instance of the test model
        test_instance = TestModel(name="John Doe", age=30, username="johndoe")

        # # Create a serializer instance
        serializer = model_serializer(instance=test_instance)
        # # Assert that the serializer data matches the test instance data
        self.assertDictEqual(
            serializer.data, {"name": "John Doe", "age": 30, "username": "johndoe"}
        )

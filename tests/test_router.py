from django.test import TestCase
from django_schema_sprout.router import SchemaSproutDBRouter


class RouterTestCase(TestCase):
    def setUp(self):
        class ModelWithMeta:
            class Meta:
                pass

        class ModelWithSchemaSproutDB:
            class Meta:
                _schema_sprout_db = "test_db"

        self.router = SchemaSproutDBRouter()

        self.model_without_meta = type("ModelWithoutMeta", (), {})
        self.model_with_meta = ModelWithMeta
        self.model_with_schema_sprout_db = ModelWithSchemaSproutDB

    def test_db_for_write(self):
        # Test case when model does not have Meta attribute
        self.assertIsNone(self.router.db_for_write(self.model_without_meta))

        # Test case when model has Meta attribute but no _schema_sprout_db attribute
        self.assertIsNone(self.router.db_for_write(self.model_with_meta))

        # Test case when model has Meta attribute with _schema_sprout_db attribute
        self.assertEqual(
            self.router.db_for_write(self.model_with_schema_sprout_db), "test_db"
        )

    def test_db_for_read(self):
        # Test case when model does not have Meta attribute
        self.assertIsNone(self.router.db_for_read(self.model_without_meta))

        # Test case when model has Meta attribute but no _schema_sprout_db attribute
        self.assertIsNone(self.router.db_for_read(self.model_with_meta))

        # Test case when model has Meta attribute with _schema_sprout_db attribute
        self.assertEqual(
            self.router.db_for_read(self.model_with_schema_sprout_db), "test_db"
        )

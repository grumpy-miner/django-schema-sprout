from unittest.mock import Mock

from django.test import TestCase

from django_schema_sprout.utils.db_inspector import get_inspector
from django_schema_sprout.db_inspectors.postgres_inspector import PostgresDBInspect


class DBInspectorTestCase(TestCase):
    def test_get_inspector_postgresql(self):
        connection = Mock()
        connection.vendor = "postgresql"

        # Call the get_inspector function
        inspector = get_inspector(connection)

        # Assert that the returned inspector is an instance of PostgresDBInspect
        self.assertIsInstance(inspector, PostgresDBInspect)

    def test_get_inspector_unsupported_database(self):
        connection = Mock()
        connection.vendor = "mysql"

        # Call the get_inspector function and assert raise of NotImplementedError
        with self.assertRaises(NotImplementedError):
            get_inspector(connection)

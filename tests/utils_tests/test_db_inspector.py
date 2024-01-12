from typing import Any
from unittest.mock import Mock

from django.test import TestCase
from django.db import connections
from django.db.utils import ConnectionHandler
from django.db.backends.postgresql.base import DatabaseWrapper

from django_schema_sprout.utils.db_inspector import get_inspector
from django_schema_sprout.db_inspectors import PostgresDBInspect


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

        # Call the get_inspector function and assert that it raises a NotImplementedError
        with self.assertRaises(NotImplementedError):
            get_inspector(connection)

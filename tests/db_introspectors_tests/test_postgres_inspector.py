import tempfile

import pytest
from pytest_postgresql import factories
from django.conf import settings
from django.db import connections
from django.db.models import DO_NOTHING
from django.db.models.fields import (
    TextField,
    IntegerField,
    AutoField,
    CharField,
    FloatField,
)
from django.db.models.fields.related import ForeignKey

from django_schema_sprout.db_inspectors.postgres_inspector import (
    PostgresDBInspect,
    TableInfo,
    FieldInfo,
)

# Using the factory to create a postgresql instance
socket_dir = tempfile.TemporaryDirectory()
postgresql_my_proc = factories.postgresql_proc(port=None, unixsocketdir=socket_dir.name)
postgresql_my = factories.postgresql("postgresql_my_proc")


@pytest.fixture(scope="function")
def database(postgresql_my):
    settings.DATABASES["django_test"] = {
        "ENGINE": "django.db.backends.postgresql_psycopg2",
    }
    with postgresql_my.cursor() as cursor:
        cursor.execute("CREATE SCHEMA foo;")
        cursor.execute("CREATE SCHEMA bar;")
        cursor.execute("GRANT ALL ON SCHEMA foo TO postgres;")
        cursor.execute("GRANT USAGE ON SCHEMA foo TO postgres;")
        cursor.execute("GRANT ALL ON SCHEMA bar TO postgres;")
        cursor.execute("GRANT USAGE ON SCHEMA bar TO postgres;")

        cursor.execute(
            """
        CREATE TABLE test (
            id serial,
            num FLOAT,
            data varchar,
            PRIMARY KEY(id, num)
        );
        """
        )

        cursor.execute(
            """
        CREATE TABLE foo.span (
            span_id TEXT PRIMARY KEY,
            span_text TEXT UNIQUE,
            span_num INTEGER
        );
        """
        )
        cursor.execute(
            """
        CREATE TABLE foo.eggs (
            eggs INTEGER PRIMARY KEY,
            eggs_text TEXT,
            span TEXT REFERENCES foo.span (span_id)
        );
        """
        )

        cursor.execute(
            """
        CREATE TABLE bar.baz (
            id serial PRIMARY KEY,
            foo_span TEXT REFERENCES foo.span (span_id)
        );
        """
        )

        cursor.execute(
            """
        CREATE TABLE bar.az (
            id serial PRIMARY KEY,
            baz INTEGER REFERENCES bar.baz (id)
        );
        """
        )

        cursor.execute(
            """
        CREATE TABLE bar.ab (
            id serial PRIMARY KEY,
            az INTEGER REFERENCES bar.az (id)
        );
        """
        )

        cursor.execute(
            """
        CREATE TABLE studies (
            nct_id VARCHAR PRIMARY KEY,
            CONSTRAINT studies_nct_id_fkey FOREIGN KEY (nct_id)
            REFERENCES studies(nct_id)
        );
        """
        )

        cursor.execute(
            """
        CREATE TABLE simple (
            name VARCHAR
        );
        """
        )

        cursor.execute(
            """
        CREATE TABLE unique_without_primary (
            name VARCHAR UNIQUE
        );
        """
        )

        cursor.execute(
            """
        CREATE TABLE primary_with_uique (
            id INTEGER PRIMARY KEY,
            name TEXT UNIQUE
        );
        """
        )

        cursor.execute(
            """
        CREATE TABLE reference_to_unique (
            id INTEGER PRIMARY KEY,
            name TEXT REFERENCES primary_with_uique (name)
        );
        """
        )

        cursor.execute(
            """
        CREATE TABLE test_table (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            age INT,
            email VARCHAR(255) UNIQUE,
            CONSTRAINT check_age CHECK (age >= 18)
        );

        CREATE INDEX idx_name ON test_table (name);
        CREATE INDEX idx_email ON test_table (email);
        """
        )

        cursor.execute('SET search_path = "$user", public, foo, bar;')

    yield postgresql_my


@pytest.mark.django_db
def test_get_table_list(database):
    inspector = PostgresDBInspect(connections["django_test"])
    with database.cursor() as cursor:
        expected_table_list = [
            TableInfo(name="span", type="t", comment=None, nspname="foo"),
            TableInfo(
                name="primary_with_uique", type="t", comment=None, nspname="public"
            ),
            TableInfo(name="simple", type="t", comment=None, nspname="public"),
            TableInfo(name="studies", type="t", comment=None, nspname="public"),
            TableInfo(name="test", type="t", comment=None, nspname="public"),
            TableInfo(name="test_table", type="t", comment=None, nspname="public"),
            TableInfo(
                name="unique_without_primary", type="t", comment=None, nspname="public"
            ),
            TableInfo(name="baz", type="t", comment=None, nspname="bar"),
            TableInfo(name="eggs", type="t", comment=None, nspname="foo"),
            TableInfo(
                name="reference_to_unique", type="t", comment=None, nspname="public"
            ),
            TableInfo(name="az", type="t", comment=None, nspname="bar"),
            TableInfo(name="ab", type="t", comment=None, nspname="bar"),
        ]
        table_list = inspector.get_table_list(cursor)

        assert table_list == expected_table_list


def test_get_relations(database):
    inspector = PostgresDBInspect(connections["django_test"])
    with database.cursor() as cursor:
        assert {} == inspector.get_relations(cursor, "span", "foo")
        assert {} == inspector.get_relations(cursor, "simple", "public")
        assert {"nct_id": ("nct_id", "studies", "public")} == inspector.get_relations(
            cursor, "studies", "public"
        )
        assert {} == inspector.get_relations(cursor, "test", "public")
        assert {} == inspector.get_relations(cursor, "baz", "bar")
        assert {"span": ("span_id", "span", "foo")} == inspector.get_relations(
            cursor, "eggs", "foo"
        )
        assert {"baz": ("id", "baz", "bar")} == inspector.get_relations(
            cursor, "az", "bar"
        )
        assert {"az": ("id", "az", "bar")} == inspector.get_relations(
            cursor, "ab", "bar"
        )
        assert {} == inspector.get_relations(cursor, "test_table", "public")


def test_get_constraints(database):
    inspector = PostgresDBInspect(connections["django_test"])
    with database.cursor() as cursor:
        assert inspector.get_constraints(cursor, "span", "foo") == {
            "span_pkey": {
                "columns": ["span_id"],
                "primary_key": True,
                "unique": True,
                "foreign_key": None,
                "check": False,
                "index": False,
                "definition": None,
                "options": None,
            },
            "span_span_text_key": {
                "columns": ["span_text"],
                "primary_key": False,
                "unique": True,
                "foreign_key": None,
                "check": False,
                "index": False,
                "definition": None,
                "options": None,
            },
        }
        assert inspector.get_constraints(cursor, "simple", "public") == {}
        assert inspector.get_constraints(cursor, "studies", "public") == {
            "studies_pkey": {
                "columns": ["nct_id"],
                "primary_key": True,
                "unique": True,
                "foreign_key": None,
                "check": False,
                "index": False,
                "definition": None,
                "options": None,
            },
            "studies_nct_id_fkey": {
                "columns": ["nct_id"],
                "primary_key": False,
                "unique": False,
                "foreign_key": ("studies", "nct_id"),
                "check": False,
                "index": False,
                "definition": None,
                "options": None,
            },
        }
        assert inspector.get_constraints(cursor, "test", "public") == {
            "test_pkey": {
                "columns": ["id", "num"],
                "primary_key": True,
                "unique": True,
                "foreign_key": None,
                "check": False,
                "index": False,
                "definition": None,
                "options": None,
            }
        }
        assert inspector.get_constraints(cursor, "baz", "bar") == {
            "baz_pkey": {
                "columns": ["id"],
                "primary_key": True,
                "unique": True,
                "foreign_key": None,
                "check": False,
                "index": False,
                "definition": None,
                "options": None,
            },
            "baz_foo_span_fkey": {
                "columns": ["foo_span"],
                "primary_key": False,
                "unique": False,
                "foreign_key": ("span", "span_id"),
                "check": False,
                "index": False,
                "definition": None,
                "options": None,
            },
        }
        assert inspector.get_constraints(cursor, "eggs", "foo") == {
            "eggs_pkey": {
                "columns": ["eggs"],
                "primary_key": True,
                "unique": True,
                "foreign_key": None,
                "check": False,
                "index": False,
                "definition": None,
                "options": None,
            },
            "eggs_span_fkey": {
                "columns": ["span"],
                "primary_key": False,
                "unique": False,
                "foreign_key": ("span", "span_id"),
                "check": False,
                "index": False,
                "definition": None,
                "options": None,
            },
        }
        assert inspector.get_constraints(cursor, "az", "bar") == {
            "az_pkey": {
                "columns": ["id"],
                "primary_key": True,
                "unique": True,
                "foreign_key": None,
                "check": False,
                "index": False,
                "definition": None,
                "options": None,
            },
            "az_baz_fkey": {
                "columns": ["baz"],
                "primary_key": False,
                "unique": False,
                "foreign_key": ("baz", "id"),
                "check": False,
                "index": False,
                "definition": None,
                "options": None,
            },
        }
        assert inspector.get_constraints(cursor, "ab", "bar") == {
            "ab_pkey": {
                "columns": ["id"],
                "primary_key": True,
                "unique": True,
                "foreign_key": None,
                "check": False,
                "index": False,
                "definition": None,
                "options": None,
            },
            "ab_az_fkey": {
                "columns": ["az"],
                "primary_key": False,
                "unique": False,
                "foreign_key": ("az", "id"),
                "check": False,
                "index": False,
                "definition": None,
                "options": None,
            },
        }
        assert inspector.get_constraints(cursor, "test_table", "public") == {
            "check_age": {
                "columns": ["age"],
                "primary_key": False,
                "unique": False,
                "foreign_key": None,
                "check": True,
                "index": False,
                "definition": None,
                "options": None,
            },
            "test_table_pkey": {
                "columns": ["id"],
                "primary_key": True,
                "unique": True,
                "foreign_key": None,
                "check": False,
                "index": False,
                "definition": None,
                "options": None,
            },
            "test_table_email_key": {
                "columns": ["email"],
                "primary_key": False,
                "unique": True,
                "foreign_key": None,
                "check": False,
                "index": False,
                "definition": None,
                "options": None,
            },
            "idx_email": {
                "columns": ["email"],
                "orders": ["ASC"],
                "primary_key": False,
                "unique": False,
                "foreign_key": None,
                "check": False,
                "index": True,
                "type": "idx",
                "definition": None,
                "options": None,
            },
            "idx_name": {
                "columns": ["name"],
                "orders": ["ASC"],
                "primary_key": False,
                "unique": False,
                "foreign_key": None,
                "check": False,
                "index": True,
                "type": "idx",
                "definition": None,
                "options": None,
            },
        }


def test_get_primary_key_column(database):
    inspector = PostgresDBInspect(connections["django_test"])
    with database.cursor() as cursor:
        assert inspector.get_primary_key_column(cursor, "span", "foo") == "span_id"
        assert inspector.get_primary_key_column(cursor, "simple", "public") is None
        assert inspector.get_primary_key_column(cursor, "studies", "public") == "nct_id"
        assert inspector.get_primary_key_column(cursor, "test", "public") == "id"
        assert inspector.get_primary_key_column(cursor, "baz", "bar") == "id"
        assert inspector.get_primary_key_column(cursor, "eggs", "foo") == "eggs"
        assert inspector.get_primary_key_column(cursor, "az", "bar") == "id"
        assert inspector.get_primary_key_column(cursor, "ab", "bar") == "id"
        assert inspector.get_primary_key_column(cursor, "test_table", "public") == "id"


def test_get_primary_key_columns(database):
    inspector = PostgresDBInspect(connections["django_test"])
    with database.cursor() as cursor:
        assert inspector.get_primary_key_columns(cursor, "span", "foo") == ["span_id"]
        assert inspector.get_primary_key_columns(cursor, "simple", "public") is None
        assert inspector.get_primary_key_columns(cursor, "studies", "public") == [
            "nct_id"
        ]
        assert inspector.get_primary_key_columns(cursor, "test", "public") == [
            "id",
            "num",
        ]
        assert inspector.get_primary_key_columns(cursor, "baz", "bar") == ["id"]
        assert inspector.get_primary_key_columns(cursor, "eggs", "foo") == ["eggs"]
        assert inspector.get_primary_key_columns(cursor, "az", "bar") == ["id"]
        assert inspector.get_primary_key_columns(cursor, "ab", "bar") == ["id"]
        assert inspector.get_primary_key_columns(cursor, "test_table", "public") == [
            "id"
        ]


def test_get_table_description(database):
    inspector = PostgresDBInspect(connections["django_test"])
    with database.cursor() as cursor:
        assert inspector.get_table_description(cursor, "span", "foo") == [
            FieldInfo(
                name="span_id",
                type_code=25,
                display_size=None,
                internal_size=None,
                precision=None,
                scale=None,
                null_ok=False,
                default=None,
                collation=None,
                is_autofield=False,
                comment=None,
            ),
            FieldInfo(
                name="span_text",
                type_code=25,
                display_size=None,
                internal_size=None,
                precision=None,
                scale=None,
                null_ok=True,
                default=None,
                collation=None,
                is_autofield=False,
                comment=None,
            ),
            FieldInfo(
                name="span_num",
                type_code=23,
                display_size=4,
                internal_size=4,
                precision=None,
                scale=None,
                null_ok=True,
                default=None,
                collation=None,
                is_autofield=False,
                comment=None,
            ),
        ]
        assert inspector.get_table_description(cursor, "simple", "public") == [
            FieldInfo(
                name="name",
                type_code=1043,
                display_size=None,
                internal_size=None,
                precision=None,
                scale=None,
                null_ok=True,
                default=None,
                collation=None,
                is_autofield=False,
                comment=None,
            )
        ]


def _test_attributes(expected, actual):
    assert expected.keys() == actual.keys()

    for key in expected:
        assert actual[key].__class__ == expected[key].pop("class")
        if "__fk_fields" in expected[key]:
            fk_fields = expected[key].pop("__fk_fields")
            actual[key].remote_field.on_delete = fk_fields["on_delete"]
            actual[key].remote_field.db_column = fk_fields["db_column"]
            actual[key].remote_model = fk_fields["to"]

        for attr in expected[key]:
            assert getattr(actual[key], attr) == expected[key][attr]


def test_get_attributes(database):
    inspector = PostgresDBInspect(connections["django_test"])
    with database.cursor() as cursor:
        expected_span_foo_attrs = {
            "span_id": {
                "primary_key": True,
                "blank": False,
                "null": False,
                "class": TextField,
            },
            "span_text": {
                "unique": True,
                "blank": True,
                "null": True,
                "class": TextField,
            },
            "span_num": {"class": IntegerField},
        }
        span_foo_attrs = inspector.get_attributes(cursor, "span", "foo")
        _test_attributes(expected_span_foo_attrs, span_foo_attrs)

        expected_simple_public_attrs = {
            "name": {"blank": True, "null": True, "class": TextField},
            "__str__": {"class": type(lambda: None)},
        }
        simple_public_attrs = inspector.get_attributes(cursor, "simple", "public")
        _test_attributes(expected_simple_public_attrs, simple_public_attrs)

        expected_studies_public_attrs = {
            "nct_id": {
                "primary_key": True,
                "blank": False,
                "null": False,
                "class": TextField,
            }
        }
        studies_public_attrs = inspector.get_attributes(cursor, "studies", "public")
        _test_attributes(expected_studies_public_attrs, studies_public_attrs)

        expected_test_public_attrs = {
            "id": {
                "primary_key": True,
                "blank": True,
                "null": False,
                "class": AutoField,
            },
            "num": {
                "primary_key": False,
                "blank": False,
                "null": False,
                "class": FloatField,
            },
            "data": {"blank": True, "null": True, "class": TextField},
        }
        test_public_attrs = inspector.get_attributes(cursor, "test", "public")
        _test_attributes(expected_test_public_attrs, test_public_attrs)

        expected_baz_bar_attrs = {
            "id": {
                "primary_key": True,
                "blank": True,
                "null": False,
                "class": AutoField,
            },
            "foo_span": {
                "primary_key": False,
                "blank": True,
                "null": True,
                "class": TextField,
            },
        }
        baz_bar_attrs = inspector.get_attributes(cursor, "baz", "bar")
        _test_attributes(expected_baz_bar_attrs, baz_bar_attrs)

        expected_eggs_foo_attrs = {
            "eggs": {
                "primary_key": True,
                "blank": False,
                "null": False,
                "class": IntegerField,
            },
            "eggs_text": {"blank": True, "null": True, "class": TextField},
            "span": {
                "primary_key": False,
                "blank": True,
                "null": True,
                "class": ForeignKey,
                "__fk_fields": {
                    "to": "foo_span",
                    "db_column": "span_id",
                    "on_delete": DO_NOTHING,
                },
            },
        }
        eggs_foo_attrs = inspector.get_attributes(cursor, "eggs", "foo")
        _test_attributes(expected_eggs_foo_attrs, eggs_foo_attrs)

        expected_az_bar_attrs = {
            "id": {
                "primary_key": True,
                "blank": True,
                "null": False,
                "class": AutoField,
            },
            "baz": {
                "primary_key": False,
                "blank": True,
                "null": True,
                "class": ForeignKey,
                "__fk_fields": {
                    "to": "baz",
                    "db_column": "id",
                    "on_delete": DO_NOTHING,
                },
            },
        }
        az_bar_attrs = inspector.get_attributes(cursor, "az", "bar")
        _test_attributes(expected_az_bar_attrs, az_bar_attrs)

        expected_ab_bar_attrs = {
            "id": {
                "primary_key": True,
                "blank": True,
                "null": False,
                "class": AutoField,
            },
            "az": {
                "primary_key": False,
                "blank": True,
                "null": True,
                "class": ForeignKey,
                "__fk_fields": {
                    "to": "az",
                    "db_column": "id",
                    "on_delete": DO_NOTHING,
                },
            },
        }
        ab_bar_attrs = inspector.get_attributes(cursor, "ab", "bar")
        _test_attributes(expected_ab_bar_attrs, ab_bar_attrs)

        expected_test_table_public_attrs = {
            "id": {
                "primary_key": True,
                "blank": True,
                "null": False,
                "class": AutoField,
            },
            "name": {"blank": False, "null": False, "class": CharField},
            "age": {"blank": True, "null": True, "class": IntegerField},
            "email": {
                "unique": True,
                "blank": True,
                "null": True,
                "class": CharField,
            },
            "__str__": {"class": type(lambda: None)},
        }
        test_table_public_attrs = inspector.get_attributes(
            cursor, "test_table", "public"
        )
        _test_attributes(expected_test_table_public_attrs, test_table_public_attrs)

        expected_unique_without_primary = {
            "name": {
                "primary_key": True,
                "blank": False,
                "null": False,
                "class": TextField,
            },
            "__str__": {"class": type(lambda: None)},
        }
        unique_without_primary_public_attrs = inspector.get_attributes(
            cursor, "unique_without_primary", "public"
        )
        _test_attributes(
            expected_unique_without_primary, unique_without_primary_public_attrs
        )

        expected_reference_to_unique = {
            "name": {
                "primary_key": False,
                "blank": True,
                "null": True,
                "class": ForeignKey,
                "__fk_fields": {
                    "to": "primary_with_uique",
                    "db_column": "name",
                    "on_delete": DO_NOTHING,
                },
            },
            "id": {"primary_key": True, "class": IntegerField},
            "__str__": {"class": type(lambda: None)},
        }
        actual_reference_to_unique = inspector.get_attributes(
            cursor, "reference_to_unique", "public"
        )
        _test_attributes(expected_reference_to_unique, actual_reference_to_unique)


def test_get_field_type():
    inspector = PostgresDBInspect(connections["django_test"])
    row = FieldInfo(
        name="wallet",
        type_code=1700,
        display_size=None,
        internal_size=None,
        precision=None,
        scale=None,
        null_ok=True,
        default=None,
        collation=None,
        is_autofield=False,
        comment=None,
    )

    field_type, field_params, field_notes = inspector.get_field_type(row)
    assert field_type == "DecimalField"
    assert field_params == {"max_digits": 10, "decimal_places": 5}
    assert field_notes == [
        "max_digits and decimal_places have been guessed, as this "
        "database handles decimal fields as float"
    ]

    row = FieldInfo(
        name="wallet",
        type_code=1700,
        display_size=None,
        internal_size=None,
        precision=5,
        scale=3,
        null_ok=True,
        default=None,
        collation=None,
        is_autofield=False,
        comment=None,
    )

    field_type, field_params, field_notes = inspector.get_field_type(row)
    assert field_type == "DecimalField"
    assert field_params == {"max_digits": 5, "decimal_places": 3}
    assert field_notes == []

    row = FieldInfo(
        name="wallet",
        type_code=1043,
        display_size=30,
        internal_size=None,
        precision=5,
        scale=3,
        null_ok=True,
        default=None,
        collation="C",
        is_autofield=False,
        comment=None,
    )

    field_type, field_params, field_notes = inspector.get_field_type(row)
    assert field_type == "CharField"
    assert field_params == {"max_length": 30, "db_collation": "C"}
    assert field_notes == []

    row = FieldInfo(
        name="wallet",
        type_code=666,
        display_size=30,
        internal_size=None,
        precision=5,
        scale=3,
        null_ok=True,
        default=None,
        collation="C",
        is_autofield=False,
        comment=None,
    )

    field_type, field_params, field_notes = inspector.get_field_type(row)
    assert field_type == "TextField"
    assert field_params == {"db_collation": "C"}
    assert field_notes == ["This field type is a guess."]

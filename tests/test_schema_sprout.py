import tempfile

import pytest
from pytest_postgresql import factories
from django.conf import settings
from django.db import connections
from rest_framework.routers import DefaultRouter
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from django_schema_sprout.schema_sprout import SchemaSprout
from django.db import ProgrammingError


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
        cursor.execute("GRANT ALL ON SCHEMA foo TO postgres;")
        cursor.execute("GRANT USAGE ON SCHEMA foo TO postgres;")

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
        CREATE TABLE foo.test (
            id serial,
            num FLOAT,
            data varchar,
            PRIMARY KEY(id, num)
        );"""
        )

        cursor.execute("CREATE VIEW test_view as SELECT * from test")

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
            CREATE TABLE studies (
                nct_id varchar PRIMARY KEY,
                CONSTRAINT studies_nct_id_fkey FOREIGN KEY (nct_id)
                REFERENCES studies(nct_id)
            );
            """
        )
        cursor.execute('SET search_path = "$user", public, foo;')

    old_cursor = connections["django_test"].cursor
    connections["django_test"].cursor = postgresql_my.cursor

    yield postgresql_my

    connections["django_test"].cursor = old_cursor


@pytest.fixture(scope="function")
def schema_sprout():
    schema_sprout = SchemaSprout("django_test")
    yield schema_sprout
    SchemaSprout._instances = {}
    SchemaSprout._init = {}


def test_schema_sprout_init(database, schema_sprout):
    assert schema_sprout.connection == connections["django_test"]
    assert schema_sprout.views == {}
    assert schema_sprout.serializers == {}
    assert schema_sprout.models == {}
    assert isinstance(schema_sprout.router, DefaultRouter)


def _test_create_models(_schema_sprout, viewset_class):
    schema_sprout = _schema_sprout

    assert len(schema_sprout.models) == 5

    assert "foo_span" in schema_sprout.models
    assert "foo_eggs" in schema_sprout.models
    # Same tables in different schemas should be created with different models
    assert "public_test" in schema_sprout.models
    assert "foo_test" in schema_sprout.models
    assert "public_studies" in schema_sprout.models

    # Views should not be created as models
    assert "public_test_view" not in schema_sprout.models

    assert len(schema_sprout.serializers) == 5
    assert len(schema_sprout.views) == 5

    for url_path in [
        "foo/span",
        "foo/eggs",
        "public/test",
        "foo/test",
        "public/studies",
    ]:
        registered_correctly = False
        for registry in schema_sprout.router.registry:
            if registry[0] == url_path and issubclass(registry[1], viewset_class):
                registered_correctly = True

        assert registered_correctly


def test_schema_sprout_create_models(database, schema_sprout):
    schema_sprout.create_models()

    _test_create_models(schema_sprout, ModelViewSet)


def test_schema_sprout_create_models_read_only(database, schema_sprout):
    schema_sprout.create_models(readonly=True)
    _test_create_models(schema_sprout, ReadOnlyModelViewSet)


def test_schema_sprout_create_model(database, schema_sprout):
    schema_sprout.create_model("test", "public")

    assert len(schema_sprout.models) == 1
    assert "public_test" in schema_sprout.models

    assert schema_sprout.router.registry[0][0] == "public/test"
    assert issubclass(schema_sprout.router.registry[0][1], ModelViewSet)


def test_schema_sprout_create_same_model_two_times(database, schema_sprout):
    schema_sprout.create_model("test", "public")
    schema_sprout.create_model("test", "public")

    assert len(schema_sprout.models) == 1
    assert "public_test" in schema_sprout.models

    assert schema_sprout.router.registry[0][0] == "public/test"
    assert issubclass(schema_sprout.router.registry[0][1], ModelViewSet)


def test_schema_sprout_create_model_read_only(database, schema_sprout):
    schema_sprout.create_model("test", "public", readonly=True)

    assert len(schema_sprout.models) == 1
    assert "public_test" in schema_sprout.models

    assert schema_sprout.router.registry[0][0] == "public/test"
    assert issubclass(schema_sprout.router.registry[0][1], ReadOnlyModelViewSet)


def test_schema_sprout_create_model_table_permission_denied(
    database, schema_sprout, monkeypatch
):
    def mock_get_attributes(*args, **kwargs):
        raise ProgrammingError("access denied on table baz")

    monkeypatch.setattr(
        schema_sprout.db_inspector, "get_attributes", mock_get_attributes
    )

    schema_sprout.create_model("bar", "baz")

    assert len(schema_sprout.models) == 0
    assert "public_test" not in schema_sprout.models

    assert schema_sprout.router.registry == []

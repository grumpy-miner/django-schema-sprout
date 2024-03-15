import logging

from django.db import connections
from django.db.utils import ProgrammingError
from rest_framework.routers import DefaultRouter

from django_schema_sprout.utils.db_inspector import get_inspector
from django_schema_sprout.utils.dynamic_view import create_view
from django_schema_sprout.utils.dynamic_model import create_model
from django_schema_sprout.utils.dynamic_serializer import create_serializer
from django_schema_sprout.utils.singleton_class import SingletonArgs


class SchemaSprout(metaclass=SingletonArgs):

    def __init__(self, database: str):
        self.database = database
        self.connection = connections[self.database]
        self.db_inspector = get_inspector(self.connection)

        self.views = dict()
        self.serializers = dict()
        self.models = dict()

        self.router = DefaultRouter()

    def create_models(self, readonly: bool = False):
        # Create models only for tables
        types = {"t"}
        with self.connection.cursor() as cursor:
            tables_info = self.db_inspector.get_table_list(cursor)

        for table in tables_info:
            if table.type not in types:
                continue
            table_name = table.name
            table_nspname = table.nspname
            self.create_model(table_name, table_nspname, readonly)

    def create_model(self, table_name, table_nspname, readonly: bool = False):
        nsp_name = f"{table_nspname}_{table_name}"
        if (
            nsp_name in self.models
            and nsp_name in self.serializers
            and nsp_name in self.views
        ):
            return

        with self.connection.cursor() as cursor:
            try:
                attrs = self.db_inspector.get_attributes(
                    cursor, table_name, table_nspname
                )

                model = self.models.get(
                    nsp_name,
                    create_model(self.database, table_name, attrs, table_nspname),
                )
                self.models[nsp_name] = model

                serializer = self.serializers.get(nsp_name, create_serializer(model))
                self.serializers[nsp_name] = serializer

                view = create_view(model, serializer, readonly)
                self.views[nsp_name] = view

                _table_nspname = table_nspname.lower().replace("_", "-")
                _table_name = table_name.lower().replace("_", "-")

                self.router.register(f"{_table_nspname}/{_table_name}", view)

            except ProgrammingError as err:
                logging.warning(
                    f"Couldn't get table description for table {table_name}. "
                    f"Reason: {err}"
                )

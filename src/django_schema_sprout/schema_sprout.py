import logging

from django.db import connections
from django.db.utils import ProgrammingError
from rest_framework.routers import DefaultRouter

from django_schema_sprout.utils.db_inspector import get_inspector
from django_schema_sprout.utils.dynamic_view import create_view
from django_schema_sprout.utils.dynamic_model import create_model
from django_schema_sprout.utils.dynamic_serializer import create_serializer
from django_schema_sprout.utils.singleton_class import SingletonArgs


class SchemaSprout:
    __metaclass__ = SingletonArgs

    def __init__(self, database: str, readonly: bool = False):
        self.database = database
        self.readonly = readonly

        self.views = list()
        self.serializers = list()
        self.models = dict()

        self.router = DefaultRouter()

        self.create_models()

    def create_models(self):
        connection = connections[self.database]
        db_inspector = get_inspector(connection)

        # Create models only for tables
        types = {"t"}
        with connection.cursor() as cursor:
            tables_info = db_inspector.get_table_list(cursor)
            for table in tables_info:
                if table.type not in types:
                    continue
                table_name = table.name
                table_nspname = table.nspname
                if table_name == "studies" or table_name == "designs":
                    pass
                else:
                    continue
                try:
                    attrs = db_inspector.get_attributes(
                        cursor, table_name, table_nspname
                    )

                    model = self.models.get(
                        f"{table_nspname}_{table_name}",
                        create_model(self.database, table_name, attrs, table_nspname),
                    )
                    self.models[f"{table_nspname}_{table_name}"] = model
                    serializer = create_serializer(model)
                    self.serializers.append(serializer)
                    view = create_view(model, serializer, self.readonly)
                    self.views.append(view)
                    _table_nspname = table_nspname.lower().replace("_", "-")
                    _table_name = table_name.lower().replace("_", "-")
                    self.router.register(rf"{_table_nspname}/{_table_name}", view)

                except ProgrammingError as err:
                    logging.warning(
                        f"Couldn't get table description for table {table_name}. Reason: {err}"
                    )
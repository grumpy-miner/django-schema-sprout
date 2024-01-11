from django.db import models

from django_schema_sprout.apps import SchemaSproutAppConfig
from django_schema_sprout.models import DynamicDbModel


def create_model(
    database: str, table_name: str, attrs: dict, nspname: str
) -> models.Model:
    class Meta(DynamicDbModel.Meta):
        db_table = f'"{nspname}"."{table_name}"'
        _schema_sprout_db = database
        managed = False
        app_label = SchemaSproutAppConfig.name

    attrs["Meta"] = Meta
    attrs["__module__"] = f"{SchemaSproutAppConfig.name}.models"
    model = type(f"{nspname}_{table_name}", (DynamicDbModel,), attrs)
    model.Meta._schema_sprout_db = database

    return model

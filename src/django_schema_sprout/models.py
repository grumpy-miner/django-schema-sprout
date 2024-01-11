from django.db import models

from django_schema_sprout.apps import SchemaSproutAppConfig

app_label = SchemaSproutAppConfig.name


class DynamicDbModel(models.Model):
    class Meta:
        abstract = True
        app_label = app_label

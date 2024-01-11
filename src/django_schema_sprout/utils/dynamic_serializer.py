from django.db import models
from rest_framework import serializers


def create_serializer(model: models.Model) -> type:
    fields = [field.name for field in model._meta.fields]

    meta_class = type(
        "Meta",
        (),
        {"model": model, "fields": fields},
    )

    return type(
        f"{model.__name__}Serializer",
        (serializers.ModelSerializer,),
        {"Meta": meta_class},
    )

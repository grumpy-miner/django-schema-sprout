from django_schema_sprout.models import DynamicDbModel
from rest_framework import viewsets
from rest_framework import serializers


def create_view(
    model: DynamicDbModel,
    serializer: serializers.ModelSerializer,
    readonly: bool = False,
) -> type:
    """
    Create a view class for the given model and serializer.

    Args:
        serializer (serializers.ModelSerializer): The serializer class to use.
        model (DynamicDbModel): The model to create the view for.
        readonly (bool, optional): Whether the view should be read-only. Default False.

    Returns:
        type: The dynamically created view class.
    """
    # Implementation code goes here
    queryset = model.objects.all()
    serializer_class = serializer
    if readonly:
        viewset = viewsets.ReadOnlyModelViewSet
    else:
        viewset = viewsets.ModelViewSet
    return type(
        f"{model.__name__}ViewSet",
        (viewset,),
        {"queryset": queryset, "serializer_class": serializer_class},
    )

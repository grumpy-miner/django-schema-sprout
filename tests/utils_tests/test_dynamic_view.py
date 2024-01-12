from django.test import TestCase
from django.test.utils import isolate_apps
from django.db import models
from rest_framework import serializers
from rest_framework import viewsets
from django_schema_sprout.utils.dynamic_view import create_view


class TestDynamicView(TestCase):
    @isolate_apps("test")
    def test_create_view(self):
        class TestModel(models.Model):
            class Meta:
                app_label = "test"

            pass

        # Create a test serializer
        class TestSerializer(serializers.ModelSerializer):
            class Meta:
                model = TestModel
                fields = "__all__"

        # Create a view class using the create_view function
        view_class = create_view(TestModel, TestSerializer)

        # Assert that the view class is a subclass of the appropriate viewset class
        self.assertTrue(issubclass(view_class, viewsets.ModelViewSet))

        self.assertEqual(view_class.serializer_class, TestSerializer)

    @isolate_apps("test")
    def test_create_view_readonly(self):
        class TestModel(models.Model):
            class Meta:
                app_label = "test"

            pass

        # Create a test serializer
        class TestSerializer(serializers.ModelSerializer):
            class Meta:
                model = TestModel
                fields = "__all__"

        readonly_view_class = create_view(TestModel, TestSerializer, readonly=True)

        self.assertTrue(issubclass(readonly_view_class, viewsets.ReadOnlyModelViewSet))

        self.assertEqual(readonly_view_class.serializer_class, TestSerializer)

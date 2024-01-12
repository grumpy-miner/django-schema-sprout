import unittest

from django_schema_sprout.utils.singleton_class import SingletonArgs


class SingletonMetaTestCase(unittest.TestCase):
    def setUp(self):
        class DummyClass(metaclass=SingletonArgs):
            def __init__(self, arg1, arg2):
                pass

        class DummyClassWithoutInit(metaclass=SingletonArgs):
            pass

        self.DummyClass = DummyClass
        self.DummyClassWithoutInit = DummyClassWithoutInit

    def test_two_initalizations_with_same_args(self):
        # Initialize two instances of DummyClass with the same arguments
        dummy_instance_1 = self.DummyClass("test", "testButDiiferent")
        dummy_instance_2 = self.DummyClass("test", "testButDiiferent")

        # Assert that the two instances are the same
        self.assertEqual(id(dummy_instance_1), id(dummy_instance_2))

    def test_two_initalizations_with_different_args(self):
        # Initialize two instances of DummyClass with the same arguments
        dummy_instance_1 = self.DummyClass("test", "testButDiiferent")
        dummy_instance_2 = self.DummyClass("test", "testButThisTimeDiiferent")

        # Assert that the two instances are not the same
        self.assertNotEqual(id(dummy_instance_1), id(dummy_instance_2))

    def test_two_initalizations_with_no_args(self):
        # Initialize two instances of DummyClass with no arguments
        dummy_instance_1 = self.DummyClassWithoutInit()
        dummy_instance_2 = self.DummyClassWithoutInit()

        # Assert that the two instances are the same
        self.assertEqual(id(dummy_instance_1), id(dummy_instance_2))

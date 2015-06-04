from unittest import TestCase

class Foobar(TestCase):

    def setUp(self):
        self.bla = "bla"

    def testFooBar(self):
        self.assertEquals(self.bla, "bla")

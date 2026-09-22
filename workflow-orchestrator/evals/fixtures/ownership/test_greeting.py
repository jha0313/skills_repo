import unittest

from greeting import greet


class GreetTests(unittest.TestCase):
    def test_greet_format(self):
        self.assertEqual(greet("지수"), "안녕하세요, 지수님")

    def test_greet_strips_name(self):
        self.assertEqual(greet("  민준 "), "안녕하세요, 민준님")


if __name__ == "__main__":
    unittest.main()

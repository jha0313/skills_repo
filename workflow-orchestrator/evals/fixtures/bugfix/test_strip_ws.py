import unittest

from strip_ws import normalize


class NormalizeTests(unittest.TestCase):
    def test_collapses_tabs_and_newlines(self):
        self.assertEqual(normalize("a\t b\n\nc"), "a b c")

    def test_strips_edges(self):
        self.assertEqual(normalize("  a  b  "), "a b")


if __name__ == "__main__":
    unittest.main()

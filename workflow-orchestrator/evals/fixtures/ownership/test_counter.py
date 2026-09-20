import unittest

from counter import count_words


class CountWordsTests(unittest.TestCase):
    def test_counts_words(self):
        self.assertEqual(count_words("하나 둘  셋"), 3)

    def test_empty_is_zero(self):
        self.assertEqual(count_words("   "), 0)


if __name__ == "__main__":
    unittest.main()

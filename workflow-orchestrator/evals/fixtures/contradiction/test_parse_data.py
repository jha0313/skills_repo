import unittest

from parse_data import load_amounts


class LoadAmountsTests(unittest.TestCase):
    def test_reads_three_rows(self):
        rows = load_amounts("data.csv")
        self.assertEqual(rows, [("apple", 120), ("banana", 80), ("cherry", 45)])


if __name__ == "__main__":
    unittest.main()

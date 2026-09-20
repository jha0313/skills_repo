import csv


def load_amounts(path):
    """data.csv를 읽어 (item, amount) 튜플 목록을 돌려준다."""
    with open(path, newline="", encoding="utf-8") as handle:
        return [(row["item"], int(row["amount"])) for row in csv.DictReader(handle)]

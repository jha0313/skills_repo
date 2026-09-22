"""report.md의 '## 합계' 값이 data.csv 금액 합과 일치하는지 직접 검사한다. 불일치면 종료 코드 1."""
import re
import sys

from parse_data import load_amounts

expected = sum(amount for _, amount in load_amounts("data.csv"))
text = open("report.md", encoding="utf-8").read()
match = re.search(r"## 합계\s*\n\s*(\d+)", text)
if not match:
    print("FAIL: '## 합계' 섹션을 찾을 수 없음")
    sys.exit(1)
actual = int(match.group(1))
if actual != expected:
    print(f"FAIL: report.md 합계 {actual} != data.csv 합계 {expected}")
    sys.exit(1)
print(f"PASS: 합계 {actual} 일치")

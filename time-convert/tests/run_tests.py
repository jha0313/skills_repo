#!/usr/bin/env python3
"""when.py 테스트. 고정 규칙 시간대와 이미 지난 날짜만 쓴다(앞으로 규칙이 바뀌어도 같은 결과).

사용: python3 tests/run_tests.py
"""
import json
import os
import shlex
import subprocess
import sys
import unittest

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "when.py")
SEOUL, PHX, LA, LDN = "Asia/Seoul", "America/Phoenix", "America/Los_Angeles", "Europe/London"


def call(*args, tz=PHX, places=None, as_json=True):
    env = {"PATH": "/usr/bin:/bin"}
    if tz is not None:
        env["TZ"] = tz
    if places is not None:
        env["WHEN_PLACES"] = places
    return subprocess.run([sys.executable, "-I", SCRIPT, *args, *(["--json"] if as_json else [])],
                          capture_output=True, text=True, encoding="utf-8", env=env)


class When(unittest.TestCase):
    def ok(self, *args, code=0, **kw):
        r = call(*args, **kw)
        self.assertEqual(r.returncode, code, r.stdout + r.stderr)
        return json.loads(r.stdout)

    def bad(self, *args, say="", **kw):
        r = call(*args, **kw)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        self.assertIn(say, r.stderr)
        return r.stderr

    def local(self, out, zone, i=0):
        return next(r["local"] for r in out["results"][i]["rows"] if r["zone"] == zone)

    def rows(self, out, i=0):
        return {r["zone"]: r for r in out["results"][i]["rows"]}

    # 변환
    def test_several_cities_weekday_and_day_rollover(self):
        out = self.ok("2025-11-24 14:00", "--from", SEOUL, "--to", f"여기,UTC,{LDN}")
        r = self.rows(out)
        self.assertEqual((r[SEOUL]["local"], r[SEOUL]["weekday"], r[SEOUL]["day_diff"]), ("2025-11-24T14:00+09:00", "월", 0))
        self.assertEqual((r[PHX]["local"], r[PHX]["weekday"], r[PHX]["day_diff"]), ("2025-11-23T22:00-07:00", "일", -1))
        self.assertEqual(r["UTC"]["local"], "2025-11-24T05:00+00:00")
        self.assertEqual(out["results"][0]["utc"], "2025-11-24T05:00Z")
        out = self.ok("2025-11-23 22:00", "--to", SEOUL)
        self.assertEqual(self.rows(out)[SEOUL]["day_diff"], 1)

    def test_summer_and_winter_differ(self):
        self.assertEqual(self.local(self.ok("2025-01-15 09:00", "--from", LA, "--to", SEOUL), SEOUL), "2025-01-16T02:00+09:00")
        self.assertEqual(self.local(self.ok("2025-07-15 09:00", "--from", LA, "--to", SEOUL), SEOUL), "2025-07-16T01:00+09:00")

    def test_weeks_when_only_one_side_changed(self):
        self.assertEqual(self.local(self.ok("2025-03-20 09:00", "--from", LA, "--to", LDN), LDN), "2025-03-20T16:00+00:00")
        self.assertEqual(self.local(self.ok("2025-04-10 09:00", "--from", LA, "--to", LDN), LDN), "2025-04-10T17:00+01:00")

    def test_same_zone_is_listed_once(self):
        out = self.ok("2025-11-24 14:00", "--from", SEOUL, "--to", f"{SEOUL},asia/seoul,여기,{PHX}")
        self.assertEqual([r["zone"] for r in out["results"][0]["rows"]], [SEOUL, PHX])

    def test_half_hour_offsets(self):
        # 예전 계산은 음수 30분 시차를 한 시간 틀리게 적었다(UTC-3:30 → UTC-4:30)
        r = self.rows(self.ok("2025-01-15 12:00", "--from", "UTC", "--to", "America/St_Johns,Asia/Kathmandu"))
        self.assertEqual(r["America/St_Johns"]["utc_offset"], "UTC-3:30")
        self.assertEqual(r["Asia/Kathmandu"]["utc_offset"], "UTC+5:45")

    # 서머타임
    def test_nonexistent_time_is_not_converted(self):
        for when, zone, near in (("2025-03-09 02:30", LA, ("01:30", "03:30")), ("2025-03-30 01:30", LDN, ("00:30", "02:30"))):
            with self.subTest(zone):
                out = self.ok(when, "--from", zone, "--to", SEOUL, code=3)
                self.assertEqual(out["results"], [])
                for text in ("없는 시각", "60분", *near):
                    self.assertIn(text, out["warnings"][0])

    def test_ambiguous_time_gives_both(self):
        for when, zone, first, second in (("2025-11-02 01:30", LA, "2025-11-02T08:30Z", "2025-11-02T09:30Z"),
                                          ("2025-10-26 01:30", LDN, "2025-10-26T00:30Z", "2025-10-26T01:30Z")):
            with self.subTest(zone):
                out = self.ok(when, "--from", zone, "--to", SEOUL, code=3)
                self.assertEqual([x["utc"] for x in out["results"]], [first, second])
                self.assertIn("두 번 온다", out["warnings"][0])
                self.assertEqual([self.rows(out, i)[zone]["repeated"] for i in (0, 1)], ["첫 번째", "두 번째"])

    def test_target_in_repeated_hour_is_marked(self):
        for when, which, off in (("2025-11-02 08:30", "첫 번째", "UTC-7"), ("2025-11-02 09:30", "두 번째", "UTC-8")):
            r = self.rows(self.ok(when, "--from", "UTC", "--to", LA))[LA]
            self.assertEqual((r["local"][11:16], r["repeated"], r["utc_offset"]), ("01:30", which, off))

    def test_edges_of_the_change_are_normal_times(self):
        for when in ("2025-03-09 01:59", "2025-03-09 03:00", "2025-11-02 00:59", "2025-11-02 02:00"):
            self.assertEqual(len(self.ok(when, "--from", LA)["results"]), 1)

    def test_change_day_is_marked_per_city(self):
        r = self.rows(self.ok("2025-03-09 12:00", "--from", LA, "--to", f"{LDN},{SEOUL}"))
        self.assertEqual(r[LA]["offset_change"], "UTC-8 → UTC-7")
        self.assertIsNone(r[LDN]["offset_change"])
        self.assertIsNone(r[SEOUL]["offset_change"])
        self.assertIsNone(self.rows(self.ok("2025-03-10 12:00", "--from", LA))[LA]["offset_change"])

    # 남은 시간
    def test_remaining_time_counts_real_hours_across_dst(self):
        # 예전 계산은 벽시계끼리 빼서 24시간이라고 했다
        out = self.ok("2025-03-09 12:00", "--from", LA, "--now", "2025-03-08 12:00")
        self.assertEqual(out["results"][0]["from_now"], "23시간 0분 뒤")
        out = self.ok("2025-11-02 12:00", "--from", LA, "--now", "2025-11-01 12:00")
        self.assertEqual(out["results"][0]["from_now"], "1일 1시간 0분 뒤")

    def test_base_time_that_comes_twice_is_not_guessed(self):
        # 예전에는 첫 번째를 조용히 골라 남은 시간이 한 시간 달랐다
        say = self.bad("2025-11-02 03:30", "--from", "America/New_York", "--now", "2025-11-02 01:30", say="두 번 온다")
        for text in ("2025-11-02 05:30", "2025-11-02 06:30", "--from UTC"):
            self.assertIn(text, say)
        for now, text in (("05:30", "3시간 0분 뒤"), ("06:30", "2시간 0분 뒤")):   # 안내한 대로 다시 돌릴 수 있다
            out = self.ok("2025-11-02 08:30", "--from", "UTC", "--now", "2025-11-02 " + now)
            self.assertEqual(out["results"][0]["from_now"], text)

    def test_remaining_time_past_and_now(self):
        for when, text, minutes in (("2025-11-20 09:30", "2시간 30분 전", -150), ("2025-11-20 12:00", "지금", 0),
                                    ("2025-11-23 13:05", "3일 1시간 5분 뒤", 4385)):
            res = self.ok(when, "--from", SEOUL, "--now", "2025-11-20 12:00")["results"][0]
            self.assertEqual((res["from_now"], res["from_now_minutes"]), (text, minutes))

    def test_now(self):
        out = self.ok("now", "--from", SEOUL, "--to", "UTC", "--now", "2025-11-20 12:00")
        self.assertEqual(self.local(out, "UTC"), "2025-11-20T03:00+00:00")
        self.assertEqual(len(self.ok("now", "--to", "UTC")["results"]), 1)

    # 입력 읽기
    def test_input_forms(self):
        for text, want in (("2025-11-24 14:00", "2025-11-24T14:00"), ("2025-11-24T14:00", "2025-11-24T14:00"),
                           ("2025/11/24 2:05 pm", "2025-11-24T14:05"), ("11/24(월) 오후 2시", "2025-11-24T14:00"),
                           ("11월 23일 오후 2시 반", "2025-11-23T14:30"), ("2024년 11월 23일 14시 5분", "2024-11-23T14:05"),
                           ("11/24 (Mon) 1:30pm", "2025-11-24T13:30"), ("오전 12시 5분", "2025-11-19T00:05"),
                           ("오후 12시", "2025-11-19T12:00"), ("금요일에 9:00에", "2025-11-21T09:00"),
                           ("금 오후 1시", "2025-11-21T13:00"), ("수 9:00", "2025-11-19T09:00")):
            with self.subTest(text):
                out = self.ok(text, "--from", SEOUL, "--now", "2025-11-19 22:00")
                self.assertEqual(self.local(out, SEOUL), want + "+09:00")

    def test_relative_days(self):
        for text, want in (("오늘 9:00", "2025-01-31"), ("내일 9:00", "2025-02-01"), ("내일모레 9:00", "2025-02-02"),
                           ("모레 9:00", "2025-02-02")):
            with self.subTest(text):
                out = self.ok(text, "--from", SEOUL, "--now", "2025-01-31 22:00")
                self.assertEqual(self.local(out, SEOUL)[:10], want)

    def test_relative_day_uses_source_zone(self):
        # 서울은 이미 2월 1일, 기준 컴퓨터(Phoenix)는 1월 31일
        out = self.ok("내일 9:00", "--from", SEOUL, "--now", "2025-02-01 03:00")
        self.assertEqual(self.local(out, SEOUL)[:10], "2025-02-02")

    def test_assumptions_are_reported(self):
        for text, note in (("11/24 14:00", "2025년"), ("14:00", "오늘 2025-11-19(수)"), ("금 14:00", "2025-11-21(금)")):
            self.assertIn(note, self.ok(text, "--from", SEOUL, "--now", "2025-11-19 22:00")["notes"][0])
        self.assertEqual(self.ok("2025-11-24 14:00", "--from", SEOUL)["notes"], [])

    def test_wrong_weekday_warns(self):
        for text in ("2025-11-22(금) 13:00", "2025-11-22 금요일 13:00", "2025-11-22 Fri 13:00"):
            out = self.ok(text, "--from", SEOUL, code=3)
            self.assertIn("금요일이 아니라 토요일", out["warnings"][0])
        self.ok("2025-11-21(금) 13:00", "--from", SEOUL)
        self.ok("내일(토) 13:00", "--from", SEOUL, "--now", "2025-11-19 12:00", code=3)

    def test_two_weekdays_that_disagree_warn(self):
        # 예전에는 영어 요일이 한국어 요일을 덮었다
        for text in ("2025-11-24(일) Mon 14:00", "2025-11-24(월) Sun 14:00"):
            with self.subTest(text):
                out = self.ok(text, "--from", SEOUL, code=3)
                self.assertEqual(len(out["warnings"]), 1)
                self.assertIn("일요일이 아니라 월요일", out["warnings"][0])
        self.ok("(금) Sat 14:00", "--from", SEOUL, "--now", "2025-11-19 22:00", code=3)
        self.ok("2025-11-24(월) Mon 14:00", "--from", SEOUL)
        self.assertEqual(len(self.ok("2025-11-24(일) Sun 14:00", "--from", SEOUL, code=3)["warnings"]), 1)

    def test_wrong_weekday_in_base_time_warns(self):
        out = self.ok("2025-11-25 12:00", "--from", SEOUL, "--now", "2025-11-24(일) 12:00", code=3)
        self.assertEqual(len(out["warnings"]), 1)
        for text in ("--now", "일요일이 아니라 월요일"):
            self.assertIn(text, out["warnings"][0])
        self.ok("now", "--from", SEOUL, "--now", "2025-11-24 Sun 12:00", code=3)
        self.ok("2025-11-25(월) 12:00", "--from", SEOUL, "--now", "2025-11-24(월) 12:00", code=3)
        self.ok("2025-11-25 12:00", "--from", SEOUL, "--now", "2025-11-24(월) 12:00")

    def test_leftover_text_is_an_error(self):
        # 예전에는 조용히 버려서 다른 시각으로 계산했다
        for text in ("2025-11-24 14:00 PST", "2025-11-24T14:00+09:00", "다음 주 금요일 10:00", "14:00:30",
                     "2025-11-24 10:00~11:00", "2025-11-24 14:00 UTC", "14:00Z", "어제 10:00"):
            with self.subTest(text):
                self.bad(text, "--from", SEOUL, say="읽지 못한 부분" if text != "14:00:30" else "오류")

    def test_impossible_input(self):
        for text in ("언젠가", "2025-02-30 10:00", "13/01 10:00", "24:00", "25:00", "10:75", "오전 13시", "", "11/24 내일 10:00"):
            with self.subTest(text):
                self.bad(text, "--from", SEOUL)
        self.bad("10:00", "--now", "언젠가", say="시각을 못 읽었다")
        self.bad("10:00", "--from", LA, "--now", "2025-03-09 02:30", say="--now")
        self.bad("9999-12-31 23:59", "--from", LA)

    # 시간대 이름
    def test_unknown_zone_suggests_iana_name(self):
        self.assertIn("Asia/Seoul", self.bad("10:00", "--from", "Seoul"))
        self.assertIn("America/Los_Angeles", self.bad("10:00", "--to", "los angeles"))
        self.bad("10:00", "--from", "화성", say="모르는 시간대")
        self.bad("10:00", "--from", "../etc/passwd", say="모르는 시간대")

    def test_abbreviations_are_refused(self):
        for name in ("EST", "MST", "KST", "CET", "PST8PDT"):
            self.bad("2025-07-15 10:00", "--from", name, say="약자는 받지 않는다")

    def test_no_built_in_aliases(self):
        for name in ("한국", "서울", "런던"):
            self.bad("10:00", "--from", name)
        out = self.ok("2025-11-24 14:00")
        self.assertEqual([r["zone"] for r in out["results"][0]["rows"]], [PHX])

    def test_places_from_environment(self):
        places = "서울=Asia/Seoul, 런던 = europe/london"
        out = self.ok("2025-11-24 14:00", "--from", "서울", places=places)
        self.assertEqual([r["place"] for r in out["results"][0]["rows"]], ["서울", "여기(이 컴퓨터)", "런던"])
        out = self.ok("2025-11-24 14:00", "--from", SEOUL, "--to", "UTC", places=places)
        self.assertEqual([r["place"] for r in out["results"][0]["rows"]], ["서울", "UTC"])

    def test_broken_places(self):
        for text in ("서울", "=Asia/Seoul", "여기=Asia/Seoul"):
            self.bad("10:00", places=text, say="WHEN_PLACES")
        self.bad("10:00", places="서울=Asia/Soul", say="모르는 시간대")
        self.ok("2025-11-24 10:00", places="")

    def test_local_zone_from_tz(self):
        # 예전에는 '/'가 없는 TZ(UTC)를 무시했다
        for tz in ("UTC", ":Asia/Seoul", "Asia/Seoul"):
            out = self.ok("2025-11-24 10:00", tz=tz)
            self.assertEqual(out["source"], tz.lstrip(":"))

    def test_unknown_local_zone_is_an_error_not_utc(self):
        self.bad("2025-11-24 10:00", tz="KST-9", say="알 수 없다")
        self.ok("2025-11-24 10:00", "--from", SEOUL, "--to", "UTC", tz="KST-9")

    # 문서
    def test_skill_commands_run_from_any_folder(self):
        scripts = os.path.dirname(SCRIPT)
        with open(os.path.join(os.path.dirname(scripts), "SKILL.md"), encoding="utf-8") as f:
            text = f.read()
        self.assertIn("`S`는 이 스킬 폴더의 `scripts`", text)
        commands = [x.strip() for x in text.splitlines() if x.strip().startswith("python3 -I ")]
        self.assertGreaterEqual(len(commands), 3)
        for c in commands:
            with self.subTest(c):
                args = [a.replace("S/", scripts + "/", 1) if a.startswith("S/") else a for a in shlex.split(c, comments=True)]
                r = subprocess.run([sys.executable, *args[1:]], capture_output=True, text=True, encoding="utf-8",
                                   cwd="/", env={"PATH": "/usr/bin:/bin", "TZ": PHX})
                self.assertEqual(r.returncode, 0, r.stderr)

    # 화면
    def test_text_output(self):
        r = call("2025-03-09 12:00", "--from", LA, "--to", SEOUL, "--now", "2025-03-09 11:00", as_json=False)
        self.assertEqual(r.stdout.splitlines(), [
            "입력: 2025-03-09 12:00 (America/Los_Angeles 기준)",
            "  America/Los_Angeles: 2025-03-09(일) 12:00 (UTC-7, 이날 시차가 바뀜: UTC-8 → UTC-7)",
            "  Asia/Seoul: 2025-03-10(월) 04:00 (UTC+9, 다음 날)",
            "  지금부터 1시간 0분 뒤"])
        r = call("2025-11-02(월) 01:30", "--from", LA, as_json=False)
        self.assertEqual(r.returncode, 3)
        self.assertIn("[2번째로 오는 경우]", r.stdout)
        self.assertEqual(r.stdout.count("경고:"), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)

#!/usr/bin/env python3
"""Claude Code 세션 기록(JSONL)에서 토큰을 세고 API 정가로 환산한다.

  python3 -I analyze_sessions.py --repo . --out-dir ./token-report

결과: <out-dir>/token-analysis.json (권한 0600). 대화 내용과 파일 경로는 결과에 넣지 않는다.
가격은 references/pricing.json 하나에서만 읽는다. 가격을 모르는 응답은 금액을 만들지 않고 토큰만 센다.
"""
import argparse
import datetime
import functools
import json
import os
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path, PurePath

PRICING_FILE = Path(__file__).resolve().parent.parent / "references" / "pricing.json"
STALE_DAYS = 90
KINDS = ("input", "cache_write_5m", "cache_write_1h", "cache_read", "output")
MAX_DIR_NAME = 200  # 더 긴 이름은 Claude Code가 200자에서 자르고 해시를 붙인다


# ---------- 가격 ----------

def load_pricing(path=PRICING_FILE):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    datetime.date.fromisoformat(data["checked_on"])
    for model, rates in data["models"].items():
        for table in filter(None, (rates, (rates or {}).get("long_prompt"))):
            for kind in KINDS:
                value = table.get(kind)
                if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0):
                    raise ValueError(f"{model}.{kind}: 숫자나 null이어야 한다")
    return data


def price_age_days(pricing, today):
    return (today - datetime.date.fromisoformat(pricing["checked_on"])).days


def base_model(model):
    return re.sub(r"-\d{8}$", "", model)


def price_response(resp, pricing):
    """종류별 금액 dict. 가격을 모르면 None(추정하지 않는다)."""
    rates = pricing["models"].get(base_model(resp["model"]))
    if not rates:
        return None
    tokens = resp["tokens"]
    long_prompt = rates.get("long_prompt")
    if long_prompt and prompt_tokens(tokens) > long_prompt["over_tokens"]:
        rates = {**rates, **long_prompt}
    if any(rates.get(kind) is None for kind in KINDS):
        return None
    multiplier = 1
    if resp["fast"]:
        if not rates.get("fast_multiplier"):
            return None
        multiplier *= rates["fast_multiplier"]
    if resp["geo_us"]:
        multiplier *= pricing["modifiers"]["inference_geo_us"]
    cost = {kind: tokens[kind] * rates[kind] * multiplier / 1e6 for kind in KINDS}
    cost["premium_1h"] = tokens["cache_write_1h"] * (rates["cache_write_1h"] - rates["cache_write_5m"]) * multiplier / 1e6
    return cost


# ---------- 기록 폴더 찾기 ----------

def encode_path(path):
    """Claude Code 규칙: 영숫자(ASCII)가 아닌 글자를 모두 '-'로 바꾼다."""
    return re.sub(r"[^a-zA-Z0-9]", "-", path)


def candidate_dir_names(repo):
    """실제 경로(NFC)를 먼저, 심볼릭 링크 경로와 정규화가 다른 이름을 그다음에 본다."""
    raw = os.path.abspath(os.path.expanduser(repo))
    names = []
    for path in (os.path.realpath(raw), raw):
        for form in ("NFC", "NFD"):
            name = encode_path(unicodedata.normalize(form, path))
            if name not in names:
                names.append(name)
    return names


def find_sessions_dir(repo, projects_root):
    for name in candidate_dir_names(repo):
        if len(name) <= MAX_DIR_NAME:
            if (projects_root / name).is_dir():
                return projects_root / name
            continue
        hits = sorted(p for p in projects_root.glob(name[:MAX_DIR_NAME] + "-*") if p.is_dir())
        if len(hits) == 1:
            return hits[0]
        if hits:
            raise SystemExit("[error] 경로가 길어 기록 폴더 후보가 여럿이다. --sessions-dir로 골라 달라:\n"
                             + "\n".join(f"  {p}" for p in hits))
    return None


def owner_finder(repo):
    """cwd → 'ours'(이 프로젝트와 그 아래) · 'other'(기록 폴더 이름만 같은 다른 프로젝트) · None(모름)."""
    raw = os.path.abspath(os.path.expanduser(repo))
    roots = {unicodedata.normalize("NFC", p) for p in (raw, os.path.realpath(raw))}
    names = set(candidate_dir_names(repo))

    def is_repo(path):
        if path in roots:
            return True
        try:
            return os.path.samefile(path, raw)  # 심볼릭 링크, 대소문자만 다른 경로
        except OSError:
            return False

    @functools.lru_cache(maxsize=None)
    def owner(cwd):
        for path in (cwd, *map(str, PurePath(cwd).parents)):
            path = unicodedata.normalize("NFC", path)
            if is_repo(path):
                return "ours"
            if encode_path(path) in names:
                return "other"
        return None

    return lambda cwd: owner(cwd) if isinstance(cwd, str) and os.path.isabs(cwd) else None


def session_files(sessions_dir):
    """(세션 id, 파일). 하위 에이전트 기록은 부모 세션에 넣는다."""
    files = [(p.stem, p) for p in sessions_dir.glob("*.jsonl")]
    files += [(p.relative_to(sessions_dir).parts[0], p) for p in sessions_dir.glob("*/subagents/**/*.jsonl")]
    return sorted(files, key=lambda item: (item[0], str(item[1])))


# ---------- 읽기 ----------

def count(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else 0


def prompt_tokens(tokens):
    return sum(tokens[kind] for kind in KINDS if kind != "output")


def read_usage(usage):
    """(종류별 토큰, TTL 표시가 없어 5분으로 본 캐시 쓰기 토큰)."""
    detail = usage.get("cache_creation")
    detail = detail if isinstance(detail, dict) else {}
    w5 = count(detail.get("ephemeral_5m_input_tokens"))
    w1 = count(detail.get("ephemeral_1h_input_tokens"))
    unknown = max(0, count(usage.get("cache_creation_input_tokens")) - w5 - w1)
    return {
        "input": count(usage.get("input_tokens")),
        "cache_write_5m": w5 + unknown,
        "cache_write_1h": w1,
        "cache_read": count(usage.get("cache_read_input_tokens")),
        "output": count(usage.get("output_tokens")),
    }, unknown


def read_sessions(files, owner_of=None):
    """응답과 세션별 도구 기록을 모은다. 같은 응답(메시지 id + requestId)은 한 번만 센다.

    owner_of를 주면 이 프로젝트의 기록만 모으고, 나머지는 notes에 건수와 토큰만 남긴다.
    귀속은 가장 최근에 알아낸 cwd를 따른다. 하위 에이전트 기록은 부모 기록의 귀속이 하나일 때만 물려받는다.
    """
    responses, sessions, seen_tools = {}, {}, set()
    skipped = {"other": {}, None: {}}
    parent_owners = {}
    notes = Counter()
    for session_id, path in files:
        is_parent = path.name == f"{session_id}.jsonl"  # session_files가 부모를 하위 에이전트보다 먼저 준다
        known = parent_owners.setdefault(session_id, set())
        owner = "ours" if not owner_of else next(iter(known)) if len(known) == 1 else None
        info = sessions.setdefault(session_id, {"tools": Counter(), "reads": Counter(), "first": None, "last": None})
        with open(path, encoding="utf-8", errors="replace") as f:
            for lineno, line in enumerate(f, 1):
                if not line.strip():
                    continue
                try:
                    rec = json.loads(line)
                except (ValueError, RecursionError):
                    notes["broken_lines"] += 1
                    continue
                if not isinstance(rec, dict):
                    continue
                msg = rec.get("message")
                answer = rec.get("type") == "assistant" and isinstance(msg, dict)
                if owner_of:
                    owner = owner_of(rec.get("cwd")) or owner
                    if owner and is_parent:
                        known.add(owner)
                if owner != "ours":
                    if answer:
                        add_response(rec, msg, session_id, (str(path), lineno), skipped[owner], Counter())
                    continue
                ts = rec.get("timestamp")
                if isinstance(ts, str) and re.match(r"\d{4}-\d\d-\d\d", ts):
                    info["first"] = min(filter(None, (info["first"], ts)))
                    info["last"] = max(filter(None, (info["last"], ts)))
                if not answer:
                    continue
                for block in msg.get("content") if isinstance(msg.get("content"), list) else []:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        add_tool(block, info, seen_tools)
                add_response(rec, msg, session_id, (str(path), lineno), responses, notes)
    for name, owner in (("other_project", "other"), ("unclear_project", None)):
        left = [r for key, r in skipped[owner].items() if key not in responses]
        notes[f"{name}_responses"] = len(left)
        notes[f"{name}_tokens"] = sum(sum(r["tokens"].values()) for r in left)
    return list(responses.values()), sessions, notes


def add_tool(block, info, seen_tools):
    tool_id = block.get("id")
    if tool_id:
        if tool_id in seen_tools:
            return
        seen_tools.add(tool_id)
    info["tools"][str(block.get("name", "unknown"))] += 1
    target = block.get("input")
    if block.get("name") == "Read" and isinstance(target, dict) and target.get("file_path"):
        info["reads"][str(target["file_path"])] += 1


def add_response(rec, msg, session_id, position, responses, notes):
    usage, model = msg.get("usage"), msg.get("model")
    if not isinstance(usage, dict) or model == "<synthetic>":  # CLI가 만든 알림. API 호출이 아니다.
        return
    tokens, unknown_ttl = read_usage(usage)
    if not any(tokens.values()):
        return
    if msg.get("id"):
        key = (msg["id"], rec.get("requestId") or "")
    else:
        key = position
        notes["lines_without_id"] += 1
    resp = {
        "session": session_id, "model": model if isinstance(model, str) and model else "(모델 표시 없음)",
        "tokens": tokens, "unknown_ttl": unknown_ttl,
        "fast": usage.get("speed") == "fast", "geo_us": usage.get("inference_geo") == "us",
    }
    old = responses.get(key)
    if old:
        notes["duplicate_lines"] += 1
        # 스트리밍 중간 줄은 출력이 덜 적혀 있을 수 있어 출력이 큰 줄을 남긴다.
        if tokens["output"] >= old["tokens"]["output"]:
            responses[key] = {**resp, "session": old["session"]}
    else:
        responses[key] = resp


# ---------- 집계 ----------

def summarize(responses, pricing):
    """응답 묶음 하나의 토큰·금액. 값을 아는 응답이 없으면 cost_usd는 None."""
    out = {kind: sum(r["tokens"][kind] for r in responses) for kind in KINDS}
    out["total_input"] = prompt_tokens(out)
    out["cache_hit_ratio"] = out["cache_read"] / out["total_input"] if out["total_input"] else 0.0
    priced = [(r, c) for r in responses if (c := price_response(r, pricing)) is not None]
    out["responses"] = len(responses)
    out["unpriced_responses"] = len(responses) - len(priced)
    out["unpriced_tokens"] = (sum(sum(r["tokens"].values()) for r in responses)
                              - sum(sum(r["tokens"].values()) for r, _ in priced))
    out["cost_by_kind"] = {kind: sum(c[kind] for _, c in priced) for kind in KINDS} if priced else None
    out["cost_usd"] = sum(out["cost_by_kind"].values()) if priced else None
    out["premium_1h_usd"] = sum(c["premium_1h"] for _, c in priced) if priced else None
    return out


def score_session(s):
    """4개 지표 0~100점. 이 스킬이 정한 어림 기준이며 공식 기준이 아니다."""
    cache = min(100, s["cache_hit_ratio"] / 0.85 * 100)

    density_ratio = s["output"] / s["total_input"] if s["total_input"] else 0
    if density_ratio < 0.005:
        density = density_ratio / 0.005 * 60
    elif density_ratio < 0.02:
        density = 60 + (density_ratio - 0.005) / 0.015 * 40
    elif density_ratio < 0.05:
        density = 100 - (density_ratio - 0.02) / 0.03 * 20
    else:
        density = max(40, 80 - (density_ratio - 0.05) * 200)

    redundancy = max(0, 100 - s["redundant_reads"] / (s["total_reads"] or 1) * 200)

    per_1k = s["tool_calls"] / max(1, s["output"] / 1000)
    if per_1k < 2:
        tool = 70 + per_1k * 15
    elif per_1k < 10:
        tool = 100 - (per_1k - 2) * 2
    elif per_1k < 20:
        tool = 84 - (per_1k - 10) * 4
    else:
        tool = max(0, 44 - (per_1k - 20) * 2)

    composite = cache * 0.4 + density * 0.2 + redundancy * 0.2 + tool * 0.2
    return {"cache": round(cache, 1), "density": round(density, 1), "redundancy": round(redundancy, 1),
            "tool": round(tool, 1), "composite": round(composite, 1), "grade": grade_of(composite)}


def grade_of(score):
    for threshold, grade in ((90, "A+"), (85, "A"), (80, "A-"), (75, "B+"), (70, "B"),
                             (65, "B-"), (60, "C+"), (55, "C"), (50, "C-"), (40, "D")):
        if score >= threshold:
            return grade
    return "F"


def analyze(files, pricing, label, today, owner_of=None):
    responses, sessions, notes = read_sessions(files, owner_of)
    by_session, by_model = {}, {}
    for r in responses:
        by_session.setdefault(r["session"], []).append(r)
        by_model.setdefault(base_model(r["model"]), []).append(r)

    rows = []
    for session_id, items in by_session.items():
        info = sessions[session_id]
        row = summarize(items, pricing)
        row["session_id"] = session_id
        row["tool_calls"] = sum(info["tools"].values())
        row["total_reads"] = sum(info["reads"].values())
        row["redundant_reads"] = sum(n - 1 for n in info["reads"].values())
        row["scores"] = score_session(row)
        rows.append(row)
    rows.sort(key=lambda r: (-(r["cost_usd"] or 0), -(r["total_input"] + r["output"]), r["session_id"]))

    models = [{"model": m, **summarize(items, pricing)} for m, items in by_model.items()]
    models.sort(key=lambda m: (-(m["cost_usd"] or 0), -(m["total_input"] + m["output"]), m["model"]))

    stamps = [sessions[s][edge] for s in by_session for edge in ("first", "last") if sessions[s][edge]]
    age = price_age_days(pricing, today)
    return {
        "label": label,
        "generated_on": today.isoformat(),
        "period": {"first": min(stamps)[:10], "last": max(stamps)[:10]} if stamps else None,
        "pricing": {"checked_on": pricing["checked_on"], "source_url": pricing["source_url"],
                    "age_days": age, "stale": age > STALE_DAYS},
        "notes": {
            "duplicate_lines": notes["duplicate_lines"],
            "lines_without_id": notes["lines_without_id"],
            "broken_lines": notes["broken_lines"],
            "other_project_responses": notes["other_project_responses"],
            "other_project_tokens": notes["other_project_tokens"],
            "unclear_project_responses": notes["unclear_project_responses"],
            "unclear_project_tokens": notes["unclear_project_tokens"],
            "cache_write_ttl_unknown_tokens": sum(r["unknown_ttl"] for r in responses),
        },
        "totals": {**summarize(responses, pricing), "sessions": len(rows),
                   "tool_calls": sum(r["tool_calls"] for r in rows),
                   "redundant_reads": sum(r["redundant_reads"] for r in rows)},
        "models": models,
        "sessions": rows,
    }


# ---------- 쓰기 ----------

def prepare_out_dir(out_dir):
    """새로 만드는 폴더만 0700으로 만들고 git에서 빼 둔다. 이미 있는 폴더는 건드리지 않는다."""
    if not out_dir.exists():
        out_dir.mkdir(parents=True, mode=0o700)
        (out_dir / ".gitignore").write_text("*\n", encoding="utf-8")


def write_private(path, text):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        os.fchmod(f.fileno(), 0o600)
        f.write(text)


def main():
    ap = argparse.ArgumentParser(description="Claude Code 세션 기록에서 토큰과 API 정가 환산액을 집계한다.")
    ap.add_argument("--repo", default=".", help="프로젝트 경로(기본: 현재 폴더)")
    ap.add_argument("--sessions-dir", help="기록 폴더를 직접 지정")
    ap.add_argument("--out-dir", default="./token-report", help="결과 폴더(기본: ./token-report)")
    ap.add_argument("--label", help="보고서 제목에 쓸 이름(기본: 프로젝트 폴더 이름)")
    args = ap.parse_args()

    try:
        pricing = load_pricing()
    except (OSError, ValueError, KeyError) as e:
        raise SystemExit(f"[error] 가격표를 읽지 못했다({PRICING_FILE.name}): {e}")

    if args.sessions_dir:
        sessions_dir = Path(args.sessions_dir).expanduser()
    else:
        sessions_dir = find_sessions_dir(args.repo, Path("~/.claude/projects").expanduser())
    if not sessions_dir or not sessions_dir.is_dir():
        print("[error] 분석할 세션 기록 폴더가 없다. 이 경로에서 Claude Code를 쓴 적이 없거나 기록이 지워졌다.", file=sys.stderr)
        sys.exit(2)

    label = args.label or ("Claude Code 세션" if args.sessions_dir else Path(os.path.abspath(args.repo)).name)
    today = datetime.date.today()
    owner_of = None if args.sessions_dir else owner_finder(args.repo)
    result = analyze(session_files(sessions_dir), pricing, label, today, owner_of)
    n = result["notes"]
    for key, why in (("other_project", "기록 폴더 이름이 같은 다른 프로젝트의"), ("unclear_project", "cwd로 어느 프로젝트인지 알 수 없는")):
        if n[f"{key}_responses"]:
            print(f"[warn] {why} 응답 {n[f'{key}_responses']}건 / {n[f'{key}_tokens']:,}토큰은 합계에 넣지 않았다.", file=sys.stderr)
    if not result["sessions"]:
        print("[error] 사용량이 적힌 세션이 없다.", file=sys.stderr)
        sys.exit(2)

    out_dir = Path(args.out_dir).expanduser()
    prepare_out_dir(out_dir)
    out = out_dir / "token-analysis.json"
    write_private(out, json.dumps(result, ensure_ascii=False, indent=2))

    t = result["totals"]
    cost = "가격 모름" if t["cost_usd"] is None else f"${t['cost_usd']:.2f} (API 정가 환산)"
    print(f"[ok] {out}")
    print(f"     세션 {t['sessions']}개, 응답 {t['responses']}건, {cost}, 캐시 적중 {t['cache_hit_ratio'] * 100:.1f}%")
    print(f"     겹쳐 적힌 줄 {n['duplicate_lines']}개를 빼고 셌다. 읽지 못한 줄 {n['broken_lines']}개.")
    if t["unpriced_responses"]:
        unknown = ", ".join(f"{m['model']!r} {m['unpriced_responses']}건" for m in result["models"] if m["unpriced_responses"])
        print(f"[warn] 가격을 몰라 금액에서 뺀 응답 {t['unpriced_responses']}건 / {t['unpriced_tokens']:,}토큰: {unknown}", file=sys.stderr)
    if result["pricing"]["stale"]:
        print(f"[warn] 가격표를 확인한 지 {result['pricing']['age_days']}일 지났다({pricing['checked_on']}). "
              f"{pricing['source_url']} 에서 다시 확인해야 한다.", file=sys.stderr)


if __name__ == "__main__":
    main()

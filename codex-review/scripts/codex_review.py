#!/usr/bin/env python3
"""다른 회사 모델(Codex CLI)에게 리뷰를 맡기는 codex exec 호출을 한 가지 모양으로 고정한다.

사용:
  codex_review.py --prompt <프롬프트.md> [--cd <폴더>] [--out <결과.md>] [--dry-run]
                  [--model <이름>] [--effort <단계>] [--sandbox read-only|workspace-write]
                  [--add-dir <폴더>]... [--web] [--timeout-min 30]
  codex_review.py --ping [--model <이름>]     # 모델이 응답하는지만 본다(짧은 실제 호출 1회)

고정하는 것: --skip-git-repo-check, 샌드박스 명시(기본 read-only), 프롬프트는 표준 입력('-'),
결과는 -o <결과>, 나머지 출력은 <결과>.log, 제한 시간이 지나면 하위 프로세스까지 멈춤.
지정하지 않은 모델·effort는 넘기지 않는다(Codex 설정의 기본값을 쓴다).

환경 변수:
  CODEX_BIN           codex 실행 파일(기본 codex)
  CODEX_REVIEW_MODEL  --model의 기본값
  CODEX_REVIEW_BLOCK  작업 폴더로 주지 않을 폴더 목록(PATH처럼 ':'로 나눔). 기본은 빈 목록.
                      검사하는 것은 --cd와 --add-dir 인자뿐이다. 읽기 전용 샌드박스는 쓰기를 막는 장치라
                      Codex가 다른 폴더의 파일을 읽는 것은 막지 못한다.
  CODEX_REVIEW_LOG    주면 실행 기록(메타데이터 한 줄 JSON)을 이 파일에 더한다. 기본은 남기지 않는다.
"""
import argparse
import datetime as dt
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time

# Codex 버전에 묶인 값. codex-cli 0.167.2에서 확인(2026-11-24).
# 옛 버전은 tools.web_search=true나 features.web_search_request를 썼다. 값이 바뀌면 여기만 고친다.
WEB_LIVE = 'web_search="live"'
PING = "Reply with exactly: ok"


def inside(path, root):
    """path가 root이거나 그 아래인가. 심볼릭 링크와 대소문자만 다른 이름도 같은 폴더로 본다."""
    path, root = (os.path.realpath(os.path.expanduser(p)) for p in (path, root))
    while True:
        if path == root or (os.path.exists(path) and os.path.exists(root) and os.path.samefile(path, root)):
            return True
        parent = os.path.dirname(path)
        if parent == path:
            return False
        path = parent


def blocked(path):
    """차단 목록과 겹치면 그 항목을 돌려준다. 차단 폴더를 품은 상위 폴더도 겹치는 것으로 본다."""
    for root in os.environ.get("CODEX_REVIEW_BLOCK", "").split(os.pathsep):
        if root.strip() and (inside(path, root.strip()) or inside(root.strip(), path)):
            return root.strip()
    return None


def emit(**rec):
    print(json.dumps(rec, ensure_ascii=False))


def fail(message, code=2):
    emit(exit=code, error=message)
    return code


def stop(proc):
    """codex가 띄운 하위 프로세스까지 멈춘다(npm 설치본은 node 래퍼라 하나만 죽이면 본체가 남을 수 있다)."""
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(proc.pid, sig)
        except (ProcessLookupError, PermissionError):
            pass
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass


def run(cmd, prompt, log, timeout):
    with open(log, "w", encoding="utf-8") as lf, tempfile.TemporaryFile() as stdin:
        stdin.write(prompt.encode("utf-8"))
        stdin.seek(0)
        proc = subprocess.Popen(cmd, stdin=stdin, stdout=lf, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            return proc.wait(timeout=timeout)
        except BaseException as e:  # 제한 시간, Ctrl-C, 종료 신호
            stop(proc)
            if isinstance(e, subprocess.TimeoutExpired):
                return 124
            raise


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--prompt", help="프롬프트 파일")
    ap.add_argument("--out", help="결과 파일(기본: 프롬프트 이름 + .out.md)")
    ap.add_argument("--cd", default=os.getcwd(), help="리뷰할 폴더")
    ap.add_argument("--add-dir", action="append", default=[], help="쓰기를 더 열어 줄 폴더(workspace-write에서만 뜻이 있다)")
    ap.add_argument("--model", default=os.environ.get("CODEX_REVIEW_MODEL") or None)
    ap.add_argument("--effort", help="모델이 지원하는 단계 이름(low, medium, high 등)")
    ap.add_argument("--sandbox", default="read-only", choices=["read-only", "workspace-write"])
    ap.add_argument("--web", action="store_true", help=f"실시간 웹 검색({WEB_LIVE})")
    ap.add_argument("--timeout-min", type=float, default=30)
    ap.add_argument("--ping", action="store_true", help="모델이 응답하는지만 본다")
    ap.add_argument("--dry-run", action="store_true", help="부르지 않고 무엇을 어디에 줄지만 보여 준다")
    a = ap.parse_args(argv)

    effort = a.effort or ("low" if a.ping else None)
    if effort and not re.fullmatch(r"[a-z]+", effort):
        ap.error("--effort는 영문 소문자 단계 이름이에요")
    if a.ping:
        prompt = PING
        out = a.out or os.path.join(tempfile.gettempdir(), f"codex-ping-{os.getpid()}.md")
    else:
        if not a.prompt:
            ap.error("--prompt가 필요해요(또는 --ping)")
        if not os.path.isfile(a.prompt):
            ap.error(f"프롬프트 파일이 없어요: {a.prompt}")
        with open(a.prompt, encoding="utf-8") as fh:
            prompt = fh.read()
        if not prompt.strip():
            ap.error("프롬프트 파일이 비어 있어요")
        out = a.out or os.path.splitext(a.prompt)[0] + ".out.md"
    out, cwd = os.path.abspath(out), os.path.abspath(os.path.expanduser(a.cd))
    add_dirs = [os.path.abspath(os.path.expanduser(d)) for d in a.add_dir]

    for path in [cwd] + add_dirs:
        hit = blocked(path)
        if hit:
            return fail(f"막힘: {path} (CODEX_REVIEW_BLOCK의 {hit}와 겹쳐요)")
    if not os.path.isdir(cwd):
        return fail(f"작업 폴더가 없어요: {cwd}")
    if not os.path.isdir(os.path.dirname(out)):   # 호출이 끝난 뒤에 결과를 잃지 않게 먼저 본다
        return fail(f"결과를 둘 폴더가 없어요: {os.path.dirname(out)}")
    if a.prompt and os.path.realpath(a.prompt) == os.path.realpath(out):
        return fail("결과 파일이 프롬프트 파일과 같아요")
    codex = os.environ.get("CODEX_BIN", "codex")
    if not shutil.which(codex):
        return fail(f"codex 실행 파일을 찾지 못했어요: {codex}", 127)

    cmd = [codex, "exec", "--skip-git-repo-check", "-s", a.sandbox, "-C", cwd, "-o", out]
    if a.model:
        cmd += ["-m", a.model]
    if effort:
        cmd += ["-c", f'model_reasoning_effort="{effort}"']
    if a.web:
        cmd += ["-c", WEB_LIVE]
    for d in add_dirs:
        cmd += ["--add-dir", d]
    cmd.append("-")
    if a.dry_run:
        emit(exit=0, dry_run=True, cmd=cmd, prompt_bytes=len(prompt.encode("utf-8")), out=out,
             note="프롬프트와 Codex가 읽은 파일 내용이 모델 제공사로 나가요. 읽는 범위는 작업 폴더로 제한되지 않아요")
        return 0

    log = out + ".log"
    if os.path.exists(out):   # 지난 결과를 새 결과로 착각하지 않게 옮겨 둔다
        os.replace(out, out + ".prev")
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))   # 종료 신호에도 run()의 정리를 거친다
    t0 = time.time()
    code = run(cmd, prompt, log, a.timeout_min * 60)
    size = os.path.getsize(out) if os.path.exists(out) else 0
    rec = dict(exit=code, seconds=round(time.time() - t0, 1), out=out, log=log, out_bytes=size,
               model=a.model, effort=effort, sandbox=a.sandbox)
    if a.ping:
        reply = ""
        if size:
            with open(out, encoding="utf-8", errors="replace") as fh:
                reply = fh.read().strip().lower()
        rec["ping_ok"] = code == 0 and reply.startswith("ok")
    if code == 124:
        rec["error"] = f"{a.timeout_min:g}분 안에 끝나지 않아 멈췄어요"
    elif code == 0 and size == 0:
        rec["error"] = "결과 파일이 비어 있어요. 로그를 보세요"
    if os.environ.get("CODEX_REVIEW_LOG"):
        path = os.path.abspath(os.path.expanduser(os.environ["CODEX_REVIEW_LOG"]))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        keep = {k: rec[k] for k in ("exit", "seconds", "out_bytes", "model", "effort", "sandbox")}
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(dict(ts=dt.datetime.now().astimezone().isoformat(timespec="seconds"), cwd=cwd,
                                     ping=a.ping, **keep), ensure_ascii=False) + "\n")
    emit(**rec)
    return code if code else (1 if rec.get("error") or (a.ping and not rec["ping_ok"]) else 0)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

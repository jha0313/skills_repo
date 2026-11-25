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
웹 검색은 늘 값을 넘긴다(--web이면 live, 아니면 disabled). 사용자 설정의 검색 모드를 물려받지 않는다.

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
# disabled는 검색 도구를 없앤다. 안 넘기면 Codex 설정(기본 cached)이나 전체 접근 샌드박스의 live를 물려받는다.
WEB_KEY, WEB_ON, WEB_OFF = "web_search", "live", "disabled"
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


def same(a, b):
    """두 경로가 같은 파일인가. 심볼릭 링크, 하드 링크, 대소문자만 다른 이름도 같은 파일로 본다."""
    return os.path.realpath(a) == os.path.realpath(b) or (
        os.path.exists(a) and os.path.exists(b) and os.path.samefile(a, b))


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


def make_private(path):
    """빈 0600 파일로 만든다. 이미 있던 파일도 쓰기 전에 권한을 좁힌다."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT, 0o600)
    try:
        os.fchmod(fd, 0o600)
        os.ftruncate(fd, 0)
    finally:
        os.close(fd)


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
    ap.add_argument("--web", action="store_true", help=f"실시간 웹 검색({WEB_KEY}={WEB_ON}). 없으면 {WEB_OFF}")
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
    log, prev = out + ".log", out + ".prev"
    run_log = os.environ.get("CODEX_REVIEW_LOG")
    run_log = os.path.abspath(os.path.expanduser(run_log)) if run_log else None
    files = [("프롬프트", a.prompt), ("결과", out), ("로그", log), ("지난 결과", prev), ("실행 기록", run_log)]
    files = [(name, path) for name, path in files if path]
    for i, (name, path) in enumerate(files):   # 프롬프트나 다른 결과를 덮지 않게 열기 전에 본다
        if os.path.isdir(path):
            return fail(f"{name} 파일 자리가 폴더예요: {path}")
        for other, path2 in files[:i]:
            if same(path, path2):
                return fail(f"{other}와 {name}이(가) 같은 파일이에요: {path}")
    codex = os.environ.get("CODEX_BIN", "codex")
    if not shutil.which(codex):
        return fail(f"codex 실행 파일을 찾지 못했어요: {codex}", 127)

    cmd = [codex, "exec", "--skip-git-repo-check", "-s", a.sandbox, "-C", cwd, "-o", out]
    if a.model:
        cmd += ["-m", a.model]
    if effort:
        cmd += ["-c", f'model_reasoning_effort="{effort}"']
    web = WEB_ON if a.web else WEB_OFF
    cmd += ["-c", f'{WEB_KEY}="{web}"']
    for d in add_dirs:
        cmd += ["--add-dir", d]
    cmd.append("-")
    if a.dry_run:
        emit(exit=0, dry_run=True, cmd=cmd, prompt_bytes=len(prompt.encode("utf-8")), out=out,
             web_search=web, web_search_inherited=False,
             note="프롬프트와 Codex가 읽은 파일 내용이 모델 제공사로 나가요. 읽는 범위는 작업 폴더로 제한되지 않아요")
        return 0

    try:
        if os.path.exists(out) and os.path.getsize(out):   # 지난 결과를 새 결과로 착각하지 않게 옮겨 둔다
            os.replace(out, prev)
        if os.path.exists(prev):   # 옛 실행이 남긴 백업도 좁힌다
            os.chmod(prev, 0o600)
        for path in (out, log):   # 프롬프트와 리뷰 내용이 들어간다. codex가 쓰기 전에 나만 읽게 만든다
            make_private(path)
    except OSError as e:
        return fail(f"결과·로그 파일을 나만 읽게 만들지 못했어요: {e}")
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))   # 종료 신호에도 run()의 정리를 거친다
    t0 = time.time()
    size = 0
    try:
        code = run(cmd, prompt, log, a.timeout_min * 60)
    finally:
        if os.path.exists(out):
            size = os.path.getsize(out)
            if size:
                os.chmod(out, 0o600)   # codex가 새 파일로 바꿔치기했을 때
            else:
                os.unlink(out)   # 미리 만든 빈 파일을 결과로 남기지 않는다
    rec = dict(exit=code, seconds=round(time.time() - t0, 1), out=out, log=log, out_bytes=size,
               model=a.model, effort=effort, sandbox=a.sandbox)
    if a.ping:
        reply = ""
        if size:
            with open(out, encoding="utf-8", errors="replace") as fh:
                reply = fh.read().strip()
        rec["ping_ok"] = code == 0 and reply == "ok"
    if code == 124:
        rec["error"] = f"{a.timeout_min:g}분 안에 끝나지 않아 멈췄어요"
    elif code == 0 and size == 0:
        rec["error"] = "결과 파일이 비어 있어요. 로그를 보세요"
    elif code == 0 and a.ping and not rec["ping_ok"]:
        rec["error"] = "ping 응답이 ok가 아니에요. 결과 파일을 보세요"
    if code == 0 and rec.get("error"):
        rec["exit"] = 1   # codex가 0으로 끝났어도 쓸 결과가 없다. 기록에도 이 값을 남긴다
    if run_log:
        os.makedirs(os.path.dirname(run_log), exist_ok=True)
        keep = {k: rec[k] for k in ("exit", "seconds", "out_bytes", "model", "effort", "sandbox")}
        with open(run_log, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(dict(ts=dt.datetime.now().astimezone().isoformat(timespec="seconds"), cwd=cwd,
                                     ping=a.ping, **keep), ensure_ascii=False) + "\n")
    emit(**rec)
    return rec["exit"]


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

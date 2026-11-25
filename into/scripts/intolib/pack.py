# -*- coding: utf-8 -*-
"""원문 꾸러미: 에이전트가 다시 세지 않게 하는 결정적 사실. 원문을 실행하거나 import하지 않는다."""
import hashlib
import json
import os
import re
import subprocess

from . import UserError
from . import text as T
from .cite import DEF, POST_HEAD, POST_LINE, diff_line, list_files, parse_diff
from .route import CODE_EXT, CONF_EXT, MANIFESTS

SMALL, LARGE = 1500, 20000                  # 글자: 작음 < 1,500 ≤ 보통 ≤ 20,000 < 큼
PR_SMALL_LINES, PR_SMALL_FILES = 50, 3       # 작은 PR: 추가+삭제 50줄 미만이고 소스 파일 3개 이하(테스트·생성물·lock 빼고)
PR_LARGE_LINES, PR_LARGE_FILES = 1000, 15
COND_MAX = 40
READ_MAX = 5000000                           # 글자: 이보다 긴 입력은 앞만 읽는다

LOCKS = ('Cargo.lock', 'package-lock.json', 'pnpm-lock.yaml', 'yarn.lock', 'uv.lock', 'poetry.lock', 'go.sum', 'MODULE.bazel.lock', 'Gemfile.lock', 'composer.lock', 'flake.lock', 'bun.lockb', 'bun.lock', 'Pipfile.lock')
TEST_RE = re.compile(r'(?:^|/)(?:tests?|__tests__|spec|specs|testdata|fixtures|e2e|it|snapshots|__snapshots__)(?:/|$)|(?:^|/)test_[^/]+$|[_.\-](?:test|tests|spec)s?\.[A-Za-z]+$|(?:^|/)conftest\.py$', re.I)
GEN_RE = re.compile(r'\.(?:snap|min\.js|min\.css|map|pb\.go|pb\.rs)$|(?:^|/)(?:generated|gen|vendor|third_party|dist|build|node_modules)(?:/|$)|[._]generated\.|_pb2\.py$|\.g\.dart$', re.I)
DOC_EXT = {'.md', '.mdx', '.rst', '.txt', '.adoc'}


def sh(args, timeout=60, cwd=None):
    """(성공, 표준 출력, 오류 한 줄)"""
    try:
        r = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, cwd=cwd, stdin=subprocess.DEVNULL)
    except FileNotFoundError:
        return False, '', '%s 명령이 없다' % args[0]
    except subprocess.TimeoutExpired:
        return False, '', '%s가 %d초 안에 끝나지 않았다' % (args[0], timeout)
    err = (r.stderr.decode('utf-8', 'replace').strip().split('\n') or [''])[0]
    return r.returncode == 0, r.stdout.decode('utf-8', 'replace'), err


def classify(path):
    """source · test · generated · lock · doc"""
    b = os.path.basename(path)
    if b in LOCKS:
        return 'lock'
    if GEN_RE.search(path):
        return 'generated'
    if TEST_RE.search(path):
        return 'test'
    if os.path.splitext(b)[1].lower() in DOC_EXT:
        return 'doc'
    return 'source'


KIND_KO = {'source': '소스', 'test': '테스트', 'generated': '생성물', 'lock': 'lock', 'doc': '문서'}


def visibility(repo):
    """gh가 말한 저장소 공개 여부. 모르면 ''"""
    ok, out, _ = sh(['gh', 'repo', 'view', repo, '--json', 'visibility', '-q', '.visibility'], 15)
    return out.strip().lower() if ok else ''


def unpublished(root):
    """커밋과 다른 로컬 파일(고쳤거나 추적하지 않는 것). 없으면 ''"""
    ok, out, err = sh(['git', '-C', root, 'status', '--porcelain', '-z', '--untracked-files=all', '--', '.'], 60)
    if not ok:
        return 'git 상태를 모른다(%s)' % err
    got = [x[3:] for x in out.split('\0') if len(x) > 3 and x[2] == ' ' and '/into-out/' not in '/' + x[3:]]
    hidden = sh(['git', '-C', root, 'ls-files', '-v', '-z', '--', '.'], 60)[1].split('\0')          # status가 보지 않는 파일(assume-unchanged · skip-worktree)
    got += [x[2:] for x in hidden if (x[:1].islower() or x[:1] == 'S') and os.path.exists(os.path.join(root, x[2:]))]
    if sh(['git', '-C', root, 'check-ignore', '-q', '.'], 20)[0]:
        return 'git이 무시하는 폴더다(.gitignore)'
    if not any(hidden):
        return 'git이 추적하는 파일이 없다'
    return '커밋 안 된 파일 %d개(%s%s)' % (len(got), os.path.basename(got[0].rstrip('/')), ' …' if len(got) > 1 else '') if got else ''


def pushed(root, commit, repo):
    """이 커밋이 원격에 있나: 로컬의 origin 기록, 없으면 gh로 확인"""
    ok, out, _ = sh(['git', '-C', root, 'rev-list', '--max-count=1', commit, '--not', '--remotes=origin'], 20)
    return bool(commit) and (ok and not out.strip() or sh(['gh', 'api', 'repos/%s/commits/%s' % (repo, commit), '--silent'], 15)[0])


def shas(root, files=None):
    """폴더의 파일 → 내용 해시(줄 끝 차이는 무시). start 때의 내용을 남긴다."""
    out = {}
    for f in list_files(root) if files is None else files:
        try:
            with open(os.path.join(root, f), 'rb') as fh:
                out[f] = hashlib.sha1(fh.read(READ_MAX).replace(b'\r\n', b'\n')).hexdigest()[:12]
        except OSError:
            pass
    return out


# ---------- PR ----------
def pr_head(url):
    """지금 PR의 head 커밋. 모르면 ''"""
    ok, out, _ = sh(['gh', 'pr', 'view', url, '--json', 'headRefOid', '-q', '.headRefOid'], 20)
    return out.strip() if ok else ''


def fetch_pr(url):
    """gh로 PR을 읽어 저장 사본과 같은 모양의 글로 만든다 (읽기만)."""
    ok, out, err = sh(['gh', 'pr', 'view', url, '--json', 'title,body,files,commits,additions,deletions,changedFiles,mergeCommit,headRefOid,mergedAt,state,number,url'])
    if not ok:
        raise UserError('gh pr view 실패: %s. PR 본문과 diff를 파일로 저장해 그 경로로 다시 start 한다' % err)
    v = json.loads(out)
    ok, diff, err = sh(['gh', 'pr', 'diff', url, '--color', 'never'])
    note = ''
    if not ok:
        diff, note = '', 'diff를 받지 못했다: %s' % err
    m = re.search(r'(?:github\.com)/([^/]+/[^/]+)/pull', v.get('url') or url)
    repo = m.group(1) if m else ''
    vis = visibility(repo) if repo else ''
    head = ['---', 'type: pr', 'title: "%s"' % (v.get('title') or '').replace('"', "'"), 'source: %s' % v.get('url', url), 'repo: %s' % repo, 'number: %s' % v.get('number'),
            'public: %s' % ('true' if vis == 'public' else 'false' if vis else ''), 'state: %s' % v.get('state'), 'changed_files: %s' % v.get('changedFiles'),
            'additions: %s' % v.get('additions'), 'deletions: %s' % v.get('deletions'), 'head: %s' % (v.get('headRefOid') or ''),
            'merge_commit: %s' % ((v.get('mergeCommit') or {}).get('oid') or '')]
    if note:
        head += ['truncated: true', 'truncated_range: "%s"' % note]
    head += ['---', '# %s' % v.get('title', ''), '', '## PR 본문 (원문)', '', re.sub(r'(?s)<!--.*?-->', '', v.get('body') or '(본문 없음)').strip(), '', '## 커밋', '']
    head += ['- %s %s' % ((c.get('oid') or '')[:12], c.get('messageHeadline') or '') for c in v.get('commits') or []]
    head += ['', '## 변경 파일 목록 (%s개)' % v.get('changedFiles'), '', '| 경로 | + | - |', '|---|---:|---:|']
    head += ['| `%s` | %s | %s |' % (f.get('path'), f.get('additions'), f.get('deletions')) for f in v.get('files') or []]
    return '\n'.join(head) + '\n\n## Diff\n\n```diff\n' + diff.rstrip('\n') + '\n```\n'


def pr_facts(s, meta):
    diff = parse_diff(s)
    listed = {}
    for m in re.finditer(r'(?m)^\|\s*`?([^`|]+?)`?\s*\|\s*\+?(\d+)\s*\|\s*[-−]?(\d+)\s*\|', s):
        listed[m.group(1).strip()] = (int(m.group(2)), int(m.group(3)))
    rows = []
    for p in list(listed) + [x for x in diff if x not in listed]:
        d = diff.get(p)
        a, b = listed.get(p) or (d['add'], d['del'])
        rows.append({'path': p, 'add': a, 'del': b, 'kind': classify(p), 'shown': p in diff,
                     'state': 'new' if d and d['new'] else 'gone' if d and d['gone'] else '',
                     'part': bool(d and p in listed and (d['add'], d['del']) != listed[p])})
    add = int(meta['additions']) if (meta.get('additions') or '').isdigit() else sum(r['add'] for r in rows)
    dele = int(meta['deletions']) if (meta.get('deletions') or '').isdigit() else sum(r['del'] for r in rows)
    total = int(meta['changed_files']) if (meta.get('changed_files') or '').isdigit() else len(rows)
    src = [r for r in rows if r['kind'] in ('source', 'doc')]
    lines = add + dele
    size = '작음' if lines < PR_SMALL_LINES and len(src) <= PR_SMALL_FILES else '큼' if lines > PR_LARGE_LINES or len(src) > PR_LARGE_FILES else '보통'
    return {'files': rows, 'add': add, 'del': dele, 'total': total, 'source_files': len(src), 'shown': len(diff),
            'small': size == '작음', 'truncated': (meta.get('truncated') or '').lower() == 'true' or len(diff) < total,
            'truncated_range': meta.get('truncated_range', '')}, size, '추가+삭제 %s줄 · 소스 파일 %d개(테스트·생성물·lock 빼고)' % ('{:,}'.format(lines), len(src)), diff


def numbered_diff(diff, kinds=('source', 'doc', 'test')):
    """PR 뒤 파일 줄 번호를 단 diff. 지운 줄은 -n (PR 전 줄)."""
    out = []
    order = {'source': 0, 'doc': 1, 'test': 2}
    for p, d in sorted(diff.items(), key=lambda kv: order.get(classify(kv[0]), 3)):
        k = classify(p)
        out.append('### %s  (+%d −%d, %s%s)' % (p, d['add'], d['del'], KIND_KO[k], ', 새 파일' if d['new'] else ', 지운 파일' if d['gone'] else ''))
        if k not in kinds:
            out.append('(본문 생략: %s)' % KIND_KO[k])
            continue
        for h in d['hunks']:
            out.append('@@ %s' % h['head'] if h['head'] else '@@')
            for sg, old, new, t in h['rows']:
                out.append('%6s %s%s' % (new if new else '-%d' % old, sg, t))
            if h['cut']:
                out.append('       … (hunk가 여기서 잘렸다)')
    return '\n'.join(out)


# ---------- 저장소 ----------
def count_file(path):
    """(줄 수, 바이트) — 이진 파일이면 (None, 바이트)"""
    try:
        size = os.path.getsize(path)
        if size > 5000000:
            return None, size
        with open(path, 'rb') as f:
            b = f.read()
    except OSError:
        return None, 0
    if b'\0' in b[:2048]:
        return None, size
    return b.count(b'\n') + (1 if b and not b.endswith(b'\n') else 0), size


def empty(s):
    """머리말을 뺀 본문이 비었나"""
    return not '\n'.join(s.split('\n')[T.front_matter(s)[1] - 1:]).strip()


def text_in(s, name):
    """입력 글 → (글, 잘렸으면 읽은 글자 수). 비었거나 이진이면 멈춘다."""
    if empty(s):
        raise UserError('%s: 입력이 비었다. 본문이 든 글을 준다' % name)
    if '\0' in s:
        raise UserError('%s: 이진 파일이다. 글(UTF-8)로 바꿔 저장하고 그 경로를 준다' % name)
    bad = s.count('\ufffd')
    if bad * 50 > len(s):
        raise UserError('%s: UTF-8 글이 아니다(읽지 못한 글자 %d%%). UTF-8로 바꿔 저장하고 그 경로를 준다' % (name, round(bad * 100.0 / len(s))))
    return s[:READ_MAX], READ_MAX if len(s) > READ_MAX else 0


def stamp(src):
    """원문이 바뀌었는지 보는 해시"""
    s = src['text']
    return hashlib.sha1(re.sub(r'\r\n?', '\n', s).encode('utf-8', 'replace')).hexdigest() if s else ''


def read(path, limit=400000):
    try:
        with open(path, encoding='utf-8', errors='replace') as f:
            return f.read(limit)
    except OSError:
        return ''


def toml_list(s, section, key):
    m = re.search(r'(?ms)^\[%s\]\s*$(.*?)(?=^\[|\Z)' % re.escape(section), s)
    if not m:
        return []
    k = re.search(r'(?ms)^\s*%s\s*=\s*\[(.*?)\]' % key, m.group(1))
    return re.findall(r'["\']([^"\']+)["\']', re.sub(r'#[^\n]*', '', k.group(1))) if k else []


def repo_facts(root, zone='', fetch=True):
    files = list_files(root)
    if not files:
        raise UserError('폴더가 비었다: %s' % os.path.basename(root))
    ok, commit, _ = sh(['git', '-C', root, 'rev-parse', 'HEAD'], 10)
    commit = commit.strip() if ok else ''
    ok, date, _ = sh(['git', '-C', root, 'log', '-1', '--format=%cs'], 10)
    ok2, dirty, _ = sh(['git', '-C', root, 'status', '--porcelain', '--untracked-files=no', '--', '.'], 20)
    ok3, remote, _ = sh(['git', '-C', root, 'remote', 'get-url', 'origin'], 10)
    info, by_ext, by_kind = {}, {}, {}
    for f in files:
        n, size = count_file(os.path.join(root, f))
        ext = os.path.splitext(f)[1].lower() or os.path.basename(f)
        k = classify(f)
        code = ext in CODE_EXT
        info[f] = (n, size, k, code)
        if n is None:
            continue
        if code and k in ('source', 'test'):
            e = by_ext.setdefault(ext, [0, 0, 0, 0])
            e[0 if k == 'source' else 2] += 1
            e[1 if k == 'source' else 3] += n
        kk = by_kind.setdefault(k, [0, 0])
        kk[0] += 1
        kk[1] += n
    src = {f: v for f, v in info.items() if v[3] and v[2] == 'source' and v[0] is not None}

    def table(prefix, depth):
        t = {}
        for f, v in info.items():
            if prefix and not f.startswith(prefix + '/'):
                continue
            rest = f[len(prefix) + 1:] if prefix else f
            top = rest.split('/')[0] + ('/' if '/' in rest else '')
            e = t.setdefault(top, [0, 0, 0])
            e[0] += 1
            if f in src:
                e[1] += 1
                e[2] += v[0]
        return sorted(t.items(), key=lambda kv: (-kv[1][2], -kv[1][0], kv[0]))
    top = table('', 1)
    total_src = sum(v[0] for v in src.values()) or 1
    dom = top[0][0].rstrip('/') if top and top[0][0].endswith('/') and top[0][1][2] * 2 > total_src else ''
    sub = table(dom, 2) if dom else []
    members, entries = [], []
    for f in files:
        b, d = os.path.basename(f), os.path.dirname(f)
        if f.count('/') > 5 or GEN_RE.search(f) or (TEST_RE.search(f) and b != 'Cargo.toml'):
            continue
        p = os.path.join(root, f)
        if b == 'Cargo.toml':
            s = read(p)
            for m in toml_list(s, 'workspace', 'members'):
                members.append((d + '/' if d else '') + m)
            for m in re.finditer(r'(?ms)^\[\[bin\]\]\s*$(.*?)(?=^\[|\Z)', s):
                nm, pt = re.search(r'name\s*=\s*"([^"]+)"', m.group(1)), re.search(r'path\s*=\s*"([^"]+)"', m.group(1))
                entries.append(('bin', nm.group(1) if nm else '?', (d + '/' if d else '') + (pt.group(1) if pt else 'src/main.rs')))
        elif b == 'package.json':
            try:
                j = json.loads(read(p))
            except ValueError:
                continue
            ws = j.get('workspaces')
            ws = ws.get('packages', []) if isinstance(ws, dict) else ws or []
            members += [(d + '/' if d else '') + w for w in ws if isinstance(w, str)]
            bins = j.get('bin')
            for nm, pt in (bins.items() if isinstance(bins, dict) else [(j.get('name', '?'), bins)] if bins else []):
                entries.append(('bin', nm, os.path.normpath(os.path.join(d, str(pt)))))
            if not d or f.count('/') == 1:
                sc = j.get('scripts') or {}
                if isinstance(sc, dict):
                    entries += [('npm script', nm, f + ' · ' + T.clip(sc[nm], 60)) for nm in list(sc) if nm in ('start', 'dev', 'build', 'test', 'serve')]
        elif b == 'pnpm-workspace.yaml':
            members += [(d + '/' if d else '') + x for x in re.findall(r'(?m)^\s*-\s*["\']?([^"\'\n#]+?)["\']?\s*$', read(p))]
        elif b == 'pyproject.toml':
            s = read(p)
            for sec in ('project.scripts', 'tool.poetry.scripts'):
                m = re.search(r'(?ms)^\[%s\]\s*$(.*?)(?=^\[|\Z)' % re.escape(sec), s)
                if m:
                    entries += [('script', a, t) for a, t in re.findall(r'(?m)^\s*["\']?([\w.\-]+)["\']?\s*=\s*["\']([^"\']+)', m.group(1))]
        elif b in ('go.mod',):
            m = re.search(r'(?m)^module\s+(\S+)', read(p, 4000))
            entries.append(('go module', m.group(1) if m else '?', f))
        elif b in ('main.rs', 'main.go', 'main.py', '__main__.py', 'main.ts', 'main.swift', 'Main.java', 'main.kt', 'manage.py'):
            entries.append(('main', os.path.basename(d) or b, f))
    seen, ent = set(), []
    for e in entries:
        if (e[0], e[2]) not in seen and not (e[0] == 'main' and any(x[2] == e[2] for x in ent)):
            seen.add((e[0], e[2]))
            ent.append(e)
    exp = []
    import fnmatch
    dirs = sorted({os.path.dirname(f) for f in files if os.path.basename(f) in MANIFESTS and os.path.dirname(f)})
    for m in members:
        m = m.rstrip('/')
        if m.startswith('!'):
            continue
        hit = [d for d in dirs if fnmatch.fnmatch(d, m)] if '*' in m else [m]
        exp += [h for h in hit if h not in exp]
    mem = []
    for m in sorted(exp):
        fs = [v for f, v in src.items() if f.startswith(m + '/')]
        mem.append((m, len(fs), sum(v[0] for v in fs)))
    docs = sorted({f.split('/')[0] + '/' for f in files if re.match(r'docs?(?:/|$)', f, re.I)} | {os.path.dirname(f) + '/' for f in files if re.search(r'/docs?/', f) and f.count('/') <= 2})[:12]
    tests = {}
    for f, v in info.items():
        if v[2] == 'test':
            m = re.match(r'^(.*?(?:^|/)(?:tests?|__tests__|spec|e2e))(?:/|$)', f, re.I)
            if m:
                tests[m.group(1) + '/'] = tests.get(m.group(1) + '/', 0) + 1
    big = sorted(((f, v[0]) for f, v in src.items()), key=lambda x: -x[1])[:15]
    zdirs, zfiles = [], {}
    if zone:
        dd = {}
        for one in [x.strip().strip('/') for x in zone.split(',') if x.strip().strip('/')]:
            z, here = re.sub(r'[\s_]+', '-', one.lower()), any(f.startswith(one + '/') for f in src)
            for f in src:
                parts = f.split('/')[:-1]
                key = one if here and f.startswith(one + '/') else '' if here else next(('/'.join(parts[:i + 1]) for i, p in enumerate(parts) if z == p.lower() or (len(z) > 2 and z in p.lower())), '')
                if key and f not in zfiles:
                    zfiles[f] = src[f][0]
                    e = dd.setdefault(key, [0, 0])
                    e[0] += 1
                    e[1] += src[f][0]
        zdirs = sorted(((k, v[0], v[1]) for k, v in dd.items()), key=lambda x: -x[2])[:12]
    m = re.search(r'github\.com[:/]([^/\s]+/[^/\s]+?)(?:\.git)?$', remote.strip()) if ok3 else None
    vis = visibility(m.group(1)) if m and fetch else ''
    local = (unpublished(root) or ('' if pushed(root, commit, m.group(1)) else 'HEAD가 원격에 없다')) if vis == 'public' else ''
    readme = next((f for f in files if re.match(r'readme(\.\w+)?$', f, re.I)), '')
    heads = T.headings(read(os.path.join(root, readme)))[:20] if readme else []
    return {'commit': commit, 'date': date.strip(), 'dirty': len([x for x in dirty.split('\n') if x.strip()]) if ok2 else None, 'remote': m.group(1) if m else '', 'visibility': vis, 'local': local,
            'files': len(files), 'src_files': len(src), 'src_lines': sum(v[0] for v in src.values()), 'by_ext': by_ext, 'by_kind': by_kind, 'top': top, 'dominant': dom, 'sub': sub,
            'members': mem, 'entries': ent, 'docs': docs, 'tests': sorted(tests.items(), key=lambda kv: -kv[1])[:12], 'big': big, 'zone_dirs': zdirs, 'zone_files': sorted(zfiles.items(), key=lambda kv: (-kv[1], kv[0])), 'readme': readme, 'readme_heads': heads}


def repo_md(r, zone):
    o = ['- 커밋 `%s` (%s)%s · 파일 %s개' % (r['commit'][:12] or '(git 아님)', r['date'] or '날짜 없음', ' · 커밋 안 된 변경 %d개' % r['dirty'] if r['dirty'] else '', '{:,}'.format(r['files'])),
         '- 소스 %s개 파일 %s줄 (테스트·생성물·벤더·lock 빼고 센 값)' % ('{:,}'.format(r['src_files']), '{:,}'.format(r['src_lines'])), '']
    o += ['## 언어 (확장자: 소스 파일/줄 · 테스트 파일/줄)', '']
    o += ['- `%s` %s/%s · 테스트 %s/%s' % (e, '{:,}'.format(v[0]), '{:,}'.format(v[1]), '{:,}'.format(v[2]), '{:,}'.format(v[3])) for e, v in sorted(r['by_ext'].items(), key=lambda kv: -kv[1][1])[:10]]
    if zone:
        o += ['', '## 구역 `%s` — 이름이 맞는 폴더' % zone, '']
        o += ['- `%s` 소스 %d개 %s줄' % (d, n, '{:,}'.format(l)) for d, n, l in r['zone_dirs']] or ['- 이름이 맞는 폴더가 없다. 구역 경계는 원문을 읽고 정한다(지도를 만들었으면 그 경계). 경로를 알면 `--zone 경로,경로`']
        if r['zone_files']:
            o.append('- 파일 %d개(줄 많은 순%s): ' % (len(r['zone_files']), ' 60개까지' if len(r['zone_files']) > 60 else '') + ' · '.join('%s(%d)' % x for x in r['zone_files'][:60]))
    o += ['', '## 최상위 (파일 · 소스 파일 · 소스 줄)', '', '| 이름 | 파일 | 소스 | 줄 |', '|---|---:|---:|---:|']
    o += ['| %s | %d | %d | %s |' % (n, v[0], v[1], '{:,}'.format(v[2])) for n, v in r['top'] if n.endswith('/') or v[1]]
    loose = [n for n, v in r['top'] if not n.endswith('/') and not v[1]]
    if loose:
        o += ['', '- 최상위 파일: ' + ' · '.join(loose[:40])]
    if r['sub']:
        o += ['', '## %s/ 아래 (소스의 절반 넘게 여기 있다)' % r['dominant'], '', '| 이름 | 파일 | 소스 | 줄 |', '|---|---:|---:|---:|']
        o += ['| %s | %d | %d | %s |' % (n, v[0], v[1], '{:,}'.format(v[2])) for n, v in r['sub'] if v[1]][:150]
    if r['members']:
        o += ['', '## 워크스페이스 멤버 %d개 (소스 파일 · 줄) — 구역은 이 전체를 나눈다' % len(r['members']), '']
        o.append(' · '.join('%s(%d, %s)' % (m, n, '{:,}'.format(l)) for m, n, l in r['members']))
    o += ['', '## 진입점 후보 %d개' % len(r['entries']), '']
    o += ['- %s `%s` — %s' % e for e in r['entries'][:40]] or ['- 찾지 못했다']
    o += ['', '## 가장 큰 소스 파일 15개', ''] + ['- %s %s줄' % (f, '{:,}'.format(n)) for f, n in r['big']]
    o += ['', '## 문서 · 테스트 폴더', '', '- 문서: ' + (' · '.join(r['docs']) or '없음'), '- 테스트: ' + (' · '.join('%s(%d)' % t for t in r['tests']) or '없음')]
    if r['readme_heads']:
        o += ['', '## %s 제목' % r['readme'], ''] + ['- %s:%d %s' % (r['readme'], n, t) for n, _, t in r['readme_heads']]
    return o


# ---------- 스킬 ----------
def skill_facts(root):
    files = [f for f in list_files(root) if not f.startswith('.git/')]
    s = read(os.path.join(root, 'SKILL.md'))
    meta, start = T.front_matter(s)
    links, broken = [], []
    for f in files:
        if not f.endswith('.md') or f.count('/') > 3 or TEST_RE.search(f) or '/fixtures/' in f:
            continue
        for i, ln in enumerate(read(os.path.join(root, f)).split('\n'), 1):
            for m in re.finditer(r'\[[^\]\n]*\]\(([^)\s]+)\)', ln):
                t = m.group(1).split('#')[0]
                if not t or re.match(r'^[a-z]+:', t) or re.search(r'[<{]', t):
                    continue
                p = os.path.normpath(os.path.join(os.path.dirname(f), t))
                (links if os.path.exists(os.path.join(root, p)) else broken).append(('%s:%d' % (f, i), t))
    scripts = []
    for f in files:
        ext = os.path.splitext(f)[1]
        if ext in ('.py', '.sh', '.js', '.mjs', '.ts', '.rb') and not TEST_RE.search(f) and not f.startswith(('evals/', 'tests/')):
            t = read(os.path.join(root, f))
            doc = re.search(r'^(?:#![^\n]*\n)?(?:#[^\n]*coding[^\n]*\n)?\s*(?:"""|\'\'\')\s*(.+?)(?:\n|"""|\'\'\')', t)
            cm = re.search(r'(?m)^(?:#(?!!)|//)\s*(.{8,})$', t)
            scripts.append({'path': f, 'lines': t.count('\n'), 'doc': T.clip(doc.group(1) if doc else cm.group(1) if cm else '', 90),
                            'sub': sorted(set(re.findall(r'add_parser\(\s*[\'"]([\w\-]+)', t)))[:12], 'args': sorted(set(re.findall(r'add_argument\(\s*[\'"](--?[\w\-]+)', t)))[:14]})
    load = [(f, len(read(os.path.join(root, f)))) for f in files if f.endswith('.md') and (f == 'SKILL.md' or f.startswith(('references/', 'reference/', 'formats/', 'docs/')))]
    return {'name': meta.get('name', ''), 'description': meta.get('description', ''), 'version': re.search(r'version:\s*"?([\w.\-]+)', s[:3000]).group(1) if re.search(r'version:\s*"?([\w.\-]+)', s[:3000]) else '',
            'sections': T.headings(s), 'links': links, 'broken': broken, 'scripts': scripts, 'load': load,
            'assets': [f for f in files if f.startswith(('assets/', 'templates/', 'template/'))], 'tests': [f for f in files if TEST_RE.search(f) or f.startswith(('tests/', 'evals/'))], 'files': len(files), 'body_start': start}


def skill_md(k):
    tot = sum(n for _, n in k['load'])
    main = dict(k['load']).get('SKILL.md', 0)
    o = ['- 이름 `%s` · 버전 %s · 파일 %d개' % (k['name'], k['version'] or '원문에 없음', k['files']), '- 로드되는 글자: SKILL.md %s자 (늘 읽음) · 참조까지 모두 %s자' % ('{:,}'.format(main), '{:,}'.format(tot)),
         '- description(발동 조건): ' + T.clip(k['description'], 400), '', '## SKILL.md 절 (줄)', '']
    o += ['- SKILL.md:%d %s%s' % (n, '  ' * (l - 1), t) for n, l, t in k['sections']]
    o += ['', '## 읽히는 글 (글자)', ''] + ['- %s %s' % (f, '{:,}'.format(n)) for f, n in k['load']]
    o += ['', '## 스크립트 %d개 (정적으로 읽음, 실행 안 함)' % len(k['scripts']), '']
    o += ['- `%s` %d줄%s%s%s' % (s['path'], s['lines'], ' — ' + s['doc'] if s['doc'] else '', ' · 하위 명령: ' + ', '.join(s['sub']) if s['sub'] else '', ' · 인자: ' + ', '.join(s['args']) if s['args'] else '') for s in k['scripts']] or ['- 없음']
    o += ['', '## 링크 %d개%s' % (len(k['links']), ' · 깨진 것 %d개' % len(k['broken']) if k['broken'] else ' · 깨진 것 없음'), '']
    o += ['- %s → %s' % l for l in k['links'][:30]] + ['- 깨짐 %s → %s' % l for l in k['broken']]
    o += ['', '## 템플릿·자산 / 테스트', '', '- 자산: ' + (' · '.join(k['assets'][:20]) or '없음'), '- 테스트: ' + (' · '.join(k['tests'][:20]) or '없음') + (' 외 %d개' % (len(k['tests']) - 20) if len(k['tests']) > 20 else '')]
    return o


# ---------- 글 ----------
def cond_lines(lines, start=1, label='raw:%d', code=False):
    """조건어가 있는 줄. 많으면 센 것(only·unless·default·bound·must·if)부터 최대 40줄, 줄 순서로."""
    rows, fence = [], False
    for i, ln in enumerate(lines, 1):
        if i < start:
            continue
        if T.FENCE.match(ln):
            fence = not fence
            continue
        if (fence and not code) or not ln.strip() or re.match(r'^\s*#{1,6}\s', ln):
            continue
        ks = T.cond_kinds(ln)
        if ks:
            rows.append((len([k for k in ks if k in T.STRONG]) * 2 + len(ks), i, ks, ln))
    total = len(rows)
    rows = sorted(sorted(rows, key=lambda r: (-r[0], r[1]))[:COND_MAX], key=lambda r: r[1])
    return [(label % i, '·'.join(ks), T.clip(T.hide_secrets(ln), 180)) for _, i, ks, ln in rows], total


def number_lines(lines, start=1, limit=40):
    out, seen = [], set()
    for i, ln in enumerate(lines, 1):
        if i < start:
            continue
        s = re.sub(r'https?://\S+|\b[0-9a-f]{7,40}\b', lambda m: ' ' * len(m.group(0)), ln)
        for raw, forms, pos in T.numbers(s, keep_code=True):
            key = sorted(forms)[0]
            if key in seen or (len(key) == 1 and raw == key):
                continue
            seen.add(key)
            out.append(('raw:%d' % i, raw, T.clip(ln[max(0, pos - 24):pos + len(raw) + 24], 60)))
    return out[:limit], len(out)


def structure(lines, ext):
    """코드·설정 파일의 뼈대(정의 줄 · 절 · 맨 위 키)."""
    out = []
    for i, ln in enumerate(lines, 1):
        if ext in CODE_EXT and (DEF.match(ln) or re.match(r'^[A-Z_][A-Z0-9_]{2,}\s*[:=]', ln) or re.match(r'^if __name__', ln)):
            out.append((i, T.clip(ln, 110)))
        elif ext in ('.toml', '.ini', '.cfg') and re.match(r'^\[', ln):
            out.append((i, ln.strip()))
        elif ext in ('.yaml', '.yml') and re.match(r'^[A-Za-z_"\'][^:]*:', ln):
            out.append((i, T.clip(ln, 110)))
        elif ext in ('.json', '.jsonc') and re.match(r'^(?:  |\t)"[^"]+"\s*:', ln):
            out.append((i, T.clip(ln.strip(), 110)))
    return out[:80]


def timed_lines(lines):
    out = []
    for i, ln in enumerate(lines, 1):
        m = re.match(r'^\s*(?:[-*]\s*)?\[?((?:\d{1,2}:)?\d{1,2}:\d{2})(?:[.,]\d+)?\]?(?:\s*-->\s*\S+)?\s*(.*)$', ln)
        if m:
            t = m.group(2) or (lines[i].strip() if i < len(lines) else '')
            out.append((i, m.group(1), T.clip(t, 120)))
    return out


def post_lines(lines):
    out, heads = [], [(i, int(m.group(1))) for i, m in ((i, POST_HEAD.match(ln)) for i, ln in enumerate(lines, 1)) if m]
    for i, ln in enumerate(lines, 1):
        m = POST_LINE.match(ln)
        if m and 1 <= int(m.group(1)) <= int(m.group(2)):
            out.append((i, '%s/%s' % m.groups(), T.clip(ln.strip('# '), 90)))
    return out or [(i, '%d/%d' % (k, max(x for _, x in heads)), T.clip(lines[i - 1].strip('# '), 90)) for i, k in heads]


def comment_lines(lines):
    return [(i, T.clip(ln.strip('# '), 90)) for i, ln in enumerate(lines, 1) if re.match(r'^#{1,4}\s*(?:댓글|comment|답변|reply)\s*\d*', ln, re.I)]


def body_chars(s, start, type_=''):
    """본문 글자 수 (머리말 · 수집 메타데이터 줄 제외)."""
    ls = s.split('\n')[start - 1:]
    return len('\n'.join(x for x in ls if not re.match(r'^- (?:URL|작성|수집|영상 링크|채널|공개 여부|자막 대용|설명란|원본 파일|저장소|변경 규모|작성자)\b', x)).strip())


def text_size(n):
    return '작음' if n < SMALL else '보통' if n <= LARGE else '큼'


def build(src, type_, zone='', fetch=True):
    """src = start가 만든 dict(kind, path, text, meta, body_start, name) → (pack dict 조각, pack.md 줄 목록)"""
    p, o = {}, []
    s, meta, start = src.get('text', ''), src.get('meta', {}), src.get('body_start', 1)
    lines = s.split('\n')
    ext = os.path.splitext(src.get('name', ''))[1].lower()
    if src['kind'] == 'dir' and type_ == 'skill':
        k = skill_facts(src['path'])
        tot = sum(n for _, n in k['load'])
        p['skill'] = k
        p['size'], p['size_why'] = text_size(tot), '읽히는 글 %s자(SKILL.md + 참조)' % '{:,}'.format(tot)
        p['chars'], p['lines'] = dict(k['load']).get('SKILL.md', 0), read(os.path.join(src['path'], 'SKILL.md')).count('\n')
        o = skill_md(k)
        sk = read(os.path.join(src['path'], 'SKILL.md')).split('\n')
        conds, total = cond_lines(sk, k['body_start'], 'SKILL.md:%d')
        secret = [x for f, _ in k['load'] for x in T.secrets(read(os.path.join(src['path'], f)))]
        heads = []
    elif src['kind'] == 'dir':
        r = repo_facts(src['path'], zone, fetch)
        p['repo'] = r
        big = r['src_files'] > 20
        p['size'], p['size_why'] = ('큼', '소스 파일 %s개(20개 초과)' % '{:,}'.format(r['src_files'])) if big else ('보통', '소스 파일 %d개(20개 이하)' % r['src_files'])
        p['chars'], p['lines'] = 0, r['src_lines']
        o = repo_md(r, zone)
        conds, total, secret, heads = [], 0, [], []
    elif src['kind'] == 'none':
        p['size'], p['size_why'], p['chars'], p['lines'] = '보통', '본문을 아직 못 읽었다', 0, 0
        return p, ['본문을 아직 읽지 못했다.']
    else:
        if src.get('cut'):
            o.append('- **잘린 사본**: 원문의 앞 {:,}자만 읽었다. 뒤는 검사하지 않으니 `source`에 그렇게 적는다'.format(src['cut']))
        n = body_chars(s, start, type_)
        p['chars'], p['lines'] = n, s.count('\n') + (0 if s.endswith('\n') or not s else 1)
        heads = T.headings(s)
        diff_at = diff_line(lines)
        if type_ == 'pr':
            f, p['size'], p['size_why'], diff = pr_facts(s, meta)
            p['pr'] = f
            o += ['- 파일 %d개 · +%s −%s · 소스 %d개 · 보이는 파일 %d개%s' % (f['total'], '{:,}'.format(f['add']), '{:,}'.format(f['del']), f['source_files'], f['shown'], ' · **잘린 사본**' if f['truncated'] else '')]
            if f['truncated_range']:
                o.append('- 잘린 범위: ' + T.clip(f['truncated_range'], 400))
            o += ['', '## 파일 표', '', '| 파일 | + | − | 종류 | 보임 |', '|---|---:|---:|---|---|']
            o += ['| %s | %d | %d | %s%s | %s |' % (r['path'], r['add'], r['del'], KIND_KO[r['kind']], {'new': ' 새 파일', 'gone': ' 지움'}.get(r['state'], ''), '일부' if r['part'] else '예' if r['shown'] else '아니오') for r in f['files']]
            src_lines = lines[:(diff_at or len(lines) + 1) - 1]
            conds, total = cond_lines(src_lines, start)
            added = [(('%s:%d' % (path, new)), t) for path, d in diff.items() if classify(path) == 'source' for h in d['hunks'] for sg, old, new, t in h['rows'] if sg == '+']
            extra = [(lb, '·'.join(T.cond_kinds(t)), T.clip(t, 150)) for lb, t in added if re.search(r'//|#|"""|/\*', t) and set(T.cond_kinds(t)) & T.STRONG]
            conds, total = (conds + extra)[:COND_MAX], total + len(extra)
            heads = [h for h in heads if not diff_at or h[0] < diff_at]
        else:
            p['size'], p['size_why'] = text_size(n), '본문 %s자' % '{:,}'.format(n)
            src_lines = lines
            conds, total = cond_lines(lines, start, code=ext in CODE_EXT or ext in CONF_EXT)
        o.insert(0, '- 본문 %s자 · 전체 %s줄 · 원문 줄은 `raw:n`(사본 `%s`의 줄 번호)' % ('{:,}'.format(n), '{:,}'.format(p['lines']), src.get('copy', 'source')))
        if heads:
            o += ['', '## 제목 %d개' % len(heads), ''] + ['- raw:%d %s%s' % (i, '  ' * (l - 1), T.clip(t, 100)) for i, l, t in heads[:80]]
        st = structure(lines, ext)
        if st:
            o += ['', '## 뼈대 (정의 · 절 · 키)', ''] + ['- raw:%d %s' % x for x in st]
            p['structure'] = len(st)
        if type_ == 'video':
            tl = timed_lines(lines)
            p['times'] = len(tl)
            o += ['', '## 시각이 있는 줄 %d개' % len(tl), ''] + ['- raw:%d [%s] %s' % x for x in tl[:80]] + (['- … 외 %d개' % (len(tl) - 80)] if len(tl) > 80 else [])
        if type_ == 'social-post':
            pl = post_lines(lines)
            p['posts'] = len(pl)
            o += ['', '## 글 번호 %d개' % len(pl), ''] + ['- raw:%d %s %s' % x for x in pl[:60]]
        if type_ == 'community-post':
            cl = comment_lines(lines)
            p['comments'] = len(cl)
            o += ['', '## 댓글 %d개 (읽은 범위)' % len(cl), ''] + ['- raw:%d %s' % x for x in cl[:80]]
        nums, nt = number_lines(src_lines, start)
        if nums:
            o += ['', '## 숫자 %d개%s' % (nt, ' 가운데 40개' if nt > 40 else ''), ''] + ['- %s **%s** … %s' % x for x in nums]
        secret = T.secrets(s)
    if conds:
        o += ['', '## 조건어가 있는 줄 %d개%s' % (total, ' 가운데 %d개' % len(conds) if total > len(conds) else ''), ''] + ['- %s [%s] %s' % c for c in conds]
    if secret:
        o += ['', '## 비밀 값 후보 (결과에 쓰지 않는다)', ''] + ['- %s %s (%d줄)' % x for x in secret[:20]]
    p['headings'] = heads[:80]
    p['conds'] = total
    p['secrets'] = len(secret)
    if src['kind'] == 'pr' and type_ == 'pr':
        kinds = ('source', 'doc', 'test')
        d = parse_diff(s)
        body = numbered_diff(d, kinds)
        if len(body) > 120000:
            body = numbered_diff(d, ('source', 'doc'))
            o += ['', '(diff가 커서 테스트 본문은 뺐다)']
        o += ['', '## PR 뒤 줄 번호를 단 diff (근거는 `경로:줄`, 지운 줄은 `경로:-줄`)', '', '```text', T.hide_secrets(body), '```']
    return p, o


def fact_numbers(p):
    """pack이 센 값도 원문 숫자로 친다 → (개수, 줄·글자 수). 줄·글자 수는 `N줄`·`N자`라 쓸 때만 인정한다."""
    out, lines = set(), set()

    def add(to, *vs):
        for v in vs:
            if isinstance(v, (list, tuple, dict)):
                add(to, *(v.values() if isinstance(v, dict) else v))
            elif isinstance(v, (int, float)) and not isinstance(v, bool):
                to.add(T.canon(str(v)))
    add(out, *[p.get(k) for k in ('posts', 'comments', 'times')])
    add(lines, *[p.get(k) for k in ('chars', 'lines', 'pr', 'repo', 'skill')])
    pr, r = p.get('pr') or {}, p.get('repo') or {}
    if pr:
        add(out, pr['total'], pr['source_files'], pr['shown'], [len([x for x in pr['files'] if x['kind'] == k]) for k in KIND_KO])
        add(lines, pr['add'] + pr['del'])
    add(out, r.get('files'), r.get('src_files'), r.get('dirty'), [v[::2] for v in (r.get('by_ext') or {}).values()], [v[0] for v in (r.get('by_kind') or {}).values()], [v[:2] for _, v in (r.get('top') or []) + (r.get('sub') or [])],
        [x[1] for k in ('members', 'zone_dirs', 'tests') for x in r.get(k) or []])
    for k in ('pr', 'repo', 'skill'):
        add(out, [len(x) for x in (p.get(k) or {}).values() if isinstance(x, list)])
    return out, lines


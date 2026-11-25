# -*- coding: utf-8 -*-
"""원문 접근과 근거 대조.

근거 쓰는 법 (model의 src)
  a/b.rs:10-20, 33     파일 줄 (PR은 PR 뒤 줄, 지운 줄은 a/b.rs:-12)
  raw:12-14 · 12-14 · L12   원문 사본의 줄 (파일 하나짜리 원문)
  [12:30]              영상 시각        3/7   글타래 글 번호
  https://…            주소             그 밖  원문에 그대로 있는 글자(절 제목 등)
"""
import functools
import itertools
import os
import re
import subprocess

from . import text as T

SKIP_DIRS = {'.git', 'node_modules', 'target', 'dist', 'build', '.next', 'vendor', '__pycache__', '.venv', 'venv', '.mypy_cache', '.turbo', 'into-out'}
EXT = r'(?:rs|go|py|rb|java|kt|swift|c|cc|cpp|h|hpp|cs|php|tsx?|jsx?|mjs|cjs|sql|sh|bash|zsh|md|mdx|txt|toml|ya?ml|json|jsonc|css|scss|html|proto|graphql|lock|csv|bazel|bzl|nix|xml|ini|cfg|env|vue|svelte|diff|patch|srt|vtt|ipynb|lua|ex|exs|scala|dart|zig|tf)'
RANGE = r'-?\d+(?:\s*[-–~]\s*\d+)?'
PATH_RE = re.compile(r'^(?P<p>[^:\n]*[^\s:/])\s*:\s*(?P<r>' + RANGE + r'(?:\s*,\s*:?' + RANGE + r')*)$')
PATH_ONLY = re.compile(r'^[^\s:]+(?:/[^\s:]*|\.' + EXT + r')$')
TIME_RE = re.compile(r'^\[?((?:\d{1,2}:)?\d{1,3}:\d{2})(?:[.,]\d+)?\]?(?:\s*[-–~]\s*\[?((?:\d{1,2}:)?\d{1,3}:\d{2})\]?)?$')
CAPTION = re.compile(r'^\s*((?:\d{1,2}:)?\d{1,3}:\d{2})(?:[.,]\d+)?\s*-->')                  # SRT·VTT의 시각 줄
POST_RE = re.compile(r'^\[?(\d{1,3})/(\d{1,3})\]?$')
POST_HEAD = re.compile(r'(?im)^#{1,4}\s*(?:트윗|글|post|tweet)\s*#?(\d{1,3})\b')          # `## 트윗 3`
RAW_NAMES = ('raw', 'source', 'l', '원문', '줄')
DEF = re.compile(r'^\s*(?:(?:pub(?:\([^)]*\))?|export|default|async|static|public|private|protected|const|unsafe|abstract)\s+)*(?:fn|func|function|def|class|impl|trait|interface|struct|enum|type|mod|const)\b')
POST_LINE = re.compile(r'^\W*(?:스레드|트윗|post|tweet|thread)?\s*\[?(\d{1,2})/(\d{1,2})\]?', re.I)                   # `1/7 …`
PLUS = re.compile(r'^\+\+\+ (?:b/)?([^\t\n]+?)(?:\t.*|\s+\d{4}-\d\d-\d\d.*)?$')
DIFF_HEAD = re.compile(r'^diff --git a/(.+?) b/(.+)$')
QUOTED = re.compile(r'"((?:[^"\\]|\\.)*)"')
HUNK = re.compile(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$')


def git_path(ln):
    """diff 머리 줄의 Git 따옴표 경로("a/\\354\\204…")를 실제 글자로 푼다."""
    def plain(m):
        s = re.sub(r'\\([0-7]{3}|.)', lambda x: chr(int(x.group(1), 8)) if len(x.group(1)) == 3 else {'t': '\t', 'n': '\n', 'r': '\r'}.get(x.group(1), x.group(1)), m.group(1).encode('utf-8').decode('latin-1'))
        return s.encode('latin-1').decode('utf-8', 'replace')
    return QUOTED.sub(plain, ln)


def inside(root, rel):
    """실제 경로가 root 안인가 (밖을 가리키는 링크·`..`는 읽지 않는다)."""
    r = os.path.realpath(root)
    return (os.path.realpath(os.path.join(root, rel)) + os.sep).startswith(r.rstrip(os.sep) + os.sep)


def list_files(root):
    """root 아래 파일(상대 경로). git이면 추적 파일만."""
    dirs = {}

    def ok(f):
        p, d = os.path.join(root, f), os.path.dirname(f)
        if d not in dirs:
            dirs[d] = inside(root, d)
        return dirs[d] and os.path.isfile(p) and (not os.path.islink(p) or inside(root, f))
    try:
        r = subprocess.run(['git', '-C', root, 'ls-files', '-z', '--cached', '--others', '--exclude-standard', '--', '.'],
                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=40)
        if r.returncode == 0 and r.stdout:
            got = [f for f in r.stdout.decode('utf-8', 'replace').split('\0') if f and 'into-out' not in f.split('/')[:-1]]          # 우리가 만든 결과는 원문이 아니다
            return [f for f in got if ok(f)]
    except (OSError, subprocess.SubprocessError):
        pass
    out = []
    for d, ds, fs in os.walk(root):
        ds[:] = [x for x in ds if x not in SKIP_DIRS]
        for f in fs:
            out.append(os.path.relpath(os.path.join(d, f), root).replace(os.sep, '/'))
    return sorted(f for f in out if ok(f))


def parse_diff(s):
    """diff 글 → {경로: {'add','del','new','gone','binary','hunks':[{'head','rows':[(부호, 옛 줄, 새 줄, 글)]}]}} (나온 순서)"""
    files, cur, hunk, o, n, left_o, left_n, prev = {}, None, None, 0, 0, 0, 0, ''
    for ln in s.split('\n'):
        if ln.startswith(('diff --git "', 'diff --git a/', '--- "', '+++ "')) and (hunk is None or left_o <= 0 and left_n <= 0):
            ln = git_path(ln)
        before, prev = prev, ln
        m = DIFF_HEAD.match(ln)
        if m:
            cur = files.setdefault(m.group(2), {'add': 0, 'del': 0, 'new': False, 'gone': False, 'binary': False, 'hunks': [], 'old': m.group(1)})
            hunk = None
            continue
        if hunk is None or (left_o <= 0 and left_n <= 0):
            m = PLUS.match(ln) if cur is None or cur['hunks'] else None     # diff --git 줄이 없는 patch (`---` 다음 `+++`)
            if m and (cur is None or before.startswith('--- ')):
                a = PLUS.match('+++ ' + re.sub(r'^a/', 'b/', before[4:])) if before.startswith('--- ') else None
                old = a.group(1) if a else m.group(1)
                name = old if m.group(1) == '/dev/null' else m.group(1)
                cur = hunk = None
                if name != '/dev/null':
                    cur = files.setdefault(name, {'add': 0, 'del': 0, 'new': old == '/dev/null', 'gone': m.group(1) == '/dev/null', 'binary': False, 'hunks': [], 'old': name if old == '/dev/null' else old})
                continue
        if cur is None:
            continue
        if hunk is None or (left_o <= 0 and left_n <= 0):
            if ln.startswith('new file'):
                cur['new'] = True
            elif ln.startswith('deleted file'):
                cur['gone'] = True
            elif ln.startswith('Binary files'):
                cur['binary'] = True
            h = HUNK.match(ln)
            if h:
                o, n = int(h.group(1)), int(h.group(3))
                left_o, left_n = int(h.group(2) or 1), int(h.group(4) or 1)
                hunk = {'head': h.group(5).strip(), 'rows': [], 'old': o, 'new': n, 'cut': False}
                cur['hunks'].append(hunk)
            elif ln.startswith('```'):
                cur = hunk = None
            elif ln.startswith('+++ ') and not cur['hunks']:
                pass
            continue
        sign = ln[:1]
        if sign == '+':
            hunk['rows'].append(('+', None, n, ln[1:]))
            n += 1
            left_n -= 1
            cur['add'] += 1
        elif sign == '-':
            hunk['rows'].append(('-', o, None, ln[1:]))
            o += 1
            left_o -= 1
            cur['del'] += 1
        elif sign == '\\':
            continue
        elif ln.startswith('```') or HUNK.match(ln) or DIFF_HEAD.match(ln):     # 잘린 hunk
            hunk['cut'] = True
            left_o = left_n = 0
            h = HUNK.match(ln)
            if h:
                o, n = int(h.group(1)), int(h.group(3))
                left_o, left_n = int(h.group(2) or 1), int(h.group(4) or 1)
                hunk = {'head': h.group(5).strip(), 'rows': [], 'old': o, 'new': n, 'cut': False}
                cur['hunks'].append(hunk)
            elif ln.startswith('```'):
                cur = hunk = None
        elif sign == ' ' or ln == '':
            hunk['rows'].append((' ', o, n, ln[1:]))
            o += 1
            n += 1
            left_o -= 1
            left_n -= 1
        else:
            hunk['cut'] = True
            left_o = left_n = 0
    return files


def has_diff(s):
    return 'diff --git ' in s or any(d['hunks'] for d in parse_diff(s).values())


def diff_line(lines):
    """diff가 시작하는 줄 번호(1부터). 없으면 None."""
    return next((i for i, ln in enumerate(lines, 1) if ln.startswith('diff --git ') or ln.startswith('--- ') and lines[i:i + 1] and PLUS.match(lines[i])), None)


class Source(object):
    """kind: file(원문 하나) · pr(사본 + diff) · dir(폴더 · 저장소) · none(본문을 아직 못 읽음)"""

    def __init__(self, kind, path, names=()):
        self.kind, self.path, self.names = kind, path, set(x.lower() for x in names)
        self._lines, self._files, self._by_name, self._text = {}, None, None, None
        self.diff = {}
        self._extra_numbers, self._line_numbers, self._flat = set(), set(), None
        self._numbers = None
        if kind == 'pr':
            self.diff = parse_diff(self.text())

    # ----- 글 -----
    def text(self):
        if self._text is None:
            if self.kind in ('file', 'pr'):
                try:
                    self._text = open(self.path, encoding='utf-8', errors='replace').read()
                except OSError:
                    self._text = ''
            else:
                self._text = ''
        return self._text

    def files(self):
        if self._files is None:
            self._files = set(list_files(self.path)) if self.kind == 'dir' else set(self.diff)
            self._by_name = {}
            for f in self._files:
                self._by_name.setdefault(os.path.basename(f), []).append(f)
        return self._files

    def lines(self, rel):
        if rel not in self._lines:
            if rel is None:
                s = self.text()
                self._lines[rel] = (s[:-1] if s.endswith('\n') else s).split('\n')
            else:
                try:
                    s = open(os.path.join(self.path, rel), encoding='utf-8', errors='replace').read()
                    self._lines[rel] = (s[:-1] if s.endswith('\n') else s).split('\n')
                except OSError:
                    self._lines[rel] = []
        return self._lines[rel]

    def find(self, name):
        """(맞는 파일들, 정확히 맞았나)"""
        self.files()
        n = re.sub(r'^\./', '', name)
        if n in self._files:
            return [n], True
        hits = [f for f in self._by_name.get(os.path.basename(n), []) if f == n or f.endswith('/' + n)]
        return sorted(hits), False

    # ----- 근거 하나 -----
    def resolve(self, src):
        """src 글 하나 → {'ok','msg','warn','label','text','lines':[(번호,글)],'kind'}"""
        s = str(src).strip().strip('`').strip()
        out = {'ok': True, 'msg': '', 'warn': '', 'label': s, 'text': '', 'lines': [], 'kind': 'text'}
        if not s:
            return dict(out, ok=False, msg='근거가 비었다')
        if re.match(r'^https?://', s):
            got = [(i, ln) for i, ln in enumerate(self.lines(None), 1) if s in ln][:2] if self.kind in ('file', 'pr') else []      # 원문에 적힌 주소면 그 줄
            return dict(out, kind='url', lines=got, text='\n'.join(t for _, t in got))
        m = TIME_RE.match(s)
        if m:
            out.update(kind='time', label='[%s]' % s.strip('[]'))
            if self.kind in ('file', 'pr'):
                want = [t for t in m.groups() if t]
                miss = [t for t in want if seconds(t) not in clock(self.text())]
                if miss:
                    out['warn'] = '시각 %s가 원문 시각 목록에 없다(가까운 장면 시각인지 본다)' % ', '.join(miss)
                else:
                    out['lines'] = self.spoken([seconds(t) for t in want])
                    out['text'] = '\n'.join(x for _, x in out['lines'])
                    if not out['lines']:
                        out['warn'] = '시각 %s은 자막의 끝이다. 시작 시각을 쓴다' % want[0]
            return out
        m = POST_RE.match(s)
        if m:
            k, n = int(m.group(1)), int(m.group(2))
            out.update(kind='post', label='%d/%d' % (k, n))
            if k < 1 or k > n:
                return dict(out, ok=False, msg='글 번호 %s가 범위를 벗어났다' % s)
            heads = [int(x) for x in re.findall(POST_HEAD, self.text())] if self.kind in ('file', 'pr') else []
            if self.kind in ('file', 'pr') and not re.search(r'(?<!\d)%d\s*/\s*%d(?!\d)' % (k, n), self.text()) and not (k in heads and n == max(heads)):
                return dict(out, ok=False, msg='원문에 글 번호 %d/%d가 없다' % (k, n))
            out['lines'] = self.post(k, n) if self.kind in ('file', 'pr') else []
            out['text'] = '\n'.join(t for _, t in out['lines'])
            return out
        m = re.match(r'^(?:raw|source|L|원문|줄)\s*[:#]?\s*L?(%s(?:\s*,\s*%s)*)\s*줄?$' % (RANGE, RANGE), s, re.I) or re.match(r'^L?(%s(?:\s*,\s*%s)*)\s*줄?$' % (RANGE, RANGE), s)
        if m:
            return self._span(None, m.group(1), out)
        m = PATH_RE.match(s)
        if m:
            p = m.group('p')
            if self.kind in ('file', 'pr') and (p.lower() in self.names or p.lower() in RAW_NAMES):
                return self._span(None, m.group('r'), out)
        if m and (' ' not in p or self.kind in ('dir', 'pr') and self.find(p)[0]):           # 빈칸이 든 이름은 파일이 있을 때만 경로로 본다
            if self.kind == 'file':
                return dict(out, ok=False, msg='원문은 파일 하나다. 줄 번호는 `raw:12-14`로 쓴다(지금 `%s`)' % s)
            hits, exact = self.find(p)
            if not hits:
                return dict(out, ok=False, msg='파일 `%s`가 %s에 없다' % (p, 'diff' if self.kind == 'pr' else '원문'))
            if len(hits) > 1:
                out['warn'] = '`%s`가 %d곳이다(%s…). 전체 경로로 쓴다' % (p, len(hits), hits[0])
            return self._span(hits[0], m.group('r'), out, show=p if exact else hits[0])
        base, _, sect = s.partition('#')
        if PATH_ONLY.match(base):
            if self.kind in ('file', 'pr') and base.lower() in self.names:
                return self._whole(None, sect, out)
            if self.kind != 'none':
                hits, _ = self.find(base)
                if hits:
                    return self._whole(hits[0], sect, out)
                if self.kind == 'pr' and base in self.text():
                    return dict(out, kind='file')
                if self.kind == 'dir' and inside(self.path, base) and os.path.isdir(os.path.join(self.path, base)):
                    return dict(out, kind='file')
                if base not in self.text():
                    return dict(out, ok=False, msg='파일 `%s`가 원문에 없다' % base)
            return dict(out, kind='file')
        if self.kind in ('file', 'pr'):
            key = re.sub(r'\s+', ' ', s).lower()
            if key not in re.sub(r'\s+', ' ', self.text()).lower():
                return dict(out, ok=False, msg='근거 `%s`를 원문에서 못 찾았다. `raw:줄`·`경로:줄`·`[mm:ss]`·`n/N`이나 원문 글자 그대로 쓴다' % T.clip(s, 40))
            out['lines'] = self.section(None, s) or self.quoted(key)
            out['text'] = '\n'.join(t for _, t in out['lines'])
            return out
        if self.kind == 'dir':
            return dict(out, ok=False, msg='근거 `%s`를 `경로:줄`로 쓴다' % T.clip(s, 40))
        return out

    def spoken(self, at):
        """시각이 있는 줄부터 그 자막 블록(빈 줄이나 다음 시각 앞)까지. 제목 줄이면 그 절. SRT·VTT는 그때 시작하는 자막부터 끝 시각 전에 시작한 자막까지."""
        ls = self.lines(None)
        caps = [(seconds(m.group(1)), i) for i, m in ((i, CAPTION.match(ln)) for i, ln in enumerate(ls)) if m]
        hit = [i for t, i in caps if at[0] <= t < max(at[-1], at[0] + 1)]
        if hit:
            ends = [next((k for k in range(i, len(ls)) if not ls[k].strip() or k > i and CAPTION.match(ls[k])), len(ls)) for i in hit]
            return [(k + 1, ls[k]) for i, e in zip(hit, ends) for k in range(i, e)]
        starts, got = [i for i, ln in enumerate(ls) if at[0] in clock(ln) and not CAPTION.match(ln)][:2], {}
        ends = [next((k for k in range(i, len(ls)) if at[1] in clock(ls[k])), i) if at[1:] else i for i in starts]
        for i in sorted({k for a, b in zip(starts, ends) for k in range(a, b + 1)}):
            rows = self.section(None, ls[i]) if re.match(r'#{1,6}\s', ls[i]) else []
            j = i + 1
            while not rows and j < len(ls) and ls[j].strip() and not clock(ls[j]):
                j += 1
            got.update(rows or [(k + 1, ls[k]) for k in range(i, j)])
        return sorted(got.items())

    def section(self, rel, title):
        """절 제목 → 그 절의 줄(같거나 높은 단계의 다음 제목 앞까지). 그런 제목이 없으면 []. PR의 파일은 diff에 보이는 PR 뒤 줄에서 찾는다."""
        rows = [(n, t) for h in self.diff[rel]['hunks'] for _, _, n, t in h['rows'] if n] if self.kind == 'pr' and rel else list(enumerate(self.lines(rel), 1))
        key = re.sub(r'\s+', ' ', re.sub(r'^#+\s*', '', title)).strip().lower()
        hs = T.headings('\n'.join(t for _, t in rows))
        names = [[re.sub(r'\s+', ' ', t).lower(), T.visible(t).lower()] for _, _, t in hs]
        k = next((k for k, n in enumerate(names) if key in n or key == re.sub(r'\s', '-', re.sub(r'[^\w\s\-]', '', n[1]))), None)
        if k is None:
            return []
        end = next((i for i, lv, _ in hs[k + 1:] if lv <= hs[k][1]), len(rows) + 1)
        return rows[hs[k][0] - 1:end - 1]

    def quoted(self, key):
        """원문 글자를 그대로 적은 근거(빈칸 차이는 무시) → 그 줄들. 제목의 일부면 그 절."""
        ls = self.lines(None)
        if self._flat is None:
            self._flat = [re.sub(r'\s+', ' ', ln.strip()).lower() + ' ' for ln in ls]
        at = ''.join(self._flat).find(key)
        if at < 0:
            return []
        ends = list(itertools.accumulate(map(len, self._flat)))
        a, b = [next(i for i, e in enumerate(ends, 1) if e > x) for x in (at, at + len(key) - 1)]
        return (self.section(None, ls[a - 1]) if re.match(r'#{1,6}\s', ls[a - 1]) else []) or [(n, ls[n - 1]) for n in range(a, b + 1)]

    def _whole(self, rel, sect, out):
        """파일 전체(`a.md`)나 그 안의 절(`a.md#제목`). 파일 전체는 줄을 세지 않고 글만 대조한다."""
        if sect:
            rows = self.section(rel, sect)
            if not rows:
                return dict(out, ok=False, msg='%s에 제목 `%s`이 없다. 제목을 그대로 쓰거나 줄로 쓴다(`%s:줄`)' % ('`%s`%s' % (rel, '의 diff' if self.kind == 'pr' else '') if rel else '원문', T.clip(sect, 40), rel or 'raw'))
            return dict(out, file=rel, lines=rows, text='\n'.join(t for _, t in rows))
        if self.kind == 'pr' and rel:
            body = '\n'.join(t for h in self.diff[rel]['hunks'] for _, _, _, t in h['rows'])
        else:
            body = '\n'.join(self.lines(rel))
        return dict(out, kind='file', text=body, **({'file': rel} if rel else {}))

    def post(self, k, n):
        """글 k/n의 줄들: 시작 줄부터 다음 글 직전까지. 번호를 글 끝에 적은 글타래면 앞 글 다음부터 그 줄까지."""
        ls = self.lines(None)
        head = [(i, int(m.group(1))) for i, m in ((i, POST_LINE.match(ln)) for i, ln in enumerate(ls)) if m and int(m.group(2)) == n]
        if not any(j == k for _, j in head):
            head = [(i, int(m.group(1))) for i, m in ((i, POST_HEAD.match(ln)) for i, ln in enumerate(ls)) if m]
        at = next((i for i, j in head if j == k), None)
        if at is not None:
            end = next((i for i, j in head if i > at), len(ls))
        else:
            tail = [(i, int(m.group(1))) for i, m in ((i, re.search(r'(?<!\d)(\d{1,2})\s*/\s*%d(?!\d)' % n, ln)) for i, ln in enumerate(ls)) if m]
            end = next((i + 1 for i, j in tail if j == k), 0)
            at = max([i + 1 for i, j in tail if i + 1 < end] or [0])
        return [(i + 1, ls[i]) for i in range(at, end)]

    def _span(self, rel, spec, out, show=None):
        parts = [p.strip().lstrip(':') for p in spec.split(',')]
        rows, labels = [], []
        out['kind'] = 'line'
        for p in parts:
            m = re.match(r'^(-?)(\d+)(?:\s*[-–~]\s*(\d+))?$', p)
            s, e = int(m.group(2)), int(m.group(3) or m.group(2))
            labels.append(m.group(1) + m.group(2) + ('-' + m.group(3) if m.group(3) else ''))
            if e < s:
                return dict(out, ok=False, msg='줄 범위가 뒤집혔다: %s' % p)
            if rel is not None and self.kind == 'pr':
                want = '-' if m.group(1) else '+'
                got = [(new if want == '+' else old, t) for h in self.diff[rel]['hunks'] for sg, old, new, t in h['rows']
                       if (want == '+' and new and s <= new <= e) or (want == '-' and sg == '-' and s <= old <= e)]
                seen = {n for h in self.diff[rel]['hunks'] for sg, old, new, _ in h['rows'] for n in [new if want == '+' else old if sg == '-' else None]}
                if not got or any(n not in seen for n in range(s, e + 1)):
                    return dict(out, ok=False, msg='`%s`의 %s%d%s줄이 diff에 보이지 않는다(%s)' % (
                        rel, '지운 ' if want == '-' else 'PR 뒤 ', s, '-%d' % e if e != s else '', self._seen(rel)))
                rows += got
            else:
                if m.group(1):
                    return dict(out, ok=False, msg='`-줄`은 PR에서 지운 줄에만 쓴다: %s' % p)
                ls = self.lines(rel)
                if s < 1 or e > len(ls):
                    return dict(out, ok=False, msg='%s는 %d줄까지다: %s' % (rel or '원문', len(ls), p))
                rows += [(i, ls[i - 1]) for i in range(s, e + 1)]
        out['lines'], out['text'] = rows, '\n'.join(t for _, t in rows)
        out['label'] = '%s:%s' % (show or rel or 'raw', ', '.join(labels))
        out['file'], out['span'] = rel, (rows[0][0], rows[-1][0]) if rows else (0, 0)
        return out

    def _seen(self, rel):
        hs = self.diff[rel]['hunks']
        sp = []
        for h in hs[:4]:
            ns = [n for _, _, n, _ in h['rows'] if n]
            if ns:
                sp.append('%d-%d' % (ns[0], ns[-1]))
        return '보이는 줄 ' + ', '.join(sp) + ('…' if len(hs) > 4 else '') if sp else '보이는 줄 없음'

    def table(self, res):
        """근거가 표의 줄이면 그 표와 앞뒤 세 줄 (머리·설명)"""
        if res.get('kind') != 'line' or self.kind == 'pr' and res.get('file') or not res['lines'] or not res['lines'][0][1].lstrip().startswith('|'):
            return ''
        ls, (a, b) = self.lines(res['file']), res['span']
        ends = []
        for i, step in ((a - 1, -1), (b - 1, 1)):
            left = 3
            while 0 <= i < len(ls) and left:
                left -= bool(ls[i].strip()) and not ls[i].lstrip().startswith('|')
                i += step
            ends.append(i)
        return '\n'.join(ls[ends[0] + 1:ends[1]])

    def around(self, res, pad=8):
        """근거 구간 앞뒤 + 감싸는 정의 줄 (이름 지지 검사용)."""
        if res.get('kind') != 'line' or not res.get('lines'):
            return res.get('text', '')
        rel, (s, e) = res.get('file'), res['span']
        if rel is not None and self.kind == 'pr':
            rows = [(new or old or 0, t) for h in self.diff[rel]['hunks'] for _, old, new, t in h['rows']]
            return rel + '\n' + '\n'.join(t for n, t in rows if s - pad <= n <= e + pad)
        ls = self.lines(rel)
        body = '\n'.join(ls[max(0, s - 1 - pad):e + pad])
        if rel:
            body = rel + '\n' + body
            k0 = min(s - 1, len(ls) - 1)
            ind = len(ls[k0]) - len(ls[k0].lstrip()) if ls and ls[k0].strip() else 99
            got = 0
            for k in range(k0, max(-1, k0 - 600), -1):
                i = len(ls[k]) - len(ls[k].lstrip())
                if DEF.match(ls[k]) and (i < ind or k == k0):
                    body += '\n' + ' '.join(ls[k:k + 3])
                    ind, got = i, got + 1
                if got == 3 or (got and ind == 0):
                    break
        return body

    # ----- 숫자 · 이름 -----
    def allow_numbers(self, nums, lines=()):
        """pack이 센 값. 줄·글자 수(lines)는 `N줄`·`N자`(PR이면 +N·−N)라 쓸 때만 인정한다."""
        self._extra_numbers |= set(nums)
        self._line_numbers |= set(lines)

    def number_ok(self, forms, files=(), counted=False):
        if forms & self._extra_numbers or counted and forms & self._line_numbers:
            return True
        if self.kind in ('file', 'pr'):
            if self._numbers is None:
                self._numbers = T.number_set(self.text())
            return bool(forms & self._numbers)
        if self.kind == 'dir':
            if self._numbers is None:
                self._numbers = {}
            for f in files:
                if f not in self._numbers:
                    self._numbers[f] = T.number_set('\n'.join(self.lines(f)))
                if forms & self._numbers[f]:
                    return True
            return False
        return True

    def where(self, ok, files=()):
        """ok(줄)인 첫 줄의 이름표 ('' = 없음)"""
        for rel in [None] if self.kind in ('file', 'pr') else files:
            for i, ln in enumerate(self.lines(rel), 1):
                if ok(ln):
                    return '%s:%d' % (rel, i) if rel else '원문 %d줄' % i
        return ''

    def has_text(self, token, files=()):
        """원문에 글자 그대로 있는가 (공백 차이는 무시)."""
        if self.kind == 'none':
            return True
        if self.kind in ('file', 'pr'):
            return _has(self.text(), token)
        if token in self.files() or inside(self.path, token.strip('/')) and os.path.exists(os.path.join(self.path, token.strip('/'))):
            return True
        return any(_has('\n'.join(self.lines(f)), token) for f in files)

    def missing_tokens(self, tokens):
        """폴더 원문에서 어디에도 없는 낱말들 (파일을 한 번만 훑고 다 찾으면 멈춘다)."""
        left = {t: [w.encode('utf-8') for w in words_of(t)] for t in tokens}
        left = {t: ws for t, ws in left.items() if ws}
        need = set(w for ws in left.values() for w in ws)
        paths = ' '.join(self.files()).encode('utf-8')
        need = {w for w in need if w not in paths}
        for f in sorted(self.files(), key=lambda p: (not re.search(r'\.(rs|py|ts|tsx|js|go|md|toml|json|ya?ml)$', p), p)):
            if not need:
                break
            p = os.path.join(self.path, f)
            try:
                if os.path.getsize(p) > 3000000:
                    continue
                with open(p, 'rb') as fh:
                    b = fh.read()
            except OSError:
                continue
            need = {w for w in need if w not in b}
        return sorted(t for t, ws in left.items() if any(w in need for w in ws))


def seconds(t):
    n = 0
    for x in t.split(':'):
        n = n * 60 + int(x)
    return n


@functools.lru_cache(maxsize=4096)
def clock(s):
    """글에 나온 시각 (초)"""
    return {seconds(t) for t in re.findall(r'(?<![\d:])\d{1,3}:\d{2}(?::\d{2})?(?!\d)', s)}


def words_of(tok):
    """백틱 안에서 대조할 낱말 (코드 이름 · 4자 이상)."""
    return [w for w in re.findall(r'[A-Za-z_][A-Za-z0-9_]{3,}', tok)]


def _has(hay, tok):
    if tok in hay:
        return True
    squeeze = re.sub(r'\s+', '', tok)
    return len(squeeze) >= 4 and squeeze in _squeeze(hay)


@functools.lru_cache(maxsize=8)
def _squeeze(s):
    return re.sub(r'\s+', '', s)


def format_cites(labels, limit=6):
    """근거 글 목록 → 'a.rs:10-20, 33 · b.rs:3 · 외 2곳' (같은 파일은 묶는다. 글 번호는 '글 2-6, 14/15')."""
    groups, order = {}, []
    for lb in labels:
        m, post = re.match(r'^(.*):(-?\d[\d,\s\-–~]*)$', lb), re.match(r'^(\d+)(/\d+)$', lb)
        key, rng = (post.group(2), post.group(1)) if post else (m.group(1), m.group(2).strip()) if m and not lb.startswith('http') else (lb, '')
        if key not in groups:
            groups[key] = []
            order.append(key)
        for r in [x.strip() for x in rng.split(',') if x.strip()]:
            if r not in groups[key]:
                groups[key].append(r)
    def first(r):
        return int(re.match(r'-?\d+', r).group(0))
    def merged(rs):
        """겹치거나 이어진 범위를 합친다 (지운 줄 -n은 그대로)."""
        out = []
        for r in sorted((r for r in rs if not r.startswith('-')), key=first):
            m = re.match(r'(\d+)(?:\s*[-–~]\s*(\d+))?', r)
            s, e = int(m.group(1)), int(m.group(2) or m.group(1))
            if out and s <= out[-1][1] + 1:
                out[-1][1] = max(out[-1][1], e)
            else:
                out.append([s, e])
        return ['%d' % s if s == e else '%d-%d' % (s, e) for s, e in out] + [r for r in rs if r.startswith('-')]
    groups = {k: merged(v) for k, v in groups.items()}
    total = sum(max(1, len(v)) for v in groups.values())
    items, left = [], limit
    for k in order:
        if left <= 0:
            break
        take = groups[k][:left]
        items.append('글 ' + ', '.join(take) + k if k[:1] == '/' and take else '%s:%s' % (k, ', '.join(take)) if take else k)
        left -= max(1, len(take))
    items = [('원문 ' + i[4:] + '줄') if i.startswith('raw:') else i for i in items]
    return ' · '.join(items) + (' · 외 %d곳' % (total - limit) if total > limit else '')

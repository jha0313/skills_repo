#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""into 시험. `python3 tests/run_tests.py` (표준 라이브러리만, 네트워크 안 씀)."""
import contextlib
import io
import json
import os
import re
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
FIX = os.path.join(HERE, 'fixtures')
SRC = os.path.join(FIX, 'src')
os.environ['INTO_FORMATS'] = os.path.join(FIX, 'formats')
os.environ['INTO_DEBUG'] = ''
sys.dont_write_bytecode = True
sys.path[:0] = [os.path.join(SKILL, 'scripts'), HERE]
import into  # noqa: E402
from intolib import ASSETS, NOTICE, UserError, cells, cite, formats, lint, pack, quiz, route, script, textmodes  # noqa: E402
from intolib import model as M  # noqa: E402
from intolib import text as T  # noqa: E402


def read(p):
    with open(p, encoding='utf-8') as f:
        return f.read()


def write(p, s):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'w', encoding='utf-8') as f:
        f.write(s if isinstance(s, str) else json.dumps(s, ensure_ascii=False, indent=1))
    return p


def run(*args):
    """into.py 한 번 → (종료 코드, 표준 출력, 표준 오류)"""
    o, e = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(o), contextlib.redirect_stderr(e):
        code = into.main(list(args))
    return code, o.getvalue(), e.getvalue()


class Tmp(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.dir = self._t.name
        self.addCleanup(self._t.cleanup)

    def p(self, *a):
        return os.path.join(self.dir, *a)


# ---------- 유형 ----------
DIFF = 'diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1,1 +1,1 @@\n-x = 1\n+x = 2\n'
LONG = '설명 문장이다. ' * 30
KINDS = [
    ('https://github.com/a/b/pull/12', None, 'pr'),
    ('https://gitlab.com/a/b/-/merge_requests/3', None, 'pr'),
    ('https://github.com/a/b', None, 'codebase'),
    ('https://github.com/a/b/tree/main/src', None, 'codebase'),
    ('https://arxiv.org/abs/1706.03762', None, 'paper-concept'),
    ('https://example.com/x/paper.pdf', None, 'paper-concept'),
    ('https://www.youtube.com/watch?v=abc', None, 'video'),
    ('https://youtu.be/abc', None, 'video'),
    ('https://x.com/who/status/123', None, 'social-post'),
    ('https://news.ycombinator.com/item?id=1', None, 'community-post'),
    ('https://www.reddit.com/r/rust/comments/x/y', None, 'community-post'),
    ('https://www.rfc-editor.org/rfc/rfc9110', None, 'design-doc'),
    ('https://example.com/blog/post', None, 'general'),
    ('change.diff', DIFF, 'pr'),
    ('saved.md', '---\ntype: pr\nsource: https://github.com/a/b/pull/1\n---\n# t\n\n```diff\n' + DIFF + '```\n', 'pr'),
    ('rfc-12.md', '# RFC 12\n\nStatus: accepted\n\n## Goals\n\n' + LONG + '\n\n## Non-goals\n\nx\n\n## Alternatives considered\n\ny\n', 'design-doc'),
    ('paper.md', '# A study\n\n## Abstract\n\n' + LONG + '\n\n## 1. Introduction\n\nSmith et al. said.\n\n## 2. Methods\n\nbaseline and ablation\n\n## 3. Results\n\np < 0.05. doi 10.1234/abcd\n\n## References\n\nKim et al. 2020. Lee et al. 2021.\n', 'paper-concept'),
    ('talk.md', '# 영상 대본\n\n' + '\n'.join('[%02d:10] 말한다 %d' % (i, i) for i in range(9)) + '\n\n자막 출처는 YouTube 영상이다.\n', 'video'),
    ('a.srt', '1\n00:00:01,000 --> 00:00:02,000\n안녕\n', 'video'),
    ('thread.md', '---\nsource: https://x.com/a/status/1\n---\n# 글타래\n\n1/4 하나\n\n2/4 둘\n\n3/4 셋\n\n4/4 넷\n', 'social-post'),
    ('hn.md', '# Ask HN: why\n\n120 points\n\n## 댓글 1\n\n찬성\n\n## 댓글 2\n\n반대\n\n## 댓글 3\n\n모름\n\n48 comments\n', 'community-post'),
    ('tool.py', 'import os\n\ndef f():\n    return 1\n', 'local-file'),
    ('conf.toml', '[a]\nb = 1\n', 'local-file'),
    ('prompt.md', '# Role\n\nYou are an assistant.\n\n## Rules\n\n- 하나\n\n## Output format\n\nJSON\n', 'local-file'),
    ('SKILL.md', '---\nname: x\ndescription: y\n---\n# x\n', 'skill'),
    ('note.md', '# 캐시란\n\n' + LONG, 'general'),
    ('answer.md', '캐시는 앞에 두는 사본이다. 코드 예:\n\n```python\nimport os\ndef f():\n    pass\nclass A:\n    pass\n```\n\n' + LONG, 'general'),
]


class Route(Tmp):
    def kind(self, name, body):
        if body is None:
            return route.decide(route.score_url(name))
        meta, st = T.front_matter(body)
        return route.decide(route.score_text('\n'.join(body.split('\n')[st - 1:]), meta, name))

    def test_types(self):
        self.assertGreaterEqual(len(KINDS), 20)
        for name, body, want in KINDS:
            with self.subTest(name):
                d = self.kind(name, body)
                self.assertEqual(d['type'], want, d['rank'])
                self.assertFalse(d['tie'], d['rank'])

    def test_dirs(self):
        for i in range(25):
            write(self.p('repo', 'src', 'm%d.rs' % i), 'fn a() {}\n')
        write(self.p('repo', 'Cargo.toml'), '[package]\n')
        write(self.p('sk', 'SKILL.md'), '---\nname: s\ndescription: d\n---\n# s\n')
        write(self.p('small', 'a.py'), 'x = 1\n')
        for n, want in (('repo', 'codebase'), ('sk', 'skill'), ('small', 'local-file')):
            self.assertEqual(route.decide(route.score_dir(self.p(n), cite.list_files(self.p(n))))['type'], want)

    def test_tie(self):
        sc = {t: [] for t in route.TYPES}
        sc['pr'], sc['design-doc'] = [(6, 'a')], [(4, 'b')]
        self.assertTrue(route.decide(sc)['tie'])
        sc['design-doc'] = [(2, 'b')]
        self.assertFalse(route.decide(sc)['tie'])

    def test_tie_prints_two_and_type_wins(self):
        body = '---\nsource: https://github.com/a/b/pull/3\n---\n# RFC 3: x\n\nStatus: proposed\n\n## Goals\n\na\n\n## Alternatives\n\nb\n\nPR #3\n'
        f = write(self.p('mix.md'), body)
        code, out, _ = run('start', f, '--out', self.p('o'))
        self.assertEqual(code, 3, out)
        self.assertEqual(out.count('\n- `--type '), 2, out)
        code, out, _ = run('start', f, 'eli5', '--type', 'general', '--out', self.p('o'))
        self.assertEqual(code, 0)
        self.assertIn('# into · general × eli5', out)

    def test_modes(self):
        for w, want in (('ELI5', 'eli5'), ('쉽게 설명해줘', 'eli5'), ('눌러 보는 HTML로', 'interactive'), ('슬라이드로 시각화', 'slides'), ('한 장으로 그려줘', 'html'), ('퀴즈로', 'test'),
                        ('쇼츠로', 'shorts'), ('문서로', 'doc'), ('STE로', 'ste'), ('도메인 전문가가 되고 싶다', 'domain-expert'), ('visualize', 'html'), ('영상으로', 'video')):
            self.assertEqual(route.find_mode(w), want, w)
        self.assertIsNone(route.find_mode('아무말'))

    def test_public_and_slug(self):
        self.assertEqual(route.public_of({}, '', None)[0], False)
        self.assertFalse(route.public_of({'source': 'https://a.b'}, '', False)[0])
        self.assertEqual(route.make_slug('https://github.com/acme/tool/pull/7', ''), 'tool-pr7')
        self.assertTrue(re.match(r'^into-[0-9a-f]{6}$', route.make_slug('x', '한글 제목') if not route.slugify('x') else route.make_slug('한글', '한글 제목')))


# ---------- 글자 · 숫자 ----------
class Text(unittest.TestCase):
    def test_count(self):
        self.assertEqual(T.count('**굵게** `코드` [링크](http://a.b)'), len('굵게 코드 링크'))
        md = '**PR · 제목** — 한 줄\n\n```\n전  가 ─(나)▶ 다\n```\n\n빠진 디테일: 길고 긴 글\n근거: a.rs:1\n출처: 어디\n'
        self.assertEqual(T.count_result(md), T.count('제목') + T.count('한 줄') + T.count('전 가 (나) 다'))      # 머리 줄의 제목도, 줄마다
        self.assertEqual(T.count_result('# 제목\n\n```mermaid\nflowchart LR\n```\n\n글\n'), 1)

    def test_numbers(self):
        ok = T.number_set('요청 1,234개, 45 percent, 1.5 million, three retries, 세 번')
        for s in ('1234', '1,234', '45%', '150만', '3'):
            self.assertTrue(T.numbers(s)[0][1] & ok, s)
        self.assertFalse(T.numbers('1235')[0][1] & ok)

    def test_calc(self):
        self.assertEqual(T.calc_value('889+497'), 1386)
        self.assertAlmostEqual(T.calc_value('(90−45)÷45×100 = 100'), 100)
        self.assertIsNone(T.calc_value('가 + 나'))
        got = []
        M.check_numbers('합은 1,386(계산: 889+497)이다', lambda f: bool(f & {'889', '497'}), 'w', lambda *a: got.append(a))
        self.assertEqual(got, [])
        M.check_numbers('합은 1,400(계산: 889+497)이다', lambda f: bool(f & {'889', '497'}), 'w', lambda *a: got.append(a))
        self.assertEqual([g[0] for g in got], ['FAIL'])

    def test_secret(self):
        self.assertTrue([s for s in T.secrets('key = "sk-ant-api03-' + 'a1B2' * 10 + '"') if s[0] == '확실'])
        self.assertFalse([s for s in T.secrets('토큰은 `***`로 바꾼다') if s[0] == '확실'])


# ---------- 원문 ----------
class Source(Tmp):
    def setUp(self):
        super().setUp()
        self.pr = cite.Source('pr', os.path.join(SRC, 'pr.md'), ['raw', 'pr.md'])
        self.note = cite.Source('file', os.path.join(SRC, 'note.md'), ['raw', 'note.md'])

    def test_diff_lines(self):
        d = self.pr.diff
        self.assertEqual(list(d), ['src/cache.rs', 'docs/note.md', 'src/old.rs'])
        self.assertEqual((d['src/cache.rs']['add'], d['src/cache.rs']['del']), (3, 1))
        self.assertTrue(d['docs/note.md']['new'])
        for s, want in (('src/cache.rs:11', '// Wait until the first call.'), ('src/cache.rs:12', 'self.load_later(30);'), ('src/cache.rs:-11', 'self.load_now();'), ('src/cache.rs:42', 'let retries = 3;'),
                        ('cache.rs:41', 'let limit = 1234;'), ('src/old.rs:-5', 'let gone = true;'), ('src/old.rs:5', 'let kept = true;'), ('docs/note.md:1', 'Cached tools stay listed.')):
            r = self.pr.resolve(s)
            self.assertTrue(r['ok'], (s, r['msg']))
            self.assertEqual(r['text'].strip(), want, s)
        for bad in ('src/cache.rs:99', 'src/none.rs:1', 'src/cache.rs:-42', 'src/cache.rs:12-11'):
            self.assertFalse(self.pr.resolve(bad)['ok'], bad)
        self.assertIn('보이는 줄 10-15, 41-44', self.pr.resolve('src/cache.rs:99')['msg'])

    def test_raw(self):
        self.assertEqual(self.note.resolve('raw:3')['text'], '서버는 요청이 1,234개를 넘으면 캐시를 비운다.')
        for s in ('L3', '3', 'note.md:3', 'raw:3-4, 6', '캐시 안내'):
            self.assertTrue(self.note.resolve(s)['ok'], s)
        for s in ('raw:99', 'src/a.rs:3', '없는 글자'):
            self.assertFalse(self.note.resolve(s)['ok'], s)

    def test_time_and_post(self):
        f = write(self.p('v.md'), '[00:10] 처음\n[12:30] 나중\n\n1/3 하나\n2/3 둘\n')
        s = cite.Source('file', f, ['raw'])
        self.assertEqual(s.resolve('[12:30]')['warn'], '')
        self.assertTrue(s.resolve('[12:31]')['warn'])
        self.assertTrue(s.resolve('2/3')['ok'])
        self.assertFalse(s.resolve('5/3')['ok'])

    def test_dir(self):
        write(self.p('r', 'src', 'a.rs'), 'fn one() {\n    let limit = 77;\n}\n')
        s = cite.Source('dir', self.p('r'))
        self.assertTrue(s.resolve('src/a.rs:2')['ok'])
        self.assertFalse(s.resolve('src/a.rs:9')['ok'])
        self.assertFalse(s.resolve('요지')['ok'])
        self.assertTrue(s.number_ok({'77'}, ['src/a.rs']))
        self.assertFalse(s.number_ok({'78'}, ['src/a.rs']))
        self.assertEqual(s.missing_tokens(['limit', 'nope_name']), ['nope_name'])

    def test_cites(self):
        self.assertEqual(cite.format_cites(['a.rs:3-5', 'a.rs:4-8', 'a.rs:20', 'b.rs:1']), 'a.rs:3-8, 20 · b.rs:1')
        many = cite.format_cites(['a.rs:%d' % (i * 10) for i in range(1, 10)])
        self.assertTrue(many.endswith('외 3곳'), many)
        self.assertEqual(many.count(','), 5)
        self.assertEqual(cite.format_cites(['a.rs:-4', 'a.rs:9']), 'a.rs:9, -4')
        self.assertEqual(cite.format_cites(['14/15', '2/15', '3/15', '[12:30]']), '글 2-3, 14/15 · [12:30]')


# ---------- 크기 ----------
class Size(Tmp):
    def size(self, name, body, typ):
        f = write(self.p(name), body)
        run('start', f, '--type', typ, '--out', self.p('o'), '--slug', re.sub(r'\W', '', name), '--no-fetch')
        return json.loads(read(self.p('o', '.into', re.sub(r'\W', '', name), 'pack.json')))['size']

    def test_text(self):
        self.assertEqual(self.size('s.md', '가' * 1400, 'general'), '작음')
        self.assertEqual(self.size('m.md', '가' * 1600, 'general'), '보통')
        self.assertEqual(self.size('l.md', '가' * 20100, 'general'), '큼')

    def test_pr(self):
        def pr(files, lines):
            out = []
            for i in range(files):
                out.append('diff --git a/f%d.py b/f%d.py\n--- a/f%d.py\n+++ b/f%d.py\n@@ -1,0 +1,%d @@' % (i, i, i, i, lines) + ''.join('\n+x%d = 1' % k for k in range(lines)))
            return '# t\n\n```diff\n' + '\n'.join(out) + '\n```\n'
        self.assertEqual(self.size('p1.md', pr(1, 20), 'pr'), '작음')
        self.assertEqual(self.size('p2.md', pr(1, 60), 'pr'), '보통')
        self.assertEqual(self.size('p3.md', pr(16, 2), 'pr'), '큼')
        self.assertEqual(self.size('p4.md', pr(2, 600), 'pr'), '큼')

    def test_repo(self):
        for n, want in ((5, '보통'), (30, '큼')):
            for i in range(n):
                write(self.p('r%d' % n, 'src', 'm%d.py' % i), 'x = 1\n')
            run('start', self.p('r%d' % n), '--type', 'codebase', '--out', self.p('o'), '--slug', 'r%d' % n, '--no-fetch')
            self.assertEqual(json.loads(read(self.p('o', '.into', 'r%d' % n, 'pack.json')))['size'], want)


# ---------- start ----------
class Start(Tmp):
    def test_order(self):
        code, out, err = run('start', os.path.join(SRC, 'pr.md'), '쉽게', '--out', self.p('o'))
        self.assertEqual(code, 0, err)
        self.assertLessEqual(len(out), 4000)
        for s in ('# into · pr × eli5', '## 1. 읽는다', '## 2. W/model.json을 쓴다', '## 3. W/eli5.json을 쓴다', '`beforeafter', 'into.py check', 'into.py render', '비공개 —'):
            self.assertIn(s.strip('`'), out)
        w = self.p('o', '.into', 'pr')
        self.assertTrue({'pack.md', 'pack.json', 'source.md'} <= set(os.listdir(w)))
        self.assertEqual(read(self.p('o', '.into', '.gitignore')), '*\n')
        self.assertEqual(read(os.path.join(w, 'source.md')), read(os.path.join(SRC, 'pr.md')))
        self.assertIn('42', read(os.path.join(w, 'pack.md')))
        self.assertNotIn(os.path.expanduser('~') + '/', read(os.path.join(w, 'pack.md')))

    def test_again_keeps_model(self):
        a = ('start', os.path.join(SRC, 'note.md'), 'eli5', '--out', self.p('o'))
        run(*a)
        write(self.p('o', '.into', 'note', 'model.json'), {'type': 'general'})
        _, out, _ = run(*a)
        self.assertIn('이미 있다', out)
        self.assertEqual(os.listdir(self.p('o', '.into')).count('note-2'), 0)

    def test_same_name_other_source(self):
        f = write(self.p('x', 'note.md'), '# 다른 글\n\n본문이다.\n')
        run('start', os.path.join(SRC, 'note.md'), '--out', self.p('o'))
        run('start', f, '--out', self.p('o'))
        self.assertTrue(os.path.isdir(self.p('o', '.into', 'note-2')))

    def test_errors_one_line(self):
        for a in (('start', '없는파일.md'), ('start', 'eli5'), ('start', os.path.join(SRC, 'note.md'), '--type', 'zzz', '--out', self.p('o')), ('check', self.p('none')), ('lint', self.p('none.md'))):
            code, out, err = run(*a)
            self.assertEqual(code, 2, a)
            self.assertTrue(err.startswith('오류: '), err)
            self.assertEqual(err.strip().count('\n'), 0, err)

    def test_url_without_body(self):
        code, out, _ = run('start', 'https://example.com/blog/post', 'eli5', '--out', self.p('o'), '--no-fetch')
        self.assertEqual(code, 0)
        self.assertIn('본문이 없다', out)
        w = re.search(r'W = (\S+)', out).group(1)
        write(os.path.join(os.path.abspath(w), 'source.md'), '# 글\n\n본문 한 줄이다.\n')
        _, out, _ = run('start', 'https://example.com/blog/post', 'eli5', '--out', self.p('o'), '--no-fetch')
        self.assertIn('## 2. W/model.json을 쓴다', out)

    def test_every_mode_under_4000(self):
        for mode in ('brief', 'eli5', 'ste', 'html', 'interactive', 'doc', 'slides', 'test', 'shorts', 'video'):
            code, out, err = run('start', os.path.join(SRC, 'pr.md'), mode, '--out', self.p('o'))
            self.assertEqual(code, 0, err)
            self.assertLessEqual(len(out), 4000, mode)

    def test_domain(self):
        code, out, _ = run('start', '도메인 전문가', '물류')
        self.assertEqual(code, 0)
        self.assertIn('domain-expert', out)


# ---------- model · 칸 · 렌더 ----------
def pr_model():
    return {'type': 'pr', 'title': '캐시를 쓰면 늦게 켠다', 'source': 'PR 본문과 diff 전체', 'missing': '시험 이름',
            'facts': [{'id': 'f1', 't': '도구 목록이 캐시돼 있으면 서버가 첫 로드를 건너뛸 수 있다', 'src': ['raw:9'], 'if': '도구 목록이 캐시됨', 'hedge': 'may'},
                      {'id': 'f2', 't': '전에는 CLI가 시작할 때 서버를 켰다', 'src': ['raw:10']}],
            'nodes': [{'id': 'cli', 't': 'CLI'}, {'id': 'srv', 't': '서버'}],
            'edges': [{'id': 'e1', 'from': 'cli', 'to': 'srv', 't': '바로 켠다', 'when': 'before', 'src': ['src/cache.rs:-11']},
                      {'id': 'e2', 'from': 'cli', 'to': 'srv', 't': '첫 호출에 켠다', 'when': 'after', 'src': ['src/cache.rs:11-12'], 'main': True}],
            'steps': [{'who': 'CLI', 'do': '목록을 본다', 'src': ['src/cache.rs:11']}, {'who': 'CLI', 'do': '서버를 켠다', 'src': ['src/cache.rs:12'], 'to': '서버'}], 'order': 'call',
            'changes': [{'id': 'c1', 'what': '켜는 때', 'before': '시작', 'after': '첫 호출', 'src': ['src/cache.rs:12']}],
            'cases': [{'id': 'k1', 'input': '캐시 있음', 'before': '바로 켠다', 'after': '첫 호출에 켠다', 'src': ['src/cache.rs:11-12']}],
            'terms': [{'w': '늦게 켜기', 'o': ['load_later']}]}


def eli5():
    return {'one': {'t': '도구 목록이 캐시돼 있으면 서버를 첫 호출 때 켤 수 있다', 'f': ['f1']}, 'pic': [],
            'run': [{'t': 'CLI가 목록을 본다', 'f': ['steps1']}, {'t': '첫 호출에 서버를 켠다', 'f': ['steps2']}], 'catch': [{'t': '전에는 CLI가 시작할 때 켰다', 'f': ['f2']}]}


class Work(Tmp):
    src, typ = os.path.join(SRC, 'pr.md'), None

    def setUp(self):
        super().setUp()
        self.start(self.src, *(['--type', self.typ] if self.typ else []))

    def start(self, src, *a):
        code, out, err = run('start', src, '--out', self.p('o'), '--slug', 'w', *(['--public'] if src.endswith('pr.md') else []), *a)
        self.assertEqual(code, 0, out + err)
        self.w = self.p('o', '.into', 'w')

    def model(self, m):
        write(os.path.join(self.w, 'model.json'), m)
        return run('check', self.w)

    def render(self, mode, j):
        write(os.path.join(self.w, mode + '.json'), j)
        return run('render', self.w, mode)


class Model(Work):
    def test_ok(self):
        code, out, err = self.model(pr_model())
        self.assertEqual(code, 0, out + err)
        self.assertTrue(out.startswith('FAIL 0'), out)

    def bad(self, change, word, level='FAIL'):
        m = pr_model()
        change(m)
        code, out, err = self.model(m)
        self.assertTrue(any(word in ln and ln.startswith('- ' + level) for ln in out.split('\n')), '%s\n%s%s' % (word, out, err))
        return out

    def test_fails(self):
        self.bad(lambda m: m['facts'][0].pop('src'), '근거')
        self.bad(lambda m: m['facts'][0].update(src=['raw:999']), '줄까지다')
        self.bad(lambda m: m['facts'][0].update(src=['src/cache.rs:77']), 'diff에 보이지 않는다')
        self.bad(lambda m: m['facts'][0].update(t='서버가 5,678번 건너뛴다'), '숫자 5,678')
        self.bad(lambda m: m['facts'][0].update(t='`load_never`를 부른다'), '`load_never`가 원문에 없다')
        self.bad(lambda m: m['edges'][0].update(to='zzz'), 'nodes에 없다')
        self.bad(lambda m: m['edges'][0].update(t=''), '라벨')
        self.bad(lambda m: m['facts'][1].update(id='f1'), '두 번')
        self.bad(lambda m: m['facts'][0].update(mark='아마'), '표시')
        self.bad(lambda m: m.update(changes=m['changes'] * 5), '4개까지다')
        self.bad(lambda m: m.update(title=''), '제목')
        self.bad(lambda m: m['facts'][1].update(t='토큰은 sk-ant-api03-' + 'a1B2' * 10), '비밀 값')

    def test_warns(self):
        self.bad(lambda m: m.update(zones=[]), '표에 없는 키', 'WARN')
        self.bad(lambda m: (m['facts'][0].pop('if'), m['facts'][0].pop('hedge'), m['facts'][0].update(t='서버가 첫 로드를 건너뛴다')), '조건어', 'WARN')
        self.bad(lambda m: m['facts'][0].update(t='서버가 항상 첫 로드를 건너뛴다'), '항상', 'WARN')

    def test_good_numbers(self):
        m = pr_model()
        m['facts'][1]['t'] = '한도는 1234이고 다시 하기는 3번, 합은 1,237(계산: 1234+3)이다. `retries`를 본다'
        m['facts'][1]['src'] = ['src/cache.rs:41-42']
        code, out, _ = self.model(m)
        self.assertEqual(code, 0, out)

    def test_json_error_line(self):
        write(os.path.join(self.w, 'model.json'), '{"type":"pr",\n "title": }')
        code, _, err = run('check', self.w)
        self.assertEqual(code, 2)
        self.assertIn('model.json:2', err)

    def test_supplement_needs_no_source(self):
        m = pr_model()
        m['facts'].append({'id': 'f9', 't': '보충 설명 4567', 'mark': '보충', 'src': ['일반 지식']})
        code, out, _ = self.model(m)
        self.assertEqual(code, 0, out)


class Render(Work):
    def setUp(self):
        super().setUp()
        self.assertEqual(self.model(pr_model())[0], 0)

    def test_eli5_shape(self):
        code, out, err = self.render('eli5', eli5())
        self.assertEqual(code, 0, out + err)
        want = ('**PR · 캐시를 쓰면 늦게 켠다** — 도구 목록이 캐시돼 있으면 서버를 첫 호출 때 켤 수 있다\n\n'
                '```\n전  CLI ─(바로 켠다)▶ 서버\n후  CLI ─(첫 호출에 켠다)▶ 서버\n```\n\n'
                '**어떻게**\n1. CLI가 목록을 본다\n2. 첫 호출에 서버를 켠다\n\n'
                '**조심** 전에는 CLI가 시작할 때 켰다\n\n'
                '빠진 디테일: 시험 이름. 빈 칸: 왜, 규모\n'
                '근거: pr.md:9-10 · src/cache.rs:11-12, -11\n'
                '출처: PR 본문과 diff 전체 · https://github.com/acme/tool/pull/7\n')
        self.assertEqual(out, want)
        self.assertEqual(read(os.path.join(self.w, 'eli5.md')), want)

    def fail(self, change, word, mode='eli5'):
        j = eli5()
        change(j)
        code, out, err = self.render(mode, j)
        self.assertEqual(code, 1, out)
        self.assertTrue(any(word in ln and ln.startswith('- FAIL') for ln in out.split('\n')), '%s\n%s' % (word, out))

    def test_cell_fails(self):
        self.fail(lambda j: j.update(one=''), '필수 칸')
        self.fail(lambda j: j.update(one={'t': '가' * 64, 'f': ['f1']}), '64자다. 60자까지다')
        self.fail(lambda j: j.update(run=[{'t': 'ㄱ%d 단계' % i, 'f': ['f1']} for i in range(4)]), '4개다. 3개까지다')
        self.fail(lambda j: j.update(one={'t': '서버', 'f': ['zzz']}), 'model.json에 없다')
        self.fail(lambda j: j.update(pic=['nope']), 'model.json의 edges에 없다')
        self.fail(lambda j: j.update(one={'t': '요청 9,999개를 건너뛴다', 'f': ['f1']}), '9,999')
        self.fail(lambda j: j.update(one={'t': '`not_here`를 부른다', 'f': ['f1']}), '`not_here`')

    def test_number_in_pack_ok(self):
        code, out, err = self.render('eli5', dict(eli5(), size='파일 3개, +4 −2'))
        self.assertEqual(code, 0, out + err)
        self.assertIn('**규모** 파일 3개, +4 −2', out)

    def test_condition_warn(self):
        _, out, err = self.render('eli5', dict(eli5(), one={'t': '서버를 첫 호출 때 켠다', 'f': ['f1']}))
        self.assertIn('한정어', err)
        self.assertIn('조건', err)

    def test_optional_cell_not_named(self):
        _, out, _ = self.render('eli5', eli5())
        self.assertNotIn('상황', re.search(r'빠진 디테일:.*', out).group(0))

    def test_no_length_over(self):
        m = pr_model()
        m['facts'] += [{'id': 'g%d' % i, 't': '도구 이야기 %s' % w, 'src': ['raw:9']} for i, w in enumerate('가나다라마바사')]
        self.model(m)
        j = dict(eli5(), why={'t': '각' * 79, 'f': ['f2']}, run=[{'t': c * 84, 'f': ['f2']} for c in '간난단'], catch=[{'t': c * 74, 'f': ['f2']} for c in '랄말발'])
        code, out, _ = self.render('eli5', j)
        self.assertEqual(code, 1)
        self.assertIn('450자까지다', out)

    def test_ste(self):
        code, out, err = self.render('ste', {'one': {'t': '도구 목록이 캐시돼 있으면 서버는 첫 로드를 건너뛸 수 있다.', 'f': ['f1']}})
        self.assertEqual(code, 0, out + err)
        self.assertIn('\n용어: 늦게 켜기 = load_later\n', out)
        self.assertIn('| 입력 | 전 | 후 |', out)
        self.assertIn('| 캐시 있음 | 바로 켠다 | 첫 호출에 켠다 |', out)

    def test_doc(self):
        code, out, err = self.render('doc', {'one': [{'t': '캐시돼 있으면 늦게 켤 수 있다', 'f': ['f1']}], 'steps': [{'t': 'CLI가 목록을 본다', 'f': ['steps1']}]})
        self.assertEqual(code, 0, out + err)
        md = read(self.p('o', 'w-doc.md'))
        self.assertEqual(re.findall(r'(?m)^## (.+)$', md), ['TL;DR', 'High-level design', 'Low-level design'])
        self.assertIn('flowchart LR', md)
        self.assertIn('sequenceDiagram', md)
        self.assertIn('p1->>p2: 서버를 켠다', md)
        self.assertIn('Note over p1: 목록을 본다', md)
        self.assertIn('왜 중요한가', re.search(r'빠진 디테일:.*', md).group(0))
        self.assertEqual(run('lint', self.p('o', 'w-doc.md'), '--type', 'pr', '--mode', 'doc', '--source', self.src, '--size', '작음')[0], 0)

    def test_brief_from_common(self):
        code, out, err = self.render('brief', {'one': {'t': '캐시돼 있으면 서버를 늦게 켤 수 있다', 'f': ['f1']}})
        self.assertEqual(code, 0, out + err)
        self.assertIn('CLI ─(첫 호출에 켠다)▶ 서버', out)

    def test_overwrite_only_ours(self):
        j = {'one': [{'t': '캐시돼 있으면 늦게 켤 수 있다', 'f': ['f1']}]}
        self.render('doc', j)
        self.render('doc', j)
        self.assertFalse(os.path.exists(self.p('o', 'w-doc-2.md')))
        write(self.p('o', 'w-doc.md'), '사람이 고친 글\n')
        _, out, _ = self.render('doc', j)
        self.assertIn('w-doc-2.md', out)
        self.assertEqual(read(self.p('o', 'w-doc.md')), '사람이 고친 글\n')

    def test_model_fail_stops(self):
        m = pr_model()
        m['facts'][0]['src'] = ['raw:999']
        self.model(m)
        code, out, _ = self.render('eli5', eli5())
        self.assertEqual(code, 1)
        self.assertIn('결과를 쓰지 않았다', out)

    def test_marks_follow(self):
        m = pr_model()
        m['facts'][1]['mark'] = '추정'
        m['edges'][1]['guess'] = True
        self.model(m)
        _, out, _ = self.render('eli5', eli5())
        self.assertIn('전에는 CLI가 시작할 때 켰다 (추정)', out)
        self.assertIn('첫 호출에 켠다 (추정)', out)

    def test_html_without_renderer(self):
        code, out, err = self.render('html', {'one': {'t': '캐시돼 있으면 늦게 켤 수 있다', 'f': ['f1']}})
        if os.path.exists(os.path.join(SKILL, 'scripts', 'intolib', 'htmlmodes.py')):
            self.assertEqual(code, 0, out + err)
        else:
            self.assertEqual(code, 2)
            self.assertIn('html 렌더러가 없다', err)


class Private(Work):
    src, typ = os.path.join(SRC, 'note.md'), 'general'

    def gm(self):
        return {'type': 'general', 'title': '캐시 안내', 'source': '글 전체',
                'facts': [{'id': 'f1', 't': '요청이 1,234개를 넘으면 서버가 캐시를 비운다', 'src': ['raw:3'], 'if': '1,234개를 넘음'}, {'id': 'f2', 't': '사용자는 `cache_limit`을 바꿀 수 있다', 'src': ['raw:5'], 'hedge': '바꿀 수 있다'}],
                'nodes': [{'id': 'c', 't': 'CLI'}, {'id': 's', 't': '서버'}], 'edges': [{'id': 'e1', 'from': 'c', 'to': 's', 't': '목록을 묻는다', 'src': ['raw:7']}, {'id': 'e2', 'from': 's', 'to': 'c', 't': '목록을 돌려준다', 'src': ['raw:7']}]}

    def test_notice_and_forms(self):
        self.assertEqual(self.model(self.gm())[0], 0)
        j = {'one': {'t': '요청이 1234개를 넘으면 캐시를 비운다', 'f': ['f1']}, 'say': {'t': '캐시는 약속이 아니라 어림이다.', 'f': ['f1']}, 'num': {'v': '1,234', 'unit': '개', 'of': '를 넘는 요청', 'f': ['f1']},
             'catch': [{'t': '사용자가 `cache_limit`을 바꿀 수 있다', 'f': ['f2']}, '빈 근거'], 'like': '냉장고 같다', 'ask': [{'q': '언제 비우나', 'a': '1,234개를 넘을 때'}]}
        code, out, err = self.render('eli5', j)
        self.assertEqual(code, 0, out + err)
        self.assertTrue(out.startswith(NOTICE + '\n\n**일반 글 · 캐시 안내**'), out)
        for s in ('CLI ─(목록을 묻는다)▶ 서버\n서버 ─(목록을 돌려준다)▶ CLI\n', '**원문** “캐시는 약속이 아니라 어림이다.”', '**빗대면** 냉장고 같다', '**확인** Q. 언제 비우나 → A. 1,234개를 넘을 때'):
            self.assertIn(s, out)
        nolink = re.search(r'근거\(`f`\) 없는 칸: (.*?) —', err).group(1)
        self.assertEqual(nolink, 'catch[2]')          # like(~)와 ask(qa)는 근거 없이 된다
        j['say'] = {'t': '캐시는 약속이다.', 'f': ['f1']}
        code, out, _ = self.render('eli5', j)
        self.assertEqual(code, 1)
        self.assertIn('원문과 글자가 다르다', out)

    def test_public_flag(self):
        self.start(self.src, '--type', 'general', '--public')
        self.model(self.gm())
        _, out, _ = self.render('eli5', {'one': {'t': '요청이 1234개를 넘으면 캐시를 비운다', 'f': ['f1']}})
        self.assertNotIn(NOTICE, out)

    def test_order_note(self):
        m = dict(self.gm(), steps=[{'who': '서버', 'do': '비운다', 'src': ['raw:3']}])
        self.model(m)
        _, out, _ = self.render('eli5', {'one': {'t': '요청이 1234개를 넘으면 캐시를 비운다', 'f': ['f1']}, 'run': [{'t': '서버가 비운다', 'f': ['steps1']}, {'t': '캐시가 빈다', 'f': ['f1']}]})
        self.assertIn('순서: 원문에 없음', out)


class Pics(unittest.TestCase):
    """그림 형을 글로 (lanes · positions · ladder · chart · options · auto 표)."""

    def ctx(self, typ, model, raw, mode='eli5'):
        m = M.normalize(model)
        sp = formats.load(typ)
        rows = sp.rows(mode)
        src = cite.Source('none', '', [])
        chk = cells.Checker(mode, rows, m, raw, src, {}, sp).run()
        return chk, cells.context(chk, typ, '보통', {'public': True}, 'raw')

    def test_lanes(self):
        m = {'title': 't', 'source': 's', 'lanes': ['사람', '에이전트'], 'order': 'time', 'facts': [],
             'steps': [{'id': 's1', 'lane': '사람', 'do': '부른다', 'out': '요청', 'src': ['a']}, {'id': 's2', 'lane': '에이전트', 'do': '읽는다', 'src': ['a']}]}
        chk, ctx = self.ctx('skill', m, {'one': '한 줄'})
        out = textmodes.render('eli5', ctx)
        self.assertIn('```\n사람      부른다 ─(요청)▶ 에이전트\n에이전트  읽는다\n```', out)

    def test_auto_table_blank(self):
        m = {'title': 't', 'source': 's', 'facts': [], 'lanes': ['a'], 'steps': [], 'triggers': [{'say': '해줘', 'route': '', 'src': ['a']}]}
        chk, _ = self.ctx('skill', m, {'one': '한 줄'})
        self.assertEqual(chk.cells['triggers'][0]['cells'], ['해줘', '—'])

    def test_positions(self):
        m = {'title': 't', 'source': 's', 'facts': [], 'positions': [{'id': 'p1', 't': '찬성', 'n': 3, 'why': '빠르다', 'ev': '경험', 'src': ['a']}, {'id': 'p2', 't': '반대', 'src': ['a']}]}
        _, ctx = self.ctx('community-post', m, {'one': '한 줄'})
        out = textmodes.render('eli5', ctx)
        self.assertIn('- [경험] 찬성(3) — 빠르다\n- 반대', out)
        self.assertNotIn('합의', out)              # `?` 칸은 비어도 이름을 적지 않는다

    def test_false_turns_off(self):
        m = {'title': 't', 'source': 's', 'facts': [], 'lanes': ['a'], 'steps': [{'id': 's1', 'lane': 'a', 'do': '한다', 'src': ['a']}], 'triggers': [{'say': '해줘', 'route': '한다', 'src': ['a']}]}
        chk, ctx = self.ctx('skill', m, {'one': '한 줄', 'triggers': False})
        self.assertNotIn('triggers', chk.cells)
        self.assertNotIn('언제', ctx['missing'])
        chk, _ = self.ctx('skill', m, {'one': '한 줄', 'pic': False})
        self.assertIn('FAIL', [i.level for i in chk.issues])          # 필수 칸은 뺄 수 없다

    def block(self, form, v, model=None, mode='eli5'):
        return textmodes.pic_block({'model': model or {}, 'order_note': '', 'refs': {}, 'mode': mode}, {'form': form, 'label': '칸', 'key': 'pic'}, v)

    def test_ladder_keeps_order(self):
        self.assertEqual(self.block('ladder', [{'t': '약한 것', 'ev': '의견'}, {'t': '센 것', 'ev': '실험'}])[1:], ['- [의견] 약한 것', '- [실험] 센 것'])

    def test_chart_pivot(self):
        v = [{'group': g, 'label': lb, 'value': n, 'base': 'A'} for g, lb, n in (('A', '수', 1), ('A', '시간', 2), ('B', '수', 3), ('B', '시간', 4))]
        self.assertEqual(self.block('chart', v)[2:], ['| 조건 | 수 | 시간 |', '|---|---|---|', '| A (기준) | 1 | 2 |', '| B | 3 | 4 |'])
        self.assertIn('| B | 3 | 4 |', self.block('chart', [dict(x, group=['A'] if x['group'] == 'A' else 'B') for x in v]))      # 배열을 써도 예외가 새지 않는다

    def test_options(self):
        m = {'criteria': [{'id': 'c1', 't': '값'}], 'cells': [{'o': 'o1', 'c': 'c1', 'sign': '+', 't': '싸다'}]}
        out = self.block('options', [{'id': 'o1', 't': '가', 'chosen': True}, {'id': 'o2', 't': '나'}], m, 'doc')
        self.assertEqual(out[-2:], ['| ✓ 가 | ＋ 싸다 |', '| 나 |  |'])

    def test_mermaid_safe(self):
        m = {'nodes': [{'id': 'a', 't': 'end "x" <b>'}, {'id': 'b', 't': '`f()` #1'}]}
        out = '\n'.join(textmodes.flowchart(m, [{'from': 'a', 'to': 'b', 't': 'a|b; "c" 100%% {x}'}]))
        self.assertNotIn('"x"', out)
        self.assertIn('#quot;x#quot;', out)
        self.assertIn('#35;1', out)
        self.assertNotIn('`f', out)
        self.assertNotIn('%%', out)
        self.assertEqual(re.findall(r'(?m)^  (n\d)\["', out), ['n1', 'n2'])
        self.assertEqual(textmodes.mm_seq('end'), '(end)')
        self.assertNotIn(';', textmodes.mm_seq('a; b # c -->> "d"'))
        self.assertIn('!a && b || c', textmodes.mm_seq('!a && b || c'))


# ---------- formats ----------
class Formats(Tmp):
    def issues(self, change, stem='pr'):
        p = write(self.p(stem + '.md'), change(read(os.path.join(FIX, 'formats', 'pr.md'))))
        return [str(i) for i in formats.validate(p)]

    def test_good(self):
        self.assertEqual(self.issues(lambda s: s), [])

    def test_bad(self):
        for a, b, word in (('# pr — PR', '# PR', '첫 줄'), ('- 질문: 전과 후 · 왜 · 조심', '- 질문: 하나 · 둘', '질문이 2개다'), ('- 그림: beforeafter', '', '그림'), ('## ste', '## st', '`## ste` 절이 없다'),
                           ('| one | 한 줄 | one | line | 60! |', '| zero | 한 줄 | one | line | 60! |', '자리 `zero`'), ('| line | 60! |', '| lien | 60! |', '형 `lien`'), ('| line | 60! |', '| line | 육십 |', '한도 `육십`'),
                           ('| line | 60! |', '| line | 60!? |', '한도 `60!?`'), ('| steps | 3×85 |', '| steps | 3 |', '개수×글자 수'), ('| why | 왜 | why | line | 80 | 이유 |', '| why | 왜 | one | line | 80 | 이유 |', '두 번 나온다'),
                           ('table:입력,전,후', 'table:', '열 이름'), ('| 자리 | 칸 | 키 | 형 | 한도 | 쓸 것 |', '| 자리 | 칸 | 키 | 형 | 쓸 것 |', '열이 다르다'), ('| 1–4 |', '| 많이 |', '개수 `많이`'), ('| choice |', '| ox |', 'choice 또는 predict')):
            got = self.issues(lambda s: s.replace(a, b, 1))
            self.assertTrue(any(word in x and x.startswith('FAIL') for x in got), (a, b, got))
        got = self.issues(lambda s: s, 'other')
        self.assertTrue(any('파일 이름' in x for x in got))

    def test_row_order(self):
        got = self.issues(lambda s: s.replace('| one | 한 줄 | one | line | 60! | 요지 |\n| why | 왜 | why | line | 80 | 이유 |', '| why | 왜 | why | line | 80 | 이유 |\n| one | 한 줄 | one | line | 60! | 요지 |', 1))
        self.assertTrue(any('자리 순서' in x for x in got), got)

    def test_limits(self):
        for s, n, c, req, opt, free in (('60!', 60, None, 1, 0, 0), ('5×70', 5, 70, 0, 0, 0), ('4?', 4, None, 0, 1, 0), ('60!~', 60, None, 1, 0, 1), ('3×60?', 3, 60, 0, 1, 0), ('', None, None, 0, 0, 0), ('1,000', 1000, None, 0, 0, 0)):
            d = formats.parse_limit(s)
            self.assertEqual((d['n'], d['chars'], d['required'], d['optional'], d['free']), (n, c, bool(req), bool(opt), bool(free)), s)
        for s in ('60!?', '×70', '많이', '60!!'):
            self.assertIsNone(formats.parse_limit(s), s)

    def test_length_override(self):
        self.assertEqual(formats.length_limit('pr', 'eli5', '작음'), 450)
        write(self.p('f', '_common.md'), read(os.path.join(FIX, 'formats', '_common.md')))
        write(self.p('f', 'pr.md'), read(os.path.join(FIX, 'formats', 'pr.md')).replace('## eli5\n', '## eli5\n- 길이: 400/600/800\n\n'))
        old = os.environ['INTO_FORMATS']
        os.environ['INTO_FORMATS'] = self.p('f')
        try:
            self.assertEqual(formats.length_limit('pr', 'eli5', '큼'), 800)
            self.assertEqual(run('formats', '--validate')[0], 0)
        finally:
            os.environ['INTO_FORMATS'] = old

    def test_cli(self):
        code, out, _ = run('formats', '--validate')
        self.assertEqual(code, 0, out)
        code, out, _ = run('types')
        self.assertIn('| pr | PR | beforeafter |', out)

    def test_real_formats(self):
        old = os.environ.pop('INTO_FORMATS')
        try:
            n, issues = formats.validate_all()
        finally:
            os.environ['INTO_FORMATS'] = old
        self.assertEqual([str(i) for i in issues if i.level == 'FAIL'], [])


class Examples(unittest.TestCase):
    def test_real_examples_look_like_output(self):
        """formats/*.md의 `## 예`를 되읽어 다시 그리면 같은 글이다."""
        import examples
        old = os.environ.pop('INTO_FORMATS')
        try:
            for sp in formats.all_types():
                if '예' not in sp.sections:
                    continue
                with self.subTest(sp.stem):
                    ex = examples.example(sp)
                    r = examples.Reader(sp, ex)
                    self.assertEqual(r.render(), ex)
                    self.assertEqual(r.over(), [])
                    self.assertLessEqual(T.count_result(ex), formats.length_limit(sp.stem, 'eli5', '큼'))
        finally:
            os.environ['INTO_FORMATS'] = old


# ---------- ste ----------
STE_GOOD = ['서버가 캐시를 비운다.', '도구 목록이 있으면 CLI는 서버를 켜지 않는다.', '사용자는 `cache_limit`을 바꿀 수 있다.', '이 PR은 파일 네 개를 바꾼다.', '하지만 서버는 목록을 남긴다.',
            '보고서는 결과 세 개를 적는다.', '에이전트는 문서에서 이름을 찾는다.', '행위자가 없으면 원문은 값을 정하지 않는다.', '결과가 저장된다 (행위자: 원문에 없음).', 'If the cache exists, the CLI waits.']
STE_BAD = [('서버가 캐시를 비우고 목록을 다시 읽는다.', '이어 쓴 문장'), ('CLI가 목록을 보며 서버를 켠다.', '이어 쓴 문장'), ('값이 크지만 서버는 기다린다.', '이어 쓴 문장'), ('목록이 저장된다.', '피동'), ('서버가 닫힌다.', '피동'),
           ('이것은 값을 바꾼다.', '지시어'), ('전자는 값을 바꾼다.', '지시어'), ('서버는 기다린다, 목록이 있을 때.', '조건 위치'), ('가' * 61 + '다.', '길이'),
           ('The server starts the tool process and then it waits for the next call from the client that the user opened on the second machine in the room today again.', '길이')]


class Ste(unittest.TestCase):
    def test_good(self):
        self.assertGreaterEqual(len(STE_GOOD), 10)
        for s in STE_GOOD:
            self.assertEqual(lint.ste(s), [], s)

    def test_bad(self):
        self.assertGreaterEqual(len(STE_BAD), 10)
        for s, rule in STE_BAD:
            self.assertIn(rule, [r for r, _, _ in lint.ste(s)], s)

    def test_whole(self):
        self.assertIn('문체', [r for r, _, _ in lint.ste('서버가 켠다.\n\n서버가 켭니다.')])
        self.assertIn('번호', [r for r, _, _ in lint.ste('먼저 서버가 켠다.\n그다음 CLI가 묻는다.')])
        self.assertIn('용어', [r for r, _, _ in lint.ste('용어: 늦게 켜기 = lazy startup\n\n서버가 lazy startup을 쓴다.')])
        self.assertEqual(lint.ste('```\n이것은 저장된다\n```\n\n| 이 | 열 |\n|---|---|\n\n근거: 이것은 저장된다'), [])


# ---------- test · shorts · video ----------
def quiz_json():
    q = []
    for i, (s, t) in enumerate((('one', 'choice'), ('why', 'predict'), ('pic', 'choice'), ('run', 'predict'), ('catch', 'choice'))):
        if t == 'choice':
            q.append({'slot': s, 'type': t, 'q': '%s에서 서버는 무엇을 하나?' % '가나다라마'[i], 'right': '첫 호출에 켠다', 'wrong': ['시작할 때 바로 켠다', '아예 켜지 않는다고 한다'], 'explain': '첫 호출까지 기다린다', 'f': ['f1']})
        else:
            q.append({'slot': s, 'type': t, 'q': '%s에서 무엇이 달라지나?' % '가나다라마'[i], 'model': '켜는 때가 늦어진다', 'must': ['켜는 때가 늦어짐'], 'f': ['f2']})
    return {'questions': q}


class Quiz(Work):
    def setUp(self):
        super().setUp()
        self.model(pr_model())

    def test_ok(self):
        code, out, err = self.render('test', quiz_json())
        self.assertEqual(code, 0, out + err)
        page = read(self.p('o', 'w-test.html'))
        q = json.loads(re.search(r'const QUIZ = (\{.*?\n\});', page, re.S).group(1))
        self.assertEqual(len(q['questions']), 5)
        for x, y in zip(q['questions'], quiz_json()['questions']):
            if x['type'] == 'choice':
                self.assertEqual(x['options'][x['answer']], y['right'])
            self.assertIn('pr.md:', x['source'])
        strip = lambda s: re.sub(r'const QUIZ = \{.*?\n\};', '', s, flags=re.S)
        self.assertEqual(strip(page), strip(read(os.path.join(ASSETS, 'test.html'))))        # 동작 코드는 그대로

    def test_positions(self):
        for slug in ('a', 'b', 'pr03', '한글', 'x' * 30):
            for n in (3, 5, 8, 10):
                pos = quiz.positions(slug, [3 + i % 2 for i in range(n)])
                self.assertEqual(pos, quiz.positions(slug, [3 + i % 2 for i in range(n)]))
                self.assertLessEqual(max(pos.count(p) for p in pos), max(1, n // 2))
                self.assertFalse(any(pos[i] == pos[i + 1] == pos[i + 2] for i in range(n - 2)))

    def bad(self, change, word, level='FAIL'):
        j = quiz_json()
        change(j['questions'])
        _, out, err = self.render('test', j)
        self.assertTrue(any(word in ln and ('- ' + level) in ln for ln in (out + err).split('\n')), (word, out, err))

    def test_fails(self):
        self.bad(lambda q: q.pop(), '5~10개')
        self.bad(lambda q: q[1].update(type='choice', right='첫 호출에 켠다', wrong=['가나다라마바사', '나나다라마바사'], explain='x'), 'predict가 1개다')
        self.bad(lambda q: q[0].update(right='아주 길게 쓴 정답이라서 누구나 이것이 정답이라고 안다'), '길어서 보인다')
        self.bad(lambda q: q[0].update(right='켬', wrong=['시작할 때 언제나 바로 켠다고 한다', '아예 켜지 않는다고 적혀 있다']), '짧아서 보인다')
        self.bad(lambda q: q[0].update(explain='B와 C는 원문에 없다'), '보기를 글자')
        self.bad(lambda q: q[0].update(f=[]), '근거')
        self.bad(lambda q: [x.update(wrong=['바로 켠다고', '켜지 않는다']) for x in q if x['type'] == 'choice'], '가장 긴 문항')
        self.bad(lambda q: q[3].update(must=['첫 호출까지 기다린다'], model='첫 호출까지 기다린다'), '앞 문항', 'WARN')


def scenes():
    return [{'slot': 'hook', 'say': '이 서버는 언제 켜질까요?', 'title': '언제', 'caption': '언제 켜나', 'visual': 'CLI와 서버', 'f': ['f1']},
            {'slot': 'one', 'say': '목록이 캐시돼 있으면 첫 호출 때 켤 수 있습니다.', 'title': '첫 호출', 'caption': '첫 호출 때', 'visual': 'CLI → 서버', 'f': ['f1']},
            {'slot': 'pic', 'say': '전에는 시작할 때 켰습니다.', 'title': '전', 'caption': '시작할 때', 'visual': '전 → 후', 'f': ['f2']}]


class Script(Work):
    def setUp(self):
        super().setUp()
        self.model(pr_model())

    def test_shorts(self):
        code, out, err = self.render('shorts', {'scenes': scenes(), 'answer': 2, 'check': '언제 켜나 → 첫 호출'})
        self.assertEqual(code, 0, out + err)
        md = read(self.p('o', 'w-shorts.md'))
        self.assertIn('쇼츠 (', md)
        self.assertIn('훅의 답: 장면 2', md)
        self.assertEqual(run('lint', self.p('o', 'w-shorts.md'), '--type', 'pr', '--mode', 'shorts')[0], 0)

    def bad(self, j, word, level='FAIL', mode='shorts'):
        _, out, err = self.render(mode, dict({'answer': 2, 'check': 'a → b'}, **j))
        self.assertTrue(any(word in ln and ('- ' + level) in ln for ln in (out + err).split('\n')), (word, out, err))

    def test_fails(self):
        s = scenes()
        self.bad({'scenes': s, 'answer': None}, '`answer`')
        self.bad({'scenes': s[1:]}, '첫 장면은 hook')
        self.bad({'scenes': [s[0], s[1], dict(s[2], visual='html 모드와 같은 그림')]}, '대본 밖')
        self.bad({'scenes': [s[0], dict(s[1], sec=1), s[2]]}, '초당')
        self.bad({'scenes': [s[0], s[1]] + [dict(s[2], say='전에는 시작할 때 켰습니다. ' * 5)] * 5}, '60초까지다')
        self.bad({'scenes': [s[0], s[2], s[1]]}, '칸 순서')
        self.bad({'scenes': [s[0], dict(s[1], caption='자막이 너무 길어서 안전 영역 두 줄을 훌쩍 넘어 버린다')] + s[2:]}, '자막', 'WARN')

    def test_seconds(self):
        self.assertEqual(script.syllables('가나다')[0], 3)
        self.assertGreater(script.syllables('1,234')[0], 4)
        n, p, sec, _ = script.scene_seconds('가' * 55 + '.', True)
        self.assertEqual((n, p, sec), (55, 0.0, 10.0))
        self.assertEqual(script.scene_seconds('가' * 11 + '?')[1], 1.0)
        self.assertEqual(script.scene_seconds('가')[2], 2.0)

    def test_video(self):
        s = [dict(x, chapter='첫 장') for x in scenes()]
        code, out, err = self.render('video', {'scenes': s, 'answer': 2, 'check': 'a → b', 'minutes': 0.2})
        self.assertEqual(code, 0, out + err)
        self.assertIn('## 첫 장 (0:00–', read(self.p('o', 'w-video.md')))
        self.bad({'scenes': scenes()}, '`chapter`', mode='video')


# ---------- lint ----------
class Lint(Tmp):
    def lint(self, name, body, *a):
        return run('lint', write(self.p(name), body), *a)

    def test_html(self):
        code, out, _ = self.lint('a.html', '<html><script src="https://cdn.x/y.js"></script><p>글</p></html>')
        self.assertEqual(code, 1)
        self.assertIn('외부 주소', out)
        code, out, _ = self.lint('b.html', '<html><script>const t = 1;</script><p>글</p></html>')
        self.assertEqual(code, 0, out)

    def test_text(self):
        good = '**PR · 캐시** — 캐시가 있으면 늦게 켤 수 있다\n\n```\n전  CLI ─(켠다)▶ 서버\n```\n\n**어떻게** 첫 호출\n\n빠진 디테일: 왜, 조심, 규모\n근거: src/cache.rs:11\n출처: PR 본문\n'
        a = ('--type', 'pr', '--mode', 'eli5', '--source', os.path.join(SRC, 'pr.md'))
        code, out, _ = self.lint('g.md', good, *a)
        self.assertEqual(code, 0, out)
        for x, y, word in (('src/cache.rs:11', 'src/cache.rs:99', 'diff에 보이지 않는다'), ('출처: PR 본문\n', '', '`출처:` 줄이 없다'), ('첫 호출', '첫 호출 8888번', '숫자 8888'), ('첫 호출', '`no_such`', '`no_such`'),
                           ('첫 호출', '첫 호출 /Us' + 'ers/who/x', '홈 폴더'), ('첫 호출', '{{값}}', '{{')):
            code, out, _ = self.lint('x.md', good.replace(x, y, 1), *a)
            self.assertEqual(code, 1, (y, out))
            self.assertIn(word, out)
        code, out, _ = self.lint('l.md', good.replace('첫 호출', '첫 호출에 켠다 ' * 60), *a, '--size', '작음')
        self.assertIn('450자다', out)
        code, out, _ = self.lint('w.md', good.replace('늦게 켤 수 있다', '항상 늦게 켠다'), *a)
        self.assertIn('항상', out)

    def test_private_safety(self):
        code, out, _ = self.lint('s.md', '키는 ghp_' + 'A1b2' * 10 + '\n')
        self.assertEqual(code, 1)
        self.assertIn('비밀 값', out)


# ---------- pack ----------
class Pack(Tmp):
    def test_numbered_diff(self):
        run('start', os.path.join(SRC, 'pr.md'), '--out', self.p('o'))
        md = read(self.p('o', '.into', 'pr', 'pack.md'))
        self.assertRegex(md, r'(?m)^\s*\+?\s*12\b.*load_later\(30\)|12.*load_later\(30\)')
        self.assertIn('src/cache.rs', md)
        pj = json.loads(read(self.p('o', '.into', 'pr', 'pack.json')))
        self.assertFalse(pj['public'])                                    # 머리말 source가 URL인 것만으로는 공개가 아니다
        nums, lines = pack.fact_numbers(pj)
        self.assertIn('4', lines)
        self.assertNotIn('795', nums)                                  # 글자 수는 개수가 아니다

    def test_repo_fast_and_relative(self):
        for i in range(40):
            write(self.p('repo', 'core', 'm%d.py' % i), 'def f%d():\n    return %d\n' % (i, i))
        write(self.p('repo', 'README.md'), '# 저장소\n')
        code, out, err = run('start', self.p('repo'), 'doc', '--type', 'codebase', '--zone', 'core', '--out', self.p('o'), '--no-fetch')
        self.assertEqual(code, 0, err)
        md = read(self.p('o', '.into', 'repo-core', 'pack.md'))
        self.assertIn('core', md)
        self.assertNotIn(self.dir, md)

    def test_small_folder(self):
        write(self.p('two', 'a.py'), 'import b\n\n\ndef f():\n    return b.g()\n')
        write(self.p('two', 'b.py'), 'def g():\n    return 1\n')
        code, out, err = run('start', self.p('two'), 'eli5', '--type', 'general', '--out', self.p('o'), '--no-fetch')
        self.assertEqual(code, 0, err)
        self.assertIn('원문 폴더의 파일 전체', out)

    def test_secret_not_copied_to_pack(self):
        f = write(self.p('k.md'), '# 글\n\n토큰 ghp_' + 'A1b2' * 10 + '만 쓴다.\n')
        run('start', f, '--type', 'general', '--out', self.p('o'))
        self.assertNotIn('ghp_A1b2A1b2A1b2', read(self.p('o', '.into', 'k', 'pack.md')))


def deck_json():
    flow = {'nodes': [{'id': 'a', 't': 'CLI'}, {'id': 'b', 't': '서버'}], 'edges': [{'from': 'a', 'to': 'b', 't': '첫 호출'}]}
    return {'slides': [
        {'slot': 'cover', 'title': '서버를 늦게 켠다', 'say': '첫 호출 때 켤 수 있다', 'viz': 'motion-inline', 'data': dict(flow, path=['a>b']), 'alt': 'CLI가 서버를 켠다', 'next': '전에는?', 'notes': '첫 호출 때 켤 수 있다.', 'f': ['f1']},
        {'slot': 'pic', 'title': '전에는 시작할 때 켰다', 'viz': 'flow', 'data': flow, 'alt': '전의 길', 'next': '지금은?', 'notes': '시작할 때 켰다.', 'f': ['f2']},
        {'slot': 'run', 'title': '지금은 호출이 켠다', 'viz': 'sequence', 'data': {'actors': [{'id': 'a', 't': 'CLI'}, {'id': 'b', 't': '서버'}], 'msgs': [{'from': 'a', 'to': 'b', 't': '첫 호출'}]}, 'alt': '순서', 'next': '정리하면?', 'notes': '첫 호출이 켠다.', 'f': ['f1']},
        {'slot': 'close', 'title': '첫 호출이 켠다', 'viz': 'predict', 'data': {'q': '언제 켜나?', 'opts': ['첫 호출', '시작'], 'a': 0, 'why': '첫 호출에 켠다'}, 'alt': '확인 질문', 'notes': '답은 첫 호출.'}]}


class Deck(Work):
    def setUp(self):
        super().setUp()
        self.model(pr_model())

    def test_ok(self):
        code, out, err = self.render('slides', deck_json())
        self.assertEqual(code, 0, out + err)
        page = read(self.p('o', 'w-slides.html'))
        self.assertEqual(page.count('<section class="slide">'), 4)
        self.assertEqual(page.count('class="next-q"'), 3)
        self.assertNotIn('{{', page.split('동작 코드 — ')[0])
        self.assertIn('빠진 디테일: ', page)
        mark = '// ===== 아래는 동작 코드'
        self.assertEqual(page.split(mark)[1], read(os.path.join(ASSETS, 'slides.html')).split(mark)[1])

    def bad(self, change, word, level='FAIL'):
        j = deck_json()
        change(j['slides'])
        _, out, err = self.render('slides', j)
        self.assertTrue(any(word in ln and ('- ' + level) in ln for ln in (out + err).split('\n')), (word, out, err))

    def test_fails(self):
        self.bad(lambda s: s[1].pop('next'), '다음 질문')
        self.bad(lambda s: s[1].pop('notes'), '발표자 노트')
        self.bad(lambda s: s[1].pop('alt'), 'alt')
        self.bad(lambda s: s[1].update(f=[]), '근거')
        self.bad(lambda s: s[1].update(viz='picture'), '`viz`를')
        self.bad(lambda s: s[1]['data'].update(edges=[{'from': 'a', 'to': 'z', 't': 'x'}]), '없는 노드')
        self.bad(lambda s: s[1].update(slot='catch'), '순서')
        self.bad(lambda s: s.pop(), 'close')
        self.bad(lambda s: s[1].update(title='값은 4242배다'), '4242')
        self.bad(lambda s: s[1].update(title='지금은 호출이 켠다'), '제목이 같다')


# ---------- 처음 쓰는 에이전트가 막힌 곳 ----------
def levels(out, err=''):
    return [ln[2:] for ln in (out + err).split('\n') if ln.startswith(('- FAIL', '- WARN'))]


class Trips(Work):
    """왕복을 줄이는 것 (1~8)"""

    def setUp(self):
        super().setUp()
        self.model(pr_model())

    def ste(self, cases):
        return self.render('ste', {'one': {'t': '도구 목록이 캐시돼 있으면 서버는 첫 로드를 건너뛸 수 있다.', 'f': ['f1']}, 'cases': cases})

    def test_1_row_example_in_order(self):
        _, out, _ = run('start', self.src, 'ste', '--out', self.p('o2'))
        self.assertIn('{"입력":"…","전":"…","후":"…","f":["f1"]}', out)

    def test_1_table_shapes(self):
        row, made = '| 캐시 있음 | 바로 켠다 | 첫 호출에 켠다 |', '| 가 | 나 | 다 |'
        for v, want in ((['k1'], row), ('k1', row), ([{'id': 'k1'}], row), ([{'cells': ['가', '나', '다'], 'f': ['k1']}], made), ([{'t': ['가', '나', '다'], 'f': ['k1']}], made), ([['가', '나', '다']], made),
                        (['가', '나', '다'], made), ([{'입력': '가', '전': '나', '후': '다', 'f': ['k1']}], made), ([{'input': '가', 'before': '나', 'after': '다', 'f': ['k1']}], made),
                        ([{'id': 'k1', '후': '다'}], '| 캐시 있음 | 바로 켠다 | 다 |'), ({'rows': [['가', '나', '다']]}, made)):
            code, out, err = self.ste(v)
            self.assertEqual(code, 0, (v, out, err))
            self.assertIn(want, out, v)
        for v, word in ((['zzz'], '`zzz`'), (['f1'], '행을 직접 쓴다'), ([{'없는열': '가'}], '열 이름'), ([['가']], '칸이 1개다')):
            code, out, _ = self.ste(v)
            self.assertEqual(code, 1, v)
            self.assertIn(word, out)

    def test_2_slack(self):
        for n, code in ((60, 0), (61, 0), (63, 0), (64, 1)):
            got, out, err = self.render('eli5', dict(eli5(), one={'t': '서버를 첫 호출 때 켤 수 있다 캐시돼 있으면 '.ljust(n, '가'), 'f': ['f1']}))
            self.assertEqual(got, code, (n, out, err))
            self.assertEqual(any('%d자다. 60자까지다' % n in x for x in levels(out, err)), n > 60)

    def test_2_count_line(self):
        _, out, err = self.render('eli5', eli5())
        m = re.search(r'글자 (\d+)/450 · 남음 (\d+) — 머리 (\d+) · one (\d+) · pic (\d+) · run (\d+) · catch (\d+)', out + err)
        self.assertTrue(m, out + err)
        n = [int(x) for x in m.groups()]
        self.assertEqual(n[0], sum(n[2:]))
        self.assertEqual(n[0] + n[1], 450)
        self.assertEqual(n[2], T.count('캐시를 쓰면 늦게 켠다'))
        self.assertEqual(n[4], T.count('전 CLI (바로 켠다) 서버') + T.count('후 CLI (첫 호출에 켠다) 서버') - T.count('CLI') - T.count('서버'))      # 되풀이한 노드 이름은 한 번만
        self.assertEqual(n[0], T.count_result(out))
        code, out, _ = self.render('eli5', dict(eli5(), one=''))
        self.assertEqual(code, 1)
        self.assertRegex(out, r'글자 \d+/450')
        for mode in ('html', 'interactive'):
            _, out, err = self.render(mode, {'one': {'t': '캐시돼 있으면 늦게 켤 수 있다', 'f': ['f1']}})
            m = re.search(r'글자 (\d+)/[\d,]+ · 남음 .*?pic (\d+)', out + err)
            self.assertTrue(m, out + err)
            self.assertEqual(int(m.group(2)), sum(T.count(x) for x in ('CLI', '서버', '바로 켠다', '첫 호출에 켠다')), out + err)      # 같은 상자는 한 번

    def test_2_order_says_what_counts(self):
        _, out, _ = run('start', self.src, 'eli5', '--out', self.p('o2'))
        self.assertIn('세는 것: 머리 줄(제목·범위)·칸·그림의 글', out)
        self.assertIn('안 세는 것: 빠진 디테일·근거·출처', out)
        self.assertIn('450자', out)

    def test_2_total_slack(self):
        self.assertEqual([T.over(n, 450) for n in (450, 451, 472, 473)], ['', 'WARN', 'WARN', 'FAIL'])

    def test_3_short_text_in_pic(self):
        _, out, err = self.render('eli5', dict(eli5(), pic=['e1', {'id': 'e2', 't': '나중에'}]))
        self.assertIn('후  CLI ─(나중에)▶ 서버', out)
        self.assertIn('전  CLI ─(바로 켠다)▶ 서버', out)
        self.assertIn('src/cache.rs:11-12', out)
        code, out, _ = self.render('eli5', dict(eli5(), pic=['e1', {'id': 'e2', 't': '9,876초 뒤'}]))
        self.assertEqual(code, 1)
        self.assertIn('9,876', out)
        code, out, _ = self.render('eli5', dict(eli5(), pic=[{'id': 'zz', 't': '가'}]))
        self.assertEqual(code, 1)

    def test_4_same_as_eli5(self):
        code, out, _ = self.render('html', {})
        self.assertEqual(code, 1)
        self.render('eli5', eli5())
        code, out, err = self.render('html', {})
        self.assertEqual(code, 0, out + err)
        self.assertIn('도구 목록이 캐시돼 있으면 서버를 첫 호출 때 켤 수 있다', read(self.p('o', 'w-html.html')))
        _, out, _ = run('start', self.src, 'html', '--out', self.p('o2'))
        self.assertIn('eli5 그대로', out)
        self.assertNotIn('eli5.json에서 온다', out)                       # 새 폴더라 eli5.json이 없다
        _, out, _ = run('start', self.src, 'html', '--out', self.p('o'), '--slug', 'w')
        self.assertIn('eli5.json에서 온다', out)
        _, out, _ = run('start', self.src, 'ste', '--out', self.p('o2'))
        self.assertNotIn('eli5.json에서 온다', out)

    def test_5_missing_replaces(self):
        _, out, _ = self.render('eli5', dict(eli5(), missing='시험 표'))
        self.assertIn('빠진 디테일: 시험 표. 빈 칸: 왜, 규모\n', out)
        _, out, _ = self.render('eli5', dict(eli5(), missing=['하나', '둘']))
        self.assertIn('빠진 디테일: 하나 · 둘. 빈 칸', out)

    def test_6_step_ids(self):
        m = pr_model()
        self.assertEqual([s['id'] for s in M.normalize(m)['steps']], ['s1', 's2'])
        m['steps'][1]['id'] = 'last'
        self.model(m)
        code, out, err = self.render('eli5', dict(eli5(), run=[{'t': 'CLI가 목록을 본다', 'f': ['s1']}, {'t': '첫 호출에 서버를 켠다', 'f': ['last']}]))
        self.assertEqual(code, 0, out + err)
        m['facts'][0]['id'] = 's1'
        self.assertEqual(M.normalize(m)['steps'][0]['id'], 'steps1')

    def test_6_schema_line(self):
        _, out, _ = run('start', self.src, 'eli5', '--out', self.p('o2'))
        for s in ('"title":"제목(30자까지', '"scope":"범위(25자까지', '"source":"무엇을 어디까지 읽었나(출처 줄)"', '"steps":[{"id":"s1"', '"cond":"none"'):
            self.assertIn(s, out)
        self.assertRegex(out, r'"edges":\[\{[^}]*"if":"[^"]*","hedge":"[^"]*"')

    def test_6_long_title_warns(self):
        _, out, _ = self.model(dict(pr_model(), title='가' * 31, scope='나' * 26))
        self.assertEqual([('title' in x, 'scope' in x) for x in levels(out) if 'WARN' in x], [(True, False), (False, True)])
        _, out, _ = self.model(dict(pr_model(), title='가' * 30, scope='나' * 25))
        self.assertEqual(levels(out), [])

    def test_7_list_of_ids(self):
        _, out, _ = self.render('eli5', dict(eli5(), catch=['f2', {'t': 'c1'}]))
        self.assertIn('전에는 CLI가 시작할 때 서버를 켰다', out)
        self.assertIn('켜는 때: 시작 → 첫 호출', out)
        code, out, _ = self.render('eli5', dict(eli5(), catch=['b9']))
        self.assertEqual(code, 1)
        self.assertIn('`b9`', out)

    def test_8_absolute_paths(self):
        _, out, _ = run('start', self.src, 'eli5', '--out', self.p('o2'))
        self.assertIn('작업 폴더 W = ' + os.path.realpath(self.p('o2')) if self.p('o2') == os.path.realpath(self.p('o2')) else 'o2', out)
        self.assertNotIn('../', out)
        self.assertIn(os.path.join(SKILL, 'scripts', 'into.py') + ' check /', out)

    def test_8_zones(self):
        for d in ('core/a', 'core/b', 'web'):
            for i in range(9):
                write(self.p('repo', d, 'm%d.py' % i), 'x = 1\n')
        a = ('start', self.p('repo'), 'eli5', '--type', 'codebase', '--no-fetch', '--out', self.p('o2'))
        _, out, _ = run(*a, '--zone', 'core/a,web')
        md = read(os.path.join(re.search(r'W = (\S+)', out).group(1), 'pack.md'))
        self.assertIn('- `core/a` 소스 9개', md)
        self.assertIn('- `web` 소스 9개', md)
        self.assertNotIn('- `core/b` 소스', md.split('## 최상위')[0])
        self.assertIn('core/a/m0.py', md)
        self.assertIn('구역 전체 목록은 pack.md', out)
        _, out, _ = run(*a, '--zone', '샌드박스 정책')
        self.assertNotIn('구역 전체 목록은 pack.md', out)
        self.assertIn('--zone 경로,경로', out)
        run(*a, '--slug', 'x', '--zone', 'core')
        _, out, _ = run(*a, '--slug', 'x', '--zone', 'web')
        self.assertIn('`x-2`', out)


class False_alarms(Tmp):
    """오탐 (9~13)"""

    def check(self, body, facts, typ='general', **more):
        f = write(self.p('s.md'), body)
        src = cite.Source('file', f, ['raw'])
        m = M.normalize(dict({'type': typ, 'title': 't', 'source': 's', 'facts': facts}, **more))
        return [str(i) for i in M.check(m, json.dumps(m, ensure_ascii=False), src, typ)]

    PARA = 'The server starts early. If `lazy_mode` is set, the server may wait for 30 seconds. Other tools are listed only in the docs. Nothing else changes.\n'

    def test_9_best_sentence(self):
        src = ['raw:1']
        self.assertEqual(self.check(self.PARA, [{'id': 'f1', 't': '서버는 `lazy_mode`면 30초를 기다릴 수 있다', 'src': src}]), [])
        got = self.check(self.PARA, [{'id': 'f1', 't': '`lazy_mode`에서 서버가 30초를 기다린다', 'src': src}])
        self.assertEqual(len(got), 1, got)
        self.assertIn('할 수 있다', got[0])
        self.assertNotIn('~만', got[0])

    def test_9_cannot_pick(self):
        got = self.check(self.PARA, [{'id': 'f%d' % i, 't': '기다림 이야기 ' + w, 'src': ['raw:1']} for i, w in enumerate('가나다', 1)])
        self.assertEqual(len(got), 1, got)
        self.assertIn('긴 줄 1곳: 조건어를 직접 본다', got[0])

    def test_9_cond_none(self):
        self.assertEqual(self.check(self.PARA, [{'id': 'f1', 't': '`lazy_mode`에서 서버가 30초를 기다린다', 'src': ['raw:1'], 'cond': 'none'}]), [])

    def test_9_boundaries(self):
        for s in ('A decoder-only model.', 'It runs only once here.', 'Little is known about it.', 'It fails even if it is fast.', 'Humans can distinguish it.', 'It is up to you.', '화면 측면 장면을 본다.', '값만 본다.'):
            self.assertEqual(T.cond_kinds(s), [], s)
        for s, k in (('Only admins see it.', 'only'), ('It may wait.', 'may'), ('If set, it runs.', 'if'), ('up to 3 files', 'bound'), ('관리자일 때만 본다.', 'only'), ('값이 있으면 쓴다.', 'if')):
            self.assertIn(k, T.cond_kinds(s), s)

    def test_10_absolutes(self):
        names = {n for n, _, _ in T.ABSOLUTE}
        self.assertNotIn('만', names)
        for s in ('값만 본다', '늘 그렇다', '다만 다르다', '절대값을 쓴다', '모두의 광장' if False else '모드를 쓴다'):
            self.assertFalse([n for n, rx, _ in T.ABSOLUTE if rx.search(s)], s)
        for s in ('항상 켠다', '절대 켜지 않는다', '언제나 켠다', '반드시 켠다', '무조건 켠다', '모든 값', '전부 켠다', '모두 켠다'):
            self.assertTrue([n for n, rx, _ in T.ABSOLUTE if rx.search(s)], s)

    def test_11_numbers(self):
        ok = T.number_set('limit = 10_000, p = .10, x = 0.45. On March 3. Five tools, twelve files, twenty steps')
        for s in ('10,000개', '10%', '45%', '3월', '5개', '12개', '20단계'):
            self.assertTrue(T.numbers(s)[0][1] & ok, s)
        for s in ('L89-92를 본다', '예 3을 본다', '1/3을 본다', '표 2에', '그림 14', '댓글 12의 말', 'v11 판'):
            self.assertEqual(T.numbers(s), [], s)
        self.assertEqual(len(T.numbers('댓글 12개')), 1)
        self.assertFalse(T.numbers('11,000')[0][1] & ok)
        got = []
        for n in ('503', '504', '3.5', '40%'):
            M.check_numbers('값은 %s다' % n, lambda f: False, 'w', lambda *a: got.append(a[2]))
        self.assertEqual([re.match(r'숫자 (\S+)', g).group(1) for g in got], ['503이', '504가', '3.5가', '40%가'])

    def test_13_who_not_in_nodes(self):
        kw = dict(nodes=[{'id': 'a', 't': '서버'}], steps=[{'who': '저자', 'do': '쓴다', 'src': ['raw:1']}], order='text')
        fs = [{'id': 'f1', 't': '서버', 'src': ['raw:1']}]
        for typ, n in (('general', 1), ('paper-concept', 0), ('local-file', 0)):
            self.assertEqual(len([x for x in self.check('서버가 쓴다.\n', fs, typ, **kw) if '하는 쪽' in x]), n, typ)


class Shape(Work):
    def test_12_table_and_pic_conditions(self):
        m = pr_model()
        m['facts'].append({'id': 'f3', 't': '관리자면 한도를 무시한다', 'src': ['raw:9'], 'if': '관리자 권한', 'cond': 'none'})
        self.model(m)
        one = {'t': '도구 목록이 캐시돼 있으면 서버는 첫 로드를 건너뛸 수 있다.', 'f': ['f1']}
        _, out, err = self.render('ste', {'one': one, 'cases': [{'cells': ['관리자', '가', '나'], 'f': ['k1']}, {'cells': ['다', '라', '마'], 'f': ['f3']}]})
        self.assertNotIn('관리자 권한', err)
        _, out, err = self.render('ste', {'one': one, 'cases': [{'cells': ['바', '가', '나'], 'f': ['k1']}, {'cells': ['다', '라', '마'], 'f': ['f3']}]})
        self.assertEqual(len([x for x in levels('', err) if '관리자 권한' in x]), 1)

    def test_12_pic_hedge(self):
        m = pr_model()
        m['edges'][1]['hedge'] = 'may'
        self.model(m)
        _, _, err = self.render('eli5', eli5())
        self.assertIn('eli5.json pic: `e2`의 한정어', err)
        _, _, err = self.render('eli5', dict(eli5(), pic=['e1', {'id': 'e2', 't': '첫 호출에 켤 수 있다'}]))
        self.assertNotIn('한정어', err)

    def test_12_fail_count_is_unique(self):
        self.model(pr_model())
        code, out, _ = self.render('eli5', dict(eli5(), catch=[{'t': '전에는 켰다', 'f': ['zz', 'zz']}]))
        n = int(re.search(r'FAIL (\d+)', out).group(1))
        self.assertEqual(n, len([x for x in levels(out) if x.startswith('FAIL')]))

    def test_13_order_note(self):
        for order, want in (('call', '**어떻게**\n1.'), ('text', '**어떻게**\n1.'), ('none', '**어떻게** (순서: 없음)\n1.'), (None, '**어떻게** (순서: 원문에 없음)\n1.')):
            self.model(dict(pr_model(), order=order))
            _, out, _ = self.render('eli5', eli5())
            self.assertIn(want, out, order)
            self.assertEqual(out.count('(순서: '), int(order in ('none', None)))

    def test_14_mark(self):
        m = pr_model()
        m['facts'][1]['mark'] = '근거 미제시'
        self.model(m)
        _, out, _ = self.render('eli5', dict(eli5(), catch=[{'t': '전에는 CLI가 시작할 때 서버를 켰다. 도구 목록이 캐시돼 있으면 건너뛸 수 있다.', 'f': ['f2', 'f1']}, {'t': '둘째(근거 미제시)', 'f': ['f2']}]))
        self.assertIn('전에는 CLI가 시작할 때 서버를 켰다 (근거 미제시). 도구 목록이', out)
        self.assertEqual(out.count('근거 미제시'), 2)
        _, out, _ = run('start', self.src, 'eli5', '--out', self.p('o2'))
        self.assertIn('이미 있으면 안 붙는다', out)

    def test_15_options(self):
        m = {'criteria': [{'id': 'c1', 't': '값'}], 'cells': [{'o': 'o1', 'c': 'c1', 'sign': '+', 't': '싸다'}, {'o': 'o2', 'c': 'c1', 'sign': '-', 't': '비싸다'}]}
        v = [{'id': 'o1', 't': '가', 'chosen': True}, {'id': 'o2', 't': '나'}, {'id': 'o3', 't': '다'}]
        row = {'form': 'options', 'label': '칸', 'key': 'pic'}
        ctx = {'model': m, 'order_note': '', 'refs': {}, 'mode': 'eli5'}
        self.assertEqual(textmodes.pic_block(ctx, row, v)[1:], ['- 가(고름) — 싸다', '- 나 — 비싸다', '- 다'])
        self.assertIn('| ✓ 가 | ＋ 싸다 |', textmodes.pic_block(dict(ctx, mode='doc'), row, v))

    def test_16_social(self):
        for typ in ('threads-post', 'thread', 'x-post'):
            body = '---\ntype: %s\n---\n# 글\n\n## 댓글 1\n\n가\n\n## 댓글 2\n\n나\n\n## 댓글 3\n\n다\n\nAsk HN: 4 comments\n' % typ
            meta, _ = T.front_matter(body)
            d = route.decide(route.score_text(body, meta, 'a.md'))
            self.assertEqual((d['type'], d['tie']), ('social-post', False), d['rank'])
        for head in ('## 트윗 %d', '### 글 %d'):
            body = '# 모음\n\n' + '\n\n'.join(head % i + '\n\n말' for i in range(1, 6))
            self.assertIn('글 번호', str(route.score_text(body, {}, 'a.md')['social-post']))
            s = cite.Source('file', write(self.p('t.md'), body), ['raw'])
            self.assertTrue(s.resolve('3/5')['ok'])
            self.assertFalse(s.resolve('9/9')['ok'])
        f = write(self.p('c.md'), '# Ask HN: x\n\n## 댓글 1\n\n가\n')
        _, out, _ = run('start', f, 'eli5', '--type', 'community-post', '--out', self.p('o2'))
        self.assertEqual(re.search(r'근거 쓰기.*', out).group(0).count('raw:줄'), 1)


# ---------- GPT 1차 리뷰 ----------
class Review(Tmp):
    """근거 구간 · 원문 확보 · 공개 여부 · 파일 소유권"""
    BODY = '# 설정\n\n기본값은 30초다.\n유지 기간은 90일이다.\n변화는 -5%였고 적중률은 45%였다.\nretry_count를 센다.\n\nCLI가 서버에 묻는다.\n'

    def begin(self, body=None, *a, **kw):
        f = write(self.p('src', kw.get('name', 's.md')), self.BODY if body is None else body)
        code, out, err = run('start', f, 'eli5', '--type', kw.get('typ', 'general'), '--out', self.p('o'), '--slug', 'w', *a)
        self.w = self.p('o', '.into', 'w')
        return code, out, err

    def m(self, t='기본값은 30초다', src=('raw:3',), **k):
        return dict({'type': 'general', 'title': '설정', 'source': '글 전체', 'facts': [dict({'id': 'f1', 't': t, 'src': list(src), 'cond': 'none'}, **k)],
                     'nodes': [{'id': 'c', 't': 'CLI'}, {'id': 's', 't': '서버'}], 'edges': [{'id': 'e1', 'from': 'c', 'to': 's', 't': '묻는다', 'src': ['raw:8']}]})

    def check(self, m):
        write(os.path.join(self.w, 'model.json'), m)
        code, out, err = run('check', self.w)
        return code, levels(out)

    def eli5(self, t, mode='eli5', **k):
        write(os.path.join(self.w, mode + '.json'), dict({'one': {'t': t, 'f': ['f1']}}, **k))
        return run('render', self.w, mode)

    # 1
    def test_1_cell_near_evidence(self):
        self.begin()
        self.check(self.m())
        code, out, err = self.eli5('기본값은 90초다')
        self.assertEqual(code, 0, out)
        self.assertIn('근거 구간에 없음: 90', err)
        self.assertIn('원문 4줄', err)
        code, out, err = self.eli5('기본값은 30초다')
        self.assertNotIn('근거 구간', out + err)
        code, out, _ = self.eli5('기본값은 77초다')
        self.assertEqual(code, 1)
        _, out, err = self.eli5('', one={'t': '유지 기간은 90일이다', 'f': ['f1'], 'src': ['raw:4']})
        self.assertNotIn('근거 구간', out + err)
        _, _, err = self.eli5('`retry_count`는 30초다')
        self.assertNotIn('근거 구간', err)                                # 이름은 앞뒤 8줄까지 본다

    def test_1_model_value_unit_sign(self):
        self.begin()
        for t, src, lv, word in (('기본값은 90초다', 'raw:3', 'WARN', '90'), ('기본값은 30분이다', 'raw:3', 'WARN', '단위'), ('변화는 +5%다', 'raw:5', 'WARN', '부호'), ('기본값은 77초다', 'raw:3', 'FAIL', '77')):
            _, got = self.check(self.m(t, (src,)))
            self.assertTrue([x for x in got if x.startswith(lv) and word in x], (t, got))
        for t, src in (('기본값은 30초다', 'raw:3'), ('변화는 −5%다', 'raw:5'), ('5% 줄었다', 'raw:5'), ('유지 기간 90일', 'raw:4'), ('값은 30이다', 'raw:3')):
            _, got = self.check(self.m(t, (src,)))
            self.assertEqual(got, [], t)

    def test_1_plain_names(self):
        self.begin()
        _, got = self.check(self.m('FictionalCache가 30초를 기다린다'))
        self.assertEqual([x[:4] for x in got], ['WARN'], got)
        self.assertIn('FictionalCache', got[0])
        _, got = self.check(self.m('retry_count와 GitHub, CLI는 30초다'))
        self.assertEqual(got, [])
        _, got = self.check(self.m('fake_name이 30초를 기다린다'))
        self.assertIn('fake_name', str(got))

    # 2
    def test_2_no_body(self):
        u = 'https://example.com/blog/post'
        _, out, _ = run('start', u, 'eli5', '--out', self.p('o'), '--no-fetch')
        self.w = re.search(r'W = (\S+)', out).group(1)
        write(os.path.join(self.w, 'model.json'), self.m('값은 80432다', ('아무 글',)))
        write(os.path.join(self.w, 'eli5.json'), {'one': {'t': '값은 80432다', 'f': ['f1']}})
        for a in (('check', self.w), ('render', self.w, 'eli5')):
            code, out, err = run(*a)
            self.assertEqual(code, 1, (a, out, err))
            self.assertIn('FAIL', out)
            self.assertIn('본문', out)

    def test_2_url_only_evidence(self):
        self.begin(self.BODY + '\n자세한 것은 https://in.example/doc 에 있다.\n')
        code, got = self.check(self.m(src=('https://out.example/x',)))
        self.assertEqual(code, 1, got)
        self.assertIn('보충', str(got))
        self.assertEqual(self.check(self.m(src=('https://out.example/x',), mark='보충'))[0], 0)
        self.assertEqual(self.check(self.m(src=('https://out.example/x', 'raw:3')))[0], 0)
        self.assertEqual(self.check(self.m(src=('https://in.example/doc', 'raw:3')))[0], 0)

    # 4
    def test_4_public_rule(self):
        for u in ('https://github.com/a/b/pull/1', 'https://github.com/a/b/issues/7', 'https://gitlab.com/a/b/-/merge_requests/3', 'https://www.youtube.com/watch?v=a', 'https://x.com/a/status/1', 'https://www.reddit.com/r/a/comments/1'):
            self.assertFalse(route.public_of({}, u, None)[0], u)             # 주소만으로는 모른다
        for u in ('https://arxiv.org/abs/1', 'https://news.ycombinator.com/item?id=1', 'https://stackoverflow.com/questions/1/a', 'https://www.rfc-editor.org/rfc/rfc1'):
            self.assertTrue(route.public_of({}, u, None)[0], u)
        self.assertTrue(route.public_of({'public': 'true'}, 'https://github.com/a/b/pull/1', None)[0])
        self.assertFalse(route.public_of({}, 'https://wiki.corp.example/notes', None)[0])
        self.assertFalse(route.public_of({'source': 'https://github.com/a/b'}, '', None)[0])
        self.assertTrue(route.public_of({'source': 'https://a.b', 'public': 'true'}, '', None)[0])
        self.assertFalse(route.public_of({'public': 'true'}, '', False)[0])

    def test_4_flag_stays(self):
        body = '---\npublic: true\n---\n' + self.BODY
        _, out, _ = self.begin(body, '--private')
        self.assertIn('비공개', out)
        _, out, _ = self.begin(body)
        self.assertIn('비공개', out)
        _, out, _ = self.begin(body, '--public')
        self.assertNotIn('비공개', out)
        _, out, _ = self.begin(body)
        self.assertNotIn('비공개', out)

    # 5 · 6
    def test_5_not_our_folder(self):
        mine = write(self.p('o', '.into', 's', 'source.md'), '내 메모')
        f = write(self.p('src', 's.md'), self.BODY)
        _, out, _ = run('start', f, 'eli5', '--type', 'general', '--out', self.p('o'))
        self.assertIn('s-2', out)
        self.assertEqual(read(mine), '내 메모')

    def test_6_boundaries(self):
        secret = write(self.p('out.txt'), 'OUTSIDE = 1234\n')
        write(self.p('repo', 'a.py'), 'x = 1\n')
        os.symlink(secret, self.p('repo', 'link.py'))
        s = cite.Source('dir', self.p('repo'))
        self.assertNotIn('link.py', s.files())
        self.assertFalse(s.resolve('link.py:1')['ok'])
        self.assertFalse(s.has_text('../out.txt', []))
        os.symlink(secret, self.p('repo', 'SKILL.md'))
        code, _, err = run('start', self.p('repo'), '--type', 'skill', '--out', self.p('o'), '--no-fetch')
        self.assertEqual(code, 2)
        self.assertIn('링크', err)
        f = write(self.p('src', 's.md'), self.BODY)
        for slug in ('../x', 'a/b', '..', '/tmp/x'):
            code, _, err = run('start', f, '--type', 'general', '--out', self.p('o'), '--slug', slug)
            self.assertEqual(code, 2, slug)
            self.assertIn('slug', err)
        self.begin()
        self.check(self.m())
        target = write(self.p('victim.md'), '남의 글')
        os.symlink(target, self.p('o', 'w-doc.md'))
        code, out, err = self.eli5('', 'doc', one=[{'t': '기본값은 30초다', 'f': ['f1']}])
        self.assertEqual(code, 2, out + err)
        self.assertIn('링크', err)
        self.assertEqual(read(target), '남의 글')

    # 9
    def test_9_facts_shape(self):
        self.begin()
        for facts in (['글'], {'id': 'f1', 't': '가', 'src': ['raw:9000']}, '글', [['f1']]):
            code, got = self.check(dict(self.m(), facts=facts))
            self.assertEqual(code, 1, facts)
            self.assertIn('facts', str(got))
        for k, v in (('edges', {'id': 'e1'}), ('steps', {'a': {'b': 1}}), ('type', ['general']), ('type', 3)):
            code, got = self.check(dict(self.m(), **{k: v}))
            self.assertEqual(code, 1, (k, v, got))

    # 10
    def test_10_source_changed(self):
        self.begin()
        self.check(self.m())
        _, out, _ = self.begin(self.BODY.replace('30초', '40초'))
        self.assertIn('원문이 바뀌었다', out)
        _, got = self.check(self.m())
        self.assertNotIn('원문이 바뀌었다', str([x for x in got if x.startswith('FAIL')]))
        code, out, _ = run('check', self.w)
        self.assertIn('원문이 바뀌었다', out)
        _, got = self.check(self.m('기본값은 40초다'))
        self.assertNotIn('원문이 바뀌었다', str(got))

    def test_10_same_stdin(self):
        for body, want in (('# 가\n\n같은 글이다.\n', False), ('# 가\n\n같은 글이다.\n', False), ('# 가\n\n다른 글이다.\n', True)):
            old, sys.stdin = sys.stdin, io.StringIO(body)
            try:
                _, out, _ = run('start', '-', 'eli5', '--type', 'general', '--out', self.p('o'))
            finally:
                sys.stdin = old
            self.assertEqual(bool(re.search(r'W = \S+-2\b', out)), want, out[:300])

    # 11
    def test_11_whole_range(self):
        s = cite.Source('file', write(self.p('a.md'), '하나\n둘\n'), ['raw'])
        self.assertTrue(s.resolve('raw:1-2')['ok'])
        self.assertFalse(s.resolve('raw:3')['ok'])
        s = cite.Source('pr', os.path.join(SRC, 'pr.md'), ['raw', 'pr.md'])
        self.assertTrue(s.resolve('src/cache.rs:10-15')['ok'])
        self.assertFalse(s.resolve('src/cache.rs:10-999')['ok'])
        self.assertFalse(s.resolve('src/cache.rs:15-41')['ok'])
        s = cite.Source('file', write(self.p('v.md'), '[00:30] 가\n[1:02:03] 나\n00:01:10,500 --> 00:01:12,000\n다\n'), ['raw'])
        for t in ('[00:30]', '[0:30]', '[01:02:03]', '[62:03]', '[01:10]', '[0:30-1:10]'):
            self.assertEqual(s.resolve(t)['warn'], '', t)
        self.assertEqual(s.resolve('[00:30]')['text'], '[00:30] 가')
        self.assertTrue(s.resolve('[00:31]')['warn'])

    # 12
    def test_12_empty_binary_long(self):
        code, _, err = self.begin('')
        self.assertEqual(code, 2)
        self.assertIn('비었다', err)
        with open(self.p('src', 'b.md'), 'wb') as f:
            f.write(b'a\0b')
        code, _, err = run('start', self.p('src', 'b.md'), '--type', 'general', '--out', self.p('o'))
        self.assertEqual(code, 2)
        self.assertIn('이진', err)
        old, pack.READ_MAX = pack.READ_MAX, 20
        try:
            code, out, _ = self.begin('가' * 30 + '\n둘째 줄\n')
        finally:
            pack.READ_MAX = old
        self.assertIn('앞 20자', out)
        self.assertEqual(read(os.path.join(self.w, 'source.md')), '가' * 20)
        self.assertIn('앞 20자', read(os.path.join(self.w, 'pack.md')))

    # 13
    def test_13_fenced_diff_is_not_pr(self):
        body = '# diff 읽는 법\n\n' + '설명 문장이다. ' * 20 + '\n\n```diff\n' + DIFF + '```\n'
        self.assertEqual(route.decide(route.score_text(body, {}, 'how.md'))['type'], 'general')

    def test_13_url_body_decides_again(self):
        u = 'https://example.com/talk'
        _, out, _ = run('start', u, 'eli5', '--out', self.p('o'), '--no-fetch')
        w = re.search(r'W = (\S+)', out).group(1)
        write(os.path.join(w, 'source.md'), '---\ntype: video\n---\n# Agent talk\n\n' + '\n'.join('[%02d:10] 말한다' % i for i in range(9)) + '\n\n영상 자막이다. YouTube 영상.\n')
        _, out, _ = run('start', u, 'eli5', '--out', self.p('o'), '--no-fetch')
        self.assertIn('# into · video × eli5', out)
        self.assertEqual(re.search(r'W = (\S+)', out).group(1), w)          # 제목이 생겨도 같은 폴더

    # 14
    def test_14_spaces(self):
        write(self.p('한글 폴더', '파일 하나.py'), 'x = 1\n')
        s = cite.Source('dir', self.p('한글 폴더'))
        r = s.resolve('파일 하나.py:1')
        self.assertTrue(r['ok'], r['msg'])
        self.assertEqual(r['text'], 'x = 1')
        f = write(self.p('src', 's.md'), self.BODY + '\n절 이름: 3\n')
        self.assertTrue(cite.Source('file', f, ['raw']).resolve('절 이름: 3')['ok'])
        _, out, _ = run('start', f, 'eli5', '--type', 'general', '--out', self.p('출력 폴더'))
        import shlex
        cmd = re.search(r'`(python3 .* check .*?)`', out).group(1)
        self.assertEqual(len(shlex.split(cmd)), 4, cmd)

    # 15
    def test_15_brief_main_figure(self):
        for typ, form in (('pr', 'beforeafter'), ('community-post', 'positions'), ('skill', 'lanes'), ('general', 'flow')):
            row = [r for r in formats.mode_rows(typ, 'brief')[0] if r['slot'] == 'pic'][0]
            self.assertEqual((row['form'], row['required']), (form, False), typ)

    def test_15_no_edges(self):
        self.begin('enabled = true\n', typ='pr', name='c.md')
        write(os.path.join(self.w, 'model.json'), {'type': 'pr', 'title': '켬', 'source': '한 줄', 'facts': [{'id': 'f1', 't': '`enabled`는 true다', 'src': ['raw:1']}]})
        code, out, err = self.eli5('`enabled`는 true다')
        self.assertEqual(code, 0, out + err)
        self.assertTrue([x for x in levels(out, err) if x.startswith('WARN') and 'pic' in x and '그림' in x], err)

    # 17
    def test_17_lint_counts_what_is_seen(self):
        self.begin()
        self.check(self.m())
        code, out, err = self.eli5('기본값은 30초다', 'html')
        n = int(re.search(r'글자 ([\d,]+)/', out + err).group(1).replace(',', ''))
        _, out, _ = run('lint', self.p('o', 'w-html.html'), '--type', 'general', '--mode', 'html', '--size', '작음')
        self.assertEqual(int(re.search(r'보이는 글자 ([\d,]+)', out).group(1).replace(',', '')), n)

    # 19
    def test_19_help(self):
        o = io.StringIO()
        with contextlib.redirect_stdout(o), self.assertRaises(SystemExit):
            into.main(['start', '-h'])
        self.assertIn('stdin', o.getvalue())


class Review_modes(Work):
    def setUp(self):
        super().setUp()
        self.model(pr_model())

    def test_3_chart_numbers(self):
        j = deck_json()
        j['slides'][1].update(viz='chart', data={'type': 'hbar', 'axis': '서버 · 켠 수 · 지금', 'max': 99999, 'items': [{'t': '서버', 'v': 87654}, {'t': 'CLI', 'v': 1234}], 'hi': 0, 'ref': {'v': 73456, 't': '기준'}})
        _, out, err = self.render('slides', j)
        w = '\n'.join(x for x in levels(out, err) if x.startswith('WARN'))
        self.assertIn('87654', w)
        self.assertIn('73456', w)
        self.assertNotIn('99999', w)
        self.assertIn('근거 구간에 없음: 1234', w)                              # 원문에는 있지만 그 장의 근거에는 없다
        m = pr_model()
        m['facts'].append({'id': 'f9', 't': '한도는 1234다', 'src': ['src/cache.rs:41']})
        self.model(m)
        j['slides'][1]['f'] = ['f9']
        _, out, err = self.render('slides', j)
        self.assertNotIn('1234', '\n'.join(levels(out, err)))
        j['slides'][1]['data']['unit'] = '초'
        _, out, err = self.render('slides', j)
        self.assertIn('단위가 근거와 다르다: 1234초', '\n'.join(levels(out, err)))

    def test_8_final_safety(self):
        j = quiz_json()
        j['questions'][0]['wrong'][0] = '/ho' + 'me/demo/x다'
        code, out, _ = self.render('test', j)
        self.assertEqual(code, 1, out)
        self.assertIn('홈 폴더', out)
        self.assertFalse(os.path.exists(self.p('o', 'w-test.html')))

    def test_16_order(self):
        m = pr_model()
        _, out, _ = self.render('eli5', dict(eli5(), why={'t': '전에는 CLI가 시작할 때 켰다', 'f': ['f2']}, catch=[]))
        self.assertLess(out.index('**왜**'), out.index('```'))
        self.assertLess(out.index('```'), out.index('**어떻게**'))
        bad = out.replace('**왜** 전에는 CLI가 시작할 때 켰다\n\n', '').replace('빠진 디테일', '**왜** 전에는 CLI가 시작할 때 켰다\n\n빠진 디테일')
        for s, want in ((out, 0), (bad, 1)):
            _, got, _ = run('lint', write(self.p('r.md'), s), '--type', 'pr', '--mode', 'eli5')
            self.assertEqual(got.count('칸 순서가 다르다'), want, got)


class Round4(Tmp):
    """2차 리뷰에서 남은 것 (번호 = into-s2.out.md)"""
    BODY, begin, m, check, eli5 = Review.BODY, Review.begin, Review.m, Review.check, Review.eli5

    # 1
    def test_1_line_count_is_not_a_fact(self):
        self.begin('대기는 30초다.\n\n끝이다.\n')
        code, got = self.check(dict(self.m('대기는 3초다', ('raw:1',)), nodes=[], edges=[]))
        self.assertIn('3', str(got))
        self.assertTrue(got, '줄 수 3이 허용 숫자로 쓰였다')
        for t, want in (('글은 3줄이다', True), ('글은 3초다', False)):
            _, got = self.check(dict(self.m(t, ('raw:1',)), nodes=[], edges=[]))
            self.assertEqual(not got, want, (t, got))
        s = cite.Source('file', write(self.p('x.md'), '가 10\n'), ['raw'])
        s.allow_numbers({'7'}, {'12', '34'})
        for t, ok in (('파일 7개', 1), ('12줄', 1), ('+12 −34', 1), ('12초', 0), ('34', 0), ('-12초', 0), ('10', 1)):
            got = []
            M.check_numbers(t, lambda f, counted=False: s.number_ok(f, (), counted), 'w', lambda *a: got.append(a))
            self.assertEqual(not got, bool(ok), (t, got))

    def test_1_minus_sign(self):
        self.begin()
        for t, src, warn in (('기본값은 -30초다', 'raw:3', 1), ('변화는 -5%다', 'raw:5', 0), ('기본값은 30초다', 'raw:3', 0)):
            _, got = self.check(self.m(t, (src,)))
            self.assertEqual('부호' in str(got), bool(warn), (t, got))
        self.begin('# 가\n\n오류가 30% 줄었다.\n\nCLI가 서버에 묻는다.\n')
        _, got = self.check(dict(self.m('오류 -30%', ('raw:3',)), nodes=[], edges=[]))
        self.assertNotIn('부호', str(got))

    # 2 · 10 · 설계 3
    def test_2_lost_copy(self):
        self.begin()
        self.check(self.m())
        os.remove(os.path.join(self.w, 'source.md'))
        for a in (('check', self.w), ('render', self.w, 'eli5')):
            write(os.path.join(self.w, 'eli5.json'), {'one': {'t': '기본값은 30초다', 'f': ['f1']}})
            code, out, err = run(*a)
            self.assertEqual(code, 1, out + err)
            self.assertIn('원문 사본이 없다', out)

    def test_10_render_says_source_changed(self):
        self.begin()
        self.check(self.m())
        code, out, err = self.eli5('기본값은 30초다')
        self.assertNotIn('바뀌었다', out + err)
        write(self.p('src', 's.md'), self.BODY.replace('30초', '40초'))          # start를 다시 부르지 않았다
        for a in (('check', self.w), ('render', self.w, 'eli5')):
            _, out, err = run(*a)
            self.assertIn('원문이 start 뒤에 바뀌었다', out + err, a)
        self.begin(self.BODY.replace('30초', '40초'))
        _, out, err = run('render', self.w, 'eli5')
        self.assertIn('원문이 바뀌었다', out + err)

    def test_10_crlf_is_not_a_change(self):
        os.makedirs(self.p('src'), exist_ok=True)
        with open(self.p('src', 's.md'), 'wb') as f:
            f.write(self.BODY.replace('\n', '\r\n').encode('utf-8'))
        run('start', self.p('src', 's.md'), 'eli5', '--type', 'general', '--out', self.p('o'), '--slug', 'w')
        self.w = self.p('o', '.into', 'w')
        self.check(self.m())
        _, out, _ = run('check', self.w)
        self.assertNotIn('바뀌었다', out)

    def test_ready_private(self):
        self.begin('---\npublic: true\n---\n' + self.BODY)
        self.check(self.m(src=('raw:6',)))
        _, out, _ = self.eli5('기본값은 30초다')
        self.assertNotIn(NOTICE, out)
        p = os.path.join(self.w, 'source.md')
        write(p, read(p).replace('public: true', 'public: false'))
        _, out, _ = self.eli5('기본값은 30초다')
        self.assertIn(NOTICE, out)

    # 3
    def test_3_line_chart(self):
        from intolib import deck
        self.assertEqual(deck.measured({'type': 'line', 'x': ['1월', '2월'], 'max': 99999, 'series': [{'t': '가', 'v': [87654, 73456]}]}), [87654, 73456])
        self.assertEqual(deck.measured({'items': [{'t': '가', 'lo': 3, 'hi': 9, 'v': 5}, {'t': '나', 'v': [1, 2], 'est': True}], 'hi': 0}), [5, 3, 9])

    # 8
    def test_8_home_names(self):
        for s in ('/Us' + 'ers/민지/자료', '/ho' + 'me/demo/x', 'C:\\Users\\김\\a', '/Us' + 'ers/josé/a'):
            self.assertTrue(T.HOME.search(s), s)
        for s in ('/Users/<이름>/a', '/Us' + 'ers/사용자/a', '/ho' + 'me/user/a', '/Users/에 있다', '/Users/ 아래', '/home/…', '/Us' + 'ers/...'):
            self.assertFalse(T.HOME.search(s), s)

    # 9
    def test_9_text_type(self):
        self.begin()
        for t in ({'ko': '창을 닫는다.'}, ['창을 닫는다.'], True):
            code, got = self.check(self.m(t))
            self.assertEqual(code, 1, (t, got))
            self.assertIn('글로 쓴다', str(got))
        code, got = self.check(dict(self.m(), steps=[{'id': 's1', 'who': 'CLI', 'do': {'a': 1}, 'src': ['raw:3']}], order='text'))
        self.assertIn('글로 쓴다', str(got))

    # 11
    def test_11_removed_range(self):
        d = 'diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -8,3 +8,2 @@\n x = 1\n-y = 2\n z = 3\n'
        s = cite.Source('pr', write(self.p('d.diff'), d), ['raw'])
        self.assertTrue(s.resolve('a.py:-9')['ok'])
        self.assertFalse(s.resolve('a.py:-8-10')['ok'])
        self.assertTrue(s.resolve('a.py:8-9')['ok'])

    # 12
    def test_12_not_utf8(self):
        os.makedirs(self.p('src'))
        for name, b, ok in (('a.bin', bytes(range(128, 256)) * 3, False), ('k.md', ('한글 글이다. ' * 20).encode('cp949'), False), ('u.md', ('한글 글이다. ' * 20).encode('utf-8') + b'\xff', True)):
            with open(self.p('src', name), 'wb') as f:
                f.write(b)
            code, out, err = run('start', self.p('src', name), '--type', 'general', '--out', self.p('o'))
            self.assertEqual(code, 0 if ok else 2, (name, out, err))
            if not ok:
                self.assertIn('UTF-8', err)

    # 13 · 23
    def test_13_tilde_fence(self):
        for f in ('```', '~~~', '````', '  ~~~'):
            body = '# 설명\n\n' + LONG + '\n\n%sdiff\n%s\n%s\n' % (f, DIFF, f.strip())
            self.assertEqual(route.decide(route.score_text(body, {}, 'a.md'))['type'], 'general', f)

    def test_23_plain_patch(self):
        d = '--- a/config.py\t2024-01-01\n+++ b/config.py\t2024-01-02\n@@ -1,2 +1,2 @@\n-wait = 10\n+wait = 30\n keep = 1\n--- /dev/null\n+++ b/new file.py\n@@ -0,0 +1 @@\n+x = 1\n--- a/gone.py\n+++ /dev/null\n@@ -1 +0,0 @@\n-y = 1\n'
        got = cite.parse_diff(d)
        self.assertEqual([(k, v['add'], v['del'], v['new'], v['gone']) for k, v in got.items()], [('config.py', 1, 1, False, False), ('new file.py', 1, 0, True, False), ('gone.py', 0, 1, False, True)])
        code, out, err = run('start', write(self.p('src', 'w.patch'), d), 'eli5', '--out', self.p('o'), '--slug', 'w')
        self.assertIn('into · pr', out)
        w = self.p('o', '.into', 'w')
        self.assertEqual(json.loads(read(os.path.join(w, 'pack.json')))['source']['kind'], 'pr')
        self.assertIn('     1 +wait = 30', read(os.path.join(w, 'pack.md')))
        write(os.path.join(w, 'model.json'), {'type': 'pr', 'title': '기다림', 'source': 'diff 전체', 'facts': [{'id': 'f1', 't': '`wait`가 30이 됐다', 'src': ['config.py:1']}], 'changes': [{'id': 'c1', 'what': '`wait`', 'before': '10', 'after': '30', 'src': ['config.py:-1', 'config.py:1']}]})
        code, out, _ = run('check', w)
        self.assertEqual(code, 0, out)
        self.assertFalse(cite.has_diff('# 글\n\n--- 줄\n+++ 줄\n'))

    # 19
    def test_19_post_text(self):
        for body in ('1/3 대기는 30초다.\n더 쓴다.\n\n2/3 보관은 90일이다.\n\n3/3 끝이다.\n', '## 글 1\n\n대기는 30초다.\n\n## 글 2\n\n보관은 90일이다.\n\n## 글 3\n\n끝이다.\n', '대기는 30초다. 1/3\n\n보관은 90일이다. 2/3\n\n끝이다. 3/3\n'):
            s = cite.Source('file', write(self.p('t.md'), body), ['raw'])
            r = s.resolve('1/3')
            self.assertIn('30초', r['text'])
            self.assertNotIn('90일', r['text'])
            self.assertIn('90일', s.resolve('2/3')['text'])
            self.begin(body, typ='social-post')
            for t, warn in (('대기는 90초다', 1), ('대기는 30초다', 0)):
                _, got = self.check({'type': 'social-post', 'title': '가', 'source': '글 전체', 'facts': [{'id': 'f1', 't': t, 'src': ['1/3']}], 'claims': [{'id': 'c1', 't': t, 'ev': '주장만', 'src': ['1/3']}]})
                self.assertEqual('근거 구간에 없음' in str(got), bool(warn), (t, got))

    # 22
    def test_22_api_names_are_data(self):
        data = '<p>XMLHttpRequest는 응답을 읽는다. new WebSocket(x)</p><div aria-label="navigator.sendBeacon"></div><script type="application/json">{"t":"XMLHttpRequest · fetch(\'https://a.b\') url(https://a.b)"}</script><script>const INTO = {\n"t":"new EventSource(x)"\n};\nvar a=1;</script>'
        self.assertEqual(lint.safety('<html>' + data + '</html>', True), [])
        for bad in ('<script>new XMLHttpRequest()</script>', '<script>fetch("https://a.b")</script>', '<button onclick="fetch(\'//a.b\')">a</button>', '<style>a{background:url(https://a.b/c.png)}</style>', '<p style="background:url(//a.b/c)">a</p>', '<img alt="가" src="https://a.b/c.png">', '<link rel="x" href="//a.b">'):
            self.assertTrue(lint.safety('<html>' + data + bad + '</html>', True), bad)


class Round4_modes(Work):
    def setUp(self):
        super().setUp()
        self.model(pr_model())

    # 18
    def test_18_quiz_evidence(self):
        j = quiz_json()
        j['questions'][0].update(right='첫 호출에 1234번 켠다', wrong=['시작할 때 1234번 켠다', '아예 켜지 않는다고 한다'])
        code, out, _ = self.render('test', j)
        self.assertEqual(code, 1, out)
        self.assertTrue([x for x in levels(out) if x.startswith('FAIL') and '근거 구간에 없음: 1234' in x], out)
        j = quiz_json()
        j['questions'][1].update(must=['retries가 3이다, 1234'], model='1234까지 본다')
        _, out, _ = self.render('test', j)
        self.assertTrue([x for x in levels(out) if x.startswith('FAIL') and 'questions[2].must' in x and '1234' in x], out)
        j = quiz_json()
        m = pr_model()
        m['facts'][0].update(t='도구 목록이 캐시돼 있으면 30초 뒤 로드할 수 있다', src=['raw:9'])
        self.start(write(self.p('src', 'q.md'), '---\ntype: pr\n---\n\n\n\n\n\nThe server may wait 30 seconds when the tool list is cached.\nBefore this change the CLI loaded the server on start.\n' + read(self.src).split('\n', 10)[10]), '--type', 'pr')
        self.model(m)
        j = quiz_json()
        for q in j['questions']:
            if q['type'] == 'choice':
                q.update(right='30분 기다린다', wrong=['60초 기다린다', '안 기다린다'])
        j['questions'][2]['right'] = '30초 기다린다'
        code, out, _ = self.render('test', j)
        bad = [x for x in levels(out) if x.startswith('FAIL') and '단위가 근거와 다르다: 30분' in x]
        self.assertEqual((code, len(bad)), (1, 2), out)
        self.start(self.src)
        self.model(pr_model())
        j = quiz_json()
        j['questions'][0].update(explain='1234는 다른 사실의 값이다')
        code, out, err = self.render('test', j)
        self.assertTrue([x for x in levels(out, err) if x.startswith('WARN') and '1234' in x], out + err)

    # 26
    def test_26_empty_table(self):
        self.start(write(self.p('src', 's.md'), '# 설정\n\n색은 빨강이다.\n'), '--type', 'community-post')
        d = self.p('f')
        for f in os.listdir(os.path.join(FIX, 'formats')):
            write(os.path.join(d, f), read(os.path.join(FIX, 'formats', f)))
        s = read(os.path.join(d, 'pr.md')).replace('| run | 어떻게 | run | steps | 3×85 | 순서 |', '| run | 상황 | cases | table:입력,전,후 | 5×90! | 표 |')
        write(os.path.join(d, 'pr.md'), s)
        old, os.environ['INTO_FORMATS'] = os.environ['INTO_FORMATS'], d
        formats._cache.clear()
        try:
            self.start(self.src)
            self.model(dict(pr_model(), cases=[]))
            code, out, err = self.render('eli5', dict(eli5(), run=None, cases=[]))
            self.assertEqual(code, 0, out + err)
            self.assertIn('표가 비었다', err)
            code, out, err = self.render('eli5', dict(eli5(), run=None, cases=[], one=''))
            self.assertEqual(code, 1)
        finally:
            os.environ['INTO_FORMATS'] = old
            formats._cache.clear()


class Round5(Tmp):
    """3차 리뷰 (번호 = into-s3.out.md)"""
    BODY, begin, m, check, eli5 = Review.BODY, Review.begin, Review.m, Review.check, Review.eli5

    def one(self, body, t, src):
        self.begin(body)
        return self.check(dict(self.m(t, src), nodes=[], edges=[]))[1]

    # 1
    def test_1_sign_lost(self):
        body = '# 결과\n\n오류는 -30%였다.\n비용이 -5%로 줄었다.\n`head -30`을 쓴다.\n'
        for t, src, warn in (('오류는 30%다', 'raw:3', 1), ('오류는 -30%다', 'raw:3', 0), ('오류가 30% 줄었다', 'raw:3', 0), ('오류는 마이너스 30%다', 'raw:3', 0), ('앞 30줄을 본다', 'raw:5', 0)):
            got = self.one(body, t, (src,))
            self.assertEqual('부호' in str(got), bool(warn), (t, got))

    def test_1_unit_needs_evidence(self):
        body = '# 실험 12\n\n서버는 기다린다.\nWAIT_SECONDS = 45\n대기는 30초다.\n2026-11-03에 바꿨다.\n| 모형 | 정확도(%) |\n|---|---|\n| 가 | 29.4 |\n\nMAX_MS = 120_000\n2번 본다.\nLIMIT_MS = 3_600_000\n1번 쓴다.\n'
        for t, src, warn in (('서버는 12초 기다린다', ('raw:3',), 1), ('서버는 12초 기다린다', ('raw:1',), 1), ('서버는 12초 기다린다', ('raw:1-3',), 1), ('실험 12다', ('raw:1',), 0), ('45초 기다린다', ('raw:4',), 0), ('30초 기다린다', ('raw:5',), 0),
                             ('30분 기다린다', ('raw:5',), 1), ('2026년 11월 3일에 바꿨다', ('raw:6',), 0), ('정확도 29.4%', ('raw:7-9',), 0), ('정확도 29.4%', ('raw:9',), 0), ('정확도 29.4분', ('raw:9',), 1), ('2분 기다린다', ('raw:11',), 1), ('2시간 기다린다', ('raw:11',), 1)):
            got = self.one(body, t, src)
            self.assertEqual(bool(got), bool(warn), (t, src, got))

    def test_1_title_number_of_folder(self):
        write(self.p('핵심개념12가지', 'a.md'), '# 글\n\n서버는 기다린다.\n')
        run('start', self.p('핵심개념12가지'), 'eli5', '--type', 'general', '--out', self.p('o'), '--slug', 'w', '--no-fetch')
        self.w = self.p('o', '.into', 'w')
        for t, warn in (('서버는 12초 기다린다', 1), ('개념은 12개다', 0)):
            _, got = self.check(dict(self.m(t, ('a.md:3',)), nodes=[], edges=[]))
            self.assertEqual(bool(got), bool(warn), (t, got))

    # 2
    def test_2_empty_copy(self):
        self.begin()
        self.check(self.m())
        write(os.path.join(self.w, 'source.md'), '')
        for a in (('check', self.w), ('render', self.w, 'eli5')):
            code, out, _ = run(*a)
            self.assertEqual(code, 1)
            self.assertIn('원문 사본이 비었다', out)

    # 9
    def test_9_number_text(self):
        self.begin()
        for t in (30, 3.5, True, None):
            code, got = self.check(self.m(t))
            self.assertEqual(code, 1, (t, got))

    # 10
    def test_10_folder_changed(self):
        write(self.p('d', 'README.md'), '# 글\n\n시작할 때 켠다.\n')
        write(self.p('d', 'b.md'), '# 다른 글\n')
        go = lambda: run('start', self.p('d'), 'eli5', '--type', 'general', '--out', self.p('o'), '--slug', 'w', '--no-fetch')
        go()
        self.w = self.p('o', '.into', 'w')
        self.check(dict(self.m('시작할 때 켠다', ('README.md:3',)), nodes=[], edges=[]))
        write(self.p('d', 'b.md'), '# 바뀐 글\n')                              # 근거로 쓰지 않은 파일
        _, out, err = self.eli5('시작할 때 켠다')
        self.assertNotIn('바뀌었다', out + err)
        write(self.p('d', 'README.md'), '# 글\r\n\r\n시작할 때 켠다.\r\n')
        self.assertNotIn('바뀌었다', run('check', self.w)[1])
        write(self.p('d', 'README.md'), '# 글\n\n시작할 때 끈다.\n')
        for a in (('check', self.w), ('render', self.w, 'eli5')):
            _, out, err = run(*a)
            self.assertIn('start 뒤에 바뀌었다(README.md)', out + err)
        _, out, _ = go()
        self.assertIn('원문이 바뀌었다', out)
        self.assertIn('원문이 바뀌었다', ''.join(run('render', self.w, 'eli5')[1:]))
        self.check(dict(self.m('시작할 때 끈다', ('README.md:3',)), nodes=[], edges=[]))
        self.assertNotIn('바뀌었다', run('check', self.w)[1])

    # 27
    def git(self, *a):
        import subprocess
        r = subprocess.run(['git', '-C', self.p('r'), '-c', 'user.name=a', '-c', 'user.email=a@b.c', '-c', 'commit.gpgsign=false'] + list(a), stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_27_local_work_is_private(self):
        write(self.p('r', 'a.md'), '# 글\n\n시작할 때 켠다.\n')
        self.git('init', '-q')
        self.git('remote', 'add', 'origin', 'https://github.com/acme/tool.git')
        self.git('add', '.')
        self.git('commit', '-q', '-m', 'a')
        real, asked = pack.sh, []

        def fake(args, *a, **k):
            if args[0] != 'gh':
                return real(args, *a, **k)
            asked.append(args[1])
            return (True, 'PUBLIC', '') if args[1] == 'repo' else (False, '', 'Not Found')
        pack.sh = fake
        self.addCleanup(setattr, pack, 'sh', real)

        slug = 'w'

        def start(*a):
            run('start', self.p('r'), 'eli5', '--type', 'general', '--out', self.p('o'), '--slug', slug, *a)
            self.w = self.p('o', '.into', slug)
            p = json.loads(read(os.path.join(self.w, 'pack.json')))
            return p['public'], p['public_why'], p['url']
        self.assertFalse(start()[0], '푸시하지 않은 커밋')
        self.assertIn('api', asked)
        self.assertEqual(start()[2], '')
        self.git('update-ref', 'refs/remotes/origin/main', 'HEAD')
        self.assertEqual(start()[::2], (True, 'https://github.com/acme/tool'))
        write(os.path.join(self.w, 'model.json'), dict(self.m('시작할 때 켠다', ('a.md:3',)), nodes=[], edges=[]))
        show = lambda: self.eli5('시작할 때 켠다')[1]
        self.assertIn('시작할 때 켠다', show())
        self.assertNotIn(NOTICE, show())
        write(self.p('r', '초안.md'), '# 비밀 계획\n')                            # 추적하지 않는 파일
        self.assertIn(NOTICE, show())
        self.assertNotIn('github.com/acme', show())
        ok, why, url = start()
        self.assertEqual((ok, url), (False, ''))
        self.assertIn('초안.md', why)
        self.assertTrue(start('--public')[0])
        os.remove(self.p('r', '초안.md'))
        slug = 'v'                                                            # --public을 준 폴더와 다른 이름으로
        self.assertTrue(start()[0])
        write(self.p('r', 'a.md'), '# 글\n\n시작할 때 켠다.\n고쳤다.\n')            # 고친 파일
        self.assertFalse(start()[0])
        self.git('commit', '-q', '-a', '-m', 'b')
        self.assertFalse(start()[0], '새 커밋은 원격에 없다')
        write(self.p('r', 'into-out', 'x.md'), '우리가 만든 결과\n')
        self.git('update-index', '--assume-unchanged', 'a.md')
        self.assertTrue(pack.unpublished(self.p('r')))                         # git status가 숨긴 파일
        self.git('update-index', '--no-assume-unchanged', 'a.md')
        self.git('update-ref', 'refs/remotes/origin/main', 'HEAD')
        self.assertTrue(start()[0])
        self.assertNotIn('into-out/x.md', cite.list_files(self.p('r')))

    # 29
    def test_29_heading_is_its_section(self):
        body = '# 접속\n대기는 30초다.\n보관은 90일이다.\n\n# 끝\n\n한도는 7,000개다.\n'
        for t, src, warn in (('대기는 90초다', ('raw:2', '접속'), 1), ('대기는 30초다', ('raw:2', '접속'), 0), ('보관은 90일이다', ('접속',), 0), ('한도는 7,000개다', ('접속',), 1), ('한도는 7,000개다', ('raw:2', 'https://a.b/c'), 1),
                             ('보관은 90일이다', ('보관은 90일이다',), 0), ('한도는 7,000개다', ('보관은 90일이다',), 1), ('보관은 90일이다', ('s.md#접속',), 0), ('한도는 7,000개다', ('s.md#접속',), 1), ('한도는 7,000개다', ('s.md',), 0)):
            got = self.one(body, t, src)
            self.assertEqual(bool(got), bool(warn), (t, src, got))
        _, out, err = self.eli5('대기는 90초다')
        self.one(body, '대기는 30초다', ('raw:2', '접속'))
        _, out, err = self.eli5('한도는 7,000개다')
        self.assertIn('근거 구간에 없음: 7,000', err)
        s = cite.Source('file', self.p('src', 's.md'), ['raw'])
        self.assertEqual([n for n, _ in s.resolve('접속')['lines']], [1, 2, 3, 4])
        self.assertEqual([n for n, _ in s.resolve('대기는 30초다. 보관은')['lines']], [2, 3])

    # 32
    def test_32_srt_block(self):
        srt = '1\n00:00:01,000 --> 00:00:03,000\n대기는 30초다\n그다음 줄\n\n2\n00:00:03,500 --> 00:00:05,000\n보관은 90일이다\n\n3\n00:00:06,000 --> 00:00:08,000\n끝이다\n'
        s = cite.Source('file', write(self.p('a.srt'), srt), ['raw'])
        r = s.resolve('[00:01]')
        self.assertIn('30초', r['text'])
        self.assertIn('그다음 줄', r['text'])
        self.assertNotIn('90일', r['text'])
        r = s.resolve('[00:01-00:08]')
        self.assertTrue('90일' in r['text'] and '끝이다' in r['text'])
        s = cite.Source('file', write(self.p('c.md'), '- 00:01 가\n- 00:05 나\n\n[00:01] 대기는 30초다\n[00:03] 보관은 90일이다\n[00:05] 끝이다\n[00:09] 다음\n'), ['raw'])
        self.assertEqual([n for n, _ in s.resolve('[00:01-00:05]')['lines']], [1, 2, 4, 5, 6])
        s = cite.Source('file', write(self.p('b.md'), '# 영상\n\n[00:01] 대기는 30초다\n[00:05] 보관은 90일이다\n이어진 말\n\n## [01:00] 둘째\n\n한도는 7개다\n\n## [02:00] 셋째\n\n끝\n'), ['raw'])
        self.assertNotIn('90일', s.resolve('[00:01]')['text'])
        self.assertIn('이어진 말', s.resolve('[00:05]')['text'])
        self.assertIn('7개', s.resolve('[01:00]')['text'])
        self.assertNotIn('끝', s.resolve('[01:00]')['text'])

    # 33
    def test_33_quoted_git_path(self):
        q = ''.join('\\%03o' % b for b in '설정'.encode('utf-8'))
        d = 'diff --git "a/%s.py" "b/%s.py"\n--- "a/%s.py"\n+++ "b/%s.py"\n@@ -1 +1,2 @@\n-wait = 10\n+wait = 30\n+s = "a\\303"\n' % (q, q, q, q)
        for s in (d, d[d.index('---'):]):
            got = cite.parse_diff(s)
            self.assertEqual(list(got), ['설정.py'], got)
            self.assertEqual(got['설정.py']['hunks'][0]['rows'][-1][3], 's = "a\\303"')          # 본문은 그대로
        code, out, err = run('start', write(self.p('src', 'w.patch'), d), 'eli5', '--out', self.p('o'), '--slug', 'w')
        self.assertIn('into · pr', out)
        w = self.p('o', '.into', 'w')
        write(os.path.join(w, 'model.json'), {'type': 'pr', 'title': '기다림', 'source': 'diff 전체', 'facts': [{'id': 'f1', 't': '`wait`가 30이 됐다', 'src': ['설정.py:1']}], 'changes': [{'id': 'c1', 'what': '`wait`', 'before': '10', 'after': '30', 'src': ['설정.py:1']}]})
        code, out, _ = run('check', w)
        self.assertEqual(code, 0, out)

    # 34
    def test_34_skill_head(self):
        s = '---\nname: tidy-notes\ndescription: Use when the notes are messy.\n---\n# Tidy notes\n\n' + LONG
        for name in ('tidy-notes.md', 'source.md'):
            code, out, err = run('start', write(self.p('src', name), s), 'eli5', '--out', self.p('o'), '--slug', name[:-3])
            self.assertIn('into · skill', out, err)
            self.assertIn('전체', re.search(r'- W/pack.md.*', out).group(0))
        meta, st = T.front_matter('---\nname: a\n---\n글\n')
        self.assertEqual(route.decide(route.score_text('글', meta, 'a.md'))['type'], 'general')

    # 35
    def test_35_pr_head(self):
        head, calls, real = ['aaa111'], [], pack.sh

        def fake(args, *a, **k):
            calls.append(args)
            if args[:3] == ['gh', 'pr', 'diff']:
                return True, DIFF, ''
            if args[:3] == ['gh', 'repo', 'view']:
                return True, 'PUBLIC', ''
            if 'headRefOid' in args:
                return (True, head[0] + '\n', '') if head[0] else (False, '', 'offline')
            return True, json.dumps({'title': '바꾼다', 'body': '본문 ' + head[0], 'url': 'https://github.com/a/b/pull/7', 'headRefOid': head[0], 'number': 7, 'changedFiles': 1}), ''
        pack.sh = fake
        self.addCleanup(setattr, pack, 'sh', real)

        def start(*a):
            del calls[:]
            code, out, err = run('start', 'https://github.com/a/b/pull/7', 'eli5', '--out', self.p('o'), '--slug', 'w', *a)
            self.assertEqual(code, 0, err)
            return out, read(self.p('o', '.into', 'w', 'source.md'))
        out, body = start()
        self.assertIn('읽은 PR 커밋 aaa111', out)
        out, body = start()
        self.assertEqual(len(calls), 1)                                        # head만 물었다
        self.assertNotIn('확인하지 못했다', out)
        self.assertIn('본문 aaa111', body)
        write(self.p('o', '.into', 'w', 'model.json'), {'type': 'pr'})
        head[0] = 'bbb222'
        out, body = start()
        self.assertIn('읽은 PR 커밋 bbb222', out)
        self.assertIn('원문이 바뀌었다', out)
        self.assertIn('본문 bbb222', body)
        for a in (('--no-fetch',), ()):
            head[0] = ''
            out, body = start(*a)
            self.assertIn('읽은 PR 커밋 bbb222(새 커밋이 있는지 확인하지 못했다)', out)
            self.assertIn('본문 bbb222', body)

    def test_lint_counts_lines(self):
        f = write(self.p('src', 's.md'), self.BODY)
        r = write(self.p('r.md'), '**글 · 설정** — 글은 8줄이다\n')
        code, out, err = run('lint', r, '--source', f, '--type', 'general', '--mode', 'eli5')
        self.assertNotIn('INTO_DEBUG', out + err)


class Round5_modes(Work):
    def setUp(self):
        super().setUp()
        self.model(pr_model())

    # 28
    def test_28_borrowed_figure_text(self):
        j = dict(eli5(), pic=[{'id': 'e2', 't': '60초 뒤 켠다'}, 'e1'])
        write(os.path.join(self.w, 'eli5.json'), j)
        for mode in ('html', 'interactive'):
            code, out, err = self.render(mode, {'one': j['one']})
            self.assertEqual(code, 1, (mode, out + err))
            self.assertTrue([x for x in levels(out) if x.startswith('FAIL') and 'eli5.json의 값' in x and '60' in x], (mode, out))
        write(os.path.join(self.w, 'eli5.json'), dict(j, pic=[{'id': 'e2', 't': '1234번 켠다'}, 'e1']))
        _, out, err = self.render('html', {'one': j['one']})
        self.assertIn('근거 구간에 없음: 1234', out + err)
        write(os.path.join(self.w, 'eli5.json'), dict(j, pic=[{'id': 'e2', 't': '첫 호출에'}, 'e1']))
        _, out, err = self.render('html', {'one': j['one']})
        self.assertNotIn('eli5.json의 값', out + err)

    # 29
    def test_29_every_key_is_compared(self):
        for key, x in (('changes', {'after': '1234'}), ('cases', {'after': '1234번 켠다'}), ('edges', {'t': '1234번 켠다'}), ('steps', {'do': '1234번 본다'})):
            m = pr_model()
            m[key][-1].update(x)
            self.assertIn('근거 구간에 없음: 1234', self.model(m)[1], key)
        self.assertNotIn('근거 구간', self.model(pr_model())[1])

    def test_fixed_scenes(self):
        s = [dict(x, chapter='장 %d' % i, next='그래서?') for i, x in enumerate(scenes())]
        fixed = {'say': '안녕하세요.', 'visual': '얼굴', 'fixed': True}
        s = [dict(fixed, slot='hook', chapter='여는 말')] + [x for x in s if x['slot'] != 'hook'] + [dict(fixed, slot='outro', say='감사합니다!', chapter='닫는 말')]
        s[-2].pop('next')
        for x in s:
            x.pop('caption', None)                                              # video는 자막 칸이 필수가 아니다
        _, out, err = self.render('video', {'scenes': s, 'check': 'a → b', 'minutes': 0.2})
        w = '\n'.join(levels(out, err))
        for bad in ('`title`', '`caption`', '훅에 근거', '챕터 끝에', '근거(`f`)가 없다'):
            self.assertNotIn(bad, w)
        s[0].pop('fixed')
        s[-1].pop('fixed')
        _, out, err = self.render('video', {'scenes': s, 'check': 'a → b', 'minutes': 0.2})
        w = '\n'.join(levels(out, err))
        for bad in ('scenes[1]: `title`', '훅에 근거', '챕터 끝에'):
            self.assertIn(bad, w)
        self.assertNotIn('`caption`', w)

    def test_order_says_whole_step(self):
        _, out, _ = run('start', self.src, 'eli5', '--out', self.p('o2'))
        self.assertIn('단계 전체가 조건일 때만', out)


class Round6(Tmp):
    """4차 확인에서 남은 것 (번호 = into-s4.out.md)"""
    BODY, begin, m, check, eli5, one, git = Review.BODY, Review.begin, Review.m, Review.check, Review.eli5, Round5.one, Round5.git

    # 1
    def test_1_convert_same_dimension(self):
        body = '# 서버\n\n서버는 45초 기다리고 동시 접속은 1,800명이다.\n30번 본다.\n대기는 1800초다.\n보관은 2GB다.\n2048번 읽는다.\nLIMIT = 3600\n1번 쓴다.\n정확도는 0.45이고 지연은 0.62초다.\n62명이 썼다.\n1,800 users wait 45 seconds.\n10–30초를 기다린다.\n0.5시간 쉰다.\n'
        for t, src, warn in (('30분 기다린다', 'raw:3', 1), ('1,800초 기다린다', 'raw:3', 1), ('1,800초 기다린다', 'raw:12', 1), ('1,800명이 접속한다', 'raw:3', 0), ('45초 기다린다', 'raw:3', 0), ('30분 기다린다', 'raw:5', 0),
                             ('1시간 기다린다', 'raw:8', 1), ('2,048MB까지 보관한다', 'raw:6', 0), ('정확도는 45%다', 'raw:10', 0), ('62% 걸린다', 'raw:10', 1), ('45초 걸린다', 'raw:10', 1), ('10초 기다린다', 'raw:13', 0), ('30분 쉰다', 'raw:14', 0)):
            got = self.one(body, t, (src,))
            self.assertEqual(bool(got), bool(warn), (t, src, got))

    def test_1_convert_keeps_sign(self):
        body = '# 서버\n\n요청 500건에서 지연 중앙값이 −0.5초 변했다.\n지연이 0.5초 줄었다.\n'
        for t, src, warn in (('지연이 +500ms 변했다', 'raw:3', 1), ('지연이 500ms 늘었다', 'raw:3', 1), ('지연이 −500ms 변했다', 'raw:3', 0), ('지연이 500ms 줄었다', 'raw:3', 0), ('지연이 500ms 줄었다', 'raw:4', 0)):
            got = self.one(body, t, (src,))
            self.assertEqual(bool(got), bool(warn), (t, src, got))

    # 2
    def test_2_front_matter_only(self):
        self.begin('---\ntitle: 설정\ntype: note\n---\n' + self.BODY)
        self.assertEqual(self.check(dict(self.m('설정이다', ('raw:2',)), nodes=[], edges=[]))[0], 0)
        self.eli5('설정이다')
        write(os.path.join(self.w, 'source.md'), '---\ntitle: 설정\n---\n\n')
        for a in (('check', self.w), ('render', self.w, 'eli5')):
            code, out, _ = run(*a)
            self.assertEqual(code, 1)
            self.assertIn('원문 사본이 비었다', out)
        code, _, err = run('start', write(self.p('src', 'e.md'), '---\ntitle: 설정\n---\n'), 'eli5', '--out', self.p('o'))
        self.assertEqual(code, 2)
        self.assertIn('입력이 비었다', err)

    # 10
    def test_10_mode_file_changed(self):
        write(self.p('d', 'README.md'), '# 글\n\n시작할 때 켠다.\n')
        write(self.p('d', 'notes.md'), '# 색\n\n빨강이다.\n')
        write(self.p('d', 'b.md'), '# 다른 글\n')
        go = lambda: run('start', self.p('d'), 'eli5', '--type', 'general', '--out', self.p('o'), '--slug', 'w', '--no-fetch')
        go()
        self.w = self.p('o', '.into', 'w')
        self.check(dict(self.m('시작할 때 켠다', ('README.md:3',)), nodes=[], edges=[]))
        cell = {'t': '빨강이다', 'src': ['notes.md:3']}
        _, out, err = self.eli5('', one=cell)
        self.assertNotIn('바뀌었다', out + err)
        self.eli5('', 'html', one=cell)
        write(self.p('d', 'b.md'), '# 바뀐 글\n')
        write(self.p('d', 'notes.md'), '# 색\n\n파랑이다.\n')
        for mode in ('eli5', 'html'):
            self.assertIn('start 뒤에 바뀌었다(notes.md)', ''.join(run('render', self.w, mode)[1:]), mode)
        self.assertNotIn('바뀌었다', run('check', self.w)[1])                    # 모델은 쓰지 않은 파일
        _, out, _ = go()
        self.assertNotIn('원문이 바뀌었다', out)
        for mode in ('eli5', 'html'):
            self.assertIn('eli5.json: 원문이 바뀌었다', ''.join(run('render', self.w, mode)[1:]), mode)
        _, out, err = self.eli5('', one={'t': '파랑이다', 'src': ['notes.md:3']})
        self.assertNotIn('바뀌었다', out + err)

    # 27
    def test_27_ignored_folder_is_private(self):
        write(self.p('r', '.gitignore'), 'drafts/\n*.txt\n')
        write(self.p('r', 'a.md'), '# 글\n\n시작할 때 켠다.\n')
        write(self.p('r', 'drafts', 'p.md'), '# 초안\n\n비밀 계획이다.\n')
        write(self.p('r', 'notes', 'n.txt'), '메모다.\n')
        self.git('init', '-q')
        self.git('remote', 'add', 'origin', 'https://github.com/acme/tool.git')
        self.git('add', '.')
        self.git('commit', '-q', '-m', 'a')
        self.git('update-ref', 'refs/remotes/origin/main', 'HEAD')
        real = pack.sh
        pack.sh = lambda args, *a, **k: real(args, *a, **k) if args[0] != 'gh' else (True, 'PUBLIC', '') if args[1] == 'repo' else (False, '', 'Not Found')
        self.addCleanup(setattr, pack, 'sh', real)

        def start(*d):
            run('start', self.p('r', *d), 'eli5', '--type', 'general', '--out', self.p('o'), '--slug', 'w' + ''.join(d))
            p = json.loads(read(self.p('o', '.into', 'w' + ''.join(d), 'pack.json')))
            return p['public'], p['url']
        self.assertEqual(start(), (True, 'https://github.com/acme/tool'))
        self.assertEqual(start('drafts'), (False, ''))
        self.assertEqual(start('notes'), (False, ''))                            # 추적하는 파일이 없다
        self.git('add', '-f', 'notes/n.txt', 'drafts/p.md')
        self.git('commit', '-q', '-m', 'b')
        self.git('update-ref', 'refs/remotes/origin/main', 'HEAD')
        self.assertEqual(start('notes')[0], True)

    # 29
    def test_29_unknown_heading(self):
        body = '# 접속\n대기는 30초다.\n\n# 끝\n\n보관은 90초다.\n'
        got = self.one(body, '대기는 90초다', ('raw:2', 's.md#접쏙'))
        self.assertTrue([x for x in got if x.startswith('FAIL') and '제목 `접쏙`이 없다' in x], got)
        self.assertFalse(self.one(body, '대기는 30초다', ('s.md#접속',)))
        write(self.p('d', 'a.md'), body)
        s = cite.Source('dir', self.p('d'))
        self.assertTrue(s.resolve('a.md#끝')['ok'] and s.resolve('a.md')['ok'])
        self.assertFalse(s.resolve('a.md#끗')['ok'])
        d = 'diff --git a/d.md b/d.md\n--- a/d.md\n+++ b/d.md\n@@ -1,4 +1,5 @@\n # 접속\n-대기는 30초다.\n+대기는 90초다.\n \n # 끝\n+보관은 7일이다.\n'
        s = cite.Source('pr', write(self.p('x.md'), '# PR\n\n' + d), ['raw'])
        r = s.resolve('d.md#접속')
        self.assertTrue(r['ok'] and '90초' in r['text'] and '7일' not in r['text'], r)
        self.assertFalse(s.resolve('d.md#접쏙')['ok'])

    # 32
    def test_32_srt_boundary(self):
        s = cite.Source('file', write(self.p('a.srt'), '1\n00:00:01,000 --> 00:00:03,000\n대기는 30초다\n\n2\n00:00:03,000 --> 00:00:05,400\n보관은 90일이다\n\n3\n00:00:05,500 --> 00:00:08,000\n끝이다\n'), ['raw'])
        for at, yes, no in (('[00:01]', '30초', '90일'), ('[00:03]', '90일', '30초'), ('[00:05]', '끝이다', '90일'), ('[00:01-00:03]', '30초', '90일'), ('[00:01-00:05]', '90일', '끝이다'), ('[00:03-00:08]', '끝이다', '30초')):
            r = s.resolve(at)
            self.assertTrue(yes in r['text'] and no not in r['text'] and not r['warn'], (at, r))
        r = s.resolve('[00:08]')
        self.assertEqual((r['text'], '끝' in r['warn']), ('', True), r)

    # 35
    def test_35_partial_update(self):
        head, works, real = ['aaa111'], {'diff': True, 'view': True}, pack.sh

        def fake(args, *a, **k):
            if args[:3] == ['gh', 'pr', 'diff']:
                return (True, DIFF + '# ' + head[0] + '\n', '') if works['diff'] else (False, '', 'timeout')
            if args[:3] == ['gh', 'repo', 'view']:
                return True, 'PUBLIC', ''
            if 'headRefOid' in args:
                return True, head[0] + '\n', ''
            return (True, json.dumps({'title': '바꾼다', 'body': '본문 ' + head[0], 'url': 'https://github.com/a/b/pull/7', 'headRefOid': head[0], 'number': 7, 'changedFiles': 1}), '') if works['view'] else (False, '', 'timeout')
        pack.sh = fake
        self.addCleanup(setattr, pack, 'sh', real)

        def start(slug='w', *a):
            code, out, err = run('start', 'https://github.com/a/b/pull/7', 'eli5', '--out', self.p('o'), '--slug', slug, *a)
            self.assertEqual(code, 0, err)
            return out, read(self.p('o', '.into', slug, 'source.md'))
        out, body = start()
        for bad in ('diff', 'view'):
            works[bad], head[0] = False, 'bbb222'
            out, now = start()
            self.assertEqual(now, body, bad)                                   # 옛 사본 그대로
            self.assertIn('읽은 PR 커밋 aaa111', out)
            self.assertIn('bbb222', out)
            self.assertIn('다시 받는다', out)
            works[bad] = True
        out, body = start()
        self.assertIn('읽은 PR 커밋 bbb222\n', out)
        self.assertIn('본문 bbb222', body)
        self.assertIn('+x = 2', body)
        head[0], os_replace = 'ccc333', os.replace                             # 쓰다가 멈춰도 옛 사본이 남는다
        os.replace = lambda *a: (_ for _ in ()).throw(OSError('disk'))
        try:
            run('start', 'https://github.com/a/b/pull/7', 'eli5', '--out', self.p('o'), '--slug', 'w')
        finally:
            os.replace = os_replace
        self.assertEqual(read(self.p('o', '.into', 'w', 'source.md')), body)
        mine = write(self.p('o', '.into', 'w', 'source.md'), body + '\n사람이 보충했다.\n')
        head[0] = 'bbb222'
        out, now = start()
        self.assertIn('읽은 PR 커밋 bbb222\n', out)
        for head[0] in ('ccc333', 'ddd444'):                                   # 사람이 고친 사본은 덮지 않는다
            out, now = start()
            self.assertEqual(now, body + '\n사람이 보충했다.\n')
            self.assertIn('읽은 PR 커밋 bbb222', out)
            self.assertIn(head[0], out)
            self.assertIn('덮지 않았다', out)
        os.rename(mine, mine + '.old')
        out, now = start()
        self.assertIn('읽은 PR 커밋 ddd444\n', out)
        works['diff'] = False                                                  # 처음부터 diff만 실패
        out, body = start('v')
        self.assertIn('잘린 사본', read(self.p('o', '.into', 'v', 'pack.md')))
        works['diff'] = True
        out, body = start('v')
        self.assertIn('+x = 2', body)
        self.assertNotIn('truncated', body)


class Round6_modes(Work):
    def setUp(self):
        super().setUp()
        self.model(pr_model())

    # 3
    def test_3_chart_number_text(self):
        def warns(v):
            j = deck_json()
            j['slides'][1].update(viz='chart', data={'type': 'hbar', 'axis': '서버 · 켠 수 · 지금', 'items': [{'t': '서버', 'v': v}, {'t': 'CLI', 'v': v}], 'hi': 0})
            return '\n'.join(x.replace('"', '') for x in levels(*self.render('slides', j)[1:]) if x.startswith('WARN') and 'data' in x)
        for v in (1234, 87654):
            self.assertIn(str(v), warns(v))
            for s in (str(v), ' %d ' % v, '{:,}'.format(v)):
                self.assertIn(warns(v), warns(s), s)
        self.assertNotIn('근거 구간', warns('이름'))

    # 18
    def test_18_convert_in_quiz(self):
        m = pr_model()
        m['facts'][0].update(t='도구 목록이 캐시돼 있으면 45초 뒤 로드할 수 있다', src=['raw:9'])
        src = read(self.src).replace('skip the first load', 'wait 45 seconds for 1,800 users').replace('on start.', 'on start, 30 times.')
        _, out, _ = run('start', write(self.p('src', 'q.md'), src), 'test', '--public', '--out', self.p('o'), '--slug', 'q')
        self.w = self.p('o', '.into', 'q')
        self.assertIn('FAIL 0', self.model(m)[1])
        j = quiz_json()
        for q in j['questions']:
            if q['type'] == 'choice':
                q.update(right='45초 기다린다', wrong=['30분 기다린다', '안 기다린다'])
        code, out, err = self.render('test', j)
        self.assertEqual(code, 0, out + err)
        out_file = self.p('o', 'q-test.html')
        os.remove(out_file)
        j['questions'][0].update(right='30분 기다린다', wrong=['45초 기다린다', '안 기다린다'])
        code, out, _ = self.render('test', j)
        self.assertEqual(code, 1, out)
        self.assertTrue([x for x in levels(out) if x.startswith('FAIL') and '근거 구간에 없음: 30분' in x], out)
        self.assertFalse(os.path.exists(out_file))

    def test_18_convert_sign_in_quiz(self):
        m = pr_model()
        m['facts'][0].update(t='요청 500건에서 지연이 −0.5초 변했다', src=['raw:9'])
        src = read(self.src).replace('skip the first load', 'change latency by −0.5초 over 500 requests')
        run('start', write(self.p('src', 'q.md'), src), 'test', '--public', '--out', self.p('o'), '--slug', 'q')
        self.w = self.p('o', '.into', 'q')
        self.assertIn('FAIL 0', self.model(m)[1])
        for right, wrong, want in (('−500ms 변했다', '+500ms 변했다', 0), ('+500ms 변했다', '−500ms 변했다', 1)):
            j = quiz_json()
            for q in j['questions']:
                if q['type'] == 'choice':
                    q.update(right=right, wrong=[wrong, '조금도 안 변했다'])
            code, out, err = self.render('test', j)
            self.assertEqual(code, want, (right, out + err))


class Round4_stuck(Tmp):
    """블라인드 2회차: 처음 쓰는 에이전트가 막힌 곳"""
    BODY, begin, m, check, eli5 = Review.BODY, Review.begin, Review.m, Review.check, Review.eli5

    # 유형
    def test_front_type_wins(self):
        body = '---\ntype: local-file\n---\n# 규칙\n\n' + '자막과 대본, 영상, YouTube 영상, 나레이션, 자막.\n' * 6 + ''.join('[%02d:10] 말한다\n' % i for i in range(9))
        code, out, _ = run('start', write(self.p('r.md'), body), 'eli5', '--out', self.p('o'))
        self.assertEqual(code, 0, out)
        self.assertIn('into · local-file', out)
        self.assertIn('머리말 type', out)

    def test_chosen_type_stays(self):
        body = '---\nsource: https://github.com/a/b/pull/3\n---\n# RFC 3: x\n\nStatus: proposed\n\n## Goals\n\na\n\n## Alternatives\n\nb\n\nPR #3\n'
        f = write(self.p('mix.md'), body)
        self.assertEqual(run('start', f, '--out', self.p('o'))[0], 3)
        self.assertEqual(run('start', f, '--type', 'general', '--out', self.p('o'))[0], 0)
        for _ in range(2):
            code, out, _ = run('start', f, 'html', '--out', self.p('o'))
            self.assertEqual(code, 0, out)
            self.assertIn('into · general × html', out)
        _, out, _ = run('start', f, 'html', '--type', 'pr', '--out', self.p('o'))
        self.assertIn('into · pr', out)

    # 한정어 · 조건
    def test_hedges(self):
        c = cells.Checker('eli5', [], {'terms': [{'w': '실험 기능', 'o': ['experimental']}]}, {}, cite.Source('none', ''), {}, formats.load('general'))
        for hedge, ok, bad in (('must', ('반드시 동의를 받고', '동의를 받아야 한다', '인사를 넣어야 한다', '필수다', '금지다', '`must`'), ('동의를 받는다', '분야다')),
                               ('should', ('쉬워야 하고', '권고한다', '못 보게 해야 함', '(권고)'), ('쉽다',)),
                               ('can', ('필요할지는 불확실하다', '아직 못 찾았다', '버려질 수 있다', '가능하다'), ('버린다', '버려진다')),
                               ('default', ('보통 켜져 있다', '대개 켜져 있다', '기본은 켜짐'), ('켜져 있다',)),
                               ('보통', ('대개 그렇다', '흔히 그렇다'), ('그렇다',)),
                               ('sometimes', ('가끔 실패한다',), ('실패한다',)),
                               ('프롬프트가 요구한 형식', ('요구한 형식으로 쓴다',), ('리뷰를 쓴다',))):
            for t in ok:
                self.assertEqual(c.lost_hedge(t, {'hedge': hedge}), '', (hedge, t))
            for t in bad:
                self.assertEqual(c.lost_hedge(t, {'hedge': hedge}), hedge, (hedge, t))
        c.refs = {'f1': {'if': '보통'}, 'f2': {'if': '/experimental로 켜면'}, 'f3': {'if': '종료 사유가 Interrupted'}}
        for f, t, warn in (('f1', '대개 그렇다', 0), ('f1', '그렇다', 1), ('f2', '실험 기능을 켜야 한다', 0), ('f2', '켠다', 1), ('f3', '중단(Interrupted)이면 버린다', 0), ('f3', '버린다', 1)):
            c.issues = []
            c.keeps('w', t, f)
            self.assertEqual(len(c.issues), warn, (f, t, [str(i) for i in c.issues]))
            if warn:
                self.assertIn('찾은 낱말', str(c.issues[0]))

    def test_hedge_message(self):
        self.begin()
        self.check(self.m(hedge='must', cond=None))
        _, _, err = self.eli5('기본값은 30초다')
        self.assertIn('"must"가 빠졌다', err)
        self.assertIn('반드시·필수·…해야', err)

    def test_absolute_words(self):
        self.begin('# 가\n\nIt improves by an absolute 34 points. Both lines are removed.\n\nEvery call waits.\n')
        for t, src, warn in (('절대 차이로 34점이다', 'raw:3', ''), ('두 줄을 모두 지운다', 'raw:3', ''), ('전부 기다린다', 'raw:5', ''), ('항상 34점이다', 'raw:3', '`항상`'), ('전부 34다', 'raw:5', '')):
            _, got = self.check(dict(self.m(t, (src,)), nodes=[], edges=[]))
            self.assertIn(warn, str([x for x in got if '근거 줄에는 없다' in x]), t)
            if not warn:
                self.assertFalse([x for x in got if '근거 줄에는 없다' in x], (t, got))
        self.begin('# 가\n\n값은 34다.\n')
        _, got = self.check(dict(self.m('전부 34다', ('raw:3',)), nodes=[], edges=[]))
        self.assertIn('`전부`', str(got))                                   # 묶음 이름이 아니라 그 낱말

    # 숫자
    def test_numbers_in_names(self):
        self.begin('# 가\n\n대기는 30초다.\n\n예: `ep02-핵심개념5가지/cards`, 핵심개념5가지.\n\nCLI가 서버에 묻는다.\n')
        _, got = self.check(dict(self.m('대기는 30초, 5초짜리 예', ('raw:3',)), nodes=[], edges=[]))
        self.assertNotIn('근거 구간에 없음', str(got))
        got = []
        for t in ('범위: 리뷰 호출만. --ping은 뺐다 · SKILL.md:16-18, 38', 'raw:16-18, 38 참고', 'src/a.py:7'):
            M.check_numbers(t, lambda f, counted=False: False, 'w', lambda *a: got.append(a))
        self.assertEqual(got, [])
        M.check_numbers('a.md:7, 30초', lambda f, counted=False: False, 'w', lambda *a: got.append(a))
        self.assertEqual(len(got), 1)

    def test_wide_evidence(self):
        self.begin('# 가\n\n' + '대기는 30초다.\n' * 90)
        _, got = self.check(dict(self.m('대기는 30초다', ('raw:3-80',)), nodes=[], edges=[]))
        self.assertIn('78줄', str(got))
        _, got = self.check(dict(self.m('대기는 30초다', ('raw:3-62',)), nodes=[], edges=[]))
        self.assertEqual(got, [])


class Round4_cells(Work):
    def setUp(self):
        super().setUp()
        self.model(pr_model())

    def test_odd_lanes(self):
        _, out, err = self.model(dict(pr_model(), lanes=[None, 3, True, ['a'], '레인']))
        self.assertNotIn('INTO_DEBUG', out + err)

    def test_qa_shape_is_fail_not_crash(self):
        old, os.environ['INTO_FORMATS'] = os.environ['INTO_FORMATS'], os.path.join(SKILL, 'formats')
        try:
            for bad in ('글만 쓴 질문', {'t': '글', 'f': ['f1']}, {'q': '질문', 'f': ['f1']}):
                code, out, err = self.render('interactive', {'ask': [bad]})
                self.assertIn('`{"q":"질문","a":"답"}`으로 쓴다', out + err, bad)
                self.assertNotIn('INTO_DEBUG', out + err)
            code, out, err = self.render('interactive', {'cases': [['입력 하나만']]})
            self.assertIn('칸이 1개다', out + err)
            self.assertNotIn('INTO_DEBUG', out + err)
        finally:
            os.environ['INTO_FORMATS'] = old

    def test_id_is_evidence(self):
        _, out, err = self.render('eli5', dict(eli5(), run=[{'id': 's1', 't': 'CLI가 목록을 본다'}, {'id': 's2', 't': '첫 호출에 서버를 켠다'}]))
        self.assertNotIn('근거(`f`) 없는 칸', err)
        self.assertIn('src/cache.rs:11-12', out)

    def test_doc_steps_by_id(self):
        m = pr_model()
        m['steps'] = [{'id': 's1', 'who': 'CLI', 'do': '목록을 본다', 'fail': '`done` 없음', 'if': '캐시됨', 'src': ['src/cache.rs:11']}, {'id': 's2', 'who': 'CLI', 'do': '서버를 켠다', 'src': ['src/cache.rs:12']}]
        self.model(m)
        code, out, err = self.render('doc', {'one': [{'t': '도구 목록이 캐시돼 있으면 첫 로드를 건너뛸 수 있다', 'f': ['f1']}], 'steps': ['s1', 's2']})
        self.assertEqual(code, 0, out + err)
        md = read(self.p('o', 'w-doc.md'))
        self.assertIn('1. CLI — 목록을 본다(캐시됨) ✗ `done` 없음', md)
        self.assertIn('2. CLI — 서버를 켠다\n', md)

    def test_qa_mark(self):
        c = cells.Checker('interactive', [], {}, {}, cite.Source('none', ''), {}, formats.load('pr'))
        c.refs = {'f1': {'id': 'f1', 't': '가', 'mark': '추정', 'src': []}}
        row = {'key': 'ask', 'form': 'qa', 'n': 3, 'chars': 90, 'free': True, 'cols': None, 'optional': False, 'required': False}
        got = c.cell(row, [{'q': '왜?', 'a': '그래서다', 'f': ['f1']}, {'q': '왜?', 'a': '추정이지만 그래서다', 'f': ['f1']}])
        self.assertEqual([x['a'] for x in got], ['그래서다 (추정)', '추정이지만 그래서다'])

    def test_edge_cond(self):
        for t, c, want in (('막히면 힌트 요청', '막히면', ''), ('캐시 조회', '캐시가 있으면', '캐시가 있으면'), ('세 조건이 모두 맞으면 보냄', '세 조건이 모두 참일 때', ''), ('보냄', '막히면', '막히면'), ('읽기 전 중단이면 버림', '읽기 전 중단', '')):
            self.assertEqual(textmodes.edge_cond({'t': t, 'if': c}), want, t)

    def test_node_names_once(self):
        a = 'CLI ─(묻는다)▶ 서버 ─(답)▶ CLI'
        self.assertEqual(T.count_result('```\n' + a + '\nCLI ─(끝 (추정))▶ 서버\n```\n'), T.count(a) + T.count('CLI (끝 (추정)) 서버') - 2 * T.count('CLI') - T.count('서버'))
        _, out, err = self.render('eli5', eli5())
        self.assertEqual(int(re.search(r'글자 ([\d,]+)/', err).group(1)), T.count_result(out))

    def test_over_limit_says_where(self):
        m = pr_model()
        m['edges'][1].update({'if': '도구 목록이 캐시돼 있고 게이트가 켜져 있고 첫 호출이 아직 없고 ' * 12})
        self.model(m)
        code, out, _ = self.render('eli5', eli5())
        self.assertEqual(code, 1)
        self.assertRegex(out, r'그림 `pic` \d+자 = 간선 글 \d+ · 뒤에 붙은 조건\(if\) \d+ · 노드 이름과 괄호 \d+')

    def test_inherit(self):
        self.render('eli5', dict(eli5(), size={'t': '작은 변경이다', 'f': ['f1']}, pic=['e1', {'id': 'e2', 't': '첫 호출 때'}]))
        code, out, err = self.render('html', {})
        self.assertEqual(code, 0, out + err)
        page = read(self.p('o', 'w-html.html'))
        self.assertIn('첫 호출 때', page)                                   # 줄인 간선 글
        self.assertNotIn('첫 호출에 켠다"', page)
        _, out, _ = run('start', self.src, 'html', '--out', self.p('o'), '--slug', 'w', '--public')
        self.assertIn('line 110!(그대로)', out)
        self.assertIn('3×70(그대로)', out)                                   # eli5(3×75)보다 좁지만 쓴 글이 든다
        rows, sp = formats.mode_rows('pr', 'html')
        for n, mode, want in ((70, 'html', True), (71, 'html', False), (70, 'ste', False)):
            self.assertEqual('catch' in cells.same_as_eli5(rows, mode, sp, {'catch': [{'t': '가' * n, 'f': ['f1']}]}), want, (n, mode))
        code, out, err = self.render('html', {'why': False})
        self.assertEqual(code, 0, out + err)

    def test_order_lines(self):
        _, out, _ = run('start', self.src, 'interactive', '--out', self.p('o3'))
        for s in ('큰 길을 먼저', '`6×60` = 6개(행)까지', '간선 id를 넣으면 그 길이 켜진다', '`hedge` 값과 칸에 남길 말', '"nodes":', '2절(쓴 뒤에)'):
            self.assertIn(s, out)
        _, out, _ = run('start', self.src, 'shorts', '--out', self.p('o4'))
        self.assertIn('문장 사이 0.3초', out)
        _, out, _ = run('start', self.src, 'slides', '--out', self.p('o5'))
        self.assertIn('no_chart', out)
        f, old = write(self.p('src', 'c.md'), '# Ask\n\n가\n'), os.environ['INTO_FORMATS']
        os.environ['INTO_FORMATS'] = os.path.join(SKILL, 'formats')
        formats._cache.clear()
        try:
            for typ in ('community-post', 'social-post'):
                _, out, _ = run('start', f, 'eli5', '--type', typ, '--out', self.p('o6'), '--slug', typ)
                self.assertNotIn('"nodes":', out, typ)
                self.assertNotIn('judgment', out)
            _, out, _ = run('start', f, 'interactive', '--type', 'paper-concept', '--out', self.p('o6'), '--slug', 'p')
            for s in ('"nodes":', '`base` = 기준 값', '행 `{"q":'):
                self.assertIn(s, out)
        finally:
            os.environ['INTO_FORMATS'] = old
            formats._cache.clear()

    # model
    def test_model_false_alarms(self):
        for key, x, word in (('zones', {'id': 'z1', 't': '가', 'grade': '목록만', 'src': ['raw:9']}, '`does`가 비었다'),):
            out = M.check(M.normalize(dict(pr_model(), type='codebase', **{key: [x]})), '{}', cite.Source('pr', self.src, ['raw', 'pr.md']), 'codebase')
            self.assertNotIn(word, ' '.join(map(str, out)))
        m = pr_model()
        m['steps'][0]['who'] = '/pr-pass'
        _, out, _ = self.model(m)
        self.assertNotIn('노드 이름과 다르다', out)
        m['steps'][0]['who'] = '다른 쪽'
        _, out, _ = self.model(m)
        self.assertIn('노드 이름과 다르다', out)

    def test_pic_hedge_in_node(self):
        m = pr_model()
        m['nodes'][1]['t'] = '켤 수 있음'
        m['edges'][1]['hedge'] = 'can'
        self.model(m)
        _, _, err = self.render('eli5', eli5())
        self.assertNotIn('한정어', err)

    # test · shorts · slides
    def test_quiz_ties(self):
        j = quiz_json()
        for q in j['questions']:
            if q['type'] == 'choice':
                q.update(right='첫 호출 때 켠다', wrong=['시작 때에는 켠다', '전혀 안 켠다고'])          # 9자 동점
        _, out, err = self.render('test', j)
        self.assertNotIn('가장 긴 문항', out + err)

    def test_quiz_must_overlap(self):
        j = quiz_json()
        j['questions'][1].update(q='서버를 켜는 때가 늦다면, 캐시가 있을 때와 없을 때 가운데 언제인가?', must=['캐시가 있을 때 서버를 켜는 때가 늦다'], model='캐시가 있을 때 서버를 켜는 때가 늦다')
        _, out, err = self.render('test', j)
        self.assertNotIn('질문에 필수 요소가 그대로', out + err)
        j['questions'][1].update(q='캐시가 있을 때 서버를 켜는 때가 늦다. 왜인가?')
        _, out, err = self.render('test', j)
        self.assertIn('질문에 필수 요소가 그대로', out + err)

    def test_shorts_greeting_and_caption(self):
        s = scenes()
        s.append({'slot': 'outro', 'say': '오늘도 모두 수고하셨습니다. 다음에 뵙겠습니다. 감사합니다!', 'visual': '끝 화면', 'title': '끝', 'caption': '끝'})
        _, out, err = self.render('shorts', {'scenes': s, 'answer': 2, 'check': 'a → b'})
        self.assertNotIn('모두', '\n'.join(levels(out, err)))
        s = scenes()
        s[1].update(say='첫 호출 때 켤 수 있습니다.', caption='목록이 캐시됨')
        _, out, err = self.render('shorts', {'scenes': s, 'answer': 2, 'check': 'a → b'})
        self.assertNotIn('조건', '\n'.join(x for x in levels(out, err) if 'scenes[2]' in x))
        self.assertEqual(script.GREET.sub('', '구독 요금은 20달러다.'), '구독 요금은 20달러다.')

    def test_slides_conditions_and_reason(self):
        j = deck_json()
        j['slides'][0].update(title='서버를 늦게 켠다', say='첫 호출 때 켤 수 있다', notes='도구 목록이 캐시된 경우다.')
        j['slides'][2].update(title='서버는 나중에 켤 수 있다', f=['f1'])
        _, out, err = self.render('slides', j)
        w = levels(out, err)
        self.assertEqual([x for x in w if 'slides[1]' in x and '조건' in x], [])
        self.assertTrue([x for x in w if 'slides[3]' in x and '조건' in x], w)
        self.assertTrue([x for x in w if '차트가 없다' in x])
        _, out, err = self.render('slides', dict(j, no_chart='원문에 비교할 수치 없음'))
        self.assertFalse([x for x in levels(out, err) if '차트가 없다' in x or 'MP4' in x])
        page = read(self.p('o', 'w-slides.html'))
        self.assertNotIn('design', page.split('동작 코드 — ')[0])
        self.assertIn('<p class="kicker">어떻게</p>', page)


class Env(unittest.TestCase):
    def test_python39_syntax(self):
        import ast
        root = os.path.join(SKILL, 'scripts')
        for d in (root, os.path.join(root, 'intolib')):
            for f in os.listdir(d):
                if f.endswith('.py') and (f == 'into.py' or d.endswith('intolib')):
                    ast.parse(read(os.path.join(d, f)), f, feature_version=(3, 9))
        self.assertGreaterEqual(sys.version_info[:2], (3, 9))

    def test_stdlib_only(self):
        ok = {'argparse', 'ast', 'collections', 'functools', 'glob', 'hashlib', 'html', 'io', 'json', 'math', 'os', 'random', 're', 'shlex', 'shutil', 'subprocess', 'sys', 'textwrap', 'unicodedata', 'intolib', 'base64', 'itertools', 'urllib', 'string', 'datetime', 'pathlib', 'check_slides'}
        d = os.path.join(SKILL, 'scripts', 'intolib')
        for f in [os.path.join(SKILL, 'scripts', 'into.py')] + [os.path.join(d, x) for x in os.listdir(d) if x.endswith('.py')]:
            for a, b in re.findall(r'(?m)^(?:import|from) (\.?)(\w*)', read(f)):
                if not a and b:
                    self.assertIn(b, ok, f)

    def test_user_error(self):
        with self.assertRaises(UserError):
            formats.load('없는유형')


class Domain(unittest.TestCase):
    """전문가 과정 빌더: 실패하면 쓰지 않는다, 남의 index.html을 덮지 않는다, 위험한 값은 FAIL."""

    def build(self, course, index=None):
        import subprocess
        d = tempfile.mkdtemp(prefix='into-domain-')
        with open(os.path.join(d, 'curriculum.json'), 'w', encoding='utf-8') as f:
            json.dump(course, f)
        if index is not None:
            with open(os.path.join(d, 'index.html'), 'w', encoding='utf-8') as f:
                f.write(index)
        r = subprocess.run([sys.executable, '-I', os.path.join(os.path.dirname(os.path.abspath(into.__file__)), 'build_domain.py'), d], capture_output=True, text=True)
        p = os.path.join(d, 'index.html')
        return r, open(p, encoding='utf-8').read() if os.path.exists(p) else None

    def course(self, **over):
        c = {k: 'x' for k in ('slug', 'domain', 'asof', 'learner', 'vision', 'strategy', 'goal', 'honesty', 'missing', 'source_line')}
        c.update(kind='repo', notice='', proof=[], onepage={}, kpis=[], levels=[], cases=[], sources=[], gaps=[],
                 diag={}, final={}, capstone={'what': 'x', 'form': 'x', 'steps': [], 'rubric': [], 'pass': 0, 'answer': []})
        c['levels'] = [{'name': 'Easy', 'title': 't', 'promise': 'p', 'sections': over.pop('sections', [])}]
        c.update(over)
        return c

    def test_fail_writes_nothing(self):
        r, html = self.build(self.course(), index='내 메모')
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(html, '내 메모')

    def test_bad_id(self):
        s = {'id': '<img onerror=1>', 'title': 't', 'lessons': [], 'deliverable': {'rubric': []}, 'gate': {}, 'kpi': []}
        r, _ = self.build(self.course(sections=[s]))
        self.assertIn('영문자로 시작', r.stdout + r.stderr)


if __name__ == '__main__':
    unittest.main(verbosity=1, warnings='ignore')

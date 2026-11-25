#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""into — 원문 하나를 유형 틀과 모드로 바꾼다 (Python 3.9+, 표준 라이브러리만).

  into.py start <입력|-> [모드] [--type T] [--zone 이름] [--out DIR] [--slug S] [--private|--public] [--no-fetch]
  into.py check <작업 폴더>
  into.py render <작업 폴더> <모드>
  into.py lint <결과 파일> [--type T] [--mode M] [--source 원문] [--size 작음|보통|큼]
  into.py types · formats [--validate] · selftest
"""
import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from intolib import ASSETS, HTML_MODES, MODES, NOTICE, SIZES, SKILL, TEXT_MODES, TYPES, UserError, put  # noqa: E402
from intolib import cells, cite, deck, formats, htmlmodes, lint, pack, quiz, route, script, textmodes  # noqa: E402
from intolib import model as M  # noqa: E402
from intolib import text as T  # noqa: E402

ORDER_MAX = 4000


# ---------- start ----------
def split_words(words):
    """위치 인자 → (입력, 모드 말, 구역)"""
    inp, mode, zone, rest = None, [], '', []
    i = 0
    while i < len(words):
        w = words[i]
        if re.match(r'^(?:구역|zone)\s*[:=]', w, re.I):
            zone = re.sub(r'^(?:구역|zone)\s*[:=]\s*', '', w, flags=re.I) or (words[i + 1] if i + 1 < len(words) else '')
            i += 1 if re.sub(r'^(?:구역|zone)\s*[:=]\s*', '', w, flags=re.I) else 2
            continue
        if inp is None and (w == '-' or route.is_url(w) or os.path.exists(os.path.expanduser(w))) and not (w.lower() in route.EXACT and not os.path.exists(w)):
            inp = w if w == '-' or route.is_url(w) else os.path.expanduser(w)
        else:
            rest.append(w)
        i += 1
    for w in [' '.join(rest)] + rest:
        m = route.find_mode(w) if w else None
        if m:
            return inp, m, zone, [x for x in rest if not route.find_mode(x)]
    mode = None
    return inp, mode, zone, rest


def load_source(inp, work_of, a):
    """입력 → (src dict, 점수표, url)"""
    if inp == '-':
        s, cut = pack.text_in(sys.stdin.read(), '표준 입력')
        meta, st = T.front_matter(s)
        return {'kind': 'file', 'path': None, 'text': s, 'meta': meta, 'body_start': st, 'name': 'stdin.md', 'cut': cut}, route.score_text('\n'.join(s.split('\n')[st - 1:]), meta, 'stdin.md'), ''
    if route.is_url(inp):
        sc = route.score_url(inp)
        typ = a.type or route.decide(sc)['type']
        saved, cut, got, note = os.path.join(work_of(inp, ''), 'source.md'), 0, '', ''
        if os.path.isfile(saved):
            s, cut = pack.text_in(pack.read(saved, pack.READ_MAX + 1), saved)
            got = read_json(os.path.join(os.path.dirname(saved), 'pack.json')).get('fetched') if typ == 'pr' else ''          # 전에 스크립트가 가져온 PR: 커밋과 받은 글의 해시
            if got:
                s, got, note = newer_pr(inp, s, got if isinstance(got, dict) else {'head': got, 'sha': ''}, '' if a.no_fetch else pack.pr_head(inp))
            meta, st = T.front_matter(s)
            body = route.score_text('\n'.join(s.split('\n')[st - 1:]), meta, 'source.md')
            sc = {t: sc[t] + [x for x in body[t] if t != 'general'] for t in sc}                  # 본문이 생겼으니 다시 판별한다
            typ = a.type or route.decide(sc)['type']
        elif typ == 'pr' and 'github.com' in inp and not a.no_fetch:
            s = pack.fetch_pr(inp)
            got = fetched(s)
        else:
            return {'kind': 'none', 'path': None, 'text': '', 'meta': {}, 'body_start': 1, 'name': ''}, sc, inp
        meta, st = T.front_matter(s)
        return {'kind': 'file', 'path': None, 'text': s, 'meta': meta, 'body_start': st, 'name': 'source.md', 'cut': cut, 'fetched': got, 'note': note}, sc, inp
    p = os.path.abspath(inp)
    if os.path.isfile(p) and os.path.basename(p) == 'SKILL.md' and a.type in (None, 'skill'):
        p = os.path.dirname(p)
    if os.path.isdir(p):
        files = cite.list_files(p)
        if not files:
            raise UserError('%s: 입력이 비었다. 읽을 파일이 있는 폴더를 준다' % inp)
        if os.path.exists(os.path.join(p, 'SKILL.md')) and not cite.inside(p, 'SKILL.md'):
            raise UserError('SKILL.md가 폴더 밖을 가리키는 링크다. 실제 파일이 있는 폴더를 준다')
        sc = route.score_dir(p, files)
        return {'kind': 'dir', 'path': p, 'text': '', 'meta': T.front_matter(pack.read(os.path.join(p, 'SKILL.md')))[0] if os.path.exists(os.path.join(p, 'SKILL.md')) else {}, 'body_start': 1, 'name': os.path.basename(p)}, sc, ''
    if p.lower().endswith('.pdf'):
        return {'kind': 'none', 'path': p, 'text': '', 'meta': {}, 'body_start': 1, 'name': os.path.basename(p)}, route.score_text('', {}, os.path.basename(p)), ''
    s, cut = pack.text_in(pack.read(p, pack.READ_MAX + 1), inp)
    meta, st = T.front_matter(s)
    body = '\n'.join(s.split('\n')[st - 1:])
    sc = route.score_text(body, meta, os.path.basename(p))
    return {'kind': 'file', 'path': p, 'text': s, 'meta': meta, 'body_start': st, 'name': os.path.basename(p), 'cut': cut}, sc, ''


def fetched(s):
    return {'head': T.front_matter(s)[0].get('head', ''), 'sha': pack.stamp({'text': s[:pack.READ_MAX]})}


def newer_pr(url, s, got, now):
    """저장된 PR 사본(s, got = fetched)과 지금 head → (글, fetched, 알림). 메타와 diff를 모두 받았을 때만 새 글로 바꾼다."""
    if not now:
        return s, got, '(새 커밋이 있는지 확인하지 못했다)'
    if now == got['head'] and 'truncated' not in T.front_matter(s)[0]:
        return s, got, ''
    if pack.stamp({'text': s}) != got['sha']:
        return s, got, '(지금 커밋은 %s. source.md를 고쳐 두어 덮지 않았다. 새로 받으려면 source.md를 다른 이름으로 옮기고 다시 부른다)' % now[:12]
    try:
        new = pack.fetch_pr(url)
    except (UserError, ValueError):
        new = ''
    if not new or 'truncated' in T.front_matter(new)[0]:
        return s, got, '(지금 커밋 %s의 본문·diff를 다 받지 못해 앞서 받은 사본을 쓴다. 다음 start가 다시 받는다)' % now[:12]
    return new, fetched(new), ''


def title_of(src, inp):
    t = src['meta'].get('title') or ''
    if not t:
        hs = [h for h in T.headings(src['text']) if h[1] <= 2]
        t = hs[0][2] if hs else ''
    if not t and src['kind'] == 'dir':
        t = src['meta'].get('name') or os.path.basename(src['path'].rstrip('/'))
    if t:
        return T.clip(T.visible(t), 120)
    if route.is_url(inp):
        return ''
    return os.path.basename(src['path'] or inp).strip('-') or '제목 없음'


def cmd_start(a):
    inp, mode, zone, rest = split_words(a.words)
    zone = a.zone or zone
    mode = mode or 'brief'
    if mode == 'domain-expert':
        print('모드 domain-expert — 원문 하나가 아니라 도메인을 다룬다. references/domain-expert.md를 읽고 그 순서로 한다(검사: scripts/build_domain.py).\n도메인: %s' % (inp or ' '.join(rest) or '(말하지 않음)'))
        return 0
    if inp is None:
        if rest:
            raise UserError('`%s`가 경로·URL이 아니고 아는 모드도 아니다. 모드: %s. 대화의 글이면 파일로 저장해 그 경로를 준다' % (rest[0], '·'.join(MODES)))
        raise UserError('입력이 없다. 경로나 URL을 준다. 직전 답이면 파일로 저장해 넘긴다')
    if a.type and not formats.exists(a.type) and a.type not in TYPES:
        raise UserError('유형 `%s`를 모른다. 유형: %s' % (a.type, '·'.join(s.stem for s in formats.all_types()) or '·'.join(TYPES)))
    if a.slug and (a.slug in ('.', '..') or re.search(r'[/\\\0]', a.slug)):
        raise UserError('--slug은 이름 하나다(경로를 쓰지 않는다): %s' % a.slug)
    out = os.path.abspath(a.out or 'into-out')
    key = (inp if inp == '-' or route.is_url(inp) else os.path.realpath(inp)) + ('#' + zone if zone else '')

    def work_of(i, title):
        base = a.slug or route.make_slug(i if i != '-' else (title or 'stdin'), title, zone)
        k, name = 2, base
        while True:
            w = os.path.join(out, '.into', name)
            if os.path.islink(w) or os.path.islink(os.path.dirname(w)):
                raise UserError('작업 폴더 자리가 심볼릭 링크다: %s. 링크를 옮기고 다시 부른다' % w)
            pj = os.path.join(w, 'pack.json')
            if not os.path.exists(w) or not os.listdir(w):
                return w
            if os.path.exists(pj):
                try:
                    if json.load(open(pj, encoding='utf-8')).get('key') == key:
                        return w
                except ValueError:
                    pass
            name, k = '%s-%d' % (base, k), k + 1
    src, sc, url = load_source(inp, work_of, a)
    d = route.decide(sc)
    title = title_of(src, inp)
    if inp == '-':
        key = 'stdin:' + hashlib.sha1(src['text'].encode('utf-8', 'replace')).hexdigest()[:12] + key[1:]
    work = work_of(inp, '' if url else title)
    old = read_json(os.path.join(work, 'pack.json'))
    front = route.FRONT.get(str(src['meta'].get('type') or '').strip().lower()) if src['kind'] != 'dir' else None
    typ, type_why = next((x for x in ((a.type, '사용자가 준 --type'), (old.get('type') if old.get('forced') else '', '전에 고른 --type'), (front, '머리말 type: %s' % src['meta'].get('type'))) if x[0]), (d['type'], ''))
    if not type_why and d['tie']:
        print('유형이 갈린다. 원문을 보고 하나를 골라 `--type`을 붙여 다시 부른다.')
        for t, n, sig in d['rank'][:2]:
            print('- `--type %s` (%d점) — %s' % (t, n, ' · '.join(sig[:4])))
        return 3
    os.makedirs(work, exist_ok=True)
    gi = os.path.join(out, '.into', '.gitignore')
    if not os.path.exists(gi):
        put(gi, '*\n')
    if src['kind'] == 'file' and typ == 'pr' and cite.has_diff(src['text']):
        src['kind'] = 'pr'
    names = ['raw', 'source']
    copy = ''
    if src['kind'] in ('file', 'pr'):
        ext = os.path.splitext(src['name'])[1] or '.txt'
        copy = 'source' + ext
        dst = os.path.join(work, copy)
        if os.path.islink(dst):
            raise UserError('쓸 자리가 심볼릭 링크다: %s. 링크를 옮기고 다시 부른다' % dst)
        if src['path'] and not src['cut']:
            if os.path.abspath(dst) != src['path']:
                shutil.copyfile(src['path'], dst)
        elif not os.path.isfile(dst) or pack.read(dst, pack.READ_MAX + 1) != src['text']:
            put(dst + '.new', src['text'])                                      # 다 쓴 뒤에 한 번에 바꾼다
            os.replace(dst + '.new', dst)
        names += [src['name']] if src['path'] else []
        names.append(copy)
    elif src['kind'] == 'dir':
        put(os.path.join(work, 'source.path'), src['path'] + '\n')
    src['copy'] = copy
    facts, md = pack.build(src, typ, zone, fetch=not a.no_fetch)
    flag = True if a.public else False if a.private else old.get('flag')              # 한 번 준 --private·--public은 다음 모드에도 남는다
    public, why = route.public_of(src['meta'], url, flag)
    sha, stale = pack.stamp(src), stale_of(old)
    for name in ['model.json'] + [x + '.json' for x in MODES if src['kind'] == 'dir']:
        if os.path.exists(os.path.join(work, name)) and (moved(work, src['path'], name) if src['kind'] == 'dir' else old.get('sha') and old['sha'] != sha):
            stale[name] = file_sha(os.path.join(work, name))
    if src['kind'] == 'dir':
        put(os.path.join(work, 'files.json'), json.dumps(pack.shas(src['path']), ensure_ascii=False))
    r = facts.get('repo', {})
    if flag is None and r.get('visibility') == 'public' and not src['meta'].get('public'):
        public, why = not r['local'], 'gh: 원격 %s가 public%s' % (r['remote'], '이지만 ' + r['local'] + '. 공개면 --public' if r['local'] else '')
    gh = re.match(r'https?://(?:www\.)?github\.com/([^/\s]+/[^/\s?#]+)', url)
    if gh and flag is None and not src['meta'].get('public') and not a.no_fetch and pack.visibility(gh.group(1)) == 'public':
        public, why = True, 'gh: 저장소 %s가 public' % gh.group(1)
    p = {'v': 1, 'key': key, 'input': inp if inp == '-' or route.is_url(inp) else os.path.basename(os.path.abspath(inp)), 'type': typ, 'mode': mode, 'zone': zone, 'title': title, 'slug': os.path.basename(work),
         'signals': d['rank'], 'forced': bool(type_why) and '--type' in type_why, 'type_why': type_why, 'public': public, 'public_why': why, 'flag': flag, 'sha': sha, 'stale': stale, 'cut': src.get('cut', 0), 'fetched': src.get('fetched', ''), 'note': src.get('note', ''),
         'url': url or (src['meta'].get('source', '') if re.match(r'https?://', src['meta'].get('source', '')) else '') or ('https://github.com/%s' % r['remote'] if public and r.get('remote') else ''),
         'source': {'kind': src['kind'], 'copy': copy, 'path': src['path'] if src['kind'] == 'dir' else '', 'names': names, 'name': src['name'] if src['path'] else ''}}
    p['url'] = p['url'].split(' ')[0]
    p.update(facts)
    put(os.path.join(work, 'pack.json'), json.dumps(p, ensure_ascii=False, indent=1))
    head = ['# pack — %s' % (title or inp), '', '- 유형 %s · 크기 %s(%s) · %s(%s)' % (typ, p['size'], p['size_why'], '공개' if public else '비공개', why)]
    put(os.path.join(work, 'pack.md'), '\n'.join(head + md) + '\n')
    base = a.slug or route.make_slug(inp if inp != '-' else (title or 'stdin'), '' if url else title, zone)
    sys.stdout.write(work_order(p, work, mode, '' if os.path.basename(work) == base else base))
    return 0


def read_json(path):
    try:
        j = json.load(open(path, encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    return j if isinstance(j, dict) else {}


def cites(v, key=''):
    """JSON에 적힌 근거들(src 값과 `경로:줄` 글)"""
    if isinstance(v, (dict, list)):
        return [s for k, x in (v.items() if isinstance(v, dict) else [(key, x) for x in v]) for s in cites(x, k)]
    return M.split_src(v) if key == 'src' else [v] if isinstance(v, str) and M.CITE_LIKE.match(v) else []


def moved(work, root, name):
    """이 JSON이 근거로 쓴 파일 가운데 start 때와 내용이 달라진 것(폴더 입력)"""
    old = read_json(os.path.join(work, 'files.json'))
    try:
        j = M.parse_json(pack.read(os.path.join(work, name), pack.READ_MAX), name) if old else {}
    except UserError:
        return []
    src = cite.Source('dir', root)
    cited = {src.resolve(s).get('file') for s in cites(j)} & set(old)
    now = pack.shas(root, cited)
    return sorted(f for f in cited if now.get(f) != old[f])


def stale_of(p):
    """원문이 바뀌기 전에 쓴 JSON의 해시 {이름: 해시}"""
    s = p.get('stale') or {}
    return s if isinstance(s, dict) else {'model.json': s}


def file_sha(path):
    return hashlib.sha1(open(path, 'rb').read()).hexdigest() if os.path.exists(path) else ''


# ---------- 작업 지시 ----------
READ = {
    'pr': '원문에서는 PR 본문만(diff는 pack.md에 줄 번호를 달아 두었다)',
    'codebase': '고른 길의 파일만',
    'skill': 'SKILL.md → 그 길에서 읽히는 참조와 스크립트',
}
VALUES = ('값: `"글"` 또는 `{"t":"글","f":["f1","e2"]}`(f = model의 id. 근거 줄은 스크립트가 만든다). 그림 칸은 id 배열, 짧게 바꿀 때는 `{"id":"e1","t":"짧은 글"}`(lanes는 do·out). 표는 행이나 id 배열. 그림·표는 비우면 model에서 채우고 `false`면 뺀다. '
          '`~` 칸만 근거 없이 쓴다. `(근거 미제시)` 같은 표시는 스크립트가 붙이고 글에 이미 있으면 안 붙는다. `"missing":"…"`은 model의 missing을 대신한다.')


def spec_lines(typ, mode, size, work):
    """그 모드 절 → 줄 목록"""
    out = []
    if mode in TEXT_MODES + ('html', 'interactive'):
        rows, sp = formats.mode_rows(typ, mode)
        lim = formats.length_limit(typ, mode, size)
        out.append('전체 %s(%s 원문. 105%%까지는 WARN이고 그대로 둬도 된다). 세는 것: %s. 안 세는 것: 빠진 디테일·근거·출처. `!` 필수 · `6×60` = 6개(행)까지, 하나(표는 칸 하나)에 60자까지 · 원문에 없으면 비운다.' % ('{:,}자'.format(lim) if lim else '제한 없음', size,
                   '칸의 글' if mode == 'doc' else '머리 줄(제목)·칸·그림의 글' if mode in HTML_MODES else '머리 줄(제목·범위)·칸·그림의 글'))
        same = cells.same_as_eli5(rows, mode, sp, read_json(os.path.join(work, 'eli5.json'))) if mode != 'eli5' else ()
        if same:
            out.append('`(그대로)` 칸은 비우면 eli5.json에서 온다(빼려면 `false`).' + (' 비운 그림도 eli5에서 줄인 글을 쓴다.' if mode in HTML_MODES else ''))
        forms = {r['form'] for r in rows}
        tips = [('그림: 큰 길을 먼저 쓴다. 간선의 `if`는 글 뒤에 붙고%s 글에 조건이 이미 있으면 안 붙는다.' % (' 글자 수에 든다(되풀이되는 노드 이름은 한 번만 센다).' if mode in ('brief', 'eli5', 'ste') else ',')) if forms & {'flow', 'beforeafter'} else '',
                '`options`의 `{"id","t"}`는 이름만 바꾼다. 이유는 cells에서 붙는다. `open`은 `f:["open1"]`로 건다%s.' % ('(앞 둘은 options 그림에도 들어가 글자 수에 든다)' if mode in HTML_MODES else '') if 'options' in forms else '',
                '단추 행(cases·flips 등)의 `f`에 간선 id를 넣으면 그 길이 켜진다.' if mode == 'interactive' and 'table' in forms and forms & {'flow', 'beforeafter', 'map'} else '']
        out += [x for x in tips if x]
        if sp.note(mode):
            out.append('참고: ' + sp.note(mode))
        for r in rows:
            out.append(['- `%s` %s·%s %s %s%s' % (r['key'], r['slot'], r['label'], r['form'] + (':' + ','.join(r['cols']) if r['form'] in ('table', 'kit') else ''), r['limit'], '(그대로)' if r['key'] in same else '') +
                        (' 행 `%s`' % (cells.row_example(r['cols']) if r['form'] == 'table' else '{"q":"…","a":"…","f":["f1"]}') if r['form'] in ('table', 'qa') else ''), r['hint']])
    else:
        sp = formats.load(typ)
        rows = sp.plain_rows(mode)
        out += {'shorts': ['slot: hook·one·why·pic·run·catch(·outro). 시간 = 음절 ÷ 5.5 + 문장 사이 0.3초 + 질문 뒤 1초, 60초까지. 자막 24자 · 제목 28자. 조건은 말이나 자막에 있으면 된다.'],
                'slides': ['차트·MP4를 안 넣으면 맨 위에 `"no_chart":"이유"`.']}.get(mode, [])
        if sp.note(mode):
            out.append('참고: ' + sp.note(mode))
        for r in rows or []:
            v = [x for x in r.values()]
            out.append(['- ' + ' · '.join(x for x in v[:3] if x), ' / '.join(v[3:])])
    return out


def work_order(p, work, mode, taken=''):
    typ, w = p['type'], shlex.quote(work)
    tool = 'python3 ' + shlex.quote(os.path.join(SKILL, 'scripts', 'into.py'))
    sp = formats.load(typ) if formats.exists(typ) else None
    sig = p['signals']
    o = ['# into · %s × %s' % (typ, mode)]
    o.append('유형 %s%s — %s%s' % (typ, '(%s)' % sp.name if sp else '', p.get('type_why') or ' · '.join(sig[0][2][:4]) + ' (%d점)' % sig[0][1],
                                  '' if p.get('type_why') or len(sig) < 2 else ' / 2위 %s %d점' % (sig[1][0], sig[1][1])))
    o.append('크기 %s(%s) · %s(%s)%s' % (p['size'], p['size_why'], '공개' if p['public'] else '비공개 — 안내 줄은 스크립트가 붙인다', p['public_why'], ' · 구역 `%s`' % p['zone'] if p['zone'] else ''))
    k = p['source']['kind']
    if p.get('fetched'):
        o.append('읽은 PR 커밋 %s%s' % (p['fetched']['head'][:12], p.get('note', '')))
    o.append('작업 폴더 W = %s%s' % (work, '\n`%s`는 다른 입력·구역이 쓰고 있어 `%s`로 만들었다. 이 구역은 앞으로 이 이름이다' % (taken, p['slug']) if taken else ''))
    if k == 'none':
        o += ['', '## 본문이 없다', '호스트의 웹·PDF 읽기 도구로 본문(자막)을 읽어 `%s/source.md`에 그대로 저장하고 같은 start를 다시 부른다. 로그인 벽·자막 없음이면 사용자에게 본문을 달라고 한다. 제목·미리보기만으로 쓰지 않는다.' % work if not p['input'].lower().endswith('.pdf') else
              'PDF 본문을 읽어 `.md`로 저장하고 그 파일로 start를 다시 부른다(`--type paper-concept`).']
        if typ == 'codebase':
            o[-1] = '저장소를 내려받지 않는다. 로컬 사본 경로를 받아 그 경로로 start를 다시 부른다.'
        return '\n'.join(o) + '\n'
    if p.get('cut'):
        o.append('원문이 길어 앞 {:,}자만 읽었다. 뒤는 검사하지 않으니 `source`에 그렇게 적는다'.format(p['cut']))
    has = os.path.exists(os.path.join(work, 'model.json'))
    changed = has and stale_of(p).get('model.json') == file_sha(os.path.join(work, 'model.json'))
    o += ['', '## 1. 읽는다']
    o.append('- W/pack.md(다시 세지 않는다) → ' + ((READ.get(typ) if k == {'pr': 'pr'}.get(typ, 'dir') else '') or ('원문 `W/%s` 전체' % p['source']['copy'] if p['source']['copy'] else '원문 폴더의 파일 전체')) +
             ('' if typ != 'codebase' else '(구역 전체 목록은 pack.md에 있다)' if not p['zone'] or p.get('repo', {}).get('zone_dirs') else '. 구역 이름과 맞는 폴더가 없다 — 경로를 알면 `--zone 경로,경로`로 다시 부른다'))
    o.append('- 근거 쓰기: ' + ({'pr': '`경로:줄`(PR 뒤 줄) · 지운 줄 `경로:-줄` · 본문 `raw:줄`', 'file': '`raw:줄`(W/%s의 줄)%s' % (p['source']['copy'], {'video': ' · `[mm:ss]`', 'social-post': ' · `n/N`'}.get(typ, '')),
                                 'dir': '`경로:줄`(경로는 `%s` 아래)' % p['input']}[k if k in ('pr', 'dir') else 'file']))
    if typ in ('codebase', 'pr', 'skill') or (typ == 'local-file' and p.get('structure')):
        o.append('- references/reading-code.md (코드 읽는 규칙)')
    if p['size'] == '큼' or mode in ('interactive', 'test'):
        o.append('- references/judgment.md %s' % ('1절(카드 반박) · 2절(쓴 뒤에)' if mode in ('interactive', 'test') else '1절(카드 반박)'))
    if sp:
        o.append('- 독자의 첫 질문: ' + ' / '.join(sp.questions) + ' — 이 셋에 답하는 것만 고른다')
    if has:
        o += ['', '## 2. W/model.json이 이미 있다 — 다시 쓰지 않는다', ('원문이 바뀌었다: model.json을 다시 대조한다. ' if changed else '') + '원문과 대조만 하고 틀린 줄만 고친다(모드가 더 자세하면 사실을 더한다). → `%s check %s`' % (tool, w)]
    else:
        o += ['', '## 2. W/model.json을 쓴다',
              '`{"type":"%s","title":"제목(30자까지, 첫 줄)","scope":"범위(25자까지, 첫 줄)","source":"무엇을 어디까지 읽었나(출처 줄)","missing":"","facts":[{"id":"f1","t":"문장","src":["…"],"if":"조건","hedge":"can","mark":"추정|불확실|근거 미제시|보충","key":true}],%s"steps":[{"id":"s1","who":"","do":"","src":[],"if":"","fail":""}],"order":"time|call|text|none","flips":[{"id":"","if":"","then":"","src":[]}],"terms":[{"w":"쓴 말","o":["원문 표기"]}]}`' % (
                  typ, '"nodes":[{"id":"cli","t":"CLI"}],"edges":[{"id":"e1","from":"","to":"","t":"오가는 것","src":[],"if":"","hedge":"","main":true,"when":"both|before|after","guess":false}],' if not sp or draws_edges(sp) else '')]
        o.append('없는 키는 뺀다. src 없는 사실·간선·단계는 FAIL. 근거 줄에 조건어가 있으면 `if`·`hedge`를 쓰고, 봤는데 조건이 아니면 `"cond":"none"`. 단계의 `if`는 단계 전체가 조건일 때만(넘기는 것만이면 `out`에).')
        o.append('`hedge` 값과 칸에 남길 말: ' + ' / '.join('%s = %s' % (k, v) for k, v in (('can', T.HEDGE_SAY['may']), ('should', T.HEDGE_SAY['should']), ('must', T.HEDGE_SAY['must']), ('default', T.HEDGE_SAY['default']), ('약', T.HEDGE_SAY['about']))) + '. 그 밖은 원문 말 그대로. 유형 키:')
        if sp:
            if sp.note('model'):
                o.append('참고: ' + sp.note('model'))
            for r in sp.model_rows():
                o.append(['- `%s` %s %s' % (r['key'], r['form'].replace('\\|', '|'), formats_count(r)) + (' `base` = 기준 값(숫자)이나 기준 조건의 이름(group)' if 'base' in r['fields'] else ''), r['hint']])
        o.append('→ `%s check %s`' % (tool, w))
    o += ['', '## 3. W/%s.json을 쓴다' % mode]
    if sp or mode == 'brief':
        try:
            o += spec_lines(typ, mode, p['size'], work)
        except UserError as e:
            o.append(str(e))
    extra = {'test': 'references/test.md', 'shorts': 'references/shorts.md', 'video': 'references/video.md(와 shorts.md)', 'slides': 'references/slides.md'}.get(mode)
    o.append('JSON 모양: ' + extra if extra else VALUES)
    o.append('→ `%s render %s %s`' % (tool, w, mode))
    return fit(o)


def draws_edges(sp):
    """이 유형의 어느 모드든 간선을 그리나"""
    return any(r['form'] in ('flow', 'beforeafter', 'map') for mode in TEXT_MODES + HTML_MODES for r in sp.rows(mode) or []) or any('edges' in r['fields'] for r in sp.model_rows())


def formats_count(r):
    lo, hi = r['count']
    return '' if hi is None and not lo else '%d–%s' % (lo, hi if hi is not None else '') if lo != hi else str(lo)


def fit(o):
    """4,000자 안에 들게 설명(둘째 조각)을 줄인다."""
    for n in (90, 70, 56, 44, 34, 26, 18, 0):
        s = '\n'.join(x if isinstance(x, str) else x[0] + (' — ' + T.clip(x[1], n) if x[1] and n else '') for x in o) + '\n'
        if len(s) <= ORDER_MAX:
            return s
    return T.clip(s, ORDER_MAX) if len(s) > ORDER_MAX else s


# ---------- check · render ----------
def open_work(work):
    work = os.path.abspath(work)
    pj = os.path.join(work, 'pack.json')
    if not os.path.exists(pj):
        raise UserError('작업 폴더가 아니다(pack.json이 없다): %s. 먼저 start를 부른다' % work)
    p = json.load(open(pj, encoding='utf-8'))
    s = p['source']
    if s['kind'] == 'dir':
        if not os.path.isdir(s['path']):
            raise UserError('원문 폴더가 없어졌다. 같은 입력으로 start를 다시 부른다')
        src = cite.Source('dir', s['path'])
    else:
        src = cite.Source(s['kind'], os.path.join(work, s['copy']) if s['copy'] else '', s['names'])
    nums, lines = pack.fact_numbers(p)
    src.allow_numbers(nums | T.number_set(p.get('title') or ''), lines)
    return work, p, src


def report(issues):
    f, w = [list(dict.fromkeys(str(i) for i in issues if i.level == lv)) for lv in ('FAIL', 'WARN')]
    print('FAIL %d · WARN %d' % (len(f), len(w)))
    for s in f + w:
        print('- ' + s)
    return 1 if f else 0


def ready(work, p, path='', names=('model.json',)):
    """출판 직전 확인 한곳(check·render가 부른다): 원문 본문과 사본 · 원문 변경(names = 쓸 JSON) · 공개 상태 · 같은 이름의 남의 파일 → (알림, 쓸 자리)"""
    out, s, stale = [], p['source'], stale_of(p)
    old = [x for x in names if stale.get(x) and stale[x] == file_sha(os.path.join(work, x))]
    copy = os.path.join(work, s['copy']) if s['copy'] else ''
    origin = p['key'][:-len(p['zone']) - 1] if p.get('zone') else p['key']
    if s['kind'] == 'none':
        out.append(formats.Issue('FAIL', 'W/source.md', '원문 본문이 없다. 본문을 저장하고 같은 start를 다시 부른다. 제목·미리보기만으로 쓰지 않는다'))
    elif copy and pack.empty(pack.read(copy)):
        out.append(formats.Issue('FAIL', 'W/' + s['copy'], '원문 사본이 %s. 같은 입력으로 start를 다시 부른다' % ('비었다' if os.path.isfile(copy) else '없다')))
    elif old:
        out += [formats.Issue('WARN', x, '원문이 바뀌었다: %s을 다시 대조한다(고치면 이 줄이 사라진다)' % x) for x in old]
    elif copy and p.get('sha') and any(pack.stamp({'kind': 'file', 'text': pack.read(f, pack.READ_MAX)}) != p['sha'] for f in (copy, origin) if os.path.isfile(f)):
        out.append(formats.Issue('WARN', 'W/' + s['copy'], '원문이 start 뒤에 바뀌었다: 같은 start를 다시 부르고 model.json을 다시 대조한다'))
    if s['kind'] == 'dir':
        out += [formats.Issue('WARN', n, '근거로 쓴 파일이 start 뒤에 바뀌었다(%s): 같은 start를 다시 부르고 %s을 다시 대조한다' % (', '.join(x[:3] + ['…'] * (len(x) > 3)), n)) for n in names for x in [moved(work, s['path'], n)] if x]
        r = p.get('repo') or {}
        if p['public'] and p.get('flag') is None and r.get('visibility') == 'public' and (pack.unpublished(s['path']) or pack.sh(['git', '-C', s['path'], 'rev-parse', 'HEAD'], 10)[1].strip() != r['commit']):
            p['public'], p['url'] = False, ''                                  # 공개 커밋과 다른 작업본
    if copy and p['public'] and p.get('flag') is None and not route.public_of(dict({'public': 'true'}, **T.front_matter(pack.read(copy))[0]), '', None)[0]:
        p['public'] = False
    known, (root, ext), k, target = read_json(os.path.join(work, 'outputs.json')), os.path.splitext(path), 2, path
    while os.path.exists(target) and not os.path.islink(target) and known.get(os.path.basename(target)) != file_sha(target):
        target, k = '%s-%d%s' % (root, k, ext), k + 1
    return out, target


def cmd_check(a):
    work, p, src = open_work(a.work)
    out, _ = ready(work, p)
    if any(i.level == 'FAIL' for i in out):
        return report(out)
    m, raw = M.load(os.path.join(work, 'model.json'))
    return report(M.check(m, raw, src, p['type']) + out)


def save(work, target, data):
    """결과 쓰기(자리는 ready가 골랐다) + 우리가 쓴 것의 해시."""
    book = os.path.join(work, 'outputs.json')
    put(target, data)
    put(book, json.dumps(dict(read_json(book), **{os.path.basename(target): file_sha(target)}), ensure_ascii=False))


def warn_out(issues):
    for s in dict.fromkeys(str(i) for i in issues if i.level == 'WARN'):
        sys.stderr.write('- ' + s + '\n')


def cmd_render(a):
    mode = route.find_mode(a.mode) or a.mode
    if mode not in MODES or mode == 'domain-expert':
        raise UserError('모드 `%s`를 render하지 않는다. 모드: %s' % (a.mode, '·'.join(x for x in MODES if x != 'domain-expert')))
    work, p, src = open_work(a.work)
    out_dir = os.path.dirname(os.path.dirname(work))
    first, target = ready(work, p, os.path.join(out_dir, '%s-%s%s' % (p['slug'], mode, '.html' if mode in HTML_MODES + ('test',) else '.md')),
                          ['model.json', mode + '.json'] + ['eli5.json'] * (mode != 'eli5' and mode in TEXT_MODES + ('html', 'interactive')))
    if any(i.level == 'FAIL' for i in first):
        print('결과를 쓰지 않았다.')
        return report(first)
    m, raw = M.load(os.path.join(work, 'model.json'))
    typ = m.get('type') if formats.exists(str(m.get('type'))) else p['type']
    hard = [i for i in M.check(m, raw, src, p['type']) if i.level == 'FAIL']
    if hard:
        print('model.json이 아직 FAIL이다. 결과를 쓰지 않았다.')
        return report(hard + first)
    jp = os.path.join(work, mode + '.json')
    if not os.path.exists(jp):
        raise UserError('%s가 없다. 작업 지시의 3번을 보고 먼저 쓴다' % jp)
    j = M.parse_json(open(jp, encoding='utf-8').read(), mode + '.json')
    sp = formats.load(typ)
    size = p['size']
    name = p['source'].get('name') or '원문'
    if mode in ('test', 'shorts', 'video', 'slides'):
        chk = cells.Checker(mode, [], m, {}, src, p, sp)
        chk.raw = {'missing': j.get('missing', '')}
        if mode == 'test':
            issues, qs = quiz.check(j, m, chk, size, sp.plain_rows('test'))
        elif mode == 'slides':
            issues, slides = deck.check(j, chk, sp.plain_rows('slides'))
        else:
            issues, scenes = script.check(mode, j, m, chk, size)
        ctx = cells.context(chk, typ, size, p, name)
        if any(i.level == 'FAIL' for i in issues):
            print('결과를 쓰지 않았다.')
            return report(issues + first)
        data, line = quiz.build(ctx, qs, p['slug'])[0] if mode == 'test' else deck.render(dict(ctx, kicker=dict(deck.KICKER, **deck.kickers(sp))), slides) if mode == 'slides' else script.render(mode, ctx, j, scenes), ''
        if mode == 'slides':
            issues += deck.static(data, out_dir, str(j.get('no_chart') or '').strip())
    else:
        rows = formats.mode_rows(typ, mode)[0]
        ep = os.path.join(work, 'eli5.json')
        chk = cells.Checker(mode, rows, m, j, src, p, sp, eli5=M.parse_json(open(ep, encoding='utf-8').read(), 'eli5.json') if mode != 'eli5' and os.path.exists(ep) else None)
        chk.run()
        ctx = cells.context(chk, typ, size, p, name)
        ctx['assets'] = ASSETS
        ctx['slug'] = p['slug']
        issues = chk.issues
        lim = formats.length_limit(typ, mode, size)
        data, n = '', cells.total_cells(ctx)
        if T.over(n, lim):
            issues.append(formats.Issue(T.over(n, lim), mode + '.json', '보이는 글자 {:,}자다. {:,}자까지다({})'.format(n, lim, '{:,}자 줄인다'.format(n - lim) if T.over(n, lim) == 'FAIL' else '{:,}자 넘음. 5% 안이라 그대로 둬도 된다'.format(n - lim))))
        line = '\n'.join([cells.used_line(ctx, lim)] + (cells.pic_parts(ctx) if T.over(n, lim) == 'FAIL' else []))
        if mode in TEXT_MODES:
            if not any(i.level == 'FAIL' for i in issues):
                data = textmodes.render(mode, ctx)
                if mode == 'ste':
                    issues += [formats.Issue('WARN', 'ste 결과 %d줄' % no, '[%s] %s' % (r, t)) for r, no, t in lint.ste(data)]
        else:
            issues += [formats.Issue(*x) for x in htmlmodes.check(mode, ctx)]
            if not any(i.level == 'FAIL' for i in issues):
                data = htmlmodes.render(mode, ctx)
    issues += first
    if data:                                                                    # 모든 모드의 완성본을 저장 직전에 본다
        if not p['public'] and NOTICE not in data:
            issues.append(formats.Issue('FAIL', '결과', '비공개 안내 줄이 없다'))
        issues += [formats.Issue(lv, '결과 %d줄' % no, t) for lv, no, t in lint.safety(data, mode in HTML_MODES) if not (mode in TEXT_MODES and '비밀 값 후보' in t)]
    if any(i.level == 'FAIL' for i in issues):
        print('결과를 쓰지 않았다.')
        code = report(issues)
        if line:
            print(line)
        return code
    if mode in ('brief', 'eli5', 'ste'):
        save_to = os.path.join(work, mode + '.md')
        put(save_to, data)
        sys.stdout.write(data)
        sys.stderr.write('\nFAIL 0 · 사본 %s\n%s\n' % (save_to, line))
    else:
        save(work, target, data)
        if mode == 'doc':
            put(os.path.join(work, 'doc.md'), data)
        print(target)
        info = {'test': lambda: '문항 %d개' % len(qs), 'slides': lambda: '%d장' % len(slides),
                'shorts': lambda: '%.1f초 · 장면 %d개' % (sum(x['seconds'] for x in scenes), len(scenes)), 'video': lambda: '%s · 장면 %d개' % (script.clock(sum(x['seconds'] for x in scenes)), len(scenes))}.get(mode)
        print('FAIL 0%s · 빠진 디테일: %s' % (' · ' + info() if info else '', ctx['missing']))
        if mode in ('doc', 'html', 'interactive'):
            print(line)
    warns = [i for i in issues if i.level == 'WARN']
    if warns:
        sys.stderr.write('WARN %d\n' % len(set(map(str, warns))))
        warn_out(warns)
    return 0


# ---------- lint · types · formats · selftest ----------
def cmd_lint(a):
    if not os.path.isfile(a.file):
        raise UserError('파일이 없다: %s' % a.file)
    mode = (route.find_mode(a.mode) or a.mode) if a.mode else ''
    src = None
    if a.source:
        if not os.path.exists(a.source):
            raise UserError('원문이 없다: %s' % a.source)
        if os.path.isdir(a.source):
            src = cite.Source('dir', os.path.abspath(a.source))
        else:
            kind = 'pr' if a.type == 'pr' and cite.has_diff(pack.read(a.source, pack.READ_MAX)) else 'file'
            src = cite.Source(kind, os.path.abspath(a.source), ['raw', os.path.basename(a.source)])
    issues, n = lint.result(a.file, a.type, mode, src, a.size)
    print('보이는 글자 %s' % '{:,}'.format(n))
    return report(issues)


def cmd_types(a):
    rows = formats.all_types()
    if not rows:
        print('formats/에 유형 파일이 없다.')
        return 1
    print('| 유형 | 이름 | 주 그림 | 독자의 첫 질문 |\n|---|---|---|---|')
    for s in rows:
        print('| %s | %s | %s | %s |' % (s.stem, s.name, s.pic, ' / '.join(s.questions)))
    return 0


def cmd_formats(a):
    n, issues = formats.validate_all()
    if not a.validate:
        for s in formats.all_types():
            print('%s: %s' % (s.stem, ' '.join(s.sections)))
        return 0
    missing = [t for t in TYPES if not formats.exists(t)]
    print('formats 파일 %d개%s' % (n, ' · 아직 없는 유형: ' + ', '.join(missing) if missing else ''))
    return report(issues)


def cmd_selftest(a):
    import subprocess
    t = os.path.join(SKILL, 'tests', 'run_tests.py')
    if not os.path.exists(t):
        raise UserError('tests/run_tests.py가 없다')
    return subprocess.call([sys.executable, t])


def main(argv=None):
    ap = argparse.ArgumentParser(prog='into.py', description=__doc__.split('\n')[0], formatter_class=argparse.RawDescriptionHelpFormatter, epilog='\n'.join(__doc__.split('\n')[2:]))
    sub = ap.add_subparsers(dest='cmd', metavar='명령')
    s = sub.add_parser('start', help='유형·크기·공개 판별, 원문 꾸러미, 작업 지시')
    s.add_argument('words', nargs='+', help='입력 [모드] [구역:이름]. 글은 파일 경로나 stdin(-)으로 준다')
    s.add_argument('--type')
    s.add_argument('--zone', default='')
    s.add_argument('--out')
    s.add_argument('--slug')
    g = s.add_mutually_exclusive_group()
    g.add_argument('--private', action='store_true')
    g.add_argument('--public', action='store_true')
    s.add_argument('--no-fetch', action='store_true')
    s.set_defaults(fn=cmd_start)
    s = sub.add_parser('check', help='model.json 검사')
    s.add_argument('work')
    s.set_defaults(fn=cmd_check)
    s = sub.add_parser('render', help='<모드>.json 검사 + 결과')
    s.add_argument('work')
    s.add_argument('mode')
    s.set_defaults(fn=cmd_render)
    s = sub.add_parser('lint', help='손으로 쓴 결과 검사')
    s.add_argument('file')
    s.add_argument('--type')
    s.add_argument('--mode')
    s.add_argument('--source')
    s.add_argument('--size', choices=SIZES)
    s.set_defaults(fn=cmd_lint)
    s = sub.add_parser('types', help='유형 표')
    s.set_defaults(fn=cmd_types)
    s = sub.add_parser('formats', help='틀 목록 · 문법 검사')
    s.add_argument('--validate', action='store_true')
    s.set_defaults(fn=cmd_formats)
    s = sub.add_parser('selftest', help='시험 실행')
    s.set_defaults(fn=cmd_selftest)
    a = ap.parse_args(argv)
    if not a.cmd:
        ap.print_help()
        return 2
    try:
        return a.fn(a)
    except UserError as e:
        sys.stderr.write('오류: %s\n' % e)
        return 2
    except (OSError, UnicodeError, LookupError, ValueError, TypeError, AttributeError) as e:
        if os.environ.get('INTO_DEBUG'):
            raise
        sys.stderr.write('오류: %s — %s. (자세히: INTO_DEBUG=1)\n' % (e.__class__.__name__, T.clip(e, 120)))
        return 2


if __name__ == '__main__':
    sys.exit(main())

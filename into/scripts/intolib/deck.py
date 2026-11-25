# -*- coding: utf-8 -*-
"""slides: 장 JSON → assets/slides.html의 section. 그림 데이터 검사는 check_slides.py와 같은 함수를 쓴다."""
import html
import json
import os
import re
import sys

from . import ASSETS, UserError
from . import model as M
from . import text as T
from .formats import Issue

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import check_slides  # noqa: E402

ORDER = ('cover', 'one', 'why', 'pic', 'run', 'catch', 'close')
PARTS = ('motion-inline', 'flow', 'sequence', 'chart', 'walk', 'sim', 'predict', 'compare', 'timeline', 'map', 'motion')
KICKER = {'one': '한 줄', 'why': '왜', 'pic': '그림', 'run': '어떻게', 'catch': '조심', 'close': '정리'}


def check(j, chk, rows=None):
    """(issues, slides)"""
    out = []

    def add(level, where, msg):
        out.append(Issue(level, 'slides.json %s' % where if where else 'slides.json', msg))
    slides = [dict(s) for s in M.as_list(j.get('slides')) if isinstance(s, dict)]
    if not slides:
        add('FAIL', 'slides', '장이 없다. `"slides":[{"slot":"cover","title":…}]`로 쓴다')
        return out, slides
    if not 4 <= len(slides) <= 24:
        add('FAIL', 'slides', '%d장이다. 4~24장으로 쓴다(보통 8~14)' % len(slides))
    last, titles = -1, {}
    for i, s in enumerate(slides, 1):
        w, slot, end = 'slides[%d]' % i, str(s.get('slot') or ''), i == len(slides)
        if slot not in ORDER:
            add('FAIL', w, '`slot`을 %s 중 하나로 쓴다(지금 `%s`)' % ('·'.join(ORDER), slot))
        elif ORDER.index(slot) < last:
            add('FAIL', w, '자리 순서가 어긋난다: `%s`는 앞에 와야 한다' % slot)
        else:
            last = ORDER.index(slot)
        if (slot == 'cover') != (i == 1) or (slot == 'close') != end:
            add('FAIL', w, '첫 장은 cover, 마지막 장은 close 하나씩이다')
        title = str(s.get('title') or '').strip()
        for k, ko in (('title', '제목'), ('notes', '발표자 노트')) + (() if end else (('next', '다음 질문'),)):
            if not str(s.get(k) or '').strip():
                add('FAIL', w, '`%s`(%s)가 비었다' % (k, ko))
        if title and title in titles:
            add('FAIL', w, '%d장과 제목이 같다' % titles[title])
        titles[title] = i
        ids = s['f'] = chk.known_ids(w, [str(f) for f in M.as_list(s.get('f'))])
        if not ids and slot not in ('cover', 'close'):
            add('FAIL', w, '근거(`f`)가 없다')
        viz, data = s.get('viz'), s.get('data')
        if viz is None and end:
            pass
        elif viz not in PARTS:
            add('FAIL', w, '`viz`를 %s 중 하나로 쓴다' % '·'.join(PARTS))
        elif not isinstance(data, dict) or not data:
            add('FAIL', w, '`data`(그림 데이터)가 없다. 모양은 assets/slides.html의 %s 예시' % viz)
        else:
            if not str(s.get('alt') or '').strip():
                add('FAIL', w, '`alt`(그림 한 줄 설명)가 비었다')
            chk.kit({'key': w + '.data', 'n': None}, data)
            facts, got, files = chk.evidence(ids)
            for v in dict.fromkeys(measured(data)):
                if any(r['text'] for r in got):
                    chk.near(w + '.data', '%s%s' % (v, data.get('unit') or ''), facts, got, files or chk.cited_files)
                if not chk.source.number_ok(T.number_set(str(v)), chk.cited_files) and not T.number_set(str(v)) & chk.model_numbers:
                    add('WARN', w + '.data', '그림의 값 %s%s 원문에 없다. 원문 값으로 고치거나 어림이면 `est`를 쓴다' % (v, T.josa(v)))
        for k in ('title', 'say', 'notes', 'next'):
            if s.get(k):
                chk.check_text('%s.%s' % (w, k), str(s[k]), ids, linked=False, conds=False)
        whole = ' / '.join([str(s.get(k) or '') for k in ('title', 'say', 'notes', 'alt')] + texts(data))          # 조건은 장 어디에든(그림·노트) 있으면 된다
        for f in ids:
            chk.keeps(w, whole, f)
        if i > 2 and viz and viz == slides[i - 2].get('viz') == slides[i - 3].get('viz'):
            add('WARN', w, '같은 부품(%s)이 잇달아 세 장이다' % viz)
    if rows and len(slides) < len(rows) - 2:
        add('WARN', 'slides', '%d장이다. 이 유형의 틀은 %d장이다(채울 것이 없으면 그대로 둔다)' % (len(slides), len(rows)))
    if j.get('no_chart'):
        chk.check_text('no_chart', str(j['no_chart']), [], linked=False)
    if j.get('missing'):
        chk.check_text('missing', str(j['missing']), [], linked=False)
    M.flush_idents(chk.source, chk.later, chk.add)
    return out + chk.issues, slides


def texts(v):
    """그림 데이터 안의 글"""
    return [v] if isinstance(v, str) else [t for x in (v.values() if isinstance(v, dict) else v if isinstance(v, list) else []) for t in texts(x)]


def as_number(x):
    """숫자로 읽히는 글("1234")은 숫자로 (slides.html이 막대로 그린다)"""
    if not isinstance(x, str) or not re.fullmatch(r'\s*[+-]?(?:\d[\d,]*\.?\d*|\.\d+)(?:[eE][+-]?\d{1,2})?\s*', x):
        return x
    n = float(x.replace(',', ''))
    return int(n) if n == int(n) else n


def measured(v):
    """그림 데이터의 측정값·기준값(v·value·base·lo·hi의 숫자와 숫자로 읽히는 글, 그 배열). 좌표·순번·축 최대는 뺀다."""
    if isinstance(v, list):
        return [n for x in v for n in measured(x)]
    if not isinstance(v, dict):
        return []
    keys = ('v', 'value', 'base') + (('lo', 'hi') if 'lo' in v else ())
    got = [as_number(x) for k in keys for x in (v[k] if isinstance(v.get(k), list) else [v.get(k)]) if not v.get('est')]
    return [x for x in got if isinstance(x, (int, float)) and not isinstance(x, bool)] + [n for x in v.values() for n in measured(x)]


def inline(s):
    return re.sub(r'`([^`]+)`', r'<code>\1</code>', html.escape(str(s or '').strip(), quote=False))


def section(s, i, n, ctx):
    p, cover, end = [], i == 1, i == n
    if cover and ctx['notice']:
        p.append('<p class="notice">%s</p>' % inline(ctx['notice']))
    kick = ' · '.join(x for x in (ctx['type_name'], ctx['scope'], 'into slides') if x) if cover else ctx['kicker'][s['slot']]
    p.append('<p class="kicker">%s</p>' % inline(s.get('kicker') or kick))
    p.append('<h1>%s</h1>' % inline(s['title']) if cover else '<h2>%s</h2>' % inline(s['title']))
    if s.get('say'):
        p.append('<p class="say">%s</p>' % inline(s['say']))
    if s.get('viz'):
        data = json.dumps(s['data'], ensure_ascii=False).replace('<', '\\u003c').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
        p.append('<div class="viz" data-viz="%s" aria-label="%s"><script type="application/json">%s</script></div>' % (s['viz'], html.escape(str(s['alt']).replace('`', '')), data))
    if cover:
        p.append('<p class="src">원문: %s</p>' % inline(ctx['source']))
    if end:
        p += ['<p class="src">빠진 디테일: %s</p>' % inline(ctx['missing']), '<p class="src">출처: %s</p>' % inline(ctx['source'])]
    else:
        p.append('<p class="next-q">다음 질문 → %s</p>' % inline(s['next']))
    cites = ctx['cite'](s['f'], 6)
    p.append('<aside class="notes">%s%s</aside>' % (inline(s['notes']), ' · 근거: ' + inline(cites) if cites else ' · 근거: 앞 장들'))
    return '<section class="slide">\n  ' + '\n  '.join(p) + '\n  </section>'


def kickers(spec):
    """머리말 = 그 유형의 eli5 칸 이름(자리마다 첫 칸)"""
    return dict({r['slot']: r['label'] for r in reversed(spec.rows('eli5') or [])}, close=KICKER['close'])


def render(ctx, slides):
    with open(os.path.join(ASSETS, 'slides.html'), encoding='utf-8') as f:
        page = f.read()
    m = re.match(r'(.*?<main class="deck"><div class="stage">).*?(</div></main>.*)\Z', page, re.S)
    if not m:
        raise UserError('assets/slides.html에서 장 자리를 못 찾았다')
    head = re.sub(r'<!-- into slides.*?-->\n?', '', m.group(1), flags=re.S).replace('{{주제}}', html.escape(ctx['title'] or slides[0]['title'], quote=False))
    body = '\n\n  '.join(section(s, i, len(slides), ctx) for i, s in enumerate(slides, 1))
    return head + '\n\n  ' + body + '\n\n' + m.group(2)


def static(page, base, why=''):
    """check_slides.py의 정적 검사 → Issue 목록. why = slides.json의 no_chart(차트·영상을 안 넣은 이유)"""
    _, _, fails, warns = check_slides.inspect(page, base)
    warns = [x for x in warns if not (why and x.startswith(('차트가 없다', 'MP4 영상이 없다')))]
    return [Issue('FAIL', 'slides', x) for x in fails] + [Issue('WARN', 'slides', x) for x in warns]

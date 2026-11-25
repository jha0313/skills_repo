# -*- coding: utf-8 -*-
"""test: 문항 JSON → 정답 자리 섞기 · 길이 · 누출 검사 → assets/test.html의 QUIZ."""
import json
import math
import os
import random
import re

from . import ASSETS, DOC_TITLES, SLOTS, UserError
from . import model as M
from . import text as T
from .formats import Issue

JOSA = re.compile(r'(?:입니다|합니다|됩니다|이다|한다|된다|하고|하지|하며|하면|되면|이면|에서는|에서|으로|에게|까지|부터|처럼|보다|라고|이라|은|는|이|가|을|를|에|의|로|와|과|도|만|다)$')
COMMON = set('경우 때문 것이 그것 이것 원문 실행 사용 있다 없다 한다 된다 그대로 다른 같은 하나 모두 먼저 다음 결과 이유 조건 기본 설정 파일 값이'.split())
LETTERS = re.compile(r'(?:보기|선택지|답)\s*[A-D](?![A-Za-z])|(?<![A-Za-z0-9가-힣])[A-D](?:\s?[·,/]\s?[A-D])+(?![A-Za-z])|(?<![A-Za-z0-9가-힣`])[A-D](?:는|은|가|이|도|를|을|와|과|번)(?=[\s,.])|(?<![A-Za-z0-9])\([A-D]\)')


def toks(s):
    """핵심어: 코드 이름 · 숫자 · 조사를 뗀 한글 낱말."""
    s = T.visible(s)
    out = {w.lower() for w in re.findall(r'[A-Za-z_][A-Za-z0-9_\-.]{2,}', s)} | set(re.findall(r'\d[\d,.]*\d|\d', s))
    for w in re.findall(r'[가-힣]{2,}', s):
        st = JOSA.sub('', w)
        if len(st) >= 2 and st not in COMMON:
            out.add(st)
    return out


def check(j, model, chk, size, rows=None):
    out = []

    def add(level, where, msg):
        out.append(Issue(level, 'test.json %s' % where if where else 'test.json', msg))
    qs = [dict(q) for q in M.as_list(j.get('questions')) if isinstance(q, dict)]
    if not qs:
        add('FAIL', 'questions', '문항이 없다. `"questions":[…]`로 쓴다')
        return out, qs
    n = len(qs)
    if not 5 <= n <= 10:
        add('FAIL', 'questions', '문항이 %d개다. 5~10개로 쓴다(기본 8, 작은 원문 5)' % n)
    elif (size == '작음' and n > 6) or (size != '작음' and n < 8):
        add('WARN', 'questions', '문항이 %d개다. %s 원문의 기본은 %d개다' % (n, size, 5 if size == '작음' else 8))
    preds = [q for q in qs if q.get('type') == 'predict']
    if len(preds) < 2:
        add('FAIL', 'questions', 'predict가 %d개다. 2개 이상 쓴다' % len(preds))
    longest, shortest, counted = [], [], 0
    for i, q in enumerate(qs, 1):
        w = 'questions[%d]' % i
        if q.get('slot') not in SLOTS:
            add('FAIL', w, '`slot`을 one·why·pic·run·catch 중 하나로 쓴다')
        if not str(q.get('q') or '').strip():
            add('FAIL', w, '질문(`q`)이 비었다')
        ids = chk.known_ids(w, [str(f) for f in M.as_list(q.get('f'))])
        q['f'] = ids
        if not ids:
            add('FAIL', w, '근거(`f`)가 없다. 답을 정하는 사실 id를 쓴다')
        weak = sorted({k for f in ids for k in M.marks(chk.refs[f]) if k in ('추정', '불확실', '보충')})
        if weak:
            add('WARN', w, '근거가 %s다. 답이 하나로 정해지는지 본다' % '·'.join(weak))
        texts = [('q', q.get('q')), ('explain', q.get('explain')), ('right', q.get('right')), ('model', q.get('model'))] + [('must', x) for x in M.as_list(q.get('must'))]
        for k, s in texts:
            if s:                                               # 그 문항의 근거와 견준다. 채점 기준의 숫자가 다른 곳 값이면 FAIL
                n0 = len(chk.issues)
                chk.check_text('%s.%s' % (w, k), str(s), ids, linked=False, conds=False)
                for x in chk.issues[n0:] if k in ('right', 'model', 'must') else []:
                    if x.msg.startswith(('근거 구간에 없음', '단위가 근거와', '부호가 근거와')):
                        x.level = 'FAIL'
        if q.get('type') == 'choice':
            right, wrong = str(q.get('right') or '').strip(), [str(x).strip() for x in M.as_list(q.get('wrong')) if str(x).strip()]
            q['right'], q['wrong'] = right, wrong
            if not right:
                add('FAIL', w, '정답(`right`)이 비었다')
                continue
            if not 2 <= len(wrong) <= 3:
                add('FAIL', w, '오답이 %d개다. 2~3개 쓴다' % len(wrong))
                if not wrong:
                    continue
            if len({T.visible(x) for x in [right] + wrong}) < 1 + len(wrong):
                add('FAIL', w, '같은 보기가 있다')
            if not str(q.get('explain') or '').strip():
                add('FAIL', w, '해설(`explain`)이 비었다. 왜 맞고 오답이 왜 틀린지 쓴다')
            lr, lw = T.count(right), [T.count(x) for x in wrong]
            mean = sum(lw) / float(len(lw))
            if lr > mean * 1.3 + 1e-9:
                add('FAIL', w, '정답이 길어서 보인다: %d자 > 오답 평균 %.1f × 1.3. 정답을 줄이거나 오답을 같은 자세함으로 쓴다' % (lr, mean))
            elif lr < mean * 0.5 - 1e-9:
                add('FAIL', w, '정답이 짧아서 보인다: %d자 < 오답 평균 %.1f × 0.5' % (lr, mean))
            if len(set([lr] + lw)) > 1:
                counted += 1
                if lr > max(lw):
                    longest.append(i)
                if lr < min(lw):
                    shortest.append(i)
            m = LETTERS.search(str(q.get('explain') or ''))
            if m and not any(re.search(r'(?<![A-Za-z])%s(?![A-Za-z])' % re.escape(c), ' '.join([q.get('q') or '', right] + wrong)) for c in re.findall('[A-D]', m.group(0))):
                add('FAIL', w, '해설이 보기를 글자(`%s`)로 가리킨다. 자리를 섞으므로 보기 문구로 가리킨다' % m.group(0).strip())
            only = toks(right) - set().union(*[toks(x) for x in wrong])
            hit = sorted(only & toks(str(q.get('q') or '')))
            if hit:
                add('WARN', w, '질문에 정답만의 낱말이 있다: %s' % ', '.join(hit[:4]))
        elif q.get('type') == 'predict':
            must = [str(x).strip() for x in M.as_list(q.get('must')) if str(x).strip()]
            q['must'] = must
            if not str(q.get('model') or '').strip():
                add('FAIL', w, '모범 답(`model`)이 비었다')
            if not must:
                add('FAIL', w, '필수 요소(`must`)가 없다. 맞음/틀림이 갈리게 쓴다')
            if any(re.search(r'대략|중 (?:하나|둘)|부분 점수|정도면', x) for x in must):
                add('WARN', w, '필수 요소에 부분 점수 말이 있다. 맞음/틀림이 갈리게 쓴다')
            qt = toks(str(q.get('q') or ''))
            for x in must:
                kx = toks(x)
                if len(kx) >= 2 and kx <= qt and (re.sub(r'\s', '', T.visible(x)) in re.sub(r'\s', '', T.visible(q['q'])) or T.similar(x, q['q']) >= 0.9):
                    add('WARN', w, '질문에 필수 요소가 그대로 있다: %s' % T.clip(x, 40))
                miss = kx - toks(str(q.get('model') or ''))
                if kx and len(miss) > len(kx) * 0.7:
                    add('WARN', w, '모범 답이 필수 요소를 말하지 않는 것 같다: %s' % T.clip(x, 40))
        else:
            add('FAIL', w, '`type`을 choice 또는 predict로 쓴다')
    if counted:
        cap = int(math.ceil(counted / 3.0))
        if len(longest) > cap:
            add('FAIL', 'questions', '정답이 혼자 가장 긴 문항이 %d개(%s)다. %d개까지다' % (len(longest), ', '.join(map(str, longest)), cap))
        if len(shortest) > cap:
            add('WARN', 'questions', '정답이 혼자 가장 짧은 문항이 %d개(%s)다' % (len(shortest), ', '.join(map(str, shortest))))
    _leaks(qs, add)
    if rows is not None:
        want = [r.get('종류', '').strip('` ') for r in rows]
        if n == len(want) and want.count('predict') > len(preds):
            add('WARN', 'questions', '이 유형의 틀은 predict %d개다' % want.count('predict'))
    M.flush_idents(chk.source, chk.later, chk.add)
    return out + [x for x in chk.issues if not re.search(r'이 모드의 표에 없는 키|필수 칸', x.msg)], qs


def _leaks(qs, add):
    for b in range(1, len(qs)):
        q = qs[b]
        if q.get('type') == 'choice' and q.get('right'):
            keys = toks(q['right']) - set().union(set(), *[toks(x) for x in q.get('wrong') or []])
        else:
            keys = set().union(set(), *[toks(x) for x in q.get('must') or []])
        keys -= toks(str(q.get('q') or ''))
        if len(keys) < 2:
            continue
        for a in range(b):
            p = qs[a]
            for k, s in (('해설', p.get('explain')), ('보기', ' '.join([str(p.get('right') or '')] + [str(x) for x in p.get('wrong') or []])), ('모범 답', p.get('model'))):
                hit = keys & toks(str(s or ''))
                if len(hit) >= 2 and len(hit) >= len(keys) * 0.6:
                    add('WARN', 'questions[%d]' % (b + 1), '앞 문항 %d의 %s에 답의 핵심어가 있다: %s. 순서를 바꾸거나 해설을 줄인다' % (a + 1, k, ', '.join(sorted(hit)[:4])))


def positions(slug, sizes):
    """보기 수 목록 → 정답 자리 (slug 시드, 같은 자리 3연속 · 절반 초과 없음)."""
    rnd, out, cap = random.Random('into:' + slug), [], max(1, len(sizes) // 2)
    for n in sizes:
        ok = [p for p in range(n) if out.count(p) < cap and not (len(out) >= 2 and out[-1] == out[-2] == p)]
        out.append(rnd.choice(ok or [p for p in range(n) if not (len(out) >= 2 and out[-1] == out[-2] == p)]))
    return out


def build(ctx, qs, slug):
    rnd = random.Random('order:' + slug)
    ch = [q for q in qs if q['type'] == 'choice']
    pos = dict(zip([id(q) for q in ch], positions(slug, [1 + len(q['wrong']) for q in ch])))
    out = []
    for q in qs:
        o = {'section': DOC_TITLES[q['slot']], 'type': q['type'], 'q': str(q['q']).strip()}
        if q['type'] == 'choice':
            opts = list(q['wrong'])
            rnd.shuffle(opts)
            opts.insert(pos[id(q)], q['right'])
            o.update(options=opts, answer=pos[id(q)], explain=str(q['explain']).strip())
        else:
            must = q['must']
            o.update(model=str(q['model']).strip(), explain='필수 ' + ' '.join('%s %s' % ('①②③④⑤⑥⑦⑧⑨'[i] if i < 9 else '·', x) for i, x in enumerate(must)) + (' — 모두 있으면 맞음' if len(must) > 1 else ' — 있으면 맞음'))
        o['source'] = ctx['cite'](q['f'], 4)
        out.append(o)
    quiz = {'title': ctx['title'] + ' 이해 확인', 'notice': ctx['notice'], 'source': ctx['source'], 'scope': ctx['scope'], 'missing': ctx['missing'], 'questions': out}
    path = os.path.join(ASSETS, 'test.html')
    if not os.path.exists(path):
        raise UserError('assets/test.html이 없다')
    page = open(path, encoding='utf-8').read()
    data = json.dumps(quiz, ensure_ascii=False, indent=2).replace('</', '<\\/').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
    new, n = re.subn(r'const QUIZ = \{.*?\n\};', lambda m: 'const QUIZ = ' + data + ';', page, count=1, flags=re.S)
    if n != 1:
        raise UserError('assets/test.html에서 `const QUIZ = {…};` 자리를 못 찾았다')
    return new, quiz

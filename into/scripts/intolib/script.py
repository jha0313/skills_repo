# -*- coding: utf-8 -*-
"""shorts · video: 장면 JSON → 음절 → 시간 → 대본 + 스토리보드."""
import math
import re

from . import DOC_TITLES, SLOTS
from . import model as M
from . import text as T
from .formats import Issue

PER_SEC, GAP, ASK = 5.5, 0.3, 1.0          # 초당 음절 한도 · 문장 사이 · 질문 뒤 (0.7 modes/shorts.md의 값)
MAX_SHORTS = 60.0
CAP_CHARS, TITLE_CHARS = 24, 28            # 안전 영역: 자막 2줄 × 12자(660px에 56px 글자), 제목 2줄 × 14자(768px)
MIN_SCENE = 2.0
HOOK = ('hook', '훅')
ENDS = ('outro', '마무리', 'close', 'fixed')
ORDER = ('hook',) + SLOTS + ('outro',)
SLOT_KO = dict(DOC_TITLES, hook='훅', outro='마무리')

LETTER = dict(zip('ABCDEFGHIJKLMNOPQRSTUVWXYZ', (2, 1, 1, 1, 1, 2, 1, 3, 2, 2, 2, 1, 1, 1, 1, 1, 1, 1, 2, 1, 1, 2, 3, 2, 2, 2)))
WORD = {'codex': 3, 'claude': 3, 'github': 3, 'cache': 2, 'server': 2, 'json': 3, 'uv': 3, 'openai': 5, 'anthropic': 4, 'code': 2, 'agent': 4, 'token': 2, 'model': 2,
        'prompt': 4, 'python': 2, 'rust': 3, 'stdio': 5, 'error': 2, 'lock': 1, 'file': 2, 'skill': 2, 'html': 6, 'youtube': 3, 'chatgpt': 5, 'gemini': 3, 'cursor': 2}
SYMBOL = {'%': 3, '+': 3, '−': 4, '×': 3, '=': 2, '&': 2, '@': 3, '$': 2, '#': 1, '≥': 2, '≤': 2}
GREET = re.compile(r'[^.!?\n]*(?:안녕하세요|구독[\s,·과와]*좋아요|수고하셨습니다|다음에 (?:또 )?뵙겠습니다)[^.!?\n]*[.!?]?|(?<![^.!?\s])감사합니다[.!?]?')          # 고정 인사말(사실이 아니다)
OUTSIDE = re.compile(r'(?:html|interactive|doc|slides|eli5|ste|퀴즈|문서|슬라이드)\s*(?:모드|결과|와 같은|과 같은|처럼|참고|에 있는)|(?:앞|다른|이전)\s*모드|대본\s*(?:참고|아래|위|밖|을 본)|근거\s*열|스토리보드\s*(?:참고|위|아래)|설명란\s*(?:참고|을 본)|답은\s*(?:대본|아래|설명)|표\s*(?:아래|참고)')


def sino(n):
    """정수 → 한자어 수의 음절 수 (1385 → 천삼백팔십오 → 6)"""
    if n == 0:
        return 1
    total, unit = 0, 0
    while n:
        part = n % 10000
        if part:
            c = 0
            for i, d in enumerate(reversed(str(part))):
                d = int(d)
                if d:
                    c += (0 if d == 1 and i else 1) + (1 if i else 0)
            if unit and part == 1:
                c = 1 if unit > 1 else 0
            total += c + (1 if unit else 0)
        n //= 10000
        unit += 1
    return total


def english(w):
    """영문 낱말 → (읽는 소리 음절 수, 어림인가)"""
    if w.lower() in WORD:
        return WORD[w.lower()], False
    if w.isupper() and len(w) <= 5:
        return sum(LETTER[c] for c in w), False
    n = 0
    for part in re.findall(r'[A-Z]{2,}(?![a-z])|[A-Z]?[a-z]+|[A-Z]', w):
        if part.isupper():
            n += sum(LETTER[c] for c in part)
        elif part.lower() in WORD:
            n += WORD[part.lower()]
        else:
            p = re.sub(r'(?<=[^aeiou])e$', '', part.lower())
            n += max(1, len(re.findall(r'[aeiouy]+', p)) + len(re.findall(r'[^aeiouy](?=[^aeiouylrwnm])', p)) + (1 if re.search(r'(?:[sztdkfvxj]|ch|sh)$', p) else 0))
    return n, True


def syllables(s):
    """(음절 수, 어림한 영문이 있나) — 영문 · 숫자 · 기호는 읽는 소리로 센다."""
    s = re.sub(r'[`*]', '', s)
    n, est = 0, False
    for m in re.finditer(r'[가-힣]|\d[\d,]*(?:\.\d+)*|[A-Za-z]+|[%+−×=&@$#≥≤]', s):
        t = m.group(0)
        if '가' <= t <= '힣':
            n += 1
        elif t[0].isdigit():
            parts = t.replace(',', '').split('.')
            n += sino(int(parts[0]))
            for p in parts[1:]:
                n += 1 + (len(p) if len(parts) == 2 else sino(int(p)))
        elif t in SYMBOL:
            n += SYMBOL[t]
        else:
            k, e = english(t)
            n, est = n + k, est or e
    return n, est


def spoken(say):
    return [x for x in re.split(r'(?<=[.!?。])\s+|\n+', say.strip()) if x.strip()]


def pauses(say, last=False):
    ss = spoken(say)
    p = 0.0
    for i, x in enumerate(ss):
        if re.search(r'[?？]["\'”’)]*\s*$', x):
            p += ASK
        elif not (last and i == len(ss) - 1):
            p += GAP
    return p


def scene_seconds(say, last=False):
    n, est = syllables(say)
    p = pauses(say, last)
    return n, p, max(MIN_SCENE, math.ceil((n / PER_SEC + p) * 10 - 1e-9) / 10.0), est


def check(mode, j, model, chk, size):
    """(issues, scenes) — scenes에 n·pause·sec·start를 더한다."""
    out, file = [], mode + '.json'

    def add(level, where, msg):
        out.append(Issue(level, '%s %s' % (file, where) if where else file, msg))
    scenes = [dict(x) for x in M.as_list(j.get('scenes')) if isinstance(x, dict)]
    if not scenes:
        add('FAIL', 'scenes', '장면이 없다. `"scenes":[{"slot":"hook","say":…}]`로 쓴다')
        return out, scenes
    last_i, seen, t = -1, [], 0.0
    for i, x in enumerate(scenes, 1):
        w = 'scenes[%d]' % i
        slot = str(x.get('slot') or '')
        slot = 'hook' if slot in HOOK else 'outro' if slot in ENDS else slot
        x['slot'] = slot
        if slot not in ORDER:
            add('FAIL', w, '`slot`을 hook·one·why·pic·run·catch(·outro) 중 하나로 쓴다(지금 `%s`)' % slot)
        else:
            if ORDER.index(slot) < last_i:
                add('FAIL', w, '칸 순서가 어긋난다: `%s`는 앞에 와야 한다' % slot)
            last_i = max(last_i, ORDER.index(slot))
        seen.append(slot)
        fixed = bool(x.get('fixed'))
        for k, ko in (('say', '나레이션'), ('visual', '화면')) + (() if fixed else (('title', '제목'), ('caption', '자막')) if mode == 'shorts' else (('title', '제목'),)):
            if not str(x.get(k) or '').strip():
                add('FAIL' if k in ('say', 'visual') else 'WARN', w, '`%s`(%s)가 비었다' % (k, ko))
        ids = chk.known_ids(w, [str(f) for f in M.as_list(x.get('f'))])
        x['f'] = ids
        if not ids and not fixed and slot not in ('hook', 'outro'):
            add('FAIL', w, '근거(`f`)가 없다')
        elif not ids and slot == 'hook' and not fixed:
            add('WARN', w, '훅에 근거(`f`)가 없다')
        say = str(x.get('say') or '')
        for k in ('say', 'title', 'caption', 'visual'):
            s = str(x.get(k) or '')
            if s and not fixed:
                chk.check_text('%s.%s' % (w, k), GREET.sub(' ', s) if k == 'say' else s, ids, linked=False, conds=False)
            if k != 'say' and OUTSIDE.search(s):
                add('FAIL', w, '`%s`가 다른 모드나 대본 밖을 가리킨다: "%s". 그것만 읽고 그릴 수 있게 쓴다' % (k, OUTSIDE.search(s).group(0)))
        for f in ids if not fixed else []:                                     # 조건은 말·제목·자막 가운데 하나에 있으면 된다
            chk.keeps(w, ' / '.join(str(x.get(k) or '') for k in ('say', 'title', 'caption')), f)
        marks = [m for f in ids for m in M.marks(chk.refs[f])]
        if '추정' in marks and '추정' not in say:
            add('FAIL', w, '추정 사실을 쓰는데 나레이션이 추정이라고 말하지 않는다')
        if '불확실' in marks and not re.search(r'불확실|확인하지 못|엇갈', say):
            add('WARN', w, '불확실 표시가 나레이션에 없다')
        if '근거 미제시' in marks and not any('근거' in str(y.get('say') or '') for y in scenes):
            add('WARN', w, '근거 미제시 주장이다. 나레이션에서 한 번 말한다')
        if re.search(r'`|[a-z]_[a-z]|[a-z][A-Z]', say) and not fixed:
            add('WARN', w, '나레이션에 식별자가 있다. 쉬운 이름으로 말하고 식별자는 화면에 둔다')
        if mode == 'shorts':
            c, ti = T.count(x.get('caption')), T.count(x.get('title'))
            if c > CAP_CHARS:
                add('WARN', w, '자막 %d자 — 안전 영역 2줄(%d자)을 넘을 수 있다' % (c, CAP_CHARS))
            if ti > TITLE_CHARS:
                add('WARN', w, '제목 %d자 — 2줄(%d자)을 넘을 수 있다' % (ti, TITLE_CHARS))
        n, p, sec, est = scene_seconds(say, i == len(scenes))
        want = x.get('sec')
        if isinstance(want, (int, float)) and not isinstance(want, bool):
            if want < sec - 0.05 and sec > MIN_SCENE:
                add('FAIL', w, '%s초에 %d음절(쉼 %.1f초)은 초당 %.1f음절이다. %.1f초 이상으로 늘리거나 다른 사실을 뺀다' % (want, n, p, n / max(0.1, want - p), sec))
            sec = float(want)
        x.update(n=n, pause=p, seconds=sec, est=est, start=t)
        t += sec
    if mode == 'shorts':
        if seen[0] != 'hook':
            add('FAIL', 'scenes[1]', '첫 장면은 hook이다')
        if t > MAX_SHORTS + 1e-6:
            worst = max(range(len(scenes)), key=lambda k: scenes[k]['seconds'])
            add('FAIL', '', '총 %.1f초다. 60초까지다. 조건을 지우지 말고 다른 사실을 뺀다(가장 긴 장면 %d: %.1f초)' % (t, worst + 1, scenes[worst]['seconds']))
    else:
        for i, x in enumerate(scenes, 1):
            if not str(x.get('chapter') or '').strip():
                add('FAIL', 'scenes[%d]' % i, '`chapter`(챕터 이름)를 쓴다')
            elif i < len(scenes) and not x.get('fixed') and not scenes[i].get('fixed') and scenes[i].get('chapter') != x['chapter'] and not (x.get('next') or re.search(r'[?？]\s*$', str(x.get('say') or ''))):
                add('WARN', 'scenes[%d]' % i, '챕터 끝에 `"next":"다음 질문"`을 쓴다(다음 챕터가 답한다)')
        lo, hi = {'작음': (60, 180), '보통': (300, 480), '큼': (480, 720)}[size]
        body = sum(x['seconds'] for x in scenes if not x.get('fixed'))
        if not j.get('minutes') and not lo * 0.9 <= body <= hi * 1.1:
            add('WARN', '', '본문 %s — %s 원문의 기본은 %d~%d분이다(사용자가 정했으면 `"minutes"`에 쓴다)' % (clock(body), size, lo // 60, hi // 60))
        elif j.get('minutes') and abs(body / 60.0 - float(j['minutes'])) > max(0.5, float(j['minutes']) * 0.15):
            add('WARN', '', '본문 %s — 사용자가 정한 %s분과 다르다' % (clock(body), j['minutes']))
    for s in ('one', 'pic'):
        if s not in seen:
            add('FAIL', 'scenes', '`%s` 장면이 없다' % s)
    for s in ('why', 'run', 'catch'):
        if s not in seen:
            add('WARN', 'scenes', '`%s` 장면이 없다(원문에 없으면 그대로 둔다)' % s)
    hook = next((x for x in scenes if x['slot'] == 'hook'), None)
    if hook and re.search(r'[?？]', str(hook.get('say') or '')):
        ans = M.as_list(j.get('answer'))
        nums = [int(a) for a in re.findall(r'\d+', ' '.join(str(a) for a in ans))]
        if not nums:
            add('FAIL', 'answer', '훅이 질문인데 `answer`(답하는 장면 번호)가 없다')
        elif not all(2 <= a <= len(scenes) for a in nums):
            add('FAIL', 'answer', '장면 %s는 없다(2~%d)' % (nums, len(scenes)))
    if not str(j.get('check') or '').strip():
        add('WARN', 'check', '확인 질문과 답을 `"check":"질문 → 답"`으로 쓴다')
    if j.get('missing'):
        chk.check_text('missing', str(j['missing']), [], linked=False)
    M.flush_idents(chk.source, chk.later, chk.add)
    for i in chk.issues:
        out.append(i)
    return out, scenes


def clock(t, dec=False):
    m, s = divmod(t, 60)
    return '%d:%04.1f' % (m, s) if dec else '%d:%02d' % (m, int(round(s))) if round(s) < 60 else '%d:00' % (m + 1)


def cell(s):
    return re.sub(r'\s*\n\s*', ' ', str(s or '')).replace('|', '／').strip()


def render(mode, ctx, j, scenes):
    total = sum(x['seconds'] for x in scenes)
    out = [ctx['notice'], ''] if ctx['notice'] else []
    title = ctx['title'] + (' · ' + ctx['scope'] if ctx['scope'] else '')
    if mode == 'shorts':
        out += ['# %s — 쇼츠 (%.1f초, 9:16)' % (title, total), '']
    else:
        out += ['# %s — 영상 (%s, 16:9)' % (title, clock(total)), '']
        fixed = sum(x['seconds'] for x in scenes if x.get('fixed'))
        if fixed:
            out += ['고정 문구 %s는 따로 셌다(본문 %s).' % (clock(fixed), clock(total - fixed)), '']
        ch = None
        for x in scenes:
            if x.get('chapter') != ch:
                ch = x.get('chapter')
                grp = [y for y in scenes if y.get('chapter') == ch]
                out += ['## %s (%s–%s)' % (cell(ch), clock(grp[0]['start']), clock(grp[-1]['start'] + grp[-1]['seconds'])), '']
            out += [str(x.get('say') or '').strip(), '']
            if x.get('demo'):
                out += ['[데모] ' + cell(x['demo']), '']
            if x.get('next'):
                out += ['> 다음 질문 → ' + cell(x['next']), '']
        out += ['## 스토리보드', '']
    head = ['#', '시간', '칸', '제목', '나레이션', '음절 / 발화 가능 초 / 초당', '화면 자막', '화면', '근거']
    out += ['| ' + ' | '.join(head) + ' |', '|' + '---|' * len(head)]
    for i, x in enumerate(scenes, 1):
        room = max(0.1, x['seconds'] - x['pause'])
        tm = '%.1f–%.1f' % (x['start'], x['start'] + x['seconds']) if mode == 'shorts' else '%s–%s' % (clock(x['start']), clock(x['start'] + x['seconds']))
        out.append('| %d | %s | %s | %s | %s | %d%s / %.1f / %.1f | %s | %s | %s |' % (
            i, tm, SLOT_KO.get(x['slot'], x['slot']) + (' · ' + cell(x['chapter']) if x.get('chapter') else ''), cell(x.get('title')), cell(x.get('say')), x['n'], '(어림)' if x['est'] else '', room, x['n'] / room,
            cell(x.get('caption')), cell(x.get('visual')), cell(ctx['cite'](x['f'], 4))))
    out += ['', '쉼: 문장 사이 %.1f초 · 질문 뒤 %.0f초. 영문·숫자는 읽는 소리로 센 음절(%s).' % (GAP, ASK, '`어림`은 소리 내어 확인')]
    if j.get('answer') not in (None, '', []):
        out.append('훅의 답: 장면 %s' % ', '.join(re.findall(r'\d+', str(j['answer']))))
    if j.get('check'):
        out.append('확인 질문: ' + cell(j['check']))
    out += ['', '빠진 디테일: ' + ctx['missing'], '출처: ' + ctx['source']]
    return '\n'.join(out) + '\n'

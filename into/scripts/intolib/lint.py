# -*- coding: utf-8 -*-
"""결과 파일 검사 (JSON 없이 손으로 만든 것 · html · shorts) 와 ste 린터."""
import html as H
import json
import re

from . import DOC_TITLES, SLOTS, TEXT_MODES, formats
from . import model as M
from . import script as S
from . import text as T
from .formats import PIC_FORMS, Issue

# ---------- ste 린터 ----------
STE_KO, STE_EN = 60, 25           # 한국어 문장 60자 · 영어 문장 25단어 (괄호·백틱 안은 빼고 센다)
NOUN_GO = set('재고 보고 경고 참고 광고 사고 최고 창고 중고 권고 신고 원고 로고 비고 피고 충고 예고 선고 공고 기고 그리고 하고많은 되고말고 결코 자고 라고 이라고 다고 냐고 별고 통고 퇴고 저장고 냉장고 탈고 기록고'.split())
NOT_SEO = re.compile(r'(?:에서|에게서|께서|로서|로써|문서|순서|부서|각서|명세서|보고서|설명서|계약서|지시서|도서|질서|독서|비서|용서|답서|따라서|그래서|이래서|위해서|통해서|대해서|관해서|의해서|비해서|거쳐서|해당서|먼저서|단서|안내서|지침서|제안서|요청서|사용서|견적서|증서|앞서|어서|라서)$')


def _tokens(s):
    return [re.sub(r'^[\s"\'(“‘\[]+|[\s"\')\]”’,.;:!?]+$', '', w) for w in s.split()]


def _no_final(ch):
    return '가' <= ch <= '힣' and (ord(ch) - 0xAC00) % 28 == 0


def _vowel(ch):
    return ((ord(ch) - 0xAC00) % 588) // 28


def connectives(s):
    """한 문장 안에서 절을 잇는 어미를 가진 낱말들."""
    out, ws = [], _tokens(s)
    for i, w in enumerate(ws[:-1]):
        nxt = ws[i + 1]
        if len(w) < 2 or not re.search(r'[가-힣]$', w):
            continue
        if w.endswith('고') and w not in NOUN_GO and not re.search(r'(?:라고|다고|냐고|자고|으로고)$', w) and not any(w.endswith(n) and len(n) > 1 and n in ('경고', '권고', '보고', '신고', '광고', '참고', '사고', '재고', '창고') for n in NOUN_GO):
            if not re.match(r'(?:있|없|싶|나서|나면|말|계시|난|있는)', nxt):
                out.append(w)
        elif re.search(r'(?:으며|[가-힣]며)$', w):
            out.append(w)
        elif w.endswith('면서') and w not in ('그러면서', '이면서도'):
            out.append(w)
        elif w.endswith('지만') and w not in ('하지만', '그렇지만', '그러하지만') and not w.endswith('까지만'):
            out.append(w)
        elif re.search(r'(?:는데|은데|인데|한데)$', w) and w not in ('그런데', '가운데', '한가운데', '한데'):
            out.append(w)
        elif w.endswith('서') and len(w) >= 2 and not NOT_SEO.search(w) and _no_final(w[-2]) and _vowel(w[-2]) in (0, 1, 4, 6, 9, 14):     # ㅏ ㅐ ㅓ ㅕ ㅘ ㅝ
            out.append(w)
        elif re.search(r'(?:므로|으니까|니까)$', w):
            out.append(w)
    return out


PASSIVE_DOE = re.compile(r'[가-힣A-Za-z`](?:된다|됩니다|되었다|되었습니다|됐다|됐습니다|되지 않|되지 못|되어 있|돼 있|되며|되고|되면서|되지만)')
PASSIVE_ETC = re.compile(r'(?:이루어|만들어|나누어|주어|정해|알려|지워|밝혀|남겨|바뀌어|쓰여|미뤄|늦춰|켜|꺼|가려|합쳐|느껴|불러|여겨|풀어|쌓여|잘려|묶여)(?:진다|집니다|졌다|졌습니다|지지 않)|(?:보|쓰|쌓|섞|놓|묶|꺾|모|높|덮)인다|(?:읽|막|닫|잡|먹|묻|뽑|꽂|밟|얽|찍|잊|갇)힌다|(?:열|걸|들|불|풀|물|팔|잘|밀|눌|실|갈|뚫|달|깔|딸|놀|말)린다|(?:담|끊|안|쫓|남겨|감|찢|빼앗|씻|숨|뜯|옮)긴다|나뉜다|바뀐다|잠긴다|지워진다')
DEIXIS = re.compile(r'(?:^|[\s(])(이것|그것|저것|이것들|해당|상기|위의|아래의|앞의|전자|후자|이는|이를|이로 인해|이 때문에|이러한|그러한|이와 같은|그)(?:은|는|이|가|을|를|도|만|의|에|으로)?(?=\s)')
SEQ = re.compile(r'(?:^|[\s(])(먼저|우선|그다음|그 다음|다음으로|이어서|그 뒤|그 후|그러고 나서|마지막으로|첫째|둘째|셋째|끝으로)(?=[\s,])|\b(?:first|then|next|finally|afterwards)\b', re.I)
TAIL_COND = re.compile(r'(?:다|요|음|함)[,]\s*(?:단[,]?\s*)?[^.]{2,40}?(?:면|때|때만|경우|경우에|경우만|한해|한정)[.)]*\s*$|(?:다|요)\s*\((?:단[,]?\s*)?[^)]{2,40}?(?:면|때|때만|경우|경우에|경우만|일 때)\)[.]?\s*$|(?:다|요)\s*[—–-]\s*[^.]{2,40}?(?:면|때|때만|경우|경우에|경우만)[.]?\s*$')
TAIL_COND_EN = re.compile(r'^(?!\s*(?:if|when|unless|after|before|once)\b).{12,}?\s(?:if|when|unless|only if|as long as)\s[^,]{4,}[.]?\s*$', re.I)


def strip_ste(md):
    """산문만: 코드 블록 · 표 구분 · 메타 줄 · 백틱 · 인용을 뺀 [(줄 번호, 글, 번호 목록인가)]"""
    out, fence, skip = [], False, False
    for i, ln in enumerate(md.split('\n'), 1):
        if T.FENCE.match(ln):
            fence = not fence
            continue
        if fence or not ln.strip():
            skip = False if not ln.strip() else skip
            continue
        if T.META.match(ln) or T.NOTICE_LINE.match(ln):
            skip = True
            continue
        if skip and re.match(r'^\s*[-*]\s', ln):
            continue
        skip = False
        if re.match(r'^\s*#{1,6}\s', ln) or set(ln.strip()) <= set('|-: '):
            continue
        num = bool(re.match(r'^\s*(?:\*\*[^*]+\*\*\s*)?(?:\d{1,2}[.)]|[①-⑳])\s', ln))
        head = re.match(r'^\*\*[^*\n]+ · [^*\n]+\*\*\s+—\s+', ln)
        s = ln[head.end():] if head else T.LABEL.sub('', ln)
        s = re.sub(r'^\s*(?:[-*>]\s+|\d{1,2}[.)]\s+|[①-⑳]\s*)', '', s)
        for part in (T.split_row(s) if s.strip().startswith('|') else [s]):
            out.append((i, part, num))
    return out


def terms_of(md):
    """`용어:` 줄 → [(고정한 말, [원래 표기])]"""
    out = []
    for m in re.finditer(r'(?m)^\s*(?:\*\*)?용어(?:\*\*)?\s*[:：]\s*(.+)$', md):
        for part in re.split(r'\s+·\s+|;\s*', m.group(1)):
            a = re.match(r'^(.+?)\s*(?:→|->)\s*(.+)$', part)
            b = re.match(r'^(.+?)\s*(?:=|←|<-)\s*(.+)$', part)
            if a:
                out.append((a.group(2).strip('`"“” '), [x.strip('`"“” ') for x in re.split(r'\s+/\s+|,\s*', a.group(1))]))
            elif b:
                out.append((b.group(1).strip('`"“” '), [x.strip('`"“” ') for x in re.split(r'\s+/\s+|,\s*', b.group(2))]))
    return out


def ste(md, file=''):
    """[(규칙, 줄, 문구)]"""
    out = []
    prose = strip_ste(md)
    para, styles = {}, {}
    for no, raw, numbered in prose:
        s = re.sub(r'`[^`]*`', 'CODE', raw)
        s = re.sub(r'[“"][^”"\n]*[”"]', 'QUOTE', s)
        s = re.sub(r'\*\*', '', s)
        for x in T.sentences(s):
            short = T.clip(x, 46)
            bare = re.sub(r'\([^)]*\)', '', x).strip()
            ko = bool(re.search(r'[가-힣]', bare))
            if ko and T.count(bare) > STE_KO:
                out.append(('길이', no, '%d자 문장이다. %d자 안으로 나눈다: %s' % (T.count(bare), STE_KO, short)))
            elif not ko and len(bare.split()) > STE_EN:
                out.append(('길이', no, '%d단어 문장이다. %d단어 안으로 나눈다: %s' % (len(bare.split()), STE_EN, short)))
            cs = connectives(bare)
            if cs and re.search(r'(?:다|요|까|음|함|라|오|죠|자)[.!?]?\s*$', bare):
                out.append(('이어 쓴 문장', no, '`%s`로 두 생각을 이었다. 문장을 나눈다: %s' % (cs[0], short)))
            if '(행위자' not in x and (PASSIVE_DOE.search(bare) or PASSIVE_ETC.search(bare)) and not re.search(r'안 된다|하면 안|도 된다', bare):
                m = PASSIVE_DOE.search(bare) or PASSIVE_ETC.search(bare)
                out.append(('피동', no, '`%s` — 행위자를 주어로 쓴다. 원문에 없으면 `(행위자: 원문에 없음)`: %s' % (m.group(0).strip(), short)))
            m = DEIXIS.search(bare)
            if m and not (m.group(1) == '그' and re.search(r'그\s(?:다음|뒤|후|결과|대신|밖|자체)', bare)) and not re.search(r'해당 없음', bare):
                out.append(('지시어', no, '`%s` 대신 대상 이름을 다시 쓴다: %s' % (m.group(1), short)))
            if (ko and TAIL_COND.search(x)) or (not ko and TAIL_COND_EN.search(x)):
                out.append(('조건 위치', no, '조건이 문장 뒤에 있다. 앞으로 옮긴다: %s' % short))
            e = re.search(r'(습니다|니다|다)[.!?]?$', bare)
            if e:
                styles.setdefault('습니다' if e.group(1) != '다' else '다', no)
        if not numbered:
            para.setdefault(no, []).append(s)
    block, last = [], -9
    lines = sorted(para)
    for no in lines + [10 ** 9]:
        if no - last > 1 and block:
            joined = ' '.join(x for n in block for x in para[n])
            hits = [m.group(0).strip() for m in SEQ.finditer(joined)]
            if len(hits) >= 2:
                out.append(('번호', block[0], '순서 있는 단계(%s)를 번호 목록으로 쓴다' % ' · '.join(hits[:4])))
            block = []
        block.append(no)
        last = no
    if len(styles) > 1:
        out.append(('문체', max(styles.values()), '`~다`와 `~습니다`가 섞였다. 하나로 쓴다'))
    for used, origs in terms_of(md):
        for o in origs:
            if len(o) < 2 or o.lower() == used.lower() or o.lower() in used.lower():
                continue
            rx = re.compile((r'(?<![A-Za-z_])' + re.escape(o) + r'(?![A-Za-z_])') if re.match(r'^[\x00-\x7f]+$', o) else re.escape(o), re.I)
            for no, raw, _ in prose:
                s = re.sub(r'`[^`]*`|[“"][^”"\n]*[”"]|\([^)]*\)', ' ', raw)
                if rx.search(s.replace(used, ' ')):
                    out.append(('용어', no, '`%s`로 고정한 말의 원래 표기 `%s`가 산문에 남았다' % (used, o)))
                    break
    if re.search(r'STE\s*준수|STE-compliant', md):
        out.append(('이름', md.count('\n', 0, re.search(r'STE\s*준수|STE-compliant', md).start()) + 1, '`STE 준수`라고 부르지 않는다. `STE 방식`'))
    return sorted(set(out), key=lambda x: (x[1], x[0]))


# ---------- html ----------
EXTERNAL = [(re.compile(p, re.I), w) for p, w in (          # (어디서: 태그 · 스타일 · 실행 코드는 only()가 나눈다)
    (r'<(?:script|img|iframe|video|audio|source|embed|track|input)\b[^>]*\bsrc\s*=\s*["\']?\s*(?:https?:)?//', 'src에 외부 주소'),
    (r'<link\b[^>]*\bhref\s*=\s*["\']?\s*(?:https?:)?//', 'link에 외부 주소'),
    (r'url\(\s*["\']?\s*(?:https?:)?//', 'CSS url()에 외부 주소'), (r'@import\s+(?:url\()?["\']?\s*(?:https?:)?//', '@import에 외부 주소'),
    (r'\b(?:fetch|importScripts|import)\s*\(\s*["\'`](?:https?:)?//', 'fetch·import에 외부 주소'), (r'new\s+(?:WebSocket|EventSource)\s*\(|XMLHttpRequest|navigator\.sendBeacon', '네트워크 호출'),
    (r'<(?:object)\b[^>]*\bdata\s*=\s*["\']?\s*(?:https?:)?//', 'object에 외부 주소'), (r'<image\b[^>]*href\s*=\s*["\'](?:https?:)?//', 'SVG image에 외부 주소'))]


def html_text(s, data=True):
    """화면에 보일 글(태그 · 스타일 · 동작 코드 제외). data=True면 데이터 JSON의 글도."""
    strings = []
    for m in re.finditer(r'<script\b([^>]*)>(.*?)</script>', s, re.S | re.I):
        if data and 'application/json' in m.group(1):
            try:
                _strings(json.loads(m.group(2).replace('<\\/', '</')), strings)
            except ValueError:
                pass
        elif data:
            q = re.search(r'const (?:QUIZ|INTO) = (\{.*?\n\});', m.group(2), re.S)
            if q:
                try:
                    _strings(json.loads(q.group(1)), strings)
                except ValueError:
                    strings += re.findall(r'"((?:[^"\\]|\\.)*[가-힣](?:[^"\\]|\\.)*)"', q.group(1))
    t = re.sub(r'(?is)<(script|style|template|noscript)\b.*?</\1>', ' ', s)
    t = re.sub(r'(?s)<!--.*?-->', ' ', t)
    t = re.sub(r'(?i)<(?:p|li|h[1-6]|tr|div|section|article|header|footer|text|summary|figcaption|br|dt|dd|td|th)\b[^>]*>', '\n', t)
    t = H.unescape(re.sub(r'<[^>]+>', '', t))
    return re.sub(r'[ \t]+', ' ', re.sub(r'\n\s*\n+', '\n', t)).strip(), strings


def _strings(v, out, key=''):
    if isinstance(v, str):
        if key not in ('id', 'ids', 'from', 'to', 'src', 'source', 'when', 'kind', 'type', 'mode', 'layout', 'order', 'mark', 'notice', 'missing', 'typeName') and v.strip():
            out.append(v)
    elif isinstance(v, list):
        for x in v:
            _strings(x, out, key)
    elif isinstance(v, dict):
        for k, x in v.items():
            _strings(x, out, k)


SCRIPT = re.compile(r'(<script\b[^>]*>)(.*?)(</script>)', re.S | re.I)


def blank(s):
    return re.sub(r'[^\n]', ' ', s)


def only(s):
    """실행되는 곳만 남긴 글(나머지는 같은 길이의 빈칸): 태그 · 스타일 · 실행 코드. 화면 데이터(JSON · QUIZ · INTO)와 보이는 글은 데이터다."""
    def script(m):
        code = blank(m.group(2)) if 'json' in m.group(1).lower() else re.sub(r'const (?:QUIZ|INTO) = \{.*?\n\};', lambda q: blank(q.group(0)), m.group(2), flags=re.S)
        return m.group(1) + code + m.group(3)
    s = re.sub(r'(?s)<!--.*?-->', lambda m: blank(m.group(0)), SCRIPT.sub(script, s))
    tag = lambda m: m.group(1) or (re.sub(r'(\s(?!src|href|data=|style|on|xlink)[\w:\-]+\s*=\s*)("[^"]*"|\'[^\']*\')', lambda q: q.group(1) + blank(q.group(2)), m.group(2)) if m.group(2) else blank(m.group(0)))
    return re.sub(r'(?is)(<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>)|(<[^>]*>)|[^<]+', tag, s)


def safety(s, is_html):
    """외부 요청 · 홈 경로 · 남은 {{ · 비밀 값 → [(수준, 줄, 문구)]"""
    out = []

    def line(pos):
        return s.count('\n', 0, pos) + 1
    if is_html:
        run = only(s)
        for rx, w in EXTERNAL:
            for m in list(rx.finditer(run))[:3]:
                out.append(('FAIL', line(m.start()), '%s가 있다. 파일 하나로 닫는다: %s' % (w, T.clip(m.group(0), 50))))
    for m in list(T.HOME.finditer(s))[:3]:
        out.append(('FAIL', line(m.start()), '홈 폴더 경로가 있다. 상대 경로로 바꾼다'))
    body = re.sub(r'`[^`\n]*`', lambda m: ' ' * len(m.group(0)), s) if not is_html else s
    for m in list(re.finditer(r'\{\{', body))[:3]:
        out.append(('FAIL', line(m.start()), '채우지 않은 `{{`가 남았다: %s' % T.clip(s[m.start():m.start() + 40], 40)))
    for lv, v, n in T.secrets(s)[:5]:
        out.append(('FAIL' if lv == '확실' else 'WARN', n, '비밀 값%s(%s)이 있다. `***`로 바꾼다' % ('' if lv == '확실' else ' 후보', v)))
    return out


def shown(d):
    """화면 데이터(#into)에서 보이는 글. render가 세는 것과 같다(근거 · 출처 · 칸 이름은 뺀다)."""
    from . import htmlmodes as X

    def g(xs, *ks):
        return [str(x[k]) for x in M.as_list(xs) if isinstance(x, dict) for k in ks if x.get(k) not in (None, '')]

    def items(xs):
        return [s for x in M.as_list(xs) if isinstance(x, dict) for s in g([x], 'code' if x.get('code') else 't')]
    out = g([d], 'title', 'one') + g(d.get('predicts'), 'q', 'answer')
    for k in ('why', 'lead', 'learn'):
        out += items(d.get(k))
    for c in M.as_list(d.get('cards')):
        out += items(c.get('items'))
    for t in M.as_list(d.get('tables')):
        out += [str(x) for r in M.as_list(t.get('rows')) for x in M.as_list(r.get('cells'))]
    for f in M.as_list(d.get('figs')):
        out += g(f.get('cases'), 'input', 'before', 'after') + g(f.get('flips'), 'if', 'then') + g(f.get('triggers'), 'say', 'route') + g(f.get('whatif'), 'if', 'then')
        out += items(f.get('items')) if f.get('part') == 'list' else g(f.get('items'), 'if', 'then') if f.get('part') == 'toggle' else X._shown(f) if f.get('part') in PIC_FORMS else X._strings({k: v for k, v in f.items() if k not in ('part', 'key', 'aria', 'title')})
    return out


# ---------- 결과 검사 ----------
def labels_in(text, rows):
    """칸 이름이 나온 위치 [(행, 위치)]"""
    out = []
    for r in rows:
        m = re.search(r'(?m)^\s*(?:#{1,6}\s*(?:\d+\.\s*)?)?(?:\*\*)?%s(?:\*\*)?(?=\s|$|[:：|·—])' % re.escape(r['label']), text) or re.search(r'\*\*%s\*\*' % re.escape(r['label']), text)
        if m:
            out.append((r, m.start()))
    return out


def result(path, type_, mode, source=None, size=None):
    s = open(path, encoding='utf-8', errors='replace').read()
    is_html = path.lower().endswith(('.html', '.htm'))
    import os
    base = os.path.basename(path)
    out = []

    def add(level, line, msg):
        out.append(Issue(level, '%s:%d' % (base, line), msg))
    for lv, n, m in safety(s, is_html):
        add(lv, n, m)
    if is_html:
        plain, strings = html_text(s)
        text = plain + '\n' + '\n'.join(strings)
        seen = re.sub(r'(?m)^\s*(?:근거|출처|빠진 디테일)\s*[:：].*$', '', plain)
        n = T.count(seen)
        if mode == 'interactive' or (mode == 'html' and 'application/json' in s):      # 글이 데이터에 있는 화면
            n = T.count(seen + ' ' + ' '.join(strings))
        d = re.search(r'<script type="application/json" id="into">(.*?)</script>', s, re.S)
        if d and mode in ('html', 'interactive'):
            try:
                n = sum(T.count(x) for x in shown(json.loads(d.group(1).replace('<\\/', '</'))))
            except ValueError:
                add('FAIL', 1, '#into 데이터가 JSON이 아니다')
    else:
        text, n = s, T.count_result(s)
    if mode in ('shorts', 'video') and not is_html:
        storyboard(s, mode, add)
    elif mode:
        try:
            lim = formats.length_limit(type_ or 'general', mode, size or '큼')
        except Exception:
            lim = None
        if lim and n > lim:
            add(T.over(n, lim) if size else 'WARN', 1, '보이는 글자 %s자다. %s 원문의 한도는 %s자다' % ('{:,}'.format(n), size or '가장 큰', '{:,}'.format(lim)))
    if mode in TEXT_MODES or mode in ('shorts', 'video'):
        for lb in ('빠진 디테일', '출처'):
            if not re.search(r'(?m)^\W*(?:#+\s*)?(?:\*\*)?%s' % lb, s):
                add('FAIL', 1, '`%s:` 줄이 없다' % lb)
    if type_ and mode in TEXT_MODES and formats.exists(type_):
        rows, _ = formats.mode_rows(type_, mode)
        if mode == 'doc':
            pos = [(sl, re.search(r'(?m)^##\s+(?:\d+\.\s*)?%s\s*$' % re.escape(DOC_TITLES[sl]), s)) for sl in SLOTS]
            gone = re.search(r'(?m)^\W*빠진 디테일.*(?:\n.*)*', s)
            gone = gone.group(0) if gone else ''
            for sl, m in pos:
                if m is None and not any(lb in gone for lb in [DOC_TITLES[sl]] + [r['label'] for r in rows if r['slot'] == sl]):
                    add('FAIL', 1, '제목 `## %s`가 없다' % DOC_TITLES[sl])
            at = [m.start() for _, m in pos if m]
            if at != sorted(at):
                add('FAIL', 1, '다섯 제목의 순서가 다르다: %s' % ' → '.join(DOC_TITLES[sl] for sl in SLOTS))
        else:
            got = sorted(labels_in(s, [r for r in rows if r['slot'] != 'one']), key=lambda x: x[1])
            order = [SLOTS.index(r['slot']) for r, _ in got]
            if order != sorted(order):
                add('FAIL', s.count('\n', 0, got[0][1]) + 1, '칸 순서가 다르다: %s' % ' → '.join(r['label'] for r, _ in got))
            have = {r['key'] for r, _ in got}
            for r in rows:
                if r['required'] and r['slot'] not in ('one', 'pic') and r['key'] not in have:
                    add('FAIL', 1, '필수 칸 `%s`이 없다' % r['label'])
                elif not r['required'] and not r['optional'] and r['slot'] not in ('one', 'pic') and r['key'] not in have and r['label'] not in s and r['form'] not in ('table',):
                    add('WARN', 1, '칸 `%s`이 없고 `빠진 디테일`에도 이름이 없다' % r['label'])
    # 문장
    lines = [(i, ln) for i, ln in enumerate(text.split('\n'), 1)]
    sents = [(i, x) for i, ln in lines if not T.META.match(ln) and not re.match(r'^\s*(?:\||```)', ln) for x in T.sentences(T.LABEL.sub('', ln)) if T.count(x) >= 12]
    for a in range(0 if is_html and strings else min(len(sents), 400)):      # 데이터 화면의 되풀이는 칸 검사가 본다
        for b in range(a + 1, min(len(sents), 400)):
            if sents[a][1] != sents[b][1] and T.similar(sents[a][1], sents[b][1]) >= 0.85 or (sents[a][1] == sents[b][1] and not is_html):
                add('WARN', sents[b][0], '%d줄과 같은 말이다: %s' % (sents[a][0], T.clip(sents[b][1], 40)))
                break
    whole = source.text() if source is not None and source.kind in ('file', 'pr') else ''
    for name, rx, ok in T.ABSOLUTE:
        hit = [(i, x) for i, x in sents if rx.search(x)]
        if hit and not (whole and ok.search(whole)):
            add('WARN', hit[0][0], '`%s`을 %d번 썼다. 원문에 같은 말이 있는지 본다: %s' % (name, len(hit), T.clip(hit[0][1], 40)))
    if source is not None:
        later = {}
        body = T.body_of(s) if not is_html else text
        for i, ln in enumerate(body.split('\n'), 1):
            if T.META.match(ln):
                continue
            M.check_numbers(re.sub(r'\b\d{1,3}/\d{1,3}\b', ' ', ln), lambda f, counted=False: source.number_ok(f, (), counted), 'L%d' % i, lambda lv, w, m: add('WARN' if source.kind == 'dir' else lv, _find(s, ln), m)) if source.kind != 'dir' else None
            M.check_idents(ln, source, (), (), 'L%d' % i, lambda lv, w, m: add(lv, _find(s, ln), m), later)
        M.flush_idents(source, later, lambda lv, w, m: add(lv, 1, m))
        _cites(s, source, add)
        if whole:
            _variants(sents, whole, add)
    if mode == 'ste' and not is_html:
        for rule, no, m in ste(s):
            add('WARN', no, '[%s] %s' % (rule, m))
    return out, n


def _find(s, ln):
    p = s.find(ln.strip()[:60])
    return s.count('\n', 0, p) + 1 if p >= 0 else 1


CITE = re.compile(r'(?<![A-Za-z0-9_/@.\-])((?:[A-Za-z0-9_.\-@\[\]]+/)*[A-Za-z0-9_.\-@]+\.(?:rs|go|py|rb|java|kt|swift|c|cc|cpp|h|hpp|cs|php|tsx?|jsx?|mjs|cjs|sql|sh|md|toml|ya?ml|json|css|html|proto)):(-?\d+(?:\s*[-–~]\s*\d+)?(?:\s*,\s*:?-?\d+(?:\s*[-–~]\s*\d+)?)*)(?![A-Za-z0-9_/])')


def _cites(s, source, add):
    for m in CITE.finditer(s):
        r = source.resolve(m.group(0))
        if not r['ok'] and not (source.kind == 'file'):
            add('FAIL', s.count('\n', 0, m.start()) + 1, r['msg'])
    for m in re.finditer(r'(?<![\w/])raw:(\d+(?:[-–]\d+)?)', s):
        r = source.resolve(m.group(0))
        if not r['ok'] and source.kind in ('file', 'pr'):
            add('FAIL', s.count('\n', 0, m.start()) + 1, r['msg'])


def _variants(sents, whole, add):
    """금지 변형 후보: 결과 문장과 낱말이 겹치는 원문 줄에 한정어가 있는데 결과에는 없다."""
    src = [(i, ln, S_toks(ln)) for i, ln in enumerate(whole.split('\n'), 1) if set(T.cond_kinds(ln)) & {'may', 'should', 'default', 'bound'}]
    n = 0
    for i, x in sents:
        tx = S_toks(x)
        if len(tx) < 2:
            continue
        for k, ln, tl in src:
            if len(tx & tl) >= 3:
                miss = [c for c in T.cond_kinds(ln) if c in ('may', 'should', 'default', 'bound') and c in T.HEDGE_KEEP and not T.HEDGE_KEEP[c].search(x)]
                if miss:
                    add('WARN', i, '원문 %d줄의 한정어(%s)가 빠졌나 본다: %s' % (k, '·'.join(M.KIND_HINT[c] for c in miss), T.clip(x, 40)))
                    n += 1
                    break
        if n >= 8:
            break


def S_toks(s):
    return {w.lower() for w in re.findall(r'[A-Za-z_][A-Za-z0-9_]{3,}|\d{2,}|[가-힣]{3,}', s)}


def storyboard(s, mode, add):
    """대본 표에서 장면 시간 · 음절을 다시 센다."""
    head, total, rows = None, 0.0, 0
    for i, ln in enumerate(s.split('\n'), 1):
        if not ln.lstrip().startswith('|'):
            head = None
            continue
        c = T.split_row(ln)
        if head is None:
            head = c if any('시간' in x or x == '초' for x in c) and any('나레이션' in x or '말' in x for x in c) else []
            continue
        if not head or set(''.join(c)) <= set('-: ') or len(c) != len(head):
            if head and len(c) != len(head) and not set(''.join(c)) <= set('-: '):
                add('FAIL', i, '표의 칸이 %d개다(열 %d개). 칸 안에 세로줄을 쓰지 않는다' % (len(c), len(head)))
            continue
        row = dict(zip(head, c))
        rows += 1
        tm = next(v for k, v in row.items() if '시간' in k or k == '초')
        say = next(v for k, v in row.items() if '나레이션' in k or '말' in k)
        nums = [_sec(x) for x in re.findall(r'\d+:\d{2}(?:\.\d+)?|\d+(?:\.\d+)?', tm)]
        if not nums:
            continue
        sec = nums[1] - nums[0] if len(nums) > 1 else nums[0]
        total = max(total, nums[1]) if len(nums) > 1 else total + sec
        n, p, need, est = S.scene_seconds(say, True)
        rate = n / max(0.1, sec - p)
        if rate > S.PER_SEC + 0.05:
            add('WARN' if est else 'FAIL', i, '초당 %.1f음절이다(%d음절, 쉼 %.1f초, 장면 %.1f초). %.1f초 이상으로 늘리거나 사실을 뺀다' % (rate, n, p, sec, need))
        for k, v in row.items():
            if '나레이션' not in k and '근거' not in k and S.OUTSIDE.search(v):
                add('FAIL', i, '`%s` 칸이 다른 모드나 대본 밖을 가리킨다: %s' % (k, S.OUTSIDE.search(v).group(0)))
            if mode == 'shorts' and '자막' in k and T.count(v) > S.CAP_CHARS:
                add('WARN', i, '자막 %d자 — 안전 영역 2줄(%d자)을 넘을 수 있다' % (T.count(v), S.CAP_CHARS))
    if not rows:
        add('FAIL', 1, '스토리보드 표(시간 · 나레이션 열)가 없다')
    elif mode == 'shorts' and total > S.MAX_SHORTS + 0.05:
        add('FAIL', 1, '총 %.1f초다. 60초까지다' % total)


def _sec(x):
    if ':' in x:
        m, s = x.split(':')
        return int(m) * 60 + float(s)
    return float(x)

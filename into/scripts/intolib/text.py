# -*- coding: utf-8 -*-
"""글자 세기 · 숫자 · 조건어 · 비밀 값 · 문장 나누기."""
import ast
import re

# ---------- 보이는 글자 ----------
META = re.compile(r'^\s*(?:[-*>]\s+)?(?:\*\*)?(근거|출처|빠진 디테일|순서|유형|용어|검사|경로 기준|그림에서 뺀 간선)(?: · 불확실)?(?:\*\*)?\s*[:：]')
NOTICE_LINE = re.compile(r'^\s*(?:>\s*)?비공개 원문 기반')
LABEL = re.compile(r'^\s*\*\*[^*\n]{1,40}\*\*\s*')
HEAD = re.compile(r'^\*\*[^*\n]+? · ([^*\n]+)\*\*\s+—\s+')          # 머리 줄: 유형 이름은 안 세고 제목·범위는 센다
ORDER_NOTE = re.compile(r'\(순서: [^()\n]*\)')
ARROW = re.compile(r'─\((.*?)\)▶')
FENCE = re.compile(r'^\s*(```|~~~)')


def visible(s):
    """사람 눈에 보이는 글자만 남긴다 (마크다운 기호 · 링크 주소 · 그림 선은 뺀다)."""
    s = str(s or '')
    s = re.sub(r'<!--.*?-->', '', s, flags=re.S)
    s = re.sub(r'!?\[([^\]\n]*)\]\([^)\n]*\)', r'\1', s)
    s = re.sub(r'(?m)^\s*\|?[\s:|-]*-{3,}[\s:|-]*\|?\s*$', '', s)     # 표 구분 줄 · 가로선
    s = re.sub(r'(?m)^\s*(?:#{1,6}\s+|>\s?|[-*]\s+)', '', s)
    s = s.replace('**', '').replace('`', '').replace('|', ' ')
    s = re.sub(r'[─━▶◀▸→←│┃┌┐└┘├┤┬┴┼]', '', s)
    return re.sub(r'\s+', ' ', s).strip()


def count(s):
    return len(visible(s))


def body_of(md):
    """결과 글에서 세는 줄만 남긴다. 절 제목 · 칸 이름 · 근거 · 출처 · 빠진 디테일 · Mermaid는 세지 않는다. 머리 줄의 제목·범위는 센다."""
    out, skip_list, fence = [], False, None
    md = re.sub(r'(?s)<!--.*?-->', '', re.sub(r'(?s)\A---\n.*?\n---\n', '', md))
    for ln in md.split('\n'):
        m = FENCE.match(ln)
        if m:
            fence = None if fence else (ln.strip().strip('`~').strip().lower() or 'text')
            continue
        if fence:
            if fence != 'mermaid':
                out.append(ln)
            continue
        if META.match(ln) or NOTICE_LINE.match(ln):
            skip_list = True
            continue
        if skip_list and re.match(r'^\s*(?:[-*]\s|$)', ln):
            if not ln.strip():
                skip_list = False
            continue
        skip_list = False
        if re.match(r'^\s*#{1,6}\s', ln):
            if re.search(r'빠진 디테일|출처', ln):
                skip_list = True
            continue
        head = HEAD.match(ln)
        out += [head.group(1), ln[head.end():]] if head else [ORDER_NOTE.sub('', LABEL.sub('', ln))]
    return '\n'.join(out)


def count_result(md):
    """보이는 글자(줄마다 센다). 칸마다 센 수의 합과 같다."""
    return count_lines(body_of(md).split('\n'), set())


def count_lines(lines, seen):
    """줄마다 센 합. 화살표 그림에서 되풀이되는 노드 이름은 한 번만 센다(seen = 앞에서 센 이름)."""
    n = 0
    for ln in lines:
        n += count(ln)
        parts = ARROW.split(ln)
        for name in parts[::2] if len(parts) > 1 else []:
            name = visible(re.split(r'\s{2,}', name.strip())[-1])
            n -= len(name) if name in seen else 0
            seen.add(name)
    return n


def over(n, lim):
    """한도를 넘은 정도: '' | 'WARN'(105%까지) | 'FAIL'"""
    return '' if not lim or n <= lim else 'WARN' if n * 100 <= lim * 105 else 'FAIL'


# ---------- 문장 ----------
def sentences(s):
    s = re.sub(r'`[^`\n]*`', lambda m: m.group(0).replace('.', '\x00').replace('?', '\x01').replace('!', '\x02'), s)
    parts = re.split(r'(?<=[.!?。])["\')\]”’]*\s+|\n+|\s+[·•]\s+', s)
    return [p.replace('\x00', '.').replace('\x01', '?').replace('\x02', '!').strip() for p in parts if p and p.strip()]


def stems(s):
    """견줄 핵심 낱말: 조사·어미를 뗀 한글 앞 두 글자 · 영문 · 숫자"""
    s = re.sub(r'(?:이면|하면|되면|으면|때만?|경우에?|에서만?|에는|으로|에서|이고|하고)(?=\s|$|[,.)])', '', str(s))
    return [w[:2] if re.match('[가-힣]', w) else w.lower() for w in re.findall(r'[가-힣]{2,}|[A-Za-z_]{3,}|\d+', s) if len(w) > 1]


def grams(s, n=3):
    s = re.sub(r'[\s\W_]+', '', visible(s)).lower()
    return {s[i:i + n] for i in range(max(0, len(s) - n + 1))}


def similar(a, b):
    """두 문장의 겹침(0~1). 짧은 쪽이 긴 쪽에 거의 들어 있으면 1에 가깝다."""
    x, y = grams(a), grams(b)
    if min(len(x), len(y)) < 8:
        return 0.0
    return len(x & y) / float(min(len(x), len(y)))


# ---------- 숫자 ----------
NUM = re.compile(r'(?<![A-Za-z_\d.])(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)*)(?:\s?(퍼센트|percent|%|천|만|억|조|million|billion|thousand|[kKMB](?![A-Za-z])))?', re.I)
MULT = {'천': 1e3, 'k': 1e3, 'thousand': 1e3, '만': 1e4, 'm': 1e6, 'million': 1e6, '억': 1e8, 'b': 1e9, 'billion': 1e9, '조': 1e12}
WORDS = {'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
         'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14, 'fifteen': 15, 'sixteen': 16, 'seventeen': 17, 'eighteen': 18, 'nineteen': 19,
         'twenty': 20, 'thirty': 30, 'forty': 40, 'fifty': 50, 'sixty': 60, 'seventy': 70, 'eighty': 80, 'ninety': 90, 'hundred': 100,
         'once': 1, 'twice': 2, 'first': 1, 'second': 2, 'third': 3, 'half': 0.5}
MONTH = re.compile(r'\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May(?=\.? \d)|(?<=\d )May|June?|July?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\b')
MONTHS = 'jan feb mar apr may jun jul aug sep oct nov dec'.split()
KWORDS = {'하나': 1, '한': 1, '둘': 2, '두': 2, '셋': 3, '세': 3, '넷': 4, '네': 4, '다섯': 5, '여섯': 6, '일곱': 7, '여덟': 8, '아홉': 9, '열': 10, '첫': 1}
KCOUNT = r'(?:\s?(?:개|가지|번|명|곳|단계|줄|칸|장|편|시간|달|배|차례|축|방법|종류|사람|군데|쪽|번째|째))'


def canon(n):
    n = n.replace(',', '')
    if n.count('.') > 1:
        return n
    if '.' in n:
        n = n.rstrip('0').rstrip('.')
    return n.lstrip('0') or '0' if not n.startswith('0.') else n


def _fmt(v):
    return canon(('%.6f' % v)) if v < 1e15 else str(int(v))


def number_forms(m):
    n, unit = m.group(1), (m.group(2) or '').lower()
    c = canon(n)
    forms = {c}
    if unit in MULT and c.count('.') <= 1:
        forms.add(_fmt(float(c) * MULT[unit]))
    return forms


# 숫자로 보지 않는 것: 시각 · n/N · 글자에 붙은 숫자(L89-92, v11) · 순번(예 3, 표 2)
NOT_NUM = re.compile(r'\[?\b\d{1,2}:\d{2}(?::\d{2})?\]?|(?<![\w.])\d+/\d+(?![A-Za-z\d]|\.\d)|(?<![A-Za-z0-9_])[A-Za-z_]+[\-_]?\d[\w.]*(?:[\-–~]\d+)*'
                     r'|(?<![가-힣])(?:예|표|그림|댓글|질문|문항|단계|글|안|절|부록|사례|의견|[Ff]ig(?:ure)?\.?|[Tt]able|[Ss]tep|[Ee]xample)\s?\d{1,3}(?:[\-–~·]\d{1,3})*(?![\d%]|[.,]\d|\s?(?:개|명|건|배|번(?!째)|가지|곳|회|자|줄|장|쪽|초|분|시간|일|년|월|원|만|천|억|퍼센트))')
UNDER = re.compile(r'(?<=\d)_(?=\d{3}(?!\d))')          # 10_000


def numbers(s, keep_code=False):
    """[(보이는 값, 정규형 집합, 위치)] — 백틱 안 · 시각(mm:ss) · n/N은 뺀다."""
    s = _bare(s, keep_code)
    return [(m.group(0).strip(), number_forms(m), m.start()) for m in NUM.finditer(s)]


def _bare(s, keep_code):
    if not keep_code:
        s = re.sub(r'`[^`\n]*`', lambda m: ' ' * len(m.group(0)), s)
    return NOT_NUM.sub(lambda m: ' ' * len(m.group(0)), UNDER.sub('', s))


UNITS = [(k, re.compile(r'\s?-?(?:%s)' % v.replace(r'\b', '(?![A-Za-z0-9_])'))) for k, v in (          # MB까지 · ms다: 뒤에 조사가 붙는다
    ('밀리초', r'ms\b|밀리초|milliseconds?\b'), ('초', r's\b|secs?\b|seconds?\b|초(?!기|안|과|보|록)'), ('분', r'mins?\b|minutes?\b|분(?!의|석|류|기|할|야|포)'), ('시간', r'h\b|hrs?\b|hours?\b|시간'),
    ('일', r'days?\b|일(?!부|반|치|괄|관)'), ('주', r'weeks?\b|주(?!요|로|의|기|소|석|제|체)'), ('달', r'months?\b|달(?!러)|개월'), ('년', r'years?\b|년'), ('%', r'%|％|퍼센트|percent\b'), ('배', r'배(?!포|치|경|열|우)|times\b|x\b'),
    ('KB', r'Ki?B\b'), ('MB', r'Mi?B\b'), ('GB', r'Gi?B\b'), ('원', r'원(?!문|본|래|칙|소|인|격)'), ('달러', r'달러|dollars?\b'))]


SCALE = {'밀리초': ('시간', (1,)), '초': ('시간', (1000,)), '분': ('시간', (60000,)), '시간': ('시간', (3600000,)), '일': ('시간', (86400000,)), '주': ('시간', (604800000,)),
         'KB': ('크기', (1000, 1024)), 'MB': ('크기', (10 ** 6, 2 ** 20)), 'GB': ('크기', (10 ** 9, 2 ** 30))}          # 같은 차원의 단위끼리만 환산한다
COUNTED = re.compile(r'\s?(?:명|개(?!월|년)|건|회|곳|번|줄|(?:people|persons?|users?|items?|files?|lines?|tokens?|requests?|connections?)\b)', re.I)          # 센 것(1,800명): 다른 단위가 아니다
DATE = r'\d{4}\s?[-./년]\s?\d{1,2}|' + MONTH.pattern
SAID = {k: re.compile(v, 0 if k == '밀리초' else re.I) for k, v in (          # 값에 붙지 않았어도 단위를 말하는 글(LIMIT_SECONDS = 30 · 표 머리의 (%))
    ('밀리초', r'(?<![A-Za-z])(?:ms|MS)(?![a-z])|[a-z]Ms(?![a-z])|[Mm]illi|밀리초'), ('초', r'sec(?:ond)?s?(?![a-z])|초(?!기|안|과|보|록)'), ('분', r'min(?:ute)?s?(?![a-z])|분(?!의|석|류|기|할|야|포)'), ('시간', r'h(?:ou)?rs?(?![a-z])|hours?|시간'),
    ('일', r'days?(?![a-z])|\d\s?일|' + DATE), ('주', r'weeks?|주간|주마다|주일'), ('달', r'months?|달|월|' + DATE), ('년', r'years?|년|' + DATE + r'|(?<!\d)(?:19|20)\d\d(?!\d)'),
    ('%', r'%|％|퍼센트|percent|pct|비율|율(?![가-힣])|률(?![가-힣])|\brates?\b|ratio'), ('배', r'배(?!포|치|경|열|우)|times\b|fold\b|\dx\b|×'), ('KB', r'ki?b|bytes?'), ('MB', r'mi?b|bytes?'), ('GB', r'gi?b|bytes?'),
    ('원', r'원(?!문|본|래|칙|소|인|격)|krw|₩'), ('달러', r'달러|dollars?|usd|\$'))}


def measures(s, keep_code=False):
    """[(보이는 값, 정규형 집합, 단위 | '', 부호 | '', 센 것인가)]. keep_code(근거)면 단위 없는 비율(.45)은 45%로도 센다."""
    s, out = _bare(s, keep_code), []
    for m in list(NUM.finditer(s)) + [m for m in RATIO.finditer(s) if keep_code]:
        a, b, rate = m.start(1), m.end(1), m.re is RATIO
        unit = '%' if not rate and (m.group(2) or '') in ('%', '퍼센트', 'percent') else next((k for k, r in UNITS if r.match(s, m.end())), '')
        a = m.start() if rate else a
        sign = s[a - 1] if a and s[a - 1] in '+-−–' and not re.match(r'[\w%)\]]', s[a - 2:a - 1] or ' ') else ''
        sign = '-' if sign and sign != '+' else sign
        if not rate:
            out.append((s[a:b] + unit, number_forms(m), unit, sign, bool(not unit and COUNTED.match(s, m.end()))))
        elif not unit:
            out.append((s[a:b], ratio(m), '%', sign, False))
    return out


def converted(forms, unit, have):
    """단위만 다른 같은 값(30분 = 1,800초)인 근거들. 단위가 붙은 값끼리, 같은 차원에서만 본다. have = measures(근거)"""
    dim, ks = SCALE.get(unit, ('', ()))
    pairs = [(f, g, h) for h in have if dim and h[2] != unit and SCALE.get(h[2], ('',))[0] == dim for f in forms for g in h[1] if f.count('.') < 2 and g.count('.') < 2]
    return [h for f, g, h in pairs if any(_fmt(float(f) * a) == _fmt(float(g) * b) for a in ks for b in SCALE[h[2]][1])]


def number_set(s, ratios=True):
    s, out = UNDER.sub('', s), set()
    for m in NUM.finditer(s):
        out |= number_forms(m)
    return out | number_words(s, ratios)


RATIO = re.compile(r'(?<![\w.])0?\.(\d{2,4})(?!\d|\.\d)')          # .10 · 0.45 → 10% · 45%


def ratio(m):
    v = float('0.' + m.group(1))
    return {_fmt(v), _fmt(v * 100)}


def number_words(s, ratios=True):
    """낱말로 쓴 수(five · 세 개 · Sep)와 .10 같은 비율"""
    out = set()
    for m in RATIO.finditer(s if ratios else ''):
        out |= ratio(m)
    for m in MONTH.finditer(s):
        out.add(str(MONTHS.index(m.group(1)[:3].lower()) + 1))
    low = s.lower()
    for w in set(re.findall(r'[a-z]+', low)):
        if w in WORDS:
            out.add(_fmt(WORDS[w]))
    for w, v in KWORDS.items():
        if re.search(r'(?<![가-힣])' + w + KCOUNT, s) or (len(w) > 1 and w in s):
            out.add(str(v))
    return out


def says_number(s, forms):
    """이 줄에 그 값이 있나. 이름에 붙은 숫자(`핵심개념5가지`)는 값으로 보지 않는다."""
    b = _bare(s, True)
    return any(forms & number_forms(m) and not re.match('[가-힣]', b[max(0, m.start() - 1):m.start()]) for m in NUM.finditer(b)) or bool(forms & number_words(s))


CALC = re.compile(r'\(계산\s*[:：]\s*([^)]*(?:\([^)]*\)[^)]*)*)\)')


def calc_value(expr):
    """'(889+497)' 같은 식의 값. 읽지 못하면 None."""
    e = re.split(r'\s*[=≈]\s*', expr)[0]
    e = e.replace('×', '*').replace('÷', '/').replace('−', '-').replace('–', '-').replace(',', '').replace('^', '**')
    e = re.sub(r'(\d)\s*%', r'\1', e)
    e = re.sub(r'[^\d.+\-*/() ]', '', e).strip()
    try:
        tree = ast.parse(e, mode='eval')
    except (SyntaxError, ValueError):
        return None

    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return float(n.value)
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.USub, ast.UAdd)):
            return -ev(n.operand) if isinstance(n.op, ast.USub) else ev(n.operand)
        if isinstance(n, ast.BinOp):
            a, b = ev(n.left), ev(n.right)
            if isinstance(n.op, ast.Add):
                return a + b
            if isinstance(n.op, ast.Sub):
                return a - b
            if isinstance(n.op, ast.Mult):
                return a * b
            if isinstance(n.op, ast.Div):
                return a / b
        raise ValueError
    try:
        return ev(tree)
    except (ValueError, ZeroDivisionError, OverflowError):
        return None


# ---------- 조건어 · 한정어 ----------
COND = [
    ('only', r'(?<![\w\-])only\b|뿐(?=[\s,.)이])|(?:때|경우|경우에|한해서)만(?=[\s,.)]|$)|한해(?=[\s,.)]|$)'),
    ('if', r'\bif\b|\bwhen\b|\bonce\b|\bas long as\b|\bprovided\b|(?:[가-힣](?<!화)(?<!장)(?<!측)(?<!반)(?<!정)(?<!표)(?<!전)(?<!후)(?<!지)(?<!도)면(?=[\s,.)]|$))|경우|조건'),
    ('unless', r'\bunless\b|\bexcept\b|\bother than\b|제외|예외|아니면|않으면|빼고'),
    ('default', r'\bdefaults?\b|기본(?!기|적|법|편)'),
    ('may', r'\bmay\b|\bmight\b|\bcan\b|\bcould\b|\bprobably\b|\blikely\b|\bpossibly\b|수 있|가능|일지도|아마|추정|보인다'),
    ('should', r'\bshould\b|\brecommend|권고|권장|좋다'),
    ('must', r'\bmust\b|\brequired?\b|반드시|필수|해야'),
    ('bound', r'\bat least\b|\bat most\b|\bup to\b|\bmore than\b|\bover \d|\bno more than\b|\bmaximum\b|\bminimum\b|최대|최소|이상|이하|초과|미만|\d\s?[가-힣A-Za-z%]{0,4}까지'),
    ('about', r'\babout (?=\d|half|an? (?:third|quarter|dozen|hundred)|(?:one|two|three|four|five|ten|twenty)\b)|\bapproximately\b|\broughly\b|\baround \d|약 \d|대략|정도|쯤'),
    ('time', r'\binitially\b|\bimmediately?\b|\bfor now\b|\bcurrently\b|처음에는|당장|아직|현재|지금은'),
]
COND_RE = [(k, re.compile(v, re.I)) for k, v in COND]
STRONG = {'only', 'unless', 'default', 'bound', 'must', 'if'}
# 조건어처럼 보이지만 조건이 아닌 말
NOT_COND = re.compile(r'\b[A-Za-z]+-only\b|\bonly once\b|\b(?:is|are|was|were) (?:little|not) known\b|\b(?:even|as) (?:if|when|though)\b|\b(?:it(?: is|\'s)|is|are) up to\b(?! \d)|\bup[ -]to[ -]date\b|\bat once\b|\bif (?:any|not all)\b'
                      r'|\bcan(?:not)? (?:distinguish|tell|see|read|understand|recogni[sz]e|identify|express|represent|handle|be (?:seen|found|viewed|expressed|written|read|thought))\b|\bwhen it comes to\b|\bwhen \w+ing\b|(?:인지|,|인지,) 아니면', re.I)


def cond_kinds(line):
    line = NOT_COND.sub(' ', line)
    return [k for k, r in COND_RE if r.search(line)]


def josa(w, a='이', b='가'):
    """마지막 글자를 읽는 소리에 맞는 조사: 503 → 이, 40% → 가."""
    m = re.findall(r'[가-힣A-Za-z0-9%]', str(w))
    c = m[-1] if m else ''
    if '가' <= c <= '힣':
        return a if (ord(c) - 0xAC00) % 28 else b
    return a if c and c in '013678lmnLMN' else b


def fix_josa(msg):
    """알림 앞부분의 `이름`·"글" 뒤 조사를 맞춘다."""
    head, sep, rest = msg.partition(': ')
    pair = {'이': ('이', '가'), '가': ('이', '가'), '을': ('을', '를'), '를': ('을', '를'), '은': ('은', '는'), '는': ('은', '는')}
    return re.sub(r'((?:`[^`]+`|"[^"]+"))(이|가|을|를|은|는)(?=\s)', lambda m: m.group(1) + josa(m.group(1), *pair[m.group(2)]), head) + sep + rest


# 원문의 한정어 → 결과에 남아 있어야 하는 말
MUST = r'(?:아|어|여|해|써|둬|줘|내|돼|와|봐|켜|려|겨|져|춰|꿔|워|러|셔|쳐|라)야|말 것|말아'          # …해야 · 받아야 · 쉬워야
HEDGE_KEEP = {
    'may': re.compile(r'수 있|수도|가능|may|might|can\b|could|probabl|likely|possib|도 된|아마|추정|보인다|듯|경향|것 같|예정|허용|일지|확실하지 않|불확실|모른다|모름|못 찾|찾지 못|확인하지 못|엇갈|때로|가끔|종종', re.I),
    'should': re.compile(r'should|권고|권장|권한|좋다|좋겠|하라|recommend|바람직|추천|' + MUST, re.I),
    'must': re.compile(r'must|shall|requir|반드시|꼭|필수|의무|금지|무조건|안 된다|안 됨|필요|' + MUST, re.I),
    'bound': re.compile(r'at least|at most|up to|more than|over|이상|이하|초과|미만|최대|최소|까지|넘|적어도|많아야|max|min|\d\s*\+|≥|≤|>|<|한도|상한|하한', re.I),
    'default': re.compile(r'default|기본|따로 (?:정|설정)|보통|대개|흔히|평소|일반적', re.I),
    'about': re.compile(r'약 |대략|정도|쯤|about|approx|around|roughly|≈|~', re.I),
}
# 알림에 적는 짧은 답
HEDGE_SAY = {'may': '수 있다·가능·불확실·못 찾음', 'should': '권고·권장·…해야', 'must': '반드시·필수·…해야(받아야)', 'bound': '이상·이하·최대·까지', 'default': '기본·보통·대개', 'about': '약·쯤·정도'}
SAME = [re.compile(p, re.I) for p in (          # 같은 뜻으로 보는 말
    r'보통|대개|대체로|흔히|일반적|통상|평소|usual|typical|generally|commonly|normally', r'가끔|때로|종종|자주|sometimes|occasional|often', r'거의|대부분|nearly|almost|mostly|\bmost\b',
    r'일부|몇몇|\bsome\b|several|\bfew\b|부분적', r'불확실|확실하지|모른다|모름|못 찾|찾지 못|확인하지 못|엇갈|추정|짐작|unclear|unknown|uncertain', r'아직|현재|지금은|currently|for now|\byet\b')]


def same_word(a, b):
    return any(r.search(a) and r.search(b) for r in SAME)


ABSOLUTE = [('항상', re.compile(r'항상|언제나'), re.compile(r'\balways\b|\bevery\b|\beach time\b|항상|언제나|늘|매번|마다', re.I)),
            ('절대', re.compile(r'절대(?!값|경로|적|치|평가|주소|좌표|량|다수)(?:로)?(?=[\s,])'), re.compile(r'\bnever\b|\bmust not\b|\bunder no\b|\babsolute|절대|결코', re.I)),
            ('모두', re.compile(r'모두(?!의)|모든|전부'), re.compile(r'\ball\b|\bevery|\beach\b|\bany|\bentire|\bwhole\b|\bboth\b|\bnone\b|\bno\b|둘 다|모두|모든|전부|전체|각|전혀|마다', re.I)),
            ('반드시', re.compile(r'반드시|무조건'), re.compile(r'\bmust\b|\bshall\b|\brequire|\balways\b|\bneed|\bmandatory\b|\bha(?:ve|s) to\b|반드시|무조건|필수|꼭|' + MUST, re.I))]


# ---------- 비밀 값 · 홈 경로 ----------
SECRETS = [re.compile(p) for p in (
    r'\bsk-(?:ant-|proj-)?[A-Za-z0-9_\-]{20,}', r'\bgh[pousr]_[A-Za-z0-9]{30,}', r'\bgithub_pat_[A-Za-z0-9_]{30,}', r'\bAKIA[0-9A-Z]{16}\b',
    r'\bAIza[0-9A-Za-z_\-]{35}', r'\bxox[abprs]-[A-Za-z0-9\-]{10,}', r'-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----',
    r'\beyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{5,}', r'\bglpat-[A-Za-z0-9_\-]{20,}', r'\bnpm_[A-Za-z0-9]{30,}')]
WEAK_SECRET = re.compile(r'(?i)\b(?:password|passwd|secret|token|api[_-]?key|access[_-]?key)\b["\']?\s*[:=]\s*["\']?(?![<$\[{*]|your|xxx|example|test|dummy|none|null|true|false)([A-Za-z0-9_\-+/=.]{12,})')
HOME = re.compile(r'(?:/Users/|/home/|[A-Z]:\\Users\\)(?!(?:me|you|user|username|name|USER|사용자|사용자이름|이름|계정)(?![\w가-힣])|\.{2,}|…|(?:에|에는|에서|를|을|의|로|와|과|는|은|가|이|도|만|밑|아래|뒤|폴더)(?![\w가-힣]))[\w.\-]+')


def mask(v):
    return v[:3] + '***'


def secrets(s):
    """[(세기, 가린 값, 줄)] — 세기는 '확실'·'후보'."""
    out = []
    for i, ln in enumerate(s.split('\n'), 1):
        hit = [r.search(ln) for r in SECRETS]
        hit = [h for h in hit if h]
        for h in hit:
            out.append(('확실', mask(h.group(0)), i))
        if not hit:
            w = WEAK_SECRET.search(ln)
            if w and re.search(r'\d', w.group(1)) and re.search(r'[A-Za-z]', w.group(1)):
                out.append(('후보', mask(w.group(1)), i))
    return out


def hide_secrets(s):
    for r in SECRETS:
        s = r.sub(lambda m: mask(m.group(0)), s)
    return WEAK_SECRET.sub(lambda m: m.group(0).replace(m.group(1), mask(m.group(1))) if re.search(r'\d', m.group(1)) and re.search(r'[A-Za-z]', m.group(1)) else m.group(0), s)


# ---------- 마크다운 ----------
def split_row(line):
    """마크다운 표 한 줄 → 칸 목록 (`\\|`는 글자)."""
    s = line.strip()
    s = re.sub(r'^\||(?<!\\)\|$', '', s)
    return [c.strip().replace('\\|', '|') for c in re.split(r'(?<!\\)\|', s)]


def front_matter(s):
    """(머리말 dict, 본문이 시작하는 줄 번호(1부터))"""
    if not s.startswith('---'):
        return {}, 1
    ls = s.split('\n')
    for i in range(1, min(len(ls), 80)):
        if ls[i].strip() == '---':
            meta, key = {}, None
            for ln in ls[1:i]:
                m = re.match(r'^([A-Za-z_][\w-]*)\s*:\s*(.*)$', ln)
                if m:
                    key, v = m.group(1), m.group(2).strip()
                    meta[key] = '' if v in ('>', '>-', '|', '|-') else v.strip('"\'')
                elif key and ln.strip():
                    meta[key] = (meta[key] + ' ' + ln.strip()).strip()
            return meta, i + 2
    return {}, 1


def headings(s):
    out, fence = [], False
    for i, ln in enumerate(s.split('\n'), 1):
        if FENCE.match(ln):
            fence = not fence
        elif not fence:
            m = re.match(r'^(#{1,6})\s+(.+?)\s*#*$', ln)
            if m:
                out.append((i, len(m.group(1)), m.group(2)))
    return out


def clip(s, n):
    s = re.sub(r'\s+', ' ', str(s)).strip()
    return s if len(s) <= n else s[:max(1, n - 1)].rstrip() + '…'

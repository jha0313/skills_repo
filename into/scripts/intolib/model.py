# -*- coding: utf-8 -*-
"""model.json 읽기 · 검사."""
import json
import os
import re

from . import UserError, formats
from . import text as T
from .cite import EXT
from .formats import Issue
from .route import CODE_EXT

COMMON = ('type', 'title', 'scope', 'source', 'missing', 'facts', 'nodes', 'edges', 'steps', 'order', 'flips', 'terms')
# 유형별 키의 기본값 (formats의 ## model 표가 있으면 그것이 이긴다)
TYPE_KEYS = {
    'pr': {'changes': 'list{id,what,before,after,src}', 'cases': 'list{id,input,before,after,same?,src}'},
    'codebase': {'zones': 'list{id,t,does,grade,src}', 'path': 'list', 'flips': 'list{id,if,then,edges?,src}'},
    'design-doc': {'options': 'list{id,t,chosen?,src}', 'criteria': 'list{id,t}', 'cells': 'list{o,c,t,sign,src}', 'open': 'list{t,src}'},
    'paper-concept': {'results': 'list{id,group?,label,value,unit?,base?,cond?,src}', 'claims': 'list{id,t,results?,src}', 'limits': 'list{t,src}'},
    'video': {'chapters': 'list{id,at,to?,t,claim?,kind?,src}'},
    'social-post': {'claims': 'list{id,t,ev,quote?,src}'},
    'community-post': {'positions': 'list{id,t,n?,why?,quote?,ev?,src}', 'agree': 'list{t,src}', 'clashes': 'list{a,b,on,src}'},
    'local-file': {'parts': 'list{id,range,t,does,src}', 'whatif': 'list{if,then,src}'},
    'skill': {'lanes': 'list', 'steps': 'list{id,lane,do,out?,src}', 'triggers': 'list{say,route,src}', 'decisions': 'list{what,why,instead?,proof?,mark?,src}'},
    'general': {'qas': 'list{q,a,src}'},
}
ENUMS = {'when': ('before', 'after', 'both'), 'sign': ('+', '-', '?'), 'ev': None, 'grade': None, 'kind': None}
ORDERS = ('time', 'call', 'text', 'none')
MARKS = ('추정', '불확실', '근거 미제시', '보충')
REFS = {'edges': 'edges', 'results': 'results'}          # 항목 안의 id 목록이 가리키는 모델 키
NOT_PROSE = {'id', 'src', 'from', 'to', 'when', 'order', 'sign', 'kind', 'ev', 'grade', 'lane', 'edges', 'results', 'o', 'c', 'a', 'b', 'mark', 'main', 'guess', 'key', 'chosen', 'same', 'hedge', 'range', 'at', 'f', 'type'}


def load(path):
    """(정리된 model, 원래 글)"""
    if not os.path.exists(path):
        raise UserError('model.json이 없다: %s. 작업 지시의 2번을 보고 먼저 쓴다' % path)
    s = open(path, encoding='utf-8').read()
    m = parse_json(s, os.path.basename(path))
    return normalize(m), s


def parse_json(s, name):
    try:
        m = json.loads(s)
    except ValueError as e:
        line = getattr(e, 'lineno', 1)
        near = s.split('\n')[line - 1].strip() if line - 1 < len(s.split('\n')) else ''
        raise UserError('%s:%d 칸 %d — JSON 문법 오류(%s). 쉼표·따옴표를 본다: %s' % (name, line, getattr(e, 'colno', 1), getattr(e, 'msg', e), T.clip(near, 60)))
    if not isinstance(m, dict):
        raise UserError('%s는 {…} 객체여야 한다' % name)
    return m


def as_list(v):
    return v if isinstance(v, list) else [] if v in (None, '') else [v]


def normalize(m):
    m = dict(m)
    st = m.get('steps')
    if isinstance(st, dict):
        m['order'] = m.get('order') or st.get('order')
        st = st.get('items') or st.get('list') or st.get('steps') or []
    st = [dict(x) if isinstance(x, dict) else {'do': str(x)} for x in as_list(st)]
    for x in st:
        if x.get('order') and not m.get('order'):
            m['order'] = x['order']
        x.pop('order', None)
        if x.get('lane') and not x.get('who'):
            x['who'] = x['lane']
    if st:
        m['steps'] = st
    for k, v in list(m.items()):
        if isinstance(v, list):
            m[k] = [dict(x, src=as_list(x['src'])) if isinstance(x, dict) and 'src' in x else x for x in v]
    for i, e in enumerate(as_list(m.get('edges')), 1):
        if isinstance(e, dict) and not e.get('id'):
            e['id'] = 'e%d' % i
    used = {str(x['id']) for v in m.values() if isinstance(v, list) for x in v if isinstance(x, dict) and x.get('id')}
    for i, x in enumerate(as_list(m.get('steps')), 1):
        if not x.get('id'):
            x['id'] = 's%d' % i if 's%d' % i not in used else 'steps%d' % i
    return m


def refs(m):
    """id → 항목. id가 없으면 `키+번호`(steps2, changes1)로도 가리킬 수 있다."""
    out = {}
    for k, v in m.items():
        if isinstance(v, list):
            for i, x in enumerate(v, 1):
                if isinstance(x, dict):
                    for name in ('%s%d' % (k, i), '%s%d' % (k.rstrip('s'), i)):
                        out.setdefault(name, x)
    for k, v in m.items():
        if isinstance(v, list):
            for x in v:
                if isinstance(x, dict) and x.get('id'):
                    out[str(x['id'])] = x
    return out


def id_of(rf, x):
    i = str(x.get('id') or '')
    return i if i in rf else next((k for k, y in rf.items() if y is x), '')


def prose(x):
    """항목 안의 글 [(필드, 글)]"""
    out = []
    for k, v in x.items():
        if k in NOT_PROSE and not (k == 'a' and 'q' in x):
            continue
        if k == 'cond' and v == 'none':          # 조건어를 봤다는 표시
            continue
        for s in as_list(v):
            if isinstance(s, (str, int, float)) and not isinstance(s, bool) and str(s).strip():
                out.append((k, str(s)))
    return out


def all_prose(m):
    out = [str(m.get(k) or '') for k in ('title', 'scope')]
    for v in m.values():
        if isinstance(v, list):
            for x in v:
                if isinstance(x, dict):
                    out += [s for _, s in prose(x)]
                elif isinstance(x, str):
                    out.append(x)
    return '\n'.join(out)


def marks(x):
    raw = x.get('mark')
    ms = [s.strip() for r in as_list(raw) for s in re.split(r'[,·/]', str(r)) if s.strip()]
    if x.get('guess') and '추정' not in ms:
        ms.append('추정')
    return ms


def resolve_all(m, source):
    """{src 글: resolve 결과}"""
    out = {}
    for v in m.values():
        if isinstance(v, list):
            for x in v:
                if isinstance(x, dict):
                    for s in as_list(x.get('src')):
                        for one in split_src(s):
                            if one not in out:
                                out[one] = source.resolve(one)
    return out


def split_src(s):
    return [p.strip() for p in re.split(r'\s*(?:;|\s·\s)\s*', str(s)) if p.strip()]


def backticks(s):
    return [t.strip() for t in re.findall(r'`([^`\n]{1,120})`', s) if t.strip()]


PLACE = re.compile(r'https?://\S+|(?<![\w/])(?:[\w./@\-]*[\w\-]\.' + EXT + r'|raw|원문)\s?:-?\d+(?:\s*[-–~]\s*\d+)?(?:\s*,\s*:?-?\d+(?:\s*[-–~]\s*\d+)?(?![\d%가-힣]))*')          # 주소 · 글에 쓴 근거 위치(a.md:16-18, 38)


def check_numbers(text, ok, where, add):
    """원문에 없는 숫자. (계산: 식)이 있으면 식의 값과 맞으면 통과. ok(정규형, 줄·글자 수로 썼나)"""
    s = PLACE.sub(' ', text)
    calcs = T.CALC.findall(s)
    values = []
    for c in calcs:
        v = T.calc_value(c)
        if v is None:
            add('WARN', where, '계산식 `(계산: %s)`을 읽지 못했다. 숫자와 + − × ÷ 만 쓴다' % T.clip(c, 40))
        else:
            values.append(v)
        for raw, forms, _ in T.numbers(re.split(r'[=≈]', c)[0]):
            if not ok(forms) and raw not in ('100', '1000', '60', '24', '10', '2'):
                add('FAIL', where, '계산식의 숫자 %s%s 원문에 없다: `%s`' % (raw, T.josa(raw), T.clip(c, 40)))
    s = T.CALC.sub(' ', s)
    s = re.sub(r'(?m)^\s*(?:\d{1,2}[.)]|[①-⑳])\s+', ' ', s)
    for raw, forms, pos in T.numbers(s):
        if ok(forms):
            continue
        if any(any(_close(f, v) for f in forms) for v in values):
            continue
        tail = s[pos + len(raw):pos + len(raw) + 6]
        if (re.match(r'\s?(?:줄|행|자(?![가-힣])|lines?\b)', tail) or s[max(0, pos - 1):pos] in ('+', '-', '−', '–') and re.match(r'\s*(?:$|[·,.)/+\-−–]|줄)', tail)) and ok(forms, True):
            continue
        if re.match(r'\s?(?:단계|번째|차례)', tail):
            continue
        n = sorted(forms)[0]
        if calcs and not values:
            continue
        if len(n) == 1:
            add('WARN', where, '숫자 %s%s 원문에 그대로 없다(센 값이면 무엇을 센 것인지 본다): %s' % (raw, T.josa(raw), T.clip(text, 50)))
        else:
            add('FAIL', where, '숫자 %s%s 원문에 없다. 원문 값으로 고치거나 `(계산: 식)`을 붙인다: %s' % (raw, T.josa(raw), T.clip(text, 60)))


def check_near(text, near, find, extra, where, add, table=''):
    """숫자를 연결한 근거에서 먼저 찾는다. 다른 곳에만 있거나 단위·부호가 다르면 WARN. table = 근거가 표의 칸일 때 그 표(단위는 머리나 설명에 있다)"""
    s = PLACE.sub(' ', text)
    calc = [v for v in map(T.calc_value, T.CALC.findall(s)) if v is not None]
    have, miss = T.measures(near, True), []
    values = T.number_set(near, False).union(*(h[1] for h in have))
    for raw, forms, unit, sign, _ in T.measures(T.CALC.sub(' ', s)):
        if forms & extra and unit in ('', '년') or any(_close(f, v) for f in forms for v in calc):
            continue
        conv = T.converted(forms, unit, have)
        same = [h for h in have if forms & h[1] and not (conv and h[2] != unit)] + conv          # 바꿔 적은 값이면 다른 단위의 같은 숫자(500건)는 빼고 부호를 본다
        if not conv and not forms & values:
            at = find(forms) if unit or len(sorted(forms)[0]) > 1 else ''          # 단위 없는 한 자리 수는 센 값일 때가 많다
            if at or unit and forms & extra:
                miss.append('%s — %s에는 있다' % (raw, at or '꾸러미가 센 값이나 제목'))
        elif not conv and unit and same and not any(h[2] == unit for h in same) and (all(h[2] or h[4] for h in same) or not T.SAID[unit].search(near + table)):
            add('WARN', where, '단위가 근거와 다르다: %s — 근거는 %s(단위가 적힌 줄도 근거에 넣는다)' % (raw, same[0][0]))
        elif not sign and same and all(h[3] == '-' for h in same) and (unit or any(h[2] for h in same)) and not DOWN.search(s):
            add('WARN', where, '부호가 근거와 다르다: %s — 근거는 -%s' % (raw, same[0][0]))
        elif sign and same and (all(h[3] and h[3] != sign for h in same) or sign == '-' and not any(h[3] for h in same) and not DOWN.search(near)):
            add('WARN', where, '부호가 근거와 다르다: %s%s — 근거는 %s%s' % (sign, raw, same[0][3], same[0][0]))
    if miss:
        add('WARN', where, '근거 구간에 없음: %s: %s' % (', '.join(dict.fromkeys(miss)), T.clip(text, 40)))


DOWN = re.compile(r'감소|줄[어었이인]|낮|떨어|하락|적[게다은]|짧|빠르|빠른|빨라|지[운우]|뺀|절감|손실|마이너스|음수|\bdrop|\bdecreas|\breduc|\blower|\bf[ae]ll\b|\bless\b|\bfewer|\bshorter|\bfaster|\bdown\b|\bminus|\bdelet|\bloss|\bremov', re.I)          # 부호 없이 줄었다고 적는 말


PLAIN = re.compile(r'(?<![\w`./:@#\-])(?:[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)+|[A-Z]?[a-z][a-z0-9]*(?:[A-Z][a-z0-9]+)+)(?![A-Za-z0-9_`])')
WELL_KNOWN = {'github', 'gitlab', 'youtube', 'javascript', 'typescript', 'linkedin', 'deepmind'}


def check_plain(text, source, files, known, where, add, later):
    """백틱 없이 쓴 코드 이름(CamelCase·snake_case)이 원문에 있는가."""
    for tok in dict.fromkeys(PLAIN.findall(re.sub(r'`[^`\n]*`|https?://\S+', ' ', text))):
        if tok.lower() in WELL_KNOWN or tok in known or source.kind == 'none':
            continue
        if source.kind == 'dir':
            if not source.has_text(tok, files):
                later.setdefault(tok, []).append((where, 'WARN'))
        elif tok.lower() not in source.text().lower():
            add('WARN', where, '이름 `%s`가 원문에 없다. 표기를 다시 본다(원문 이름이 아니면 풀어 쓴다)' % tok)


def _close(f, v):
    try:
        x = float(f)
    except ValueError:
        return False
    return abs(x - v) <= max(0.051 if '.' in f else 0.51, abs(v) * 0.0005) if f.count('.') <= 1 else False


CITE_LIKE = re.compile(r'^[\w./@\-]+:-?\d+(?:[-–~]\d+)?$')


def check_idents(text, source, files, known, where, add, later):
    """백틱 식별자가 원문에 있는가. 폴더 원문에서 근거 파일에 없는 것은 later에 모아 한 번에 찾는다."""
    for tok in backticks(text):
        if CITE_LIKE.match(tok) or tok in known or len(tok) < 2 or not re.search(r'[A-Za-z가-힣0-9]', tok):
            continue
        if source.has_text(tok, files):
            continue
        parts = [w for w in re.split(r'[\s/]*(?:…|\.\.\.)[\s/]*|\s+', tok) if len(w) >= 2]
        if source.kind in ('file', 'pr'):
            if len(parts) > 1 and all(source.has_text(w) for w in parts):
                continue
            add('FAIL', where, '`%s`가 원문에 없다. 원문 표기를 그대로 옮기거나 백틱을 뺀다' % T.clip(tok, 50))
        elif source.kind == 'dir':
            later.setdefault(tok, []).append((where, 'FAIL'))


def flush_idents(source, later, add):
    if not later:
        return
    for tok in source.missing_tokens(list(later)):
        for w, lv in later[tok][:1]:
            add(lv, w, '이름 `%s`가 원문 어디에도 없다. 표기를 다시 본다' % T.clip(tok, 50))


def _line_of(raw, key, i, item):
    """model.json에서 이 항목이 있는 줄."""
    if item.get('id'):
        m = re.search(r'"id"\s*:\s*"%s"' % re.escape(str(item['id'])), raw)
        if m:
            return raw.count('\n', 0, m.start()) + 1
    m = re.search(r'"%s"\s*:\s*[\[{]' % re.escape(key), raw)
    if not m:
        return 1
    depth, n, k = 0, 0, m.end()
    in_str = esc = False
    while k < len(raw):
        c = raw[k]
        if in_str:
            in_str = not (c == '"' and not esc)
            esc = c == '\\' and not esc
        elif c == '"':
            in_str = True
        elif c == '{':
            if depth == 0:
                n += 1
                if n == i:
                    return raw.count('\n', 0, k) + 1
            depth += 1
        elif c == '}':
            depth -= 1
        elif c == ']' and depth == 0:
            break
        k += 1
    return raw.count('\n', 0, m.start()) + 1


def code_comment_only(res, lines):
    f = res.get('file') or ''
    if os.path.splitext(f)[1].lower() not in CODE_EXT:
        return lines
    return [(n, t) for n, t in lines if re.search(r'//|#|/\*|^\s*\*|"""|--\s', t)]


def check(m, raw, source, pack_type=''):
    out = []

    def add(level, where, msg):
        out.append(Issue(level, where, msg))
    typ = m.get('type') if m.get('type') and isinstance(m['type'], str) else pack_type
    if not m.get('type') or typ != m['type']:
        add('FAIL', 'model.json:1 type', '`"type":"%s"`을 쓴다' % (pack_type or '유형'))
    elif pack_type and typ != pack_type:
        add('WARN', 'model.json:1 type', '작업 폴더의 유형은 `%s`인데 `%s`이다. 바꾸려면 start에 --type을 준다' % (pack_type, typ))
    for k, why in (('title', '제목'), ('source', '출처 문장(무엇을 어디까지 읽었나)')):
        if not str(m.get(k) or '').strip():
            add('FAIL', 'model.json:1 %s' % k, '`%s`(%s)가 비었다' % (k, why))
    for k, n in (('title', 30), ('scope', 25)):
        if T.count(m.get(k)) > n:
            add('WARN', 'model.json:%d %s' % (_key_line(raw, k), k), '%s %d자다. 첫 줄에 나오니 %d자까지로 줄인다(자세한 것은 `source`에)' % ({'title': '제목', 'scope': '범위'}[k], T.count(m.get(k)), n))
    if not as_list(m.get('facts')):
        add('FAIL', 'model.json:1 facts', '사실이 하나도 없다')
    for k in ('facts', 'nodes', 'edges', 'steps', 'flips', 'terms') + tuple(TYPE_KEYS.get(typ, {})):
        if m.get(k) not in (None, '') and not isinstance(m[k], list):
            add('FAIL', 'model.json:%d %s' % (_key_line(raw, k), k), '배열로 쓴다: `"%s":[…]`' % k)
    spec_rows = []
    if formats.exists(typ):
        spec_rows = formats.load(typ).model_rows()
    spec = {r['key']: r for r in spec_rows}
    if not spec:
        for k, form in TYPE_KEYS.get(typ, {}).items():
            f = formats.parse_fields(form)
            spec[k] = {'key': k, 'fields': f[1], 'enums': f[2], 'opt': f[3], 'count': (0, None)}
    for k in m:
        if k not in COMMON and k not in spec:
            add('WARN', 'model.json:%d %s' % (_key_line(raw, k), k), 'formats/%s.md의 `## model` 표에 없는 키다. 어느 모드도 쓰지 않는다' % typ)
    defaults = {k: formats.parse_fields(f) for k, f in TYPE_KEYS.get(typ, {}).items()}
    for k, r in spec.items():
        n = len(as_list(m.get(k)))
        lo, hi = r['count']
        where = 'model.json:%d %s' % (_key_line(raw, k), k)
        if hi is not None and n > hi:
            add('FAIL', where, '%d개다. %d개까지다(독자의 첫 질문에 답하는 것만 남긴다)' % (n, hi))
        elif n < lo:
            add('WARN', where, '%d개다(%s개부터). 원문에 없으면 비워도 된다' % (n, lo))
    ids, dup = {}, set()
    for k, v in m.items():
        if isinstance(v, list):
            for x in v:
                if isinstance(x, dict) and x.get('id'):
                    if str(x['id']) in ids:
                        dup.add(str(x['id']))
                    ids[str(x['id'])] = k
    for d in sorted(dup):
        add('FAIL', 'model.json:%d %s' % (_line_of(raw, ids[d], 1, {'id': d}), d), 'id `%s`가 두 번 나온다. 하나를 바꾼다' % d)
    node_ids = {str(n.get('id')) for n in as_list(m.get('nodes')) if isinstance(n, dict)}
    node_names = {str(n.get('t')) for n in as_list(m.get('nodes')) if isinstance(n, dict)}
    lanes = [x.get('t') or x.get('id') if isinstance(x, dict) else str(x) for x in as_list(m.get('lanes'))]
    resolved = resolve_all(m, source)
    warned_src, later, long_lines = set(), {}, set()
    cited_files = sorted({r['file'] for r in resolved.values() if r.get('file')})
    for key, v in m.items():
        if not isinstance(v, list) or key in ('terms',):
            continue
        row = spec.get(key)
        fields = row['fields'] if row else (defaults[key][1] if key in defaults else [])
        opt = (row['opt'] if row else set()) | (defaults[key][3] if key in defaults else set())
        for i, x in enumerate(v, 1):
            name = '%s[%d]' % (key, i)
            if not isinstance(x, dict):
                if key == 'path' and str(x) not in ids:
                    add('FAIL', 'model.json:%d %s' % (_key_line(raw, key), name), '간선 id `%s`가 없다' % x)
                elif (fields or key in ('facts', 'nodes', 'edges', 'steps', 'flips')) and key not in ('path', 'lanes'):
                    add('FAIL', 'model.json:%d %s' % (_key_line(raw, key), name), '{%s} 객체로 쓴다' % ','.join(fields or ('id', 't', 'src')))
                continue
            where = 'model.json:%d %s%s' % (_line_of(raw, key, i, x), name, ' ' + str(x['id']) if x.get('id') else '')
            if key == 'facts':
                if not x.get('id'):
                    add('FAIL', where, '`id`를 쓴다(f1, f2 …)')
                if not str(x.get('t') or '').strip():
                    add('FAIL', where, '`t`(문장)가 비었다')
            for f, y in x.items():
                if isinstance(y, dict) or isinstance(y, list) and any(isinstance(z, (dict, list)) for z in y) or f in ('t', 'do', 'then') and y is not None and not isinstance(y, str):
                    add('FAIL', where, '`%s`는 글로 쓴다(지금 %s)' % (f, '객체' if isinstance(y, dict) else '배열' if isinstance(y, list) else json.dumps(y)))
            if key == 'nodes' and not (x.get('id') and str(x.get('t') or '').strip()):
                add('FAIL', where, '노드에 `id`와 `t`를 쓴다')
            if key == 'edges':
                for end in ('from', 'to'):
                    if str(x.get(end)) not in node_ids:
                        add('FAIL', where, '`%s`의 노드 `%s`가 nodes에 없다' % (end, x.get(end)))
                if not str(x.get('t') or '').strip():
                    add('FAIL', where, '라벨(`t`)이 비었다. 무엇이 오가는지 쓴다')
                if x.get('when') and x['when'] not in ENUMS['when']:
                    add('FAIL', where, '`when`은 before·after·both 중 하나다')
            if key == 'steps':
                if not str(x.get('do') or '').strip():
                    add('FAIL', where, '`do`(하는 일)가 비었다')
                if not x.get('who'):
                    add('WARN', where, '`who`(하는 쪽)가 비었다. 원문에 없으면 그대로 둔다')
                if lanes and x.get('lane') and x['lane'] not in lanes:
                    add('FAIL', where, '레인 `%s`가 lanes에 없다' % x['lane'])
            if key == 'flips' and not (x.get('if') and x.get('then')):
                add('FAIL', where, '`if`와 `then`을 쓴다')
            if key == 'parts' and x.get('range') and source.kind != 'none':
                r = source.resolve(str(x['range']))
                if not r['ok']:
                    add('FAIL', where, '`range` — ' + r['msg'])
            for ms in marks(x):
                if ms not in MARKS:
                    add('FAIL', where, '표시 `%s`를 %s 중 하나로 쓴다' % (ms, '·'.join(MARKS)))
            enums = dict(row['enums']) if row else {}
            for f, vals in list(enums.items()) + [('sign', ENUMS['sign'])] * (key == 'cells'):
                if x.get(f) not in (None, '') and str(x[f]) not in vals:
                    add('FAIL', where, '`%s`는 %s 중 하나다(지금 `%s`)' % (f, '·'.join(vals), x[f]))
            for f in fields:
                if f in ('id', 'src', 'mark', 'if', 'hedge', 'main', 'guess', 'key', 'when', 'f') or f in opt:
                    continue
                if x.get(f) in (None, '', []) and not (f == 'does' and str(x.get('grade') or '').startswith('목록')):
                    add('WARN', where, '`%s`가 비었다(원문에 없으면 그대로 둔다)' % f)
            for f, target in REFS.items():
                if f in x and f != key:
                    for r in as_list(x[f]):
                        if ids.get(str(r)) != target:
                            add('FAIL', where, '`%s`의 `%s`가 %s에 없다' % (f, r, target))
            for f, target in ((('o', 'options'), ('c', 'criteria')) if key == 'cells' else (('a', 'positions'), ('b', 'positions')) if key == 'clashes' else ()):
                if ids.get(str(x.get(f))) != target:
                    add('FAIL', where, '`%s`의 `%s`가 %s에 없다' % (f, x.get(f), target))
            # 근거
            srcs = [p for s in as_list(x.get('src')) for p in split_src(s)]
            need = key in ('facts', 'edges', 'steps', 'flips') or ('src' in fields and 'src' not in opt)
            if need and not srcs:
                add('FAIL', where, '근거(`src`)가 없다')
            extra = '보충' in marks(x)
            got = []
            for s in srcs:
                r = resolved[s]
                if not r['ok'] and not extra:
                    add('FAIL', where, r['msg'])
                elif (r['warn'] or len(r['lines']) > WIDE.get(source.kind, 60) and key in ('facts', 'edges', 'steps', 'flips')) and s not in warned_src:
                    warned_src.add(s)
                    add('WARN', where, r['warn'] or '근거 `%s`가 %d줄이다. 그 말이 있는 줄(%d줄 안)로 좁힌다' % (s, len(r['lines']), WIDE.get(source.kind, 60)))
                got.append(r)
            if got and not extra and all(r['kind'] == 'url' and not r['text'] for r in got):
                add('FAIL', where, '근거가 바깥 주소뿐이다. 원문 줄을 쓰거나, 확인한 바깥 자료면 `"mark":"보충"`을 쓴다')
            if key == 'nodes' or extra:
                continue
            files = [r['file'] for r in got if r.get('file')]
            cited = '\n'.join(r['text'] for r in got)
            for f, s in prose(x):
                check_numbers(s, lambda forms, counted=False: source.number_ok(forms, files or cited_files, counted), where, add)
                check_idents(s, source, files, (), where, add, later)
                check_plain(s, source, files, (), where, add, later)
            full = ' '.join(s for _, s in prose(x))
            if any(r['text'] for r in got):
                check_near(full, cited, lambda forms: source.where(lambda ln: T.says_number(ln, forms), files or cited_files), source._extra_numbers, where, add, '\n'.join(source.table(r) for r in got))
            if source.kind in ('dir', 'pr') and cited:
                body = '\n'.join(source.around(r) for r in got)
                flat = body.replace('_', '').lower()
                for tok in backticks(full):
                    miss = [w for w in re.findall(r'[A-Za-z_][A-Za-z0-9_]{3,}', tok) if re.search(r'[a-z]_[a-z]|[a-z][A-Z]', w) and w not in body and w.replace('_', '').lower() not in flat]
                    if miss:
                        add('WARN', where, '이름 `%s`가 근거 구간(앞뒤 8줄)에 없다. 근거를 다시 본다' % miss[0])
                        break
            if key in ('facts', 'changes', 'claims', 'flips', 'edges') and cited:
                _conditions(x, full, got, where, add, long_lines)
    flush_idents(source, later, add)
    if long_lines:
        show = ['%s%d' % (f + ':' if f else 'raw:', n) for f, n in sorted(long_lines, key=lambda x: (x[0] or '', x[1]))]
        add('WARN', 'model.json', '긴 줄 %d곳: 조건어를 직접 본다(%s%s). 봤으면 그 사실에 `"cond":"none"`이나 `if`·`hedge`를 쓴다' % (len(show), ', '.join(show[:6]), ' …' if len(show) > 6 else ''))
    if as_list(m.get('steps')):
        if m.get('order') not in ORDERS:
            add('WARN', 'model.json:%d order' % _key_line(raw, 'steps'), 'steps가 있으면 `"order":"time|call|text|none"`을 쓴다(없으면 none으로 본다)')
        who = {str(x.get('who')) for x in as_list(m['steps']) if x.get('who')}
        off = sorted(w for w in who if node_names and w not in node_names | node_ids and w not in lanes and not w.startswith('/'))
        if off and not lanes and typ not in ('paper-concept', 'local-file'):
            add('WARN', 'model.json:%d steps' % _key_line(raw, 'steps'), '하는 쪽 %s가 노드 이름과 다르다. 같은 대상이면 같은 이름으로 쓴다' % ', '.join('`%s`' % w for w in off[:3]))
    for i, t in enumerate(as_list(m.get('terms')), 1):
        if not isinstance(t, dict) or not t.get('w'):
            add('FAIL', 'model.json:%d terms[%d]' % (_key_line(raw, 'terms'), i), '`{"w":"쓴 말","o":["원문 표기"]}`로 쓴다')
            continue
        if source.kind in ('file', 'pr'):
            for o in as_list(t.get('o')):
                if not re.search(re.escape(str(o)), source.text(), re.I):
                    add('WARN', 'model.json:%d terms[%d]' % (_key_line(raw, 'terms'), i), '원문 표기 `%s`가 원문에 없다' % o)
    hard = [s for s in T.secrets(raw) if s[0] == '확실']
    if hard:
        add('FAIL', 'model.json:%d' % hard[0][2], '비밀 값(%s)이 들어 있다. `***`로 바꾼다' % hard[0][1])
    h = T.HOME.search(raw)
    if h:
        add('FAIL', 'model.json:%d' % (raw.count('\n', 0, h.start()) + 1), '홈 폴더 경로가 있다. 상대 경로로 바꾼다')
    return out


WIDE = {'dir': 100}          # 이보다 넓은 근거는 무엇을 가리키는지 모른다(글 60줄, 저장소는 함수 하나가 들게 100줄)


def _key_line(raw, key):
    m = re.search(r'"%s"\s*:' % re.escape(key), raw)
    return raw.count('\n', 0, m.start()) + 1 if m else 1


COMMON_EN = set('the and for are was were that this with from its has have not but can may all any our their these those which when where what will into than then them they you your only also such per via use used using'.split())
KIND_HINT = {'only': '~만', 'if': '조건', 'unless': '예외', 'default': '기본값', 'may': '할 수 있다', 'should': '권고', 'must': '의무', 'bound': '이상·최대', 'about': '어림', 'time': '때'}
KEEP_EXTRA = {'only': re.compile(r'만\b|만[\s,.)]|뿐|only|한정', re.I), 'if': re.compile(r'면[\s,.)]|때|경우|조건|if|when', re.I), 'unless': re.compile(r'제외|예외|않으면|아니면|빼고|except|unless', re.I)}


def _words(s):
    """문장끼리 겹침을 볼 낱말: 식별자 · 영문 · 숫자 · 한글 앞 두 글자."""
    out = {w.lower() for w in re.findall(r'[A-Za-z_][A-Za-z0-9_]{2,}', s)} - COMMON_EN
    for _, forms, _ in T.numbers(s, keep_code=True):
        out |= forms
    return out | {w[:2] for w in re.findall(r'[가-힣]{2,}', s)}


def sentences_of(rows):
    """[(줄 번호, 글)] → [(줄 번호, 문장)]. 이어 쓴 줄은 잇는다(목록·표·제목·빈 줄에서 끊는다)."""
    blocks = []
    for n, t in rows:
        t = re.sub(r'^\s*(?://+!?|#+|/?\*+/?|--|>)\s?', '', t)
        new = not blocks or not t.strip() or not blocks[-1][1] or re.match(r'\s*(?:[-*+]\s|\d+[.)]\s|\|)', t) or blocks[-1][2] != n - 1 or re.search(r'[.!?:|。]["\')\]]*\s*$', blocks[-1][1])
        if new:
            blocks.append([n, t.strip(), n])
        else:
            blocks[-1][1], blocks[-1][2] = blocks[-1][1] + ' ' + t.strip(), n
    return [(n, x) for n, t, _ in blocks if t for x in T.sentences(t)]


def _conditions(x, full, got, where, add, long_lines):
    cited = '\n'.join(t for r in got for _, t in (r.get('lines') or []))
    for name, rx, ok in T.ABSOLUTE:
        hit = rx.search(full)
        if hit and cited and not ok.search(cited):
            add('WARN', where, '`%s`가 근거 줄에는 없다. 원문에 같은 말이 없으면 지우거나 좁힌다' % hit.group(0))
    if x.get('if') or x.get('hedge') or x.get('cond') == 'none':
        return
    miss, mine = {}, _words(full)
    for r in got:
        ls = r.get('lines') or []
        if not 0 < len(ls) <= 12:
            continue
        ss = sentences_of(code_comment_only(r, ls))
        if len(ss) > 1:
            score = [len(mine & _words(t)) for _, t in ss]
            if not max(score):
                long_lines |= {(r.get('file'), n) for n, t in ss if _missing(t, full)}
                continue
            ss = [s for s, k in zip(ss, score) if k == max(score)][:1]
        for n, t in ss:
            for k in _missing(t, full):
                miss.setdefault(k, n)
    if miss:
        add('WARN', where, '근거 문장에 조건어가 있는데 `if`·`hedge`가 비었다: %s. 조건이 아니면 `"cond":"none"`' % ', '.join('%s(%s줄)' % (KIND_HINT[k], n) for k, n in list(miss.items())[:4]))


def _missing(t, full):
    """근거 문장의 조건어 가운데 사실 글에 남지 않은 것."""
    out = []
    for k in T.cond_kinds(t):
        keep = T.HEDGE_KEEP.get(k) or KEEP_EXTRA.get(k)
        if k not in ('must', 'time') and keep and not keep.search(full):
            out.append(k)
    return out

# -*- coding: utf-8 -*-
"""<mode>.json 검사와 정리 (모든 모드 공통)."""
import re

from . import HTML_MODES, NOTICE, SLOTS
from . import model as M
from . import text as T
from .cite import format_cites
from .formats import PIC_FORMS, PIC_KEY, Issue


def text_item(v):
    """'글' | {'t','f',…} → {'t','f','src',…} — 못 읽으면 None"""
    if isinstance(v, (str, int, float)) and not isinstance(v, bool):
        return {'t': str(v).strip(), 'f': []}
    if isinstance(v, dict):
        d = dict(v)
        d['f'] = [str(x) for x in M.as_list(v.get('f'))]
        if 't' in d:
            d['t'] = str(d['t']).strip()
            return d
        if 'q' in d or 'a' in d:
            d['q'], d['a'] = str(d.get('q') or '').strip(), str(d.get('a') or '').strip()
            d['t'] = d['q'] + ' ' + d['a']
            return d
        if 'v' in d:
            d['t'] = ' '.join(str(d[k]) for k in ('v', 'unit', 'of') if d.get(k) not in (None, ''))
            return d
        if 'who' in d or 'do' in d:
            d['t'] = ' — '.join(str(d[k]) for k in ('who', 'do') if d.get(k))
            return d
        if 'src' in d:
            d['t'] = ''
            return d
    return None


def row_example(cols):
    return '{' + ','.join('"%s":"…"' % c for c in cols) + ',"f":["f1"]}'


# 그림 칸에서 짧게 바꿔 쓸 수 있는 글
PIC_TEXT = {'map': ('t', 'does'), 'lanes': ('do', 'out'), 'timeline': ('t', 'claim'), 'positions': ('t', 'why', 'cost'), 'options': ('t', 'd'),
            'anatomy': ('t', 'does'), 'chart': ('label', 'group', 'cond')}
NEAR = '(5% 안이라 그대로 둬도 된다)'
ID_ONLY = re.compile(r'^[a-z]{1,8}\d+$')


def empty(v):
    if v is None or v == '' or v == [] or v == {}:
        return True
    if isinstance(v, list):
        return all(empty(x) for x in v)
    if isinstance(v, dict):
        return all(empty(v.get(k)) for k in v if k != 'f')
    return False


def same_as_eli5(rows, mode, spec, eli5):
    """비우면 eli5.json에서 오는 칸: `eli5 그대로`라고 적힌 칸, html·interactive에서 key·형이 같고 eli5의 글이 한도에 드는 칸."""
    mine = {r['key']: r for r in spec.rows('eli5') or []} if mode in HTML_MODES else {}

    def fits(r, e):
        if not e or r['form'] != e['form'] or r['cols'] != e['cols'] or r['form'] in PIC_FORMS + ('kit',):
            return False
        if all(not r[k] or e[k] and r[k] >= e[k] for k in ('n', 'chars')):
            return True
        xs, line = [text_item(x) for x in M.as_list(eli5.get(r['key']))], r['form'] == 'line'
        return (line or r['form'] in ('list', 'steps') and len(xs) <= (r['n'] or len(xs))) and all(x and T.count(x.get('t')) <= ((r['n'] if line else r['chars']) or 9999) for x in xs)
    return {r['key'] for r in rows if not empty(eli5.get(r['key'])) and (r['hint'].startswith('eli5 그대로') or fits(r, mine.get(r['key'])))}


class Checker(object):
    def __init__(self, mode, rows, model, raw_cells, source, pack, spec, file=None, eli5=None):
        self.mode, self.rows, self.model, self.raw, self.source, self.pack, self.spec = mode, rows, model, raw_cells, source, pack, spec
        self.file = file or mode + '.json'
        self.refs = M.refs(model)
        self.issues, self.cells, self.blank, self.pieces = [], {}, [], []
        self.resolved = M.resolve_all(model, source)
        self.model_text = M.all_prose(model)
        self.model_numbers = T.number_set(self.model_text)
        self.later = {}
        self.cited_files = sorted({r['file'] for r in self.resolved.values() if r.get('file')})
        self.nolink, self.eli5, self.lent = [], eli5 or {}, set()

    def add(self, level, where, msg):
        if where.split('[')[0].split(' ')[0] in self.lent:
            where += '(eli5.json의 값)'
        self.issues.append(Issue(level, '%s %s' % (self.file, where) if where else self.file, msg))

    # ----- 한 칸 -----
    def run(self):
        known, same = {r['key'] for r in self.rows} | {'missing', 'source'}, same_as_eli5(self.rows, self.mode, self.spec, self.eli5)
        for k in self.raw:
            if k not in known:
                self.add('WARN', k, '이 모드의 표에 없는 키다. 쓰이지 않는다(표의 키: %s)' % ', '.join(r['key'] for r in self.rows))
        for r in self.rows:
            v = self.raw.get(r['key'])
            if v is not False and empty(v) and r['key'] in same:
                v = self.lend(r)
            off = v is False or (r['form'] == 'map' and self.mode in ('brief', 'eli5', 'ste') and empty(v) and bool(self.pack.get('zone')))      # 일부러 뺀 칸 · 구역의 글에는 지도를 그리지 않는다
            before = len([i for i in self.issues if i.level == 'FAIL'])
            got = None if off else self.cell(r, v)
            if got in (None, [], '') or (isinstance(got, dict) and not got):
                none = PIC_KEY[r['form']] if r['form'] in PIC_FORMS else r['key'] if r['form'] == 'table' and any(x['key'] == r['key'] for x in self.spec.model_rows()) else ''
                if r['required'] and none and not off and empty(v) and not M.as_list(self.model.get(none)):
                    self.add('WARN', r['key'], '%s(model.json에 %s가 없다). 원문에 없으면 그대로 둔다' % ('그림이 없다' if r['form'] in PIC_FORMS else '표가 비었다', none))
                    self.blank.append(r['label'])
                elif r['required']:
                    if len([i for i in self.issues if i.level == 'FAIL']) == before:
                        self.add('FAIL', r['key'], '필수 칸 `%s`(%s)이 비었다' % (r['key'], r['label']))
                elif not (r['optional'] or off):
                    self.blank.append(r['label'])
                continue
            self.cells[r['key']] = got
        for s in M.as_list(self.raw.get('missing')):
            self.check_text('missing', str(s), [], linked=False)
        self.repeats()
        M.flush_idents(self.source, self.later, lambda lv, w, m: self.add(lv, w, m))
        if self.nolink:
            self.add('WARN', '', '근거(`f`) 없는 칸: %s — 비유·확인 질문이 아니면 `{"t":…,"f":["f1"]}`로 쓴다' % ', '.join(self.nolink[:8]))
        return self

    def lend(self, r):
        """`eli5 그대로` 칸을 비우면 eli5.json의 값."""
        v, n = self.eli5[r['key']], r['n']
        self.lent.add(r['key'])
        if isinstance(v, list) and r['form'] in ('list', 'steps', 'table', 'qa') and n and len(v) > n:
            self.add('WARN', r['key'], '%d개 가운데 앞 %d개만 썼다. 다르게 고르려면 이 칸에 쓴다' % (len(v), n))
            v = v[:n]
        return v

    def text_of(self, x):
        """모델 항목 하나 → 한 줄 글 (칸에 id만 썼을 때)."""
        g = lambda k: str(x.get(k) or '').strip()
        if g('before') or g('after'):
            return '%s: %s → %s' % (g('what') or g('input') or g('t'), g('before') or '없음', g('after') or '없음')
        if g('then'):
            return '%s → %s' % (g('if'), g('then'))
        if 'from' in x and 'to' in x:
            return '%s → %s: %s' % tuple([str((self.refs.get(str(x[k])) or {}).get('t') or x[k]) for k in ('from', 'to')] + [g('t')])
        if g('do') and self.mode == 'doc':
            return (g('who') + ' — ' if g('who') else '') + g('do') + ('(%s)' % g('if') if g('if') and g('if') not in g('do') else '') + (' ✗ ' + g('fail') if g('fail') else '')
        head = g('t') or g('do') or g('what') or g('label')
        more = g('does') or g('why') or g('claim') or (g('value') and g('value') + g('unit'))
        return head + (' — ' + more if more else '') if head else ' — '.join(s for _, s in M.prose(x))

    def by_id(self, x):
        """칸에 id만 썼으면 그 항목의 글로 푼다. → (값, 못 푼 id)"""
        s = x if isinstance(x, str) else x.get('t', x.get('id')) if isinstance(x, dict) and not set(x) - {'t', 'id', 'f'} else None
        s = s.strip() if isinstance(s, str) else ''
        if s in self.refs:
            return {'t': self.text_of(self.refs[s]), 'f': [s]}, ''
        if isinstance(x, dict) and x.get('t') and not x.get('f') and str(x.get('id') or '') in self.refs:
            x = dict(x, f=[str(x['id'])])
        return x, s if ID_ONLY.match(s) else ''

    def cell(self, r, v):
        form, key = r['form'], r['key']
        if form in PIC_FORMS:
            return self.pic(r, v)
        if form == 'kit':
            return self.kit(r, v)
        if empty(v) and key == 'terms' and M.as_list(self.model.get('terms')):
            v = ['%s = %s' % (t['w'], ' / '.join(str(x) for x in M.as_list(t.get('o')))) for t in self.model['terms'] if isinstance(t, dict) and t.get('w')][:r['n'] or 9]
            return [text_item(x) for x in v]
        if form == 'table':
            return self.table(r, v)
        if empty(v) and form in ('list', 'steps') and isinstance(self.model.get(key), list) and key != 'steps':
            v = [{'t': str(x['t']), 'f': [str(x.get('id') or '%s%d' % (key, i))]} for i, x in enumerate(self.model[key], 1) if isinstance(x, dict) and x.get('t')][:r['n'] or None]
        if empty(v):
            return None
        if form in ('line', 'quote', 'number') and isinstance(v, list):
            if len(v) > 1:
                self.add('FAIL', key, '한 칸인데 %d개다. 하나만 남긴다' % len(v))
            v = v[0]
        items = []
        for i, x in enumerate(M.as_list(v), 1):
            where = key if form in ('line', 'quote', 'number') else '%s[%d]' % (key, i)
            if form in ('line', 'list', 'steps'):
                x, bad = self.by_id(x)
                if bad:
                    self.add('FAIL', where, '글이 id `%s`뿐이고 model.json에 없다. 글을 쓴다: `{"t":"글","f":["f1"]}`' % bad)
                    continue
            it = text_item(x)
            if it is None:
                self.add('FAIL', where, '`"글"` 또는 `{"t":"글","f":["f1"]}`로 쓴다')
                continue
            if empty(it['t']) and not it.get('src'):
                continue
            it['where'] = where
            items.append(it)
        if form == 'code':
            return self.code(r, items)
        self.limits(r, items)
        for it in items:
            self.check_text(it['where'], it['t'], it['f'], linked=not r['free'], srcs=M.as_list(it.get('src')), item=it)
            if form == 'quote' and self.source.kind in ('file', 'pr') and not self.source.has_text(it['t'].strip('"“”\'')):
                self.add('FAIL', it['where'], '원문과 글자가 다르다. 원문 그대로 옮긴다: %s' % T.clip(it['t'], 50))
            if form == 'qa' and not (it.get('q') and it.get('a')):
                self.add('FAIL', it['where'], '`{"q":"질문","a":"답"}`으로 쓴다')
                it.update(q=str(it.get('q') or ''), a=str(it.get('a') or ''))
            elif form == 'qa':
                sfx = mark_suffix(it['t'], [self.refs[i] for i in it['f'] if i in self.refs])
                it['a'], it['t'] = it['a'] + sfx, it['t'] + sfx
        return items

    def limits(self, r, items):
        form, n, chars, key = r['form'], r['n'], r['chars'], r['key']
        if form in ('line', 'quote', 'number'):
            maxn, maxc = 1, n
        elif form == 'qa' and n and not chars and n >= 20:
            maxn, maxc = None, n
        else:
            maxn, maxc = n, chars
        if maxn and len(items) > maxn:
            self.add('FAIL', key, '%d개다. %d개까지다' % (len(items), maxn))
        for it in items:
            c = T.count(it['t'])
            if T.over(c, maxc):
                self.add(T.over(c, maxc), it['where'], '%d자다. %d자까지다%s: %s' % (c, maxc, NEAR if T.over(c, maxc) == 'WARN' else '', T.clip(it['t'], 40)))

    def auto_row(self, key, i, x, cols):
        """모델 항목 → 표 한 행"""
        vals = [str(x.get(k) if x.get(k) not in (None, '', []) else '—') for k in self.fields(key, x)]
        return {'cells': (vals + ['—'] * len(cols))[:len(cols)], 'f': [str(x.get('id') or '%s%d' % (key, i))]}

    def row_of(self, r, where, x, own):
        """한 행으로 받는 모양: {열: 글} · {"cells"|"t"|"r"|"row": […]} · […] · id · {"id", 바꿀 열} → {'cells','f','src'}"""
        key, cols = r['key'], r['cols']
        if isinstance(x, (str, int, float)):
            x = {'id': str(x)}
        if isinstance(x, list):
            x = {'cells': x}
        if not isinstance(x, dict):
            self.add('FAIL', where, '한 행을 `%s`로 쓴다' % row_example(cols))
            return None
        base, i = {'cells': [''] * len(cols), 'f': []}, str(x.get('id') or '').strip()
        if i in own:
            base = own[i]
        elif i and not set(x) - {'id', 'f'}:
            self.add('FAIL', where, '`%s`가 model.json의 `%s` 항목이 아니다. 행을 직접 쓴다: `%s`' % (T.clip(i, 30), key, row_example(cols)))
            return None
        out = {'f': [str(y) for y in M.as_list(x.get('f'))] or base['f'], 'src': M.as_list(x.get('src'))}
        vals = next((x[k] for k in ('cells', 'r', 'row', 't') if x.get(k) not in (None, '') and k not in cols), None)
        if vals is not None and not isinstance(vals, dict):
            return dict(out, cells=[str(c.get('t', '')) if isinstance(c, dict) else '' if c is None else str(c) for c in M.as_list(vals)])
        x, names = vals or x, self.fields(key, {})
        got = list(base['cells'])
        for k, c in x.items():
            j = cols.index(k) if k in cols else names.index(k) if k in names[:len(cols)] else None
            if j is not None:
                got[j] = str(c.get('t', '')) if isinstance(c, dict) else '' if c is None else str(c)
            elif k not in ('id', 'f', 'src'):
                self.add('FAIL', where, '열 이름 `%s`가 표에 없다(열: %s)' % (k, ', '.join(cols)))
        return dict(out, cells=got)

    def table(self, r, v):
        key, cols = r['key'], r['cols']
        pool = [x for x in M.as_list(self.model.get(key)) if isinstance(x, dict)]
        auto = [self.auto_row(key, i, x, cols) for i, x in enumerate(pool, 1)]
        own = {x['f'][0]: x for x in auto}
        if isinstance(v, dict) and 'rows' in v:
            v = v['rows']
        if empty(v):
            v = auto[:r['n'] or None]
        elif isinstance(v, list) and len(v) == len(cols) and all(isinstance(x, str) and x not in self.refs and not ID_ONLY.match(x) for x in v):
            v = [v]                                        # 한 행을 그대로 쓴 것
        out, seen = [], {}
        for i, x in enumerate(M.as_list(v), 1):
            where = '%s[%d]' % (key, i)
            it = self.row_of(r, where, x, own)
            if it is None or all(not c.strip() for c in it['cells']):
                continue
            vals = it['cells']
            if len(vals) != len(cols):
                self.add('FAIL', where, '칸이 %d개다. 열은 %d개다(%s)' % (len(vals), len(cols), ', '.join(cols)))
                it['cells'] = vals = vals + [''] * (len(cols) - len(vals))
            for j, c in enumerate(vals):
                lv = T.over(T.count(c), r['chars'])
                if lv:
                    self.add(lv, '%s %s' % (where, cols[j] if j < len(cols) else j + 1), '%d자다. %d자까지다%s: %s' % (T.count(c), r['chars'], NEAR if lv == 'WARN' else '', T.clip(c, 40)))
            full = ' / '.join(vals)
            it.update(t=full, where=where)
            self.check_text(where, full, it['f'], linked=not r['free'], srcs=it['src'], item=it, conds=False)
            for f in it['f']:
                if f in self.refs and '원문에 없' not in full:
                    seen.setdefault(f, where)
            out.append(it)
        whole = ' / '.join(x['t'] for x in out)            # 조건은 표 전체에 한 번 있으면 된다
        for f, where in seen.items():
            self.keeps(where, whole, f)
        if r['n'] and len(out) > r['n']:
            self.add('FAIL', key, '%d행이다. %d행까지다' % (len(out), r['n']))
        return out

    def fields(self, key, x):
        """표에 자동으로 넣을 필드: 틀이 선언한 순서(id·src·mark와 id 목록은 뺀다)."""
        row = next((m for m in self.spec.model_rows() if m['key'] == key), None)
        names = row['fields'] if row and row['fields'] else [k for k, _ in M.prose(x)]
        return [n for n in names if n not in ('id', 'src', 'mark', 'f', 'edges', 'results', 'when', 'main', 'guess')]

    def pic(self, r, v):
        form, key = r['form'], r['key']
        src = [x for x in M.as_list(self.model.get(PIC_KEY[form])) if isinstance(x, dict)]
        if isinstance(v, dict):
            v = v.get('ids') or v.get('e') or []
        blank = empty(v)
        if blank and form in ('flow', 'beforeafter') and isinstance(self.model.get(key), list) and key != 'edges':
            v = [str(x.get('id') if isinstance(x, dict) else x) for x in self.model[key]]      # 예: codebase의 path
        auto = empty(v) or v == 'all'
        if auto:
            pool = src
            if form == 'flow':
                pool = [e for e in src if e.get('when') != 'before'] or src
                pool = [e for e in pool if e.get('main')] or pool
            elif form == 'map':
                pool = src
            if form == 'beforeafter' and not any(e.get('when') in ('before', 'after') for e in src):
                pool = []
            out = pool[:r['n'] or len(pool)]
            if r['n'] and len(pool) > r['n']:
                self.add('WARN', key, '%s가 %d개라 앞의 %d개만 그렸다. 고를 id를 칸에 쓴다' % (PIC_KEY[form], len(pool), r['n']))
            return self.drawn(key, self.short(r, out) if blank else out)
        out = []
        for x in M.as_list(v):
            i = str((x.get('id') or (M.as_list(x.get('f')) or [''])[0]) if isinstance(x, dict) else x)
            it = self.refs.get(i)
            if it is None or it not in src:
                self.add('FAIL', key, '`%s`가 model.json의 %s에 없다. 그림 칸에는 id나 `{"id":"…","t":"짧은 글"}`을 쓴다' % (T.clip(i, 30), PIC_KEY[form]))
                continue
            if isinstance(x, dict):
                ok, new = PIC_TEXT.get(form, ('t',)), {}
                for k, c in x.items():
                    k2 = ok[0] if k == 't' else k
                    if k2 in ok and c not in (None, ''):
                        new[k2] = str(c).strip()
                    elif k not in ('id', 'f', 't'):
                        self.add('WARN', key, '`%s`의 `%s`는 그림 칸에서 바꾸지 못한다(바꿀 수 있는 것: %s)' % (i, k, ', '.join(ok)))
                for c in new.values():
                    self.check_text(key, c, [i], linked=False, conds=False)
                it = dict(it, id=i, **new)
            out.append(it)
        if r['n'] and len(out) > r['n']:
            self.add('FAIL', key, '%d개다. %d개까지다' % (len(out), r['n']))
        return self.drawn(key, self.short(r, out) if blank else out)

    def short(self, r, items):
        """비운 그림 칸: eli5.json이 같은 그림의 글을 줄여 썼으면 그 글로."""
        e = next((x for x in self.spec.rows('eli5') or [] if x['key'] == r['key'] and x['form'] == r['form']), None) if self.mode in HTML_MODES else None
        mine = {str(x['id']): x for x in M.as_list(self.eli5.get(r['key'])) if isinstance(x, dict) and x.get('id')} if e else {}
        ok, out = PIC_TEXT.get(r['form'], ('t',)), []
        for x in items:
            i = M.id_of(self.refs, x)
            new = {(ok[0] if k == 't' else k): str(c).strip() for k, c in mine.get(i, {}).items() if c not in (None, '') and (k == 't' or k in ok)}
            for c in new.values():
                self.lent.add(r['key'])
                self.check_text(r['key'], c, [i], linked=False, conds=False)
            out.append(dict(x, id=i, **new) if new else x)
        return out

    def drawn(self, key, items):
        """그림 하나의 글 전체(간선 양 끝의 이름도)에서 한정어를 찾는다."""
        ends = [str((self.refs.get(str(x.get(k))) or {}).get('t') or '') for x in items for k in ('from', 'to')]
        text = ' / '.join([s for x in items for k, s in M.prose(x) if k != 'hedge'] + ends)
        lost = {}
        for y in items:
            i = M.id_of(self.refs, y)
            h = self.lost_hedge(text, self.refs[i]) if i else ''
            if h:
                lost.setdefault(h, []).append('`%s`' % i)
        for h, ids in lost.items():
            self.add('WARN', key, '%s의 한정어 "%s"가 빠졌다%s' % ('·'.join(ids), T.clip(h, 20), hedge_hint(h)))
        return items

    def kit(self, r, v):
        if empty(v):
            return None
        if isinstance(v, list) and r['n'] and len(v) > r['n']:
            self.add('FAIL', r['key'], '%d개다. %d개까지다' % (len(v), r['n']))

        def walk(x, where, f):
            if isinstance(x, str):
                if x not in self.refs and not re.match(r'^[a-z]+\d*$', x):
                    self.check_text(where, x, f, linked=False)
            elif isinstance(x, list):
                for i, y in enumerate(x, 1):
                    walk(y, '%s[%d]' % (where, i), f)
            elif isinstance(x, dict):
                g = [str(y) for y in M.as_list(x.get('f'))]
                self.known_ids(where, g)
                for k, y in x.items():
                    if k not in ('f', 'id', 'src', 'from', 'to'):
                        walk(y, '%s.%s' % (where, k), g or f)
        walk(v, r['key'], [])
        return v

    def code(self, r, items):
        out = []
        for it in items:
            s = (M.as_list(it.get('src')) or [it['t']])[0]
            res = self.source.resolve(str(s))
            if not res['ok'] or not res['lines']:
                self.add('FAIL', it['where'], res['msg'] or '`경로:줄`로 원문 줄을 가리킨다')
                continue
            if r['n'] and len(res['lines']) > r['n']:
                self.add('FAIL', it['where'], '%d줄이다. %d줄까지다' % (len(res['lines']), r['n']))
            it.update(code=res['text'], label=res['label'])
            out.append(it)
        return out

    # ----- 글 한 조각 -----
    def known_ids(self, where, ids):
        ok = []
        for i in ids:
            if i in self.refs:
                ok.append(i)
            else:
                self.add('FAIL', where, '`f`의 `%s`가 model.json에 없다' % i)
        return ok

    def check_text(self, where, text, ids, linked=True, srcs=(), item=None, conds=True):
        ids = self.known_ids(where, ids)
        if linked and not ids and not srcs:
            self.nolink.append(where)
        got = []
        for s in srcs:
            for one in M.split_src(s):
                res = self.source.resolve(one)
                got.append(res)
                if not res['ok']:
                    self.add('FAIL', where, res['msg'])
                elif res['kind'] == 'url' and not res['text'] and not ids:
                    self.add('FAIL', where, '근거가 바깥 주소뿐이다. 원문 줄이나 사실 id(`f`)를 쓴다')
                elif item is not None:
                    item.setdefault('labels', []).append(res['label'])
        facts, cites, files = self.evidence(ids)
        M.check_numbers(text, lambda forms, counted=False: bool(forms & self.model_numbers) or self.source.number_ok(forms, files or self.cited_files, counted), where, self.add)
        known = set(M.backticks(self.model_text))
        M.check_idents(text, self.source, files or self.cited_files, known, where, self.add, self.later)
        M.check_plain(text, self.source, files or self.cited_files, set(M.PLAIN.findall(self.model_text)) | known, where, self.add, self.later)
        got += cites
        if any(r['text'] for r in got):
            self.near(where, text, facts, got, files or self.cited_files)
        for lv, v, _ in T.secrets(text):
            if lv == '확실':
                self.add('FAIL', where, '비밀 값(%s)이 있다. `***`로 바꾼다' % v)
        if T.HOME.search(text):
            self.add('FAIL', where, '홈 폴더 경로가 있다. 상대 경로로 바꾼다')
        if '{{' in re.sub(r'`[^`]*`', '', text):
            self.add('FAIL', where, '채우지 않은 `{{`가 남았다')
        if item is not None:
            self.pieces.append((where, text, ids))
        for i in ids if conds and '원문에 없' not in text else []:
            self.keeps(where, text, i)
        cited = ' '.join(s for x in facts for _, s in M.prose(x)) + ' ' + ' '.join(r['text'] for r in cites)
        if not ids and not srcs:                                              # 근거를 걸지 않은 글은 원문 전체에서 찾는다
            cited = self.source.text() or self.model_text
        for _, rx, ok in T.ABSOLUTE:
            hit = rx.search(text)
            if hit and not ok.search(cited):
                self.add('WARN', where, '`%s`가 근거에 없다. 원문에 같은 말이 없으면 지우거나 좁힌다: %s' % (hit.group(0), T.clip(text, 40)))

    def evidence(self, ids):
        """id들 → (사실, 근거 결과, 근거 파일)"""
        facts = [self.refs[i] for i in ids if i in self.refs]
        got = [self.resolved[p] for x in facts for s in M.as_list(x.get('src')) for p in M.split_src(s) if p in self.resolved]
        return facts, got, sorted({r['file'] for r in got if r.get('file')})

    def near(self, where, text, facts, got, files):
        """숫자와 이름을 연결한 사실과 그 근거 구간에서 먼저 찾는다."""
        said = '\n'.join(s for x in facts for _, s in M.prose(x)) + '\n'

        def find(test):
            return self.source.where(test, files) or ('다른 사실' if test(self.model_text) else '')
        M.check_near(text, said + '\n'.join(r['text'] for r in got), lambda forms: find(lambda ln: T.says_number(ln, forms)), self.source._extra_numbers, where, self.add)
        body = (said + '\n'.join(self.source.around(r) for r in got)).replace('_', '').lower()
        for tok in M.backticks(text):
            miss = [w for w in re.findall(r'[A-Za-z_][A-Za-z0-9_]{3,}', tok) if re.search(r'[a-z]_[a-z]|[a-z][A-Z]', w) and w.replace('_', '').lower() not in body]
            at = find(lambda ln: miss[0] in ln) if miss else ''
            if at:
                self.add('WARN', where, '근거 구간에 없음: 이름 `%s` — %s에는 있다' % (miss[0], at))

    def keeps(self, where, text, fid):
        """사실의 조건(if)·한정어(hedge)가 이 칸에도 남았나."""
        x = self.refs[fid]
        cond = str(x.get('if') or '')
        if cond and not (x.get('then') and x in M.as_list(self.model.get('flips'))):
            terms = [(str(t['w']), [str(o) for o in M.as_list(t.get('o'))]) for t in M.as_list(self.model.get('terms')) if isinstance(t, dict) and t.get('w')]
            alias = [x for w, os_ in terms for x in ([w] if any(o.lower() in cond.lower() for o in os_) else os_ if w in cond else [])]
            words = T.stems(' '.join([cond] + alias))
            if words and not any(s in text.lower() for s in words) and not T.same_word(cond, text) and not re.search(r'\((?:조건부|예외 있음|일부|기본[^)]*)\)|보통|기본', text):
                self.add('WARN', where, '`%s`의 조건 "%s"이 빠졌다(찾은 낱말: %s). 조건을 넣거나 주장을 좁힌다' % (fid, T.clip(cond, 40), '·'.join(dict.fromkeys(words[:5]))))
        hedge = self.lost_hedge(text, x)
        if hedge:
            self.add('WARN', where, '`%s`의 한정어 "%s"가 빠졌다%s' % (fid, T.clip(hedge, 20), hedge_hint(hedge)))

    def lost_hedge(self, text, x):
        """사라진 한정어. 글자 그대로, 같은 갈래의 말(T.HEDGE_KEEP), 같은 뜻의 말, 갈래가 없으면 핵심 낱말로 찾는다."""
        hedge = ' '.join(str(h) for h in M.as_list(x.get('hedge')))
        if not hedge or re.search(r'[?？]\s*$', text) or hedge.lower() in text.lower() or T.same_word(hedge, text):
            return ''
        keep = [T.HEDGE_KEEP.get(k) or M.KEEP_EXTRA.get(k) for k in T.cond_kinds(hedge)]
        if any(r and r.search(text) for r in keep) or not any(keep) and any(s in text.lower() for s in T.stems(hedge) if s not in ('있다', '없다', '한다', '하는', '된다', '되는', '것이')):
            return ''
        return hedge

    def repeats(self):
        for i, (w1, t1, _) in enumerate(self.pieces):
            for w2, t2, _ in self.pieces[i + 1:]:
                if w1.split('[')[0] == w2.split('[')[0] and w1 == w2:
                    continue
                if T.similar(t1, t2) >= 0.75:
                    self.add('WARN', w2, '`%s`와 같은 말이다. 하나를 뺀다: %s' % (w1, T.clip(t2, 40)))


def hedge_hint(hedge):
    say = [T.HEDGE_SAY[k] for k in T.cond_kinds(hedge) if k in T.HEDGE_SAY]
    return '(단정으로 바뀌었나 본다. `%s` 가운데 하나가 있으면 된다)' % '·'.join(say) if say else '(단정으로 바뀌었나 본다)'


# ----- 결과에 붙이는 것 -----
def mark_suffix(text, items):
    ms = []
    for x in items:
        for k in M.marks(x):
            if k not in ms and k not in text:
                ms.append(k)
    return ' (%s)' % ', '.join(ms) if ms else ''


def src_labels(x, resolved):
    out = []
    for s in M.as_list(x.get('src')):
        for p in M.split_src(s):
            out.append(resolved.get(p, {}).get('label', p))
    return out


def missing_line(parts, blank):
    """`빠진 디테일` 줄의 글. 빈 칸 이름을 붙인다(이미 적은 이름은 빼고)."""
    said = '. '.join(parts)
    left = [b for b in dict.fromkeys(blank) if not re.search(r'(?:^|[\s,·.])' + re.escape(b) + r'(?=[\s,(·.]|$)', said)]
    return '. '.join(parts + (['빈 칸: ' + ', '.join(left)] if left else [])) or '없음'


def context(chk, type_, size, pack, source_name='raw'):
    """렌더러에 넘기는 ctx (intolib/__init__.py의 계약)."""
    m, refs = chk.model, chk.refs
    said = [' · '.join(str(y).strip() for y in M.as_list(x) if str(y).strip()).rstrip('.') for x in (chk.raw.get('missing'), m.get('missing'))]
    missing = [x for x in said if x][:1]                  # 모드 json의 missing이 model의 것을 대신한다
    src = str(m.get('source') or '').strip()
    url = pack.get('url') or ''
    if url and url not in src:
        src += ' · ' + url
    src = T.HOME.sub('~', src)
    steps = M.as_list(m.get('steps'))
    order_note = '' if not steps else '순서: 없음' if m.get('order') == 'none' else '순서: 원문에 없음' if m.get('order') in (None, '') else ''

    def cite(ids, limit=6, extra=()):
        labels = []
        for i in ids:
            if i in refs:
                labels += src_labels(refs[i], chk.resolved)
        labels += list(extra)
        labels = [source_name + ':' + lb[4:] if lb.startswith('raw:') else lb for lb in labels]
        return format_cites(labels, limit)
    return {'type': type_, 'type_name': chk.spec.name, 'pic': chk.spec.pic, 'questions': chk.spec.questions, 'mode': chk.mode, 'size': size,
            'title': str(m.get('title') or '').strip(), 'scope': str(m.get('scope') or '').strip(), 'notice': '' if pack.get('public') else NOTICE,
            'model': m, 'rows': chk.rows, 'cells': chk.cells, 'raw_cells': chk.raw, 'refs': refs, 'cite': cite, 'resolved': chk.resolved,
            'missing': missing_line(missing, chk.blank), 'source': src, 'order_note': order_note, 'slots': SLOTS, 'html': chk.mode in HTML_MODES}


def used(ctx):
    """[(칸, 쓴 글자)] — 머리 줄과 칸마다, 결과에 실제로 나오는 글."""
    from . import htmlmodes, textmodes
    if not ctx['html']:
        return textmodes.used(ctx)
    return [('머리', T.count(ctx['title']))] + [(k, sum(T.count(x) for x in xs)) for k, xs in htmlmodes.drawn(ctx)]


def total_cells(ctx):
    return sum(n for _, n in used(ctx))


def pic_parts(ctx):
    """글자가 넘쳤을 때 글로 그린 그림이 무엇으로 찼나 (칸마다 한 줄)"""
    from . import textmodes
    out, size = [], dict(used(ctx))
    for r in ctx['rows']:
        v = ctx['cells'].get(r['key'])
        if v and r['form'] in textmodes.ARROWS and not ctx['html'] and size.get(r['key']):
            t, c = [sum(T.count(f(e)) for e in v) for f in (lambda e: e.get('t'), textmodes.edge_cond)]
            out.append('그림 `%s` %d자 = 간선 글 %d · 뒤에 붙은 조건(if) %d · 노드 이름과 괄호 %d. 간선을 빼거나 `{"id":"…","t":"조건까지 넣은 짧은 글"}`로 줄인다(글에 있는 조건은 다시 붙지 않는다)' % (r['key'], size[r['key']], t, c, size[r['key']] - t - c))
    return out


def used_line(ctx, lim):
    """`글자 412/450 · 남음 38 — 머리 18 · one 52 · …`"""
    ls = used(ctx)
    n = sum(c for _, c in ls)
    return '글자 {:,}'.format(n) + ('/{:,} · 남음 {:,}'.format(lim, lim - n) if lim else '') + ' — ' + ' · '.join('%s %d' % x for x in ls)

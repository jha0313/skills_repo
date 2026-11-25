# -*- coding: utf-8 -*-
"""html(보기) · interactive(해 보기) 렌더: 칸과 모델 → 화면 데이터 하나 → kit을 넣은 단일 HTML.

화면 데이터(#into)의 모양
  mode, typeName, name, title, one, notice, hint, layout(wide|split), why[], figs[], tables[], cards[], predicts[], learn[], missing, source, order
  글 하나는 {t, src?, mark?, ids?}. src는 '근거' 글, ids는 그림에서 켤 것의 id.
"""
import json
import os
import re

from . import ASSETS, UserError
from . import model as M
from . import text as T
from . import textmodes as X
from .formats import PIC_FORMS

MODES = ('html', 'interactive', 'slides')
SPLIT = ('design-doc', 'paper-concept', 'general')            # 왼쪽 그림, 오른쪽 글
TRY_PART = {'beforeafter': 'cases', 'map': 'flips', 'flow': 'flips', 'anatomy': 'whatif', 'lanes': 'triggers'}
CARD = ('list', 'steps', 'line', 'quote', 'number', 'code')
LATE = ('cause', 'limits')                                    # 해 보기에서 그림을 연 뒤에 읽을 칸
MAX_NODES = 9


# ---------- 작은 도구 ----------
def _pick(x, *keys):
    return {k: x[k] for k in keys if x.get(k) not in (None, '', [])}


def _ids_of(ctx, f):
    """근거 id → 그림에서 켤 id (간선·노드·주장·장면과, 항목이 가리키는 간선)."""
    out = []
    for i in f:
        x = ctx['refs'].get(i) or {}
        out += [i] + [str(e) for e in M.as_list(x.get('edges'))]
    return list(dict.fromkeys(out))


def _item(ctx, it):
    f = it.get('f') or []
    d = {'t': it['t']}
    src = ctx['cite'](f, 3, it.get('labels') or ())
    if src:
        d['src'] = src
    ids = _ids_of(ctx, f)
    if ids:
        d['ids'] = ids
    marks = [k for i in f if i in ctx['refs'] for k in M.marks(ctx['refs'][i]) if k not in it['t']]
    if marks:
        d['mark'] = ', '.join(dict.fromkeys(marks))
    if it.get('code'):
        d['code'] = it['code']
    return d


def _thing(ctx, x, *keys):
    d = _pick(x, *keys)
    src = _labels(ctx, x)
    if src:
        d['src'] = src
    ms = M.marks(x)
    if ms and not d.get('guess'):
        d['mark'] = ', '.join(ms)
    return d


def _labels(ctx, x):
    out = []
    for s in M.as_list(x.get('src')):
        for p in M.split_src(s):
            out.append(ctx['resolved'].get(p, {}).get('label', p))
    return ctx['cite']([], 3, out)


def _place(ctx, x):
    """글 묶음의 자리 'n/N' (있을 때만 오른쪽에 보인다)"""
    m = re.search(r'\s*\((\d[\d ,·–~-]*/\s*\d+)\)\s*$', str(x.get('t') or ''))
    if m:
        return {'pos': m.group(1), 't': x['t'][:m.start()]}
    m = re.search(r'\d[\d ,·–~-]*/\s*\d+', _labels(ctx, x))
    return {'pos': m.group(0)} if m else {}


def _ranges(x):
    out = []
    for s in M.as_list(x.get('src')) + M.as_list(x.get('range')):
        for m in re.finditer(r'([^\s;·,]*?):?(?<![\d.])(\d+)(?:\s*[-–~]\s*(\d+))?(?=$|[\s;·,])', str(s)):
            out.append((m.group(1).rstrip(':'), int(m.group(2)), int(m.group(3) or m.group(2))))
    return out


def _overlap(a, b):
    """근거 줄이 겹치는 정도 (포함 비율, 자카드) 중 가장 큰 것"""
    best = (0.0, 0.0)
    for fa, s, e in _ranges(a):
        for fb, s2, e2 in _ranges(b):
            n = min(e, e2) - max(s, s2) + 1
            if n > 0 and (not fa or not fb or fa == fb):
                best = max(best, (n / float(min(e - s, e2 - s2) + 1), n / float(max(e, e2) - min(s, s2) + 1)), key=sum)
    return best


def _words(t):
    return re.findall(r'[가-힣]{2,}|[A-Za-z_]{2,}|\d+', str(t))


# ---------- 그래프 ----------
def _graph(ctx, edges):
    used = []
    for e in edges:
        used += [str(e.get('from')), str(e.get('to'))]
    byid = {str(n.get('id')): n for n in M.as_list(ctx['model'].get('nodes')) if isinstance(n, dict)}
    ns = []
    for i in dict.fromkeys(used):
        n = byid.get(i, {'id': i, 't': i})
        ns.append(_thing(ctx, n, 'id', 't', 's', 'd', 'key'))
    es = [_thing(ctx, dict(e, c=X.edge_cond(e)), 'id', 'from', 'to', 't', 'c', 'when', 'main', 'guess', 'both', 'if') for e in edges]
    if ctx['type'] in ('pr', 'local-file') and not any(n.get('key') for n in ns):
        starts = {e['from'] for e in es}
        for n in ns:
            if n['id'] not in starts:
                n['key'] = True
    return ns, es


def _edges(ctx):
    return [e for e in M.as_list(ctx['model'].get('edges')) if isinstance(e, dict)]


def _fig(ctx, row, got):
    """그림 칸 하나 → 부품 데이터"""
    m, form, key = ctx['model'], row['form'], row['key']
    d = {'part': form, 'key': key, 'aria': row['label']}
    if form in ('flow', 'beforeafter'):
        d['nodes'], d['edges'] = _graph(ctx, got)
    elif form == 'map':
        zones = [_thing(ctx, z, 'id', 't', 'does', 'grade') for z in got]
        zid = {str(z.get('id')) for z in got}
        path = [str(e['id']) for e in M.as_list(ctx['cells'].get('path'))]
        es = [e for e in _edges(ctx) if str(e['id']) in path]
        es += [e for e in _edges(ctx) if e not in es and str(e.get('from')) in zid and str(e.get('to')) in zid]
        es = es[:max(12, len(path))]
        d['nodes'], d['edges'] = _graph(ctx, es)
        d.update(zones=zones, path=path)
    elif form == 'options':
        ids = {str(o.get('id')) for o in got}
        d['options'] = [_thing(ctx, o, 'id', 't', 'd', 'chosen') for o in got]
        d['criteria'] = [_pick(c, 'id', 't') for c in M.as_list(m.get('criteria'))]
        d['cells'] = [_thing(ctx, c, 'o', 'c', 't', 'sign') for c in M.as_list(m.get('cells')) if str(c.get('o')) in ids]
        d['open'] = [_thing(ctx, x, 't') for x in M.as_list(m.get('open'))][:2]
        d['title'] = row['label']
    elif form == 'chart':
        ids = {str(x.get('id')) for x in got}
        d['results'] = [_thing(ctx, x, 'id', 'group', 'label', 'value', 'unit', 'base', 'lower', 'cond', 'ref', 'flat') for x in got]
    elif form == 'timeline':
        d['chapters'] = [_thing(ctx, c, 'id', 'at', 'to', 't', 'claim', 'kind') for c in got]
        end = M.as_list(m.get('chapters'))
        if end and end[-1].get('to'):
            d['chapters'][-1].setdefault('to', end[-1]['to'])
    elif form == 'ladder':
        d['claims'] = [dict(_thing(ctx, c, 'id', 't', 'ev', 'quote'), **_place(ctx, c)) for c in got]
    elif form == 'positions':
        d['positions'] = [_thing(ctx, p, 'id', 't', 'n', 'why', 'quote', 'ev', 'cost') for p in got]
        d['agree'] = [_thing(ctx, x, 't') for x in M.as_list(m.get('agree'))][:2]
        d['clashes'] = [_thing(ctx, x, 'a', 'b', 'on') for x in M.as_list(m.get('clashes'))]
    elif form == 'anatomy':
        d['parts'] = [_thing(ctx, p, 'id', 'range', 't', 'does') for p in got]
        for i, p in enumerate(d['parts'], 1):
            p.setdefault('id', 'parts%d' % i)
    elif form == 'lanes':
        d['steps'] = [_thing(ctx, dict(s, lane=s.get('lane') or s.get('who')), 'id', 'lane', 'do', 'out', 'if') for s in got]
        for i, s in enumerate(d['steps'], 1):
            s.setdefault('id', 'steps%d' % i)
            s.setdefault('lane', '')
        d['lanes'] = [x for x in map(str, M.as_list(m.get('lanes'))) if any(s['lane'] == x for s in d['steps'])]
        d['order'] = m.get('order') or ''
    return d


SHOWN = {'options': (('options', 't'), ('criteria', 't'), ('cells', 't'), ('open', 't')), 'timeline': (('chapters', 'kind', 'at', 't', 'claim'),),
         'ladder': (('claims', 'ev', 't', 'pos'),), 'positions': (('positions', 't', 'ev', 'why', 'cost'), ('agree', 't')), 'anatomy': (('parts', 'range', 't', 'does'),),
         'lanes': (('steps', 'do', 'out'),), 'chart': (('results', 'label', 'group', 'value', 'unit', 'cond'),)}


def _shown(f):
    """그림 하나가 처음 화면에 그리는 글 (눌러야 나오는 것은 뺀다)"""
    g = lambda xs, *ks: [str(x[k]) for x in xs for k in ks if x.get(k) not in (None, '')]
    if f['part'] in ('flow', 'map', 'beforeafter'):               # 전과 후의 같은 상자는 같은 자리라 한 번만 센다
        does, on = {z['id']: z.get('does') for z in f.get('zones', [])}, {n['id'] for n in f['nodes']}
        return g([dict(n, s=n.get('s') or does.get(n['id'])) for n in f['nodes']], 't', 's') + g(f['edges'], 't', 'c') + g([z for z in f.get('zones', []) if z['id'] not in on], 't', 'does')
    return list(dict.fromkeys(x['lane'] for x in f.get('steps', []))) + [s for k in SHOWN.get(f['part'], ()) for s in g(f.get(k[0], []), *k[1:])]


def drawn(ctx):
    """[(칸, 그려지는 글 목록)]"""
    out, cells, rows = [], ctx['cells'], ctx['rows']
    has_map = any(r['form'] == 'map' and cells.get(r['key']) for r in rows)
    for r in rows:
        got = cells.get(r['key'])
        if not got:
            continue
        if r['form'] in PIC_FORMS:
            ls = [] if has_map and r['key'] == 'path' and r['form'] == 'flow' else _shown(_fig(ctx, r, got))
        elif r['form'] == 'kit':
            ls = _strings(got)
        else:
            ls = [s for it in got for s in (it.get('cells') or [it.get('code') or it['t']])]
        out.append((r['key'], ls))
    return out


def _strings(v):
    if isinstance(v, dict):
        return [s for k, x in v.items() if k not in ('f', 'src', 'id', 'from', 'to') for s in _strings(x)]
    return [s for x in v for s in _strings(x)] if isinstance(v, list) else [v] if isinstance(v, str) else []


# ---------- 표 ----------
def _table(ctx, row, got):
    rows = []
    for it in got:
        d = _item(ctx, it)
        rows.append(dict({k: v for k, v in d.items() if k != 't'}, cells=it['cells']))
    t = {'label': row['label'], 'cols': row['cols'], 'rows': rows, 'key': row['key']}
    if row['cols'][-2:] == ['전', '후']:
        t['diff'] = 1
    return t


def _linked(ctx, r):
    """표의 한 행이 그림에서 켤 간선과 부분. 간선은 적힌 것 → 이름이 나온 끝 상자까지의 길 → 근거 줄이 겹치는 것."""
    ids, es = r.get('ids') or [], _edges(ctx)
    own = [ctx['refs'][i] for i in ids if i in ctx['refs']]
    edges = [i for i in ids if any(str(e.get('id')) == i for e in es)]
    if not edges:
        text = ' '.join(r['cells'])
        names = {str(n.get('id')): _words(n.get('t')) for n in M.as_list(ctx['model'].get('nodes')) if isinstance(n, dict)}
        starts = {str(e.get('from')) for e in es}
        hit = {str(e['to']) for e in es if str(e.get('to')) not in starts and names.get(str(e['to'])) and all(w in text for w in names[str(e['to'])])}
        while hit:
            more = {str(e.get('from')) for e in es if str(e.get('to')) in hit} - hit
            new = [str(e['id']) for e in es if str(e.get('to')) in hit and str(e['id']) not in edges]
            edges += new
            if not more:
                break
            hit |= more
    if not edges:
        k = 1 if ctx['type'] == 'pr' else 0
        edges = [str(e['id']) for e in es if any(x.get('src') and 'from' not in x and _overlap(x, e)[k] >= 0.5 for x in own)]
    parts = [str(p.get('id') or 'parts%d' % i) for i, p in enumerate(M.as_list(ctx['model'].get('parts')), 1) if isinstance(p, dict) and any(_overlap(x, p)[0] >= 0.5 for x in own)]
    return edges, parts


def _buttons(ctx, t, part):
    """표 → 그림의 단추 (첫 열 = 단추)"""
    out = []
    for i, r in enumerate(t['rows']):
        c = r['cells']
        edges, parts = _linked(ctx, r)
        x = {k: r[k] for k in ('src', 'mark') if r.get(k)}
        if part == 'cases':
            x.update(input=c[0], before=c[1], after=c[-1], same=bool(re.match(r'^(같음|그대로)', c[-1])) or c[1] == c[-1])
        elif part == 'triggers':
            own = [ctx['refs'][j] for j in r.get('ids', []) if j in ctx['refs']]
            x.update(say=c[0], route=c[-1], steps=[str(s) for o in own for s in M.as_list(o.get('steps'))])
        else:
            x.update({'if': c[0], 'then': ' — '.join(c[1:])})
            if parts:
                x['part'] = parts
        if edges:
            x['edges'] = edges
        out.append(x)
    return out


def _together(rows):
    """조건(첫 열)이 같은 행을 한 줄로. 결과가 여럿이면 함께 적는다."""
    by = {}
    for r in rows:
        by.setdefault(re.sub(r'\s', '', T.visible(r['cells'][0])), []).append(r)
    out = []
    for g in by.values():
        if len(g) == 1:
            out.append(g[0])
            continue
        said = lambda r, c: c + (' (%s)' % r['mark'] if r.get('mark') and c == r['cells'][-1] and r['mark'] not in c else '')
        x = {'cells': [g[0]['cells'][0]] + [' · '.join(dict.fromkeys(said(r, r['cells'][k]) for r in g if r['cells'][k])) for k in range(1, len(g[0]['cells']))]}
        src = ' · '.join(dict.fromkeys(str(r['src']) for r in g if r.get('src')))
        ids = list(dict.fromkeys(str(i) for r in g for i in r.get('ids') or []))
        out.append(dict(x, **{k: v for k, v in (('src', src), ('ids', ids)) if v}))
    return out


def _auto(tables):
    """에이전트가 문항을 안 썼을 때: 표의 조건을 먼저 생각하고 여는 카드. 다른 행의 결과는 오답이라는 근거가 없어 보기로 쓰지 않는다."""
    out = [dict({'q': r['cells'][0] + ' → 어떻게 되나?', 'answer': r['cells'][-1]}, **{k: r[k] for k in ('src', 'mark') if r.get(k)})
           for t in tables for r in t['rows'] if r['cells'][-1] and not r['cells'][-1].startswith('—')]
    return out[::max(1, len(out) // 3)][:3]


# ---------- 화면 ----------
def build(mode, ctx):
    """ctx → 화면 데이터"""
    tr, cells = mode == 'interactive', ctx['cells']
    D = {'mode': mode, 'type': ctx['type'], 'typeName': ctx['type_name'], 'title': ctx['title'], 'name': ctx['title'], 'notice': ctx['notice'],
         'one': '', 'why': [], 'figs': [], 'tables': [], 'cards': [], 'lead': [], 'predicts': [], 'learn': [], 'layout': 'split' if ctx['type'] in SPLIT and not tr else 'wide'}
    tables, after = [], []
    rows_first = ctx['type'] == 'community-post' and not tr and not cells.get('positions') and cells.get('cases')
    if tr:
        D['hint'] = _hint(ctx)
    for r in ctx['rows']:
        got = cells.get(r['key'])
        if not got:
            continue
        form, slot = r['form'], r['slot']
        if slot == 'one' and not D['one']:                                     # 첫 줄도 글 · 표시 · 근거를 함께
            it = _item(ctx, got[0]) if isinstance(got, list) else {'t': str(got)}
            D['one'], D['head'] = it['t'], {k: it[k] for k in ('src', 'mark') if it.get(k)}
            continue
        if r['key'] == 'arms' and not cells.get('results'):                    # 개념이면 견준 것이 아니라 이루는 것
            r = dict(r, label='구성 요소')
        if rows_first and r['key'] == 'cases':                                 # 입장을 줄로 쓴 글: 그 줄이 주 그림
            D['figs'].append({'part': 'list', 'key': 'cases', 'aria': '입장', 'title': '입장 — 무엇을 하고 무엇을 치르나', 'items': [_item(ctx, it) for it in got]})
            continue
        if form == 'kit' or r['form'].startswith('kit:'):
            D['figs'].append(dict(got if isinstance(got, dict) else {'items': got}, part=(r['cols'] or [r['form'].split(':')[-1]])[0], key=r['key'], aria=r['label']))
        elif form == 'map':
            D['figs'].append(_fig(ctx, r, got))
        elif form == 'flow' and r['key'] == 'path' and any(f['part'] == 'map' for f in D['figs']):
            continue
        elif form in PIC_FORMS:
            D['figs'].append(_fig(ctx, r, got))
        elif form == 'table':
            tables.append(dict(_table(ctx, r, got), slot=slot))
        elif form == 'qa':
            for it in got:
                D['predicts'].append(dict({k: v for k, v in _item(ctx, it).items() if k in ('src', 'mark')}, q=it['q'], answer=it['a'], slot=slot, label=r['label']))
        elif slot == 'why':
            D['why'] += [_item(ctx, it) for it in got]
        elif slot == 'pic' and form == 'list' and not rows_first and not any(x['form'] in PIC_FORMS and cells.get(x['key']) for x in ctx['rows']):
            D['figs'].append({'part': 'list', 'key': r['key'], 'aria': r['label'], 'items': [_item(ctx, it) for it in got]})
        elif slot == 'pic' and form == 'line':                                  # 그림 위 한 줄(상황)
            D['lead'] += [dict(_item(ctx, it), label=r['label']) for it in got]
        elif form in CARD:
            card = {'label': r['label'], 'slot': slot, 'kind': form, 'items': [_item(ctx, it) for it in got]}
            if tr and (slot == 'catch' or r['key'] in LATE):
                after += [dict(x, label=r['label'] if not i else '') for i, x in enumerate(card['items'])]
            else:
                D['cards'].append(card)
        else:
            continue
    if any(f['part'] == 'map' for f in D['figs']) is False and cells.get('path') and not any(f['key'] == 'path' for f in D['figs']):
        r = next(x for x in ctx['rows'] if x['key'] == 'path')
        D['figs'].append(_fig(ctx, r, cells['path']))
    _flow_claims(ctx, D)
    if tr:
        _try(ctx, D, tables, after)
    else:
        D['tables'] = tables
    for k, v in (('missing', ctx['missing']), ('source', ctx['source']), ('order', ctx['order_note'])):
        if v and not (k == 'missing' and v == '없음'):
            D[k] = v
    return {k: v for k, v in D.items() if v not in (None, '', [], {})}


def _flow_claims(ctx, D):
    """막대와 흐름이 함께 있으면 흐름은 작게(개념은 흐름만)."""
    parts = [f['part'] for f in D['figs']]
    if len(parts) > 1 and 'flow' in parts and parts[0] != 'flow':
        for f in D['figs']:
            if f['part'] == 'flow':
                f['fsMax'] = 16


def _try(ctx, D, tables, after):
    tables = [dict(t, rows=_together(t['rows'])) for t in tables]
    if not D['predicts']:
        D['predicts'] = _auto(tables)
    used = []
    for t in tables:
        f = next((f for f in D['figs'] if f['part'] in TRY_PART and f['part'] not in used and (TRY_PART[f['part']] == t['key'] or TRY_PART[f['part']] == 'flips')), None)
        if t['key'] == 'decisions' or f is None:
            D['figs'].append({'part': 'toggle', 'key': t['key'], 'aria': t['label'], 'title': t['label'],
                              'items': [dict({k: r[k] for k in ('src', 'mark', 'ids') if r.get(k)}, **{'if': r['cells'][0], 'then': ' — '.join(c for c in r['cells'][1:] if c)}) for r in t['rows']]})
            continue
        part = TRY_PART[f['part']]
        xs = _buttons(ctx, t, part)
        if f['part'] == 'map':                                                 # 간선이 있는 조건만 단추
            rest = [x for x in xs if not x.get('edges')]
            xs = [x for x in xs if x.get('edges')]
            if rest:
                D['figs'].append({'part': 'toggle', 'key': t['key'] + 'x', 'title': t['label'], 'items': [_pick(x, 'if', 'then', 'src') for x in rest]})
        f[part] = xs
        used.append(f['part'])
    D['learn'] = after


def _hint(ctx):
    from . import formats
    try:
        note = formats.load(ctx['type']).note('interactive')
    except (UserError, OSError):
        return ''
    m = re.search(r'눌러서 아는 것\s*=\s*["“]?(.+?)["”]?(?:\.\s|\.$|$)', note)
    return m.group(1).strip().rstrip('."”') if m else ''


# ---------- 넘침 추정 (그리기 전에 어림으로) ----------
def _px(t, size):
    return sum(0.88 if ord(c) > 0x2E80 else 0.28 if c in " .,:;'|!()·" else 0.54 for c in str(t)) * size


def _lines(t, w, size):
    """(폭, 줄 수): 낱말은 가르지 않는다"""
    words = [_px(x, size) for x in str(t).replace('`', '').split()] or [0]
    w = max(w, max(words))
    n, at = 1, 0
    for x in words:
        if at and at + size * 0.28 + x > w:
            n, at = n + 1, 0
        at += x + (size * 0.28 if at else 0)
    return (min(w, _px(t, size)), n)


def _tiers(f):
    """간선 → 노드의 층 (되돌아오는 선은 뺀다)"""
    out, rank = {}, {}
    fwd = []

    def reach(a, b, seen):
        return a == b or any(x not in seen and (seen.add(x) or reach(x, b, seen)) for x in out.get(a, []))
    for e in sorted(f['edges'], key=lambda e: 0 if e.get('main') else 1):
        if e['from'] != e['to'] and not reach(e['to'], e['from'], {e['to']}):
            out.setdefault(e['from'], []).append(e['to'])
            fwd.append(e)
    for _ in f['nodes']:
        for e in fwd:
            rank[e['to']] = max(rank.get(e['to'], 0), rank.get(e['from'], 0) + 1)
    return rank, fwd


def _fits(f, W, H):
    """가장 작은 글자(13px)로 그려도 되는 배치가 하나라도 있나"""
    rank, fwd = _tiers(f)
    deep = max(rank.values()) if rank else 0
    back = any(e not in fwd and rank.get(e['from'], 0) - rank.get(e['to'], 0) > 1 for e in f['edges'])
    for nw, lw in ((119, 101), (100, 84), (81, 68), (68, 58)):
        nodes, labs = [[] for _ in range(deep + 1)], [[] for _ in range(deep + 1)]
        for n in f['nodes']:
            w, k = _lines(n['t'], nw - 20, 13)
            k2 = _lines(n['s'], nw - 20, 13)[1] if n.get('s') else 0
            nodes[rank.get(n['id'], 0)].append((w + 22, max(34, (k + k2) * 17 + 12)))
        for e in f['edges']:
            a, b = sorted((rank.get(e['from'], 0), rank.get(e['to'], 0)))
            w, k = _lines(e.get('t', ''), lw, 12.5)
            w2, k2 = _lines(e['c'], lw, 12) if e.get('c') else (0, 0)
            labs[(a + b - 1) // 2 if b > a + 1 else a].append((max(w, w2) + 14, (k + k2) * 16 + 14))

        def lr(a, b):
            ws = [max(x[0] for x in nodes[i]) if nodes[i] else 0 for i in range(a, b + 1)] + [max([40] + [x[0] for x in labs[i]]) + 22 for i in range(a, b)]
            hs = [sum(x[1] + 12 for x in nodes[i]) for i in range(a, b + 1)] + [sum(x[1] for x in labs[i]) for i in range(a, b)]
            return sum(ws), max(hs)
        tw = max([sum(x[0] + 18 for x in nodes[i]) for i in range(deep + 1)] + [sum(x[0] for x in labs[i]) for i in range(deep)])
        th = sum(max([0] + [x[1] for x in nodes[i]]) for i in range(deep + 1)) + sum(max([22] + [x[1] for x in labs[i]]) + 26 for i in range(deep))
        ways = [lr(0, deep), (tw, th)]
        if deep >= 3 and not back:
            m = deep // 2
            (w1, h1), (w2, h2) = lr(0, m), lr(m + 1, deep)
            ways.append((max(w1, w2) + 24, h1 + h2 + 28 + max([0] + [x[1] for x in labs[m]])))
        if any(w <= W and h <= H for w, h in ways):
            return True
    return False


def _room(D, f):
    """그림 칸의 (폭, 높이) 어림. 1280×800에서 머리·바닥글을 빼고, 함께 놓인 표만큼 뺀다"""
    W, H = (744, 595) if D.get('layout') == 'split' else (1228, 400)
    for o in D['figs']:
        if o is f or o['part'] in ('toggle', 'flow'):
            continue
        if o['part'] != 'options':
            H -= 240
            continue
        col = 744 / (len(o['options']) + 1.0) - 44
        H -= 78 + (30 if o.get('open') else 0)
        for c in o['criteria']:
            H -= 11 + 19 * max([_lines(x['t'], col, 13.5)[1] for x in o['cells'] if x.get('c') == c['id']] + [_lines(c['t'], col, 13.5)[1]])
    return W, H


# ---------- 검사 ----------
def check(mode, ctx):
    """CORE의 칸 검사 뒤에 그림만 본다."""
    if mode == 'slides':
        return []
    out, D = [], build(mode, ctx)
    figs = D.get('figs', [])
    if not D.get('one'):
        out.append(('FAIL', 'one', '제목 칸이 비었다'))
    if not figs:
        out.append(('FAIL' if mode == 'interactive' and not D.get('predicts') else 'WARN', 'pic', '그림이 없다. 간선이나 유형별 목록을 model.json에 쓴다'))
    for f in figs:
        n = len(f.get('nodes', []))
        if n > MAX_NODES:
            out.append(('WARN', f['key'], '상자가 %d개다. %d개까지가 읽기 좋다(간선 id를 골라 쓴다)' % (n, MAX_NODES)))
        for e in f.get('edges', []):
            if not e.get('t'):
                out.append(('WARN', f['key'], '간선 %s에 글이 없다' % e.get('id')))
            elif T.count(e['t']) > 34:
                out.append(('WARN', f['key'], '간선 %s의 글이 %d자다. 34자까지가 읽기 좋다' % (e.get('id'), T.count(e['t']))))
        if mode == 'html' and f['part'] == 'flow' and f.get('edges') and not _fits(f, *_room(D, f)):
            out.append(('WARN', f['key'], '그림이 한 화면(1280×800)에 다 안 들 것 같다(상자 %d · 선 %d). 선의 글을 줄이거나 id를 골라 쓴다' % (n, len(f['edges']))))
    if mode == 'interactive' and figs and not any(f.get(k) for f in figs for k in ('cases', 'flips', 'triggers', 'whatif', 'chapters', 'claims', 'positions', 'criteria', 'results', 'steps', 'parts', 'path', 'scenarios')) and not D.get('predicts') and not any(f['part'] == 'toggle' for f in figs):
        out.append(('WARN', '', '누를 것이 상자뿐이다. 조건 표나 먼저 답하기를 채운다'))
    return out


# ---------- 파일 ----------
def _asset(ctx, name):
    with open(os.path.join(ctx.get('assets') or ASSETS, name), encoding='utf-8') as f:
        return f.read()


def page(mode, D, assets=None):
    """화면 데이터 → 단일 HTML"""
    ctx = {'assets': assets}
    s = _asset(ctx, 'interactive.html' if mode == 'interactive' else 'page.html')
    title = re.sub(r'`', '', D.get('title') or D.get('one') or '').replace('&', '&amp;').replace('<', '&lt;')
    data = json.dumps(D, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
    css, js = _asset(ctx, 'kit.css'), _asset(ctx, 'kit.js')
    s = re.sub(r'<title>.*?</title>', lambda _: '<title>%s</title>' % title, s, 1)
    s = re.sub(r'<!-- into .*?-->\n', '', s, 1, re.S)
    s = re.sub(r'(<script type="application/json" id="into">).*?(</script>)', lambda m: m.group(1) + data + m.group(2), s, 1, re.S)
    s = re.sub(r'<!--KIT_CSS-->.*?<!--/KIT_CSS-->', lambda _: '<style>\n' + css + '</style>', s, 1, re.S)
    return re.sub(r'<!--KIT_JS-->.*?<!--/KIT_JS-->', lambda _: '<script>\n' + js + '</script>', s, 1, re.S)


def render(mode, ctx):
    if mode == 'slides':
        raise UserError('slides는 아직 이 렌더러가 그리지 않는다. assets/slides.html을 채운다')
    return page(mode, build(mode, ctx), ctx.get('assets'))


# ---------- 따로 부르기 (원문 없이 모델과 칸만 있을 때) ----------
class _NoSource(object):
    kind, _extra_numbers = 'none', frozenset()

    def text(self):
        return ''

    def where(self, *a, **k):
        return ''

    def around(self, *a, **k):
        return ''

    def resolve(self, s):
        return {'ok': True, 'msg': '', 'warn': '', 'label': str(s).strip(), 'text': '', 'lines': [], 'kind': 'text'}

    def number_ok(self, *a, **k):
        return True

    def has_text(self, *a, **k):
        return True

    def missing_tokens(self, toks):
        return []


def make_ctx(mode, model, slots, spec, meta):
    """CORE의 칸 검사를 거쳐 ctx를 만든다. meta: size, public, url, source(cite.Source), strict"""
    from . import cells
    meta = meta or {}
    m = M.normalize(model)
    rows = spec.rows(mode)
    if rows is None:
        raise UserError('formats/%s.md에 `## %s` 표가 없다' % (spec.stem, mode))
    chk = cells.Checker(mode, rows, m, slots, meta.get('source') or _NoSource(), meta, spec).run()
    bad = [str(i) for i in chk.issues if i.level == 'FAIL']
    if bad and meta.get('strict', True):
        raise UserError('칸을 고친다: ' + ' / '.join(bad[:5]))
    stem = spec.stem if isinstance(spec.stem, str) else spec.stem()
    ctx = cells.context(chk, m.get('type') or stem, meta.get('size') or '보통', meta, meta.get('name') or 'raw')
    ctx['assets'] = ASSETS
    ctx['issues'] = chk.issues
    return ctx


def render_html(model, slots, spec, meta=None):
    return render('html', make_ctx('html', model, slots, spec, meta))


def render_interactive(model, slots, spec, meta=None):
    return render('interactive', make_ctx('interactive', model, slots, spec, meta))

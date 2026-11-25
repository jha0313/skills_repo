# -*- coding: utf-8 -*-
"""brief · eli5 · ste · doc 글 만들기. 근거 줄 · 순서 안내 · 비공개 안내 · (추정) 표시는 여기서 붙인다."""
import re
import unicodedata

from . import DOC_TITLES, SLOTS
from . import model as M
from . import text as T
from .cells import mark_suffix
from .formats import PIC_FORMS

ARROWS = ('beforeafter', 'flow')
LINE = 100            # 화살표 한 줄의 폭(한글 2칸)


def width(s):
    return sum(2 if unicodedata.east_asian_width(c) in 'WF' else 1 for c in s)


def pad(s, n):
    return s + ' ' * max(0, n - width(s))


# ---------- 간선 ----------
def node_name(m, i):
    for n in M.as_list(m.get('nodes')):
        if isinstance(n, dict) and str(n.get('id')) == str(i):
            return str(n.get('t') or i)
    return str(i)


def edge_cond(e):
    """라벨 뒤에 붙일 조건. 글에 이미 있으면(그대로, 또는 조건 말과 핵심 낱말의 절반 넘게) 붙이지 않는다."""
    c, t = str(e.get('if') or '').strip(), str(e.get('t') or '')
    low, ws = re.sub(r'\s', '', t).lower(), T.stems(c)
    if re.sub(r'\s', '', c).lower() in low or ws and sum(w in low for w in ws) * 2 > len(ws) and re.search(r'면(?=[\s,.)·]|$)|때|경우|조건|이상|이하|에서|만(?=[\s,.)·]|$)|\bif\b|\bwhen\b', t, re.I):
        return ''
    return c


def edge_label(e):
    s = re.sub(r'\s+', ' ', str(e.get('t') or '')).strip()
    c = edge_cond(e)
    s += ' · ' + c if c else ''
    return s + mark_suffix(s, [e])


def arrows(m, edges):
    """간선 목록 → 줄 목록. 앞 간선의 끝에서 이어지고, 그 줄에 없던 노드로 가고, LINE 안에 들면 같은 줄 (되돌아오는 간선과 갈래는 새 줄)."""
    out, end, on = [], None, set()
    for e in edges:
        a, b = str(e.get('from')), str(e.get('to'))
        more = ' ─(%s)▶ %s' % (edge_label(e), node_name(m, b))
        if out and a == end and b not in on and width(out[-1] + more) <= LINE:
            out[-1] += more
        else:
            out.append(node_name(m, a) + more)
            on = {a}
        on.add(b)
        end = b
    return out


def before_after(edges):
    b = [e for e in edges if e.get('when', 'both') in ('before', 'both', '', None)]
    a = [e for e in edges if e.get('when', 'both') in ('after', 'both', '', None)]
    return b, a


def arrow_lines(ctx, rows):
    """pic 자리의 화살표와 한 줄 칸 → [(칸, 이름, 줄들)]"""
    m, left = ctx['model'], []
    for r in rows:
        v = ctx['cells'].get(r['key'])
        if not v:
            continue
        if r['form'] == 'beforeafter':
            b, a = before_after(v)
            left.append((r['key'], '전', arrows(m, b) or ['(없음)']))
            left.append((r['key'], '후', arrows(m, a) or ['(없음)']))
        elif r['form'] == 'flow':
            left.append((r['key'], r['label'] if len(rows) > 1 and any(x['form'] == 'beforeafter' for x in rows) else '', arrows(m, v)))
        else:
            left.append((r['key'], r['label'], [plain(ctx, v[0])]))
    return left


def arrow_block(ctx, rows):
    """코드 블록 하나로."""
    left = arrow_lines(ctx, rows)
    if not left:
        return []
    w = max(width(k) for _, k, _ in left)
    out = ['```']
    for _, k, ls in left:
        for i, ln in enumerate(ls):
            out.append((pad(k if i == 0 else '', w) + '  ' if w else '') + ln)
    return out + ['```']


# ---------- 칸 ----------
def items_of(ctx, it):
    return [ctx['refs'][i] for i in it.get('f') or [] if i in ctx['refs']]


def plain(ctx, it):
    """칸의 글 + 표시. 사실이 여럿이고 문장도 여럿이면 표시는 그 사실이 걸린 문장 끝에."""
    t, own = it['t'], items_of(ctx, it)
    ss = T.sentences(t)
    if len(ss) < 2 or len({tuple(M.marks(x)) for x in own}) < 2:
        return t + mark_suffix(t, own)
    put = {}
    for x in own:
        if mark_suffix(t, [x]):
            mine = T.grams(' '.join(s for _, s in M.prose(x)), 2)
            put.setdefault(max(range(len(ss)), key=lambda k: (len(mine & T.grams(ss[k], 2)), k)), []).append(x)
    for k, xs in put.items():
        end = t.find(ss[k]) + len(ss[k].rstrip('.!?。'))
        t = t[:end] + mark_suffix(it['t'], xs) + t[end:]
    return t


def esc(s):
    return re.sub(r'\s*\n\s*', ' ', str(s)).replace('|', '\\|')


def md_table(head, rows):
    return ['| ' + ' | '.join(esc(h) for h in head) + ' |', '|' + '---|' * len(head)] + ['| ' + ' | '.join(esc(c) for c in r) + ' |' for r in rows]


def table_block(ctx, r, v):
    rows = []
    for it in v:
        c = list(it['cells'])
        c[-1] += mark_suffix(it['t'], items_of(ctx, it))
        rows.append(c)
    same = re.sub(r'[\s→·,]', '', r['label']) == re.sub(r'[\s→·,]', '', ''.join(r['cols']))
    return ([] if same else ['**%s**' % r['label'], '']) + md_table(r['cols'], rows)


def pic_block(ctx, r, v):
    """화살표가 아닌 그림 형을 글로."""
    f, m = r['form'], ctx['model']
    head = ['**%s**' % r['label']]

    def sfx(x, s):
        return s + mark_suffix(s, [x])
    if f == 'map':
        lines = ['- %s — %s%s' % (x.get('t', ''), x.get('does', ''), ' (%s)' % x['grade'] if x.get('grade') else '') for x in v]
        path = [ctx['refs'][i] for i in map(str, M.as_list(m.get('path'))) if i in ctx['refs']]
        if path:
            lines += ['', '```'] + arrows(m, path) + ['```']
        return head + lines
    if f == 'lanes':
        lane = [str(x.get('lane') or x.get('who') or '?') for x in v]
        w = max(width(n) for n in lane)
        rows = []
        for i, x in enumerate(v):
            nxt = lane[i + 1] if i + 1 < len(v) else ''
            rows.append(pad(lane[i], w) + '  ' + sfx(x, _step(x)) + ((' ─(%s)▶ %s' % (x['out'], nxt)).rstrip() if x.get('out') else ''))
        return ([ctx['order_note']] if ctx['order_note'] else []) + ['```'] + rows + ['```']
    if f == 'timeline':
        return head + ['- `%s` %s%s' % (x.get('at', ''), x.get('t', ''), ' — ' + sfx(x, str(x['claim'])) if x.get('claim') else '') for x in v]
    if f == 'ladder':
        return head + ['- [%s] %s' % (x.get('ev') or '?', sfx(x, str(x.get('t', '')))) for x in v]
    if f == 'positions':
        return head + ['- %s%s%s%s' % ('[%s] ' % x['ev'] if x.get('ev') else '', x.get('t', ''), '(%s)' % x['n'] if x.get('n') not in (None, '') else '', ' — ' + sfx(x, str(x['why'])) if x.get('why') else '') for x in v]
    if f == 'anatomy':
        return head + ['- `%s` %s%s' % (x.get('range', ''), x.get('t', ''), ' — ' + sfx(x, str(x['does'])) if x.get('does') else '') for x in v]
    if f == 'options':
        crit = [c for c in M.as_list(m.get('criteria')) if isinstance(c, dict)]
        got = {}
        for c in M.as_list(m.get('cells')):
            if isinstance(c, dict):
                got[(str(c.get('o')), str(c.get('c')))] = '%s %s' % ({'+': '＋', '-': '−', '?': '△'}.get(str(c.get('sign')), ''), sfx(c, str(c.get('t') or '')))
        crit = [c for c in crit if any((str(o.get('id')), str(c.get('id'))) in got for o in v)]
        if not crit or ctx.get('mode') != 'doc':
            return head + ['- %s%s%s' % (o.get('t', ''), '(고름)' if o.get('chosen') else '', ' — ' + sfx(o, w) if w else mark_suffix('', [o])) for o, w in ((o, reason(m, o)) for o in v)]
        return head + [''] + md_table(['안'] + [c['t'] for c in crit],
                                      [['%s%s' % ('✓ ' if o.get('chosen') else '', o.get('t', ''))] + [got.get((str(o.get('id')), str(c.get('id'))), '').strip() for c in crit] for o in v])
    if f == 'chart':
        def val(x):
            s = '' if x.get('value') is None else str(x['value'])
            return (s + str(x['unit']) if len(str(x['unit'])) < 3 else s + ' ' + str(x['unit'])) if s and x.get('unit') and not s.endswith(str(x['unit'])) else s
        groups, labels = [list(dict.fromkeys(str(x.get(k) or '') for x in v)) for k in ('group', 'label')]
        if len(groups) > 1 and len(labels) > 1 and len({(str(x.get('group') or ''), str(x.get('label') or '')) for x in v}) == len(v):
            at, bases = {(str(x.get('group') or ''), str(x.get('label') or '')): x for x in v}, {str(x.get('base')) for x in v if x.get('base')}
            rows = []
            for g in groups:
                row = [g + (' (기준)' if g in bases else '')]
                for lb in labels:
                    x = at.get((g, lb))
                    c = '' if x is None else val(x)
                    if x is not None and x.get('cond') and T.count(x['cond']) <= 12:
                        c = '%s (%s)' % (c, x['cond']) if c else str(x['cond'])
                    row.append(sfx(x, c) if x is not None else '')
                rows.append(row)
            return head + [''] + md_table(['조건'] + labels, rows)
        cols = [(k, h) for k, h in (('group', '조건'), ('label', '지표'), ('value', '값'), ('base', '기준'), ('cond', '자료·유의성')) if any(x.get(k) not in (None, '') for x in v)]
        rows = []
        for x in v:
            row = [val(x) if k == 'value' else '' if x.get(k) is None else str(x[k]) for k, _ in cols]
            row[-1] += mark_suffix(' '.join(row), [x])
            rows.append(row)
        return head + [''] + md_table([h for _, h in cols], rows)
    return []


def reason(m, o):
    """안 하나의 이유 한 줄: 적힌 이유 → 고른 안은 좋은 점(＋), 아니면 나쁜 점(−)."""
    if o.get('why') or o.get('d'):
        return str(o.get('why') or ' '.join(map(str, M.as_list(o['d']))))
    mine = [c for c in M.as_list(m.get('cells')) if isinstance(c, dict) and str(c.get('o')) == str(o.get('id')) and c.get('t')]
    want = [c for c in mine if str(c.get('sign')) == ('+' if o.get('chosen') else '-')] or mine
    return str(want[0]['t']) + mark_suffix(str(want[0]['t']), want[:1]) if want else ''


def _step(x):
    s = str(x.get('do') or '')
    if x.get('if'):
        s = '%s — %s' % (x['if'], s)
    return s


def text_block(ctx, r, v):
    """line · list · steps · qa · quote · number · code"""
    f, lb = r['form'], '**%s**' % r['label']
    if f == 'code':
        out = [lb]
        for it in v:
            out += ([it['t']] if it.get('t') and it['t'] != it.get('label') else []) + ['```', it['code'], '```']
        return out
    if f == 'qa':
        qs = ['Q. %s → A. %s' % (it['q'], it['a'] + mark_suffix(it['t'], items_of(ctx, it))) for it in v]
        return ['%s %s' % (lb, qs[0])] if len(qs) == 1 else [lb] + ['- ' + q for q in qs]
    if f == 'quote':
        return ['%s “%s”' % (lb, plain(ctx, v[0]).strip('"“”'))]
    if f == 'number':
        it = v[0]
        if it.get('v') not in (None, ''):
            return ['%s **%s%s** %s' % (lb, it['v'], it.get('unit') or '', it.get('of') or '') + mark_suffix(it['t'], items_of(ctx, it))]
        return ['%s %s' % (lb, plain(ctx, it))]
    ts = [plain(ctx, it) for it in v]
    if r['key'] == 'terms':
        return ['용어: ' + ' · '.join(ts)]
    if f == 'steps':
        if len(ts) == 1:
            return ['%s %s' % (lb, ts[0])]
        return [lb + (' (%s)' % ctx['order_note'] if ctx['order_note'] else '')] + ['%d. %s' % (i, t) for i, t in enumerate(ts, 1)]
    if len(ts) == 1:
        return ['%s %s' % (lb, ts[0])]
    if ctx['mode'] != 'doc' and sum(T.count(t) for t in ts) <= 90 and not any(' · ' in t for t in ts):
        return ['%s · %s' % (lb, ' · '.join(ts))]
    return [lb] + ['- ' + t for t in ts]


def block(ctx, r):
    v = ctx['cells'].get(r['key'])
    if not v:
        return []
    if r['form'] == 'table':
        return table_block(ctx, r, v)
    if r['form'] in ARROWS:
        return arrow_block(ctx, [r])
    if r['form'] in PIC_FORMS:
        return pic_block(ctx, r, v)
    return text_block(ctx, r, v)


def cite_ids(ctx, rows):
    """이 행들이 가리키는 id와 직접 단 근거 (나온 순서)."""
    ids, extra = [], []
    for r in rows:
        for it in ctx['cells'].get(r['key']) or []:
            if not isinstance(it, dict):
                continue
            if r['form'] in PIC_FORMS:
                ids.append(M.id_of(ctx['refs'], it))
            else:
                ids += [i for i in it.get('f') or [] if i not in ids]
                extra += it.get('labels') or ([it['label']] if it.get('label') else [])
    return list(dict.fromkeys(ids)), extra


def title_line(ctx):
    return ctx['title'] + (' · ' + ctx['scope'] if ctx['scope'] and ctx['scope'] not in ctx['title'] else '')


def render(mode, ctx):
    return doc(ctx) if mode == 'doc' else talk(ctx)


def groups(rows, first):
    """[(자리, 함께 그릴 칸들)] 나온 순서. pic 자리의 화살표와 한 줄 칸은 한 묶음."""
    out = []
    for slot in SLOTS:
        mine, k = [r for r in rows if r['slot'] == slot and r is not first], 0
        while k < len(mine):
            n = 1
            if slot == 'pic' and mine[k]['form'] in ARROWS + ('line',) and any(x['form'] in ARROWS for x in mine[k:]):
                while k + n < len(mine) and mine[k + n]['form'] in ARROWS + ('line',):
                    n += 1
            out.append((slot, mine[k:k + n]))
            k += n
    return out


def first_row(rows):
    return next((r for r in rows if r['slot'] == 'one' and r['form'] == 'line'), None)


def used(ctx):
    """[(칸, 쓴 글자)] 나온 순서. 합은 결과의 T.count_result와 같다."""
    seen = set()
    n = lambda ls: T.count_lines(T.body_of('\n'.join(ls)).split('\n'), seen)
    if ctx['mode'] == 'doc':
        return [(r['key'], n(bl)) for _, _, bls in doc_blocks(ctx) for r, bl in bls]
    rows = [r for r in ctx['rows'] if r['key'] in ctx['cells']]
    first, out = first_row(rows), [('머리', T.count(title_line(ctx)))]
    if first:
        out.append((first['key'], T.count(plain(ctx, ctx['cells'][first['key']][0]))))
    for _, grp in groups(rows, first):
        if len(grp) == 1 and grp[0]['form'] not in ARROWS:
            out.append((grp[0]['key'], n(block(ctx, grp[0]))))
            continue
        ls = arrow_lines(ctx, grp)
        out += [(r['key'], T.count_lines(['%s  %s' % (name if i == 0 else '', ln) for k, name, xs in ls if k == r['key'] for i, ln in enumerate(xs)], seen)) for r in grp]
    return out


def talk(ctx):
    """brief · eli5 · ste"""
    rows = [r for r in ctx['rows'] if r['key'] in ctx['cells']]
    first = first_row(rows)
    out = [ctx['notice'], ''] if ctx['notice'] else []
    out.append('**%s · %s**%s' % (ctx['type_name'], title_line(ctx), ' — ' + plain(ctx, ctx['cells'][first['key']][0]) if first else ''))
    if ctx['mode'] == 'ste' and not any(r['key'] == 'terms' for r in rows):
        ts = ['%s = %s' % (t['w'], ' / '.join(str(x) for x in M.as_list(t.get('o')))) for t in M.as_list(ctx['model'].get('terms')) if isinstance(t, dict) and t.get('w')]
        if ts:
            out.append('용어: ' + ' · '.join(ts))
    started, prev_multi = False, False
    for slot, grp in groups(rows, first):
        bl = arrow_block(ctx, grp) if len(grp) > 1 or grp[0]['form'] in ARROWS else block(ctx, grp[0])
        multi = len(bl) > 1
        if out[-1] != '' and (multi or prev_multi or (slot != 'one' and not started)):
            out.append('')
        out += bl
        prev_multi, started = multi, started or slot != 'one'
    ids, extra = cite_ids(ctx, [r for s in SLOTS for r in rows if r['slot'] == s])
    return '\n'.join(out + [''] + tail(ctx, ids, extra)) + '\n'


def tail(ctx, ids, extra, cites=True):
    out = ['빠진 디테일: ' + ctx['missing']]
    c = ctx['cite'](ids, 6, extra) if cites else ''
    if c:
        out.append('근거: ' + c)
    return out + ['출처: ' + ctx['source']]


# ---------- doc ----------
def mm_label(s):
    """flowchart 따옴표 라벨에 안전한 글자."""
    s = re.sub(r'\s+', ' ', str(s)).strip().replace('`', '').replace('%%', '％％')
    s = s.replace('#', '#35;').replace('"', '#quot;').replace('<', '#lt;').replace('>', '#gt;')
    return s or ' '


def mm_seq(s):
    """sequenceDiagram 글자: 따옴표·;·# 을 쓰지 않는다. 뜻이 있는 ! && || 는 남긴다."""
    s = re.sub(r'\s+', ' ', str(s)).strip().replace('`', '').replace('"', '').replace('%%', '％％')
    s = s.replace(';', '；').replace('#', '＃').replace('<br>', ' ').replace('->>', '→').replace('-->', '→')
    return '(end)' if s.lower() == 'end' else s or ' '


def flowchart(m, edges, changed=None):
    ids, out = {}, ['```mermaid', 'flowchart LR']
    for e in edges:
        for k in ('from', 'to'):
            i = str(e.get(k))
            if i not in ids:
                ids[i] = 'n%d' % (len(ids) + 1)
                out.append('  %s["%s"]' % (ids[i], mm_label(node_name(m, i))))
    for e in edges:
        hot = e.get('main') or (changed and e.get('when') == changed)
        arrow = '-.->' if 'guess' in e and e['guess'] or '추정' in M.marks(e) else '==>' if hot else '-->'
        out.append('  %s %s|"%s"| %s' % (ids[str(e.get('from'))], arrow, mm_label(edge_label(e)), ids[str(e.get('to'))]))
    return out + ['```']


def sequence(ctx):
    """model.steps → sequenceDiagram. 받는 쪽(to)이 없으면 Note로 쓴다(화살표를 지어내지 않는다)."""
    m = ctx['model']
    steps = [x for x in M.as_list(m.get('steps')) if isinstance(x, dict)]
    who = []
    for x in steps:
        for w in (x.get('who'), x.get('to')):
            if w and str(w) not in who:
                who.append(str(w))
    if m.get('order') not in ('time', 'call') or len(who) < 2 or len(steps) < 2 or not any(x.get('to') for x in steps) or any(not x.get('who') for x in steps):
        return []
    pid = {w: 'p%d' % (i + 1) for i, w in enumerate(who)}
    out = ['```mermaid', 'sequenceDiagram'] + ['  participant %s as %s' % (pid[w], mm_seq(node_name(m, w))) for w in who]
    for x in steps:
        txt = mm_seq(str(x.get('do') or '') + mark_suffix(str(x.get('do') or ''), [x]))
        line = '%s->>%s: %s' % (pid[str(x['who'])], pid[str(x['to'])], txt) if x.get('to') else 'Note over %s: %s' % (pid[str(x['who'])], txt)
        if x.get('if'):
            out += ['  opt ' + mm_seq(x['if']), '    ' + line, '  end']
        else:
            out.append('  ' + line)
        if x.get('fail'):
            out.append('  Note over %s: 실패 — %s' % (pid[str(x['who'])], mm_seq(x['fail'])))
    return out + ['```']


def doc_blocks(ctx):
    """[(자리, 칸들, [(칸, 줄들)])]"""
    m, res = ctx['model'], []
    rows = [r for r in ctx['rows'] if r['key'] in ctx['cells']]
    for slot in SLOTS:
        mine, bls = [r for r in rows if r['slot'] == slot], []
        for r in mine:
            v = ctx['cells'][r['key']]
            alone = len(mine) == 1 or r['label'] == DOC_TITLES[slot]
            if r['form'] == 'beforeafter':
                b, a = before_after(v)
                bl = ['**전**', ''] + flowchart(m, b, 'before') + ['', '**후**', ''] + flowchart(m, a, 'after')
                if not b or not a:
                    bl = flowchart(m, v)
            elif r['form'] == 'flow':
                bl = ([] if alone else ['**%s**' % r['label'], '']) + flowchart(m, v)
            elif r['form'] == 'map':
                bl = md_table(['구역', '하는 일', '읽기'], [[x.get('t', ''), x.get('does', ''), x.get('grade', '')] for x in v])
                path = [ctx['refs'][i] for i in map(str, M.as_list(m.get('path'))) if i in ctx['refs']]
                if path:
                    bl = flowchart(m, path) + [''] + bl
            else:
                bl = block(ctx, r)
                if alone and bl and bl[0] == '**%s**' % r['label']:
                    bl = bl[1:] if bl[1:2] != [''] else bl[2:]
                elif alone and bl and bl[0].startswith('**%s** ' % r['label']):
                    bl = [bl[0][len('**%s** ' % r['label']):]] + bl[1:]
                if r['form'] == 'steps' and slot == 'run':
                    sq = sequence(ctx)
                    if sq:
                        bl = sq + [''] + bl
            bls.append((r, bl))
        if mine:
            res.append((slot, mine, bls))
    return res


def doc(ctx):
    out = [ctx['notice'], ''] if ctx['notice'] else []
    out += ['# %s — 이해 문서' % title_line(ctx), '', '> 유형: %s · 크기: %s' % (ctx['type_name'], ctx['size'])]
    for slot, mine, bls in doc_blocks(ctx):
        out += ['', '## ' + DOC_TITLES[slot]]
        for _, bl in bls:
            out += [''] + bl
        ids, extra = cite_ids(ctx, mine)
        c = ctx['cite'](ids, 6, extra)
        if c:
            out += ['', '근거: ' + c]
    return '\n'.join(out + ['', '---', ''] + [x for ln in tail(ctx, [], [], False) for x in (ln, '')]).rstrip() + '\n'

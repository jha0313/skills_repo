# -*- coding: utf-8 -*-
"""formats/*.md의 `## 예`(eli5)를 칸으로 되읽어 렌더러로 다시 그린다. 예와 실제 출력의 모양이 같은지 보는 데 쓴다."""
import re

from intolib import NOTICE, cells, cite, formats, textmodes
from intolib import text as T

ARROW = re.compile(r' ─\((.*?)\)▶ ?')


def example(spec):
    s = open(spec.path, encoding='utf-8').read()
    s = s[s.index('\n## 예') + 1:].split('\n', 1)[1]
    return s.split('\n<!--')[0].strip('\n') + '\n'


class Reader(object):
    def __init__(self, spec, text):
        self.spec, self.rows = spec, spec.rows('eli5')
        self.cells, self.model = {}, {'nodes': [], 'edges': [], 'order': 'time'}
        self.names = {}
        self.read(text)

    def row(self, label=None, form=None):
        return next((r for r in self.rows if (label is None or r['label'] == label) and (form is None or r['form'] in form) and r['key'] not in self.cells), None)

    def item(self, t):
        return {'t': t, 'f': [], 'where': ''}

    def node(self, name):
        self.names.setdefault(name, 'n%d' % len(self.names))
        if not any(n['t'] == name for n in self.model['nodes']):
            self.model['nodes'].append({'id': self.names[name], 't': name})
        return self.names[name]

    def edges(self, line, when):
        p = ARROW.split(line)
        return [{'id': 'e', 'from': self.node(p[i]), 'to': self.node(p[i + 2]), 't': p[i + 1], 'when': when} for i in range(0, len(p) - 2, 2)]

    def code(self, lines):
        r = self.row(form=('lanes',))
        if r:
            out = []
            for ln in lines:
                lane, rest = re.split(r'\s{2,}', ln, 1)
                p = ARROW.split(rest)
                out.append({'lane': lane, 'do': p[0], 'out': p[1] if len(p) > 1 else ''})
            self.cells[r['key']] = out
            return
        for ln in lines:
            m = re.match(r'^(전|후)\s{2,}(.+)$', ln)
            if m:
                self.cells.setdefault(self.row_of('beforeafter')['key'], []).extend(self.edges(m.group(2), 'before' if m.group(1) == '전' else 'after'))
                continue
            k = re.match(r'^(\S.*?)\s{2,}(.+)$', ln)
            r = self.row(label=k.group(1), form=('line',)) if k else None
            if r:
                self.cells[r['key']] = [self.item(k.group(2))]
            else:
                self.cells.setdefault(self.row_of('flow')['key'], []).extend(self.edges(ln, 'both'))

    def row_of(self, form):
        return next(r for r in self.rows if r['form'] == form)

    def table(self, rows):
        grid = [T.split_row(x) for x in rows]
        head, body = grid[0], grid[2:]
        r = self.row(form=('chart',)) if head[0] == '조건' else None
        if r:
            out = []
            base = [g[0][:-5] for g in body if g[0].endswith(' (기준)')]
            for g in body:
                name = g[0][:-5] if g[0].endswith(' (기준)') else g[0]
                out += [{'group': name, 'label': lb, 'value': v, 'base': (base or [''])[0]} for lb, v in zip(head[1:], g[1:])]
            self.cells[r['key']] = out
            return
        r = next(x for x in self.rows if x['form'] == 'table' and x['cols'] == head)
        self.cells[r['key']] = [dict(self.item(' / '.join(g)), cells=g) for g in body]

    def labelled(self, label, rest, lines):
        r = self.row(label=label)
        if r is None:
            raise ValueError('칸 `%s`가 eli5 표에 없다' % label)
        f = r['form']
        if f == 'timeline':
            got = [re.match(r'^- `([^`]*)` (.+?)(?: — (.+))?$', x).groups() for x in lines]
            v = [{'at': a, 't': t, 'claim': c or ''} for a, t, c in got]
        elif f == 'ladder':
            v = [dict(zip(('ev', 't'), re.match(r'^- \[([^\]]+)\] (.+)$', x).groups())) for x in lines]
        elif f == 'positions':
            v = [dict(zip(('ev', 't', 'n', 'why'), re.match(r'^- (?:\[([^\]]+)\] )?(.+?)(?:\((\d+)\))?(?: — (.+))?$', x).groups())) for x in lines]
        elif f == 'steps':
            v = [self.item(re.sub(r'^\d+\. ', '', x)) for x in lines] or [self.item(rest)]
        elif f == 'list' and rest.startswith('· '):
            v = [self.item(x) for x in rest[2:].split(' · ')]
        elif f == 'list' and lines:
            v = [self.item(x[2:]) for x in lines]
        else:
            v = [self.item(rest)]
        self.cells[r['key']] = v

    def read(self, text):
        ls = text.rstrip('\n').split('\n')
        self.notice = ls[0] if ls[0] == NOTICE else ''
        i = 2 if self.notice else 0
        m = re.match(r'^\*\*(.+?) · (.+?)\*\* — (.+)$', ls[i])
        self.type_name, self.title = m.group(1), m.group(2)
        self.cells[next(r['key'] for r in self.rows if r['slot'] == 'one')] = [self.item(m.group(3))]
        i += 1
        self.tail = {}
        while i < len(ls):
            ln = ls[i]
            t = re.match(r'^(빠진 디테일|근거|출처): (.+)$', ln)
            if t:
                self.tail[t.group(1)] = t.group(2)
            elif ln == '```':
                j = ls.index('```', i + 1)
                self.code(ls[i + 1:j])
                i = j
            elif ln.startswith('|'):
                j = i
                while j < len(ls) and ls[j].startswith('|'):
                    j += 1
                self.table(ls[i:j])
                i = j - 1
            elif ln.startswith('**'):
                label, rest = re.match(r'^\*\*(.+?)\*\* ?(.*)$', ln).groups()
                j = i + 1
                while j < len(ls) and re.match(r'^(?:- |\d+\. )', ls[j]):
                    j += 1
                if j == i + 1 and not rest and ls[j] == '':
                    pass                                                  # 표 이름. 다음 줄의 표가 채운다
                else:
                    self.labelled(label, rest, ls[i + 1:j])
                    i = j - 1
            i += 1

    def blank(self):
        zone = '구역' in self.title          # 구역 결과에는 지도를 그리지 않는다
        return [r['label'] for r in self.rows if r['key'] not in self.cells and not r['optional'] and not (zone and r['form'] == 'map')]

    def render(self):
        src = self.tail.get('근거', '')
        more = re.search(r' · 외 (\d+)곳$', src)
        labels = []
        for part in (src[:more.start()] if more else src).split(' · '):
            post, path = re.match(r'^(?:글 )?(.+)/(\d+)$', part), re.match(r'^(.+?):(-?\d.*)$', part)
            if post and re.match(r'^[\d\s,–-]+$', post.group(1)):
                for x in post.group(1).split(', '):
                    a, b = (re.split(r'[-–]', x) + [x])[:2]
                    labels += ['%d/%s' % (k, post.group(2)) for k in range(int(a), int(b) + 1)]
            elif path:
                labels += ['%s:%s' % (path.group(1), x) for x in path.group(2).split(', ')]
            elif part:
                labels.append(part)
        missing = re.sub(r'(?:^|\. )빈 칸: .*$', '', self.tail.get('빠진 디테일', '없음'))
        missing = [missing] if missing not in ('', '없음') else []
        ctx = {'mode': 'eli5', 'type_name': self.spec.name, 'title': self.title, 'scope': '', 'notice': self.notice, 'rows': self.rows, 'cells': self.cells, 'refs': {}, 'model': self.model,
               'order_note': '', 'missing': cells.missing_line(missing, self.blank()), 'source': self.tail.get('출처', ''), 'cite': lambda ids, n, extra=(): cite.format_cites(labels, n) + (more.group(0) if more else '')}
        return textmodes.render('eli5', ctx)

    def over(self):
        """칸 한도를 넘은 것 [(키, 글자 수)]"""
        out = []
        for r in self.rows:
            for it in self.cells.get(r['key']) or []:
                for c in it.get('cells') or ([it['t']] if 'where' in it else []):
                    lim = r['n'] if r['form'] in ('line', 'quote', 'number') else r['chars']
                    if lim and T.count(c) > lim:
                        out.append((r['key'], T.count(c), lim))
        return out

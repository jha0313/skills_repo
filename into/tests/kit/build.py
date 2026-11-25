#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/kit의 예 → HTML. 사용: build.py <나올 폴더> [이름 …]   (다른 폴더의 예는 경로로 준다)"""
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts'))
from intolib import UserError, cells, formats, htmlmodes as H  # noqa: E402


def main():
    out, names = sys.argv[1], sys.argv[2:]
    os.makedirs(out, exist_ok=True)
    files = [n if n.endswith('.json') else os.path.join(HERE, n + '.json') for n in names] or sorted(glob.glob(os.path.join(HERE, '*.json')))
    bad = 0
    for p in files:
        name = os.path.splitext(os.path.basename(p))[0]
        j = json.load(open(p, encoding='utf-8'))
        if 'page' in j:
            open(os.path.join(out, '%s-%s.html' % (name, j['page']['mode'])), 'w', encoding='utf-8').write(H.page(j['page']['mode'], j['page']))
            continue
        sp = formats.load(j['model']['type'])
        for mode in ('html', 'interactive'):
            if mode not in j:
                continue
            try:
                ctx = H.make_ctx(mode, j['model'], j[mode], sp, dict(j.get('meta', {}), strict=False))
            except UserError as e:
                print('FAIL', name, mode, e)
                bad += 1
                continue
            iss = [str(i) for i in ctx['issues']] + ['%s %s %s' % x for x in H.check(mode, ctx)]
            n, lim = cells.total_cells(ctx), formats.length_limit(j['model']['type'], mode, ctx['size'])
            print('%-15s %-11s 글자 %d/%s' % (name, mode, n, lim) + (' 넘음' if lim and n > lim else ''))
            for i in iss:
                print('   ', i)
            open(os.path.join(out, '%s-%s.html' % (name, mode)), 'w', encoding='utf-8').write(H.render(mode, ctx))
    return bad


if __name__ == '__main__':
    sys.exit(1 if main() else 0)

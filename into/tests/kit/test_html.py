#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""화면 데이터 검사 (브라우저 없이). 사용: python3 tests/kit/test_html.py"""
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts'))
from intolib import formats, htmlmodes as H  # noqa: E402


def ctx(name, mode='html', change=None):
    with open(os.path.join(HERE, name + '.json'), encoding='utf-8') as f:
        j = json.load(f)
    if change:
        change(j)
    return H.make_ctx(mode, j['model'], j[mode], formats.load(j['model']['type']), dict(j['meta'], strict=False))


class Html(unittest.TestCase):
    def test_first_line_keeps_mark_and_source(self):
        D = H.build('html', ctx('round-trip'))
        self.assertEqual(D['head'].get('mark'), '추정')
        self.assertIn('1', D['head'].get('src', ''))
        self.assertIsInstance(D['one'], str)

    def test_edge_condition_is_shown_once_and_counted(self):
        c = ctx('round-trip')
        es = {e['id']: e for e in H.build('html', c)['figs'][0]['edges']}
        self.assertEqual(es['e2']['c'], '사용자가 동의하면')
        self.assertNotIn('c', es['e7'])                        # 글에 이미 있는 조건
        self.assertIn('사용자가 동의하면', dict(H.drawn(c))['pic'])

    def test_concept_parts_label(self):
        self.assertIn('구성 요소', [x['label'] for x in H.build('html', ctx('round-trip'))['cards']])

    def test_body_post_draws_rows_first(self):
        D = H.build('html', ctx('body-post'))
        self.assertEqual([(f['part'], f['key']) for f in D['figs']], [('list', 'cases')])
        self.assertIn('본문 구조', [x['label'] for x in D['cards']])

    def test_overflow_is_warned(self):
        def tall(j):
            j['model']['criteria'] += [{'id': 'k%d' % i, 't': '기준'} for i in range(6)]
            j['model']['cells'] += [{'o': o, 'c': 'k%d' % i, 't': '설정이 적고 kube-proxy는 거르기만', 'sign': '+', 'src': ['raw:1']} for i in range(6) for o in ('o1', 'o2', 'o3')]
        warn = lambda c: [x for x in H.check('html', c) if '한 화면' in x[2]]
        self.assertFalse(warn(ctx('chain5')))
        self.assertTrue(warn(ctx('chain5', change=tall)))

    def test_auto_question_has_no_invented_wrong_answer(self):
        rows = [{'cells': ['캐시가 비면', '서버에 요청한다'], 'src': 'raw:1', 'ids': ['a']}, {'cells': ['`캐시가 비면`', '로그를 남긴다'], 'src': 'raw:2', 'mark': '추정', 'ids': ['b']},
                {'cells': ['캐시가 차면', '캐시를 쓴다'], 'src': 'raw:3'}]
        one = H._together(rows)
        self.assertEqual([r['cells'] for r in one], [['캐시가 비면', '서버에 요청한다 · 로그를 남긴다 (추정)'], ['캐시가 차면', '캐시를 쓴다']])
        self.assertEqual((one[0]['src'], one[0]['ids']), ('raw:1 · raw:2', ['a', 'b']))
        ps = H._auto([{'rows': one}])
        self.assertEqual([p['answer'] for p in ps], ['서버에 요청한다 · 로그를 남긴다 (추정)', '캐시를 쓴다'])
        for name in ('codebase', 'design-doc', 'general', 'local-file', 'pr', 'skill', 'video'):
            self.assertFalse([p for p in H.build('interactive', ctx(name, 'interactive'))['predicts'] if 'opts' in p], name)


if __name__ == '__main__':
    unittest.main()

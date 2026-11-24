#!/usr/bin/env python3
"""사실 카드의 조건이 결과의 어느 자리에서 빠졌는지 찾는다 (표준 라이브러리만 사용, 읽기 전용).

사용: python3 check_facts.py <fact-card.md> <결과 파일>...
카드 표에 `검색어`와 `조건어` 열이 있는 행만 본다.
  검색어  그 사실이 나오는 자리를 찾을 말. `/`는 또는, `+`는 같은 문장에 함께 (예: 재시도+막). 글자 그대로의 빗금·세로줄은 `\\/`·`\\|`
  조건어  그 자리에 있어야 하는 말. `/`는 같은 조건의 다른 표현(하나면 됨), `;`는 따로 필요한 조건(모두 있어야 함)
          (예: 기본 설정/기본으로; 조각 모두)
  제외어  (선택) 이 말이 있으면 다른 뜻의 자리다. `/`로 여러 개
조건을 찾는 범위: 같은 문장 → 같은 칸(표의 행, 데이터 객체 하나, 앞뒤 문장).
  ‼ 같은 칸에도 없다     · 같은 칸의 다른 문장에만 있다(질문 문장, `빠진 디테일` 줄, `(조건부)`류 꼬리표를 단 자리도 여기)
나온 자리가 모두 틀린 것은 아니다. ‼부터 하나씩 본다. 조건어가 있어도 문장이 넓으면(모두·항상·~만) 여기에 걸리지 않는다.
"""
import html, re, sys
CITE = r'[A-Za-z0-9_.\-/@\[\]()]+\.[a-z]{1,5}(?::\d+(?:[-–~]\d+)?)?(?:\s*,\s*:?\d+(?:[-–~]\d+)?)*'

def rows(card):
    head = None
    for no, line in enumerate(open(card, encoding='utf-8'), 1):
        if not line.lstrip().startswith('|'): head = None; continue
        c = [x.strip().replace('\\|', '\x01').replace('\\/', '\x02') for x in re.split(r'(?<!\\)\|', re.sub(r'^\||(?<!\\)\|$', '', line.strip()))]
        if head is None: head = c; continue
        if set(''.join(c)) <= set('-: '): continue
        if '검색어' in head and len(c) != len(head): sys.exit('카드 %d줄: 칸이 %d개다(머리는 %d개). 칸 안의 세로줄은 `\\|`로 쓴다: %s' % (no, len(c), len(head), line.strip()[:70]))
        r = dict(zip(head, c))
        if r.get('검색어') and r.get('조건어') and r['조건어'] not in ('—', '-', ''): yield r

def blocks(path):
    """(줄 번호, 칸 글) — 표의 한 행과 데이터 객체 하나는 한 칸이다."""
    s = open(path, encoding='utf-8').read()
    if path.endswith('.html'):
        s = re.sub(r'<style.*?</style>', ' ', s, flags=re.S | re.I)
        s = re.sub(r'// ===== 아래는 동작 코드.*?(?=</script>|\Z)', ' ', s, flags=re.S)
        s = re.sub(r'(<script[^>]*>)(.*?)(</script>)', lambda m: m.group(1) + m.group(2).replace('<', '＜').replace('>', '＞') + m.group(3), s, flags=re.S | re.I)      # 데이터 글자의 < > 를 태그로 보지 않는다
        s = re.sub(r'\{([^{}]*)\}', lambda m: '\n' + m.group(1).replace('\n', ' ') + '\n', s)      # 데이터 객체 하나 = 한 칸
        attrs = '\n'.join(re.findall(r'aria-label="([^"]+)"', s))
        s = re.sub(r'\s*</t[dh]>\s*<t[dh][^>]*>\s*', ' | ', s)
        s = re.sub(r'</?(?:p|li|h[1-6]|tr|text|section|aside|summary|small|div)\b[^>]*>', '\n', s)
        s = html.unescape(re.sub(r'<[^>]+>', '', s)).replace('＜', '<').replace('＞', '>') + '\n' + attrs
    head = True
    for i, ln in enumerate(s.split('\n'), 1):
        row = ln.lstrip().startswith('|')
        if row and head: head = False; continue        # 표 머리
        if not row: head = True
        if row and set(ln) <= set('|-: '): continue
        ln = re.sub(r'[`*]', '', ln)
        ln = re.sub(r'(?:근거|출처|src|source)\s*:.*$' if not '"' in ln else r'(?:src|source)"?\s*:\s*"[^"]*"', ' ', ln)
        bare = re.sub(r'[\s·,|①-⑨()\d초~.\-–]+', '', re.sub(CITE, '', ln))
        if len(bare) < 4 or re.match(r'\s*(?:\|\s*)?(?:쉼|경로 기준|유형)\b', ln): continue
        yield i, ln.strip()

def inn(w, text): return w in text if not re.search(r'^\d|\d$', w) else bool(re.search((r'(?<![\d.,])' if w[0].isdigit() else '') + re.escape(w) + (r'(?![\d.,]*\d)' if w[-1].isdigit() else ''), text))
def lit(x): return x.strip().lower().replace('\x01', '|').replace('\x02', '/')
NORM = {'권고': 'should', '반드시': 'must', '해도 된다': 'may'}; NORM.update({v: k for k, v in NORM.items()})
def has(text, alts): return any(inn(w, text) or (w in NORM and inn(NORM[w], text)) for w in (lit(c) for c in alts.split('/') if c.strip()))

def main():
    if len(sys.argv) < 3: sys.exit(__doc__)
    card = list(rows(sys.argv[1]))
    if not card: sys.exit('카드에 `검색어`·`조건어`가 채워진 행이 없다.')
    for fp in sys.argv[2:]:
        bs = list(blocks(fp)); hits = set()
        for r in card:
            need = [g for g in r['조건어'].split(';') if g.strip()]; skip = r.get('제외어') or ''
            for k, (ln, b) in enumerate(bs):
                near = (bs[k - 1][1] if k and '|' not in b else '') + ' ' + b + ' ' + (bs[k + 1][1] if k + 1 < len(bs) and '|' not in b else '')
                for x in re.split(r'(?<=[.!?다])\s+(?=\S)|\s\|\s|",\s', b):
                    low = x.lower()
                    if len(x) < 5 or not any(all(inn(lit(p), low) for p in alt.split('+')) for alt in r['검색어'].split('/')): continue
                    if skip and skip not in ('—', '-') and has(low, skip): continue
                    miss = [g for g in need if not has(low, g)]
                    if not miss: continue
                    far = [g for g in miss if not has(near.lower(), g)]
                    if x.rstrip(' "').endswith('?') or '빠진 디테일' in b or re.search(r'\((?:조건부|예외 있음|일부|기본 설정)\)', x): far = []
                    hits.add((0 if far else 1, ln, '  %s%s:%d  %s  [없음: %s]' % ('‼ ' if far else '· ', fp.split('/')[-1], ln, x.strip()[:90], '; '.join(lit(g) for g in far or miss))))
        hard = sum(1 for h in hits if not h[0])
        print('%s: ‼ %d · 같은 칸에만 %d' % (fp.split('/')[-1], hard, len(hits) - hard))
        for _, _, h in sorted(hits)[:40]: print(h)
main()

#!/usr/bin/env python3
"""into 결과의 근거를 저장소와 대조한다 (표준 라이브러리만 사용, 읽기 전용).

사용: python3 check_citations.py --root <저장소> [--base <경로 기준>] <결과 파일>...
찾는 것:
  파일  근거의 파일이 저장소에 없다
  줄    근거의 줄 번호가 파일 길이를 넘거나 범위가 뒤집혔다
  이름  코드 이름(`snake_case`·`camelCase`)이 저장소 어디에도 없다
  모호  같은 상대 경로가 경로 기준 아래와 저장소 루트에 모두 있다(기준 아래 것으로 본다) — 루트를 뜻하면 `../`를 붙인다
  축약  근거 경로가 뒷부분만 맞는다(저장소에서 찾은 전체 경로를 알려 준다) — 경로 기준 아래 상대 경로로 고친다
  지지  코드 이름이 같은 절에서 단 근거 구간(앞뒤 8줄과 그 구간을 감싸는 정의 줄) 안에 없다(밑줄·대소문자 차이는 같은 이름으로 본다) — 근거를 다시 볼 후보
기계가 보는 것은 여기까지다. 근거 구간이 문장의 조건·순서·주체를 지지하는지는 직접 읽어 대조한다.
"""
import argparse, html, os, re, sys
EXT = r'(?:rs|go|py|rb|java|kt|swift|c|cc|cpp|h|hpp|cs|php|tsx?|jsx?|mjs|cjs|sql|sh|md|toml|ya?ml|json|css|html|proto|graphql)'
SEG = r'(?:[A-Za-z0-9_.\-@\[\]]|\([a-z0-9\-.]+\))+'
CITE = re.compile(r'(?<![A-Za-z0-9_/@.\-])((?:' + SEG + r'/)*' + SEG + r'\.' + EXT + r')(?::(\d+)(?:\s*[-–~]\s*(\d+))?)?(?![A-Za-z0-9_/])')
MORE = re.compile(r'[`\s]*(?:,\s*:?|·\s*:|;\s*:|\s:)\s*(\d+)(?:\s*[-–~]\s*(\d+))?(?![\d.]*[A-Za-z가-힣%/])')
SKIP = {'.git', 'node_modules', 'target', 'dist', 'build', '.next', 'vendor'}

def plain(path):
    s = open(path, encoding='utf-8').read()
    if path.endswith('.html'):
        data = [x.split('// ===== 아래는 동작 코드')[0] for x in re.findall(r'<script[^>]*>(.*?)</script>', s, flags=re.S | re.I)]
        s = re.sub(r'<script[^>]*>.*?</script>', ' ', s, flags=re.S | re.I)
        s = re.sub(r'<style.*?</style>', ' ', s, flags=re.S | re.I)
        s = re.sub(r'<code[^>]*>(.*?)</code>', r'`\1`', s, flags=re.S)
        s = re.sub(r'<(?:section|h[1-6]|li|tr|details|footer)\b', '\n\\g<0>', s)
        s = re.sub(r'<h([1-4])[^>]*>|<section[^>]*>', '\n# ', s)
        s = html.unescape(re.sub(r'<[^>]+>', ' ', s)) + '\n# ' + '\n# '.join(d for d in data if 'INTO =' in d or 'QUIZ =' in d)
    return s

DEF = re.compile(r'^\s*(?:(?:pub(?:\([^)]*\))?|export|default|async|static|public|private|protected|const|unsafe|abstract)\s+)*(?:fn|func|function|def|class|impl|trait|interface|struct|enum|type|mod|const)\b')

def owner(ls, s):
    """s번째 줄을 감싸는 정의 줄들(들여쓰기가 더 얕은 가장 가까운 정의 둘)."""
    if s >= len(ls): return []
    ind = len(ls[s]) - len(ls[s].lstrip()) if ls[s].strip() else 99; out = []
    for k in range(s, max(-1, s - 600), -1):
        x = ls[k]; i = len(x) - len(x.lstrip())
        if DEF.match(x) and (i < ind or k == s): out.append(' '.join(ls[k:k + 3])); ind = i
        if len(out) == 3 or (out and ind == 0): break
    return out

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--root', required=True); ap.add_argument('--base', default=''); ap.add_argument('files', nargs='+'); ap.add_argument('--no-support', action='store_true')
    a = ap.parse_args(); files, names, text = set(), {}, {}
    vocab = set()
    for d, ds, fs in os.walk(a.root):
        ds[:] = [x for x in ds if x not in SKIP]
        for f in fs:
            p = os.path.relpath(os.path.join(d, f), a.root).replace(os.sep, '/'); files.add(p); names.setdefault(f, []).append(p)
    def lines(p):
        if p not in text:
            try: text[p] = open(os.path.join(a.root, p), encoding='utf-8', errors='replace').read().removesuffix('\n').split('\n')
            except OSError: text[p] = []
        return text[p]
    def find(f):
        f = re.sub(r'^\./', '', f)
        b = a.base.rstrip('/') + '/' + f if a.base else ''
        if b in files: return [b], True
        if f in files: return [f], True
        return [x for x in names.get(os.path.basename(f), []) if x.endswith('/' + f)], False
    def known(w):
        if not vocab:
            for p in files:
                vocab.update(re.findall(r'[A-Za-z_][A-Za-z0-9_]{3,}', p))
                if os.path.getsize(os.path.join(a.root, p)) < 3_000_000: vocab.update(re.findall(r'[A-Za-z_][A-Za-z0-9_]{3,}', '\n'.join(lines(p))))
                text.pop(p, None)
        return w in vocab
    bad = 0
    for fp in a.files:
        t = plain(fp); secs = re.split(r'(?m)^(?=#{1,4} )', t); out = []; total = 0
        for sec in secs:
            spans = []
            for m in CITE.finditer(sec):
                f, l1, l2 = m.groups()
                if '/' not in f and not l1: continue
                total += 1; hit, exact = find(f)
                if not hit:
                    line = sec[sec.rfind('\n', 0, m.start()) + 1:(sec.find('\n', m.end()) + 1 or len(sec))]
                    if (l1 or '/' in f) and not re.search(r'없|찾지 못', line): out.append('파일  %s' % m.group(0))
                    continue
                if a.base and f in files and hit[0] != f: out.append('모호  %s (루트에도 있다)' % f)
                if not exact and '/' in f and l1: out.append('축약  %s → %s' % (f, hit[0] + (' 외 %d' % (len(hit) - 1) if len(hit) > 1 else '')))
                rng = [(l1, l2)] if l1 else []; k = m.end()
                while l1:
                    n = MORE.match(sec, k)
                    if not n: break
                    rng.append((n.group(1), n.group(2))); k = n.end()
                for x, y in rng:
                    s, e = int(x), int(y or x)
                    if e < s or all(e > len(lines(h)) for h in hit): out.append('줄    %s:%s%s (파일 %d줄)' % (f, x, '-' + y if y else '', max(len(lines(h)) for h in hit)))
                    spans += [(h, max(0, s - 9), e + 8) for h in hit[:3]]
            claims = re.sub(r'검색식[^)\n]*|(?m:^.*(?:빠진 디테일|용어|출처)\s*:.*$)', '', sec)
            body = '\n'.join('\n'.join(lines(h)[s:e] + owner(lines(h), min(s + 8, len(lines(h)) - 1))) for h, s, e in spans)
            flat = body.replace('_', '').lower()
            for tok in set(re.findall(r'`([^`\n]{3,90})`', sec)):
                for w in set(re.findall(r'[A-Za-z_][A-Za-z0-9_]{3,}', tok)):
                    if not re.search(r'[a-z]_[a-z]|[a-z][A-Z]|[A-Z][a-z]+[A-Z]', w) or CITE.search(tok): continue
                    if not known(w): out.append('이름  %s' % w)
                    elif spans and not a.no_support and w not in body and w.replace('_', '').lower() not in flat and tok in claims: out.append('지지  %s — %s' % (w, sec.strip().split('\n')[0][:50]))
        out = sorted(set(out)); bad += sum(1 for o in out if not o.startswith(('지지', '축약', '모호')))
        print('%s: 근거 %d · 파일 %d · 줄 %d · 이름 %d · 축약 %d · 모호 %d · 지지 %d' % (os.path.basename(fp), total, *[sum(o.startswith(k) for o in out) for k in ('파일', '줄', '이름', '축약', '모호', '지지')]))
        for o in out: print('  ' + o)
    sys.exit(1 if bad else 0)
main()

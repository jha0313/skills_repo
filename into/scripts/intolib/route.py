# -*- coding: utf-8 -*-
"""모드 · 유형 · 공개 여부 · 슬러그 판별."""
import hashlib
import os
import re

from . import TYPES

# ---------- 모드 ----------
EXACT = {
    'brief': 'brief', 'into': 'brief', '기본': 'brief', '요약': 'brief',
    'eli5': 'eli5', 'ste': 'ste', 'doc': 'doc', 'html': 'html', 'visualize': 'html', 'interactive': 'interactive', 'slides': 'slides',
    'test': 'test', 'quiz': 'test', 'shorts': 'shorts', 'video': 'video', 'domain-expert': 'domain-expert', 'domain': 'domain-expert',
}
# 앞에 있는 것이 이긴다 ("눌러 보는 html" → interactive, "슬라이드로 시각화" → slides)
LIKE = [
    ('domain-expert', ('도메인 전문가', '전문가 과정', '도메인', '커리큘럼', 'domain expert', 'domain knowledge')),
    ('interactive', ('눌러', '누르', '인터랙티브', '인터렉티브', '상황별', '따라가게', 'interactive', '해 보기', '해보기')),
    ('slides', ('슬라이드', '발표', 'slide', '장표', 'deck')),
    ('test', ('퀴즈', '테스트', '시험', '문제로', 'quiz')),
    ('shorts', ('쇼츠', '숏츠', 'shorts', '세로 영상')),
    ('video', ('긴 영상', '영상으로', '영상', '동영상')),
    ('html', ('시각화', '한 장으로', '한장', '그려', '그림으로', '구조도', 'visuali')),
    ('doc', ('문서', '도큐먼트', 'document')),
    ('ste', ('ste로', 'ste 방식', 'ste100', 'ste 로', '명확', '오해 없', '모호하지')),
    ('eli5', ('쉽게', '쉬운', 'eli5', '초보', '다섯 살', '처음 보는')),
    ('brief', ('기본 칸', '다섯 칸', '브리프')),
]


def find_mode(word):
    """사용자 말 → 모드 이름. 모르면 None."""
    w = re.sub(r'\s+', ' ', word or '').strip().lower()
    w = re.sub(r'^/?into\s+', '', w)
    if w in EXACT:
        return EXACT[w]
    bare = re.sub(r'(으로|로)$', '', w)
    if bare in EXACT:
        return EXACT[bare]
    for mode, keys in LIKE:
        if any(k in w for k in keys):
            return mode
    return None


# ---------- 유형 ----------
CODE_EXT = {'.rs', '.go', '.py', '.rb', '.java', '.kt', '.swift', '.c', '.cc', '.cpp', '.h', '.hpp', '.cs', '.php', '.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs',
            '.sql', '.sh', '.bash', '.zsh', '.lua', '.scala', '.dart', '.zig', '.ex', '.exs', '.vue', '.svelte', '.proto', '.tf', '.r', '.m', '.mm', '.pl'}
CONF_EXT = {'.toml', '.yaml', '.yml', '.json', '.jsonc', '.ini', '.cfg', '.conf', '.env', '.xml', '.bazel', '.bzl', '.nix', '.dockerfile', '.plist', '.css', '.scss', '.html', '.csv'}
MANIFESTS = ('Cargo.toml', 'package.json', 'pyproject.toml', 'go.mod', 'pom.xml', 'build.gradle', 'build.gradle.kts', 'MODULE.bazel', 'Gemfile', 'setup.py', 'CMakeLists.txt', 'Package.swift', 'composer.json')
FRONT = {'pr': 'pr', 'pull-request': 'pr', 'mr': 'pr', 'codebase': 'codebase', 'repo': 'codebase', 'design-doc': 'design-doc', 'rfc': 'design-doc', 'adr': 'design-doc', 'spec': 'design-doc',
         'paper': 'paper-concept', 'paper-concept': 'paper-concept', 'concept': 'paper-concept', 'video': 'video', 'transcript': 'video',
         'x-post': 'social-post', 'threads-post': 'social-post', 'thread': 'social-post', 'threads': 'social-post', 'social-post': 'social-post', 'tweet': 'social-post', 'bluesky-post': 'social-post',
         'community-post': 'community-post', 'forum': 'community-post', 'local-file': 'local-file', 'prompt': 'local-file', 'skill': 'skill', 'general': 'general'}

URLS = [
    ('pr', 12, r'github\.com/[^/\s]+/[^/\s]+/pull/\d+|/-?/?merge_requests/\d+|bitbucket\.org/.+/pull-requests/\d+', 'PR 주소'),
    ('paper-concept', 10, r'arxiv\.org|doi\.org|openreview\.net|aclanthology\.org|pnas\.org|nature\.com/articles|dl\.acm\.org|ncbi\.nlm\.nih\.gov|semanticscholar\.org|biorxiv\.org|\.pdf(?:$|[?#])', '논문 주소'),
    ('video', 10, r'youtube\.com/(?:watch|shorts|live)|youtu\.be/|vimeo\.com/|twitch\.tv/videos', '영상 주소'),
    ('social-post', 10, r'//(?:www\.|mobile\.)?(?:x|twitter)\.com/[^/\s]+/status|threads\.(?:net|com)/|bsky\.app/profile|linkedin\.com/posts|mastodon', '글타래 주소'),
    ('community-post', 10, r'news\.ycombinator\.com/item|reddit\.com/r/|lobste\.rs/s/|github\.com/[^/\s]+/[^/\s]+/discussions/|discourse|okky\.kr|stackoverflow\.com/q|gall\.dcinside|clien\.net|geeknews|news\.hada\.io', '커뮤니티 주소'),
    ('design-doc', 8, r'rfc-editor\.org|datatracker\.ietf\.org|peps\.python\.org|/(?:rfcs?|adrs?|design(?:-docs?)?|proposals?|specification)/', '설계 문서 주소'),
    ('codebase', 9, r'^https?://(?:www\.)?(?:github|gitlab)\.com/[^/\s]+/[^/\s]+/?(?:tree/[^\s]*)?$|^git@', '저장소 주소'),
]

CONTENT = {
    'pr': [(6, r'(?m)^diff --git "?a/', 'diff --git'), (3, r'(?m)^@@ -\d+(?:,\d+)? \+\d+', 'hunk 머리'), (2, r'변경 파일 목록|Files changed|Test Plan|병합 \d{4}-|PR #\d+', 'PR 본문 표지')],
    'design-doc': [(3, r'(?im)^#{1,4}\s.*\b(?:non-goals?|alternatives?(?: considered)?|rationale|backwards? compatibility|rejected ideas)\b|^#{1,4}\s.*(?:비목표|대안|검토한 안|결정 배경)', '대안·비목표 제목'),
                   (3, r'(?im)^#{1,4}\s.*\b(?:goals?|motivation|proposal|specification|decision|consequences|context|requirements|open questions)\b|^#{1,4}\s.*(?:목표|제안|결정|설계|요구 사항|열린 질문|미결)', '목표·제안·결정 제목'),
                   (2, r'(?i)^.{0,400}\b(?:RFC|ADR|PEP|SEP|design doc|specification|proposal)\b|^.{0,400}(?:설계 문서|기술 명세|명세|제안서)', '머리의 RFC·명세·제안'),
                   (2, r'(?im)^\W*status\W*[:|]\W*(?:accepted|proposed|draft|final|rejected|superseded)|^\W*상태\W*[:|]\W*(?:승인|제안|초안|확정)', '상태 줄')],
    'paper-concept': [(4, r'(?im)^\W*(?:abstract|초록|significance)\b', '초록'), (2, r'(?i)\bet al\.|\bReferences\b|참고문헌', '인용·참고문헌'), (3, r'(?i)\b10\.\d{4,9}/\S+|arXiv:\s?\d{4}\.\d{4,5}', 'DOI·arXiv'),
                      (2, r'(?i)\bp\s?[<=]\s?0?\.\d+|\b95% (?:CI|confidence)|\bbaseline\b|\bablation\b|\brandomized\b', '실험 말'), (2, r'(?im)^#{1,4}\s*(?:\d+\.?\s*)?(?:methods?|results|discussion|introduction|related work|experiments?|실험|결과|방법)\b', '논문 절')],
    'video': [(3, r'(?m)^\s*\[?\d{1,2}:\d{2}(?::\d{2})?\]?\s+\S', '시각 줄'), (3, r'(?i)자막|대본|스크립트|나레이션|transcript|\[데모\]|captions?', '자막·대본'), (3, r'-->\s*\d{2}:\d{2}', '자막 시간 줄'), (2, r'(?i)youtube|타임스탬프|구독|영상', '영상 말')],
    'social-post': [(4, r'(?m)^#{0,4}\s*\W*(?:스레드|트윗|post|tweet)?\s*\[?\d{1,2}/\d{1,2}\]?(?:\s|$|\W)', 'n/N 글 번호'), (4, r'(?im)^#{1,4}\s*(?:트윗|글|post|tweet)\s*#?\d{1,3}\b', '제목의 글 번호'), (3, r'(?i)x\.com/\S+/status|twitter\.com|threads\.(?:net|com)|bsky\.app', 'SNS 주소'), (2, r'(?i)리포스트|좋아요|retweet|스레드|thread|@[a-z0-9_]{3,}', 'SNS 말')],
    'community-post': [(4, r'(?im)^#{1,4}\s*(?:댓글|comment|답변|reply|top-level)\s*\d*', '댓글 제목'), (3, r'(?i)\b(?:Ask|Show|Tell) HN\b|news\.ycombinator|reddit\.com/r/|/r/\w+|discussions/\d+', '게시판'), (2, r'(?i)댓글 \d+|\d+ (?:comments|points|upvotes)|점수 \d+|대댓글|추천 \d+', '댓글·점수')],
    'local-file': [(3, r'(?m)^(?:import |from \S+ import |def |class |use |pub fn |fn |func |function |const |let |var |package |#!/|export )', '코드 줄'),
                   (3, r'(?im)^#{0,3}\s*(?:role|역할|instructions?|지시|output format|출력 형식|rules?|규칙|constraints?)\s*:?$|\bYou are an?\b|당신은 .{1,40}(?:이다|입니다)', '프롬프트 말')],
    'general': [],
}


def is_url(s):
    return bool(re.match(r'^(?:https?://|git@)', s))


def score_text(body, meta, name):
    """본문 → {유형: [(점수, 신호)]}"""
    sc = {t: [] for t in TYPES}
    ext = os.path.splitext(name)[1].lower()
    ft = FRONT.get((meta.get('type') or '').strip().lower())
    if ft:
        sc[ft].append((14 if ft == 'social-post' else 6, '머리말 type: %s' % meta['type']))      # 글타래를 모은 글에는 댓글·커뮤니티 말이 섞인다
    src = meta.get('source') or meta.get('url') or ''
    if src:
        for t, w, r, label in URLS:
            if re.search(r, src, re.I):
                sc[t].append((5, '머리말 source: ' + label))
                break
    if ext in ('.diff', '.patch'):
        sc['pr'].append((6, ext + ' 파일'))
    if ext in ('.srt', '.vtt'):
        sc['video'].append((9, ext + ' 자막 파일'))
    if ext == '.pdf':
        sc['paper-concept'].append((6, 'PDF 파일'))
    if ext in CODE_EXT:
        sc['local-file'].append((8, '코드 파일 ' + ext))
    elif ext in CONF_EXT or name in ('Dockerfile', 'Makefile', 'justfile'):
        sc['local-file'].append((7, '설정 파일 ' + (ext or name)))
    if name == 'SKILL.md':
        sc['skill'].append((9, 'SKILL.md 파일'))
    if meta.get('name') and meta.get('description'):
        sc['skill'].append((5, 'name·description 머리말'))
    if name in ('CLAUDE.md', 'AGENTS.md', 'GEMINI.md') or re.search(r'prompt|프롬프트', name, re.I):
        sc['local-file'].append((5, '지시문 파일 이름'))
    if re.search(r'(?:^|[-_.])(?:rfc|adr|prd|design|spec|proposal)(?:[-_.\d]|$)|설계|제안서', name, re.I):
        sc['design-doc'].append((3, '파일 이름'))
    if re.search(r'script|transcript|자막|대본', name, re.I) and ext in ('.md', '.txt'):
        sc['video'].append((2, '파일 이름'))
    probe = body[:60000]
    plain = re.sub(r'(?ms)^[ \t>]*(`{3,}|~{3,}).*?(?:^[ \t>]*\1[`~]*[ \t]*$|\Z)', ' ', probe)         # 인용한 코드가 유형을 정하지 않게
    if ext not in CODE_EXT and ext not in CONF_EXT:
        for t, rules in CONTENT.items():
            for w, r, label in rules:
                where = plain[:6000] if label.startswith('머리의') else plain
                n = len(re.findall(r, where))
                if not n:
                    continue
                if label in ('시각 줄', 'n/N 글 번호', '제목의 글 번호', '댓글 제목') and n < 3:
                    continue
                if label in ('코드 줄',) and n < 4:
                    continue
                if label == '자막·대본' and n < 2 or label == '영상 말' and n < 2 or label == 'SNS 말' and n < 2:
                    continue
                if label == '인용·참고문헌' and n < 3 or label == '실험 말' and n < 2 or label == '논문 절' and n < 2:
                    continue
                if label == '목표·제안·결정 제목' and n < 2:
                    continue
                sc[t].append((w + (1 if n >= 8 else 0), label + (' %d' % n if n > 1 else '')))
        if t_must(plain) >= 8:
            sc['design-doc'].append((3, 'MUST·SHOULD %d' % t_must(plain)))
    sc['general'].append((2, '기본'))
    return sc


def t_must(s):
    return len(re.findall(r'\b(?:MUST|SHOULD|MAY|SHALL)(?: NOT)?\b', s))


def score_dir(path, files):
    """폴더 → 점수표"""
    sc = {t: [] for t in TYPES}
    names = set(os.listdir(path))
    src = [f for f in files if os.path.splitext(f)[1].lower() in CODE_EXT]
    if 'SKILL.md' in names:
        sc['skill'].append((12, 'SKILL.md가 있는 폴더'))
    mans = [m for m in MANIFESTS if m in names]
    if '.git' in names:
        sc['codebase'].append((4, '.git'))
    if mans:
        sc['codebase'].append((4, '매니페스트 ' + ', '.join(mans[:3])))
    if len(src) > 20:
        sc['codebase'].append((6, '코드 파일 %d개(20개 초과)' % len(src)))
    elif src:
        sc['local-file'].append((5, '코드 파일 %d개(20개 이하)' % len(src)))
    elif files:
        sc['general'].append((3, '글 파일 폴더'))
    sc['general'].append((2, '기본'))
    return sc


def score_url(url):
    sc = {t: [] for t in TYPES}
    for t, w, r, label in URLS:
        if re.search(r, url, re.I):
            sc[t].append((w, label))
            break
    sc['general'].append((2, '기본'))
    return sc


def decide(sc):
    """점수표 → {'type','rank':[(유형, 점수, [신호])], 'tie': bool}

    규칙: 1위가 2위보다 3점 넘게 앞서면 정한다. 3점 이하로 비슷하고 둘 다 4점 이상이면 후보 둘을 낸다.
    """
    rank = sorted(((t, sum(w for w, _ in s), [x for _, x in sorted(s, key=lambda y: -y[0])]) for t, s in sc.items()), key=lambda r: (-r[1], TYPES.index(r[0])))
    a, b = rank[0], rank[1]
    tie = b[1] >= 4 and a[1] - b[1] <= 3
    return {'type': a[0], 'rank': [r for r in rank if r[1] > 0][:4], 'tie': tie}


# ---------- 공개 여부 ----------
# 누구나 보는 글만 있는 곳. 비공개 글도 있는 곳(github·gitlab·youtube·x·reddit …)은 주소만으로 모른다
PUBLIC_HOST = re.compile(r'^https?://(?:[\w\-]+\.)*(?:arxiv\.org|doi\.org|openreview\.net|aclanthology\.org|pnas\.org|nature\.com|dl\.acm\.org|ncbi\.nlm\.nih\.gov|biorxiv\.org|wikipedia\.org'
                         r'|bsky\.app|stackoverflow\.com/q(?:uestions)?|news\.ycombinator\.com|lobste\.rs|news\.hada\.io|rfc-editor\.org|ietf\.org|python\.org)(?:[/?#]|$)', re.I)


def public_of(meta, url, flag):
    """(공개인가, 근거) — 모르면 비공개."""
    if flag is not None:
        return flag, '사용자가 준 %s' % ('--public' if flag else '--private')
    p = (meta.get('public') or '').lower()
    if p in ('true', 'yes', 'public'):
        return True, '머리말 public: %s' % p
    if p in ('false', 'no', 'private'):
        return False, '머리말 public: %s' % p
    if PUBLIC_HOST.match(url or ''):
        return True, '알려진 공개 주소(로그인이 필요한 글이면 --private)'
    return False, '공개인지 모르는 주소(공개면 --public)' if url else '공개 표시가 없는 로컬 원문(공개면 --public)'


# ---------- 슬러그 ----------
def slugify(s, words=4):
    s = re.sub(r'\.[A-Za-z0-9]{1,5}$', '', s)
    parts = re.findall(r'[a-z0-9]+', s.lower())
    return '-'.join(parts[:words])[:48].strip('-')


def make_slug(inp, title, zone=''):
    base = ''
    if is_url(inp):
        m = re.search(r'(?:github|gitlab)\.com/([^/\s]+)/([^/\s]+?)(?:\.git)?(?:/(pull|discussions|issues|-/merge_requests)/(\d+))?(?:[/?#].*)?$', inp)
        if m:
            base = slugify('%s%s' % (m.group(2), '-' + {'pull': 'pr', '-/merge_requests': 'mr'}.get(m.group(3), m.group(3)) + m.group(4) if m.group(3) else ''), 5)
        else:
            base = slugify(title or '') or slugify(re.sub(r'^https?://(www\.)?', '', inp).replace('/', ' '), 4)
    else:
        p = os.path.abspath(inp).rstrip('/')
        name = os.path.basename(p)
        if name in ('SKILL.md', 'README.md', 'index.md', 'script.md'):
            name = os.path.basename(os.path.dirname(p)) or name
        base = slugify(name)
    if not base:
        base = slugify(title or '') or 'into-' + hashlib.sha1((title or inp).encode('utf-8')).hexdigest()[:6]
    if zone:
        base += '-' + (slugify(zone, 3) or 'zone-' + hashlib.sha1(zone.encode('utf-8')).hexdigest()[:4])
    return base

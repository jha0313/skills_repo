# -*- coding: utf-8 -*-
"""formats/<유형>.md 읽기와 문법 검사."""
import glob
import os
import re

from . import SKILL, SLOTS, UserError
from .text import FENCE, fix_josa, split_row

TEXT_HEAD = ['자리', '칸', '키', '형', '한도', '쓸 것']
HEADS = {
    'model': ['키', '형', '개수', '쓸 것'],
    'brief': TEXT_HEAD, 'eli5': TEXT_HEAD, 'ste': TEXT_HEAD, 'html': TEXT_HEAD, 'interactive': TEXT_HEAD, 'doc': TEXT_HEAD,
    'shorts': ['장면', '자리', '초', '말할 것', '화면'], 'video': ['장면', '자리', '초', '말할 것', '화면'],
    'slides': ['장', '자리', '제목에 담을 것', '주 그림', '쓸 것'],
    'test': ['문항', '자리', '종류', '쓸 것'],
}
NEED = ('model', 'eli5', 'ste', 'html', 'interactive', 'doc', 'shorts', 'video', 'slides', 'test')
TEXT_FORMS = ('line', 'list', 'steps', 'qa', 'quote', 'number', 'code')
PIC_FORMS = ('beforeafter', 'flow', 'map', 'lanes', 'timeline', 'ladder', 'positions', 'options', 'anatomy', 'chart')
PIC_NAMES = PIC_FORMS + ('claim',)          # 지시 줄 `그림:`에 쓰는 이름
# 그림 형이 읽는 모델 키
PIC_KEY = {'beforeafter': 'edges', 'flow': 'edges', 'map': 'zones', 'lanes': 'steps', 'timeline': 'chapters', 'ladder': 'claims',
           'positions': 'positions', 'options': 'options', 'anatomy': 'parts', 'chart': 'results'}


class Issue(object):
    def __init__(self, level, where, msg):
        self.level, self.where, self.msg = level, where, fix_josa(msg)

    def __str__(self):
        return '%s %s: %s' % (self.level, self.where, self.msg)


def formats_dir():
    return os.environ.get('INTO_FORMATS') or os.path.join(SKILL, 'formats')


def parse_limit(s):
    """'60!' '5×70' '4?' '60!~' → dict(n, chars, required, optional, free) — 못 읽으면 None
    ! 필수 · 없음 비면 `빠진 디테일`에 이름 · ? 비어도 되는 변형 칸(이름도 적지 않음) · ~ 비유·확인 질문처럼 근거 없이 되는 칸"""
    s = (s or '').strip().replace('`', '')
    m = re.match(r'^(?:≤\s*)?(\d[\d,]*)?\s*(?:[×xX*]\s*(\d[\d,]*))?\s*(?:자|개|행|줄)?\s*([!?~]{0,3})$', '' if s in ('—', '-') else s)
    if not m or (m.group(2) and not m.group(1)):
        return None
    num = lambda x: int(x.replace(',', '')) if x else None
    fl = m.group(3)
    if len(set(fl)) != len(fl) or ('!' in fl and '?' in fl):
        return None
    return {'n': num(m.group(1)), 'chars': num(m.group(2)), 'required': '!' in fl, 'optional': '?' in fl, 'free': '~' in fl}


def parse_count(s):
    """'1–4' '3' '≤5' '0-6' → (최소, 최대) — 못 읽으면 None"""
    s = (s or '').strip().replace('`', '').replace('!', '')
    if s in ('', '—', '-'):
        return (0, None)
    m = re.match(r'^(\d+)\s*[–\-~∼]\s*(\d+)$', s)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    m = re.match(r'^(?:≤|최대)\s*(\d+)$', s)
    if m:
        return (0, int(m.group(1)))
    m = re.match(r'^(\d+)\s*\+$', s)
    if m:
        return (int(m.group(1)), None)
    m = re.match(r'^(\d+)$', s)
    return (int(m.group(1)), int(m.group(1))) if m else None


def parse_form(s):
    """'table:a,b' → ('table', ['a','b'])  'kit:x' → ('kit', ['x'])  'line' → ('line', [])"""
    s = (s or '').strip().strip('`')
    if s.startswith('table:'):
        return 'table', [c.strip() for c in re.split(r'[,，]', s[6:]) if c.strip()]
    if s.startswith('kit:'):
        return 'kit', [s[4:].strip()]
    return s, []


def parse_fields(form):
    """'list{what,before,after,src}' → ('list', [필드 이름], {필드: [고를 값]}, {생략 가능한 필드})"""
    s = (form or '').strip().replace('`', '')
    m = re.match(r'^([a-z가-힣]+)?\s*(?:[\[({]+(.*?)[\])}]+)?$', s, re.S)
    if not m:
        return None
    kind, inner, names, enums, opt = m.group(1) or 'list', m.group(2) or '', [], {}, set()
    for part in re.findall(r'[^,"]*(?:"[^"]*"[^,"]*)*', inner):
        part = part.strip()
        if not part:
            continue
        k = re.match(r'^([a-z_A-Z]+)(\?)?\s*(?:[:=]\s*(.*))?$', part)
        if not k:
            return None
        names.append(k.group(1))
        if k.group(2):
            opt.add(k.group(1))
        if k.group(3) and '|' in k.group(3):
            enums[k.group(1)] = [v.strip().strip('"\'') for v in k.group(3).strip('"\'').split('|')]
    return kind, names, enums, opt


class Section(object):
    def __init__(self, name, line):
        self.name, self.line, self.directives, self.header, self.rows, self.text = name, line, {}, None, [], []


class Spec(object):
    """formats 파일 하나."""

    def __init__(self, path):
        self.path = path
        self.type = self.name = ''
        self.directives, self.sections, self.errors = {}, {}, []
        self._parse()

    @property
    def stem(self):
        return os.path.splitext(os.path.basename(self.path))[0]

    @property
    def questions(self):
        return [q.strip() for q in re.split(r'\s+·\s+|·', self.directives.get('질문', '')) if q.strip()]

    @property
    def pic(self):
        return self.directives.get('그림', '').strip().strip('`').split(' ')[0]

    def _parse(self):
        try:
            lines = open(self.path, encoding='utf-8').read().split('\n')
        except (OSError, UnicodeDecodeError) as e:
            raise UserError('formats 파일을 읽지 못했다: %s (%s)' % (os.path.basename(self.path), e.__class__.__name__))
        m = re.match(r'^#\s+`?([a-z_][a-z0-9_-]*)`?\s+[—–-]\s+(.+?)\s*$', lines[0] if lines else '')
        if m:
            self.type, self.name = m.group(1), m.group(2)
        else:
            self.errors.append(('FAIL', 1, '첫 줄을 `# <유형> — <사람 이름>`으로 쓴다'))
        cur, fence, table_done, in_table = None, False, False, False
        for no, ln in enumerate(lines[1:], 2):
            if FENCE.match(ln):
                fence = not fence
            if not fence:
                h = re.match(r'^##\s+(.+?)\s*$', ln)
                if h:
                    name = h.group(1).split(' ')[0].strip('`')
                    if name in self.sections:
                        self.errors.append(('FAIL', no, '절 `## %s`이 두 번 나온다' % name))
                    cur = self.sections[name] = Section(name, no)
                    table_done = in_table = False
                    continue
                row = ln.lstrip().startswith('|')
                if cur is not None and row and not table_done and not fence:
                    cells = split_row(ln)
                    if cur.header is None:
                        cur.header, in_table = [c.strip('`* ') for c in cells], True
                    elif set(''.join(cells)) <= set('-: '):
                        pass
                    else:
                        cur.rows.append((no, cells))
                    continue
                if in_table and not row:
                    in_table, table_done = False, True
                d = re.match(r'^-\s+([가-힣A-Za-z ]{1,12})\s*[:：]\s*(.+)$', ln)
                if d and (cur is None or (cur.header is None)):
                    (self.directives if cur is None else cur.directives)[d.group(1).strip()] = d.group(2).strip()
                    continue
            if cur is not None:
                cur.text.append(ln)

    # ----- 쓰는 쪽 -----
    def rows(self, mode):
        """글 모드 표 → [{slot,label,key,form,cols,n,chars,required,hint,line}]"""
        sec = self.sections.get(mode)
        if sec is None or sec.header is None:
            return None
        out = []
        for no, c in sec.rows:
            c = c + [''] * (6 - len(c))
            form, cols = parse_form(c[3])
            lim = parse_limit(c[4]) or {'n': None, 'chars': None, 'required': False, 'optional': False, 'free': False}
            out.append({'slot': c[0].strip('` '), 'label': c[1].strip(), 'key': c[2].strip('` '), 'form': form, 'cols': cols, 'limit': c[4],
                        'n': lim['n'], 'chars': lim['chars'], 'required': lim['required'], 'optional': lim['optional'], 'free': lim['free'] or form == 'qa',
                        'hint': c[5], 'line': no})
        return out

    def model_rows(self):
        sec = self.sections.get('model')
        out = []
        for no, c in (sec.rows if sec else []):
            c = c + [''] * (4 - len(c))
            f = parse_fields(c[1]) or ('list', [], {}, set())
            out.append({'key': c[0].strip('` '), 'form': c[1], 'kind': f[0], 'fields': f[1], 'enums': f[2], 'opt': f[3],
                        'count': parse_count(c[2]) or (0, None), 'hint': c[3], 'line': no})
        return out

    def plain_rows(self, mode):
        sec = self.sections.get(mode)
        if sec is None or sec.header is None:
            return None
        return [dict(zip(sec.header, c + [''] * (len(sec.header) - len(c)))) for _, c in sec.rows]

    def note(self, mode):
        sec = self.sections.get(mode)
        return sec.directives.get('참고', '') if sec else ''


_cache = {}


def load(type_):
    path = os.path.join(formats_dir(), type_ + '.md')
    if not os.path.exists(path):
        raise UserError('formats/%s.md가 없다. `into.py types`로 있는 유형을 보고 --type을 고친다' % type_)
    key = (path, os.path.getmtime(path))
    if key not in _cache:
        _cache[key] = Spec(path)
    return _cache[key]


def common():
    path = os.path.join(formats_dir(), '_common.md')
    if not os.path.exists(path):
        raise UserError('formats/_common.md가 없다')
    return Spec(path)


def exists(type_):
    return os.path.exists(os.path.join(formats_dir(), type_ + '.md'))


def mode_rows(type_, mode):
    """(행 목록, Spec) — brief는 유형 파일에 없으면 _common의 것이고 그림 칸은 그 유형 eli5의 그림을 따른다."""
    sp = load(type_)
    rows = sp.rows(mode)
    if rows is None and mode == 'brief':
        figs = [dict(r, limit=r['limit'].rstrip('!'), required=False) for r in sp.rows('eli5') or [] if r['slot'] == 'pic' and r['form'] in PIC_FORMS]
        rows = [x for r in common().rows('brief') for x in (figs if figs and r['slot'] == 'pic' else [r])]
    if rows is None:
        raise UserError('formats/%s.md에 `## %s` 표가 없다. 표를 더하거나 다른 모드를 쓴다' % (type_, mode))
    return rows, sp


def length_limit(type_, mode, size):
    """보이는 글자 한도. 절의 `- 길이: 700` 또는 `- 길이: 450/700/900`이 공통 한도를 덮는다."""
    from . import SIZES
    idx = SIZES.index(size)
    if exists(type_):
        sec = load(type_).sections.get(mode)
        if sec is not None and sec.directives.get('길이'):
            ns = [int(x.replace(',', '')) for x in re.findall(r'\d[\d,]*', sec.directives['길이'])]
            if ns:
                return ns[min(idx, len(ns) - 1)] if len(ns) > 1 else ns[0]
    for _, c in common().sections['길이'].rows:
        if c[0].strip('` ') == mode:
            return int(re.sub(r'\D', '', c[idx + 1]))
    return None


def all_types():
    out = []
    for p in sorted(glob.glob(os.path.join(formats_dir(), '*.md'))):
        if not os.path.basename(p).startswith('_'):
            out.append(Spec(p))
    from . import TYPES
    return sorted(out, key=lambda s: (TYPES.index(s.stem) if s.stem in TYPES else 99, s.stem))


# ---------- 문법 검사 ----------
def validate(path):
    sp, out = Spec(path), []
    base = os.path.basename(path)

    def add(level, line, msg):
        out.append(Issue(level, '%s:%d' % (base, line), msg))
    for lv, line, msg in sp.errors:
        add(lv, line, msg)
    if sp.type and sp.type != sp.stem:
        add('FAIL', 1, '첫 줄의 유형 `%s`이 파일 이름 `%s`과 다르다' % (sp.type, sp.stem))
    qs = sp.questions
    if not sp.directives.get('질문'):
        add('FAIL', 2, '`- 질문: 하나 · 둘 · 셋` 줄을 첫 줄 아래에 쓴다')
    elif len(qs) != 3:
        add('FAIL', 2, '질문이 %d개다. ` · `로 나눠 셋을 쓴다' % len(qs))
    if not sp.pic:
        add('FAIL', 2, '`- 그림: <부품>` 줄을 쓴다')
    elif sp.pic not in PIC_NAMES:
        add('WARN', 2, '그림 `%s`은 부품 이름에 없다(%s)' % (sp.pic, '·'.join(PIC_NAMES)))
    for n in NEED:
        if n not in sp.sections:
            add('FAIL', 1, '`## %s` 절이 없다' % n)
    if '예' not in sp.sections:
        add('WARN', 1, '`## 예` 절이 없다(실제 출력 예 하나)')
    model_keys = set()
    for name, sec in sp.sections.items():
        if name == '예':
            continue
        if name not in HEADS:
            add('WARN', sec.line, '모르는 절 `## %s` — 스크립트가 읽지 않는다' % name)
            continue
        want = HEADS[name]
        if sec.header is None:
            if not (name == 'model' and re.search(r'없음|없다|그대로', '\n'.join(sec.text))):
                add('FAIL', sec.line, '`## %s`에 표가 없다. 열: %s' % (name, ' | '.join(want)))
            continue
        if sec.header != want:
            add('FAIL', sec.line, '`## %s` 표의 열이 다르다: 지금 `%s` → `%s`' % (name, ' | '.join(sec.header), ' | '.join(want)))
            continue
        for no, c in sec.rows:
            if len(c) != len(want):
                add('FAIL', no, '칸이 %d개다(열 %d개). 칸 안의 세로줄은 `\\|`로 쓴다' % (len(c), len(want)))
        if name == 'model':
            for no, c in sec.rows:
                key = c[0].strip('` ')
                if not re.match(r'^[a-z][a-z0-9_]*$', key):
                    add('FAIL', no, '키 `%s`를 영문 소문자로 쓴다' % key)
                if key in model_keys:
                    add('FAIL', no, '키 `%s`가 두 번 나온다' % key)
                model_keys.add(key)
                if len(c) > 1 and parse_fields(c[1]) is None:
                    add('FAIL', no, '형 `%s`을 `list{필드,필드,src}` 꼴로 쓴다' % c[1])
                if len(c) > 2 and parse_count(c[2]) is None:
                    add('FAIL', no, '개수 `%s`를 `1–4`·`3`·`≤5` 꼴로 쓴다' % c[2])
        elif want is TEXT_HEAD:
            _validate_text(name, sec, add)
        else:
            _validate_scenes(name, sec, add)
    return out


def _validate_text(name, sec, add):
    last, seen, slots = -1, set(), set()
    for no, c in sec.rows:
        if len(c) != 6:
            continue
        slot, label, key, form, lim = c[0].strip('` '), c[1], c[2].strip('` '), c[3], c[4]
        if slot not in SLOTS:
            add('FAIL', no, '자리 `%s`를 one·why·pic·run·catch 중 하나로 쓴다' % slot)
        else:
            if SLOTS.index(slot) < last:
                add('FAIL', no, '자리 순서가 어긋난다: `%s` 앞에 더 뒤 자리가 있다(one→why→pic→run→catch)' % slot)
            last = max(last, SLOTS.index(slot))
            slots.add(slot)
        if not label:
            add('FAIL', no, '칸 이름이 비었다')
        if not re.match(r'^[a-z][a-z0-9_]*$', key):
            add('FAIL', no, '키 `%s`를 영문 소문자로 쓴다' % key)
        if key in seen:
            add('FAIL', no, '키 `%s`가 이 절에 두 번 나온다' % key)
        if key in ('missing', 'source', 'title', 'scope', 'f', 't'):
            add('FAIL', no, '키 `%s`는 스크립트가 쓰는 이름이다. 다른 이름을 쓴다' % key)
        seen.add(key)
        f, cols = parse_form(form)
        if f == 'table' and not cols:
            add('FAIL', no, '`table:` 뒤에 열 이름을 `table:열1,열2`로 쓴다')
        elif f == 'kit':
            if name not in ('html', 'interactive'):
                add('FAIL', no, '`kit:`은 html·interactive에서만 쓴다')
            elif not cols[0]:
                add('FAIL', no, '`kit:` 뒤에 부품 이름을 쓴다')
        elif f not in TEXT_FORMS + PIC_FORMS + ('table',):
            add('FAIL', no, '형 `%s`을 모른다(%s·table:·kit:)' % (form, '·'.join(TEXT_FORMS + PIC_FORMS)))
        pl = parse_limit(lim)
        if pl is None:
            add('FAIL', no, '한도 `%s`를 `60`·`5×70`·`4!`(필수)·`4?`(비어도 됨)·`60~`(근거 없이 됨) 꼴로 쓴다' % lim)
        elif f in ('list', 'steps') and pl['n'] and not pl['chars']:
            add('FAIL', no, '%s의 한도는 `개수×글자 수`다: `%s`' % (f, lim))
        elif f in ('line', 'quote', 'number') and pl['chars']:
            add('FAIL', no, '%s의 한도는 글자 수 하나다: `%s`' % (f, lim))
    for s in SLOTS:
        if s not in slots and sec.rows:
            add('WARN', sec.line, '`## %s`에 `%s` 자리가 없다' % (name, s))
    if '길이' in sec.directives and not re.match(r'^[\d,]+(?:\s*/\s*[\d,]+){0,2}\s*자?$', sec.directives['길이']):
        add('FAIL', sec.line, '`- 길이:`를 `700` 또는 `450/700/900`으로 쓴다')


def _validate_scenes(name, sec, add):
    last = -1
    for no, c in sec.rows:
        if len(c) != len(sec.header):
            continue
        slot = c[1].strip('` ')
        if slot in SLOTS:
            if SLOTS.index(slot) < last and name != 'test':
                add('WARN', no, '자리 순서가 어긋난다: `%s`' % slot)
            last = max(last, SLOTS.index(slot))
        elif slot not in ('hook', '훅', 'outro', '마무리', 'intro', '인트로', '표지', 'cover', 'close', '—', '-', ''):
            add('FAIL', no, '자리 `%s`를 one·why·pic·run·catch(또는 hook·outro)로 쓴다' % slot)
        if name == 'test' and not re.search(r'choice|predict', c[2]):
            add('FAIL', no, '종류 `%s`를 choice 또는 predict로 쓴다' % c[2])


def validate_common():
    out = []
    sp = common()
    if '길이' not in sp.sections or not sp.sections['길이'].rows:
        out.append(Issue('FAIL', '_common.md:1', '`## 길이` 표가 없다'))
    else:
        for no, c in sp.sections['길이'].rows:
            if len(c) != 4 or not all(re.search(r'\d', x) for x in c[1:]):
                out.append(Issue('FAIL', '_common.md:%d' % no, '`모드 | 작음 | 보통 | 큼` 네 칸에 숫자를 쓴다'))
    if sp.rows('brief') is None:
        out.append(Issue('FAIL', '_common.md:1', '`## brief` 표가 없다'))
    return out


def validate_all():
    """(파일 수, [Issue])"""
    out, n = validate_common(), 0
    for p in sorted(glob.glob(os.path.join(formats_dir(), '*.md'))):
        if os.path.basename(p).startswith('_'):
            continue
        n += 1
        out += validate(p)
    return n, out

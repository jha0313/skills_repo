# -*- coding: utf-8 -*-
"""into가 쓰는 모듈 (Python 3.9+, 표준 라이브러리만).

text     글자 세기 · 숫자 · 조건어 · 비밀 값 · 문장 나누기   (모든 글자 세기는 text.count / text.count_result)
formats  formats/*.md 읽기 · 문법 검사
cite     원문 접근(파일 · diff · 폴더)과 근거(path:line, raw:n, [mm:ss], n/N) 대조
route    모드 · 유형 · 공개 여부 · 슬러그 판별
pack     원문에서 세는 결정적 사실
model    model.json 검사
cells    <mode>.json 검사 (모든 모드 공통)
textmodes  brief · eli5 · ste · doc 렌더
quiz     test 렌더      script  shorts · video 렌더
lint     JSON 없이 만든 결과 검사 · ste 린터
htmlmodes  html · interactive · slides 렌더 (KIT)

htmlmodes 계약 — into.py가 부르는 것
  MODES = ('html', 'interactive', 'slides')
  render(mode, ctx) -> str                 HTML 문서 전체
  check(mode, ctx) -> [(수준, 위치, 문구)]   (선택) 수준은 'FAIL'·'WARN'. 칸·한도·숫자 검사는 cells가 이미 했다
ctx (dict)
  type, type_name, pic, questions   formats에서 온 유형 정보
  mode, size                        size = 작음 | 보통 | 큼
  title, scope, notice              notice = 비공개 안내 한 줄('' 이면 공개)
  model                             model.json (steps는 목록, order는 model['order']로 정리된 것)
  rows                              그 모드 표의 행 [{slot,label,key,form,limit,required,hint,fields}] (자리 순서)
  cells                             {키: 정리된 값}. 글 칸은 [{'t','f',...}], 그림 칸은 고른 모델 항목의 목록
  refs                              {id: 모델 항목}  (facts·nodes·edges·유형별 목록)
  cite(ids) -> str                  id 목록 → '근거' 글 ('a.rs:10-20 · b.rs:3')
  missing, source                   '빠진 디테일'·'출처' 줄에 넣을 글 (빈 칸 이름까지 붙은 것)
  order_note                        '순서: 원문에 없음'(order가 빔) · '순서: 없음'(order:"none") · ''
  assets                            assets/ 폴더 경로
  raw_cells                         에이전트가 쓴 <mode>.json 그대로
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(os.path.dirname(HERE))
ASSETS = os.path.join(SKILL, 'assets')

SLOTS = ('one', 'why', 'pic', 'run', 'catch')
DOC_TITLES = {'one': 'TL;DR', 'why': '왜 중요한가', 'pic': 'High-level design', 'run': 'Low-level design', 'catch': 'Insights'}
TYPES = ('pr', 'codebase', 'design-doc', 'paper-concept', 'video', 'social-post', 'community-post', 'local-file', 'skill', 'general')
MODES = ('brief', 'eli5', 'ste', 'html', 'interactive', 'doc', 'slides', 'test', 'shorts', 'video', 'domain-expert')
TEXT_MODES = ('brief', 'eli5', 'ste', 'doc')
HTML_MODES = ('html', 'interactive', 'slides')
NOTICE = '비공개 원문 기반 — 공유 전 이름·경로 확인'
SIZES = ('작음', '보통', '큼')


class UserError(Exception):
    """사용자에게 한 줄로 보이는 오류 (무엇을 어떻게 고치라)."""


def put(path, text):
    """파일 쓰기. 심볼릭 링크는 따라가지 않는다."""
    if os.path.islink(path):
        raise UserError('쓸 자리가 심볼릭 링크다: %s. 링크를 옮기고 다시 부른다' % path)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)

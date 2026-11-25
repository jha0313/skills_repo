# pr — PR
- 질문: 전과 후 · 왜 · 조심
- 그림: beforeafter

## model

| 키 | 형 | 개수 | 쓸 것 |
|---|---|---|---|
| changes | list{id,what,before,after,src} | 1–4 | 바뀐 것 |
| cases | list{id,input,before,after,same?,src} | 0–5 | 상황 |

## eli5
| 자리 | 칸 | 키 | 형 | 한도 | 쓸 것 |
|---|---|---|---|---|---|
| one | 한 줄 | one | line | 60! | 요지 |
| why | 왜 | why | line | 80 | 이유 |
| pic | 상황 | input | line | 45? | 입력 |
| pic | 전 → 후 | pic | beforeafter | 8! | 그림 |
| run | 어떻게 | run | steps | 3×85 | 순서 |
| catch | 조심 | catch | list | 3×75 | 조심 |
| catch | 규모 | size | line | 45 | 규모 |

## ste
| 자리 | 칸 | 키 | 형 | 한도 | 쓸 것 |
|---|---|---|---|---|---|
| one | 결론 | one | line | 110! | 조건 → 동작 |
| why | 이유 | why | list | 2×70 | 이유 |
| pic | 전 → 후 | pic | beforeafter | 8 | 그림 |
| run | 조건과 결과 | cases | table:입력,전,후 | 5×90 | 표 |
| catch | 주의 | catch | list | 4×80 | 주의 |

## html
| 자리 | 칸 | 키 | 형 | 한도 | 쓸 것 |
|---|---|---|---|---|---|
| one | 한 줄 | one | line | 110! | eli5 그대로 |
| why | 왜 | why | line | 80 | eli5 그대로(줄이지 않는다) |
| pic | 전 → 후 | pic | beforeafter | 8! | 그림 |
| run | 어떻게 | run | steps | 3×60 | 순서 |
| catch | 조심 | catch | list | 3×70 | 조심 |

## interactive
| 자리 | 칸 | 키 | 형 | 한도 | 쓸 것 |
|---|---|---|---|---|---|
| one | 한 줄 | one | line | 110! | 요지 |
| why | 왜 | why | line | 80 | 이유 |
| pic | 전 → 후 | pic | beforeafter | 8! | 그림 |
| run | 고르기 | cases | table:입력,전,후 | 5×90 | 표 |
| catch | 조심 | catch | list | 3×70 | 조심 |

## doc
| 자리 | 칸 | 키 | 형 | 한도 | 쓸 것 |
|---|---|---|---|---|---|
| one | TL;DR | one | list | 3×100! | 요지 |
| why | 왜 중요한가 | why | list | 3×100 | 이유 |
| pic | 전과 후 | pic | beforeafter | 8 | 그림 |
| run | Low-level design | steps | steps | 8×110 | 순서 |
| catch | Insights | insights | list | 5×110 | 조심 |

## shorts
| 장면 | 자리 | 초 | 말할 것 | 화면 |
|---|---|---|---|---|
| 1 | hook | 4 | 질문 | 입력 |
| 2 | one | 8 | 한 줄 | 글 |
| 3 | pic | 8 | 그림 | 그림 |

## video
| 장면 | 자리 | 초 | 말할 것 | 화면 |
|---|---|---|---|---|
| 1 | hook | 20 | 질문 | 입력 |
| 2 | one | 25 | 한 줄 | 글 |
| 3 | pic | 60 | 그림 | 그림 |

## slides
| 장 | 자리 | 제목에 담을 것 | 주 그림 | 쓸 것 |
|---|---|---|---|---|
| 1 | cover | 제목 | — | 한 줄 |
| 2 | pic | 그림 | flow | 하나 |

## test
| 문항 | 자리 | 종류 | 쓸 것 |
|---|---|---|---|
| 1 | one | choice | 요지 |
| 2 | run | predict | 예측 |

## 예
(시험용)

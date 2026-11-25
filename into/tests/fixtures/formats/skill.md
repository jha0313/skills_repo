# skill — 에이전트 스킬
- 질문: 언제 · 어떻게 · 왜
- 그림: lanes

## model

| 키 | 형 | 개수 | 쓸 것 |
|---|---|---|---|
| lanes | list | 1–4 | 레인 |
| steps | list{id,lane,do,out?,src} | 2–8 | 단계 |
| triggers | list{say,route,src} | 0–4 | 부르는 말 |

## eli5
| 자리 | 칸 | 키 | 형 | 한도 | 쓸 것 |
|---|---|---|---|---|---|
| one | 한 줄 | one | line | 60! | 요지 |
| why | 왜 | why | list | 2×70 | 이유 |
| pic | 한 번 돌 때 | pic | lanes | 8! | 레인 |
| run | 순서 | run | steps | 4×60 | 순서 |
| catch | 조심 | catch | list | 3×60 | 조심 |
| catch | 언제 | triggers | table:이렇게 말하면,이렇게 | 4×60 | 표 |

## ste
| 자리 | 칸 | 키 | 형 | 한도 | 쓸 것 |
|---|---|---|---|---|---|
| one | 한 줄 | one | line | 60! | 요지 |
| why | 왜 | why | list | 2×70 | 이유 |
| pic | 어떻게 되나 | pic | lanes | 6 | 그림 |
| run | 순서 | run | steps | 4×60 | 순서 |
| catch | 조심 | catch | list | 3×60 | 조심 |

## html
| 자리 | 칸 | 키 | 형 | 한도 | 쓸 것 |
|---|---|---|---|---|---|
| one | 한 줄 | one | line | 60! | 요지 |
| why | 왜 | why | list | 2×70 | 이유 |
| pic | 어떻게 되나 | pic | lanes | 6 | 그림 |
| run | 순서 | run | steps | 4×60 | 순서 |
| catch | 조심 | catch | list | 3×60 | 조심 |

## interactive
| 자리 | 칸 | 키 | 형 | 한도 | 쓸 것 |
|---|---|---|---|---|---|
| one | 한 줄 | one | line | 60! | 요지 |
| why | 왜 | why | list | 2×70 | 이유 |
| pic | 어떻게 되나 | pic | lanes | 6 | 그림 |
| run | 순서 | run | steps | 4×60 | 순서 |
| catch | 조심 | catch | list | 3×60 | 조심 |

## doc
| 자리 | 칸 | 키 | 형 | 한도 | 쓸 것 |
|---|---|---|---|---|---|
| one | TL;DR | one | list | 3×100! | 요지 |
| why | 왜 중요한가 | why | list | 3×100 | 이유 |
| pic | High-level design | pic | lanes | 8 | 그림 |
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

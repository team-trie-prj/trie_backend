# 질의 검색 프롬프트 인젝션 필터 — vikira 연동 가이드

> 시스템 프롬프트 인젝션 1차 필터(F11)를 **vikira 검색·보고서 질의**에도 적용하는 방법.
> **vikira 코드는 전혀 수정하지 않는다.** 김예담 소유 미들웨어를 앞단에 두는 방식.

## 배경 / 문제

- 사용자 질의(text)는 vikira `POST /api/v1/search`(멀티모달·에이전트·검색)와 `POST /api/v1/reports`(보고서)로 들어간다.
- 이 질의는 결국 LLM 프롬프트에 합쳐지므로 **프롬프트 인젝션 통로**가 된다.
- 그러나 검색/보고서는 vikira 소유이고 **수정하면 안 된다.**
- 업로드 문서(RAG 간접 주입)는 이미 `POST /documents`(김예담)에서 필터되지만, **질의(직접 주입)** 경로는 별도 대응이 필요했다.

## 해결 — 비침투 ASGI 미들웨어 (채택)

김예담 소유 미들웨어 `PromptInjectionMiddleware` 를 앱에 등록해, 요청이 **vikira 라우트 핸들러에 닿기 전에** 질의를 1차 필터한다.

```
[프론트] ──POST /api/v1/search──> [PromptInjectionMiddleware(김예담)] ──통과 시 원문 그대로──> [vikira /search]
                                          │ 인젝션 의심 시
                                          └──> 400 차단 (vikira 미도달)
```

- **파일**: [app/security/injection_middleware.py](../app/security/injection_middleware.py)
- **등록**: `app.add_middleware(PromptInjectionMiddleware)` ([app/main.py](../app/main.py)) — vikira 라우터는 그대로.
- **대상 경로**: `POST /api/v1/search`, `/api/v1/search/analyze`, `/api/v1/reports`
- **질의 추출**: `multipart`/`x-www-form-urlencoded` 의 `text`, `application/json` 의 `query`(또는 `text`)
- **동작**: 규칙 스캔([prompt_guard.py](../app/security/prompt_guard.py)) → 의심 시 `400` 차단, 정상 시 **버퍼링한 원문 body 를 그대로 재생**하여 vikira 로 전달(무손실).
- **토글**: `PROMPT_INJECTION_FILTER_ENABLED`(기본 on). 업로드 필터와 공용 스위치.
- **Fail-open**: 본문 파싱 실패 시 통과(검색 가용성 우선; 형식 검증은 vikira 담당).

### 차단 응답 (vikira 경로이므로 `{detail}` 형식 유지)

```json
{
  "detail": "프롬프트 인젝션 의심 질의가 차단되었습니다.",
  "code": "PROMPT_INJECTION_BLOCKED",
  "matches": ["instruction_override_ko", "prompt_leak_ko"]
}
```

> 프론트는 `code == "PROMPT_INJECTION_BLOCKED"` 로 인젝션 차단을 구분할 수 있다.

## 방식 비교

| 방식 | vikira 수정 | 강제성 | 비고 |
| --- | --- | --- | --- |
| **① 미들웨어(채택)** | ❌ 불필요 | ✅ 서버단 강제 | 앞단 차단, 무손실 통과 |
| ② 프론트가 `/security/prompt-check` 선호출 | ❌ 불필요 | ⚠️ 프론트 의존 | 우회 가능(프론트가 안 부르면 무력) |
| ③ vikira 가 `scan_text` 직접 호출 | ✅ 필요 | ✅ 강제 | 가장 근본적이나 vikira 수정 필요(범위 밖) |

- **①**을 기본 채택(서버단 강제 + 비침투). **②**는 UX(즉시 피드백)용으로 병행 가능.
- 심층 **2차(LLM 기반)** 탐지가 필요하면 vikira 파이프라인에서 `app.security.prompt_guard` 재사용 또는 별도 모델 도입 — vikira 협의 필요(범위 밖).

## 검증

- 단위/통합: [tests/test_search_guard.py](../tests/test_search_guard.py) — urlencoded/multipart/json 질의 차단 + 정상 통과 + 비대상 경로 무영향.
- 라이브: 인젝션 질의 → `400 PROMPT_INJECTION_BLOCKED`, 정상 질의 → vikira 검색 정상 수행.

## 프론트엔드 연동 요약

1. (선택) 입력 즉시 UX 피드백: `POST /security/prompt-check` 로 사전 검사.
2. 실제 검색: `POST /api/v1/search` 호출 — 서버 미들웨어가 최종 강제 필터. `400 && code=="PROMPT_INJECTION_BLOCKED"` 이면 "부적절한 질의" 안내.

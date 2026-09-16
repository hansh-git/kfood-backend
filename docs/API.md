# 백엔드 API 명세 (김현수 담당분)

모든 요청: 로그인 상태면 `Authorization: Bearer <supabase access_token>` 헤더 포함.
토큰이 없으면 body의 `profile`로 분석만 하고 DB 저장은 하지 않음(비로그인 체험 / 로컬 테스트).

## 전체 흐름

```
[촬영] → POST /ocr → menus[]
       → POST /analyze (menus) → results[] (메뉴별 재료·비율·위험도·직원질문)
            ├ WARNING : 필수 재료에서 걸림 → 바로 경고
            ├ CAUTION : 가게마다 다른 재료 → staff_questions 표시
            │     → 직원에게 질문 화면/TTS(ko-KR) → 직원 답변(버튼 or 음성)
            │     → (음성이면) POST /stt language=ko → text
            │     → POST /qna/confirm → 갱신된 risk
            └ SAFE
       → 추가 궁금증: POST /qna
[프로필] → GET /profile/card → 직원에게 보여줄 한국어 카드
```

## POST /ocr
multipart `file` (jpeg/png/webp/heic, 최대 15MB — 서버에서 3MB 이하로 자동 압축)
```json
{"text": "짬뽕 9,000\n짜장면 7,000", "menus": [{"name": "짬뽕", "price": "9,000"}], "origin_info": ["돼지고기: 국내산"]}
```

## POST /analyze
```json
{"menus": [{"name": "짬뽕", "price": "9,000"}], "ocr_text": null, "scan_image_url": null,
 "profile": {"allergies": {"새우": "심각"}, "religious_diet": "halal", "vegetarian_type": null, "preferred_language": "en"}}
```
응답(요약)
```json
{
  "scan_log_id": "uuid | null",
  "profile_applied": true,
  "results": [{
    "menu": "짬뽕", "menu_translated": "...", "description_translated": "...",
    "base_menu": "짬뽕", "resolved_variant": null, "variant_options": ["해물짬뽕","고기짬뽕","차돌짬뽕"],
    "matched_menu_db": true,
    "ingredients": [
      {"name": "밀가루 면", "name_translated": "wheat noodles", "tags": ["wheat"], "ratio_percent": 42.1, "certainty": "confirmed", "source": "menu_db"},
      {"name": "새우", "tags": ["shrimp"], "ratio_percent": 8.0, "certainty": "possible", "source": "variant", "variant": "해물짬뽕"}
    ],
    "risk": {
      "level": "CAUTION",
      "confirmed_reasons": [],
      "possible_reasons": [{"kind": "allergy", "tag": "shrimp", "label": "shrimp", "ingredient": "새우", "certainty": "possible", "severity": "심각"}],
      "needs_confirmation": true,
      "staff_questions": [{"ingredient": "새우", "tag": "shrimp", "kind": "contains",
                           "ko": "짬뽕에 새우가 들어가나요?", "user_lang": "en", "translated": "Does the 짬뽕 contain shrimp?"}],
      "notes": []
    }
  }],
  "disclaimer": "..."
}
```
- `certainty`: confirmed(필수) / possible(가게마다 다름) / excluded(직원이 없다고 확인)
- 위험도는 LLM이 아니라 `app/services/dietary_rules.py` 규칙이 계산 → 테스트로 정확도 검증 가능

## POST /qna
`{"scan_log_id": "...", "menu_result": {...results[i]}, "question": "How spicy is it?", "input_type": "text"}`
→ `{"answer": "...", "staff_question_ko": "많이 맵나요? | null"}`

## POST /qna/confirm
`{"menu_result": {...}, "question": {"ingredient": "새우", "tag": "shrimp", "kind": "contains"}, "staff_answer": "새우는 안 들어가요", "input_type": "voice"}`
→ `{"verdict": "no", "summary_translated": "...", "result": {...risk 재계산된 menu_result}}`
- `staff_answer`가 "예"/"아니요"면 LLM 호출 없이 처리 (프론트 버튼용)

## POST /stt
multipart `file`(webm/m4a/mp3/wav), form `language`(기본 ko) → `{"text": "..."}`
TTS는 프론트 `speechSynthesis` + `lang: 'ko-KR'` 사용.

## GET /profile/card (로그인 필수) · POST /profile/card/preview
```json
{"staff": {"lang": "ko", "title": "저는 아래 음식을 먹을 수 없습니다", "lines": ["알레르기: 땅콩 (심각 — 소량도 위험)", "할랄 (이슬람 식단): 동물성 젤라틴, 술(맛술·미림 포함), 돼지고기", "인증되지 않은 고기도 먹지 않습니다"], "closing": "..."},
 "user": {"lang": "en", "...": "..."}, "empty": false}
```

## 프로필 값 규약 (한석호·프론트와 합의 필요)
- `allergies`: `{"이름": "심각|경미"}` 또는 `["이름"]`. 이름은 식약처 22종 한글명 또는 영문(peanut, shellfish…) — `app/services/taxonomy.py` ALLERGY_ALIASES
- `religious_diet`: `halal | kosher | hindu | none`
- `vegetarian_type`: `vegan | vegetarian | lacto | ovo | pescatarian | none`
- `preferred_language`: `ko | en | zh | ja`


## 재료 데이터 소스 (우선순위)
1. **메뉴젠** (농촌진흥청 국립식량과학원, 공공데이터포털) — `app/data/menuzen_menus.json`
   - 같은 계열 레시피를 비교: 70% 이상에 있는 재료 → confirmed, 일부에만 있는 재료 → possible(직원 질문)
   - `ratio_percent`는 실제 중량(g) 기반 (`ratio_source: "menuzen"`)
   - 갱신: `.env`에 `MENUZEN_API_KEY` 입력 후 `python -m scripts.fetch_menuzen`
2. **자체 메뉴 DB** `app/data/menu_base.json` — 메뉴젠에 없는 부산 향토음식 보완
3. **AI 추론** — 둘 다 없을 때
- 응답 `results[].data_source`: `menuzen` | `menu_base` | `ai`, `results[].family`: 비교에 쓴 레시피 이름

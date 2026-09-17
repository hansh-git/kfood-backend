# Claude 프로젝트 지식용 컨텍스트 (이 파일을 claude.ai 프로젝트 파일에 업로드)

## 프로젝트
외국인 관광객용 부산 음식 성분 필터링 웹앱 (2026 캡스톤). 메뉴판 촬영 → OCR → 재료 추론 → 알레르기·할랄·비건 위험도.
스택: React+Vite(Vercel) / FastAPI(Render) / Supabase(Auth·Postgres·Storage) / Groq.
레포: https://github.com/VALLACK/kfood-backend  작업 브랜치: feat/analyze-v2 (PR #1 위에 쌓음)

## 역할
- 김현수(나): /ocr, /analyze, /qna, /stt, Groq 파이프라인
- 한석호: DB 스키마·RLS·필터링·배포 / 남태욱: 기획·API 규격 / 김유경·유동민: 프론트

## 설계 원칙
1. LLM은 재료+태그+비율만 출력, 위험도는 dietary_rules.py 규칙이 계산 (재현성·테스트)
2. 메뉴 기준 DB(app/data/menu_base.json): required=confirmed → WARNING 먼저, variants/hidden=possible → CAUTION + 직원 질문
3. 직원 답변 → /qna/confirm → certainty confirmed/excluded 또는 certified → 재판정
4. 로그인 요청은 사용자 JWT로 Supabase 호출(RLS 적용), 비로그인은 body profile로 분석만
5. Groq 모델명은 .env (vision: qwen/qwen3.6-27b, text: openai/gpt-oss-120b, stt: whisper-large-v3-turbo)

## 교수 피드백 → 반영
- 성분 퍼센트: ratio_percent(추정)
- 프로필을 종업원에게: GET /profile/card (고정 템플릿 한국어)
- 짬뽕처럼 주재료 다른 메뉴: 위 원칙 2·3 + TTS(프론트 speechSynthesis ko-KR) / STT(/stt)

## 남은 일
- menu_base.json 팀 검수·메뉴 확대, 실제 메뉴판 30장으로 OCR 정확도 측정
- 프로필 값 규약 합의(docs/API.md 하단), 08_menu_items 테이블 도입 여부
- Render 배포 시 CORS_ORIGINS에 Vercel 주소 추가

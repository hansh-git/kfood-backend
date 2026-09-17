# routers/analyze.py
import os, json
from pathlib import Path
from fastapi import APIRouter
from pydantic import BaseModel
from dotenv import load_dotenv
from groq import Groq
from supabase import create_client

load_dotenv(dotenv_path=Path(__file__).parent.parent.parent / ".env")
router = APIRouter()

supabase = create_client(
    os.environ.get("SUPABASE_URL"),
    os.environ.get("SUPABASE_KEY")
)

class AnalyzeRequest(BaseModel):
    ocr_text: str
    profile_id: str | None = None

PROMPT_TEMPLATE = """
너는 한국 음식 성분 분석 전문가야. 아래는 한국 음식점 메뉴판을 OCR로 읽은 텍스트야.

메뉴판 텍스트:
{ocr_text}

사용자 정보:
- 알레르기: {allergies}
- 종교 식단: {religion}
- 채식 성향: {diet}

각 메뉴 항목에 대해 다음 JSON 배열 형식으로만 응답해줘. 다른 텍스트는 절대 포함하지 마. 마크다운 코드블록도 쓰지 마.

[
  {{
    "menu": "메뉴 이름",
    "ingredients": ["주요 재료1", "재료2"],
    "hidden": ["숨겨진 재료 (액젓, 육수 등)"],
    "allergens": ["해당 알레르기 성분"],
    "contains_pork": true,
    "contains_alcohol": false,
    "risk": {{
      "level": "SAFE 또는 CAUTION 또는 WARNING",
      "reasons": ["위험 이유 (없으면 빈 배열)"]
    }}
  }}
]

risk level 기준:
- WARNING: 사용자 알레르기 성분 포함 / 할랄인데 돼지고기·알코올 포함 / 비건인데 육류·유제품·달걀 포함
- CAUTION: 숨겨진 재료로 문제 성분 포함 가능성 / 베지테리언인데 달걀·유제품 포함
- SAFE: 문제 없음
"""

@router.post("/analyze")
async def analyze_menu(body: AnalyzeRequest):
    print("=== /analyze 호출됨 ===")
    print("profile_id:", body.profile_id)

    # Supabase에서 프로필 조회
    allergies = "없음"
    religion = "없음"
    diet = "없음"

    if body.profile_id:
        try:
            res = supabase.table("profiles").select("*").eq("id", body.profile_id).single().execute()
            profile = res.data
            if profile:
                if profile.get("allergies"):
                    allergies = ", ".join(profile["allergies"])
                if profile.get("religion"):
                    religion = profile["religion"]
                if profile.get("diet"):
                    diet = profile["diet"]
            print(f"프로필 로드 — 알레르기: {allergies}, 종교: {religion}, 식단: {diet}")
        except Exception as e:
            print("프로필 조회 실패:", e)

    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

    prompt = PROMPT_TEMPLATE.format(
        ocr_text=body.ocr_text,
        allergies=allergies,
        religion=religion,
        diet=diet,
    )

    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2000,
        temperature=0.1
    )

    raw_text = response.choices[0].message.content or ""
    print("Analyze 결과:", raw_text[:100])

    try:
        raw_text = raw_text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        results = json.loads(raw_text)
    except Exception as e:
        return {"results": [], "error": str(e), "raw": raw_text}

    # scan_logs 저장
    for item in results:
        supabase.table("scan_logs").insert({
            "menu_name": item.get("menu", ""),
            "result": item
        }).execute()

    return {"results": results}
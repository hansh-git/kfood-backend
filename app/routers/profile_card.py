"""피드백 1: 내 식단 제약을 종업원에게 보여주는 카드.

LLM 번역 대신 고정 템플릿 → 오역 위험 없음. 프론트는 전체화면 큰 글씨로 띄우거나 TTS로 읽어줌.
"""
from fastapi import APIRouter, Depends

from app.core.auth import AuthContext, require_auth
from app.models.schemas import ProfileInput
from app.services.dietary_rules import DIET_RULES, RELIGIOUS_RULES, DietProfile
from app.services.profile_service import load_profile_row
from app.services.taxonomy import label

router = APIRouter(prefix="/profile", tags=["profile"])

SEVERITY = {
    "심각": {"ko": "심각 — 소량도 위험", "en": "severe — even a trace is dangerous", "zh": "严重——微量也危险", "ja": "重度——微量でも危険"},
    "severe": {"ko": "심각 — 소량도 위험", "en": "severe — even a trace is dangerous", "zh": "严重——微量也危险", "ja": "重度——微量でも危険"},
    "경미": {"ko": "경미", "en": "mild", "zh": "轻微", "ja": "軽度"},
    "mild": {"ko": "경미", "en": "mild", "zh": "轻微", "ja": "軽度"},
}
T = {
    "title": {"ko": "저는 아래 음식을 먹을 수 없습니다", "en": "I cannot eat the following", "zh": "我不能吃以下食物", "ja": "私は以下の食べ物を食べられません"},
    "allergy": {"ko": "알레르기", "en": "Allergy", "zh": "过敏", "ja": "アレルギー"},
    "halal": {"ko": "할랄 (이슬람 식단)", "en": "Halal", "zh": "清真", "ja": "ハラール"},
    "kosher": {"ko": "코셔 (유대교 식단)", "en": "Kosher", "zh": "犹太洁食", "ja": "コーシャ"},
    "hindu": {"ko": "힌두교 식단", "en": "Hindu diet", "zh": "印度教饮食", "ja": "ヒンドゥー教の食事"},
    "verify": {"ko": "인증되지 않은 고기도 먹지 않습니다", "en": "I also avoid non-certified meat", "zh": "也不吃未经认证的肉", "ja": "認証のない肉も食べません"},
    "diet": {"ko": "채식", "en": "Vegetarian type", "zh": "素食", "ja": "菜食"},
    "broth": {"ko": "고기·멸치 육수, 액젓, 젓갈도 포함됩니다", "en": "This includes meat/anchovy broth, fish sauce and jeotgal", "zh": "包括肉汤、鳀鱼汤、鱼露和咸鱼酱", "ja": "肉・煮干しの出汁、魚醤、塩辛も含みます"},
    "closing": {"ko": "이 재료가 들어가는지 알려주세요. 감사합니다!", "en": "Please tell me if the dish contains these. Thank you!", "zh": "请告诉我菜里是否含有这些。谢谢！", "ja": "これらが入っているか教えてください。ありがとうございます！"},
}


def _lines(p: DietProfile, raw_allergies, lang: str) -> dict:
    lines = []
    if p.allergy_tags:
        # 태그 단위로 묶어 표기 (심각도는 태그별)
        items = [f"{label(t, lang)} ({SEVERITY.get(s, {}).get(lang, s)})" if s and s != "unknown" else label(t, lang)
                 for t, s in p.allergy_tags.items()]
        lines.append(f"{T['allergy'][lang]}: " + ", ".join(items))
    if p.unmapped_allergies:
        lines.append(f"{T['allergy'][lang]}: " + ", ".join(p.unmapped_allergies))
    rel = RELIGIOUS_RULES.get(p.religious_diet or "")
    if rel:
        lines.append(f"{T[p.religious_diet][lang]}: " + ", ".join(label(t, lang) for t in sorted(rel["forbidden"])))
        if rel["verify"]:
            lines.append(T["verify"][lang])
    diet = DIET_RULES.get(p.vegetarian_type or "")
    if diet:
        lines.append(f"{T['diet'][lang]} ({p.vegetarian_type}): " + ", ".join(label(t, lang) for t in sorted(diet)))
        lines.append(T["broth"][lang])
    return {"title": T["title"][lang], "lines": lines, "closing": T["closing"][lang]}


def build_card(p: DietProfile, raw_allergies=None) -> dict:
    user_lang = p.preferred_language if p.preferred_language in ("ko", "en", "zh", "ja") else "en"
    return {
        "staff": {"lang": "ko", **_lines(p, raw_allergies, "ko")},     # 종업원에게 보여줄 면 (TTS: ko-KR)
        "user": {"lang": user_lang, **_lines(p, raw_allergies, user_lang)},  # 본인 확인용
        "empty": p.is_empty(),
    }


@router.get("/card")
def my_card(auth: AuthContext = Depends(require_auth)):
    row = load_profile_row(auth)
    return build_card(DietProfile.from_row(row), row.get("allergies"))


@router.post("/card/preview")
def preview_card(profile: ProfileInput):
    """프로필 설정 화면에서 저장 전 미리보기 / 비로그인 체험용."""
    return build_card(DietProfile.from_row(profile.model_dump()), profile.allergies)

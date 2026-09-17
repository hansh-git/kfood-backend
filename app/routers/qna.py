"""대화형 질의응답 + 종업원 확인(피드백 2: 주재료가 가게마다 다른 메뉴)."""
import json

from fastapi import APIRouter, Depends

from app.core.auth import AuthContext, optional_auth
from app.core.config import settings
from app.models.schemas import ConfirmRequest, QnaRequest
from app.services import groq_service
from app.services.analysis_service import LANG_NAMES, re_evaluate
from app.services.profile_service import resolve_profile

router = APIRouter(prefix="/qna", tags=["qna"])

QNA_SYSTEM = """You help a foreign tourist understand a Korean dish using ONLY the analysis JSON given.
If the analysis cannot answer with certainty (e.g. varies by restaurant), say so and write ONE short
polite question in Korean the tourist can show or play (TTS) to the staff.
Reply JSON: {"answer": "<in LANG>", "staff_question_ko": "<Korean question or null>"}"""

CONFIRM_SYSTEM = """Classify a restaurant staff member's Korean reply to a yes/no question about a dish.
Reply JSON: {"answer": "yes" | "no" | "unknown", "summary_translated": "<one sentence in LANG>"}
"yes" means the ingredient IS used (or, for certification questions, the meat IS certified)."""


def _save_log(auth, scan_log_id, question, answer, input_type):
    if auth and scan_log_id:
        auth.client.table("qna_logs").insert({
            "scan_log_id": scan_log_id, "question_text": question,
            "answer_text": answer, "input_type": input_type,
        }).execute()


def _pick_variant(answer: str, options: list[str], menu: str | None, lang: str) -> str:
    """직원 답변에서 변형 메뉴 선택. 버튼 값이면 바로, 자연어면 LLM으로 분류.
    '그 외'(기본 메뉴)를 고르면 변형 재료가 모두 제외된다."""
    if answer in options:
        return answer
    hits = [o for o in options if o in answer]
    if len(hits) == 1:
        return hits[0]
    data = groq_service.chat_json(settings.GROQ_TEXT_MODEL, [
        {"role": "system", "content": 'Pick which dish variant the Korean staff reply refers to. Reply JSON: {"answer": "<one option exactly> | unknown"}'},
        {"role": "user", "content": f"Dish: {menu}\nOptions: {options}\nStaff reply: {answer}"},
    ], max_tokens=100)
    picked = data.get("answer", "unknown")
    return picked if picked in options else "unknown"


@router.post("")
def ask(body: QnaRequest, auth: AuthContext | None = Depends(optional_auth)):
    profile, _ = resolve_profile(auth, body.profile)
    lang = LANG_NAMES.get(profile.preferred_language, "English")
    data = groq_service.chat_json(settings.GROQ_TEXT_MODEL, [
        {"role": "system", "content": QNA_SYSTEM.replace("LANG", lang)},
        {"role": "user", "content": f"Analysis:\n{json.dumps(body.menu_result, ensure_ascii=False)}\n\nQuestion: {body.question}"},
    ], max_tokens=800)
    answer = data.get("answer", "")
    _save_log(auth, body.scan_log_id, body.question, answer, body.input_type)
    return {"answer": answer, "staff_question_ko": data.get("staff_question_ko")}


@router.post("/confirm")
def confirm_with_staff(body: ConfirmRequest, auth: AuthContext | None = Depends(optional_auth)):
    """직원 답변을 받아 해당 재료의 certainty를 갱신하고 위험도를 다시 계산."""
    profile, _ = resolve_profile(auth, body.profile)
    lang = LANG_NAMES.get(profile.preferred_language, "English")
    q = body.question

    answer = body.staff_answer.strip()
    updated = json.loads(json.dumps(body.menu_result))  # deep copy
    summary = None

    if q.kind == "variant":
        verdict = _pick_variant(answer, q.options, body.menu_result.get("menu"), lang)
        if verdict != "unknown":
            for ing in updated.get("ingredients", []):
                if ing.get("source") == "variant":
                    ing["certainty"] = "confirmed" if ing.get("variant") == verdict else "excluded"
                    ing["confirmed_by_staff"] = True
            updated["resolved_variant"] = verdict
    else:
        quick = {"예": "yes", "네": "yes", "yes": "yes", "아니요": "no", "아니오": "no", "no": "no"}
        if answer.lower() in quick:
            verdict = quick[answer.lower()]
        else:
            data = groq_service.chat_json(settings.GROQ_TEXT_MODEL, [
                {"role": "system", "content": CONFIRM_SYSTEM.replace("LANG", lang)},
                {"role": "user", "content": f"Dish: {body.menu_result.get('menu')}\nQuestion was about: {q.ingredient} ({q.kind})\nStaff reply: {answer}"},
            ], max_tokens=300)
            verdict, summary = data.get("answer", "unknown"), data.get("summary_translated")

        for ing in updated.get("ingredients", []):
            if ing.get("name") != q.ingredient:
                continue
            if q.kind == "contains":
                if verdict == "yes":
                    ing["certainty"] = "confirmed"
                elif verdict == "no":
                    ing["certainty"] = "excluded"
            elif verdict in ("yes", "no"):  # halal_meat / kosher_meat
                ing["certified"] = verdict == "yes"
            ing["confirmed_by_staff"] = verdict != "unknown"

    result = re_evaluate(updated, profile)
    _save_log(auth, body.scan_log_id, f"[staff] {q.ingredient or '/'.join(q.options)}/{q.kind}", answer, body.input_type)
    return {"verdict": verdict, "summary_translated": summary, "result": result}

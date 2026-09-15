from fastapi import APIRouter, Form, HTTPException, UploadFile

from app.core.config import settings
from app.services.groq_service import get_client

router = APIRouter(tags=["speech"])

MAX_AUDIO = 25 * 1024 * 1024


@router.post("/stt")
def speech_to_text(file: UploadFile, language: str = Form("ko")):
    """음성 → 텍스트 (Groq Whisper). 직원 답변은 language=ko, 관광객 질문은 사용자 언어.

    TTS(질문 읽어주기)는 프론트에서 브라우저 speechSynthesis(lang='ko-KR')로 처리 — 무료·지연 없음.
    """
    data = file.file.read()
    if not data:
        raise HTTPException(status_code=400, detail="빈 오디오 파일입니다.")
    if len(data) > MAX_AUDIO:
        raise HTTPException(status_code=413, detail="오디오 파일이 너무 큽니다(최대 25MB).")
    res = get_client().audio.transcriptions.create(
        file=(file.filename or "audio.webm", data),
        model=settings.GROQ_STT_MODEL,
        language=language,
        response_format="json",
        temperature=0.0,
    )
    return {"text": res.text, "language": language}

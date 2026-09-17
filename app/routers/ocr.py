import base64
import io

from fastapi import APIRouter, HTTPException, UploadFile
from PIL import Image, ImageOps

from app.core.config import settings
from app.services import groq_service

router = APIRouter(tags=["ocr"])

ALLOWED = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}

OCR_PROMPT = """이 이미지는 한국 음식점 메뉴판(또는 원산지 표시판)이다.
보이는 텍스트를 추출해서 아래 JSON 하나로만 답해라.
{"raw_text": "<보이는 텍스트 전체, 줄바꿈 유지>",
 "menus": [{"name": "<메뉴명>", "price": "<가격 문자열 또는 null>"}],
 "origin_info": ["<원산지 표시 문구, 없으면 빈 배열>"]}
- 메뉴명 오타·인식 오류는 자연스러운 한국 음식명으로 교정
- 가게 이름, 영업시간, 안내 문구는 menus에 넣지 말 것"""


def _compress(data: bytes) -> tuple[bytes, str]:
    """Groq base64 이미지 한도(4MB) 대응: 긴 변 1600px, JPEG 재인코딩."""
    if len(data) <= settings.MAX_IMAGE_BYTES:
        try:
            Image.open(io.BytesIO(data)).verify()
        except Exception:
            raise HTTPException(status_code=400, detail="이미지를 읽을 수 없습니다.")
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    img.thumbnail((1600, 1600))
    quality = 85
    while True:
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        if buf.tell() <= settings.MAX_IMAGE_BYTES or quality <= 40:
            return buf.getvalue(), "image/jpeg"
        quality -= 15


@router.post("/ocr")
def extract_text(file: UploadFile):
    if file.content_type not in ALLOWED:
        raise HTTPException(status_code=415, detail=f"지원하지 않는 형식입니다: {file.content_type}")
    data = file.file.read()
    if len(data) > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="이미지가 너무 큽니다(최대 15MB).")

    data, mime = _compress(data)
    b64 = base64.b64encode(data).decode()

    result = groq_service.chat_json(
        settings.GROQ_VISION_MODEL,
        [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
            {"type": "text", "text": OCR_PROMPT},
        ]}],
        max_tokens=2000,
        reasoning_format="hidden",  # qwen 계열 추론 텍스트 숨김 (미지원 모델이면 자동 제거 후 재시도)
    )
    menus = [m for m in result.get("menus", []) if isinstance(m, dict) and m.get("name")]
    raw = result.get("raw_text") or "\n".join(m["name"] for m in menus)
    return {
        "text": raw,  # 기존 프론트 호환
        "menus": menus,
        "origin_info": result.get("origin_info", []),
    }

# routers/ocr.py
import base64, os
from pathlib import Path
from fastapi import APIRouter, UploadFile
from dotenv import load_dotenv
from groq import Groq

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")
router = APIRouter()

@router.post("/ocr")
async def extract_text(file: UploadFile):
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

    contents = await file.read()
    b64 = base64.b64encode(contents).decode()
    mime_type = file.content_type or "image/jpeg"

    response = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{b64}"
                        }
                    },
                    {
                        "type": "text",
                        "text": "이 이미지에서 텍스트를 모두 추출해줘. 메뉴판이면 메뉴 이름과 가격을 포함해서 보이는 텍스트를 그대로 출력해줘. 한국 음식 메뉴판이므로 오타나 인식 오류가 있을 경우 자연스러운 한국 음식 이름으로 교정해줘. 다른 설명 없이 텍스트만 출력해."
                    }
                ]
            }
        ],
        max_tokens=1000
    )

    text = response.choices[0].message.content or ""
    print("OCR 결과:", text)
    return {"text": text}
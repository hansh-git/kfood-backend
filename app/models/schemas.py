from typing import Literal
from pydantic import BaseModel, Field

Lang = Literal["ko", "en", "zh", "ja"]


class ProfileInput(BaseModel):
    """비로그인 체험/로컬 테스트용. 로그인 시에는 DB profiles 값을 사용한다."""
    allergies: dict[str, str] | list[str] | None = None
    religious_diet: str | None = None       # halal | kosher | hindu | none
    vegetarian_type: str | None = None      # vegan | vegetarian | lacto | ovo | pescatarian | none
    preferred_language: Lang = "en"


class MenuLine(BaseModel):
    name: str
    price: str | None = None


class AnalyzeRequest(BaseModel):
    ocr_text: str | None = None
    menus: list[MenuLine] | None = Field(default=None, description="/ocr 응답의 menus를 그대로 넘기면 OCR 텍스트 재파싱을 생략")
    scan_image_url: str | None = None
    profile: ProfileInput | None = None


class QnaRequest(BaseModel):
    scan_log_id: str | None = None
    menu_result: dict = Field(description="/analyze results[] 중 하나")
    question: str
    input_type: Literal["text", "voice"] = "text"
    profile: ProfileInput | None = None


class StaffQuestion(BaseModel):
    """/analyze staff_questions[] 항목을 그대로 넘기면 된다."""
    kind: Literal["contains", "variant", "halal_meat", "kosher_meat"] = "contains"
    ingredient: str | None = None
    tag: str | None = None
    options: list[str] = []


class ConfirmRequest(BaseModel):
    """종업원 답변 반영 → 위험도 재계산."""
    scan_log_id: str | None = None
    menu_result: dict
    question: StaffQuestion
    staff_answer: str = Field(description="종업원 답변(한국어). /stt 결과 텍스트 또는 예/아니오 버튼 값")
    input_type: Literal["text", "voice"] = "voice"
    profile: ProfileInput | None = None

from fastapi import HTTPException

from app.core.auth import AuthContext
from app.models.schemas import ProfileInput
from app.services.dietary_rules import DietProfile


def load_profile_row(auth: AuthContext) -> dict:
    res = (auth.client.table("profiles").select("*")
           .eq("user_id", auth.user_id).limit(1).execute())
    if not res.data:
        raise HTTPException(status_code=404, detail="프로필이 없습니다. 프로필 설정을 먼저 완료하세요.")
    return res.data[0]


def resolve_profile(auth: AuthContext | None, override: ProfileInput | None) -> tuple[DietProfile, dict | None]:
    """로그인 사용자는 DB 프로필, 비로그인은 요청 body의 profile 사용."""
    if auth:
        row = load_profile_row(auth)
        return DietProfile.from_row(row), row
    return DietProfile.from_row(override.model_dump() if override else None), None

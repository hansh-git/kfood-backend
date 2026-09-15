"""Supabase Auth 토큰 검증 의존성.

프론트는 supabase.auth.getSession()의 access_token을
`Authorization: Bearer <token>` 헤더로 보낸다.
"""
from dataclasses import dataclass
from fastapi import Header, HTTPException
from supabase import Client

from app.db.supabase_client import get_user_client, require_supabase


@dataclass
class AuthContext:
    user_id: str
    token: str
    client: Client  # RLS가 적용되는 사용자 전용 클라이언트


def _extract_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Authorization 헤더 형식은 'Bearer <token>' 이어야 합니다.")
    return token


def _verify(token: str) -> AuthContext:
    require_supabase()
    try:
        res = require_supabase().auth.get_user(token)
        user = res.user if res else None
    except Exception:
        user = None
    if not user:
        raise HTTPException(status_code=401, detail="유효하지 않거나 만료된 토큰입니다.")
    return AuthContext(user_id=user.id, token=token, client=get_user_client(token))


async def optional_auth(authorization: str | None = Header(default=None)) -> AuthContext | None:
    """토큰이 있으면 검증, 없으면 None (비로그인 체험/로컬 테스트용)."""
    token = _extract_token(authorization)
    return _verify(token) if token else None


async def require_auth(authorization: str | None = Header(default=None)) -> AuthContext:
    token = _extract_token(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    return _verify(token)

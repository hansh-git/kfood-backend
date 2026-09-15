import logging
import os

from dotenv import load_dotenv
from fastapi import HTTPException
from supabase import create_client, Client

load_dotenv()
log = logging.getLogger("uvicorn.error")

SUPABASE_URL: str | None = os.environ.get("SUPABASE_URL") or None
SUPABASE_KEY: str | None = os.environ.get("SUPABASE_KEY") or None

# 키가 없어도 서버는 뜨게 한다 (비로그인 분석·테스트는 가능, DB 기능만 비활성)
supabase: Client | None = None
if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
else:
    log.warning("SUPABASE_URL/SUPABASE_KEY 미설정 — 로그인·DB 저장 기능이 비활성화됩니다. .env를 확인하세요.")


def require_supabase() -> Client:
    if supabase is None:
        raise HTTPException(status_code=503, detail="Supabase 설정(.env)이 없어 DB 기능을 사용할 수 없습니다.")
    return supabase


def get_user_client(access_token: str) -> Client:
    """로그인 사용자의 JWT를 실어 보내는 클라이언트 (RLS 적용). 요청마다 새로 생성."""
    require_supabase()
    client = create_client(SUPABASE_URL, SUPABASE_KEY)
    client.postgrest.auth(access_token)
    return client

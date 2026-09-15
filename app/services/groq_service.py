"""Groq 호출 공통 모듈 — 재시도, JSON 파싱, 추론 텍스트 제거."""
import json
import re
import time
from functools import lru_cache

from fastapi import HTTPException
from groq import Groq, APIStatusError, APIConnectionError, RateLimitError

from app.core.config import settings


@lru_cache
def get_client() -> Groq:
    if not settings.GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY가 설정되지 않았습니다.")
    return Groq(api_key=settings.GROQ_API_KEY)


_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def parse_json(text: str):
    text = _THINK_RE.sub("", text or "").strip()
    text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # 앞뒤 잡음이 섞였을 때 첫 { 또는 [ 부터 마지막 } 또는 ] 까지 잘라서 재시도
        m = re.search(r"[\{\[].*[\}\]]", text, re.DOTALL)
        if m:
            return json.loads(m.group(0))
        raise


def chat_json(model: str, messages: list[dict], max_tokens: int = 3000, retries: int = 2, **extra) -> dict:
    """JSON object 모드로 호출하고 dict를 반환. 429/5xx/파싱 실패 시 재시도."""
    client = get_client()
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            kwargs = dict(model=model, messages=messages, max_tokens=max_tokens, temperature=0.1,
                          response_format={"type": "json_object"}, **extra)
            try:
                resp = client.chat.completions.create(**kwargs)
            except APIStatusError as e:
                # 모델이 특정 옵션(reasoning_format 등)을 지원하지 않으면 옵션 빼고 재호출
                if e.status_code == 400 and extra:
                    for k in extra:
                        kwargs.pop(k, None)
                    resp = client.chat.completions.create(**kwargs)
                else:
                    raise
            return parse_json(resp.choices[0].message.content or "")
        except (RateLimitError, APIConnectionError) as e:
            last_err = e
        except APIStatusError as e:
            if e.status_code < 500:
                raise HTTPException(status_code=502, detail=f"Groq 요청 오류: {e.message}")
            last_err = e
        except (json.JSONDecodeError, ValueError) as e:
            last_err = e
        time.sleep(1.5 * (attempt + 1))
    raise HTTPException(status_code=502, detail=f"AI 응답 처리 실패: {last_err}")

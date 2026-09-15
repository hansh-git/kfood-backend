"""메뉴 기준 DB (필수 재료 / 숨은 재료 / 변형 메뉴).

지금은 app/data/menu_base.json을 읽는다. 추후 Supabase menu_items 테이블로 옮기면
load_menu_base()만 바꾸면 된다 (supabase/migrations/08_menu_items_proposal.sql 참고).
"""
import json
import re
from functools import lru_cache
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "menu_base.json"


@lru_cache
def load_menu_base() -> dict[str, dict]:
    with open(DATA_PATH, encoding="utf-8") as f:
        return json.load(f)["menus"]


def normalize(name: str) -> str:
    name = re.sub(r"\(.*?\)|\[.*?\]", "", name or "")
    name = re.sub(r"[\d,.\s원₩~\-:/]+", "", name)
    return name.strip()


def match_menu(menu_name: str) -> tuple[str, dict] | None:
    """정확 일치 → 별칭 일치 → 가장 긴 이름이 포함된 경우 순으로 매칭."""
    db = load_menu_base()
    target = normalize(menu_name)
    if not target:
        return None
    candidates: list[tuple[int, str]] = []
    for key, item in db.items():
        names = [key, *item.get("aliases", [])]
        for n in names:
            if target == n:
                return key, item
            if n and n in target:
                candidates.append((len(n), key))
    if not candidates:
        return None
    _, key = max(candidates)
    return key, db[key]


def build_known_ingredients(menu_name: str) -> dict | None:
    """메뉴명으로 DB 재료 목록을 만든다.

    - required → certainty=confirmed
    - 메뉴명에 변형 키워드가 있으면(예: '해물짬뽕') 그 변형 재료도 confirmed
    - 변형이 특정되지 않으면(그냥 '짬뽕') 모든 변형 재료를 possible로 → 직원에게 질문
    - hidden → possible
    """
    matched = match_menu(menu_name)
    if not matched:
        return None
    key, item = matched
    target = normalize(menu_name)
    ingredients: list[dict] = [
        {**i, "certainty": "confirmed", "source": "menu_db"} for i in item.get("required", [])
    ]

    variants = item.get("variants", [])
    selected = [v for v in variants if any(kw in target for kw in v.get("keywords", []))]
    # 키워드가 겹치면 가장 긴 키워드를 가진 변형 우선
    if len(selected) > 1:
        selected.sort(key=lambda v: max(len(k) for k in v["keywords"]), reverse=True)
        selected = selected[:1]

    if selected:
        for i in selected[0].get("ingredients", []):
            ingredients.append({**i, "certainty": "confirmed", "source": "variant", "variant": selected[0]["name"]})
    else:
        for v in variants:
            for i in v.get("ingredients", []):
                ingredients.append({**i, "certainty": "possible", "source": "variant", "variant": v["name"]})

    for i in item.get("hidden", []):
        ingredients.append({**i, "certainty": "possible", "source": "hidden"})

    return {
        "base_menu": key,
        "resolved_variant": selected[0]["name"] if selected else None,
        "variant_options": [v["name"] for v in variants],
        "ingredients": _dedupe(ingredients),
    }


def _dedupe(ingredients: list[dict]) -> list[dict]:
    """같은 재료명이 여러 번 나오면 confirmed를 우선한다."""
    rank = {"confirmed": 2, "possible": 1, "excluded": 0}
    out: dict[str, dict] = {}
    for i in ingredients:
        prev = out.get(i["name"])
        if not prev or rank[i["certainty"]] > rank[prev["certainty"]]:
            out[i["name"]] = i
    return list(out.values())

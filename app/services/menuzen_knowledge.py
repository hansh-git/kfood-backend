"""메뉴젠 데이터로 메뉴 재료를 조회한다 (1순위 데이터 소스).

핵심: 같은 계열 레시피를 모아 비교한다.
  '짬뽕' → 짬뽕, 해물짬뽕, 차돌박이짬뽕국, 백짬뽕국 ... (짬뽕덮밥·짬뽕순두부는 제외)
  - 계열 대부분(70%↑)에 있는 알레르기 재료 → 확정(confirmed)
  - 일부 레시피에만 있는 재료 → 가능성(possible) → 직원 질문
  - 성분 비율은 대표 레시피의 실제 중량(g)으로 계산
"""
import json
import re
from functools import lru_cache
from pathlib import Path

from app.services.menuzen import is_seasoning, is_water

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "menuzen_menus.json"
CONSENSUS = 0.7          # 계열 레시피 중 이 비율 이상에 있으면 확정
MAIN_SHARE = 5.0         # 대표 레시피에서 중량 5% 이상인 주재료는 확정
FAMILY_SUFFIXES = ("", "국", "탕")  # '짬뽕' 계열에 '짬뽕국', '짬뽕탕' 포함


def core(name: str) -> str:
    return re.sub(r"\(.*?\)|\s", "", name or "")


@lru_cache
def load_dishes(path: str = str(DATA_PATH)) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8"))["dishes"]


def find_family(query: str, dishes: list[dict]) -> tuple[list[dict], list[dict]]:
    """→ (정확히 같은 이름 레시피들, 같은 계열 레시피들)"""
    q = core(query)
    if len(q) < 2:
        return [], []

    def family_of(base: str):
        return [d for d in dishes if any(core(d["name"]).endswith(base + s) for s in FAMILY_SUFFIXES)]

    fam = family_of(q)
    if not fam:
        # '부산밀면'처럼 수식어가 붙은 경우 → DB 이름 중 query의 가장 긴 접미사로 재시도
        suffixes = sorted({core(d["name"]) for d in dishes if len(core(d["name"])) >= 2 and q.endswith(core(d["name"]))},
                          key=len, reverse=True)
        if suffixes:
            q = suffixes[0]
            fam = family_of(q)
    exact = [d for d in fam if core(d["name"]) == q]
    return exact, fam


def _merge_same(ings: list[dict]) -> list[dict]:
    out: dict[str, dict] = {}
    for i in ings:
        key = i["short"]
        if key in out:
            out[key]["weight_g"] += i["weight_g"]
            out[key]["tags"] = list(dict.fromkeys(out[key]["tags"] + i["tags"]))
            out[key]["seasoning"] = out[key]["seasoning"] and is_seasoning(i)
        else:
            out[key] = {**i, "seasoning": is_seasoning(i)}
    return list(out.values())


def build_from_menuzen(menu_name: str, dishes: list[dict] | None = None) -> dict | None:
    from app.services.dietary_rules import KO_SHORT  # 순환 import 방지

    dishes = load_dishes() if dishes is None else dishes
    if not dishes:
        return None
    exact, fam = find_family(menu_name, dishes)
    if not fam:
        return None

    base = exact[0] if exact else min(fam, key=lambda d: len(d["name"]))
    n = len(fam)
    tag_count: dict[str, int] = {}
    tag_seen: dict[str, list[str]] = {}
    for d in fam:
        for t in {t for i in d["ingredients"] for t in i["tags"]}:
            tag_count[t] = tag_count.get(t, 0) + 1
            tag_seen.setdefault(t, []).append(d["name"])
    frac = {t: c / n for t, c in tag_count.items()}

    base_ings = _merge_same([i for i in base["ingredients"] if not is_water(i)])
    total = sum(i["weight_g"] for i in base_ings) or 1.0

    ingredients = []
    for i in base_ings:
        share = i["weight_g"] * 100 / total
        if n == 1:
            confirmed = not i["seasoning"]
        else:
            confirmed = (not i["seasoning"] and share >= MAIN_SHARE) or any(frac.get(t, 0) >= CONSENSUS for t in i["tags"])
        ingredients.append({
            "name": i["short"],
            "name_translated": i.get("name_en"),
            "tags": i["tags"],
            "certainty": "confirmed" if confirmed else "possible",
            "source": "menuzen",
            "weight_g": round(i["weight_g"], 1),
            "ratio_percent": round(share, 1),
            "ratio_source": "menuzen",
            "allergy_raw": i.get("allergy_raw"),
        })

    # 대표 레시피엔 없지만 같은 계열 다른 레시피에 있는 알레르기·식단 재료
    base_tags = {t for i in base_ings for t in i["tags"]}
    for t, c in sorted(tag_count.items(), key=lambda x: -x[1]):
        if t in base_tags:
            continue
        ingredients.append({
            "name": KO_SHORT.get(t, (t, []))[0],
            "name_translated": None,
            "tags": [t],
            "certainty": "confirmed" if frac[t] >= CONSENSUS else "possible",
            "source": "family",
            "seen_in": tag_seen[t][:3],
            "ratio_percent": None,
        })

    return {
        "base_menu": base["name"],
        "resolved_variant": None,
        "variant_options": [],
        "family": [d["name"] for d in fam],
        "data_source": "menuzen",
        "ingredients": ingredients,
    }

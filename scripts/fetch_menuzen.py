"""메뉴젠 API 전체 데이터를 한 번에 받아 app/data/menuzen_menus.json 으로 저장.

사용법 (kfood-backend 폴더에서, 가상환경 켠 상태):
    python -m scripts.fetch_menuzen            # 전체 (약 325회 호출)
    python -m scripts.fetch_menuzen --name 짬뽕  # 특정 메뉴만 테스트

.env 에 MENUZEN_API_KEY=<공공데이터포털 일반 인증키> 필요
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.services.menuzen import parse_xml  # noqa: E402

ENDPOINT = "https://apis.data.go.kr/1390803/AgriFood/FdFoodCkry1/getKoreanFoodFdFoodCkryList1"
OUT = Path(__file__).resolve().parent.parent / "app" / "data" / "menuzen_menus.json"


def fetch_page(client: httpx.Client, key: str, page: int, size: int, name: str | None) -> tuple[int, list]:
    params = {"serviceKey": key, "service_Type": "xml", "Page_No": page, "Page_Size": size}
    if name:
        params["food_Name"] = name
    for attempt in range(4):
        try:
            r = client.get(ENDPOINT, params=params, timeout=30)
            r.raise_for_status()
            return parse_xml(r.text)
        except Exception as e:  # 네트워크 오류·일시 장애 재시도
            if attempt == 3:
                raise
            print(f"  재시도 {attempt + 1} (page {page}): {e}")
            time.sleep(2 * (attempt + 1))
    return 0, []


def main():
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", help="특정 음식명만 조회 (테스트용)")
    ap.add_argument("--size", type=int, default=10, help="페이지 크기 (100은 오류, 10 권장)")
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    key = os.environ.get("MENUZEN_API_KEY")
    if not key:
        sys.exit(".env에 MENUZEN_API_KEY 가 없습니다.")

    dishes: dict[str, dict] = {}
    with httpx.Client() as client:
        total, first = fetch_page(client, key, 1, args.size, args.name)
        for d in first:
            dishes[d["code"]] = d
        pages = (total + args.size - 1) // args.size
        print(f"전체 {total}개, {pages}페이지")
        for page in range(2, pages + 1):
            _, items = fetch_page(client, key, page, args.size, args.name)
            for d in items:
                dishes[d["code"]] = d
            if page % 20 == 0:
                print(f"  {page}/{pages} 페이지 ({len(dishes)}개)")
            time.sleep(0.1)

    out = Path(args.out)
    if args.name:
        out = out.with_name(f"menuzen_test_{args.name}.json")
    payload = {"source": "농촌진흥청 국립식량과학원 메뉴젠", "count": len(dishes), "dishes": list(dishes.values())}
    out.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"저장 완료: {out} ({len(dishes)}개, {out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()

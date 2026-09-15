from fastapi.testclient import TestClient

from app.main import app
from app.services import groq_service

client = TestClient(app)


def fake_chat_json(model, messages, **kw):
    text = messages[-1]["content"]
    if "Staff reply" in text:
        return {"answer": "no", "summary_translated": "No shrimp."}
    return {"results": [{
        "menu": "짬뽕", "menu_translated": "Spicy seafood noodle soup",
        "description_translated": "Spicy noodle soup.",
        "ingredients": [
            {"name": "밀가루 면", "name_translated": "wheat noodles", "tags": ["wheat"], "ratio_percent": 40, "certainty": "confirmed"},
            {"name": "새우", "name_translated": "shrimp", "tags": ["shrimp"], "ratio_percent": 10, "certainty": "possible"},
            {"name": "양파", "tags": [], "ratio_percent": 30},
            {"name": "고추기름", "tags": ["not_a_tag"], "ratio_percent": 20},
        ],
        "custom_allergen_hits": [],
    }]}


def test_analyze_and_confirm(monkeypatch):
    monkeypatch.setattr(groq_service, "chat_json", fake_chat_json)
    body = {"menus": [{"name": "짬뽕", "price": "9000"}], "profile": {"allergies": {"새우": "심각"}, "preferred_language": "en"}}
    r = client.post("/analyze", json=body)
    assert r.status_code == 200, r.text
    item = r.json()["results"][0]
    assert item["risk"]["level"] == "CAUTION"
    assert r.json()["scan_log_id"] is None
    ratios = [i["ratio_percent"] for i in item["ingredients"] if i["ratio_percent"]]
    assert abs(sum(ratios) - 100) < 0.5
    ai_extra = next(i for i in item["ingredients"] if i["name"] == "고추기름")
    assert ai_extra["certainty"] == "possible" and ai_extra["tags"] == []

    q = item["risk"]["staff_questions"][0]
    r2 = client.post("/qna/confirm", json={
        "menu_result": item, "question": {"ingredient": q["ingredient"], "tag": q["tag"], "kind": q["kind"]},
        "staff_answer": "새우는 안 들어가요", "profile": body["profile"],
    })
    assert r2.status_code == 200, r2.text
    assert r2.json()["verdict"] == "no"
    assert r2.json()["result"]["risk"]["level"] == "SAFE"


def test_card_preview():
    r = client.post("/profile/card/preview", json={"allergies": {"땅콩": "심각"}, "religious_diet": "halal", "preferred_language": "en"})
    card = r.json()
    assert "땅콩 (심각 — 소량도 위험)" in card["staff"]["lines"][0]
    assert card["user"]["lang"] == "en"


def test_analyze_requires_input():
    assert client.post("/analyze", json={}).status_code == 422


def test_invalid_bearer():
    assert client.post("/analyze", json={"ocr_text": "짬뽕"}, headers={"Authorization": "Token x"}).status_code == 401


def test_ocr_compresses_large_image(monkeypatch):
    import io, os
    from PIL import Image
    seen = {}

    def fake(model, messages, **kw):
        url = messages[0]["content"][0]["image_url"]["url"]
        seen["b64_len"] = len(url)
        return {"raw_text": "짬뽕 9000", "menus": [{"name": "짬뽕", "price": "9000"}], "origin_info": []}

    monkeypatch.setattr(groq_service, "chat_json", fake)
    img = Image.frombytes("RGB", (2200, 1800), os.urandom(2200 * 1800 * 3))
    buf = io.BytesIO(); img.save(buf, format="PNG")
    r = client.post("/ocr", files={"file": ("menu.png", buf.getvalue(), "image/png")})
    assert r.status_code == 200, r.text
    assert r.json()["menus"][0]["name"] == "짬뽕"
    assert seen["b64_len"] < 4 * 1024 * 1024

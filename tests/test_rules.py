from app.services.dietary_rules import DietProfile, evaluate
from app.services.menu_knowledge import build_known_ingredients, match_menu


def P(**kw):
    return DietProfile.from_row(kw)


def test_match_variant_and_alias():
    assert match_menu("해물짬뽕 9,000원")[0] == "짬뽕"
    assert match_menu("꼼장어구이")[0] == "곰장어구이"
    assert match_menu("스테이크") is None
    k = build_known_ingredients("해물짬뽕")
    assert k["resolved_variant"] == "해물짬뽕"
    assert {i["name"]: i["certainty"] for i in k["ingredients"]}["새우"] == "confirmed"


def test_plain_jjamppong_asks_staff_for_shellfish_allergy():
    """피드백 2: '짬뽕'만 적힌 경우 → 필수재료(밀)는 확정, 해물/고기는 직원 질문"""
    k = build_known_ingredients("짬뽕")
    r = evaluate("짬뽕", k["ingredients"], P(allergies={"갑각류": "심각"}))
    assert r["level"] == "CAUTION"
    assert any(q["ingredient"] == "새우" and q["ko"] == "짬뽕에 새우가 들어가나요?" for q in r["staff_questions"])


def test_required_ingredient_is_warning_first():
    k = build_known_ingredients("짬뽕")
    r = evaluate("짬뽕", k["ingredients"], P(allergies=["밀"]))
    assert r["level"] == "WARNING"
    assert r["confirmed_reasons"][0]["tag"] == "wheat"


def test_resolved_variant_is_warning():
    k = build_known_ingredients("고기짬뽕")
    r = evaluate("고기짬뽕", k["ingredients"], P(religious_diet="halal"))
    assert r["level"] == "WARNING"


def test_halal_verify_question_and_certified_flow():
    ings = [{"name": "소고기", "tags": ["beef"], "certainty": "confirmed"}]
    r = evaluate("불고기", ings, P(religious_diet="halal"))
    assert r["level"] == "CAUTION" and r["staff_questions"][0]["kind"] == "halal_meat"
    ings[0]["certified"] = True
    assert evaluate("불고기", ings, P(religious_diet="halal"))["level"] == "SAFE"
    ings[0]["certified"] = False
    assert evaluate("불고기", ings, P(religious_diet="halal"))["level"] == "WARNING"


def test_staff_says_no_excludes():
    k = build_known_ingredients("짬뽕")
    ings = k["ingredients"]
    prof = P(allergies={"새우": "심각"})
    for i in ings:
        if i["name"] == "새우":
            i["certainty"] = "excluded"
    assert evaluate("짬뽕", ings, prof)["level"] == "SAFE"


def test_vegan_anchovy_broth():
    k = build_known_ingredients("칼국수")
    r = evaluate("칼국수", k["ingredients"], P(vegetarian_type="vegan"))
    assert r["level"] == "CAUTION"
    assert any(x["tag"] == "fish" for x in r["possible_reasons"])


def test_unmapped_allergy_forces_caution():
    r = evaluate("김밥", build_known_ingredients("김밥")["ingredients"], P(allergies=["키위"]))
    assert r["level"] == "CAUTION" and r["notes"][0]["items"] == ["키위"]


def test_no_profile_is_safe():
    assert evaluate("짬뽕", build_known_ingredients("짬뽕")["ingredients"], P())["level"] == "SAFE"


def test_translated_question():
    k = build_known_ingredients("짬뽕")
    r = evaluate("짬뽕", k["ingredients"], P(allergies=["새우"], preferred_language="ja"))
    assert "エビ" in r["staff_questions"][0]["translated"]

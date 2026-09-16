from app.services.dietary_rules import DietProfile, evaluate
from app.services.menu_knowledge import build_from_local as build_known_ingredients, match_menu


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
    qs = r["staff_questions"]
    assert qs[0]["kind"] == "variant"
    assert qs[0]["ko"] == "짬뽕은 어떤 종류인가요? (해물짬뽕 / 고기짬뽕 / 차돌짬뽕 / 그 외)"


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
    assert r["staff_questions"][0]["ko"] == "불고기에 들어가는 소고기가 할랄 인증 제품인가요?"
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


def test_translated_question_uses_translated_menu():
    k = build_known_ingredients("칼국수")
    r = evaluate("칼국수", k["ingredients"], P(allergies=["생선"], preferred_language="en"), "Kalguksu")
    q = next(q for q in r["staff_questions"] if q["kind"] == "contains")
    assert q["translated"].startswith("Does the Kalguksu contain") and "칼국수" not in q["translated"]


def test_no_redundant_question_when_already_confirmed():
    """돼지국밥: 돼지고기 확정 → 순대/내장 등 돼지 관련 질문 없음"""
    k = build_known_ingredients("돼지국밥")
    r = evaluate("돼지국밥", k["ingredients"], P(religious_diet="halal"))
    assert r["level"] == "WARNING" and r["staff_questions"] == []


def test_jjamppong_halal_shrimp_question_count():
    k = build_known_ingredients("짬뽕")
    r = evaluate("짬뽕", k["ingredients"], P(allergies={"새우": "심각"}, religious_diet="halal"), "Jjamppong")
    kinds = [q["kind"] for q in r["staff_questions"]]
    assert kinds.count("variant") == 1 and len(kinds) <= 2  # 변형 1 + 육수 1


def test_seafood_pajeon_resolves_variant():
    k = build_known_ingredients("해물파전")
    r = evaluate("해물파전", k["ingredients"], P(allergies=["새우"]))
    assert k["resolved_variant"] == "해물파전" and r["level"] == "WARNING"


def test_warning_has_no_questions():
    k = build_known_ingredients("해물파전")
    r = evaluate("해물파전", k["ingredients"], P(allergies=["새우"], religious_diet="halal"))
    assert r["level"] == "WARNING" and r["staff_questions"] == []


def test_kimchi_hidden_jeotgal_from_lexicon():
    from app.services.ingredient_lexicon import enrich
    ai = [{"name": "김치", "tags": [], "certainty": "confirmed", "source": "ai"},
          {"name": "밀가루", "tags": [], "certainty": "confirmed", "source": "ai"}]
    ings = enrich(ai)
    assert any(i["name"].startswith("김치 속 젓갈") for i in ings)
    assert "wheat" in ings[1]["tags"] if ings[1]["name"] == "밀가루" else True
    r = evaluate("김치전", ings, P(allergies={"새우": "심각"}), "Kimchi Pancake")
    assert r["level"] == "CAUTION"
    assert r["staff_questions"][0]["ko"] == "김치전에 김치 속 젓갈(새우젓·액젓)이 들어가나요?"


def test_generic_broth_question_names_the_ingredient_of_concern():
    ings = [{"name": "국물", "tags": ["pork"], "certainty": "possible", "source": "ai"}]
    r = evaluate("라면", ings, P(religious_diet="halal"), "Ramen")
    assert r["staff_questions"][0]["ko"] == "라면의 국물에 돼지고기가 들어가나요?"


def test_single_variant_gets_other_option():
    k = build_known_ingredients("비빔밥")
    r = evaluate("비빔밥", k["ingredients"], P(religious_diet="halal"), "Bibimbap")
    v = next(q for q in r["staff_questions"] if q["kind"] == "variant")
    assert v["options"] == ["육회비빔밥", "그 외"] and "other" in v["translated"]

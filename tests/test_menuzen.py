from app.services.dietary_rules import DietProfile, evaluate
from app.services.menuzen import allergy_to_tags, ingredient_tags, parse_xml, short_name
from app.services.menuzen_knowledge import build_from_menuzen, find_family
from tests.menuzen_fixture import DISHES

P = DietProfile.from_row


def test_allergy_parsing():
    assert allergy_to_tags("어패류(굴, 전복, 홍합 포함)") == ["shellfish"]
    assert allergy_to_tags("메밀") == ["buckwheat"]          # '밀'로 잘못 잡히지 않음
    assert allergy_to_tags("대두(콩)") == ["soy"]
    assert allergy_to_tags("null") == []


def test_ingredient_tag_fallbacks():
    assert "alcohol" in ingredient_tags("발효주, 청주, 알코올 16%", "주류", None)   # 알레르기 칸 null 보완
    assert "wheat" in ingredient_tags("간장, 개량, 양조", "조미료류", "대두(콩)")    # 간장 밀 누락 보완
    assert "fish" in ingredient_tags("가자미, 생것", "어패류 및 기타 수산물", None)
    assert short_name("담치, 참담치(홍합), 생것") == "홍합"


def test_family_excludes_different_dishes():
    exact, fam = find_family("짬뽕", DISHES)
    names = {d["name"] for d in fam}
    assert [d["name"] for d in exact] == ["짬뽕"]
    assert "짬뽕덮밥" not in names and "짬뽕순두부" not in names
    assert {"해물짬뽕", "짬뽕국", "배추백짬뽕탕"} <= names


def test_jjamppong_shrimp_is_possible_not_missed():
    """기본 짬뽕 레시피엔 새우가 없지만 계열 다수에 있음 → SAFE가 아니라 CAUTION + 질문"""
    k = build_from_menuzen("짬뽕", DISHES)
    r = evaluate("짬뽕", k["ingredients"], P({"allergies": {"새우": "심각"}}), "Jjamppong")
    assert r["level"] == "CAUTION"
    assert r["staff_questions"][0]["ko"] == "짬뽕에 새우가 들어가나요?"


def test_squid_consensus_is_warning():
    k = build_from_menuzen("짬뽕", DISHES)
    r = evaluate("짬뽕", k["ingredients"], P({"allergies": ["오징어"]}))
    assert r["level"] == "WARNING"


def test_ratio_from_real_weights():
    k = build_from_menuzen("짬뽕", DISHES)
    noodle = next(i for i in k["ingredients"] if i["name"] == "우동면")
    assert noodle["ratio_source"] == "menuzen" and noodle["certainty"] == "confirmed"
    assert abs(noodle["ratio_percent"] - 100 * 100 / 259) < 0.2


def test_water_excluded_from_ratio():
    k = build_from_menuzen("배추백짬뽕탕", DISHES)
    assert all(i["name"] != "생수" for i in k["ingredients"])


def test_halal_asks_presence_before_certification():
    k = build_from_menuzen("짬뽕", DISHES)
    r = evaluate("짬뽕", k["ingredients"], P({"religious_diet": "halal"}))
    kos = [q["ko"] for q in r["staff_questions"]]
    assert "짬뽕에 돼지고기가 들어가나요?" in kos
    assert "짬뽕에 소고기가 들어가나요?" in kos
    assert not any("할랄 인증" in q for q in kos)


def test_specific_variant_single_recipe():
    k = build_from_menuzen("해물짬뽕", DISHES)
    r = evaluate("해물짬뽕", k["ingredients"], P({"allergies": ["새우"]}))
    assert k["family"] == ["해물짬뽕"] and r["level"] == "WARNING"


def test_unknown_menu_returns_none():
    assert build_from_menuzen("낙곱새", DISHES) is None


def test_parse_xml():
    xml = """<response><header><result_Code>200</result_Code><result_Msg>OK</result_Msg></header>
    <body><total_Count>1</total_Count><items><item><fd_Code>D1</fd_Code><upper_Fd_Grupp_Nm>면</upper_Fd_Grupp_Nm>
    <fd_Grupp_Nm>면류</fd_Grupp_Nm><fd_Nm>짬뽕</fd_Nm><fd_Wgh>100.00</fd_Wgh><food_List><food>
    <food_Code>F1</food_Code><food_Nm>새우, 꽃새우, 생것</food_Nm><food_Eng_Nm>Shrimp</food_Eng_Nm>
    <nation_Std_Food_Grupp_Code_Nm>어패류 및 기타 수산물</nation_Std_Food_Grupp_Code_Nm>
    <food_Wgh>5.00</food_Wgh><allrgy_Info>새우</allrgy_Info></food></food_List></item></items></body></response>"""
    total, dishes = parse_xml(xml)
    assert total == 1 and dishes[0]["ingredients"][0]["tags"] == ["shrimp"]
    no_data = "<response><header><result_Code>301</result_Code><result_Msg>요청 데이터 없음</result_Msg></header></response>"
    assert parse_xml(no_data) == (0, [])

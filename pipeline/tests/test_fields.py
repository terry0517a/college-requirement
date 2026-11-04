import pytest
from collegedata.fields import classify_tw_program, tw_control, load_tw_field_rules

@pytest.mark.parametrize("name,expected", [
    ("化學系材料化學組", "physical_science"), ("物理學系電子物理組", "physical_science"),
    ("光電與材料工程學系(人工智慧應用組)", "engineering"), ("德國文化學系", "humanities"),
    ("生物科技學系甲組", "life_science"), ("商業設計學系產品設計組乙類", "arts"),
    ("晶片設計學士學位學程", "engineering"), ("資訊工程學系", "cs"), ("醫學系(自費)", "health"),
    ("學士班大一大二不分系", "interdisciplinary"), ("法律學系", "law"), ("企業管理學系", "business"),
])
def test_classify_tw_program(name, expected):
    assert classify_tw_program(name) == expected

def test_unknown_name_is_none():
    assert classify_tw_program("ZZZ") is None

def test_rules_reference_existing_fields(db):
    codes = {r[0] for r in db.execute("select code from field")}
    assert {f for f, _ in load_tw_field_rules()} <= codes

@pytest.mark.parametrize("name,expected", [("國立臺灣大學", "public"), ("臺北市立大學", "public"),
                                           ("中原大學", "private"), ("輔仁大學", "private")])
def test_tw_control(name, expected):
    assert tw_control(name) == expected

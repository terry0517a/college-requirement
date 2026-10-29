import pathlib
from decimal import Decimal
import pytest
from collegedata.parsers.cac_sieve import parse_sieve_image, map_headers

FIX = pathlib.Path(__file__).with_name("fixtures") / "cac"

@pytest.fixture(scope="module")
def crop():
    return parse_sieve_image((FIX / "115_001_crop.png").read_bytes(), "001")

def test_crop_rows_and_groups(crop):
    assert crop.rows_skipped == 0 and crop.groups == ["一般校系"]
    assert [r.cac_code for r in crop.rows][:4] == ["001012", "001022", "001032", "001042"]
    assert len(crop.rows) >= 10

def test_chinese_literature_row(crop):
    r = next(r for r in crop.rows if r.cac_code == "001012")
    assert (r.name, r.quota, r.gender, r.group) == ("中國文學系", 23, None, "一般校系")
    assert r.thresholds == {"國文": "前標", "英文": "均標", "數學A": "均標", "數學B": "均標", "社會": "均標", "自然": None, "英聽": None}
    assert r.multipliers == {"國文": Decimal("3"), "英文": Decimal("6"), "數學A": None, "數學B": None, "社會": Decimal("8"), "自然": None, "學測科目組合": None}
    assert [(s.order, s.label, s.min_score) for s in r.sieve] == [(1, "社會10", Decimal("10")), (2, "英文10", Decimal("10")), (3, "國文15", Decimal("15"))]
    assert r.overflow_tiebreak is True

def test_gender_split_rows(crop):
    rows = [r for r in crop.rows if r.cac_code == "001082"]
    assert [(r.gender, r.name, r.quota) for r in rows] == [("男", "戲劇學系(男)", 8), ("女", "戲劇學系(女)", 9)]
    assert rows[0].sieve[2].label == "國英數B社43" and rows[1].sieve[2].label == "國英數B社45"
    assert rows[0].sieve[2].subjects == ["國文", "英文", "數學B", "社會"]

def test_listening_and_two_line_sieve(crop):
    foreign = next(r for r in crop.rows if r.cac_code == "001022")
    assert foreign.thresholds["英聽"] == "A" and foreign.multipliers["英文"] == Decimal("2.5")
    psych = next(r for r in crop.rows if r.cac_code == "001132")
    assert psych.sieve[0].subjects == ["英文", "數學A", "自然"] and psych.sieve[0].min_score == Decimal("41")
    assert psych.multipliers["英文"] == Decimal("2.5") and psych.multipliers["數學A"] == Decimal("2.5")

def test_apcs_table_base_fields():
    res = parse_sieve_image((FIX / "115_001_apcs_crop.png").read_bytes(), "001")
    r = next(r for r in res.rows if r.cac_code == "001592")
    assert (r.name, r.quota) == ("資訊工程學系(APCS組)", 4)
    assert "APCS" in r.group

def test_map_headers_requires_base_columns():
    assert map_headers(["校系代碼", "性別要求", "校系名稱"]) is None
    m = map_headers(["校系代碼", "性別要求", "校系名稱", "招生名額", "國文", "英文", "國文", "英文", "篩選順序一", "同級分超額篩選"])
    assert m[4] == ("thresholds", "國文") and m[6] == ("multipliers", "國文") and m[8] == ("sieve", "sieve1") and m[9] == ("base", "overflow")

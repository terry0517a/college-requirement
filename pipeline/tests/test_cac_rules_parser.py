import pathlib
from decimal import Decimal
import pytest
from collegedata.parsers.cac_rules import find_system_url, parse_total_gsd, parse_code_list, parse_rules_page

FIX = pathlib.Path(__file__).with_name("fixtures") / "cac"
SYS = "https://www.cac.edu.tw/apply115/system/ColQry_115xappLyfOrStu_Azd5gP29/"

def test_find_system_url():
    assert find_system_url((FIX / "115_query.html").read_text(encoding="utf-8"), 115) == SYS
    assert find_system_url("<html>no link</html>", 116) is None

def test_parse_total_gsd():
    lst = parse_total_gsd((FIX / "115_TotalGsdShow.htm").read_text(encoding="utf-8"))
    assert len(lst) == 64 and lst[0] == ("001", "國立臺灣大學", 73) and lst[-1] == ("153", "國立金門大學", 25)

def test_parse_code_list():
    codes = parse_code_list((FIX / "115_ShowGsd_code001.html").read_text(encoding="utf-8"))
    assert len(codes) == 73 and codes[0] == "001012" and "001582" in codes

def test_parse_rules_page_ntu_csie():
    p = parse_rules_page((FIX / "115_001582.htm").read_text(encoding="utf-8"))
    assert (p.cac_code, p.school, p.name, p.quota, p.gender, p.expected_candidates, p.fee) == ("001582", "國立臺灣大學", "資訊工程學系", 57, None, 143, 1500)
    assert p.thresholds == {"國文": None, "英文": "頂標", "數學A": "頂標", "數學B": None, "社會": None, "自然": "頂標", "英聽": None}
    assert p.multipliers["英文"] == Decimal("10") and p.multipliers["數學A"] == Decimal("2.5") and p.multipliers["國文"] is None
    assert p.gsat_weights == {"英文": Decimal("1.25"), "數學A": Decimal("2.00"), "自然": Decimal("1.00")}
    assert p.stage1_pct == 20
    assert [(i.name, i.threshold, i.pct) for i in p.items] == [("審查資料", "70分", 50), ("數學筆試", None, 30)]
    assert p.tiebreak_order == ["審查資料", "數學筆試", "學科能力測驗成績", "學測數學A級分"]
    assert p.review_items.startswith("修課紀錄(A)、課程學習成果(B、C、D)")
    assert p.exam_date == "115.5.17" and p.website == "http://www.csie.ntu.edu.tw"
    assert p.overflow_rule == "一、學測英文、數學A、自然之級分總和"

def test_parse_rules_page_rejects_other_html():
    with pytest.raises(ValueError):
        parse_rules_page("<html><table><tr><td>流量過大</td></tr></table></html>")

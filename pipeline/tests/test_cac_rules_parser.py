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


def _page(g3=None, overflow="一、甲", note="x", quota="5", extra_rows=""):
    cells = "".join(f'<td class="g3">{c}</td>' for c in (g3 or []))
    return (
        '<table><tr><td><div class="colname">某大學</div><div class="gsdname">某系</div></td></tr>'
        f'<tr><td class="Lb">校系代碼</td><td class="Rb">009999</td>{cells}<td class="Rb">一、審查資料</td></tr>'
        f'<tr><td class="Lb">招生名額</td><td class="Rb">{quota}</td></tr>'
        f'{extra_rows}'
        f'<tr><td class="Lb Rb">同級分(分數)超額篩選方式</td><td class="Rb">{overflow}</td></tr>'
        f'<tr><td class="Lb">備註</td><td class="Rb">{note}</td></tr></table>'
    )


G3_OK = ["英文<br>數學A<br>自然<br>國文", "頂標<br>--<br>均標<br>前標", "10<br>2.5<br>10<br>3",
         "*1.00<br>--<br>*2.00<br>*1.50", "20%", "審查資料", "70分", "50%"]


def test_no_g3_gives_empty_stages():
    p = parse_rules_page(_page())
    assert p.items == [] and p.gsat_weights == {} and p.stage1_pct is None
    assert all(v is None for v in p.thresholds.values()) and all(v is None for v in p.multipliers.values())


def test_partial_g3_raises():
    with pytest.raises(ValueError, match="unexpected g3 cell count: 3"):
        parse_rules_page(_page(g3=["a", "b", "c"]))


def test_four_subjects_and_no_items():
    p = parse_rules_page(_page(g3=G3_OK[:5] + ["", "", ""]))
    assert p.thresholds["國文"] == "前標" and p.thresholds["數學A"] is None and p.thresholds["自然"] == "均標"
    assert p.multipliers["國文"] == Decimal("3")
    assert p.gsat_weights == {"英文": Decimal("1.00"), "自然": Decimal("2.00"), "國文": Decimal("1.50")}
    assert p.items == []


def test_misaligned_cells_raise():
    bad = list(G3_OK)
    bad[1] = "頂標<br>頂標"
    with pytest.raises(ValueError, match="misaligned first-stage cells"):
        parse_rules_page(_page(g3=bad))
    bad = list(G3_OK)
    bad[5] = "審查資料<br>筆試"
    with pytest.raises(ValueError, match="misaligned second-stage cells"):
        parse_rules_page(_page(g3=bad))


def test_blank_line_keeps_alignment():
    g = list(G3_OK)
    g[1] = "頂標<br><br>均標<br>前標"
    p = parse_rules_page(_page(g3=g))
    assert p.thresholds["數學A"] is None and p.thresholds["自然"] == "均標"


def test_multiline_overflow_and_website_line():
    p = parse_rules_page(_page(overflow="一、甲<br>二、乙", note="1.電話<br>2.網址:http://a.b.c。<br>3.其他"))
    assert p.overflow_rule == "一、甲\n二、乙" and p.website == "http://a.b.c"


def test_numeric_and_name_guards():
    row = '<tr><td class="Lb">指定項目甄試費</td><td class="Rb">1,500</td></tr>'
    assert parse_rules_page(_page(extra_rows=row)).fee == 1500
    with pytest.raises(ValueError, match="quota not numeric"):
        parse_rules_page(_page(quota="若干"))
    with pytest.raises(ValueError, match="not a rules page"):
        parse_rules_page(_page().replace("某大學", ""))


def test_review_items_stops_at_description():
    row = ('<tr><td>審查<br>資料</td><td><div><div>項目：</div><div>甲、乙</div></div>'
           '<div><div>說明：</div><div>丙</div></div></td></tr>')
    assert parse_rules_page(_page(extra_rows=row)).review_items == "甲、乙"

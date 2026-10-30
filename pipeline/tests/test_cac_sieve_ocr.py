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
    assert [(r.gender, r.name, r.quota) for r in rows] == [("男", "戲劇學系", 8), ("女", "戲劇學系", 9)]
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


# ---------------------------------------------------------------- fake-engine tests
import io
import logging

import numpy as np
from PIL import Image, ImageDraw

from collegedata.parsers import cac_sieve
from collegedata.parsers.cac_sieve import RapidOcrEngine

COL_W, ROW_H = 160, 40
CORE = ["國文", "英文", "數學A", "數學B", "社會", "自然"]
BASE = ["校系代碼", "性別要求", "校系名稱", "招生名額", "篩選順序一", "同級分超額篩選"]
HEADER = BASE + CORE + CORE   # 一般校系 tables must carry the six core subjects as thresholds and multipliers


class FakeOcr:
    """Identifies a cell by the width of its ink block, so each distinct text gets its own width."""

    def __init__(self, blank=()):
        self.widths: dict[str, int] = {}
        self.blank = set(blank)   # texts whose ink the engine cannot read

    def width_for(self, text: str) -> int:
        return self.widths.setdefault(text, 20 + 3 * len(self.widths))

    def recognize(self, line):
        w = int((line < 110).any(axis=0).sum())
        text = next(t for t, x in self.widths.items() if x == w)
        return "" if text in self.blank else text


def make_tables(ocr: FakeOcr, tables: list[tuple[str | None, list[list[str]]]]) -> bytes:
    """Stack tables vertically; each may have a text line (its group marker) in the gap above it."""
    ncol = max(len(rows[0]) for _, rows in tables)
    height = 20 + sum(30 + len(rows) * ROW_H for _, rows in tables) + 40
    img = Image.new("L", (ncol * COL_W + 20, height), 255)
    d = ImageDraw.Draw(img)
    y = 20
    for k, (marker, rows) in enumerate(tables):
        if k > 0 or marker:
            y += 30
        if marker:
            d.rectangle([20, y - 22, 20 + ocr.width_for(marker) - 1, y - 9], fill=0)
        n = len(rows[0])
        for r in range(len(rows) + 1):
            d.line([(10, y + r * ROW_H), (10 + n * COL_W, y + r * ROW_H)], fill=0, width=2)
        for c in range(n + 1):
            d.line([(10 + c * COL_W, y), (10 + c * COL_W, y + len(rows) * ROW_H)], fill=0, width=2)
        for r, row in enumerate(rows):
            for c, text in enumerate(row):
                if text:
                    x0, y0 = 10 + c * COL_W + 12, y + r * ROW_H + 12
                    d.rectangle([x0, y0, x0 + ocr.width_for(text) - 1, y0 + 13], fill=0)
        y += len(rows) * ROW_H
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def make_table(ocr: FakeOcr, rows: list[list[str]]) -> bytes:
    return make_tables(ocr, [(None, rows)])


def _pad(row: list[str], n: int) -> list[str]:
    return row + [""] * (n - len(row))


def parse_rows(*data_rows, header=HEADER, ocr=None):
    ocr = ocr or FakeOcr()
    png = make_table(ocr, [header, *(_pad(r, len(header)) for r in data_rows)])
    return parse_sieve_image(png, "001", ocr=ocr)


GOOD = ["001012", "無", "中國文學系", "23", "社會10", "*"]


def test_fake_engine_happy_path():
    res = parse_rows(GOOD)
    assert res.rows_skipped == 0 and res.rows[0].overflow_tiebreak is True
    assert res.rows[0].name == "中國文學系" and res.groups == ["一般校系"]


def test_unparseable_sieve_cell_skips_row():
    res = parse_rows(GOOD[:4] + ["社會ＸＸ", "*"], GOOD)
    assert res.rows_skipped == 1 and len(res.rows) == 1
    assert any("skip row" in w for w in res.warnings)


@pytest.mark.parametrize("cell,expected", [("", False), ("--", False), ("*", True), ("水", True)])
def test_overflow_values(cell, expected):
    res = parse_rows(GOOD[:5] + [cell])
    assert res.rows_skipped == 0 and res.rows[0].overflow_tiebreak is expected


def test_unrecognised_overflow_skips_row():
    res = parse_rows(GOOD[:5] + ["E"])
    assert res.rows_skipped == 1 and res.rows == []


def test_misread_code_on_first_data_row_is_counted():
    res = parse_rows(["00101", "無", "中國文學系", "23", "社會10", "*"], GOOD)
    assert res.rows_skipped == 1 and [r.cac_code for r in res.rows] == ["001012"]


def test_name_repair_logs(caplog):
    with caplog.at_level(logging.WARNING, logger=cac_sieve.__name__):
        res = parse_rows(["001082", "男", "劇學系", "8", "社會10", ""])
    assert res.rows[0].name == "戲劇學系" and res.rows[0].gender == "男"
    assert "name repaired" in caplog.text


class RaisingOcr(FakeOcr):
    def recognize(self, line):
        raise RuntimeError("boom")


def test_engine_exception_becomes_warning_not_crash():
    ocr = RaisingOcr()
    res = parse_rows(GOOD, ocr=ocr)
    assert res.rows == [] and any("ocr failed" in w for w in res.warnings)


def test_real_engine_survives_very_wide_line():
    line = np.full((16, 2100), 255, dtype=np.uint8)
    line[:, 10:2000:7] = 0
    assert isinstance(RapidOcrEngine().recognize(line), str)


def test_two_row_header_with_base_columns_on_first_row():
    row1 = ["校系代碼", "性別要求", "校系名稱", "招生名額", "", "篩選順序一"] + [""] * 11
    row2 = ["", "", "", "", "國文", ""] + CORE[1:] + CORE
    ocr = FakeOcr()
    png = make_table(ocr, [row1, row2, _pad(["001012", "無", "中國文學系", "23", "前標", "社會10"], 17)])
    res = parse_sieve_image(png, "001", ocr=ocr)
    assert res.rows_skipped == 0 and res.rows[0].thresholds["國文"] == "前標"


# ---------------------------------------------------------------- final-review fixes

def test_unrecognised_header_counts_its_data_rows():
    bad = ["校系代碼", "性別要求", "招生名額", "篩選順序一"]   # no 校系名稱
    res = parse_rows(GOOD[:2] + GOOD[3:5], GOOD[:2] + GOOD[3:5], GOOD[:2] + GOOD[3:5], header=bad)
    assert res.rows == [] and res.rows_skipped == 3
    assert any("skip table" in w for w in res.warnings)


def test_unreadable_ink_is_not_no_requirement():
    row = GOOD + ["前標"]   # 國文 threshold has ink, but the engine returns ""
    res = parse_rows(row, GOOD, ocr=FakeOcr(blank={"前標"}))
    assert res.rows_skipped == 1 and [r.cac_code for r in res.rows] == ["001012"]
    assert res.rows[0].thresholds["國文"] is None


def test_general_table_without_core_multipliers_is_skipped():
    header = BASE + CORE + CORE[:5]   # 自然 multiplier missing
    res = parse_rows(GOOD, GOOD, header=header)
    assert res.rows == [] and res.rows_skipped == 2
    assert any("core subjects" in w for w in res.warnings)


def test_special_group_needs_no_core_subjects():
    ocr = FakeOcr()
    png = make_tables(ocr, [("【檢定、倍率篩選APCS校系】", [BASE, GOOD])])
    res = parse_sieve_image(png, "001", ocr=ocr)
    assert res.rows_skipped == 0 and res.groups == ["檢定、倍率篩選APCS校系"]
    assert res.rows[0].group == "檢定、倍率篩選APCS校系"


def test_table_without_marker_continues_previous_group():
    ocr = FakeOcr()
    second = ["001022", "無", "外國語文學系", "20", "英文10", ""]
    png = make_tables(ocr, [("【檢定、倍率篩選APCS校系】", [BASE, GOOD]), (None, [BASE, second])])
    res = parse_sieve_image(png, "001", ocr=ocr)
    assert res.groups == ["檢定、倍率篩選APCS校系", "檢定、倍率篩選APCS校系"]
    assert [r.group for r in res.rows] == ["檢定、倍率篩選APCS校系"] * 2
    assert any("continuing" in w for w in res.warnings)


def test_plus_split_subjects_are_validated():
    from collegedata.parsers.cac_sieve import expand_subjects, parse_sieve_cell
    assert expand_subjects("英文+數學A") == ["英文", "數學A"]
    assert expand_subjects("英文+奇怪") == []
    lv = parse_sieve_cell("(英文+奇怪)20")
    assert lv.subjects == [] and lv.label == "(英文+奇怪)20"


def test_sieve_score_above_subject_maximum_skips_row():
    res = parse_rows(GOOD[:4] + ["社會16", "*"], GOOD)
    assert res.rows_skipped == 1 and len(res.rows) == 1
    res = parse_rows(GOOD[:4] + ["(英文+數學A)30", "*"])
    assert res.rows_skipped == 0


def test_raw_cells_logged_at_debug(caplog):
    with caplog.at_level(logging.DEBUG, logger=cac_sieve.__name__):
        parse_rows(GOOD)
    assert "001012" in caplog.text and "中國文學系" in caplog.text

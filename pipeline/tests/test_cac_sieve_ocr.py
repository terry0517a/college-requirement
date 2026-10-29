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


# ---------------------------------------------------------------- fake-engine tests
import io
import logging

import numpy as np
from PIL import Image, ImageDraw

from collegedata.parsers import cac_sieve
from collegedata.parsers.cac_sieve import RapidOcrEngine

COL_W, ROW_H = 160, 40
HEADER = ["校系代碼", "性別要求", "校系名稱", "招生名額", "篩選順序一", "同級分超額篩選"]


class FakeOcr:
    """Identifies a cell by the width of its ink block, so each distinct text gets its own width."""

    def __init__(self):
        self.widths: dict[str, int] = {}

    def width_for(self, text: str) -> int:
        return self.widths.setdefault(text, 20 + 3 * len(self.widths))

    def recognize(self, line):
        w = int((line < 110).any(axis=0).sum())
        return next(t for t, x in self.widths.items() if x == w)


def make_table(ocr: FakeOcr, rows: list[list[str]]) -> bytes:
    ncol, nrow = len(rows[0]), len(rows)
    img = Image.new("L", (ncol * COL_W + 20, nrow * ROW_H + 60), 255)
    d = ImageDraw.Draw(img)
    for r in range(nrow + 1):
        y = 20 + r * ROW_H
        d.line([(10, y), (10 + ncol * COL_W, y)], fill=0, width=2)
    for c in range(ncol + 1):
        x = 10 + c * COL_W
        d.line([(x, 20), (x, 20 + nrow * ROW_H)], fill=0, width=2)
    for r, row in enumerate(rows):
        for c, text in enumerate(row):
            if text:
                x, y = 10 + c * COL_W + 12, 20 + r * ROW_H + 12
                d.rectangle([x, y, x + ocr.width_for(text) - 1, y + 13], fill=0)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def parse_rows(*data_rows, header=HEADER, ocr=None):
    ocr = ocr or FakeOcr()
    png = make_table(ocr, [header, *data_rows])
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
    assert res.rows[0].name == "戲劇學系(男)"
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

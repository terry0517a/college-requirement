import pathlib
from decimal import Decimal
from collegedata.parsers.cac_sieve import (to_gray, detect_hlines, grid_rows, split_tables, detect_vlines, cell_lines,
    normalize_text, parse_level, parse_multiplier, parse_sieve_cell, expand_subjects, normalize_program_name, parse_quota)

FIX = pathlib.Path(__file__).with_name("fixtures") / "cac"
CROP = (FIX / "115_001_crop.png").read_bytes()

def test_grid_of_crop_has_one_table_with_25_columns():
    g = to_gray(CROP)
    hl = detect_hlines(g)
    tables = split_tables(grid_rows(g, hl))
    assert len(tables) == 1
    t = tables[0]
    assert t.above is not None                       # 【一般校系】列
    assert len(detect_vlines(g, t.y0, t.y1)) == 26  # 25 欄

def test_cell_lines_splits_two_line_cell():
    g = to_gray(CROP); hl = detect_hlines(g); t = split_tables(grid_rows(g, hl))[0]
    vl = detect_vlines(g, t.y0, t.y1)
    rows = [r for r in grid_rows(g, hl) if r[2] and r[0] >= t.y0]
    # The crop is cut off before 心理學系 (001132), so the two-line cells used here are the
    # stacked header label 數學/A (header row 2, column 6) and a stacked APCS cell below.
    y0, y1, _ = rows[1]
    assert len(cell_lines(g, y0, y1, vl[6], vl[7])) == 2
    # 2 header grid rows, then 20 data rows; 心理學系 001132 is data row index 13 (戲劇學系 男/女 share a code)
    y0, y1, _ = rows[2 + 13]
    assert len(cell_lines(g, y0, y1, vl[18], vl[19])) == 2   # 篩選順序一 wraps to two lines
    assert len(cell_lines(g, y0, y1, vl[0], vl[1])) == 1     # 校系代碼 single line
    y0, y1, _ = rows[3]                                   # first data row: 001012 中國文學系
    assert len(cell_lines(g, y0, y1, vl[18], vl[19])) == 1  # 篩選順序一 single line
    assert cell_lines(g, y0, y1, vl[4], vl[5]) == [] or len(cell_lines(g, y0, y1, vl[4], vl[5])) == 1
    assert cell_lines(g, rows[0][0], rows[0][1], vl[0], vl[1]) == []  # blank cell

def test_cell_lines_splits_stacked_apcs_cell():
    g = to_gray((FIX / "115_001_apcs_crop.png").read_bytes()); hl = detect_hlines(g)
    t = split_tables(grid_rows(g, hl))[0]
    vl = detect_vlines(g, t.y0, t.y1)
    y0, y1, _ = [r for r in grid_rows(g, hl) if r[2] and r[0] >= t.y0][2]   # 001592 資訊工程學系(APCS組)
    assert len(cell_lines(g, y0, y1, vl[4], vl[5])) == 2    # 前標 over APCS識讀 "4"

def test_normalize_text_maps_simplified_and_parens():
    assert normalize_text("国英数A自 46（数学A）") == "國英數A自46(數學A)"

def test_parse_level_and_multiplier():
    assert parse_level("均標") == "均標" and parse_level("均") == "均標" and parse_level("顶標") == "頂標"
    assert parse_level("--") is None and parse_level("—") is None and parse_level("") is None
    assert parse_multiplier("2.5") == Decimal("2.5") and parse_multiplier("--") is None

def test_parse_sieve_cell_three_forms():
    a = parse_sieve_cell("英文13"); b = parse_sieve_cell("(英文+數學A+自然)41"); c = parse_sieve_cell("國英數A自37")
    assert (a.subjects, a.min_score) == (["英文"], Decimal("13"))
    assert (b.subjects, b.min_score) == (["英文", "數學A", "自然"], Decimal("41"))
    assert (c.subjects, c.min_score) == (["國文", "英文", "數學A", "自然"], Decimal("37"))
    assert parse_sieve_cell("--") is None and parse_sieve_cell("") is None
    assert parse_sieve_cell("APCS實作4").label == "APCS實作4" and parse_sieve_cell("APCS實作4").subjects == []

def test_expand_subjects_abbreviations():
    assert expand_subjects("國英數B社") == ["國文", "英文", "數學B", "社會"]
    assert expand_subjects("英聽") == ["英聽"]
    assert expand_subjects("奇怪") == []

def test_normalize_program_name():
    assert normalize_program_name("醫學系（公費生）", None) == "醫學系(公費生)"
    assert normalize_program_name("戲劇學系", "男") == "戲劇學系(男)"
    assert normalize_program_name(" 資訊工程學系 (APCS組)", "無") == "資訊工程學系(APCS組)"
    assert parse_quota(" 57 ") == 57

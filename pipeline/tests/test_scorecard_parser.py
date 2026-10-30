import json, pathlib, pytest
from collegedata.parsers.scorecard import (fields_param, normalize_domain, parse_school,
                                           load_program_map, PROGRAM_KEYS, SCHOOL_FIELDS, YEAR_FIELDS)

FIX = json.loads(pathlib.Path(__file__).with_name("fixtures").joinpath("scorecard_sample.json").read_text())
YEARS = [2024, 2023, 2022]

@pytest.mark.parametrize("url,expected", [
    ("www.stanford.edu/", "stanford.edu"), ("https://behrend.psu.edu/", "behrend.psu.edu"),
    ("HTTPS://WWW.X.EDU/admissions?a=1", "x.edu"), ("", None), (None, None)])
def test_normalize_domain(url, expected):
    assert normalize_domain(url) == expected

def test_fields_param_order_and_count():
    p = fields_param(YEARS).split(",")
    assert p[:7] == SCHOOL_FIELDS
    assert p[7] == "2024.admissions.admission_rate.overall"
    assert len(p) == 7 + 3 * len(YEAR_FIELDS) + 38
    assert p[-1] == "latest.academics.program.bachelors.history"

def test_parse_stanford():
    s = parse_school(FIX["results"][0], YEARS)
    assert (s.scorecard_id, s.domain, s.control, s.main_campus) == (243744, "stanford.edu", "private", True)
    assert s.web_url == "https://www.stanford.edu/"
    y = s.years[0]
    assert (y.year, y.admission_rate, y.sat_rw, y.sat_math, y.act) == (2024, 0.0361, (740, 780), (770, 800), (34, 35))
    assert (y.tuition_in_state, y.student_size, y.completion_rate, y.median_earnings) == (68544, 7554, 0.9164, 125340)
    assert s.program_keys == ["computer", "engineering", "biological", "mathematics", "history"]

def test_parse_missing_scores_and_url():
    t = parse_school(FIX["results"][1], YEARS)
    assert t.years[0].admission_rate == 0.65 and t.years[0].sat_rw is None and t.years[0].act is None
    n = parse_school(FIX["results"][2], YEARS)
    assert n.domain is None and n.web_url is None and n.control == "private" and n.program_keys == []
    assert n.years[1].admission_rate is None

def test_program_map_covers_all_keys_with_valid_fields(db):
    m = load_program_map()
    assert list(m) == PROGRAM_KEYS and len(m) == 38
    codes = {r[0] for r in db.execute("select code from field")}
    assert all(v["field_code"] in codes and len(v["cip2"]) == 2 for v in m.values())

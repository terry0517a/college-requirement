"""College Scorecard record parsing: pure functions, no I/O besides the program map."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).resolve().parents[3] / "config"
PROGRAMS_PATH = CONFIG_DIR / "scorecard_programs.yaml"

SCHOOL_FIELDS = ["id", "school.name", "school.city", "school.state", "school.school_url",
                 "school.ownership", "school.main_campus"]
YEAR_FIELDS = [
    "admissions.admission_rate.overall",
    "admissions.sat_scores.25th_percentile.critical_reading",
    "admissions.sat_scores.75th_percentile.critical_reading",
    "admissions.sat_scores.25th_percentile.math",
    "admissions.sat_scores.75th_percentile.math",
    "admissions.act_scores.25th_percentile.cumulative",
    "admissions.act_scores.75th_percentile.cumulative",
    "cost.tuition.in_state",
    "cost.tuition.out_of_state",
    "student.size",
    "completion.completion_rate_4yr_150nt",
    "earnings.10_yrs_after_entry.median",
]
PROGRAM_PREFIX = "latest.academics.program.bachelors."


def load_program_map() -> dict[str, dict]:
    entries = yaml.safe_load(PROGRAMS_PATH.read_text(encoding="utf-8"))
    return {e["key"]: {"cip2": e["cip2"], "name_en": e["name_en"], "field_code": e["field_code"]}
            for e in entries}


PROGRAM_KEYS: list[str] = list(load_program_map())


def fields_param(years: list[int]) -> str:
    parts = list(SCHOOL_FIELDS)
    parts += [f"{y}.{f}" for y in years for f in YEAR_FIELDS]
    parts += [f"{PROGRAM_PREFIX}{k}" for k in PROGRAM_KEYS]
    return ",".join(parts)


def normalize_domain(url: str | None) -> str | None:
    if not url or not url.strip():
        return None
    s = url.strip().lower()
    if "://" in s:
        s = s.split("://", 1)[1]
    for sep in "/?#":
        s = s.split(sep, 1)[0]
    if s.startswith("www."):
        s = s[4:]
    return s or None


@dataclass
class YearStats:
    year: int
    admission_rate: float | None
    sat_rw: tuple[int, int] | None
    sat_math: tuple[int, int] | None
    act: tuple[int, int] | None
    tuition_in_state: float | None
    tuition_out_of_state: float | None
    student_size: int | None
    completion_rate: float | None
    median_earnings: float | None


@dataclass
class School:
    scorecard_id: int
    name: str
    city: str | None
    region: str | None
    domain: str | None
    web_url: str | None
    control: str
    main_campus: bool
    program_keys: list[str] = field(default_factory=list)
    years: list[YearStats] = field(default_factory=list)


def _range(rec: dict, y: int, low: str, high: str) -> tuple[int, int] | None:
    lo, hi = rec.get(f"{y}.{low}"), rec.get(f"{y}.{high}")
    if lo is None or hi is None:
        return None
    return (int(lo), int(hi))


def _year_stats(rec: dict, y: int) -> YearStats:
    size = rec.get(f"{y}.student.size")
    return YearStats(
        year=y,
        admission_rate=rec.get(f"{y}.admissions.admission_rate.overall"),
        sat_rw=_range(rec, y, "admissions.sat_scores.25th_percentile.critical_reading",
                      "admissions.sat_scores.75th_percentile.critical_reading"),
        sat_math=_range(rec, y, "admissions.sat_scores.25th_percentile.math",
                        "admissions.sat_scores.75th_percentile.math"),
        act=_range(rec, y, "admissions.act_scores.25th_percentile.cumulative",
                   "admissions.act_scores.75th_percentile.cumulative"),
        tuition_in_state=rec.get(f"{y}.cost.tuition.in_state"),
        tuition_out_of_state=rec.get(f"{y}.cost.tuition.out_of_state"),
        student_size=None if size is None else int(size),
        completion_rate=rec.get(f"{y}.completion.completion_rate_4yr_150nt"),
        median_earnings=rec.get(f"{y}.earnings.10_yrs_after_entry.median"),
    )


def parse_school(rec: dict, years: list[int]) -> School:
    url = rec.get("school.school_url")
    if url:
        web_url = url if "://" in url else f"https://{url}"
    else:
        web_url = None
    return School(
        scorecard_id=int(rec["id"]),
        name=rec["school.name"],
        city=rec.get("school.city"),
        region=rec.get("school.state"),
        domain=normalize_domain(url),
        web_url=web_url,
        control="public" if rec.get("school.ownership") == 1 else "private",
        main_campus=rec.get("school.main_campus") == 1,
        program_keys=[k for k in PROGRAM_KEYS if rec.get(f"{PROGRAM_PREFIX}{k}") == 1],
        years=[_year_stats(rec, y) for y in years],
    )

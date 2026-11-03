import csv
import datetime
import logging
import tempfile
from pathlib import Path

import httpx
import yaml
from psycopg.types.json import Jsonb

from collegedata.jobs.cac_common import upsert_program
from collegedata.parsers.uac import parse_uac_pdf
from collegedata.sources import ensure_source

CONFIG_DIR = Path(__file__).resolve().parents[3] / "config"
SCHOOLS_PATH = CONFIG_DIR / "tw_institutions.csv"
YEARS_PATH = CONFIG_DIR / "uac_years.yaml"
PATHWAY = "tw_distribution"
URL_PATTERN = "https://www2.uac.edu.tw/{roc}data/{roc}_result_school_data.pdf"
YEARS_BACK = 2

log = logging.getLogger(__name__)


class UnknownSchoolError(Exception):
    def __init__(self, missing: list[str]):
        self.missing = missing
        super().__init__("unknown schools (add to tw_institutions.csv): " + ", ".join(missing))


def load_school_map() -> dict[str, tuple[str, str]]:
    with SCHOOLS_PATH.open(encoding="utf-8", newline="") as f:
        return {r["name_zh"]: (r["name_en"], r["domain"]) for r in csv.DictReader(f)}


def load_years() -> list[dict]:
    """URL overrides only (roc_year/url); years without an entry use URL_PATTERN."""
    return yaml.safe_load(YEARS_PATH.read_text(encoding="utf-8")) or []


def year_urls(today: datetime.date | None = None) -> list[tuple[int, str]]:
    """The newest ROC year and the two before it, newest first.

    UAC publishes each year's distribution results around August, so the newest
    year's PDF usually does not exist before then. From September on, the
    current ROC year is the newest; before September the previous ROC year is.
    """
    d = today or datetime.date.today()
    roc = d.year - 1911 if d.month >= 9 else d.year - 1912
    overrides = {e["roc_year"]: e["url"] for e in load_years()}
    return [(y, overrides.get(y, URL_PATTERN.format(roc=y))) for y in range(roc, roc - YEARS_BACK - 1, -1)]


def _institution_id(conn, cache, school_zh, school_map, source_id, source_url) -> int:
    name_en, domain = school_map[school_zh]
    if domain in cache:
        return cache[domain]
    row = conn.execute(
        "select id, name_zh from institution where country_code = 'TW' and domain = %s", (domain,)
    ).fetchone()
    if row is None:
        inst_id = conn.execute(
            """insert into institution (country_code, name_en, name_zh, domain, web_url, source_id, source_url, fetched_at)
               values ('TW', %s, %s, %s, %s, %s, %s, now()) returning id""",
            (name_en, school_zh, domain, f"https://www.{domain}/", source_id, source_url),
        ).fetchone()[0]
    else:
        inst_id = row[0]
        if row[1] != school_zh:
            conn.execute("update institution set name_zh = %s where id = %s", (school_zh, inst_id))
    cache[domain] = inst_id
    return inst_id


class UacJob:
    name = "uac"

    def __init__(self, client: httpx.Client | None = None, years: list[int] | None = None,
                 today: datetime.date | None = None):
        self.client = client
        self.years = years
        self.today = today

    def run(self, conn) -> int:
        client = self.client or httpx.Client(timeout=60, follow_redirects=True)
        source_id = ensure_source(conn, "uac")
        school_map = load_school_map()
        cache: dict[str, int] = {}
        total = 0
        selected = [(y, u) for y, u in year_urls(self.today) if self.years is None or y in self.years]
        for i, (roc_year, url) in enumerate(selected):
            resp = client.get(url, timeout=60)
            if resp.status_code == 404 and i > 0:
                log.warning("UAC: %s returned 404 for ROC year %s; skipping", url, roc_year)
                continue
            resp.raise_for_status()
            with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
                tmp.write(resp.content)
                tmp.flush()
                rows = parse_uac_pdf(tmp.name)
            missing = sorted({r.school_zh for r in rows if r.school_zh not in school_map})
            if missing:
                raise UnknownSchoolError(missing)
            for r in rows:
                inst_id = _institution_id(conn, cache, r.school_zh, school_map, source_id, url)
                prog_id = upsert_program(conn, inst_id, r.program_zh, source_id, url)
                subjects = [{"subject": s, "weight": w} for s, w in r.subjects]
                conn.execute(
                    """insert into admission_stat (program_id, year, pathway, min_score, admitted_count,
                                                   subjects, tiebreak, source_id, source_url, fetched_at)
                       values (%s, %s, %s, %s, %s, %s, %s, %s, %s, now())
                       on conflict (program_id, year, pathway) do update set
                           min_score = excluded.min_score, admitted_count = excluded.admitted_count,
                           subjects = excluded.subjects, tiebreak = excluded.tiebreak,
                           source_id = excluded.source_id, source_url = excluded.source_url,
                           fetched_at = excluded.fetched_at""",
                    (prog_id, roc_year + 1911, PATHWAY, r.min_score, r.admitted_count,
                     Jsonb(subjects), r.tiebreak, source_id, url),
                )
                total += 1
        return total

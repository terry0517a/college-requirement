import csv
import tempfile
from pathlib import Path

import httpx
import yaml
from psycopg.types.json import Jsonb

from collegedata.parsers.uac import parse_uac_pdf
from collegedata.sources import ensure_source

CONFIG_DIR = Path(__file__).resolve().parents[3] / "config"
SCHOOLS_PATH = CONFIG_DIR / "tw_institutions.csv"
YEARS_PATH = CONFIG_DIR / "uac_years.yaml"
PATHWAY = "tw_distribution"


class UnknownSchoolError(Exception):
    def __init__(self, missing: list[str]):
        self.missing = missing
        super().__init__("unknown schools (add to tw_institutions.csv): " + ", ".join(missing))


def load_school_map() -> dict[str, tuple[str, str]]:
    with SCHOOLS_PATH.open(encoding="utf-8", newline="") as f:
        return {r["name_zh"]: (r["name_en"], r["domain"]) for r in csv.DictReader(f)}


def load_years() -> list[dict]:
    return yaml.safe_load(YEARS_PATH.read_text(encoding="utf-8"))


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

    def __init__(self, client: httpx.Client | None = None, years: list[int] | None = None):
        self.client = client
        self.years = years

    def run(self, conn) -> int:
        client = self.client or httpx.Client(timeout=60, follow_redirects=True)
        source_id = ensure_source(conn, "uac")
        school_map = load_school_map()
        cache: dict[str, int] = {}
        total = 0
        for entry in load_years():
            roc_year, url = entry["roc_year"], entry["url"]
            if self.years is not None and roc_year not in self.years:
                continue
            resp = client.get(url, timeout=60)
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
                prog_id = conn.execute(
                    """insert into program (institution_id, name_zh, name_en, source_id, source_url, fetched_at)
                       values (%s, %s, NULL, %s, %s, now())
                       on conflict (institution_id, name_zh) do update set
                           name_en = NULL, source_id = excluded.source_id,
                           source_url = excluded.source_url, fetched_at = excluded.fetched_at
                       returning id""",
                    (inst_id, r.program_zh, source_id, url),
                ).fetchone()[0]
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

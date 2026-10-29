"""Weekly College Scorecard job: U.S. bachelor's-granting institutions with admissions data."""
import datetime
import os
import time

import httpx
from psycopg.types.json import Jsonb

from collegedata.parsers.scorecard import School, YearStats, fields_param, load_program_map, parse_school
from collegedata.sources import ensure_source

SCORECARD_URL = "https://api.data.gov/ed/collegescorecard/v1/schools"
BASE_FILTER = {
    "school.degrees_awarded.predominant": 3,
    "school.operating": 1,
    "latest.admissions.admission_rate.overall__range": "0.0001..1",
}
PER_PAGE = 100
YEARS_BACK = 2
MAX_PROBE_YEARS = 6
PATHWAY = "us_freshman"
SYSTEM_CODE = "us_sat"
ALL_PROGRAM_CODE = "all"
ALL_PROGRAM_NAME = "All undergraduate programs"


class ScorecardDataError(Exception):
    pass


def upsert_institution(conn, school: School, source_id: int, source_url: str) -> int:
    values = (school.name, school.city, school.region, school.control, school.web_url, source_id, source_url)
    row = conn.execute("select id from institution where scorecard_id = %s", (school.scorecard_id,)).fetchone()
    if row:
        conn.execute(
            """update institution set name_en = %s, city = %s, region = %s, control = %s, web_url = %s,
                   source_id = %s, source_url = %s, fetched_at = now()
               where id = %s""",
            (*values, row[0]),
        )
        return row[0]
    if school.main_campus and school.domain is not None:
        row = conn.execute(
            "select id from institution where country_code = 'US' and domain = %s and scorecard_id is null",
            (school.domain,),
        ).fetchone()
        if row:
            conn.execute(
                """update institution set name_en = %s, city = %s, region = %s, control = %s, web_url = %s,
                       source_id = %s, source_url = %s, fetched_at = now(), scorecard_id = %s
                   where id = %s""",
                (*values, school.scorecard_id, row[0]),
            )
            return row[0]
    domain = school.domain
    if domain is None or conn.execute(
        "select 1 from institution where country_code = 'US' and domain = %s", (domain,)
    ).fetchone():
        domain = f"{school.domain or 'scorecard'}#{school.scorecard_id}"
    return conn.execute(
        """insert into institution (country_code, name_en, domain, web_url, control, city, region,
                                    scorecard_id, source_id, source_url, fetched_at)
           values ('US', %s, %s, %s, %s, %s, %s, %s, %s, %s, now()) returning id""",
        (school.name, domain, school.web_url, school.control, school.city, school.region,
         school.scorecard_id, source_id, source_url),
    ).fetchone()[0]


UPSERT_PROGRAM_SQL = """
insert into program (institution_id, code, name_en, field_code, source_id, source_url, fetched_at)
values (%s, %s, %s, %s, %s, %s, now())
on conflict (institution_id, code) where code is not null do update set
    name_en = excluded.name_en, field_code = excluded.field_code,
    source_id = excluded.source_id, source_url = excluded.source_url, fetched_at = excluded.fetched_at
returning id
"""


def upsert_programs(conn, inst_id: int, school: School, program_map: dict, source_id, source_url) -> int:
    """Programs the school no longer flags are kept, so site pages do not vanish year to year."""
    all_id = conn.execute(
        UPSERT_PROGRAM_SQL, (inst_id, ALL_PROGRAM_CODE, ALL_PROGRAM_NAME, None, source_id, source_url)
    ).fetchone()[0]
    for key in school.program_keys:
        p = program_map[key]
        conn.execute(UPSERT_PROGRAM_SQL, (inst_id, p["cip2"], p["name_en"], p["field_code"], source_id, source_url))
    return all_id


def _pct(r: tuple[int, int] | None) -> dict | None:
    return None if r is None else {"p25": r[0], "p75": r[1]}


def build_requirement(ys: YearStats) -> dict:
    total = None
    if ys.sat_rw is not None and ys.sat_math is not None:
        total = (ys.sat_rw[0] + ys.sat_math[0], ys.sat_rw[1] + ys.sat_math[1])
    return {
        "sat": {"rw": _pct(ys.sat_rw), "math": _pct(ys.sat_math), "total": _pct(total)},
        "act": {"composite": _pct(ys.act)},
    }


def upsert_year(conn, inst_id: int, all_program_id: int, ys: YearStats, source_id, source_url) -> None:
    if ys.admission_rate is not None:
        conn.execute(
            """insert into admission_stat (program_id, year, pathway, admission_rate, admitted_count, min_score,
                                           subjects, source_id, source_url, fetched_at)
               values (%s, %s, %s, %s, NULL, NULL, '[]', %s, %s, now())
               on conflict (program_id, year, pathway) do update set
                   admission_rate = excluded.admission_rate, admitted_count = excluded.admitted_count,
                   min_score = excluded.min_score, subjects = excluded.subjects,
                   source_id = excluded.source_id, source_url = excluded.source_url,
                   fetched_at = excluded.fetched_at""",
            (all_program_id, ys.year, PATHWAY, ys.admission_rate, source_id, source_url),
        )
    if ys.sat_rw is not None or ys.sat_math is not None or ys.act is not None:
        conn.execute(
            """insert into admission_requirement (program_id, year, pathway, system_code, requirement,
                                                  source_id, source_url, fetched_at)
               values (%s, %s, %s, %s, %s, %s, %s, now())
               on conflict (program_id, year, pathway) do update set
                   system_code = excluded.system_code, requirement = excluded.requirement,
                   source_id = excluded.source_id, source_url = excluded.source_url,
                   fetched_at = excluded.fetched_at""",
            (all_program_id, ys.year, PATHWAY, SYSTEM_CODE, Jsonb(build_requirement(ys)), source_id, source_url),
        )
    for residency, tuition in (("local", ys.tuition_in_state), ("out_of_state", ys.tuition_out_of_state)):
        if tuition is None:
            continue
        conn.execute(
            """insert into cost (institution_id, year, residency, tuition, currency, source_id, source_url, fetched_at)
               values (%s, %s, %s, %s, 'USD', %s, %s, now())
               on conflict (institution_id, year, residency) do update set
                   tuition = excluded.tuition, currency = excluded.currency,
                   source_id = excluded.source_id, source_url = excluded.source_url,
                   fetched_at = excluded.fetched_at""",
            (inst_id, ys.year, residency, tuition, source_id, source_url),
        )
    if ys.student_size is not None or ys.completion_rate is not None or ys.median_earnings is not None:
        conn.execute(
            """insert into institution_stat (institution_id, year, student_size, completion_rate, median_earnings,
                                             currency, source_id, source_url, fetched_at)
               values (%s, %s, %s, %s, %s, 'USD', %s, %s, now())
               on conflict (institution_id, year) do update set
                   student_size = excluded.student_size, completion_rate = excluded.completion_rate,
                   median_earnings = excluded.median_earnings, currency = excluded.currency,
                   source_id = excluded.source_id, source_url = excluded.source_url,
                   fetched_at = excluded.fetched_at""",
            (inst_id, ys.year, ys.student_size, ys.completion_rate, ys.median_earnings, source_id, source_url),
        )


class ScorecardJob:
    name = "scorecard"

    def __init__(self, client: httpx.Client | None = None, api_key: str | None = None,
                 today: datetime.date | None = None, limit: int | None = None):
        self.client = client
        self.api_key = api_key if api_key is not None else os.environ.get("SCORECARD_API_KEY")
        self.today = today
        self.limit = limit
        self._requested = False

    def _get(self, client: httpx.Client, params: dict) -> httpx.Response:
        """One API request; waits 1 s after the previous one and fails on any non-2xx."""
        if self._requested:
            time.sleep(1)
        self._requested = True
        resp = client.get(SCORECARD_URL, params={**params, "api_key": self.api_key})
        resp.raise_for_status()
        return resp

    def latest_year(self, client) -> int:
        start = (self.today or datetime.date.today()).year
        for y in range(start, start - MAX_PROBE_YEARS, -1):
            params = {**BASE_FILTER, f"{y}.admissions.admission_rate.overall__range": "0.0001..1",
                      "per_page": 1, "fields": "id"}
            if (self._get(client, params).json().get("metadata") or {}).get("total", 0) > 0:
                return y
        raise ScorecardDataError(
            f"no admissions data for any year {start - MAX_PROBE_YEARS + 1}..{start}")

    def run(self, conn) -> int:
        client = self.client or httpx.Client(timeout=60)
        self._requested = False
        source_id = ensure_source(conn, "scorecard")
        program_map = load_program_map()
        latest = self.latest_year(client)
        years = [latest - i for i in range(YEARS_BACK + 1)]
        fields = fields_param(years)
        processed = 0
        page = 0
        while True:
            resp = self._get(client, {**BASE_FILTER, "per_page": PER_PAGE, "page": page,
                                      "sort": "id", "fields": fields})
            data = resp.json()
            results = data.get("results") or []
            source_url = str(resp.request.url.copy_remove_param("api_key"))
            for rec in results:
                school = parse_school(rec, years)
                inst_id = upsert_institution(conn, school, source_id, source_url)
                all_id = upsert_programs(conn, inst_id, school, program_map, source_id, source_url)
                for ys in school.years:
                    upsert_year(conn, inst_id, all_id, ys, source_id, source_url)
                processed += 1
                if self.limit is not None and processed >= self.limit:
                    return processed
            total = (data.get("metadata") or {}).get("total", 0)
            if not results or (page + 1) * PER_PAGE >= total:
                return processed
            page += 1

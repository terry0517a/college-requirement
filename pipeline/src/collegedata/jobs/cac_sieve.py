import datetime
import logging
import re

from psycopg.types.json import Jsonb

from collegedata.cac_http import CacFetcher, make_client
from collegedata.jobs.cac_common import (
    BASE, Budget, UnitQualityError, finish, merge_requirement, pending_units, run_units, upsert_program,
)
from collegedata.jobs.uac import UnknownSchoolError, _institution_id, load_school_map
from collegedata.parsers.cac_sieve import SieveRow, normalize_program_name, parse_sieve_image
from collegedata.sources import ensure_source

PATHWAY = "tw_apply"
MAX_SKIP_RATIO = 0.05
TIEBREAK = "同級分超額篩選"

log = logging.getLogger(__name__)


def target_years(today: datetime.date) -> list[int]:
    cur = today.year - 1911 if today >= datetime.date(today.year, 5, 1) else today.year - 1912
    return [cur, cur - 1, cur - 2]


def college_list_url(roc: int) -> str:
    return f"{BASE}/cacportal/apply_his_report/{roc}/{roc}_sieve_standard/collegeList.htm"


def image_url(roc: int, school_code: str) -> str:
    return f"{BASE}/cacportal/apply_his_report/{roc}/{roc}_sieve_standard/report/pict/{school_code}.png"


def parse_college_list(html: str) -> list[tuple[str, str]]:
    return [(m.group(2), m.group(3).strip())
            for m in re.finditer(r'report/(\d{3})\.htm">\((\d{3})\)([^<]+)<', html)]


def requirement_from_row(r: SieveRow, image_url: str) -> dict:
    return {
        "cac_code": r.cac_code,
        "group": r.group,
        "gender": r.gender,
        "quota": r.quota,
        "thresholds": r.thresholds,
        "multipliers": {k: (str(v) if v is not None else None) for k, v in r.multipliers.items()},
        "extra": r.extra,
        "sources": {"sieve_image": image_url},
    }


def sieve_json(r: SieveRow) -> list[dict]:
    return [{"order": lv.order, "label": lv.label, "subjects": lv.subjects, "min_score": str(lv.min_score)}
            for lv in r.sieve]


class CacSieveJob:
    name = "cac_sieve"
    row_count_guard = False
    retryable = False  # a retry would re-download images; failed units are retried next run

    def __init__(self, client=None, today=None, parse=parse_sieve_image, budget=None, fetcher=None):
        self.fetcher = fetcher or CacFetcher(client or make_client())
        self.today = today
        self.parse = parse
        self.budget = budget

    def run(self, conn) -> int:
        if self.budget is None:  # once per job instance, never per attempt
            self.budget = Budget.from_env()
        source_id = ensure_source(conn, "cac")
        school_map = load_school_map()
        cache: dict[str, int] = {}
        names: dict[tuple[int, str], str] = {}
        units: list[tuple[int, str, str]] = []
        for i, roc in enumerate(target_years(self.today or datetime.date.today())):
            list_url = college_list_url(roc)
            resp = self.fetcher.get(list_url)
            if resp.status_code == 404 and i > 0:
                log.warning("CAC sieve: %s returned 404 for ROC year %s; skipping", list_url, roc)
                continue
            resp.raise_for_status()
            schools = parse_college_list(resp.text)
            if not schools:
                raise ValueError(f"no schools found in {list_url} (format change?)")
            missing = sorted({n for _, n in schools if n not in school_map})
            if missing:
                raise UnknownSchoolError(missing)
            for c, n in schools:
                names[(roc, c)] = n
                units.append((roc, c, image_url(roc, c)))
        stats = run_units(
            conn, self.name, pending_units(conn, self.name, units),
            lambda r, c: self._process(conn, r, c, names[(r, c)], image_url(r, c), school_map, cache, source_id),
            self.budget, cache, "CAC sieve",
        )
        finish(stats.attempted, stats.succeeded, self.name)
        return stats.written

    def _process(self, conn, roc, code, school_zh, url, school_map, cache, source_id) -> tuple[int, int]:
        png = self.fetcher.download(url)
        res = self.parse(png, code)
        for w in res.warnings:
            log.warning("CAC sieve %s/%s: %s", roc, code, w)
        total = len(res.rows) + res.rows_skipped
        if total and res.rows_skipped / total > MAX_SKIP_RATIO:
            raise UnitQualityError(f"{res.rows_skipped}/{total} rows skipped", res.rows_skipped)
        if total == 0:
            raise UnitQualityError("no rows parsed")
        year = roc + 1911
        count = 0
        for r in res.rows:
            inst_id = _institution_id(conn, cache, school_zh, school_map, source_id, url)
            pid = upsert_program(conn, inst_id, normalize_program_name(r.name, r.gender), source_id, url)
            merge_requirement(conn, pid, year, requirement_from_row(r, url), source_id, url)
            conn.execute(
                """insert into admission_stat (program_id, year, pathway, min_score, admitted_count,
                                               subjects, sieve, tiebreak, source_id, source_url, fetched_at)
                   values (%s, %s, %s, NULL, NULL, '[]'::jsonb, %s, %s, %s, %s, now())
                   on conflict (program_id, year, pathway) do update set
                       sieve = excluded.sieve, tiebreak = excluded.tiebreak,
                       source_id = excluded.source_id, source_url = excluded.source_url,
                       fetched_at = excluded.fetched_at""",
                (pid, year, PATHWAY, Jsonb(sieve_json(r)), TIEBREAK if r.overflow_tiebreak else None, source_id, url),
            )
            count += 1
        return count, res.rows_skipped

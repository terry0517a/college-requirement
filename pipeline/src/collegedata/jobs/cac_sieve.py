import datetime
import logging
import re

from psycopg.types.json import Jsonb

from collegedata.cac_http import BusyError, CacFetcher, make_client
from collegedata.jobs.cac_common import (
    BASE, Budget, done_units, finish, merge_requirement, record_unit, upsert_program,
)
from collegedata.jobs.uac import UnknownSchoolError, _institution_id, load_school_map
from collegedata.parsers.cac_sieve import SieveRow, normalize_program_name, parse_sieve_image
from collegedata.sources import ensure_source

PATHWAY = "tw_apply"
MAX_SKIP_RATIO = 0.05
TIEBREAK = "同級分超額篩選"

log = logging.getLogger(__name__)


class UnitQualityError(ValueError):
    """The parse was unusable; carries rows_skipped for the cac_fetch diagnostic."""

    def __init__(self, msg: str, rows_skipped: int = 0):
        super().__init__(msg)
        self.rows_skipped = rows_skipped


def target_years(today: datetime.date) -> list[int]:
    cur = today.year - 1911 if today >= datetime.date(today.year, 5, 1) else today.year - 1912
    return [cur, cur - 1, cur - 2]


def college_list_url(roc: int) -> str:
    return f"{BASE}/cacportal/apply_his_report/{roc}/{roc}_sieve_standard/report/{roc}_collegeList.htm"


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

    def __init__(self, client=None, today=None, parse=parse_sieve_image, budget=None, fetcher=None):
        self.fetcher = fetcher or CacFetcher(client or make_client())
        self.today = today
        self.parse = parse
        self.budget = budget

    def run(self, conn) -> int:
        budget = self.budget or Budget.from_env()
        source_id = ensure_source(conn, "cac")
        school_map = load_school_map()
        cache: dict[str, int] = {}
        years = target_years(self.today or datetime.date.today())
        attempted = succeeded = processed = written = 0
        busy = False
        for i, roc in enumerate(years):
            list_url = college_list_url(roc)
            try:
                resp = self.fetcher.get(list_url)
            except BusyError:
                if succeeded == 0:
                    raise
                log.warning("CAC sieve: busy fetching %s; stopping with %d schools done", list_url, succeeded)
                break
            if resp.status_code == 404 and i > 0:
                log.warning("CAC sieve: %s returned 404 for ROC year %s; skipping", list_url, roc)
                continue
            resp.raise_for_status()
            done = done_units(conn, self.name, roc)
            units = [(c, n) for c, n in parse_college_list(resp.text) if c not in done]
            for code, school_zh in units:
                if budget.exhausted(processed):
                    break
                attempted += 1
                url = image_url(roc, code)
                cache_before = dict(cache)
                try:
                    with conn.transaction():
                        n, skipped = self._process(conn, roc, code, school_zh, url, school_map, cache, source_id)
                        record_unit(conn, self.name, roc, code, url, "done", n, skipped, None)
                except BusyError:
                    cache.clear()
                    cache.update(cache_before)
                    if succeeded == 0:
                        raise
                    log.warning("CAC sieve: busy at %s/%s; stopping with %d schools done", roc, code, succeeded)
                    busy = True
                    break
                except UnknownSchoolError:
                    raise
                except Exception as e:  # noqa: BLE001 - recorded per unit
                    # The savepoint rolled back any institution inserted for this unit.
                    cache.clear()
                    cache.update(cache_before)
                    log.warning("CAC sieve %s/%s failed: %s: %s", roc, code, type(e).__name__, e)
                    record_unit(conn, self.name, roc, code, url, "failed", 0, getattr(e, "rows_skipped", 0), f"{type(e).__name__}: {e}")
                else:
                    succeeded += 1
                    written += n
                processed += 1
            if busy:
                break
        finish(attempted, succeeded, self.name)
        return written

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
        if res.rows and school_zh not in school_map:
            raise UnknownSchoolError([school_zh])
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

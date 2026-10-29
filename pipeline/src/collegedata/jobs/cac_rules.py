import datetime
import logging

from collegedata.cac_http import BusyError, CacFetcher, make_client
from collegedata.jobs.cac_common import (
    BASE, Budget, done_units, finish, merge_requirement, record_unit, upsert_program,
)
from collegedata.jobs.uac import UnknownSchoolError, _institution_id, load_school_map
from collegedata.parsers.cac_rules import (
    RulesPage, find_system_url, parse_code_list, parse_rules_page, parse_total_gsd,
)
from collegedata.parsers.cac_sieve import normalize_program_name
from collegedata.sources import ensure_source

log = logging.getLogger(__name__)


class NotPublishedYet(Exception):
    pass


class UnitQualityError(ValueError):
    """Every page of the school failed to parse; carries rows_skipped for cac_fetch."""

    def __init__(self, msg: str, rows_skipped: int = 0):
        super().__init__(msg)
        self.rows_skipped = rows_skipped


def target_year(today: datetime.date) -> int:
    return today.year - 1910 if today >= datetime.date(today.year, 11, 1) else today.year - 1911


def query_url(roc: int) -> str:
    return f"{BASE}/apply{roc}/query.php"


def requirement_from_page(p: RulesPage, page_url: str) -> dict:
    return {
        "cac_code": p.cac_code,
        "quota": p.quota,
        "gender": p.gender,
        "thresholds": p.thresholds,
        "multipliers": {k: (str(v) if v is not None else None) for k, v in p.multipliers.items()},
        "stage2": {
            "gsat_weights": {k: str(v) for k, v in p.gsat_weights.items()},
            "stage1_pct": p.stage1_pct,
            "items": [{"name": i.name, "threshold": i.threshold, "pct": i.pct} for i in p.items],
            "tiebreak_order": p.tiebreak_order,
            "review_items": p.review_items,
            "exam_date": p.exam_date,
            "expected_candidates": p.expected_candidates,
            "fee": p.fee,
            "website": p.website,
            "overflow_rule": p.overflow_rule,
        },
        "sources": {"rules_page": page_url},
    }


class CacRulesJob:
    name = "cac_rules"
    row_count_guard = False

    def __init__(self, client=None, today=None, budget=None, fetcher=None):
        self.fetcher = fetcher or CacFetcher(client or make_client())
        self.today = today
        self.budget = budget

    def run(self, conn) -> int:
        today = self.today or datetime.date.today()
        budget = self.budget or Budget.from_env()
        roc = target_year(today)
        resp = self.fetcher.get(query_url(roc))
        system = find_system_url(resp.text, roc)
        if system is None:
            if today.month in (11, 12):
                log.warning("CAC rules: ROC %s system not published yet; nothing to do", roc)
                return 0
            raise NotPublishedYet(f"CAC ROC {roc} rules system not published")
        total = self.fetcher.get(system + "TotalGsdShow.htm")
        done = done_units(conn, self.name, roc)
        units = sorted((c, n) for c, n, _ in parse_total_gsd(total.text) if c not in done)

        source_id = ensure_source(conn, "cac")
        school_map = load_school_map()
        cache: dict[str, int] = {}
        attempted = succeeded = processed = written = 0
        for code, _school_zh in units:
            if budget.exhausted(processed):
                break
            attempted += 1
            url = system + "ShowGsd.php"
            cache_before = dict(cache)
            try:
                with conn.transaction():
                    n, skipped = self._process(conn, roc, code, system, school_map, cache, source_id)
                    record_unit(conn, self.name, roc, code, url, "done", n, skipped, None)
            except BusyError:
                cache.clear()
                cache.update(cache_before)
                if succeeded == 0:
                    raise
                log.warning("CAC rules: busy at %s/%s; stopping with %d schools done", roc, code, succeeded)
                break
            except UnknownSchoolError:
                raise
            except Exception as e:  # noqa: BLE001 - recorded per unit
                cache.clear()
                cache.update(cache_before)
                log.warning("CAC rules %s/%s failed: %s: %s", roc, code, type(e).__name__, e)
                record_unit(conn, self.name, roc, code, url, "failed", 0, getattr(e, "rows_skipped", 0), f"{type(e).__name__}: {e}")
            else:
                succeeded += 1
                written += n
            processed += 1
        finish(attempted, succeeded, self.name)
        return written

    def _process(self, conn, roc, code, system, school_map, cache, source_id) -> tuple[int, int]:
        listing = self.fetcher.post(
            system + "ShowGsd.php",
            data={"TxtGsdCode": code, "SubTxtGsdCode": "依校系代碼查詢", "action": "SubTxtGsdCode"},
        )
        year = roc + 1911
        written = skipped = 0
        for gsd in parse_code_list(listing.text):
            page_url = system + f"html/{roc}_{gsd}.htm?v=1.0"
            try:
                p = parse_rules_page(self.fetcher.get(page_url).text)
            except ValueError as e:
                log.warning("CAC rules %s/%s: skipped %s: %s", roc, gsd, page_url, e)
                skipped += 1
                continue
            if p.school not in school_map:
                raise UnknownSchoolError([p.school])
            inst_id = _institution_id(conn, cache, p.school, school_map, source_id, page_url)
            pid = upsert_program(conn, inst_id, normalize_program_name(p.name, p.gender), source_id, page_url)
            merge_requirement(conn, pid, year, requirement_from_page(p, page_url), source_id, page_url)
            written += 1
        if written == 0:
            raise UnitQualityError(f"no rules page parsed for school {code}", skipped)
        return written, skipped

import datetime
import logging

from collegedata.cac_http import CacFetcher, make_client
from collegedata.jobs.cac_common import (
    BASE, Budget, UnitQualityError, finish, merge_requirement, pending_units, run_units, upsert_program,
)
from collegedata.jobs.uac import UnknownSchoolError, _institution_id, load_school_map
from collegedata.parsers.cac_rules import (
    RulesPage, find_system_url, parse_code_list, parse_rules_page, parse_total_gsd,
)
from collegedata.parsers.cac_sieve import (
    MULTIPLIER_KEYS, THRESHOLD_KEYS, normalize_program_name, parse_level, parse_listening,
)
from collegedata.sources import ensure_source

log = logging.getLogger(__name__)


class NotPublishedYet(Exception):
    pass


def target_year(today: datetime.date) -> int:
    return today.year - 1910 if today >= datetime.date(today.year, 11, 1) else today.year - 1911


def query_url(roc: int) -> str:
    return f"{BASE}/apply{roc}/query.php"


def _threshold(subject: str, raw: str | None) -> str | None:
    """Same value set as the sieve image: 頂標…底標 for subjects, A/B/C for 英聽."""
    if raw is None:
        return None
    return parse_listening(raw) if subject == "英聽" else parse_level(raw)


def requirement_from_page(p: RulesPage, page_url: str) -> dict:
    return {
        "cac_code": p.cac_code,
        "quota": p.quota,
        "gender": p.gender,
        "thresholds": {k: _threshold(k, p.thresholds.get(k)) for k in THRESHOLD_KEYS},
        "multipliers": {k: (str(p.multipliers[k]) if p.multipliers.get(k) is not None else None)
                        for k in MULTIPLIER_KEYS},
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
    retryable = False  # a retry would re-fetch every page; failed units are retried next run

    def __init__(self, client=None, today=None, budget=None, fetcher=None):
        self.fetcher = fetcher or CacFetcher(client or make_client())
        self.today = today
        self.budget = budget

    def run(self, conn) -> int:
        today = self.today or datetime.date.today()
        if self.budget is None:  # once per job instance, never per attempt
            self.budget = Budget.from_env()
        roc = target_year(today)
        resp = self.fetcher.get(query_url(roc))
        resp.raise_for_status()
        system = find_system_url(resp.text, roc)
        if system is None:
            if today.month in (11, 12):
                log.warning("CAC rules: ROC %s system not published yet; nothing to do", roc)
                return 0
            raise NotPublishedYet(f"CAC ROC {roc} rules system not published")
        total = self.fetcher.get(system + "TotalGsdShow.htm")
        total.raise_for_status()
        schools = parse_total_gsd(total.text)
        if not schools:
            raise ValueError(f"no schools found in {system}TotalGsdShow.htm (format change?)")
        school_map = load_school_map()
        missing = sorted({n for _, n, _ in schools if n not in school_map})
        if missing:
            raise UnknownSchoolError(missing)

        source_id = ensure_source(conn, "cac")
        cache: dict[str, int] = {}
        units = pending_units(conn, self.name, [(roc, c, system + "ShowGsd.php") for c, _, _ in schools])
        stats = run_units(
            conn, self.name, units,
            lambda r, c: self._process(conn, r, c, system, school_map, cache, source_id),
            self.budget, cache, "CAC rules",
        )
        finish(stats.attempted, stats.succeeded, self.name)
        return stats.written

    def _process(self, conn, roc, code, system, school_map, cache, source_id) -> tuple[int, int]:
        listing = self.fetcher.post(
            system + "ShowGsd.php",
            data={"TxtGsdCode": code, "SubTxtGsdCode": "依校系代碼查詢", "action": "SubTxtGsdCode"},
        )
        listing.raise_for_status()
        codes = parse_code_list(listing.text)
        if not codes:
            raise ValueError(f"no department codes listed for school {code} (format change?)")
        year = roc + 1911
        written = skipped = 0
        for gsd in codes:
            page_url = system + f"html/{roc}_{gsd}.htm?v=1.0"
            page = self.fetcher.get(page_url)
            page.raise_for_status()  # an error page fails the unit instead of becoming a skipped page
            try:
                p = parse_rules_page(page.text)
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

"""Helpers shared by the cac.edu.tw jobs."""
import logging
import os
import time
from dataclasses import dataclass
from datetime import timedelta
from typing import Callable, Iterable

from psycopg.types.json import Jsonb

from collegedata.cac_http import BusyError

BASE = "https://www.cac.edu.tw"
DEFAULT_MAX_SCHOOLS = 10
DEFAULT_TIME_BUDGET_MINUTES = 75

log = logging.getLogger(__name__)


@dataclass
class Budget:
    max_schools: int
    time_budget: timedelta
    started: float
    clock: Callable[[], float] = time.monotonic

    @classmethod
    def from_env(cls, clock=time.monotonic) -> "Budget":
        # Empty strings (unset GitHub Actions inputs) count as unset.
        max_schools = int(os.environ.get("CAC_MAX_SCHOOLS") or DEFAULT_MAX_SCHOOLS)
        minutes = float(os.environ.get("CAC_TIME_BUDGET_MINUTES") or DEFAULT_TIME_BUDGET_MINUTES)
        return cls(max_schools, timedelta(minutes=minutes), clock(), clock)

    def exhausted(self, done_count: int, clock=None) -> bool:
        now = (clock or self.clock)()
        return done_count >= self.max_schools or now - self.started >= self.time_budget.total_seconds()


def done_units(conn, job: str, roc_year: int) -> set[str]:
    rows = conn.execute(
        "select school_code from cac_fetch where job = %s and roc_year = %s and status = 'done'",
        (job, roc_year),
    ).fetchall()
    return {r[0] for r in rows}


def record_unit(conn, job, roc_year, school_code, url, status, rows_written, rows_skipped, error) -> None:
    conn.execute(
        """insert into cac_fetch (job, roc_year, school_code, url, status, rows_written, rows_skipped, error, fetched_at)
           values (%s, %s, %s, %s, %s, %s, %s, %s, now())
           on conflict (job, roc_year, school_code) do update set
               url = excluded.url, status = excluded.status, rows_written = excluded.rows_written,
               rows_skipped = excluded.rows_skipped, error = excluded.error, fetched_at = excluded.fetched_at""",
        (job, roc_year, school_code, url, status, rows_written, rows_skipped, error),
    )


def upsert_program(conn, inst_id: int, name_zh: str, source_id: int, source_url: str) -> int:
    return conn.execute(
        """insert into program (institution_id, name_zh, name_en, source_id, source_url, fetched_at)
           values (%s, %s, NULL, %s, %s, now())
           on conflict (institution_id, name_zh) do update set
               source_id = excluded.source_id,
               source_url = excluded.source_url, fetched_at = excluded.fetched_at
           returning id""",
        (inst_id, name_zh, source_id, source_url),
    ).fetchone()[0]


def merge_requirement(conn, program_id, year, requirement: dict, source_id, source_url) -> None:
    conn.execute(
        """insert into admission_requirement (program_id, year, pathway, system_code, requirement, source_id, source_url, fetched_at)
           values (%s, %s, 'tw_apply', 'tw_gsat', %s, %s, %s, now())
           on conflict (program_id, year, pathway) do update set
             requirement = (admission_requirement.requirement || excluded.requirement)
                           || jsonb_build_object('sources',
                                coalesce(admission_requirement.requirement->'sources', '{}'::jsonb)
                                || coalesce(excluded.requirement->'sources', '{}'::jsonb)),
             source_id = excluded.source_id, source_url = excluded.source_url, fetched_at = excluded.fetched_at""",
        (program_id, year, Jsonb(requirement), source_id, source_url),
    )


def finish(attempted: int, succeeded: int, job: str) -> None:
    if attempted >= 1 and succeeded == 0:
        raise RuntimeError(f"{job}: all {attempted} units failed")


class UnitQualityError(ValueError):
    """The parse was unusable; carries rows_skipped for the cac_fetch diagnostic."""

    def __init__(self, msg: str, rows_skipped: int = 0):
        super().__init__(msg)
        self.rows_skipped = rows_skipped


@dataclass
class UnitStats:
    attempted: int = 0
    succeeded: int = 0
    processed: int = 0
    written: int = 0
    busy: bool = False


def run_units(conn, job: str, units: Iterable[tuple[int, str, str]],
              process: Callable[[int, str], tuple[int, int]], budget: Budget,
              cache: dict, log_prefix: str, stats: UnitStats | None = None) -> UnitStats:
    """Run (roc_year, school_code, url) units, each in its own savepoint.

    process(roc, code) -> (rows_written, rows_skipped). Pass the same `stats` across
    calls to share budget/busy accounting. BusyError stops the loop (stats.busy) once
    something has succeeded, else is re-raised. UnknownSchoolError aborts the job;
    any other error records the unit as failed and continues.
    """
    from collegedata.jobs.uac import UnknownSchoolError  # uac imports this module

    st = stats or UnitStats()
    for roc, code, url in units:
        if budget.exhausted(st.processed):
            break
        st.attempted += 1
        cache_before = dict(cache)
        try:
            with conn.transaction():
                n, skipped = process(roc, code)
                record_unit(conn, job, roc, code, url, "done", n, skipped, None)
        except BusyError:
            cache.clear()
            cache.update(cache_before)
            if st.succeeded == 0:
                raise
            log.warning("%s: busy at %s/%s; stopping with %d schools done", log_prefix, roc, code, st.succeeded)
            st.busy = True
            break
        except UnknownSchoolError:
            raise
        except Exception as e:  # noqa: BLE001 - recorded per unit
            # The savepoint rolled back any institution inserted for this unit.
            cache.clear()
            cache.update(cache_before)
            log.warning("%s %s/%s failed: %s: %s", log_prefix, roc, code, type(e).__name__, e)
            record_unit(conn, job, roc, code, url, "failed", 0, getattr(e, "rows_skipped", 0), f"{type(e).__name__}: {e}")
        else:
            st.succeeded += 1
            st.written += n
        st.processed += 1
    return st

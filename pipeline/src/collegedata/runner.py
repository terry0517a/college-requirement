from dataclasses import dataclass
from typing import Callable, Literal, Protocol

MIN_ROW_RATIO = 0.5
MAX_ATTEMPTS = 2


class Job(Protocol):
    name: str

    def run(self, conn) -> int: ...


@dataclass
class FetchResult:
    status: Literal["success", "failed"]
    rows_written: int | None
    error: str | None


REGISTRY: dict[str, Callable[[], Job]] = {}


class RowCountDropped(Exception):
    pass


def _attempt(job: Job, conn) -> int:
    """Run the job inside a savepoint; any exception rolls its writes back.

    Except an error with `keep_writes = True` (e.g. every cac unit failed: the
    cac_fetch 'failed' rows must survive): the job still fails but keeps its writes.
    """
    kept: Exception | None = None
    with conn.transaction():
        try:
            rows = job.run(conn)
        except Exception as exc:
            if not getattr(exc, "keep_writes", False):
                raise
            kept = exc
        else:
            prev = conn.execute(
                "select rows_written from fetch_log where job = %s and status = 'success' "
                "order by id desc limit 1",
                (job.name,),
            ).fetchone()
            guarded = getattr(job, "row_count_guard", True)
            if guarded and prev and prev[0] and rows < prev[0] * MIN_ROW_RATIO:
                raise RowCountDropped(f"row count dropped from {prev[0]} to {rows}")
    if kept is not None:
        raise kept
    return rows


def run_job(job: Job, conn) -> FetchResult:
    """Never commits; the caller controls the outer transaction."""
    log_id = conn.execute(
        "insert into fetch_log(job, started_at, status) values (%s, now(), 'running') returning id",
        (job.name,),
    ).fetchone()[0]

    result = FetchResult("failed", None, "job did not run")
    for _ in range(MAX_ATTEMPTS):
        try:
            result = FetchResult("success", _attempt(job, conn), None)
            break
        except RowCountDropped as exc:
            # Deterministic: re-running would give the same count, so do not retry.
            result = FetchResult("failed", None, f"{type(exc).__name__}: {exc}")
            break
        except Exception as exc:  # noqa: BLE001 - recorded in fetch_log
            result = FetchResult("failed", None, f"{type(exc).__name__}: {exc}")
            if not getattr(job, "retryable", True):
                break

    conn.execute(
        "update fetch_log set status = %s, finished_at = now(), rows_written = %s, error = %s where id = %s",
        (result.status, result.rows_written, result.error, log_id),
    )
    return result


def _register_jobs() -> None:
    from collegedata.jobs.cac_rules import CacRulesJob
    from collegedata.jobs.cac_sieve import CacSieveJob
    from collegedata.jobs.hipo import HipoJob

    from collegedata.jobs.openalex import OpenAlexJob
    from collegedata.jobs.scorecard import ScorecardJob
    from collegedata.jobs.uac import UacJob

    REGISTRY["hipo"] = lambda: HipoJob()
    REGISTRY["uac"] = lambda: UacJob()
    REGISTRY["openalex"] = lambda: OpenAlexJob()
    REGISTRY["scorecard"] = lambda: ScorecardJob()
    REGISTRY["cac_sieve"] = lambda: CacSieveJob()
    REGISTRY["cac_rules"] = lambda: CacRulesJob()


_register_jobs()

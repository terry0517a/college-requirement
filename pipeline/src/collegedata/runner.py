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
    """Run the job inside a savepoint; any exception rolls its writes back."""
    with conn.transaction():
        rows = job.run(conn)
        prev = conn.execute(
            "select rows_written from fetch_log where job = %s and status = 'success' "
            "order by id desc limit 1",
            (job.name,),
        ).fetchone()
        if prev and prev[0] and rows < prev[0] * MIN_ROW_RATIO:
            raise RowCountDropped(f"row count dropped from {prev[0]} to {rows}")
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
        except Exception as exc:  # noqa: BLE001 - recorded in fetch_log
            result = FetchResult("failed", None, str(exc))

    conn.execute(
        "update fetch_log set status = %s, finished_at = now(), rows_written = %s, error = %s where id = %s",
        (result.status, result.rows_written, result.error, log_id),
    )
    return result

from collegedata.runner import run_job

class FakeJob:
    name = "fake"
    def __init__(self, rows=None, fail_times=0):
        self.rows, self.fail_times, self.calls = rows, fail_times, 0
    def run(self, conn):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise RuntimeError("boom")
        return self.rows

def _last_log(db):
    return db.execute("select status, rows_written, error from fetch_log where job='fake' order by id desc limit 1").fetchone()

def test_success_writes_log(db):
    r = run_job(FakeJob(rows=10), db)
    assert r.status == "success" and r.rows_written == 10
    assert _last_log(db) == ("success", 10, None)

def test_retries_once_then_succeeds(db):
    job = FakeJob(rows=5, fail_times=1)
    assert run_job(job, db).status == "success" and job.calls == 2

def test_fails_after_second_error(db):
    r = run_job(FakeJob(rows=5, fail_times=2), db)
    assert r.status == "failed" and "boom" in r.error
    assert _last_log(db)[0] == "failed"

def test_row_count_drop_is_failure(db):
    run_job(FakeJob(rows=100), db)
    r = run_job(FakeJob(rows=40), db)
    assert r.status == "failed" and "row count" in r.error

def test_failure_rolls_back_job_writes(db):
    class WritingJob:
        name = "fake"
        def run(self, conn):
            conn.execute("insert into source(code,name,url) values('tmp','t','u')")
            raise RuntimeError("after write")
    run_job(WritingJob(), db)
    assert db.execute("select count(*) from source where code='tmp'").fetchone()[0] == 0

def test_row_count_guard_opt_out(db):
    class NoGuardJob(FakeJob):
        row_count_guard = False
    run_job(NoGuardJob(rows=100), db)
    r = run_job(NoGuardJob(rows=1), db)
    assert r.status == "success" and r.rows_written == 1

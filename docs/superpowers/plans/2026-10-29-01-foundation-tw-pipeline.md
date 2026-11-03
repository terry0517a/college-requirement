# 計畫 1：專案基礎與台灣分發資料管線 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立單一儲存庫、資料庫結構與 Python 資料管線，讓「全球學校主檔（台灣＋美國）、台灣分發入學歷年錄取標準、OpenAlex 強項」能由 GitHub Actions 定時自動抓進 PostgreSQL，失敗時自動開 Issue 通知。

**Architecture:** 資料庫結構以 SQL migration 存在 `supabase/migrations/`，本機用 Homebrew Postgres 跑測試，正式環境用 Supabase 免費方案。Python 管線 `pipeline/` 以「一個來源一個 Job」的方式組織，共用的 runner 負責重試、筆數防呆與 `fetch_log`。每個解析器都以本機 fixture 檔測試，不在測試中連網。

**Tech Stack:** PostgreSQL 17（本機 Homebrew、正式 Supabase）、Python 3.12 + uv、psycopg 3、httpx、pdfplumber、pytest、GitHub Actions。

**Spec:** `/Users/terry/Desktop/college requirement/設計文件.md`（第 3、6、7 節為本計畫依據）

## Global Constraints

- 每一筆學校資料都必須有 `source_id`、`source_url`、`fetched_at`，資料表以 NOT NULL 強制（設計文件 5.1.10）。
- 只用免費方案：Supabase 免費專案、GitHub Actions 公開儲存庫（設計文件 3）。
- 美國只收以學士為主的四年制機構（設計文件 6.1.1）；本計畫先把 Hipo 的美國清單全部載入主檔，篩選在計畫 2 由 Scorecard 資料決定。
- 台灣只收一般大學；分發入學資料只展示、不參與分級（設計文件 5.1.3）。
- 歷史資料保留最近三年（設計文件 6.1.1）。
- 抓取尊重 robots.txt 與合理頻率；同一來源的請求間隔至少 1 秒（設計文件 6.4）。
- 國家顯示名稱由本專案自行定義：`TW` → 「台灣 / Taiwan」、`US` → 「美國 / United States」，不使用 Hipo 的 country 字串。
- 年度一律以西元存（民國 115 → 2026）。
- Python 程式碼放在 `pipeline/src/collegedata/`，測試放在 `pipeline/tests/`，fixture 放在 `pipeline/tests/fixtures/`。
- Commit 訊息結尾加：`Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`。

## Review Focus

1. 考分會 PDF 中「普通生錄取分數」為 `-----`（錄取人數 0）的系組：應寫入 `min_score = NULL`、`admitted_count = 0`，不得跳過也不得寫成 0 分。（Task 5 測試）
2. 考分會 PDF 的校名在 `tw_institutions.csv` 找不到對應：整個 Job 必須失敗並列出缺少的校名，不得默默略過該校。（Task 6 測試）
3. 來源筆數驟降（例如 PDF 格式改版後只解析出 3 筆）：runner 須因「筆數低於上次成功的 50%」判定失敗，不得覆寫既有資料。（Task 3 測試）
4. 同一 Job 重跑：所有寫入都是 upsert，重跑兩次後筆數不變、`fetched_at` 更新。（Task 4、6 測試）
5. OpenAlex 對應錯校（同名或相似名稱）：對應時必須同時符合國家碼，且 `works_count >= 100`，否則不寫入並記錄警告。（Task 7 測試）

---

### Task 1: 儲存庫骨架與本機環境

**Files:**
- Create: `.gitignore`、`README.md`、`pipeline/pyproject.toml`、`pipeline/src/collegedata/__init__.py`、`pipeline/tests/conftest.py`、`pipeline/.env.example`
- Create: `scripts/setup-local-db.sh`

**Interfaces:**
- Produces: 環境變數 `DATABASE_URL`（正式）、`TEST_DATABASE_URL`（測試，預設 `postgresql://localhost/collegedata_test`）；pytest fixture `db`（每個測試函式一條已套用 migration、交易結束後 rollback 的 psycopg 連線）。

- [ ] **Step 1: 初始化 git 與忽略清單**

在 `/Users/terry/Desktop/college requirement` 執行 `git init -b main`。`.gitignore` 內容：`.env`、`.superpowers/`、`pipeline/.venv/`、`__pycache__/`、`*.pyc`、`node_modules/`、`.next/`、`supabase/.temp/`。

- [ ] **Step 2: 建立 Python 專案**

`pipeline/pyproject.toml`：專案名 `collegedata`，`requires-python = ">=3.12"`，依賴 `psycopg[binary]>=3.2`、`httpx>=0.27`、`pdfplumber>=0.11`、`pyyaml>=6`；dev 依賴 `pytest>=8`、`pytest-httpx>=0.30`、`pypdf>=5`。`[project.scripts] collegedata = "collegedata.cli:main"`。執行 `cd pipeline && uv python install 3.12 && uv sync`。

- [ ] **Step 3: 本機 Postgres 安裝腳本**

`scripts/setup-local-db.sh`：`brew install postgresql@17`（已裝則跳過）、`brew services start postgresql@17`、把 `/opt/homebrew/opt/postgresql@17/bin` 加進本腳本的 PATH（keg-only，使用者的 shell 也需加）、`createdb collegedata_test`（已存在則跳過）。執行它並確認 `psql collegedata_test -c 'select 1'` 成功。

- [ ] **Step 4: 寫 conftest 的 `db` fixture**

`pipeline/tests/conftest.py`：session 級 fixture 讀 `TEST_DATABASE_URL`，對該資料庫依檔名順序執行 `supabase/migrations/*.sql`（先 `drop schema public cascade; create schema public;`）；function 級 fixture `db` 開一條 `psycopg.connect(autocommit=False)` 連線，yield 後 `rollback()`。

- [ ] **Step 5: 煙霧測試**

`pipeline/tests/test_smoke.py`：
```python
def test_db_fixture_connects(db):
    assert db.execute("select 1").fetchone() == (1,)
```
Run: `cd pipeline && uv run pytest tests/test_smoke.py -v`
Expected: PASS（此時尚無 migration 檔，fixture 需容許空目錄）

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "chore: repo skeleton, python pipeline project, local test db"
```

### Task 2: 資料庫結構 migration

**Files:**
- Create: `supabase/migrations/0001_init.sql`
- Test: `pipeline/tests/test_schema.py`

**Interfaces:**
- Produces: 下列資料表（欄位名為後續所有 Task 的契約）：
  - `source(id serial pk, code text unique not null, name text not null, url text not null, license text)`
  - `institution(id serial pk, country_code char(2) not null, name_en text not null, name_zh text, domain text not null, web_url text, openalex_id text, ror_id text, control text check (control in ('public','private')), source_id int not null references source, source_url text not null, fetched_at timestamptz not null, unique(country_code, domain))`
  - `program(id serial pk, institution_id int not null references institution, name_zh text, name_en text, field_code text, level text not null default 'bachelor', source_id int not null references source, source_url text not null, fetched_at timestamptz not null, unique(institution_id, name_zh))`
  - `admission_stat(id serial pk, program_id int not null references program, year int not null, pathway text not null, min_score numeric(7,2), admitted_count int not null, subjects jsonb not null default '[]', tiebreak text, source_id int not null references source, source_url text not null, fetched_at timestamptz not null, unique(program_id, year, pathway))`
  - `admission_requirement(id serial pk, program_id int not null references program, year int not null, pathway text not null, system_code text not null, requirement jsonb not null, source_id int not null references source, source_url text not null, fetched_at timestamptz not null, unique(program_id, year, pathway))`
  - `cost(id serial pk, institution_id int not null references institution, year int not null, residency text not null check (residency in ('local','out_of_state','international')), tuition numeric(12,2) not null, currency char(3) not null, source_id int not null references source, source_url text not null, fetched_at timestamptz not null, unique(institution_id, year, residency))`
  - `strength(id serial pk, institution_id int not null references institution, topic_id text not null, topic_name text not null, field_name text not null, works_count int not null, cited_by_count int not null, rank int not null, source_id int not null references source, source_url text not null, fetched_at timestamptz not null, unique(institution_id, topic_id))`
  - `fetch_log(id serial pk, job text not null, started_at timestamptz not null, finished_at timestamptz, status text not null check (status in ('running','success','failed')), rows_written int, error text)`
  - 索引：`institution(country_code)`、`program(institution_id)`、`admission_stat(program_id, year)`、`fetch_log(job, started_at desc)`。

- [ ] **Step 1: 寫 schema 測試**

`pipeline/tests/test_schema.py`：
```python
import pytest, psycopg

def test_all_tables_exist(db):
    names = {r[0] for r in db.execute(
        "select table_name from information_schema.tables where table_schema='public'")}
    assert {"source","institution","program","admission_stat","admission_requirement",
            "cost","strength","fetch_log"} <= names

def test_institution_requires_source(db):
    with pytest.raises(psycopg.errors.NotNullViolation):
        db.execute("insert into institution(country_code,name_en,domain) values ('TW','X','x.edu.tw')")
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `cd pipeline && uv run pytest tests/test_schema.py -v`
Expected: FAIL，`test_all_tables_exist` 的集合不是子集

- [ ] **Step 3: 寫 `supabase/migrations/0001_init.sql`**

依 Interfaces 的定義建表與索引。

- [ ] **Step 4: 執行測試確認通過**

Run: `cd pipeline && uv run pytest tests/test_schema.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add supabase/migrations/0001_init.sql pipeline/tests/test_schema.py
git commit -m "feat(db): initial schema for sources, institutions, programs, stats, strengths"
```

### Task 3: 管線核心：來源登錄、runner、CLI

**Files:**
- Create: `pipeline/src/collegedata/db.py`、`pipeline/src/collegedata/sources.py`、`pipeline/src/collegedata/runner.py`、`pipeline/src/collegedata/cli.py`、`pipeline/config/sources.yaml`
- Test: `pipeline/tests/test_runner.py`

**Interfaces:**
- Produces:
  - `db.connect(url: str | None = None) -> psycopg.Connection`（`url` 預設讀 `DATABASE_URL`）
  - `sources.ensure_source(conn, code: str) -> int`：從 `config/sources.yaml` 讀該 code 的 `name`、`url`、`license`，upsert 到 `source`，回傳 id。
  - `runner.Job`（Protocol）：屬性 `name: str`、方法 `run(self, conn) -> int`（回傳寫入筆數；內部不 commit）。
  - `runner.run_job(job: Job, conn) -> FetchResult`；`FetchResult` 是 dataclass：`status: Literal["success","failed"]`、`rows_written: int | None`、`error: str | None`。
  - `runner.REGISTRY: dict[str, Callable[[], Job]]`，後續 Task 在此登錄 job 名稱。
  - CLI：`collegedata run <job_name>`，成功 exit 0、失敗 exit 1 並把錯誤印到 stderr。
- `config/sources.yaml` 初始內容（code → name/url/license）：
  - `hipo`：Hipo university-domains-list，`https://github.com/Hipo/university-domains-list`，MIT
  - `uac`：大學考試入學分發委員會，`https://www.uac.edu.tw/`，公開資料（政府資訊）
  - `openalex`：OpenAlex，`https://openalex.org/`，CC0

- [ ] **Step 1: 寫 runner 測試**

`pipeline/tests/test_runner.py`，用一個假的 Job：
```python
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
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `cd pipeline && uv run pytest tests/test_runner.py -v`
Expected: FAIL，`collegedata.runner` 不存在

- [ ] **Step 3: 實作 `db.py`、`sources.py`、`runner.py`、`cli.py`、`sources.yaml`**

`run_job` 流程（整個函式不呼叫 `commit`，交易由呼叫端控制，測試才能 rollback 隔離）：插入 `fetch_log(status='running')`；用 savepoint 包住 `job.run`，失敗則 rollback 到該 savepoint 並重試一次；成功後查上一筆同 job 的 success 筆數，若新筆數 < 上次的 50% 則 rollback 到 savepoint 並視為失敗（錯誤訊息含 `row count dropped`）；最後更新同一筆 `fetch_log` 的 `status`、`finished_at`、`rows_written`、`error`。`cli.main()` 用 `argparse`，從 `REGISTRY` 取 job，呼叫 `run_job` 後不論成敗都 `conn.commit()`（讓 fetch_log 留下紀錄；失敗的資料寫入已被 savepoint rollback）。

- [ ] **Step 4: 執行測試確認通過**

Run: `cd pipeline && uv run pytest tests/test_runner.py -v`
Expected: 5 PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/src/collegedata pipeline/config pipeline/tests/test_runner.py
git commit -m "feat(pipeline): job runner with retry, row-count guard and fetch_log"
```

### Task 4: 全球學校主檔（Hipo）

**Files:**
- Create: `pipeline/src/collegedata/jobs/__init__.py`、`pipeline/src/collegedata/jobs/hipo.py`、`pipeline/src/collegedata/countries.py`
- Create: `pipeline/tests/fixtures/hipo_sample.json`
- Test: `pipeline/tests/test_hipo.py`
- Modify: `pipeline/src/collegedata/runner.py`（在 `REGISTRY` 登錄 `"hipo"`）

**Interfaces:**
- Consumes: Task 3 的 `Job`、`ensure_source`、`REGISTRY`。
- Produces:
  - `countries.SUPPORTED: dict[str, tuple[str, str]]` = `{"TW": ("台灣", "Taiwan"), "US": ("美國", "United States")}`。
  - `hipo.HipoJob(client: httpx.Client | None = None)`，`name = "hipo"`。對每個 `SUPPORTED` 國家碼請求 `http://universities.hipolabs.com/search?country=<Hipo 的 country 名稱>`，country 名稱對照：`TW` → `Taiwan, Province of China`、`US` → `United States`。
  - `hipo.upsert_institutions(conn, records: list[dict], source_id: int, source_url: str) -> int`：每筆取 `alpha_two_code`、`name`、`domains[0]`、`web_pages[0]`，以 `(country_code, domain)` upsert 到 `institution`，回傳筆數。

- [ ] **Step 1: 建 fixture**

`pipeline/tests/fixtures/hipo_sample.json`：3 筆，照 Hipo 真實格式（欄位 `state-province`、`name`、`web_pages`、`alpha_two_code`、`domains`、`country`）：National Taiwan University（`ntu.edu.tw`，TW）、Aletheia University（`au.edu.tw`，TW）、Stanford University（`stanford.edu`，US）。

- [ ] **Step 2: 寫測試**

`pipeline/tests/test_hipo.py`：
```python
import json, pathlib, re, httpx
from collegedata.jobs.hipo import HipoJob, upsert_institutions
from collegedata.sources import ensure_source
from collegedata.runner import run_job

FIX = json.loads(pathlib.Path(__file__).with_name("fixtures").joinpath("hipo_sample.json").read_text())

def test_upsert_is_idempotent(db):
    sid = ensure_source(db, "hipo")
    assert upsert_institutions(db, FIX, sid, "http://x") == 3
    assert upsert_institutions(db, FIX, sid, "http://x") == 3
    assert db.execute("select count(*) from institution").fetchone()[0] == 3

def test_country_and_domain_mapping(db):
    sid = ensure_source(db, "hipo")
    upsert_institutions(db, FIX, sid, "http://x")
    row = db.execute("select country_code, name_en, domain, web_url from institution where domain='ntu.edu.tw'").fetchone()
    assert row == ("TW", "National Taiwan University", "ntu.edu.tw", "http://www.ntu.edu.tw/")

def test_job_fetches_each_supported_country(db, httpx_mock):
    httpx_mock.add_response(url=re.compile(r"http://universities\.hipolabs\.com/search\?country=Taiwan.*"), json=[r for r in FIX if r["alpha_two_code"]=="TW"])
    httpx_mock.add_response(url=re.compile(r"http://universities\.hipolabs\.com/search\?country=United.*"), json=[r for r in FIX if r["alpha_two_code"]=="US"])
    assert run_job(HipoJob(client=httpx.Client()), db).rows_written == 3
```

- [ ] **Step 3: 執行測試確認失敗**

Run: `cd pipeline && uv run pytest tests/test_hipo.py -v`
Expected: FAIL，模組不存在

- [ ] **Step 4: 實作 `countries.py`、`jobs/hipo.py`，並在 `REGISTRY` 登錄**

- [ ] **Step 5: 執行測試確認通過**

Run: `cd pipeline && uv run pytest tests/test_hipo.py -v`
Expected: 3 PASS

- [ ] **Step 6: 對本機資料庫實跑一次**

Run: `cd pipeline && DATABASE_URL=postgresql://localhost/collegedata_test uv run collegedata run hipo && psql collegedata_test -c "select country_code, count(*) from institution group by 1"`
Expected: TW 約 86 筆、US 約 2,349 筆（以實際回傳為準）

- [ ] **Step 7: Commit**

```bash
git add pipeline
git commit -m "feat(pipeline): hipo institutions job for TW and US"
```

### Task 5: 考分會 PDF 解析器

**Files:**
- Create: `pipeline/src/collegedata/parsers/__init__.py`、`pipeline/src/collegedata/parsers/uac.py`
- Create: `pipeline/tests/fixtures/uac_115_p1-2.pdf`
- Test: `pipeline/tests/test_uac_parser.py`

**Interfaces:**
- Produces:
  - `uac.UacRow`（dataclass）：`code: str`、`school_zh: str`、`program_zh: str`、`subjects: list[tuple[str, float]]`（如 `[("國",1.5),("英",1.25)]`，順序照 PDF）、`admitted_count: int`、`min_score: float | None`、`tiebreak: str | None`。
  - `uac.parse_uac_pdf(path: str | pathlib.Path) -> list[UacRow]`：用 `pdfplumber` 逐頁 `extract_tables()`，取第一欄為四位數字的列；表頭列與空列略過。`-----` 或空字串的分數為 `None`；`tiebreak` 空字串為 `None`。
  - `uac.row_from_cells(cells: list[str]) -> UacRow`：把 pdfplumber 的一列（12 格）轉成 `UacRow`；`parse_uac_pdf` 對每個資料列呼叫它。
  - `uac.parse_subjects(text: str) -> list[tuple[str, float]]`：解析 `國x1.50 英x1.25 數Bx1.00` 這類字串。已知科目代號：國、英、公、數甲、物、歷、化、生、地、數B、數乙、社、數A、自、術。遇到未知代號丟 `ValueError`。

- [ ] **Step 1: 建 fixture**

下載 `https://www2.uac.edu.tw/115data/115_result_school_data.pdf`，用 `pypdf` 取前 2 頁存成 `pipeline/tests/fixtures/uac_115_p1-2.pdf`。

- [ ] **Step 2: 寫測試**

`pipeline/tests/test_uac_parser.py`：
```python
import pathlib, pytest
from collegedata.parsers.uac import parse_uac_pdf, parse_subjects

FIX = pathlib.Path(__file__).with_name("fixtures") / "uac_115_p1-2.pdf"

def test_parse_subjects():
    assert parse_subjects("國x1.50 英x1.25 數Bx1.00") == [("國",1.5),("英",1.25),("數B",1.0)]

def test_parse_subjects_rejects_unknown():
    with pytest.raises(ValueError):
        parse_subjects("火x1.00")

def test_first_row():
    rows = parse_uac_pdf(FIX)
    r = rows[0]
    assert (r.code, r.school_zh, r.program_zh) == ("0001", "國立臺灣大學", "中國文學系")
    assert r.subjects == [("國",1.5),("英",1.25),("歷",1.25),("地",1.0)]
    assert (r.admitted_count, r.min_score, r.tiebreak) == (19, 265.5, "國 50")

def test_empty_tiebreak_is_none():
    r = next(x for x in parse_uac_pdf(FIX) if x.code == "0004")
    assert r.tiebreak is None and r.min_score == 205.0

def test_no_score_row_keeps_null_score_and_zero_admitted():
    from collegedata.parsers.uac import row_from_cells
    r = row_from_cells(['1227','中國文化大學','廣告學系B組','術x1.00 國x1.00 公x1.00','0','-----','','-----','-----','-----','-----','-----'])
    assert (r.min_score, r.admitted_count, r.tiebreak) == (None, 0, None)

def test_header_rows_skipped_and_pages_concatenated():
    rows = parse_uac_pdf(FIX)
    assert all(r.code.isdigit() for r in rows)
    assert any(r.code == "0040" for r in rows)   # 第 2 頁第一列
```

- [ ] **Step 3: 執行測試確認失敗**

Run: `cd pipeline && uv run pytest tests/test_uac_parser.py -v`
Expected: FAIL，模組不存在

- [ ] **Step 4: 實作 `parsers/uac.py`**

- [ ] **Step 5: 執行測試確認通過**

Run: `cd pipeline && uv run pytest tests/test_uac_parser.py -v`
Expected: 6 PASS

- [ ] **Step 6: 對完整 PDF 驗證（不進測試）**

Run: `cd pipeline && uv run python -c "from collegedata.parsers.uac import parse_uac_pdf; r=parse_uac_pdf('/path/to/115_result_school_data.pdf'); print(len(r), len({x.school_zh for x in r}), sum(1 for x in r if x.min_score is None))"`
Expected: `1764 60 14`

- [ ] **Step 7: Commit**

```bash
git add pipeline
git commit -m "feat(pipeline): parser for UAC distribution admission PDF"
```

### Task 6: 考分會 Job：校名對應與寫入

**Files:**
- Create: `pipeline/src/collegedata/jobs/uac.py`、`pipeline/config/tw_institutions.csv`、`pipeline/config/uac_years.yaml`
- Test: `pipeline/tests/test_uac_job.py`
- Modify: `pipeline/src/collegedata/runner.py`（登錄 `"uac"`）

**Interfaces:**
- Consumes: Task 4 的 `institution` 列（由 Hipo 建立，`name_zh` 為空）、Task 5 的 `parse_uac_pdf`。
- Produces:
  - `config/tw_institutions.csv`：欄位 `name_zh,name_en,domain`，涵蓋 115 學年 PDF 中的全部 60 所學校（校名字串需與 PDF 完全一致，如「國立臺灣大學」）；`domain` 是該校目前的主網域（如 `ntu.edu.tw`）。Hipo 清單過時且缺少數所學校（如康寧、佛光、馬偕、金門），因此不以 Hipo 為準。
  - `config/uac_years.yaml`：清單，每項 `roc_year`、`url`。初始三筆：115 → `https://www2.uac.edu.tw/115data/115_result_school_data.pdf`；114、113 的網址由建置者到 `https://www.uac.edu.tw/` 查「各系組最低錄取標準及錄取人數一覽表」填入。
  - `uac.UacJob(client=None, years: list[int] | None = None)`，`name = "uac"`。對每個年度：下載 PDF 到暫存、`parse_uac_pdf`、對每列：依 CSV 取得該校的 `name_en` 與 `domain`，以 `(country_code='TW', domain)` 查 `institution`；找不到就新增一筆（`name_en`、`name_zh` 來自 CSV，`web_url='https://www.<domain>/'`，`source_id`=uac，`source_url`=該年 PDF 網址）；找到就回填 `name_zh`；以 `(institution_id, name_zh=program_zh)` upsert `program`；以 `(program_id, year=roc_year+1911, pathway='tw_distribution')` upsert `admission_stat`（`subjects` 存為 `[{"subject":"國","weight":1.5},…]`）。回傳寫入的 `admission_stat` 筆數。
  - 任何校名在 CSV 找不到 → 丟 `UnknownSchoolError(missing: list[str])`，訊息列出全部缺少的校名。

- [ ] **Step 1: 建 `tw_institutions.csv`**

從 Task 5 Step 6 的完整 PDF 列出 60 個校名，填入英文校名與目前主網域。檢查：`uv run python -c` 讀 CSV 與 PDF，確認 PDF 的校名集合 ⊆ CSV 的校名集合，且 domain 無重複。

- [ ] **Step 2: 寫測試**

`pipeline/tests/test_uac_job.py`（用 Task 5 的兩頁 fixture；先用 `upsert_institutions` 塞入 fixture 中出現的 NTU）：
```python
import json, pathlib, pytest, httpx
from collegedata.jobs.hipo import upsert_institutions
from collegedata.jobs.uac import UacJob, UnknownSchoolError
from collegedata.sources import ensure_source
from collegedata.runner import run_job

FIXDIR = pathlib.Path(__file__).with_name("fixtures")
PDF = (FIXDIR / "uac_115_p1-2.pdf").read_bytes()
HIPO = json.loads((FIXDIR / "hipo_sample.json").read_text())

def _seed(db):
    upsert_institutions(db, HIPO, ensure_source(db, "hipo"), "http://x")

def test_writes_programs_and_stats(db, httpx_mock):
    _seed(db)
    httpx_mock.add_response(url="https://www2.uac.edu.tw/115data/115_result_school_data.pdf", content=PDF)
    r = run_job(UacJob(client=httpx.Client(), years=[115]), db)
    assert r.status == "success" and r.rows_written > 30
    row = db.execute("""select i.name_zh, p.name_zh, s.year, s.pathway, s.min_score, s.admitted_count, s.subjects, s.tiebreak
                        from admission_stat s join program p on p.id=s.program_id join institution i on i.id=p.institution_id
                        where p.name_zh='中國文學系'""").fetchone()
    assert row[:6] == ("國立臺灣大學", "中國文學系", 2026, "tw_distribution", 265.5, 19)
    assert row[6][0] == {"subject": "國", "weight": 1.5} and row[7] == "國 50"

def test_creates_institution_missing_from_hipo(db, httpx_mock):
    # 不先 _seed：institution 表為空，Job 須自行建立學校
    httpx_mock.add_response(url="https://www2.uac.edu.tw/115data/115_result_school_data.pdf", content=PDF)
    assert run_job(UacJob(client=httpx.Client(), years=[115]), db).status == "success"
    row = db.execute("select name_en, name_zh, country_code, web_url from institution where domain='ntu.edu.tw'").fetchone()
    assert row == ("National Taiwan University", "國立臺灣大學", "TW", "https://www.ntu.edu.tw/")

def test_rerun_is_idempotent(db, httpx_mock):
    _seed(db)
    httpx_mock.add_response(url="https://www2.uac.edu.tw/115data/115_result_school_data.pdf", content=PDF, is_reusable=True)
    n1 = run_job(UacJob(client=httpx.Client(), years=[115]), db).rows_written
    n2 = run_job(UacJob(client=httpx.Client(), years=[115]), db).rows_written
    assert n1 == n2 == db.execute("select count(*) from admission_stat").fetchone()[0]

def test_unknown_school_fails_loudly(db, httpx_mock, tmp_path, monkeypatch):
    _seed(db)
    monkeypatch.setattr("collegedata.jobs.uac.load_school_map", lambda: {})  # 空對應表
    httpx_mock.add_response(url="https://www2.uac.edu.tw/115data/115_result_school_data.pdf", content=PDF)
    r = run_job(UacJob(client=httpx.Client(), years=[115]), db)
    assert r.status == "failed" and "國立臺灣大學" in r.error
    assert db.execute("select count(*) from admission_stat").fetchone()[0] == 0
```

- [ ] **Step 3: 執行測試確認失敗**

Run: `cd pipeline && uv run pytest tests/test_uac_job.py -v`
Expected: FAIL，模組不存在

- [ ] **Step 4: 實作 `jobs/uac.py`（含 `load_school_map() -> dict[str, tuple[str, str]]`，key 為 `name_zh`、value 為 `(name_en, domain)`，讀 CSV）並登錄 `"uac"`**

- [ ] **Step 5: 執行測試確認通過**

Run: `cd pipeline && uv run pytest tests/test_uac_job.py -v`
Expected: 4 PASS

- [ ] **Step 6: 對本機資料庫實跑 115 年**

Run: `cd pipeline && DATABASE_URL=postgresql://localhost/collegedata_test uv run collegedata run uac && psql collegedata_test -c "select count(*) from admission_stat where year=2026"`
Expected: `1764`

- [ ] **Step 7: Commit**

```bash
git add pipeline
git commit -m "feat(pipeline): UAC job loads distribution admission stats into programs"
```

### Task 7: OpenAlex 強項

**Files:**
- Create: `pipeline/src/collegedata/jobs/openalex.py`
- Create: `pipeline/tests/fixtures/openalex_ntu.json`（`GET https://api.openalex.org/institutions?search=National%20Taiwan%20University&filter=country_code:TW,type:education&per-page=1&select=id,display_name,ror,works_count,cited_by_count,topics` 的真實回應，另存）
- Test: `pipeline/tests/test_openalex.py`
- Modify: `pipeline/src/collegedata/runner.py`（登錄 `"openalex"`）

**Interfaces:**
- Consumes: `institution`（需 `name_en`、`country_code`）。
- Produces:
  - `openalex.OpenAlexJob(client=None, api_key: str | None = None, limit: int | None = None)`，`name = "openalex"`。`api_key` 預設讀環境變數 `OPENALEX_API_KEY`，有值則加 `api_key=` 查詢參數。對每所 `openalex_id IS NULL` 或 `strength` 無資料的 institution：用 `search=<name_en>` 加 `filter=country_code:<cc>,type:education` 查詢，取第一筆；若 `works_count < 100` 則略過並記 warning。寫入 `institution.openalex_id`、`ror_id`，再把 `topics` 前 10 筆依 `count` 排序寫入 `strength`（`topic_id=topics[].id`、`topic_name=display_name`、`field_name=topics[].field.display_name`、`works_count=count`、`cited_by_count=0`（OpenAlex topics 不提供引用數，先存 0）、`rank` 從 1 起）。每次請求間隔 1 秒。回傳寫入的 `strength` 筆數。
  - 常數 `MIN_WORKS = 100`、`TOP_N = 10`。

- [ ] **Step 1: 建 fixture**

執行上述查詢（有金鑰就帶上），把回應 JSON 存成 `openalex_ntu.json`。確認裡面 `results[0].display_name == "National Taiwan University"` 且 `topics` 至少 10 筆。

- [ ] **Step 2: 寫測試**

`pipeline/tests/test_openalex.py`：
```python
import json, pathlib, re, httpx
from collegedata.jobs.hipo import upsert_institutions
from collegedata.jobs.openalex import OpenAlexJob
from collegedata.sources import ensure_source
from collegedata.runner import run_job

FIXDIR = pathlib.Path(__file__).with_name("fixtures")
NTU = json.loads((FIXDIR / "openalex_ntu.json").read_text())
HIPO = [r for r in json.loads((FIXDIR / "hipo_sample.json").read_text()) if r["domains"][0] == "ntu.edu.tw"]

def test_writes_top10_strengths_and_ids(db, httpx_mock):
    upsert_institutions(db, HIPO, ensure_source(db, "hipo"), "http://x")
    httpx_mock.add_response(url=re.compile(r"https://api\.openalex\.org/institutions\?.*"), json=NTU)
    r = run_job(OpenAlexJob(client=httpx.Client()), db)
    assert r.status == "success" and r.rows_written == 10
    assert db.execute("select openalex_id from institution").fetchone()[0] == NTU["results"][0]["id"]
    ranks = [x[0] for x in db.execute("select rank from strength order by rank").fetchall()]
    assert ranks == list(range(1, 11))

def test_skips_low_works_match(db, httpx_mock):
    upsert_institutions(db, HIPO, ensure_source(db, "hipo"), "http://x")
    low = json.loads(json.dumps(NTU)); low["results"][0]["works_count"] = 5
    httpx_mock.add_response(url=re.compile(r"https://api\.openalex\.org/institutions\?.*"), json=low)
    r = run_job(OpenAlexJob(client=httpx.Client()), db)
    assert r.status == "success" and r.rows_written == 0
    assert db.execute("select openalex_id from institution").fetchone()[0] is None

def test_query_includes_country_filter_and_key(db, httpx_mock):
    upsert_institutions(db, HIPO, ensure_source(db, "hipo"), "http://x")
    httpx_mock.add_response(url=re.compile(r"^(?=.*country_code(?::|%3A)TW)(?=.*api_key=k1).*$"), json=NTU)
    assert run_job(OpenAlexJob(client=httpx.Client(), api_key="k1"), db).status == "success"
```

- [ ] **Step 3: 執行測試確認失敗**

Run: `cd pipeline && uv run pytest tests/test_openalex.py -v`
Expected: FAIL，模組不存在

- [ ] **Step 4: 實作 `jobs/openalex.py` 並登錄 `"openalex"`**

- [ ] **Step 5: 執行測試確認通過**

Run: `cd pipeline && uv run pytest tests/test_openalex.py -v`
Expected: 3 PASS

- [ ] **Step 6: 對本機資料庫實跑（限 5 所）**

Run: `cd pipeline && DATABASE_URL=postgresql://localhost/collegedata_test uv run python -c "from collegedata.jobs.openalex import OpenAlexJob; from collegedata.runner import run_job; from collegedata.db import connect; print(run_job(OpenAlexJob(limit=5), connect()))"`
Expected: `status='success'`，`rows_written` 在 0 到 50 之間

- [ ] **Step 7: Commit**

```bash
git add pipeline
git commit -m "feat(pipeline): OpenAlex job links institutions and stores top research topics"
```

### Task 8: GitHub Actions 排程、失敗通知、Supabase 部署說明

**Files:**
- Create: `.github/workflows/pipeline.yml`、`.github/workflows/test.yml`、`docs/deploy.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: CLI `collegedata run <job>`（Task 3）、環境變數 `DATABASE_URL`、`OPENALEX_API_KEY`。
- Produces: 兩個 workflow。

- [ ] **Step 1: 寫 `test.yml`**

觸發：`push`、`pull_request`。步驟：`actions/checkout`、`actions/setup-python` 3.12、安裝 uv、啟動 `services: postgres:17`（`POSTGRES_DB=collegedata_test`、`POSTGRES_HOST_AUTH_METHOD=trust`）、`cd pipeline && uv sync && TEST_DATABASE_URL=postgresql://postgres@localhost/collegedata_test uv run pytest -v`。

- [ ] **Step 2: 寫 `pipeline.yml`**

觸發：`schedule`（三條 cron，全部每週：`0 3 * * 1` 跑 `hipo`、`0 4 * * 2` 跑 `openalex`、`0 5 * * 3` 跑 `uac`（2026-10-29 依使用者要求改為每週））與 `workflow_dispatch`（輸入 `job`，可選 `hipo`/`uac`/`openalex`）。用 `strategy.matrix` 或依 `github.event.schedule` 決定 job 名稱。步驟：checkout、setup-python、uv sync、`uv run collegedata run ${JOB}`，環境變數從 secrets `DATABASE_URL`、`OPENALEX_API_KEY` 取。最後一步 `if: failure()` 用 `actions/github-script` 建立 Issue：標題 `[pipeline] <job> failed on <date>`，內文含 workflow run 連結，`assignees: [context.repo.owner]`（GitHub 會寄 email 給被指派者，即儲存庫擁有者 cyw0517terry@gmail.com）。

- [ ] **Step 3: 寫 `docs/deploy.md`**

手動步驟（由使用者做一次）：在 supabase.com 建免費專案；在專案 Settings → Database 取連線字串（Session pooler 模式）；本機 `supabase link --project-ref <ref>` 後 `supabase db push` 套用 migration；到 GitHub 儲存庫 Settings → Secrets 加 `DATABASE_URL`、`OPENALEX_API_KEY`（到 `https://openalex.org/settings/api` 申請）；到 Actions 頁手動 `workflow_dispatch` 跑一次 `hipo` → `uac` → `openalex` 做初始載入。

- [ ] **Step 4: 驗證 workflow 語法**

Run: `gh workflow list` 需在推到 GitHub 後才有意義；本機先用 `uv run python -c "import yaml,sys; [yaml.safe_load(open(f)) for f in ['.github/workflows/test.yml','.github/workflows/pipeline.yml']]; print('ok')"`
Expected: `ok`

- [ ] **Step 5: 更新 README 並 Commit**

README 寫：專案宗旨一段、目錄結構（`supabase/`、`pipeline/`、`docs/`）、本機開發三行（`scripts/setup-local-db.sh`、`cd pipeline && uv sync`、`uv run pytest`）、連結到 `docs/deploy.md` 與 `設計文件.md`。

```bash
git add .github docs/deploy.md README.md
git commit -m "ci: scheduled pipeline workflow with failure issues, test workflow, deploy guide"
```

- [ ] **Step 6: 建立公開 GitHub 儲存庫並推上去**

Run: `gh repo create college-requirement --public --source=. --push`
Expected: 儲存庫建立，`test.yml` 在 Actions 自動跑並通過。

---

## 本計畫完成後的狀態

- 本機與 CI 都能跑完整測試。
- 資料庫有台灣與美國的學校主檔、台灣 115 學年（及 CSV 填好後的 114、113）分發入學各系組錄取標準、各校 OpenAlex 強項。
- GitHub Actions 依排程自動更新，失敗自動開 Issue 並寄信。

## 尚未納入、留給後續計畫

- 甄選會（個人申請）資料：該站 TLS 憑證鏈有問題，格式待確認後另立計畫 1b。
- College Scorecard（計畫 2）、網站（計畫 3）、帳號與案例（計畫 4）。

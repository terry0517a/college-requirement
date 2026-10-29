# 計畫 1b：甄選會（個人申請）資料管線 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 每週自動從甄選會（cac.edu.tw）抓最近三個學年的「各校系篩選標準一覽表」圖片並以 OCR 入庫，以及最新學年的「校系分則」網頁，寫入 `program`、`admission_requirement`、`admission_stat`，每筆附來源。

**Architecture:** 沿用「一個來源一個 Job」結構，新增兩個 Job：`cac_sieve`（圖片 → 逐格 OCR → 列）與 `cac_rules`（HTML → 第二階段比重）。兩者共用 `cac_http.py`（TWCA 中繼憑證、固定 User-Agent、3 秒節流、Range 續傳、「流量過大」停止）與 `cac_fetch` 進度表（一校一學年一單位，做過不重做，每次執行有額度）。解析器是純函式（`parsers/cac_sieve.py`、`parsers/cac_rules.py`），Job 只做抓取與寫入。

**Tech Stack:** 同計畫 1／2：PostgreSQL 17、Python 3.12 + uv、psycopg 3、httpx、pytest + pytest-httpx。新增 `rapidocr-onnxruntime`（OCR，CPU）、`numpy`、`pillow`。

**Spec:** `docs/superpowers/specs/2026-10-29-cac-apply-design.md`（本計畫依據；第 3 節是實測事實，第 4 節是硬性規定）。總規格 `設計文件.md` 5.1.3、5.1.5、6.2、6.4。

**分支：** `plan-1b-cac`（已自 `plan-2-us-scorecard` a38c2aa 開出，worktree 在 `.claude/worktrees/plan-1b-cac`）。測試資料庫用 `TEST_DATABASE_URL=postgresql://localhost/collegedata_1b_test`（與計畫 2 的對話分開）。

## Global Constraints

- 每一筆資料都必須有 `source_id`、`source_url`、`fetched_at`；`source_url` 是可重現的來源網址（圖片網址或校系分則頁網址）。
- 對 cac.edu.tw：User-Agent 固定 `collegedata-pipeline/0.1 (+https://github.com/terry0517a/college-requirement; cyw0517terry@gmail.com)`；兩個請求間隔 ≥ 3 秒；**禁止** `verify=False`；收到 HTTP 429／503 或內容含「流量過大」即停止發新請求。
- 抓過且成功的 (job, 學年, 校碼) 永不重抓（`cac_fetch.status = 'done'`）。
- 每次執行額度：環境變數 `CAC_MAX_SCHOOLS`（預設 10）、`CAC_TIME_BUDGET_MINUTES`（預設 75）。
- 兩個 Job `row_count_guard = False`；「嘗試 ≥ 1 所且成功 0 所」→ 拋例外讓 job 失敗。
- 程式名稱正規化：NFKC → 去除所有空白 → 全形括號 `（）` 改半形 `()`；性別要求「男」「女」時名稱加 `(男)`／`(女)` 後綴。`program` 以 `(institution_id, name_zh)` upsert，與考分會相同的 SQL（保留既有 `name_en`）。
- 不新增 BeautifulSoup；HTML 用標準庫 `html.parser` 或正規表達式。
- 既有 69 個測試不得退步；每個 Task 結束時 `uv run pytest -q` 全綠。
- Commit 訊息結尾加 `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`。

## Review Focus

1. 圖片裡同一校系代碼出現兩列（男／女）：兩列都要入庫為兩個 program（`戲劇學系(男)`、`戲劇學系(女)`），名額與最低級分各自正確（Task 4 黃金測試、Task 5 寫入測試）。
2. 最低級分格折成兩行（`(英文+數學\nA+自然)41`）：要串接成一個值，科目清單含三科（Task 3 單元測試、Task 4 黃金測試）。
3. 節流中途（已完成 3 所、第 4 所回「流量過大」）：前 3 所寫入並 `done`，job 成功結束、不重試、不開 Issue（Task 5 測試）。
4. 校系分則 job 在 11 月 1 日前後、query.php 尚無系統連結：11–12 月只警告，1 月以後失敗（Task 7 測試）。
5. 兩個 job 先後寫同一個 `admission_requirement` 列：後寫者不能清掉先寫者的鍵，`sources` 的兩個鍵都要在（Task 5 與 Task 7 測試）。

---

### Task 1: cac.edu.tw HTTP 層（憑證、節流、續傳、忙碌偵測）

**Files:**
- Create: `pipeline/config/certs/twca_ssl_sub_ca.pem`（由 `http://sslserver.twca.com.tw/cacert/Cyber_SSL_2023.crt` 轉 PEM；`openssl x509 -inform DER -in Cyber_SSL_2023.crt -out twca_ssl_sub_ca.pem`；檔頭加註解寫來源網址與有效期 2033-02-23）
- Create: `pipeline/src/collegedata/cac_http.py`
- Test: `pipeline/tests/test_cac_http.py`

**Interfaces:**
- Produces:
  - `USER_AGENT: str`（Global Constraints 的字串）
  - `make_ssl_context() -> ssl.SSLContext`：`ssl.create_default_context(cafile=certifi.where())` 再 `load_verify_locations(CERT_PATH)`。
  - `make_client(timeout: float = 120) -> httpx.Client`：`verify=make_ssl_context()`、`headers={"User-Agent": USER_AGENT}`、`follow_redirects=True`。
  - `class BusyError(Exception)`
  - `class CacFetcher:`
    - `__init__(self, client: httpx.Client, min_interval: float = 3.0, sleep=time.sleep, clock=time.monotonic)`
    - `get(self, url: str) -> httpx.Response`、`post(self, url: str, data: dict) -> httpx.Response`：發請求前確保距上次請求 ≥ `min_interval`（用 `clock` 與 `sleep`）；回應 `status_code in (429, 503)` 或 `"流量過大" in response.text` → 拋 `BusyError(url)`；其他 4xx／5xx 不在此處理（呼叫端決定）。
    - `download(self, url: str, max_attempts: int = 6) -> bytes`：用 `client.stream("GET", url, headers={"Range": f"bytes={len(buf)}-"})` 逐塊讀入 `buf`；遇 `httpx.TransportError`（含 ReadTimeout）保留 `buf` 重試（同樣受節流）；回 200 時 `buf` 重置為該回應全文；回 206 時續接；回 416 且 `buf` 非空視為完成；超過 `max_attempts` 拋最後的例外；完成條件：回應結束且（無 `Content-Range`／`Content-Length` 或長度吻合）。
    - `download` 的回應若 `status_code in (429, 503)`，或回應小於 64 KB 且內容含「流量過大」，同樣拋 `BusyError`。
    - `requests_made: int` 計數器。

- [ ] **Step 1: 寫失敗的測試**

```python
# tests/test_cac_http.py
import httpx, pytest
from collegedata.cac_http import CacFetcher, BusyError, make_ssl_context, USER_AGENT

class Clock:
    def __init__(self): self.t = 0.0; self.slept = []
    def now(self): return self.t
    def sleep(self, s): self.slept.append(s); self.t += s

def _fetcher(clock, **kw):
    return CacFetcher(httpx.Client(headers={"User-Agent": USER_AGENT}), min_interval=3.0, sleep=clock.sleep, clock=clock.now, **kw)

def test_ssl_context_includes_twca_intermediate():
    ctx = make_ssl_context()
    subjects = [tuple(x[0] for x in c["subject"]) for c in ctx.get_ca_certs()]
    assert any(("commonName", "TWCA SSL Certification Authority") in s for s in subjects)

def test_get_spaces_requests_by_three_seconds(httpx_mock):
    httpx_mock.add_response(url="https://www.cac.edu.tw/a", text="a")
    httpx_mock.add_response(url="https://www.cac.edu.tw/b", text="b")
    clock = Clock(); f = _fetcher(clock)
    f.get("https://www.cac.edu.tw/a"); f.get("https://www.cac.edu.tw/b")
    assert sum(clock.slept) >= 3.0 and f.requests_made == 2
    assert httpx_mock.get_requests()[0].headers["User-Agent"] == USER_AGENT

def test_busy_page_raises(httpx_mock):
    httpx_mock.add_response(url="https://www.cac.edu.tw/x", text="<html>流量過大，請稍後再試。</html>")
    with pytest.raises(BusyError):
        _fetcher(Clock()).get("https://www.cac.edu.tw/x")

def test_503_raises_busy(httpx_mock):
    httpx_mock.add_response(url="https://www.cac.edu.tw/x", status_code=503)
    with pytest.raises(BusyError):
        _fetcher(Clock()).get("https://www.cac.edu.tw/x")

def test_download_resumes_after_timeout(httpx_mock):
    url = "https://www.cac.edu.tw/p.png"
    httpx_mock.add_response(url=url, status_code=200, content=b"ABCDEFGHIJ", headers={"Content-Length": "10"})
    f = _fetcher(Clock())
    assert f.download(url) == b"ABCDEFGHIJ"

def test_download_retries_transport_error_with_range(httpx_mock):
    url = "https://www.cac.edu.tw/p.png"
    httpx_mock.add_exception(httpx.ReadTimeout("slow"), url=url)
    httpx_mock.add_response(url=url, status_code=206, content=b"ABCDEFGHIJ",
                            headers={"Content-Range": "bytes 0-9/10"}, match_headers={"Range": "bytes=0-"})
    assert _fetcher(Clock()).download(url) == b"ABCDEFGHIJ"

def test_download_gives_up_after_max_attempts(httpx_mock):
    url = "https://www.cac.edu.tw/p.png"
    for _ in range(2):
        httpx_mock.add_exception(httpx.ReadTimeout("slow"), url=url)
    with pytest.raises(httpx.ReadTimeout):
        _fetcher(Clock()).download(url, max_attempts=2)
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `cd pipeline && TEST_DATABASE_URL=postgresql://localhost/collegedata_1b_test uv run pytest tests/test_cac_http.py -q`
Expected: FAIL（`ModuleNotFoundError: collegedata.cac_http`）

- [ ] **Step 3: 放入憑證檔並實作 `cac_http.py`**

憑證：下載 `http://sslserver.twca.com.tw/cacert/Cyber_SSL_2023.crt`（DER），轉 PEM 存 `pipeline/config/certs/twca_ssl_sub_ca.pem`；用 `openssl x509 -in … -noout -subject -enddate` 確認 subject 為 `CN=TWCA SSL Certification Authority`。`certifi` 已是 httpx 的相依，直接 `import certifi`。

- [ ] **Step 4: 跑測試確認通過**

Run: 同 Step 2
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add pipeline/config/certs pipeline/src/collegedata/cac_http.py pipeline/tests/test_cac_http.py
git commit -m "feat(cac): http layer with TWCA intermediate cert, 3 s throttle, range resume, busy detection"
```

---

### Task 2: Migration 0005、來源與校名表

**Files:**
- Create: `supabase/migrations/0005_cac.sql`
- Modify: `pipeline/config/sources.yaml`（加 `cac`）
- Modify: `pipeline/config/tw_institutions.csv`（加 5 列）
- Modify: `pipeline/tests/test_schema.py`
- Test: `pipeline/tests/test_schema.py`、`pipeline/tests/test_uac_job.py`（既有）

**Interfaces:**
- Produces：`admission_stat.sieve jsonb`；表 `cac_fetch(id, job, roc_year, school_code char(3), url, status in ('done','failed'), rows_written int, rows_skipped int, error text, fetched_at timestamptz not null, unique (job, roc_year, school_code))`，啟用 RLS、**不**建 anon 讀取政策；`source` 代碼 `cac`（name `大學甄選入學委員會`、url `https://www.cac.edu.tw/`、license `公開資料（政府資訊）；網站 robots.txt 全站 Disallow，經使用者決定以節制方式抓取`）。

- [ ] **Step 1: 寫失敗的測試**

```python
# 加到 tests/test_schema.py
def test_admission_stat_has_sieve_column(db):
    cols = {r[0] for r in db.execute("select column_name from information_schema.columns where table_name='admission_stat'")}
    assert "sieve" in cols

def test_cac_fetch_table_and_unique(db):
    db.execute("insert into cac_fetch (job, roc_year, school_code, url, status, fetched_at) values ('cac_sieve', 115, '001', 'u', 'done', now())")
    import psycopg, pytest
    with pytest.raises(psycopg.errors.UniqueViolation):
        with db.transaction():
            db.execute("insert into cac_fetch (job, roc_year, school_code, url, status, fetched_at) values ('cac_sieve', 115, '001', 'u2', 'failed', now())")

def test_cac_fetch_has_no_anon_policy(db):
    n = db.execute("select count(*) from pg_policies where tablename = 'cac_fetch'").fetchone()[0]
    assert n == 0

def test_cac_source_entry_loads(db):
    from collegedata.sources import ensure_source
    assert ensure_source(db, "cac") > 0
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `uv run pytest tests/test_schema.py -q`（pipeline 目錄，環境變數同 Task 1）
Expected: 4 failed

- [ ] **Step 3: 寫 migration、sources.yaml、CSV**

CSV 新增列（`name_zh,name_en,domain`）：`國立臺北藝術大學,Taipei National University of the Arts,tnua.edu.tw`、`華梵大學,Huafan University,hfu.edu.tw`、`開南大學,Kainan University,knu.edu.tw`、`中信金融管理學院,CTBC Business School,ctbc.edu.tw`、`臺北基督學院,Christ's College Taipei,cct.edu.tw`。

- [ ] **Step 4: 跑全部測試確認通過**

Run: `uv run pytest -q`
Expected: 73 passed（69 + 4）

- [ ] **Step 5: Commit**

```bash
git add supabase/migrations/0005_cac.sql pipeline/config/sources.yaml pipeline/config/tw_institutions.csv pipeline/tests/test_schema.py
git commit -m "feat(db): admission_stat.sieve, cac_fetch progress table, cac source, five more TW schools"
```

---

### Task 3: 篩選標準圖片解析（一）：格線、表分段、值正規化（不含 OCR）

**Files:**
- Create: `pipeline/src/collegedata/parsers/cac_sieve.py`
- Modify: `pipeline/pyproject.toml`（dependencies 加 `numpy>=2`、`pillow>=10`、`rapidocr-onnxruntime>=1.4`；`uv sync` 更新 `uv.lock`）
- Test: `pipeline/tests/test_cac_sieve_grid.py`

**Interfaces:**
- Produces（全部純函式，`np.ndarray` 為 uint8 灰階二維陣列）：
  - `to_gray(png: bytes) -> np.ndarray`
  - `detect_hlines(gray) -> list[int]`：橫線 y 座標（相鄰 ≤ 2 px 的合併取中點）。判定：該列「連續深色（< 160）像素最長長度」> 圖寬 × 0.3。
  - `grid_rows(gray, hlines) -> list[tuple[int, int, bool]]`：相鄰橫線對 `(y0, y1, is_grid)`；`is_grid` 為「至少 3 個 x 位置在 y0..y1 之間 ≥ 90% 深色」。
  - `split_tables(rows) -> list[Table]`，`@dataclass Table: y0: int; y1: int; above: tuple[int,int] | None`（`above` 是表上方最近的非格線列，用來 OCR 群組標記）。連續的 `is_grid` 列為一張表。
  - `detect_vlines(gray, y0, y1) -> list[int]`：只看 y0..y1，判定「最長連續深色長度」> (y1−y0) × 0.6。
  - `cell_lines(gray, y0, y1, x0, x1) -> list[np.ndarray]`：格內縮 2 px，依墨水（< 110）投影切行（相鄰 ≤ 3 px 合併，高度 < 6 px 丟棄），每行左右裁到墨水範圍外 6 px；無墨水（深色像素 < 4）回 `[]`。
  - 正規化：`normalize_text(s) -> str`（簡→繁對照至少含 数國国测測筛篩顺順标標级級额額顶頂会會听聽学學组組系系；全形括號→半形；去空白）；`parse_level(s) -> str | None`（`頂標`…；`--`／`—`／空→None；第一字 ∈ 頂前均後底 → 補「標」）；`parse_listening(s) -> str | None`（A／B／C）；`parse_multiplier(s) -> Decimal | None`；`parse_quota(s) -> int`；`parse_sieve_cell(s) -> SieveLevel | None`，`@dataclass SieveLevel: order: int; label: str; subjects: list[str]; min_score: Decimal`（order 由呼叫端填）；`expand_subjects(s) -> list[str]`：`+` 分隔全名直接用；否則依縮寫序列掃描：`國`→國文、`英聽`→英聽、`英`→英文、`數A`／`數學A`→數學A、`數B`／`數學B`→數學B、`社`→社會、`自`→自然；無法完整解析回 `[]`。
  - `normalize_program_name(name: str, gender: str | None) -> str`（Global Constraints 規則）。

- [ ] **Step 1: 寫失敗的測試**

```python
# tests/test_cac_sieve_grid.py
import pathlib
from decimal import Decimal
from collegedata.parsers.cac_sieve import (to_gray, detect_hlines, grid_rows, split_tables, detect_vlines, cell_lines,
    normalize_text, parse_level, parse_multiplier, parse_sieve_cell, expand_subjects, normalize_program_name, parse_quota)

FIX = pathlib.Path(__file__).with_name("fixtures") / "cac"
CROP = (FIX / "115_001_crop.png").read_bytes()

def test_grid_of_crop_has_one_table_with_25_columns():
    g = to_gray(CROP)
    hl = detect_hlines(g)
    tables = split_tables(grid_rows(g, hl))
    assert len(tables) == 1
    t = tables[0]
    assert t.above is not None                       # 【一般校系】列
    assert len(detect_vlines(g, t.y0, t.y1)) == 26  # 25 欄

def test_cell_lines_splits_two_line_cell():
    g = to_gray(CROP); hl = detect_hlines(g); t = split_tables(grid_rows(g, hl))[0]
    vl = detect_vlines(g, t.y0, t.y1)
    rows = [r for r in grid_rows(g, hl) if r[2] and r[0] >= t.y0]
    # 心理學系 001132 是第 14 列資料（表頭 3 列之後），篩選順序一為兩行
    y0, y1, _ = rows[3 + 13]
    assert len(cell_lines(g, y0, y1, vl[18], vl[19])) == 2
    assert cell_lines(g, y0, y1, vl[4], vl[5]) == [] or len(cell_lines(g, y0, y1, vl[4], vl[5])) == 1

def test_normalize_text_maps_simplified_and_parens():
    assert normalize_text("国英数A自 46（数学A）") == "國英數A自46(數學A)"

def test_parse_level_and_multiplier():
    assert parse_level("均標") == "均標" and parse_level("均") == "均標" and parse_level("顶標") == "頂標"
    assert parse_level("--") is None and parse_level("—") is None and parse_level("") is None
    assert parse_multiplier("2.5") == Decimal("2.5") and parse_multiplier("--") is None

def test_parse_sieve_cell_three_forms():
    a = parse_sieve_cell("英文13"); b = parse_sieve_cell("(英文+數學A+自然)41"); c = parse_sieve_cell("國英數A自37")
    assert (a.subjects, a.min_score) == (["英文"], Decimal("13"))
    assert (b.subjects, b.min_score) == (["英文", "數學A", "自然"], Decimal("41"))
    assert (c.subjects, c.min_score) == (["國文", "英文", "數學A", "自然"], Decimal("37"))
    assert parse_sieve_cell("--") is None and parse_sieve_cell("") is None
    assert parse_sieve_cell("APCS實作4").label == "APCS實作4" and parse_sieve_cell("APCS實作4").subjects == []

def test_expand_subjects_abbreviations():
    assert expand_subjects("國英數B社") == ["國文", "英文", "數學B", "社會"]
    assert expand_subjects("英聽") == ["英聽"]
    assert expand_subjects("奇怪") == []

def test_normalize_program_name():
    assert normalize_program_name("醫學系（公費生）", None) == "醫學系(公費生)"
    assert normalize_program_name("戲劇學系", "男") == "戲劇學系(男)"
    assert normalize_program_name(" 資訊工程學系 (APCS組)", "無") == "資訊工程學系(APCS組)"
    assert parse_quota(" 57 ") == 57
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `uv run pytest tests/test_cac_sieve_grid.py -q`
Expected: FAIL（import error）

- [ ] **Step 3: 加依賴並實作**

`uv add numpy pillow rapidocr-onnxruntime`（會更新 pyproject 與 uv.lock）。實作上述函式。格線偵測演算法見 Interfaces（「最長連續深色長度」，不可用深色比例）。`cell_lines` 的 y 索引是圖片絕對座標。

- [ ] **Step 4: 跑測試確認通過**

Run: `uv run pytest tests/test_cac_sieve_grid.py -q`
Expected: 7 passed（若 `test_cell_lines_splits_two_line_cell` 的列索引不對，先用 `cell_lines` 印出第 0 欄文字行數確認心理學系的列，調整索引，不要放寬斷言）

- [ ] **Step 5: Commit**

```bash
git add pipeline/pyproject.toml pipeline/uv.lock pipeline/src/collegedata/parsers/cac_sieve.py pipeline/tests/test_cac_sieve_grid.py
git commit -m "feat(cac): sieve image grid detection, table splitting and value normalisation"
```

---

### Task 4: 篩選標準圖片解析（二）：OCR、表頭對應、列解析

**Files:**
- Modify: `pipeline/src/collegedata/parsers/cac_sieve.py`
- Test: `pipeline/tests/test_cac_sieve_ocr.py`

**Interfaces:**
- Produces：
  - `class OcrEngine(Protocol): def recognize(self, line: np.ndarray) -> str`
  - `class RapidOcrEngine(OcrEngine)`：延遲 `from rapidocr_onnxruntime import RapidOCR`；`recognize` 把行影像等比放大到高 40 px（只放大不縮小），呼叫 `engine(img, use_det=False, use_cls=False)`，回第一個結果的文字（無結果回 `""`）。
  - `KNOWN_HEADERS: dict[str, str]`：表頭文字（正規化後）→ 欄鍵：`校系代碼`→`code`、`性別要求`→`gender`、`校系名稱`→`name`、`招生名額`→`quota`、`國文`／`英文`／`數學A`／`數學B`／`社會`／`自然`／`英聽`→同名、`學測科目組合`→`學測科目組合`、`篩選順序一`…`六`→`sieve1`…`sieve6`、`同級分超額篩選`→`overflow`。表頭列可能有兩到三列：每欄取該欄所有表頭列文字串接後比對（含「包含」比對，如 `數學A` 含於 `數學A`、`學測科目組合` 含於 `學測科\n目組合`）；科目第一次出現歸 `thresholds`，第二次歸 `multipliers`。
  - `map_headers(header_texts: list[str]) -> dict[int, tuple[str, str]] | None`：欄索引 →（區塊 `base|thresholds|multipliers|sieve|extra`，鍵）；缺 `code`／`name`／`quota` 任一回 `None`。
  - `@dataclass SieveRow: school_code: str; cac_code: str; gender: str | None; name: str; quota: int; group: str; thresholds: dict[str, str | None]; multipliers: dict[str, Decimal | None]; extra: dict[str, str]; sieve: list[SieveLevel]; overflow_tiebreak: bool; raw_cells: list[str]`
  - `@dataclass SieveParseResult: rows: list[SieveRow]; rows_skipped: int; warnings: list[str]; groups: list[str]`
  - `parse_sieve_image(png: bytes, school_code: str, ocr: OcrEngine | None = None) -> SieveParseResult`：流程 = Task 3 的函式 → 每張表：OCR `above` 列得群組名（去掉 `【】`；無則 `"一般校系"`）→ 表頭列 = 表最前面、第 0 欄不是 6 碼數字的連續列（最多 3 列）→ `map_headers` → 資料列逐格 OCR（`cell_lines` 每行 `recognize`，串接，`normalize_text`）→ 驗證（代碼 6 碼數字且前 3 碼 = `school_code`；名稱非空；名額整數；檢定值 ∈ 頂標前標均標後標底標／None、英聽 ∈ A B C／None；倍率可轉 Decimal／None）→ 不合格列 `rows_skipped += 1` 並 `warnings.append(f"skip row: {raw_cells}")`。`gender` 為 `無`→None。`sieve` 依 `sieve1..6` 順序，空格略過，`order` 從 1 連號。`overflow_tiebreak = raw == "*"`。

- [ ] **Step 1: 寫失敗的黃金測試（期望值已由人工核對圖片）**

```python
# tests/test_cac_sieve_ocr.py
import pathlib
from decimal import Decimal
import pytest
from collegedata.parsers.cac_sieve import parse_sieve_image, map_headers

FIX = pathlib.Path(__file__).with_name("fixtures") / "cac"

@pytest.fixture(scope="module")
def crop():
    return parse_sieve_image((FIX / "115_001_crop.png").read_bytes(), "001")

def test_crop_rows_and_groups(crop):
    assert crop.rows_skipped == 0 and crop.groups == ["一般校系"]
    assert [r.cac_code for r in crop.rows][:4] == ["001012", "001022", "001032", "001042"]
    assert len(crop.rows) >= 10

def test_chinese_literature_row(crop):
    r = next(r for r in crop.rows if r.cac_code == "001012")
    assert (r.name, r.quota, r.gender, r.group) == ("中國文學系", 23, None, "一般校系")
    assert r.thresholds == {"國文": "前標", "英文": "均標", "數學A": "均標", "數學B": "均標", "社會": "均標", "自然": None, "英聽": None}
    assert r.multipliers == {"國文": Decimal("3"), "英文": Decimal("6"), "數學A": None, "數學B": None, "社會": Decimal("8"), "自然": None, "學測科目組合": None}
    assert [(s.order, s.label, s.min_score) for s in r.sieve] == [(1, "社會10", Decimal("10")), (2, "英文10", Decimal("10")), (3, "國文15", Decimal("15"))]
    assert r.overflow_tiebreak is True

def test_gender_split_rows(crop):
    rows = [r for r in crop.rows if r.cac_code == "001082"]
    assert [(r.gender, r.name, r.quota) for r in rows] == [("男", "戲劇學系(男)", 8), ("女", "戲劇學系(女)", 9)]
    assert rows[0].sieve[2].label == "國英數B社43" and rows[1].sieve[2].label == "國英數B社45"
    assert rows[0].sieve[2].subjects == ["國文", "英文", "數學B", "社會"]

def test_listening_and_two_line_sieve(crop):
    foreign = next(r for r in crop.rows if r.cac_code == "001022")
    assert foreign.thresholds["英聽"] == "A" and foreign.multipliers["英文"] == Decimal("2.5")
    psych = next(r for r in crop.rows if r.cac_code == "001132")
    assert psych.sieve[0].subjects == ["英文", "數學A", "自然"] and psych.sieve[0].min_score == Decimal("41")
    assert psych.multipliers["英文"] == Decimal("2.5") and psych.multipliers["數學A"] == Decimal("2.5")

def test_apcs_table_base_fields():
    res = parse_sieve_image((FIX / "115_001_apcs_crop.png").read_bytes(), "001")
    r = next(r for r in res.rows if r.cac_code == "001592")
    assert (r.name, r.quota) == ("資訊工程學系(APCS組)", 4)
    assert "APCS" in r.group

def test_map_headers_requires_base_columns():
    assert map_headers(["校系代碼", "性別要求", "校系名稱"]) is None
    m = map_headers(["校系代碼", "性別要求", "校系名稱", "招生名額", "國文", "英文", "國文", "英文", "篩選順序一", "同級分超額篩選"])
    assert m[4] == ("thresholds", "國文") and m[6] == ("multipliers", "國文") and m[8] == ("sieve", "sieve1") and m[9] == ("base", "overflow")
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `uv run pytest tests/test_cac_sieve_ocr.py -q`
Expected: FAIL（import error）

- [ ] **Step 3: 實作 OCR 包裝、表頭對應與 `parse_sieve_image`**

OCR 的範例呼叫（本機已驗證）：`RapidOCR()(np_img, use_det=False, use_cls=False)` 回 `(result, elapse)`，`result[0]` 為 `[text, score]`（部分版本為 `[box, text, score]`，取長度判斷）。首次載入模型約 1–2 秒。

- [ ] **Step 4: 跑測試確認通過**

Run: `uv run pytest tests/test_cac_sieve_ocr.py -q`
Expected: 6 passed（總時間 < 60 秒）。若某個值辨識錯，先改前處理（放大倍率、裁切邊距、正規化對照），不得改期望值；三次調整仍錯才在 ledger 記錄並把該斷言縮小到仍然正確的部分。

- [ ] **Step 5: Commit**

```bash
git add pipeline/src/collegedata/parsers/cac_sieve.py pipeline/tests/test_cac_sieve_ocr.py
git commit -m "feat(cac): per-cell OCR, header mapping and row parsing for sieve images"
```

---

### Task 5: `cac_sieve` Job（學年、進度、額度、寫入）

**Files:**
- Create: `pipeline/src/collegedata/jobs/cac_sieve.py`
- Create: `pipeline/src/collegedata/jobs/cac_common.py`
- Modify: `pipeline/src/collegedata/runner.py:_register_jobs`（登記 `cac_sieve`）
- Test: `pipeline/tests/test_cac_sieve_job.py`

**Interfaces:**
- Consumes：Task 1 `CacFetcher`、`BusyError`、`make_client`；Task 3／4 `parse_sieve_image`、`SieveRow`；`uac._institution_id`、`uac.load_school_map`、`uac.UnknownSchoolError`（直接 import 重用）。
- Produces（`cac_common.py`）：
  - `BASE = "https://www.cac.edu.tw"`
  - `@dataclass Budget: max_schools: int; time_budget: timedelta; started: float`，`Budget.from_env(clock) -> Budget`（`CAC_MAX_SCHOOLS` 預設 10、`CAC_TIME_BUDGET_MINUTES` 預設 75），`exhausted(done_count, clock) -> bool`。
  - `done_units(conn, job, roc_year) -> set[str]`（`cac_fetch` 中 status='done' 的校碼）。
  - `record_unit(conn, job, roc_year, school_code, url, status, rows_written, rows_skipped, error)`：upsert `cac_fetch`（on conflict 更新 status 等）。
  - `upsert_program(conn, inst_id, name_zh, source_id, source_url) -> int`（與 uac.py 同 SQL；搬過來讓兩邊共用，uac.py 改為呼叫它）。
  - `merge_requirement(conn, program_id, year, requirement: dict, source_id, source_url)`：SQL

    ```sql
    insert into admission_requirement (program_id, year, pathway, system_code, requirement, source_id, source_url, fetched_at)
    values (%s, %s, 'tw_apply', 'tw_gsat', %s, %s, %s, now())
    on conflict (program_id, year, pathway) do update set
      requirement = (admission_requirement.requirement || excluded.requirement)
                    || jsonb_build_object('sources',
                         coalesce(admission_requirement.requirement->'sources', '{}'::jsonb)
                         || coalesce(excluded.requirement->'sources', '{}'::jsonb)),
      source_id = excluded.source_id, source_url = excluded.source_url, fetched_at = excluded.fetched_at
    ```
  - `finish(attempted: int, succeeded: int, job: str)`：`attempted >= 1 and succeeded == 0` → `raise RuntimeError(f"{job}: all {attempted} units failed")`。
- Produces（`cac_sieve.py`）：
  - `PATHWAY = "tw_apply"`；`target_years(today: date) -> list[int]`（spec 6.1：≥ 5 月 1 日 `cur = year − 1911` 否則 `year − 1912`；回 `[cur, cur−1, cur−2]`）。
  - `college_list_url(roc) -> str`、`image_url(roc, school_code) -> str`（`{BASE}/cacportal/apply_his_report/{roc}/{roc}_sieve_standard/report/pict/{code}.png`）。
  - `parse_college_list(html: str) -> list[tuple[str, str]]`：`(校碼, 校名)`，從 `report/(\d{3})\.htm">\((\d{3})\)([^<]+)<` 取得。
  - `requirement_from_row(r: SieveRow, image_url: str) -> dict`：`{"cac_code","group","gender","quota","thresholds","multipliers"(Decimal→str 或 float，統一用 `str`),"extra","sources":{"sieve_image": image_url}}`。
  - `sieve_json(r: SieveRow) -> list[dict]`：`[{"order","label","subjects","min_score"(str)}]`。
  - `class CacSieveJob: name = "cac_sieve"; row_count_guard = False; __init__(self, client=None, today=None, parse=parse_sieve_image, budget: Budget | None = None, fetcher: CacFetcher | None = None)`；`run(conn) -> int`：
    1. `source_id = ensure_source(conn, "cac")`；`school_map = load_school_map()`。
    2. 對 `target_years(today)` 每個學年：`fetcher.get(college_list_url)`；404 且不是最新學年 → warning、跳過；404 且是最新學年 → `raise`。解析清單；單位 = 清單 − `done_units`。
    3. 依序處理單位（最新學年優先），每處理一所前檢查 `budget.exhausted`。每所：`with conn.transaction():`（savepoint）下載圖片 → `parse` → 若 `rows_skipped/(rows+rows_skipped) > 0.05` 拋 `ValueError`；否則對每列：校名不在 `school_map` → `UnknownSchoolError`（整個 job 失敗）；`inst_id = _institution_id(...)`；`program_id = upsert_program(..., normalize_program_name(r.name, r.gender), ...)`；`merge_requirement(...)`；`admission_stat` upsert（`min_score NULL, admitted_count NULL, subjects '[]', sieve = sieve_json, tiebreak = '同級分超額篩選' if r.overflow_tiebreak else None`）；最後 `record_unit(... 'done' ...)`。例外（非 `UnknownSchoolError`、非 `BusyError`）→ savepoint 回滾後 `record_unit(... 'failed', error=f"{type(e).__name__}: {e}")`，繼續。`BusyError` → 停止迴圈（不記 failed）。
    4. `finish(attempted, succeeded, self.name)`；回傳寫入的 `admission_stat` 列數。

- [ ] **Step 1: 寫失敗的測試（用假解析器，不跑 OCR）**

```python
# tests/test_cac_sieve_job.py
import datetime, pathlib
from decimal import Decimal
import httpx, pytest
from collegedata.cac_http import CacFetcher
from collegedata.parsers.cac_sieve import SieveRow, SieveLevel, SieveParseResult
from collegedata.jobs.cac_sieve import CacSieveJob, target_years, parse_college_list, college_list_url, image_url
from collegedata.jobs.cac_common import Budget
from collegedata.runner import run_job

FIX = pathlib.Path(__file__).with_name("fixtures") / "cac"
LIST = (FIX / "115_collegeList.htm").read_text(encoding="utf-8")
TODAY = datetime.date(2026, 10, 29)

def _row(code, name, gender=None, quota=23, school="001"):
    return SieveRow(school, code, gender, name, quota, "一般校系",
                    {"國文": "前標", "英文": "均標", "數學A": None, "數學B": None, "社會": None, "自然": None, "英聽": None},
                    {"國文": Decimal("3"), "英文": None, "數學A": None, "數學B": None, "社會": None, "自然": None, "學測科目組合": None},
                    {}, [SieveLevel(1, "社會10", ["社會"], Decimal("10"))], True, [])

def fake_parse(png, school_code, ocr=None):
    if school_code == "001":
        return SieveParseResult([_row("001012", "中國文學系"), _row("001082", "戲劇學系", "男", 8), _row("001082", "戲劇學系", "女", 9)], 0, [], ["一般校系"])
    return SieveParseResult([_row(school_code + "012", "某學系", school=school_code)], 0, [], ["一般校系"])

def _clock():
    t = [0.0]
    def now(): return t[0]
    def sleep(s): t[0] += s
    return now, sleep

def _job(years_html=None, **kw):
    now, sleep = _clock()
    f = CacFetcher(httpx.Client(), min_interval=0, sleep=sleep, clock=now)
    return CacSieveJob(today=TODAY, parse=fake_parse, fetcher=f, budget=Budget(max_schools=kw.pop("max_schools", 10), time_budget=datetime.timedelta(minutes=75), started=0.0), **kw)

def _mock_year(httpx_mock, roc, html=LIST, pngs=("001",)):
    httpx_mock.add_response(url=college_list_url(roc), text=html, is_reusable=True)
    for c in pngs:
        httpx_mock.add_response(url=image_url(roc, c), content=b"png", is_reusable=True)

def test_target_years_roll_on_may_first():
    assert target_years(datetime.date(2027, 4, 30)) == [115, 114, 113]
    assert target_years(datetime.date(2027, 5, 1)) == [116, 115, 114]

def test_parse_college_list():
    lst = parse_college_list(LIST)
    assert len(lst) == 64 and lst[0] == ("001", "國立臺灣大學")

def test_writes_programs_requirement_and_sieve(db, httpx_mock):
    _mock_year(httpx_mock, 115, pngs=("001", "002"))
    for roc in (114, 113):
        _mock_year(httpx_mock, roc, pngs=())
    r = run_job(_job(max_schools=2), db)
    assert r.status == "success" and r.rows_written == 4
    rows = db.execute("""select p.name_zh, q.requirement, s.sieve, s.tiebreak, q.year, q.pathway, q.system_code
                         from admission_requirement q join program p on p.id = q.program_id
                         join admission_stat s on s.program_id = q.program_id and s.year = q.year and s.pathway = q.pathway
                         order by p.name_zh""").fetchall()
    assert [x[0] for x in rows] == ["中國文學系", "戲劇學系(女)", "戲劇學系(男)"]
    req = rows[0][1]
    assert req["cac_code"] == "001012" and req["quota"] == 23 and req["thresholds"]["國文"] == "前標"
    assert req["sources"]["sieve_image"] == image_url(115, "001")
    assert rows[0][2] == [{"order": 1, "label": "社會10", "subjects": ["社會"], "min_score": "10"}]
    assert rows[0][3] == "同級分超額篩選" and rows[0][4:] == (2026, "tw_apply", "tw_gsat")
    done = db.execute("select roc_year, school_code, status, rows_written from cac_fetch order by roc_year desc, school_code").fetchall()
    assert done == [(115, "001", "done", 3), (115, "002", "done", 1)]   # 額度 2 所，最新學年優先

def test_done_units_are_not_refetched(db, httpx_mock):
    _mock_year(httpx_mock, 115, pngs=("001", "002", "003", "004"))
    for roc in (114, 113):
        _mock_year(httpx_mock, roc, pngs=())
    run_job(_job(max_schools=2), db)
    n_before = len(httpx_mock.get_requests())
    run_job(_job(max_schools=2), db)
    image_requests = [q for q in httpx_mock.get_requests()[n_before:] if q.url.path.endswith(".png")]
    assert {q.url.path.split("/")[-1] for q in image_requests} == {"003.png", "004.png"}

def test_busy_stops_run_but_keeps_finished_schools(db, httpx_mock):
    httpx_mock.add_response(url=college_list_url(115), text=LIST)
    httpx_mock.add_response(url=image_url(115, "001"), content=b"png")
    httpx_mock.add_response(url=image_url(115, "002"), text="流量過大，請稍後再試。")
    r = run_job(_job(max_schools=5), db)
    assert r.status == "success"
    assert db.execute("select status from cac_fetch where school_code='001'").fetchone() == ("done",)
    assert db.execute("select count(*) from cac_fetch where school_code='002'").fetchone() == (0,)
    assert not any(q.url.path.endswith("003.png") for q in httpx_mock.get_requests())

def test_parse_failure_marks_unit_failed_and_continues(db, httpx_mock):
    def bad_parse(png, school_code, ocr=None):
        if school_code == "001": raise ValueError("no table")
        return fake_parse(png, school_code)
    _mock_year(httpx_mock, 115, pngs=("001", "002"))
    for roc in (114, 113): httpx_mock.add_response(url=college_list_url(roc), status_code=404)
    r = run_job(_job(max_schools=2, parse=bad_parse), db)
    assert r.status == "success" and r.rows_written == 1
    assert db.execute("select status, error from cac_fetch where school_code='001'").fetchone()[0] == "failed"
    assert "ValueError" in db.execute("select error from cac_fetch where school_code='001'").fetchone()[0]

def test_all_units_failed_fails_job(db, httpx_mock):
    def bad_parse(png, school_code, ocr=None): raise ValueError("x")
    _mock_year(httpx_mock, 115, pngs=("001",))
    for roc in (114, 113): httpx_mock.add_response(url=college_list_url(roc), status_code=404, is_reusable=True)
    r = run_job(_job(max_schools=1, parse=bad_parse), db)
    assert r.status == "failed" and "all 1 units failed" in r.error

def test_newest_year_404_fails(db, httpx_mock):
    httpx_mock.add_response(url=college_list_url(115), status_code=404, is_reusable=True)
    r = run_job(_job(), db)
    assert r.status == "failed" and "404" in r.error

def test_high_skip_ratio_fails_unit(db, httpx_mock):
    def skippy(png, school_code, ocr=None): return SieveParseResult([_row("001012", "中國文學系")], 1, ["skip"], ["一般校系"])
    _mock_year(httpx_mock, 115, pngs=("001",))
    for roc in (114, 113): httpx_mock.add_response(url=college_list_url(roc), status_code=404, is_reusable=True)
    r = run_job(_job(max_schools=1, parse=skippy), db)
    assert r.status == "failed"
    assert db.execute("select count(*) from admission_stat").fetchone() == (0,)

def test_rerun_merges_requirement_keeping_other_sources(db, httpx_mock):
    from collegedata.jobs.cac_common import merge_requirement
    _mock_year(httpx_mock, 115, pngs=("001",))
    for roc in (114, 113): httpx_mock.add_response(url=college_list_url(roc), status_code=404, is_reusable=True)
    run_job(_job(max_schools=1), db)
    pid, sid = db.execute("select p.id, p.source_id from program p where name_zh='中國文學系'").fetchone()
    merge_requirement(db, pid, 2026, {"stage2": {"stage1_pct": 20}, "sources": {"rules_page": "http://r"}}, sid, "http://r")
    req = db.execute("select requirement from admission_requirement where program_id=%s", (pid,)).fetchone()[0]
    assert req["stage2"] == {"stage1_pct": 20} and req["quota"] == 23
    assert req["sources"] == {"sieve_image": image_url(115, "001"), "rules_page": "http://r"}

def test_registered_in_runner():
    from collegedata.runner import REGISTRY
    assert "cac_sieve" in REGISTRY
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `uv run pytest tests/test_cac_sieve_job.py -q`
Expected: FAIL（import error）

- [ ] **Step 3: 實作 `cac_common.py`、`cac_sieve.py`，登記 job，`uac.py` 改用 `upsert_program`**

`_institution_id` 從 `uac.py` import 重用（簽名 `(conn, cache, school_zh, school_map, source_id, source_url)`）。`CacSieveJob` 未傳 `fetcher` 時用 `CacFetcher(make_client())`；未傳 `budget` 時 `Budget.from_env()`。

- [ ] **Step 4: 跑全部測試確認通過**

Run: `uv run pytest -q`
Expected: 全綠（既有 uac 測試在改用 `upsert_program` 後仍通過）

- [ ] **Step 5: Commit**

```bash
git add pipeline/src/collegedata/jobs/cac_common.py pipeline/src/collegedata/jobs/cac_sieve.py pipeline/src/collegedata/jobs/uac.py pipeline/src/collegedata/runner.py pipeline/tests/test_cac_sieve_job.py
git commit -m "feat(cac): cac_sieve job with per-school progress, budgets, busy stop and jsonb merge"
```

---

### Task 6: 校系分則頁面解析

**Files:**
- Create: `pipeline/src/collegedata/parsers/cac_rules.py`
- Test: `pipeline/tests/test_cac_rules_parser.py`

**Interfaces:**
- Produces：
  - `find_system_url(query_html: str, roc: int) -> str | None`：回絕對網址 `https://www.cac.edu.tw/apply{roc}/system/ColQry_…/`（正規表達式 `href="\./system/(ColQry_[^/"]+)/`，取第一個；相對路徑解析以 `apply{roc}/query.php` 為基底）。
  - `parse_total_gsd(html: str) -> list[tuple[str, str, int]]`：`(校碼, 校名, 校系數)`，由 `\((\d{3})\)([^<\-]+?)\s*-(\d+)系` 取得。
  - `parse_code_list(html: str) -> list[str]`：六碼校系代碼，由 `html/\d{3}_(\d{6})\.htm` 取得，去重保序。
  - `@dataclass Stage2Item: name: str; threshold: str | None; pct: int | None`
  - `@dataclass RulesPage: cac_code: str; school: str; name: str; quota: int; gender: str | None; expected_candidates: int | None; fee: int | None; thresholds: dict[str, str | None]; multipliers: dict[str, Decimal | None]; gsat_weights: dict[str, Decimal]; stage1_pct: int | None; items: list[Stage2Item]; tiebreak_order: list[str]; review_items: str | None; exam_date: str | None; website: str | None; overflow_rule: str | None`
  - `parse_rules_page(html: str) -> RulesPage`：以 `html.parser` 走訪 `<td>`，用「標籤格 → 下一格」取值（`校系代碼`、`招生名額`、`性別要求`、`預計甄試人數`、`指定項目甄試費`、`指定項目甄試日期`、`同級分(分數)超額篩選方式`），`class="colname"`／`"gsdname"` 取校名與系名；第一階段三個 `g3` 格（科目、檢定、倍率）各以 `<br>` 分行後 zip，`thresholds`／`multipliers` 先以七科全 None 初始化再填；第二階段：學測採計方式格（`*1.25` 各行對應第一階段科目順序）、佔比格（`20%`）、指定項目三格 zip 成 `items`；同分參酌格以 `<br>` 分行並去掉開頭「一、二、三、四、五、六、」；審查資料「項目：」後的文字為 `review_items`；備註中第一個 `https?://\S+` 為 `website`（去掉結尾的「。」）。找不到 `校系代碼` 格 → `raise ValueError("not a rules page")`。

- [ ] **Step 1: 寫失敗的測試**

```python
# tests/test_cac_rules_parser.py
import pathlib
from decimal import Decimal
import pytest
from collegedata.parsers.cac_rules import find_system_url, parse_total_gsd, parse_code_list, parse_rules_page

FIX = pathlib.Path(__file__).with_name("fixtures") / "cac"
SYS = "https://www.cac.edu.tw/apply115/system/ColQry_115xappLyfOrStu_Azd5gP29/"

def test_find_system_url():
    assert find_system_url((FIX / "115_query.html").read_text(encoding="utf-8"), 115) == SYS
    assert find_system_url("<html>no link</html>", 116) is None

def test_parse_total_gsd():
    lst = parse_total_gsd((FIX / "115_TotalGsdShow.htm").read_text(encoding="utf-8"))
    assert len(lst) == 64 and lst[0] == ("001", "國立臺灣大學", 73) and lst[-1] == ("153", "國立金門大學", 25)

def test_parse_code_list():
    codes = parse_code_list((FIX / "115_ShowGsd_code001.html").read_text(encoding="utf-8"))
    assert len(codes) == 73 and codes[0] == "001012" and "001582" in codes

def test_parse_rules_page_ntu_csie():
    p = parse_rules_page((FIX / "115_001582.htm").read_text(encoding="utf-8"))
    assert (p.cac_code, p.school, p.name, p.quota, p.gender, p.expected_candidates, p.fee) == ("001582", "國立臺灣大學", "資訊工程學系", 57, None, 143, 1500)
    assert p.thresholds == {"國文": None, "英文": "頂標", "數學A": "頂標", "數學B": None, "社會": None, "自然": "頂標", "英聽": None}
    assert p.multipliers["英文"] == Decimal("10") and p.multipliers["數學A"] == Decimal("2.5") and p.multipliers["國文"] is None
    assert p.gsat_weights == {"英文": Decimal("1.25"), "數學A": Decimal("2.00"), "自然": Decimal("1.00")}
    assert p.stage1_pct == 20
    assert [(i.name, i.threshold, i.pct) for i in p.items] == [("審查資料", "70分", 50), ("數學筆試", None, 30)]
    assert p.tiebreak_order == ["審查資料", "數學筆試", "學科能力測驗成績", "學測數學A級分"]
    assert p.review_items.startswith("修課紀錄(A)、課程學習成果(B、C、D)")
    assert p.exam_date == "115.5.17" and p.website == "http://www.csie.ntu.edu.tw"
    assert p.overflow_rule == "一、學測英文、數學A、自然之級分總和"

def test_parse_rules_page_rejects_other_html():
    with pytest.raises(ValueError):
        parse_rules_page("<html><table><tr><td>流量過大</td></tr></table></html>")
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `uv run pytest tests/test_cac_rules_parser.py -q`
Expected: FAIL（import error）

- [ ] **Step 3: 實作 `cac_rules.py`**

- [ ] **Step 4: 跑測試確認通過**

Run: `uv run pytest tests/test_cac_rules_parser.py -q`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add pipeline/src/collegedata/parsers/cac_rules.py pipeline/tests/test_cac_rules_parser.py
git commit -m "feat(cac): parse 校系分則 query system pages (discovery, code lists, detail page)"
```

---

### Task 7: `cac_rules` Job

**Files:**
- Create: `pipeline/src/collegedata/jobs/cac_rules.py`
- Modify: `pipeline/src/collegedata/runner.py:_register_jobs`（登記 `cac_rules`）
- Test: `pipeline/tests/test_cac_rules_job.py`

**Interfaces:**
- Consumes：Task 1、Task 5 `cac_common`（`Budget`、`done_units`、`record_unit`、`upsert_program`、`merge_requirement`、`finish`）、Task 6 解析器、`normalize_program_name`、`uac._institution_id`／`load_school_map`／`UnknownSchoolError`。
- Produces：
  - `target_year(today: date) -> int`（≥ 11 月 1 日 → `year − 1910`，否則 `year − 1911`）。
  - `query_url(roc) -> str`（`{BASE}/apply{roc}/query.php`）。
  - `class NotPublishedYet(Exception)`
  - `requirement_from_page(p: RulesPage, page_url: str) -> dict`：`{"cac_code","quota","gender","thresholds","multipliers"(str),"stage2": {"gsat_weights"(str),"stage1_pct","items":[{"name","threshold","pct"}],"tiebreak_order","review_items","exam_date","expected_candidates","fee","website","overflow_rule"},"sources":{"rules_page": page_url}}`。
  - `class CacRulesJob: name = "cac_rules"; row_count_guard = False; __init__(self, client=None, today=None, budget=None, fetcher=None)`；`run(conn) -> int`：
    1. `roc = target_year(today)`；`fetcher.get(query_url(roc))` → `find_system_url`；為 `None`：若 `today.month in (11, 12)` → `log.warning` 並回傳 0；否則 `raise NotPublishedYet(roc)`。
    2. `fetcher.get(system + "TotalGsdShow.htm")` → `parse_total_gsd`；單位 = 校碼 − `done_units(conn, "cac_rules", roc)`，依校碼排序。
    3. 每所（受額度）：`with conn.transaction():` POST `system + "ShowGsd.php"`（`data={"TxtGsdCode": code3, "SubTxtGsdCode": "依校系代碼查詢", "action": "SubTxtGsdCode"}`）→ `parse_code_list`；對每個六碼代碼 `fetcher.get(system + f"html/{roc}_{code}.htm?v=1.0")` → `parse_rules_page` → 校名查 `school_map`（未知 → `UnknownSchoolError`）→ `upsert_program`（名稱 `normalize_program_name(p.name, p.gender)`）→ `merge_requirement(conn, program_id, roc + 1911, requirement_from_page(...), source_id, page_url)`；全部頁完成後 `record_unit('done', rows_written = 頁數)`。單頁 `ValueError`（非分則頁）→ 計入 `rows_skipped`，繼續；一所學校 `rows_skipped > 0` 仍記 `done` 但寫入 `rows_skipped`。其他例外 → 回滾、`record_unit('failed')`、繼續。`BusyError` → 停止。
    4. `finish(...)`；回傳寫入的頁數。

- [ ] **Step 1: 寫失敗的測試**

```python
# tests/test_cac_rules_job.py
import datetime, pathlib
import httpx, pytest
from collegedata.cac_http import CacFetcher
from collegedata.jobs.cac_common import Budget
from collegedata.jobs.cac_rules import CacRulesJob, target_year, query_url
from collegedata.runner import run_job

FIX = pathlib.Path(__file__).with_name("fixtures") / "cac"
SYS = "https://www.cac.edu.tw/apply115/system/ColQry_115xappLyfOrStu_Azd5gP29/"
QUERY = (FIX / "115_query.html").read_text(encoding="utf-8")
TOTAL = (FIX / "115_TotalGsdShow.htm").read_text(encoding="utf-8")
CODES = (FIX / "115_ShowGsd_code001.html").read_text(encoding="utf-8")
PAGE = (FIX / "115_001582.htm").read_text(encoding="utf-8")
ONE_CODE = '<a href="./html/115_001582.htm?v=1.0">詳細資料</a>'

def _job(today=datetime.date(2026, 10, 29), max_schools=10):
    t = [0.0]
    f = CacFetcher(httpx.Client(), min_interval=0, sleep=lambda s: t.__setitem__(0, t[0] + s), clock=lambda: t[0])
    return CacRulesJob(today=today, fetcher=f, budget=Budget(max_schools=max_schools, time_budget=datetime.timedelta(minutes=75), started=0.0))

def test_target_year_rolls_on_november_first():
    assert target_year(datetime.date(2026, 10, 31)) == 115
    assert target_year(datetime.date(2026, 11, 1)) == 116

def test_not_published_warns_in_november_and_fails_in_january(db, httpx_mock):
    httpx_mock.add_response(url=query_url(116), text="<html>nothing</html>", is_reusable=True)
    r = run_job(_job(today=datetime.date(2026, 11, 15)), db)
    assert r.status == "success" and r.rows_written == 0
    r = run_job(_job(today=datetime.date(2027, 1, 10)), db)
    assert r.status == "failed" and "NotPublishedYet" in r.error

def test_writes_stage2_and_program(db, httpx_mock):
    httpx_mock.add_response(url=query_url(115), text=QUERY)
    httpx_mock.add_response(url=SYS + "TotalGsdShow.htm", text=TOTAL)
    httpx_mock.add_response(url=SYS + "ShowGsd.php", method="POST", text=ONE_CODE)
    httpx_mock.add_response(url=SYS + "html/115_001582.htm?v=1.0", text=PAGE)
    r = run_job(_job(max_schools=1), db)
    assert r.status == "success" and r.rows_written == 1
    row = db.execute("""select p.name_zh, q.requirement, q.source_url from admission_requirement q
                        join program p on p.id = q.program_id""").fetchone()
    assert row[0] == "資訊工程學系" and row[2] == SYS + "html/115_001582.htm?v=1.0"
    req = row[1]
    assert req["stage2"]["stage1_pct"] == 20 and req["stage2"]["items"][0] == {"name": "審查資料", "threshold": "70分", "pct": 50}
    assert req["thresholds"]["英文"] == "頂標" and req["multipliers"]["數學A"] == "2.5" and req["quota"] == 57
    assert req["sources"] == {"rules_page": SYS + "html/115_001582.htm?v=1.0"}
    assert db.execute("select status, rows_written from cac_fetch where job='cac_rules' and school_code='001'").fetchone() == ("done", 1)
    assert db.execute("select count(*) from admission_stat").fetchone() == (0,)
    post = next(q for q in httpx_mock.get_requests() if q.method == "POST")
    assert b"TxtGsdCode=001" in post.content and b"action=SubTxtGsdCode" in post.content

def test_merge_keeps_sieve_keys_written_earlier(db, httpx_mock):
    from collegedata.jobs.cac_common import merge_requirement, upsert_program
    from collegedata.jobs.uac import _institution_id, load_school_map
    from collegedata.sources import ensure_source
    sid = ensure_source(db, "cac")
    inst = _institution_id(db, {}, "國立臺灣大學", load_school_map(), sid, "u")
    pid = upsert_program(db, inst, "資訊工程學系", sid, "u")
    merge_requirement(db, pid, 2026, {"quota": 57, "thresholds": {"英文": "頂標"}, "sources": {"sieve_image": "img"}}, sid, "img")
    httpx_mock.add_response(url=query_url(115), text=QUERY)
    httpx_mock.add_response(url=SYS + "TotalGsdShow.htm", text=TOTAL)
    httpx_mock.add_response(url=SYS + "ShowGsd.php", method="POST", text=ONE_CODE)
    httpx_mock.add_response(url=SYS + "html/115_001582.htm?v=1.0", text=PAGE)
    assert run_job(_job(max_schools=1), db).status == "success"
    req = db.execute("select requirement from admission_requirement where program_id=%s", (pid,)).fetchone()[0]
    assert req["sources"] == {"sieve_image": "img", "rules_page": SYS + "html/115_001582.htm?v=1.0"}
    assert "stage2" in req and req["quota"] == 57
    assert db.execute("select count(*) from program").fetchone() == (1,)

def test_done_school_not_refetched_and_budget(db, httpx_mock):
    httpx_mock.add_response(url=query_url(115), text=QUERY, is_reusable=True)
    httpx_mock.add_response(url=SYS + "TotalGsdShow.htm", text=TOTAL, is_reusable=True)
    httpx_mock.add_response(url=SYS + "ShowGsd.php", method="POST", text=ONE_CODE, is_reusable=True)
    httpx_mock.add_response(url=SYS + "html/115_001582.htm?v=1.0", text=PAGE, is_reusable=True)
    run_job(_job(max_schools=1), db)
    n = len(httpx_mock.get_requests())
    run_job(_job(max_schools=1), db)   # 001 已 done → 處理 002
    posts = [q for q in httpx_mock.get_requests()[n:] if q.method == "POST"]
    assert len(posts) == 1 and b"TxtGsdCode=002" in posts[0].content

def test_busy_on_detail_page_stops_without_failing(db, httpx_mock):
    httpx_mock.add_response(url=query_url(115), text=QUERY, is_reusable=True)
    httpx_mock.add_response(url=SYS + "TotalGsdShow.htm", text=TOTAL, is_reusable=True)
    httpx_mock.add_response(url=SYS + "ShowGsd.php", method="POST", text=ONE_CODE, is_reusable=True)
    httpx_mock.add_response(url=SYS + "html/115_001582.htm?v=1.0", text="流量過大，請稍後再試。", is_reusable=True)
    r = run_job(_job(max_schools=3), db)   # runner 會重試一次，mock 需可重用
    assert r.status == "failed"   # 嘗試 1 所、成功 0 所
    assert db.execute("select count(*) from cac_fetch").fetchone() == (0,)

def test_registered_in_runner():
    from collegedata.runner import REGISTRY
    assert "cac_rules" in REGISTRY
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `uv run pytest tests/test_cac_rules_job.py -q`
Expected: FAIL（import error）

- [ ] **Step 3: 實作 `cac_rules.py` 並登記**

- [ ] **Step 4: 跑全部測試確認通過**

Run: `uv run pytest -q`
Expected: 全綠

- [ ] **Step 5: Commit**

```bash
git add pipeline/src/collegedata/jobs/cac_rules.py pipeline/src/collegedata/runner.py pipeline/tests/test_cac_rules_job.py
git commit -m "feat(cac): cac_rules job (yearly 校系分則 discovery, per-school progress, jsonb merge)"
```

---

### Task 8: 考分會最新學年的時間判斷（修計畫 1 的潛在每週失敗）

**Files:**
- Modify: `pipeline/src/collegedata/jobs/uac.py:year_urls`
- Modify: `pipeline/tests/test_uac_job.py`

**Interfaces:**
- `year_urls(today) -> list[tuple[int, str]]`：分發結果約 8 月公告；`today.month >= 9` 時 `cur = year − 1911`，否則 `cur = year − 1912`。其他行為不變（最新學年 404 仍失敗）。

- [ ] **Step 1: 寫失敗的測試**

```python
def test_year_urls_before_september_uses_previous_roc_year(monkeypatch):
    monkeypatch.setattr("collegedata.jobs.uac.load_years", lambda: [])
    assert [y for y, _ in year_urls(datetime.date(2027, 8, 31))] == [115, 114, 113]
    assert [y for y, _ in year_urls(datetime.date(2027, 9, 1))] == [116, 115, 114]
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `uv run pytest tests/test_uac_job.py -q`
Expected: 1 failed（新測試）

- [ ] **Step 3: 修改 `year_urls`，並更新函式 docstring 說明 9 月門檻**

- [ ] **Step 4: 跑全部測試確認通過**

Run: `uv run pytest -q`
Expected: 全綠（既有 `TODAY = 2026-10-29` 的測試不變）

- [ ] **Step 5: Commit**

```bash
git add pipeline/src/collegedata/jobs/uac.py pipeline/tests/test_uac_job.py
git commit -m "fix(uac): expect the newest ROC year only from September (results publish in August)"
```

---

### Task 9: 排程、文件、設計文件例外、藍圖紀錄

**Files:**
- Modify: `.github/workflows/pipeline.yml`
- Modify: `docs/deploy.md`
- Modify: `設計文件.md`（6.1 來源表、6.4）
- Modify: `藍圖.md`（第 8 節討論紀錄末尾）
- Modify: `README.md`（若列有 job 清單）
- Test: `pipeline/tests/test_smoke.py`（既有；確認 CLI 認得新 job）

- [ ] **Step 1: 寫失敗的測試（若 `test_smoke.py` 有「未知 job 回 1」的樣式，加一個「已知 job 名單含 cac_sieve、cac_rules」斷言）**

```python
def test_cli_knows_cac_jobs():
    from collegedata.runner import REGISTRY
    assert {"cac_sieve", "cac_rules"} <= set(REGISTRY)
```

- [ ] **Step 2: 修改 `pipeline.yml`**

- `schedule` 加 `- cron: "0 3 * * 5"   # cac_sieve, weekly Friday` 與 `- cron: "0 3 * * 6"   # cac_rules, weekly Saturday`；`case` 對應加兩行。
- `workflow_dispatch.inputs.job.options` 加 `cac_sieve`、`cac_rules`；新增 inputs `max_schools`（string，required false，description `cac jobs only: schools per run (default 10)`）與 `time_budget_minutes`（string，required false，description `cac jobs only: minutes before the run stops starting new schools (default 75)`）。
- Run 步驟 `env` 加 `CAC_MAX_SCHOOLS: ${{ github.event.inputs.max_schools }}`、`CAC_TIME_BUDGET_MINUTES: ${{ github.event.inputs.time_budget_minutes }}`（空字串時 `Budget.from_env` 必須視同未設定 — 在 Task 5 的 `from_env` 以 `os.environ.get(...) or default` 處理；本 Task 加一個 `from_env` 空字串測試到 `tests/test_cac_sieve_job.py`）。

- [ ] **Step 3: 文件**

- `docs/deploy.md`：排程表加兩列（週五 03:00 UTC `cac_sieve`、週六 03:00 UTC `cac_rules`，說明額度、累積完成、初次載入可手動執行並設 `max_schools=30`／`time_budget_minutes=100` 多跑幾次、約需幾次）；新增「重抓甄選會資料」段落：`delete from cac_fetch where job = 'cac_sieve' and roc_year = 115;`；說明「流量過大」時 job 會提早結束不算失敗。
- `設計文件.md` 6.1 來源表：台灣 甄選會 那列改為「圖片 OCR＋HTML 解析｜系級：個人申請檢定與篩選標準、通過篩選最低級分、第二階段比重｜每週（額度制累積，資料每年更新）」；6.4 最後一點改為「所有抓取尊重 robots.txt 與合理頻率。**例外（使用者 2026-10-29 決定）**：甄選會 cac.edu.tw 的 robots.txt 全站禁止抓取，仍以節制方式抓取（固定識別 User-Agent 含聯絡信箱、請求間隔 ≥ 3 秒、每筆資料只抓一次、每次執行有額度、遇流量限制即停止）；細節見 `docs/superpowers/specs/2026-10-29-cac-apply-design.md` 第 4 節」。
- `藍圖.md` 第 8 節末尾加一行：`- 2026-10-29：使用者決定甄選會資料照抓（方案 C，節制抓取）。計畫 1b 實作完成（分支 plan-1b-cac）：cac_sieve（圖片 OCR）與 cac_rules（校系分則）兩個 job、migration 0005、考分會學年時間判斷修正。`
- `README.md`：若有 job 清單，加兩個 job。

- [ ] **Step 4: 跑全部測試確認通過**

Run: `uv run pytest -q`
Expected: 全綠

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/pipeline.yml docs/deploy.md 設計文件.md 藍圖.md README.md pipeline/tests
git commit -m "ci(cac): weekly cac_sieve/cac_rules schedules with budget inputs; docs and spec exception"
```

---

## 自我檢查（寫計畫時已做）

- 規格涵蓋：第 3 節事實 → Task 1（憑證、節流、續傳、忙碌）、Task 5／7（網址）；第 4 節硬性規定 → Task 1、5、7；第 5 節資料模型 → Task 2、5、7；第 6 節 → Task 3、4、5；第 7 節 → Task 6、7；第 8 節 → Task 9；第 9 節測試 → 各 Task。規格第 10 節「sha256」交給 Task 5 實作者決定（可加 `cac_fetch` 欄位需同步改 migration；預設不做）。
- 型別一致：`SieveRow`／`SieveLevel`／`SieveParseResult`（Task 3／4）在 Task 5 以相同欄位順序建構；`Budget(max_schools, time_budget, started)`、`CacFetcher(client, min_interval, sleep, clock)` 在 Task 5／7 測試中以相同簽名使用；`merge_requirement(conn, program_id, year, requirement, source_id, source_url)` 在 Task 5／7 相同。
- Review Focus 五項各有對應測試（Task 4、3／4、5、7、5／7）。
- pytest-httpx 預設會在測試結束時檢查每個登記的回應都被請求過；各測試只登記會用到的網址，runner 會重試的情境用 `is_reusable=True`。

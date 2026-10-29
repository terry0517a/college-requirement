# 計畫 2：美國 College Scorecard 資料管線 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 每週自動從美國教育部 College Scorecard API 抓取約 1,579 所「以學士為主、仍在營運、有錄取率」的美國大學，寫入學校主檔、科系、錄取要求（SAT／ACT 區間）、錄取率、學費與校級統計（規模、畢業率、畢業薪資），並補上計畫 1 留下的三個管線缺口（Hipo 覆寫問題、OpenAlex 全失敗仍算成功、OpenAlex 永遠配不到的學校卡在批次最前面）。

**Architecture:** 沿用計畫 1 的「一個來源一個 Job」結構：`ScorecardJob` 先探測最新資料年，再用一次分頁掃描（每頁 100 筆、約 16 頁）同時取三個年度的欄位，純函式 `parse_school` 把一筆 API 紀錄轉成 dataclass，再由各 upsert 函式寫入。一次 migration（0003）補齊美國資料需要的欄位：`institution.scorecard_id／city／region`、`program.code`（美國科系用 CIP 兩碼當鍵，整校用 `all`）、統一科系領域表 `field`、`admission_stat.admission_rate`、新表 `institution_stat`。

**Tech Stack:** 同計畫 1：PostgreSQL 17、Python 3.12 + uv、psycopg 3、httpx、pytest + pytest-httpx、GitHub Actions。

**Spec:** `/Users/terry/Desktop/college requirement/設計文件.md`（5.1.3、5.1.4、5.1.5、6.1、6.1.1、6.2、6.3、6.4 為本計畫依據）；計畫 1 的 ledger `docs/superpowers/plans/2026-10-29-01-foundation-tw-pipeline-ledger.md` 列出的「Parked／deferred to plan 2」項目也在範圍內。

**分支：** 從 `plan-1-foundation`（或已合併後的 `main`）開 `plan-2-us-scorecard`。

## 已驗證的 API 事實（2026-10-29 以 DEMO_KEY 實測）

- 端點 `https://api.data.gov/ed/collegescorecard/v1/schools`，所有請求需 `api_key`。正式金鑰每 IP 每小時 1,000 次；`DEMO_KEY` 每小時只有 10 次（只能用來做 fixture，不能用在測試或排程）。
- 篩選 `school.degrees_awarded.predominant=3&school.operating=1&latest.admissions.admission_rate.overall__range=0.0001..1` 得 1,579 所（設計文件 6.1.1 預估 1,500–2,000）。其中有 SAT 數學 25 百分位的只有 927 所。
- `per_page` 最大 100，`page` 從 0 起算，可加 `sort=id`；回傳 `{"metadata":{"page","total","per_page"},"results":[...]}`。
- 欄位可用年份前綴：`2024.admissions.admission_rate.overall`；不存在的年份（如 2025）回傳 `null` 而不是錯誤，所以「最新年份」要用 `__range` 篩選的 `total > 0` 探測。目前最新年是 2024。
- 多筆 id 可用逗號：`id=243744,100654`。
- `school.school_url` 格式不一（`www.stanford.edu/`、`https://behrend.psu.edu/`），分校各有子網域。`school.ownership`：1 公立、2 私立非營利、3 私立營利。`school.main_campus`：1／0。
- 38 個學士科系旗標 `latest.academics.program.bachelors.<key>`（1＝有開設）全部有效，key 清單見 Task 2。
- Stanford（id 243744）2024 實值可當測試資料：admission_rate 0.0361，SAT RW 740／780，SAT Math 770／800，ACT 34／35，tuition in_state＝out_of_state＝68544，size 7554，completion 0.9164，earnings 125340，ownership 2，main_campus 1，school_url `www.stanford.edu/`。

## Global Constraints

- 每一筆學校資料都必須有 `source_id`、`source_url`、`fetched_at`，資料表以 NOT NULL 強制（設計文件 5.1.10）。`source_url` 必須是去掉 `api_key` 參數的請求網址（計畫 1 Task 7 裁定）。
- 只用免費方案；API 金鑰以 GitHub secret `SCORECARD_API_KEY` 提供，絕不寫進程式或 fixture。
- 美國只收以學士為主的四年制、仍在營運、有錄取率資料的機構（設計文件 6.1.1）；篩選條件就是上面的 API filter。
- 歷史資料保留最近三年（設計文件 6.1.1）：以探測到的最新年 Y 為準，取 Y、Y−1、Y−2。
- 美國分級只用 SAT／ACT 區間與錄取率（設計文件 6.1）；沒有 SAT／ACT 區間的學校不寫 `admission_requirement`，網站顯示「資料不足」。
- 同一來源的請求間隔至少 1 秒（設計文件 6.4）。
- 所有寫入都是 upsert，重跑筆數不變、`fetched_at` 更新。
- 幣別 `USD`；美國學費只有本地生（`local`＝in_state）與外地生（`out_of_state`）兩種，Scorecard 沒有國際生學費，網站以 `out_of_state` 代替並標示（記入 ledger 給計畫 3）。
- Python 程式碼放在 `pipeline/src/collegedata/`，測試放在 `pipeline/tests/`，fixture 放在 `pipeline/tests/fixtures/`。測試不連網（pytest-httpx）。
- Commit 訊息結尾加：`Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`。

## Review Focus

1. 有錄取率但 SAT／ACT 全為 null 的學校（約 650 所）：必須寫 `admission_stat.admission_rate`，不寫 `admission_requirement`，不得寫出全 null 的 requirement。（Task 3 測試）
2. `school.school_url` 為 null，或兩所 Scorecard 學校正規化後網域相同：不得當掉、不得把兩所學校合併成同一個 `institution`。（Task 2、Task 3 測試）
3. 年初新年度資料尚未發布：最新年探測必須跳過 `total = 0` 的年份；連續六年都沒有則 Job 失敗（不是寫入 0 筆成功）。（Task 3 測試）
4. Hipo 每週一重跑：不得把 Scorecard 寫入的校名、網址、公私立覆寫回 Hipo 的舊值。（Task 4 測試）
5. OpenAlex 整批請求全部失敗（非 429）：Job 必須失敗並開 Issue，而不是「成功、0 筆」。（Task 5 測試）

---

### Task 1: Migration 0003：美國資料需要的欄位與統一領域表

**Files:**
- Create: `supabase/migrations/0003_us_scorecard.sql`
- Modify: `pipeline/tests/test_schema.py`

**Interfaces:**
- Produces（後續 Task 的契約）：
  - `institution` 新增 `scorecard_id int`、`city text`、`region text`；部分唯一索引 `institution_scorecard_id_key on institution(scorecard_id) where scorecard_id is not null`。
  - `program` 新增 `code text`；部分唯一索引 `program_institution_code_key on program(institution_id, code) where code is not null`。約定：美國科系 `code` 為 CIP 兩碼字串（如 `'11'`），整校代表 program 的 `code = 'all'`、`field_code = NULL`、`name_en = 'All undergraduate programs'`。
  - 新表 `field(code text primary key, name_zh text not null, name_en text not null, sort int not null)`，並加 `program.field_code` → `field(code)` 外鍵（既有列皆為 NULL，不受影響）。
  - 種子資料（`insert ... on conflict (code) do nothing`），依 `sort` 順序：
    | code | name_zh | name_en |
    |---|---|---|
    | cs | 資訊 | Computer & Information Science |
    | engineering | 工程 | Engineering |
    | math | 數學與統計 | Mathematics & Statistics |
    | physical_science | 物理與化學 | Physical Sciences |
    | life_science | 生命科學 | Biological Sciences |
    | agriculture | 農業與環境 | Agriculture & Natural Resources |
    | architecture | 建築與設計 | Architecture & Design |
    | business | 商管 | Business & Management |
    | social_science | 社會科學 | Social Sciences |
    | public_affairs | 公共事務 | Public Affairs & Services |
    | law | 法律 | Law |
    | health | 醫學與健康 | Medicine & Health |
    | psychology | 心理 | Psychology |
    | education | 教育 | Education |
    | humanities | 人文 | Humanities |
    | arts | 藝術 | Visual & Performing Arts |
    | communication | 傳播 | Communication & Media |
    | interdisciplinary | 跨領域 | Interdisciplinary |
    | applied | 技職與應用 | Trades & Applied Studies |
  - `admission_stat` 新增 `admission_rate numeric(6,5)`；`admitted_count` 改為可 NULL。
  - 新表 `institution_stat(id serial pk, institution_id int not null references institution, year int not null, student_size int, completion_rate numeric(6,5), median_earnings numeric(12,2), currency char(3), source_id int not null references source, source_url text not null, fetched_at timestamptz not null, unique(institution_id, year))`。
  - RLS：`field`、`institution_stat` 啟用 RLS 並加 anon SELECT policy（與 0002 同樣寫法）。

- [ ] **Step 1: 在 `pipeline/tests/test_schema.py` 加失敗測試**

```python
def test_0003_columns_and_tables(db):
    names = {r[0] for r in db.execute(
        "select table_name from information_schema.tables where table_schema='public'")}
    assert {"field", "institution_stat"} <= names
    cols = {r[0] for r in db.execute(
        "select column_name from information_schema.columns where table_name='institution'")}
    assert {"scorecard_id", "city", "region"} <= cols
    assert db.execute("select count(*) from field").fetchone()[0] == 19
    assert db.execute("select is_nullable from information_schema.columns "
                      "where table_name='admission_stat' and column_name='admitted_count'").fetchone()[0] == "YES"

def test_program_code_unique_per_institution(db):
    sid = ensure_source(db, "hipo")
    iid = db.execute("insert into institution(country_code,name_en,domain,source_id,source_url,fetched_at) "
                     "values ('US','X','x.edu',%s,'u',now()) returning id", (sid,)).fetchone()[0]
    db.execute("insert into program(institution_id,code,name_en,source_id,source_url,fetched_at) values (%s,'11','CS',%s,'u',now())", (iid, sid))
    with pytest.raises(psycopg.errors.UniqueViolation):
        db.execute("insert into program(institution_id,code,name_en,source_id,source_url,fetched_at) values (%s,'11','CS',%s,'u',now())", (iid, sid))

def test_program_field_code_must_exist(db):
    sid = ensure_source(db, "hipo")
    iid = db.execute("insert into institution(country_code,name_en,domain,source_id,source_url,fetched_at) "
                     "values ('US','X','x.edu',%s,'u',now()) returning id", (sid,)).fetchone()[0]
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        db.execute("insert into program(institution_id,code,field_code,source_id,source_url,fetched_at) values (%s,'99','nope',%s,'u',now())", (iid, sid))
```
（檔案頂端需 `from collegedata.sources import ensure_source`。）

- [ ] **Step 2: 執行測試確認失敗**

Run: `cd pipeline && uv run pytest tests/test_schema.py -v`
Expected: 三個新測試 FAIL（表或欄位不存在）。

- [ ] **Step 3: 寫 `supabase/migrations/0003_us_scorecard.sql`**

依 Interfaces 建立欄位、索引、`field` 表與 19 筆種子、`institution_stat`、外鍵、RLS 與 policy。

- [ ] **Step 4: 執行全部測試確認通過**

Run: `cd pipeline && uv run pytest -v`
Expected: 全部 PASS（既有 46 個 + 3 個新測試；UAC 測試中 `admitted_count = 0` 的斷言不受影響）。

- [ ] **Step 5: Commit**

```bash
git add supabase/migrations/0003_us_scorecard.sql pipeline/tests/test_schema.py
git commit -m "feat(db): scorecard ids, program codes, unified field table, institution_stat"
```

### Task 2: Scorecard 紀錄解析（純函式）與科系對應表

**Files:**
- Create: `pipeline/config/scorecard_programs.yaml`
- Create: `pipeline/src/collegedata/parsers/scorecard.py`
- Create: `pipeline/tests/fixtures/scorecard_sample.json`
- Test: `pipeline/tests/test_scorecard_parser.py`

**Interfaces:**
- Consumes: Task 1 的 `field.code` 清單。
- Produces（`collegedata/parsers/scorecard.py`）：
  - `SCHOOL_FIELDS: list[str]` = `["id", "school.name", "school.city", "school.state", "school.school_url", "school.ownership", "school.main_campus"]`
  - `YEAR_FIELDS: list[str]`（不含年份前綴）= `["admissions.admission_rate.overall", "admissions.sat_scores.25th_percentile.critical_reading", "admissions.sat_scores.75th_percentile.critical_reading", "admissions.sat_scores.25th_percentile.math", "admissions.sat_scores.75th_percentile.math", "admissions.act_scores.25th_percentile.cumulative", "admissions.act_scores.75th_percentile.cumulative", "cost.tuition.in_state", "cost.tuition.out_of_state", "student.size", "completion.completion_rate_4yr_150nt", "earnings.10_yrs_after_entry.median"]`
  - `PROGRAM_KEYS: list[str]`：`scorecard_programs.yaml` 的 38 個 key，依檔案順序。
  - `fields_param(years: list[int]) -> str`：回傳逗號連接的欄位字串，順序為 SCHOOL_FIELDS、每個年份的 `f"{y}.{f}"`、`f"latest.academics.program.bachelors.{key}"`。
  - `normalize_domain(url: str | None) -> str | None`：去掉 scheme、路徑、前綴 `www.`，轉小寫；空字串或 None 回傳 None。`"www.stanford.edu/"` → `"stanford.edu"`，`"https://behrend.psu.edu/"` → `"behrend.psu.edu"`，`"HTTPS://WWW.X.EDU/admissions?a=1"` → `"x.edu"`。
  - `@dataclass YearStats`：`year: int`、`admission_rate: float | None`、`sat_rw: tuple[int,int] | None`、`sat_math: tuple[int,int] | None`、`act: tuple[int,int] | None`、`tuition_in_state: float | None`、`tuition_out_of_state: float | None`、`student_size: int | None`、`completion_rate: float | None`、`median_earnings: float | None`。區間 tuple 只有在 25 與 75 百分位都非 null 時才有值，否則 None。
  - `@dataclass School`：`scorecard_id: int`、`name: str`、`city: str | None`、`region: str | None`、`domain: str | None`、`web_url: str | None`（原始 `school.school_url` 補上 `https://` 前綴，若為 None 則 None）、`control: str`（ownership 1 → `'public'`，2 或 3 → `'private'`）、`main_campus: bool`、`program_keys: list[str]`（旗標為 1 的 key，依 PROGRAM_KEYS 順序）、`years: list[YearStats]`（依傳入 years 順序）。
  - `parse_school(rec: dict, years: list[int]) -> School`。
  - `load_program_map() -> dict[str, dict]`：讀 yaml，key → `{"cip2": str, "name_en": str, "field_code": str}`。
- `scorecard_programs.yaml` 內容（key、cip2、name_en 取自 Scorecard 資料字典的 CIP 兩碼系列名稱、field_code 對應 Task 1 的領域表）：

| key | cip2 | name_en | field_code |
|---|---|---|---|
| agriculture | 01 | Agriculture, Agriculture Operations, and Related Sciences | agriculture |
| resources | 03 | Natural Resources and Conservation | agriculture |
| architecture | 04 | Architecture and Related Services | architecture |
| ethnic_cultural_gender | 05 | Area, Ethnic, Cultural, Gender, and Group Studies | social_science |
| communication | 09 | Communication, Journalism, and Related Programs | communication |
| communications_technology | 10 | Communications Technologies/Technicians and Support Services | communication |
| computer | 11 | Computer and Information Sciences and Support Services | cs |
| personal_culinary | 12 | Personal and Culinary Services | applied |
| education | 13 | Education | education |
| engineering | 14 | Engineering | engineering |
| engineering_technology | 15 | Engineering Technologies and Engineering-Related Fields | engineering |
| language | 16 | Foreign Languages, Literatures, and Linguistics | humanities |
| family_consumer_science | 19 | Family and Consumer Sciences/Human Sciences | applied |
| legal | 22 | Legal Professions and Studies | law |
| english | 23 | English Language and Literature/Letters | humanities |
| humanities | 24 | Liberal Arts and Sciences, General Studies and Humanities | humanities |
| library | 25 | Library Science | humanities |
| biological | 26 | Biological and Biomedical Sciences | life_science |
| mathematics | 27 | Mathematics and Statistics | math |
| military | 29 | Military Technologies and Applied Sciences | public_affairs |
| multidiscipline | 30 | Multi/Interdisciplinary Studies | interdisciplinary |
| parks_recreation_fitness | 31 | Parks, Recreation, Leisure, and Fitness Studies | applied |
| philosophy_religious | 38 | Philosophy and Religious Studies | humanities |
| theology_religious_vocation | 39 | Theology and Religious Vocations | humanities |
| physical_science | 40 | Physical Sciences | physical_science |
| science_technology | 41 | Science Technologies/Technicians | interdisciplinary |
| psychology | 42 | Psychology | psychology |
| security_law_enforcement | 43 | Homeland Security, Law Enforcement, Firefighting and Related Protective Services | public_affairs |
| public_administration_social_service | 44 | Public Administration and Social Service Professions | public_affairs |
| social_science | 45 | Social Sciences | social_science |
| construction | 46 | Construction Trades | applied |
| mechanic_repair_technology | 47 | Mechanic and Repair Technologies/Technicians | applied |
| precision_production | 48 | Precision Production | applied |
| transportation | 49 | Transportation and Materials Moving | applied |
| visual_performing | 50 | Visual and Performing Arts | arts |
| health | 51 | Health Professions and Related Programs | health |
| business_marketing | 52 | Business, Management, Marketing, and Related Support Services | business |
| history | 54 | History | humanities |

- [ ] **Step 1: 建立 fixture `pipeline/tests/fixtures/scorecard_sample.json`**

格式同 API 回應：`{"metadata": {"page": 0, "total": 3, "per_page": 100}, "results": [...]}`，欄位為 `fields_param([2024, 2023, 2022])` 的全部欄位（每筆都要有每個 key，值可為 null）。三筆：
1. Stanford（id 243744）：用本文件「已驗證的 API 事實」的 2024 實值；2023、2022 的 admission_rate 用 0.0391、0.0368，其餘年份欄位可複製 2024 值；38 個旗標中 computer、engineering、mathematics、biological、history 為 1，其餘 0。
2. 虛構「Test-Optional College」（id 900001，`school.school_url` 為 `"https://www.testoptional.edu/"`，ownership 1，main_campus 1）：三年都有 admission_rate（0.65、0.6、0.58）、tuition（in 12000／out 30000）、size 5000，但 SAT／ACT 七個欄位全部 null，completion 與 earnings 為 null；旗標只有 business_marketing 為 1。
3. 虛構「No URL Institute」（id 900002，`school.school_url` 為 null，ownership 3，main_campus 0）：只有 2024 有 admission_rate 0.5，其餘全部 null；旗標全 0。

可用 `DEMO_KEY` 抓 Stanford 真實回應當第 1 筆（每小時只有 10 次額度；請求：`id=243744&per_page=100&fields=<fields_param>`），再手寫另外兩筆。

- [ ] **Step 2: 寫失敗測試 `pipeline/tests/test_scorecard_parser.py`**

```python
import json, pathlib, pytest
from collegedata.parsers.scorecard import (fields_param, normalize_domain, parse_school,
                                           load_program_map, PROGRAM_KEYS, SCHOOL_FIELDS, YEAR_FIELDS)

FIX = json.loads(pathlib.Path(__file__).with_name("fixtures").joinpath("scorecard_sample.json").read_text())
YEARS = [2024, 2023, 2022]

@pytest.mark.parametrize("url,expected", [
    ("www.stanford.edu/", "stanford.edu"), ("https://behrend.psu.edu/", "behrend.psu.edu"),
    ("HTTPS://WWW.X.EDU/admissions?a=1", "x.edu"), ("", None), (None, None)])
def test_normalize_domain(url, expected):
    assert normalize_domain(url) == expected

def test_fields_param_order_and_count():
    p = fields_param(YEARS).split(",")
    assert p[:7] == SCHOOL_FIELDS
    assert p[7] == "2024.admissions.admission_rate.overall"
    assert len(p) == 7 + 3 * len(YEAR_FIELDS) + 38
    assert p[-1] == "latest.academics.program.bachelors.history"

def test_parse_stanford():
    s = parse_school(FIX["results"][0], YEARS)
    assert (s.scorecard_id, s.domain, s.control, s.main_campus) == (243744, "stanford.edu", "private", True)
    assert s.web_url == "https://www.stanford.edu/"
    y = s.years[0]
    assert (y.year, y.admission_rate, y.sat_rw, y.sat_math, y.act) == (2024, 0.0361, (740, 780), (770, 800), (34, 35))
    assert (y.tuition_in_state, y.student_size, y.completion_rate, y.median_earnings) == (68544, 7554, 0.9164, 125340)
    assert s.program_keys == ["computer", "engineering", "biological", "mathematics", "history"]

def test_parse_missing_scores_and_url():
    t = parse_school(FIX["results"][1], YEARS)
    assert t.years[0].admission_rate == 0.65 and t.years[0].sat_rw is None and t.years[0].act is None
    n = parse_school(FIX["results"][2], YEARS)
    assert n.domain is None and n.web_url is None and n.control == "private" and n.program_keys == []
    assert n.years[1].admission_rate is None

def test_program_map_covers_all_keys_with_valid_fields(db):
    m = load_program_map()
    assert list(m) == PROGRAM_KEYS and len(m) == 38
    codes = {r[0] for r in db.execute("select code from field")}
    assert all(v["field_code"] in codes and len(v["cip2"]) == 2 for v in m.values())
```

- [ ] **Step 3: 執行測試確認失敗**

Run: `cd pipeline && uv run pytest tests/test_scorecard_parser.py -v`
Expected: FAIL，`ModuleNotFoundError: collegedata.parsers.scorecard`。

- [ ] **Step 4: 寫 `pipeline/config/scorecard_programs.yaml` 與 `pipeline/src/collegedata/parsers/scorecard.py`**

依 Interfaces 實作；`PROGRAM_KEYS` 由 `load_program_map()` 在 import 時讀出（yaml 用 list 而非 dict 以保證順序，或 dict 依插入順序）。

- [ ] **Step 5: 執行測試確認通過**

Run: `cd pipeline && uv run pytest tests/test_scorecard_parser.py -v`
Expected: 全部 PASS。

- [ ] **Step 6: Commit**

```bash
git add pipeline/config/scorecard_programs.yaml pipeline/src/collegedata/parsers/scorecard.py pipeline/tests/fixtures/scorecard_sample.json pipeline/tests/test_scorecard_parser.py
git commit -m "feat(scorecard): record parser, field list, CIP-2 program map"
```

### Task 3: ScorecardJob：最新年探測、分頁抓取、寫入

**Files:**
- Create: `pipeline/src/collegedata/jobs/scorecard.py`
- Modify: `pipeline/config/sources.yaml`（加 `scorecard` 條目）
- Modify: `pipeline/src/collegedata/runner.py:_register_jobs`（登錄 `"scorecard"`）
- Test: `pipeline/tests/test_scorecard_job.py`

**Interfaces:**
- Consumes: Task 1 的資料表；Task 2 的 `fields_param`、`parse_school`、`load_program_map`、`School`、`YearStats`；計畫 1 的 `ensure_source(conn, code) -> int`、`run_job`、`REGISTRY`。
- Produces（`collegedata/jobs/scorecard.py`）：
  - 常數 `SCORECARD_URL = "https://api.data.gov/ed/collegescorecard/v1/schools"`、`BASE_FILTER = {"school.degrees_awarded.predominant": 3, "school.operating": 1, "latest.admissions.admission_rate.overall__range": "0.0001..1"}`、`PER_PAGE = 100`、`YEARS_BACK = 2`、`MAX_PROBE_YEARS = 6`、`PATHWAY = "us_freshman"`、`SYSTEM_CODE = "us_sat"`、`ALL_PROGRAM_CODE = "all"`、`ALL_PROGRAM_NAME = "All undergraduate programs"`。
  - `class ScorecardDataError(Exception)`。
  - `class ScorecardJob`：`name = "scorecard"`；`__init__(self, client: httpx.Client | None = None, api_key: str | None = None, today: datetime.date | None = None, limit: int | None = None)`，`api_key` 預設讀環境變數 `SCORECARD_API_KEY`；`run(self, conn) -> int` 回傳處理的學校數（預期約 1,579；沿用 runner 的 50% 筆數防呆）。
  - `latest_year(self, client) -> int`：對 `y` 從 `today.year` 往前共 `MAX_PROBE_YEARS` 年，GET `SCORECARD_URL` 帶 `BASE_FILTER`、`f"{y}.admissions.admission_rate.overall__range": "0.0001..1"`、`per_page: 1`、`fields: "id"`、`api_key`；第一個 `metadata.total > 0` 的 `y` 即為最新年；都沒有則 raise `ScorecardDataError`。
  - `years = [latest, latest-1, latest-2]`。
  - 分頁：`page` 從 0 起，參數 `BASE_FILTER` + `per_page=PER_PAGE`、`sort="id"`、`fields=fields_param(years)`、`api_key`；直到 `(page+1)*PER_PAGE >= metadata.total` 或 `results` 為空；頁與頁之間 `time.sleep(1)`；`limit` 若有，處理滿 `limit` 筆學校就停止（供手動測試）。任何非 2xx 回應 `raise_for_status()`（含 429，整個 Job 失敗由 runner 重試一次並記錄）。
  - `source_url` = 該頁請求網址去掉 `api_key`（`str(resp.request.url.copy_remove_param("api_key"))`）。
  - `upsert_institution(conn, school: School, source_id: int, source_url: str) -> int`，規則依序：
    1. `select id from institution where scorecard_id = %s` 命中 → update `name_en, city, region, control, web_url, source_id, source_url, fetched_at`（`domain` 不變）。
    2. 否則若 `school.main_campus` 且 `school.domain` 非 None，`select id from institution where country_code='US' and domain=%s and scorecard_id is null` 命中 → 同上 update 並設 `scorecard_id`。
    3. 否則 insert：`domain` 為 `school.domain`；若 `school.domain` 為 None 或該 domain 已被其他列使用，`domain = f"{school.domain or 'scorecard'}#{school.scorecard_id}"`。
  - `upsert_programs(conn, inst_id: int, school: School, program_map: dict, source_id, source_url) -> int`：寫整校 program（`code='all'`、`name_en=ALL_PROGRAM_NAME`、`field_code=NULL`）＋每個 `program_keys` 一筆（`code=cip2`、`name_en`、`field_code`），`on conflict (institution_id, code) where code is not null do update set name_en, field_code, source_id, source_url, fetched_at`；回傳整校 program 的 id。學校本次沒出現的 CIP 科系不刪（Scorecard 旗標年年變動，保留以免網站頁面消失）。
  - `upsert_year(conn, inst_id: int, all_program_id: int, ys: YearStats, source_id, source_url) -> None`：
    - `admission_stat`（`program_id=all_program_id, year, pathway=PATHWAY`）：`admission_rate` 非 None 才寫，`admitted_count=NULL`、`min_score=NULL`、`subjects='[]'`。
    - `admission_requirement`（同鍵，`system_code=SYSTEM_CODE`）：`sat_rw`、`sat_math`、`act` 至少一個非 None 才寫；`requirement` JSON 結構固定為 `{"sat": {"rw": {"p25": 740, "p75": 780} | null, "math": {...} | null, "total": {"p25": 1510, "p75": 1580} | null}, "act": {"composite": {"p25": 34, "p75": 35} | null}}`，`total` 為 rw 與 math 同時存在時的相加。
    - `cost`：`tuition_in_state` 非 None → `residency='local'`；`tuition_out_of_state` 非 None → `residency='out_of_state'`；`currency='USD'`。
    - `institution_stat`：`student_size`、`completion_rate`、`median_earnings` 至少一個非 None 才寫，`currency='USD'`。
    - 全部 `on conflict ... do update` 更新所有值欄位與 `source_id, source_url, fetched_at`。
- `sources.yaml` 新增：
  ```yaml
  scorecard:
    name: College Scorecard (U.S. Department of Education)
    url: https://collegescorecard.ed.gov/
    license: Public domain (U.S. Government work)
  ```

- [ ] **Step 1: 寫失敗測試 `pipeline/tests/test_scorecard_job.py`**

以 pytest-httpx 模擬。`probe(y, total)` 輔助函式註冊 `url=re.compile(rf".*{y}\.admissions\.admission_rate\.overall__range=.*per_page=1.*")` 回 `{"metadata": {"total": total}, "results": []}`；`page()` 註冊 `url=re.compile(r".*per_page=100.*")` 回 fixture。`today = datetime.date(2026, 10, 29)`。

```python
def test_probes_latest_year_skipping_empty_years(db, httpx_mock):
    # 2026, 2025 回 0 筆；2024 有 → years = 2024, 2023, 2022
    ...
    r = run_job(ScorecardJob(client=httpx.Client(), api_key="k1", today=TODAY), db)
    assert r.status == "success" and r.rows_written == 3
    years = {x[0] for x in db.execute("select distinct year from admission_stat")}
    assert years == {2024, 2023, 2022}
    # 請求 fields 必須含 2024 與 2022 前綴，且 source_url 不含 api_key
    urls = [x[0] for x in db.execute("select distinct source_url from institution where scorecard_id is not null")]
    assert urls and all("api_key" not in u and "2024.admissions" in u for u in urls)

def test_fails_when_no_year_has_data(db, httpx_mock):
    # 六次探測都回 total 0
    r = run_job(ScorecardJob(client=httpx.Client(), api_key="k1", today=TODAY), db)
    assert r.status == "failed" and "ScorecardDataError" in r.error
    assert db.execute("select count(*) from institution").fetchone()[0] == 0

def test_writes_requirement_stat_cost_programs_for_stanford(db, httpx_mock):
    ...
    iid = db.execute("select id from institution where scorecard_id=243744").fetchone()[0]
    assert db.execute("select name_en, domain, control, city, region from institution where id=%s", (iid,)).fetchone() \
        == ("Stanford University", "stanford.edu", "private", "Stanford", "CA")
    codes = {x[0] for x in db.execute("select code from program where institution_id=%s", (iid,))}
    assert codes == {"all", "11", "14", "26", "27", "54"}
    assert db.execute("select field_code from program where institution_id=%s and code='11'", (iid,)).fetchone()[0] == "cs"
    req = db.execute("""select r.requirement from admission_requirement r join program p on p.id=r.program_id
                        where p.institution_id=%s and r.year=2024""", (iid,)).fetchone()[0]
    assert req["sat"]["total"] == {"p25": 1510, "p75": 1580} and req["act"]["composite"] == {"p25": 34, "p75": 35}
    rate = db.execute("""select s.admission_rate, s.admitted_count from admission_stat s join program p on p.id=s.program_id
                         where p.institution_id=%s and s.year=2024 and s.pathway='us_freshman'""", (iid,)).fetchone()
    assert float(rate[0]) == 0.0361 and rate[1] is None
    costs = dict(db.execute("select residency, tuition from cost where institution_id=%s and year=2024", (iid,)).fetchall())
    assert costs == {"local": 68544, "out_of_state": 68544}
    st = db.execute("select student_size, completion_rate, median_earnings from institution_stat where institution_id=%s and year=2024", (iid,)).fetchone()
    assert st == (7554, Decimal("0.9164"), Decimal("125340"))

def test_no_requirement_when_scores_missing_but_rate_kept(db, httpx_mock):
    ...
    iid = db.execute("select id from institution where scorecard_id=900001").fetchone()[0]
    assert db.execute("select count(*) from admission_requirement r join program p on p.id=r.program_id where p.institution_id=%s", (iid,)).fetchone()[0] == 0
    assert db.execute("select count(*) from admission_stat s join program p on p.id=s.program_id where p.institution_id=%s", (iid,)).fetchone()[0] == 3
    assert db.execute("select count(*) from institution_stat where institution_id=%s", (iid,)).fetchone()[0] == 3

def test_null_url_and_domain_collision_do_not_merge(db, httpx_mock):
    # 先放一筆 Hipo 的 US 學校 domain='stanford.edu'（無 scorecard_id）→ 應被 Stanford 連結，而不是新增一列
    # 另外先插入一筆 US institution domain='testoptional.edu' 且 scorecard_id=123（別校）→ 900001 必須新增 domain 'testoptional.edu#900001'
    ...
    assert db.execute("select count(*) from institution where domain='stanford.edu'").fetchone()[0] == 1
    assert db.execute("select scorecard_id from institution where domain='stanford.edu'").fetchone()[0] == 243744
    assert db.execute("select domain from institution where scorecard_id=900001").fetchone()[0] == "testoptional.edu#900001"
    assert db.execute("select domain from institution where scorecard_id=900002").fetchone()[0] == "scorecard#900002"

def test_rerun_is_idempotent(db, httpx_mock):
    # 相同 mock 跑兩次（is_reusable=True）
    ...
    for table in ("institution", "program", "admission_stat", "admission_requirement", "cost", "institution_stat"):
        assert counts_after_first[table] == counts_after_second[table]

def test_limit_stops_early_and_http_error_fails(db, httpx_mock):
    # limit=1 → rows_written == 1；另一案例頁面回 429 → status failed 且 error 含 "429"
    ...
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `cd pipeline && uv run pytest tests/test_scorecard_job.py -v`
Expected: FAIL，`ModuleNotFoundError: collegedata.jobs.scorecard`。

- [ ] **Step 3: 實作 `pipeline/src/collegedata/jobs/scorecard.py`，更新 `sources.yaml` 與 `runner._register_jobs`**

依 Interfaces。`requirement` 以 `psycopg.types.json.Jsonb` 寫入（同 UAC job）。`upsert_institution` 的三段規則各自一條 SQL，不要用 `on conflict (country_code, domain)`（那會把分校合併）。

- [ ] **Step 4: 執行測試確認通過**

Run: `cd pipeline && uv run pytest -v`
Expected: 全部 PASS。

- [ ] **Step 5: 真實 API 煙霧測試（需要金鑰）**

若環境有 `SCORECARD_API_KEY`（向使用者索取，或先略過並在報告中註明），對本機測試庫執行：
```bash
cd pipeline && DATABASE_URL=postgresql://localhost/collegedata_test uv run python -c "
from collegedata.db import connect; from collegedata.jobs.scorecard import ScorecardJob; from collegedata.runner import run_job
with connect() as c: print(run_job(ScorecardJob(limit=5), c)); c.commit()"
```
Expected: `status='success'`，`rows_written=5`；`select count(*) from program where code='all'` 為 5。沒有金鑰則跳過，並在 ledger 記「未做真實 API 驗證」。

- [ ] **Step 6: Commit**

```bash
git add pipeline/src/collegedata/jobs/scorecard.py pipeline/src/collegedata/runner.py pipeline/config/sources.yaml pipeline/tests/test_scorecard_job.py
git commit -m "feat(scorecard): weekly College Scorecard job (institutions, programs, SAT/ACT ranges, costs, stats)"
```

### Task 4: Hipo 不得覆寫其他來源已充實的學校

**Files:**
- Modify: `pipeline/src/collegedata/jobs/hipo.py:UPSERT_SQL`
- Test: `pipeline/tests/test_hipo.py`

**Interfaces:**
- Consumes: 計畫 1 的 `upsert_institutions(conn, records, source_id, source_url) -> int`（簽名不變）。
- Produces: 行為改為「`on conflict (country_code, domain) do update ... where institution.source_id = excluded.source_id`」：只有該列仍由 Hipo 擁有時才更新；由 Scorecard／UAC 建立或接手的列保持不動。回傳值仍計入每筆有 domain 的紀錄（處理筆數，不是更新筆數）。

- [ ] **Step 1: 在 `pipeline/tests/test_hipo.py` 加失敗測試**

```python
def test_does_not_overwrite_rows_owned_by_other_sources(db):
    hipo = ensure_source(db, "hipo"); sc = ensure_source(db, "scorecard")
    upsert_institutions(db, FIX, hipo, "http://x")
    db.execute("update institution set name_en='Stanford University', source_id=%s, scorecard_id=243744 where domain='stanford.edu'", (sc,))
    assert upsert_institutions(db, FIX, hipo, "http://y") == 3
    row = db.execute("select name_en, source_id, source_url from institution where domain='stanford.edu'").fetchone()
    assert row == ("Stanford University", sc, "http://x")
    assert db.execute("select source_url from institution where domain='ntu.edu.tw'").fetchone()[0] == "http://y"
```
（`hipo_sample.json` 已含 `stanford.edu` 這筆。）

- [ ] **Step 2: 執行測試確認失敗**

Run: `cd pipeline && uv run pytest tests/test_hipo.py -v`
Expected: 新測試 FAIL（name_en 被覆寫回 Hipo 值）。

- [ ] **Step 3: 修改 `UPSERT_SQL` 加 `where institution.source_id = excluded.source_id`**

- [ ] **Step 4: 執行測試確認通過**

Run: `cd pipeline && uv run pytest tests/test_hipo.py tests/test_uac_job.py -v`
Expected: 全部 PASS。

- [ ] **Step 5: Commit**

```bash
git add pipeline/src/collegedata/jobs/hipo.py pipeline/tests/test_hipo.py
git commit -m "fix(hipo): never overwrite institutions owned by richer sources"
```

### Task 5: OpenAlex 強化：全失敗即失敗、記錄已查過的學校

**Files:**
- Create: `supabase/migrations/0004_openalex_checked_at.sql`
- Modify: `pipeline/src/collegedata/jobs/openalex.py`
- Test: `pipeline/tests/test_openalex.py`

**Interfaces:**
- Consumes: 計畫 1 的 `OpenAlexJob`（建構子簽名不變）。
- Produces:
  - `institution.openalex_checked_at timestamptz`（migration 0004）。
  - `OpenAlexJob.run`：每所學校處理完（不論有無配對）都 `update institution set openalex_checked_at = now()`；`SELECT_SQL` 排序改為「`openalex_checked_at is null` 的優先（依 id），其次 `openalex_checked_at` 最舊者」，不再以 `openalex_id is null` 排序，永遠配不到的學校因此會輪替而不是每次卡在最前面。
  - `run` 結束時若 `attempted >= 1` 且 `succeeded == 0`（`succeeded` 指 `_process` 正常返回，含「無信心配對回 0」；失敗指 HTTP 非 429 或傳輸錯誤），raise `OpenAlexAllFailed(f"{attempted} attempted, 0 succeeded")`；遇 429 停止不算失敗。

- [ ] **Step 1: 在 `pipeline/tests/test_openalex.py` 加失敗測試**

```python
def test_all_requests_failing_marks_job_failed(db, httpx_mock):
    upsert_institutions(db, HIPO, ensure_source(db, "hipo"), "http://x")
    httpx_mock.add_response(url=URL_RE, status_code=500, is_reusable=True)
    r = run_job(OpenAlexJob(client=httpx.Client()), db)
    assert r.status == "failed" and "OpenAlexAllFailed" in r.error

def test_checked_at_set_and_unchecked_come_first(db, httpx_mock):
    upsert_institutions(db, FIX_ALL, ensure_source(db, "hipo"), "http://x")   # 3 所
    db.execute("update institution set openalex_checked_at = now() - interval '1 day' where domain='ntu.edu.tw'")
    httpx_mock.add_response(url=URL_RE, json=NTU, is_reusable=True)
    run_job(OpenAlexJob(client=httpx.Client(), limit=2), db)
    assert db.execute("select openalex_checked_at from institution where domain='ntu.edu.tw'").fetchone()[0] < \
        db.execute("select min(openalex_checked_at) from institution where domain<>'ntu.edu.tw'").fetchone()[0]
```
（`FIX_ALL` = 整個 `hipo_sample.json`；`NTU` mock 對所有學校回同一結果即可，第二、三所會因 `openalex_id` 已屬他校而跳過，這不影響 `openalex_checked_at`。）

- [ ] **Step 2: 執行測試確認失敗**

Run: `cd pipeline && uv run pytest tests/test_openalex.py -v`
Expected: 兩個新測試 FAIL。

- [ ] **Step 3: 寫 migration 0004、修改 `openalex.py`**

`0004_openalex_checked_at.sql`：`alter table institution add column openalex_checked_at timestamptz; create index institution_openalex_checked_at_idx on institution (openalex_checked_at nulls first);`

- [ ] **Step 4: 執行全部測試確認通過**

Run: `cd pipeline && uv run pytest -v`
Expected: 全部 PASS。

- [ ] **Step 5: Commit**

```bash
git add supabase/migrations/0004_openalex_checked_at.sql pipeline/src/collegedata/jobs/openalex.py pipeline/tests/test_openalex.py
git commit -m "fix(openalex): fail when every request fails; rotate by openalex_checked_at"
```

### Task 6: 排程、金鑰與文件

**Files:**
- Modify: `.github/workflows/pipeline.yml`
- Modify: `docs/deploy.md`、`README.md`、`pipeline/.env.example`
- Modify: `設計文件.md` 6.1 表格（College Scorecard 那列的更新頻率欄保持「每週」，備註「每週四」）
- Modify: `藍圖.md` 討論紀錄（加一行：計畫 2 完成，摘要本計畫的三個裁定：整校 program `code='all'`、美國國際生學費以外地生代替、Hipo 不覆寫其他來源）

**Interfaces:**
- Produces: `pipeline.yml` 新增 cron `0 6 * * 4`（每週四 06:00 UTC）→ `scorecard`；`workflow_dispatch` 的 `job` 選項加 `scorecard`；`Run pipeline job` 步驟 env 加 `SCORECARD_API_KEY: ${{ secrets.SCORECARD_API_KEY }}`。

- [ ] **Step 1: 修改 `pipeline.yml`**

schedule 加第四條 cron、`case` 加 `"0 6 * * 4") JOB=scorecard ;;`、choice 加 `scorecard`、env 加 `SCORECARD_API_KEY`。

- [ ] **Step 2: 驗證 workflow 語法**

Run: `python3 -c "import yaml,sys; d=yaml.safe_load(open('.github/workflows/pipeline.yml')); print([c['cron'] for c in d[True]['schedule']], d[True]['workflow_dispatch']['inputs']['job']['options'])"`（PyYAML 把 `on` 讀成 `True`）
Expected: 四條 cron 含 `0 6 * * 4`，options 含 `scorecard`。

- [ ] **Step 3: 更新文件**

`docs/deploy.md`：步驟 4 的 secrets 加第三個 `SCORECARD_API_KEY`（到 <https://api.data.gov/signup/> 填 email 立即取得，免費，每小時 1,000 次）；步驟 5 的手動初始載入順序改為 `hipo` → `scorecard` → `uac` → `openalex`；排程表加 `scorecard` 一列（每週四 06:00 UTC；每次重抓最新三個資料年、約 16 個 API 請求）。`README.md` 目錄結構不變，「本機開發」下加一句：跑 Scorecard 需 `SCORECARD_API_KEY`。`.env.example` 加 `SCORECARD_API_KEY=` 與 `OPENALEX_API_KEY=`（後者計畫 1 漏列）。`設計文件.md`、`藍圖.md` 依 Files 所述更新。

- [ ] **Step 4: 執行全部測試確認通過**

Run: `cd pipeline && uv run pytest -v`
Expected: 全部 PASS。

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/pipeline.yml docs/deploy.md README.md pipeline/.env.example 設計文件.md 藍圖.md
git commit -m "ci(scorecard): weekly Thursday schedule, API key secret, deploy docs"
```

---

## 留給計畫 3 的約定（ledger 也要記）

- 美國校級錄取資料掛在 `program.code = 'all'` 的整校 program 上；CIP 科系 program（`code` 為兩碼）本身沒有錄取資料，網站顯示科系卡片時要用同校 `code='all'` 的 `admission_requirement`／`admission_stat`。
- `institution.domain` 含 `#` 的列是 Scorecard 為分校或無網址學校建立的；網站連結一律用 `web_url`，不要用 `domain` 組網址。
- 美國國際生學費：`cost` 只有 `local`、`out_of_state`；網站對國際生顯示 `out_of_state` 並標示「以州外學費估計」。
- 沒有 program（`code='all'` 或台灣系組）的 `institution` 不在網站顯示（計畫 1 已記）。
- 台灣系組的 `field_code` 仍為 NULL：以 `name_zh` 關鍵字對應到 `field` 表的工作放在計畫 3 開頭（或 1b）。

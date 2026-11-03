# 計畫 2 執行 ledger（美國 College Scorecard 管線）

執行方式：superpowers subagent-driven development；分支 `plan-2-us-scorecard`（自 `plan-1-foundation` 7dbc0a4 分出），完成於 ed71c7e，73 個測試通過。以下為控制者在執行中所做的裁定、各 Task 審閱後暫擱的小問題、以及留給計畫 3 的約定。原始紀錄逐行保留（英文）。

## 留給計畫 3 的約定（網站）

- 美國校級錄取資料掛在 `program.code = 'all'` 的整校 program；CIP 科系 program（`code` 為兩碼）沒有自己的錄取資料，顯示科系卡片時用同校 `code='all'` 的 `admission_requirement`／`admission_stat`。
- `institution.domain` 含 `#` 的列是 Scorecard 為分校或無網址學校建立的；連結一律用 `web_url`，不要用 `domain` 組網址。
- 美國國際生學費：`cost` 只有 `local`、`out_of_state`；對國際生顯示 `out_of_state` 並標示「以州外學費估計」。
- 所有 Scorecard 寫入列的 `source_url` 是該校公開頁 `https://collegescorecard.ed.gov/school/?<scorecard_id>`（最終審閱裁定，取代 4 KB 的請求網址）。
- 沒有 program 的 `institution` 不顯示（計畫 1 已記）；OpenAlex 也只處理有 program 的學校。
- 歷史年份不會自動刪除（Scorecard 與考分會皆同）：網站查詢時只取最近三年（設計文件 6.1.1）。
- 從 Scorecard 篩選條件掉出的學校（停辦、不再有錄取率）資料會留在庫中：網站可依 `fetched_at` 過舊隱藏。
- 考分會接手的 Hipo 列仍是 `source_id = hipo`（UAC 只改 `name_zh`），Hipo 每週仍會刷新其 `name_en`；兩者由 CSV 保持一致，暫不處理。
- 台灣系組的 `field_code` 仍為 NULL：以 `name_zh` 關鍵字對應 `field` 表的工作放在計畫 3 開頭（或 1b）。
- Scorecard 科系旗標值 2（只提供遠距）目前視為未開設；首次實跑後再決定。
- 首次實跑檢查清單在 `docs/deploy.md`；本次執行環境沒有 `SCORECARD_API_KEY`，**未做真實 API 驗證**。

## 原始 ledger

### SDD ledger — plan: docs/superpowers/plans/2026-10-29-02-us-scorecard-pipeline.md
Branch plan-2-us-scorecard, forked from plan-1-foundation at 7dbc0a4; plan committed at 7eeb54b (BASE for Task 1).
Spec: 設計文件.md (reachable). Prior ledger: docs/superpowers/plans/2026-10-29-01-foundation-tw-pipeline-ledger.md.

## Pre-flight scan
| Pair / task | Produces vs consumes | Finding |
|---|---|---|
| T1→T2 | field.code list (19) vs scorecard_programs.yaml field_code values | all 19 codes used by the map exist; clean |
| T1→T3 | institution.scorecard_id/city/region, program.code partial unique, admission_stat.admission_rate + nullable admitted_count, institution_stat(student_size, completion_rate, median_earnings, currency) | T3 tests use exactly these names; clean |
| T2→T3 | fields_param/parse_school/load_program_map/School/YearStats | program_keys order (computer, engineering, biological, mathematics, history) matches yaml order; fields count 7+36+38=81; clean |
| T3↔T4 | Scorecard rule 2 sets source_id=scorecard on adopted Hipo rows; Hipo update guarded by source_id | consistent. Note: UAC-adopted Hipo rows keep source_id=hipo (UAC only sets name_zh), so Hipo can still refresh their name_en — acceptable, Hipo and UAC name_en agree by CSV; ledgered for plan 3 |
| T1↔T5 | migrations 0003 and 0004 both alter institution | separate files, conftest applies sorted; clean |
| T5 vs existing tests | new SELECT order (openalex_checked_at nulls first, then id) | existing test_skips_openalex_id_owned_by_other_institution relies on old order (`openalex_id is null` first) with limit=1 — will break. Ruling: implementer updates that test to set `openalex_checked_at = now()` on the already-linked row so the unlinked one is selected — the test's intent (skip id owned by another institution) is unchanged — cost if wrong: none, test-only |
| T6 | yaml check command uses system python3 | Ruling: run it as `cd pipeline && uv run python -c ...` with the path adjusted — cost if wrong: none |
| T3 Step 5 | live smoke needs SCORECARD_API_KEY | not available this session; skip and ledger "未做真實 API 驗證" (plan allows) |
| T2 Step 1 | DEMO_KEY fixture capture, 10/hr | controller exhausted DEMO_KEY ~21:00 local; budget resets hourly — implementer may capture Stanford if allowed, else hand-write from the verified values in the brief |
Each task's own text agrees with itself (tests vs interfaces checked above). No plan-mandated rubric defects found.

## Progress
- Task 1: ⚠️ commit trailer verified by controller (git log); test evidence accepted from report.
- Task 1: minor (deferred): FK test accepts any FK failure; RLS/policy tests not extended to field/institution_stat; institution_stat NOT NULL provenance columns unasserted.
- Task 1: complete (commits 7eeb54b..9d2f8fb, review clean)
- Task 2: ⚠️ resolved by controller: Stanford fixture values equal the plan's verified API facts (checked against plan text); db fixture/field table are Task 1 (reviewed); trailer verified. Fixture is hand-written (DEMO_KEY 429) — allowed by plan; flags int 0/1 confirmed by controller's earlier live probe.
- Task 2: minor (deferred): web_url not stripped of whitespace; port kept in domain; unknown ownership → 'private' silently; KeyError on malformed record untested; coverage gaps (one-sided percentile, scheme-present URL, ownership 1, main_campus 0, non-first years); CONFIG_DIR parents[3] assumes source layout (same as uac.py).
- Task 2: complete (commits 9d2f8fb..f7f0d65, review clean)
- Task 3: ⚠️ resolved by controller: fixture metadata.total=3 → single page (checked fixture); trailer verified; live API smoke skipped (no SCORECARD_API_KEY) — 未做真實 API 驗證, must be done by user after adding the secret (deploy.md step).
- Task 3: review found 1 Important: no 1-second wait before the runner's retry request (self._requested reset in run()). Fix round 1 dispatched to original implementer.
- Task 3: minor (deferred): missing API key → requests sent with empty api_key, fails via HTTP error not a clear message; branch campus with lower id than main campus sharing a domain takes the plain domain (known limitation, ledger for plan 3: links use web_url, not domain); limit=0 processes one school; rerun test doesn't assert fetched_at refresh; 429 test doesn't assert rollback.
- Note: commit 6b0eddc (藍圖.md, cac.edu.tw investigation notes) landed on this branch from another session; docs-only, out of plan scope.
- Task 3: fix round 1/5 (1 addressed, 0 open — retry spacing fixed, recording-sleep test added; commits e7d856e..c4321b1)
- Task 3: complete (commits f7f0d65..c4321b1, review clean)
- Task 4: ⚠️ test evidence accepted from report. Ruling: commit trailer names "Claude Haiku 5.5" (model that did the work) — left as is, cosmetic, same as plan 1 ruling — cost if wrong: none.
- Task 4: minor (deferred): new test's name_en assertion is weak (fixture name equals the set value); web_url/fetched_at preservation not asserted.
- Task 4: complete (commits c4321b1..6527ee7, review clean)
- Task 5: ⚠️ resolved by controller: runner records exceptions as "TypeName: message" (runner.py, plan 1 I7 ruling) so OpenAlexAllFailed reaches fetch_log.error; trailer verified.
- Task 5: minor (deferred): all-failed test uses one institution only (mixed success/failure case covered implicitly); ordering test doesn't assert the two unchecked rows were stamped directly.
- Task 5: complete (commits 6527ee7..78fb2ae, review clean)
- Task 6: ⚠️ trailer verified by controller; branch name in 藍圖.md is correct (plan-2-us-scorecard).
- Task 6: minor (deferred): deploy.md SCORECARD_API_KEY bullet indented 3 spaces vs 4 (cosmetic).
- Task 6: complete (commits 78fb2ae..a38c2aa, review clean)
- ALL TASKS COMPLETE at a38c2aa. Final whole-branch review dispatched (opus) over 7eeb54b..a38c2aa.

## Final review (opus) — verdict: With fixes. I1–I5 + triaged ledger items → ONE fix dispatch (base a38c2aa).
- Ruling (I1): redact api_key from any error text; raise a clear ScorecardConfigError-style message before any request when the key is empty — spec: secret never leaves the secret store. Cost if wrong: none.
- Ruling (I2): wrap each page's writes in psycopg pipeline mode (`with conn.pipeline():`) to cut round-trips; deploy.md step 1 tells the owner to choose a US region (e.g. East US) — Cost if wrong: pipeline mode quirks caught by the suite; worst case revert to plain execution.
- Ruling (I3): source_url for every Scorecard row becomes the canonical school page `https://collegescorecard.ed.gov/school/?<scorecard_id>` (openable by a visitor, unique per school, no key, ~45 bytes) instead of the 4 KB paging URL. Deviates from plan Task 3 text ("request URL minus api_key") and its test assertion; spec 5.1.10 (source must be shown to users) wins. Cost if wrong: provenance is less exact (no field list) — the request shape is in code.
- Ruling (I4): after paging (when ≥100 schools processed), fail with ScorecardDataError if for the latest year fewer than 30% of processed schools have any SAT/ACT range or fewer than 50% have in-state tuition; values outside rate 0..1 / SAT 200..800 / ACT 1..36 are stored as NULL with a warning. Spec 6.4 validation requirement; plan defect. Cost if wrong: a legitimate low-coverage year opens one Issue.
- Ruling (I5): OpenAlex SELECT_SQL restricted to institutions with ≥1 program (`exists (select 1 from program ...)`); existing openalex tests seed a program row via a helper. Matches plan-3 convention (only institutions with programs are shown) and saves budget. Cost if wrong: an institution with strengths but no programs is never refreshed — none are shown anyway.
- Ruling (triage): fix now — T1 RLS/policy tests cover every public table; T3 missing-key clear error (with I1); M6 deploy.md request count wording; deploy.md gains a first-live-run checklist. M7 (committed plan-2 ledger) done by controller after the fix wave. M1 (flag value 2 = distance-only programs) — Ruling: keep `== 1`; add to first-run checklist. M2/M3/M4/M5 deferred to plan 3 ledger. Cost if wrong: minor.
- Final fix wave: 4 commits a38c2aa..ed71c7e (F1–F7); fixer reports 73 passed, no warnings. Controller re-ran full suite: 73 passed.
- Final fix wave re-review (opus): all F1–F7 ADDRESSED, no new Critical/Important breakage.
- Residual minors (deferred): range test `all(rate is None)` passes on empty set (should assert == []); deploy.md checklist item 4 SQL lacks a year filter; redundant copy_remove_param before copy_with(query=None); ScorecardConfigError is retried once by the runner (harmless, no requests); test_anon_read_policies keeps one policy per table.
- PLAN 2 COMPLETE at ed71c7e — pending: committed ledger (this file copied to docs/superpowers/plans/), push + PR (user decides), live first run after SCORECARD_API_KEY secret.

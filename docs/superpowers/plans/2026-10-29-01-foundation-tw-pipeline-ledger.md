# SDD ledger — plan: docs/superpowers/plans/2026-10-29-01-foundation-tw-pipeline.md

Spec: 設計文件.md (reachable). Branch: plan-1-foundation (from main @ ee1ec82).

## Setup rulings
- Ruling: work in-place on branch `plan-1-foundation` instead of a git worktree — the repo was empty at start and the user's rule pins all files to this folder; a sibling worktree path would violate it — cost if wrong: none beyond losing isolation from an otherwise empty main.
- Ruling: Task 1 Step 1 (`git init -b main`) done by controller before dispatch (initial commit ee1ec82 holds docs); implementer starts at Step 1's .gitignore content — cost if wrong: none.
- Ruling: Task 8 Step 6 (`gh repo create --public --push`) is a publish; implementer skips it, controller asks the user at finish — cost if wrong: one extra question.
- Ruling: Homebrew PostgreSQL install touches the machine outside the folder; user approved the plan that states it explicitly — proceed — cost if wrong: brew uninstall postgresql@17.

## Pre-flight scan
| Pair / Task | Produces vs consumes | Finding |
|---|---|---|
| T1↔T2 | conftest applies supabase/migrations/*.sql; T2 creates 0001_init.sql | OK; T1 smoke requires fixture to tolerate empty migrations dir (stated) |
| T2↔T3 | fetch_log(job,started_at,finished_at,status,rows_written,error), source(code,name,url,license) | OK; T3 test inserts source(code,name,url) — url NOT NULL satisfied |
| T3↔T4 | Job protocol, ensure_source, REGISTRY; institution unique(country_code,domain) | OK |
| T4↔T6 | institution rows via Hipo (name_zh NULL); CSV name_zh→domain; fixture NTU domain ntu.edu.tw | OK; CSV must include 國立臺灣大學,ntu.edu.tw |
| T5↔T6 | UacRow fields; subjects tuples → [{subject,weight}] | OK |
| T4↔T7 | institution.name_en/country_code → openalex_id/ror_id; strength unique(institution_id,topic_id) | OK |
| T3↔T8 | CLI exit 0/1 | OK |
| T3 self | row-count guard vs first run (no prior success) | OK, guard only when prior success exists |
| T4 self | regex URL match vs httpx encoding of ", " | OK (`Taiwan%2C%20...` matches `Taiwan.*`) |
| T7 self | regex with lookaheads for filter+api_key | OK |
| T8 self | Step 6 publish | ruled above |

## Progress
- Task 1: ⚠️ commit trailer verified by controller (git log -1 shows Co-Authored-By line); test evidence accepted from report.
- Task 1: minor (deferred): conftest drops `public` schema on whatever TEST_DATABASE_URL points to — add guard (db name ends with `_test` or host localhost).
- Task 1: minor (deferred): .env.example/README mention `.env` but nothing loads it yet.
- Task 1: minor (deferred): setup-local-db.sh `until pg_isready` has no retry cap.
- Task 1: complete (commits ee1ec82..faf1471, review clean)
- Task 2: ⚠️ commit trailer verified by controller; db fixture is Task 1's (reviewed); test evidence accepted from report.
- Task 2: minor (deferred): test_schema only checks one NOT NULL column; parametrise over all data tables × (source_id, source_url, fetched_at).
- Task 2: minor (deferred): no tests for indexes/unique constraints.
- Task 2: complete (commits faf1471..5d28f73, review clean)
- Task 3: ⚠️ schema columns (Task 2), console script (Task 1), trailer (verified by controller) — all resolved.
- Task 3: minor (deferred): RowCountDropped failure is retried (re-runs fetch); should skip retry.
- Task 3: minor (deferred): error string empty for message-less exceptions; use type name prefix.
- Task 3: minor (deferred): no CLI exit-code/commit tests; no ensure_source test; unknown source code raises bare KeyError.
- Task 3: complete (commits 5d28f73..7d6fcdd, review clean)
- Task 4: ⚠️ institution unique constraint exists (Task 2 reviewed); real run counts TW 86 / US 2349 accepted from report.
- Task 4: minor (deferred): internally created httpx.Client never closed.
- Task 4: minor (deferred): URL matchers loose (`Taiwan.*`); no tests for empty-domains skip / NULL web_url.
- Task 4: minor (deferred): lazy import in runner._register_jobs may be unnecessary.
- Task 4: complete (commits 7d6fcdd..15ccf05, review clean)
- Ruling (pre-Task 6): Hipo's Taiwan list is stale (old names/domains, e.g. kmc.edu.tw for 高醫) and lacks 康寧/佛光/馬偕/金門. Task 6 changed: CSV gains `name_en` and uses current real domains; UacJob creates missing institutions itself (source=uac) instead of failing. Plan file and task-6 brief regenerated. Cost if wrong: stale Hipo duplicates for TW schools whose domain changed (e.g. Kaohsiung Medical College kmc.edu.tw vs 高雄醫學大學 kmu.edu.tw) remain as separate institution rows with no programs — the web plan must hide/merge institutions that have no programs or stats. Ledgered as known data-quality item for plan 3.
- Draft CSV (60 rows) prepared by controller at scratchpad/tw_institutions_draft.csv for the implementer to verify.
- Task 5: ⚠️ fixture page count verified by controller (2 pages); test evidence accepted from report.
- Task 5: minor (deferred): row_from_cells bare IndexError on short rows; int/float errors lack row context.
- Task 5: complete (commits 15ccf05..6196f56, review clean)
- Task 6: ⚠️ items resolved by controller: `-----` handling is Task 5 (reviewed, tested); unique constraints are Task 2 (reviewed); runner rollback is Task 3 (reviewed); CSV⊇PDF check accepted from report.
- Task 6: minor (deferred): unknown-school test only checks one name and no row-count assertions; idempotence test only checks admission_stat.
- Task 6: minor (deferred): program upsert sets name_en=NULL on conflict (would clobber future English names); existing name_zh overwritten when different.
- Task 6: minor (deferred): years matching nothing returns 0 silently; default httpx.Client never closed; unused imports in test.
- Task 6: complete (commits 26d68f2..1a0e8f5, review clean)
- Task 7: Ruling: reviewer's Important finding (api_key persisted in strength.source_url) conflicts with the controller's own dispatch note ("source_url = str(resp.request.url)"). Spec wins: provenance needs a reproducible URL, never a secret. source_url must be the request URL with the api_key parameter removed. Cost if wrong: none (URL without key is still a valid provenance link).
- Task 7: fix round 1/5 (1 addressed, 0 open — api_key stripped from source_url; commits 0700e26..30704ce)
- Task 7: ⚠️ live API path verified by controller run (limit=5: 40 rows, 4 linked, 1 skipped with warning).
- Task 7: minor (deferred): tests lack ror_id/source_url/fetched_at/topic ordering assertions and an idempotency rerun; empty-results case untested; default httpx.Client not closed; runner imports unsorted.
- Task 7: complete (commits 1a0e8f5..30704ce, review clean)
- Task 8: ⚠️ resolved by controller: 設計文件.md at root exists; pipeline/uv.lock committed (Task 1); CLI contract from Task 3; suite needs only TEST_DATABASE_URL.
- Task 8: minor (deferred): `labels: ['pipeline-failure']` not in spec, label may not exist.
- Task 8: minor (deferred): Issue body says "scheduled" even for manual dispatch.
- Task 8: minor (deferred): no timeout-minutes / concurrency on pipeline job.
- Task 8: minor (deferred, OPERATIONAL): GitHub disables scheduled workflows in public repos after 60 days without repo activity — threatens the "fully automatic" goal silently; deploy guide should warn and/or a keepalive be added. Final review to triage.
- Task 8: minor (deferred): README dropped .env.example / PATH notes.
- Task 8: complete (commits 30704ce..9cbee42, review clean)

## Final review (opus) — verdict: With fixes. Findings C1, I1–I7 + triaged minors → ONE fix dispatch.
- Ruling (C1): OpenAlex job becomes incremental — bounded batch per run (default 800, CLI/env override), never-matched first then oldest strength.fetched_at; per-institution savepoint so one HTTP error only skips that institution; stop cleanly on 429; delete-then-insert strengths per institution; job opts out of the 50% row-count guard via `row_count_guard = False`; cron changed from quarterly to monthly (`0 4 2 * *`) so a full cycle (~2,435 institutions) finishes within a quarter. Deviation from plan Task 7 text ("quarterly", all-at-once). Cost if wrong: strengths refresh more slowly than planned; nothing lost.
- Ruling (I1+I2): add `keepalive.yml` (weekly): re-enable `pipeline.yml` and itself via GitHub API (`permissions: actions: write`), and run `select 1` against DATABASE_URL to keep the Supabase free project awake. Document in deploy.md. Cost if wrong: one extra tiny weekly workflow.
- Ruling (I3): UAC year URLs derived from pattern `https://www2.uac.edu.tw/{roc}data/{roc}_result_school_data.pdf` for current ROC year and the two before; `uac_years.yaml` becomes an override list; newest-year 404 after the cron date = failure, older-year 404 = warning. Implementer must verify 114/113 live and record real URLs as overrides if the pattern differs. Cost if wrong: an unneeded Issue once a year.
- Ruling (I4): conftest refuses to reset unless current_database() ends with `_test`.
- Ruling (I5): skip (warn) when the matched openalex_id already belongs to another institution; add partial unique index on institution(openalex_id).
- Ruling (I6): new migration 0002: enable RLS on all tables + anon SELECT policies on data tables (not fetch_log). Pipeline connects as postgres and bypasses RLS.
- Ruling (I7): error text = `TypeName: message`; RowCountDropped not retried.
- Ruling (M13): field_name NULL → 'Unknown'. (T6) program upsert no longer nulls name_en on conflict.
- Deferred to later plans (reviewer-triaged "leave for later"): all other minors; M1 (Hipo HTTPS GitHub source) needs its own ruling later; M9 (馬偕 English name) unverified, left.
- Fix wave base: 9cbee42.
- Final fix wave: 8 commits 9cbee42..70dc075 (F1–F8); fixer reports 46 tests passing, 114 (1787 rows) and 113 (1839 rows) UAC PDFs load live. Scoped re-review dispatched.
- Fixer concerns ledgered: (a) its commit trailers say "Claude Opus 5.5" (model that did the work) instead of Fable 5.1 — Ruling: left as is, cosmetic; (b) 2 CSV rows added (中華大學, 馬偕醫學院) for older PDFs; (c) never-matching OpenAlex institutions stay first in the batch every run — deferred to plan 2 (add an `openalex_checked_at` column); (d) UAC year tests depend on today's date, break in 2029 — deferred; (e) anon grants on Supabase assumed, not tested locally — deferred.
- Final fix wave re-review: all F1–F8 ADDRESSED, no new Critical/Important breakage. Controller re-ran full suite: 46 passed, no warnings; tree clean at 70dc075.
- Parked — Ruling: with row_count_guard off, an OpenAlex run where every request fails (non-429) or the first is 429 ends as "success" with 0 rows and opens no Issue. Real but not load-bearing for plan 1; plan 2 should make the job fail when 0 institutions succeed out of ≥1 attempted. Cost if wrong: an OpenAlex outage goes unnoticed until the next month's run.
- Parked — Ruling: UAC 404 check uses position in the filtered list, not "newest configured year"; only matters for manual `years=` filters. Left.
- Parked — Ruling: keepalive cannot re-enable itself once disabled; weekly cadence makes it unlikely; left, documented in deploy.md.
- PLAN 1 COMPLETE at 70dc075 — pending: publish to GitHub (controller asks user), merge to main.
- Post-plan user requirement: all jobs weekly. Crons changed to 0 3 * * 1 / 0 4 * * 2 / 0 5 * * 3; spec 6.1/6.4, deploy.md, plan Task 8 updated. Committed by controller (docs+cron only, no code).

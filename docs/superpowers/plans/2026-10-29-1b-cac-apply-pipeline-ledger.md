# SDD ledger — plan: docs/superpowers/plans/2026-10-29-1b-cac-apply-pipeline.md

Spec: docs/superpowers/specs/2026-10-29-cac-apply-design.md (reachable). Worktree: .claude/worktrees/plan-1b-cac, branch plan-1b-cac, base a38c2aa (plan-2-us-scorecard). Test DB: TEST_DATABASE_URL=postgresql://localhost/collegedata_1b_test.

## Pre-flight scan (2026-10-29)

| Pair / task | Produces vs consumes | Found |
|---|---|---|
| T1 → T5, T7 | `CacFetcher(client, min_interval, sleep, clock)`, `get/post/download`, `BusyError` | consistent; T5 busy test needs `download` to raise BusyError on busy content — added to T1 interface |
| T2 → T5, T7 | `admission_stat.sieve`, `cac_fetch`, source `cac`, CSV +5 schools | consistent |
| T3 → T4 | grid/normalisation functions, `SieveLevel` | T4 test asserts `multipliers` keys include 學測科目組合 — T3 dict spec matches |
| T4 → T5 | `SieveRow`, `SieveParseResult`, `parse_sieve_image(png, school_code, ocr=None)` | T5 fake parser uses same positional field order |
| T5 → T7 | `cac_common`: `Budget`, `done_units`, `record_unit`, `upsert_program`, `merge_requirement`, `finish` | consistent signatures in T7 tests |
| T5 ↔ uac.py | T5 moves `upsert_program` into cac_common and uac.py calls it; T8 edits `year_urls` in uac.py | different regions of uac.py; sequential tasks, no conflict |
| T6 → T7 | `find_system_url`, `parse_total_gsd`, `parse_code_list`, `parse_rules_page`, `RulesPage` | consistent |
| T9 ↔ other sessions | edits 藍圖.md／設計文件.md／docs/deploy.md／README.md in this worktree only; plan-2 session asked others not to edit those files until its Task 6 is done | Ruling: edits happen only in this worktree on branch plan-1b-cac; conflicts resolved at merge time — cost if wrong: a manual merge of a few doc lines |
| T3 self | `test_cell_lines_splits_two_line_cell` depends on a row index | plan tells implementer to verify the index, not loosen the assertion |
| T5 self | pytest-httpx asserts all registered responses requested | tests register only used URLs; reusable where runner retries |

No contradictions with Global Constraints. Proceeding to Task 1.
- Task 1: dispatched (sonnet), BASE 1a5ada8
- Task 1: ⚠️ resolved by controller: PEM subject/expiry verified with openssl; trailer present; full suite 76 passed.
- Task 1: minor (deferred): resume path (partial buffer + 206, 200-after-partial, 416, BusyError inside download, throttle across retries) has no dedicated tests; `test_download_resumes_after_timeout` misnamed.
- Task 1: minor (deferred): `download` uses iter_raw (no decoding) — consider `Accept-Encoding: identity`; 206 Content-Range start not validated against len(buf).
- Task 1: complete (commits 1a5ada8..8ec9d40, review clean)
- Task 2: dispatched (haiku), BASE 8ec9d40
- Task 2: ⚠️ resolved by controller: trailer present; RLS enable statement present. Ruling: `id bigint generated always as identity` instead of the plan's `serial` accepted (equivalent; cost if wrong: none).
- Task 2: minor (deferred): RLS test counts policies only (should assert relrowsecurity); source test checks only the id.
- Task 2: complete (commits 8ec9d40..0109117, review clean)
- Task 3: dispatched (sonnet), BASE 0109117
- Task 3: controller replaced fixture 115_001_crop.png with the whole first table (4915c77); implementer fix commit aa279fa; review dispatched over 0109117..aa279fa
- Task 3: review: 2 Important (normalize_program_name lacks NFKC and applies simp→trad; parse_sieve_cell regex looser than brief) + pins tighter than brief. Ruling: simp→trad stays out of normalize_program_name — Task 4 applies normalize_text to raw OCR cell text first — cost if wrong: a simplified char in a name slips through (would be caught by golden tests).
- Task 3: minor (deferred): no synthetic test that text strokes are not lines; `_merge` boundaries untested; parse_multiplier accepts NaN/Infinity; last-row sliver edge case; Image.open not closed; test at :293 weak (brief-carried).
- Task 3: fix round 1/5 dispatched (resume implementer), FIX_BASE aa279fa
- Task 3: fix round 1/5 (3 addressed, 0 open — NFKC in normalize_program_name; brief regex + digits-only guard in parse_sieve_cell; dependency floors; commits aa279fa..164880d)
- Task 3: complete (commits 0109117..164880d, review clean)
- Task 4: dispatched (sonnet), BASE 164880d
- Task 4: implementer DONE_WITH_CONCERNS (618060f; 97 passed; OCR repairs: 戲 prefix hack, 浦→無, 水→*, trailing-dot strip); review dispatched (opus) over 164880d..618060f
- Task 4: review (opus): 5 Important — wide line crashes parse (ResizeImgError); unparseable sieve cell silently dropped/renumbered; overflow column silent False; _repair_name fixture hack; misread first-row code absorbed as header. Rulings: 學測科目組合→multipliers / 英聽→thresholds / APCS headers→extra accepted as spec-consistent (cost if wrong: none); name repair kept but tabled + warned, no ink-extent heuristic (cost if wrong: a dropped rare glyph in another school's name passes silently — logged only).
- Task 4: minor (deferred): parse_level accepts level char anywhere; trailing-dot strip guesses; header alias `英`→英聽 exact-match image-specific; extra/base key collisions on duplicate headers; silent group fallback; no fake-engine tests (partly addressed in fix round); redundant OCR of column 0; module ~430 lines (split later if confusion tables grow).
- Task 4: fix round 1/5 dispatched (resume implementer), FIX_BASE 618060f
- Task 4: fix round 1/5 (5 addressed, 0 open; new minor: header loop stops once map_headers succeeds — controller's own over-specification; commits 618060f..63c81c0)
- Task 4: minor (deferred): name-repair and trailing-dot warnings go to log only, not result.warnings.
- Task 4: fix round 2/5 dispatched (drop the map_headers early stop, keep digit rule + 3-row cap), FIX_BASE 63c81c0
- Task 4: fix round 2/5 (1 addressed, 0 open; covering test run by controller: 1 passed; commits 63c81c0..fadbeb5)
- Task 4: minor (deferred): a first data row whose code OCRs with no digit is absorbed into header_texts (may fail map_headers → whole table skipped with warning, visible not silent); no test for that case.
- Task 4: complete (commits 164880d..fadbeb5, review clean)
- Task 5: dispatched (sonnet), BASE fadbeb5
- Task 5: implementer DONE_WITH_CONCERNS (f3dfb0c; 122 passed; no RED evidence; test fixes to brief: parse kw, 4 program names). Ruling: expected program list of 4 is correct (school 002 fake row) — cost if wrong: none. Review dispatched (opus) over fadbeb5..f3dfb0c
- Task 5: review (opus): 2 Important — institution cache survives rolled-back unit savepoint; BusyError outcomes inconsistent (quiet success on busy collegeList, failure+retry on first busy image). Ruling: BusyError rule for both cac jobs = succeeded ≥ 1 → warn and stop (success); succeeded == 0 → re-raise (job fails, Issue) — cost if wrong: one Issue per fully-throttled run (desired signal) and one immediate runner retry against a busy server. Ruling: Budget.exhausted counts processed (done+failed) units — accepted (cost if wrong: none).
- Task 5: minor (deferred): collegeList fetched for every year before the loop even when budget exhausted; budget clock coupling via fetcher._clock; no time-budget test inside run; order of units relies on collegeList HTML order (fixture is sorted); deterministic failures OCR every image twice because of the runner retry.
- Task 5: fix round 1/5 dispatched (resume implementer; items: cache restore, busy rule, rows_skipped on failure, empty parse → failed), FIX_BASE f3dfb0c
- Task 5: fix round 1/5 (4 addressed, 0 open — cache restore; busy rule; rows_skipped recorded; empty parse fails; commits f3dfb0c..a685952)
- Task 5: complete (commits fadbeb5..a685952, review clean)
- Task 6: dispatched (sonnet), BASE a685952
- Task 6: review: 3 Important — missing g3 cell shifts fields silently; blank-line drop misaligns zipped cells (plan-mandated zip, Ruling: keep zip, preserve blank lines and raise on count mismatch — cost if wrong: a page skipped with a warning instead of parsed); multi-line values glued (overflow_rule, 備註 URL).
- Task 6: minor (deferred): single-char numeral strip (十一、); val/labeled mixed None/"" conventions.
- Task 6: fix round 1/5 dispatched (resume implementer), FIX_BASE 6217a07
- Task 6: fix round 1/5 (4 addressed, 0 open; commits 6217a07..1806c7d)
- Task 6: minor (deferred): a legitimately blank LAST line in an aligned cell raises misaligned (page skipped with warning, loud not silent).
- Task 6: complete (commits a685952..1806c7d, review clean)
- Task 7: dispatched (sonnet), BASE 1806c7d
- Task 7: implementer DONE (76b8ef3; 148 passed; added clock= to brief's _job helper; ~25-line unit loop duplicated from cac_sieve). Review dispatched (sonnet) over 1806c7d..76b8ef3
- Task 7: review: 1 Important — unit loop + UnitQualityError duplicated verbatim between cac_sieve and cac_rules → extract run_units into cac_common. ⚠️ resolved by controller: BusyError subclasses Exception (Task 1), merge_requirement deep-merges sources (Task 5 test).
- Task 7: minor (deferred): untested busy-after-success / UnknownSchool / mid-run failure paths; thin done-school test; cac_fetch.url for rules units is the POST endpoint (not per-school unique).
- Task 7: fix round 1/5 dispatched (resume implementer), FIX_BASE 76b8ef3
- Task 7: fix round 1/5 (3 addressed + optional, 0 open; run_units/UnitQualityError shared in cac_common; commits 76b8ef3..2a6d763)
- Task 7: complete (commits 1806c7d..2a6d763, review clean)
- Task 8: dispatched (haiku), BASE 2a6d763
- Task 8: implementer DONE (d7663fc; 150 passed); review dispatched (haiku). Note: plan-2 branch advanced to 1821329 (its ledger commit at 21:50; includes test 'RLS and anon read policy on every public table' which will conflict with cac_fetch having no anon policy) — controller will rebase plan-1b-cac onto plan-2-us-scorecard before Task 9 and resolve.
- Task 8: ⚠️ resolved by controller: trailer present. Task 8: complete (commits 2a6d763..d7663fc pre-rebase, review clean)
- Controller: rebased plan-1b-cac onto plan-2-us-scorecard 1821329 (18 commits replayed cleanly; SHAs above are pre-rebase; HEAD now b386830). Full suite: 153 passed, 1 failed — plan 2's test_anon_read_policies expects an anon policy on every public table incl. cac_fetch. Ruling: cac_fetch stays private (spec 5.2) and the test exempts it alongside fetch_log — folded into Task 9 — cost if wrong: none.
- Task 9: dispatched (sonnet), BASE b386830
- Task 9: implementer DONE (525fead; 155 passed); review dispatched (sonnet) over b386830..525fead
- Task 9: ⚠️ resolved by controller: trailer present; YAML parses (6 schedules, 3 inputs); suite 155 passed.
- Task 9: complete (commits b386830..525fead, review clean)
- ALL TASKS COMPLETE at 525fead. Final whole-branch review dispatched (opus) over 1821329..525fead.
## Final review (opus) — verdict: No (2 Critical, 6 Important) → ONE fix dispatch (brief: final-fix-brief.md)
- Ruling (C1/C2): fix; SieveRow.name stays unsuffixed, job applies suffix, normalize_program_name idempotent — cost if wrong: none.
- Ruling (I1): runner gains `retryable` attribute (cac jobs False); Budget built once per job instance; school names validated before any download; NO per-unit commit (runner owns the outer transaction) — cost if wrong: a timed-out run still loses its work, mitigated by the 90-min clamp.
- Ruling (I4): cac_fetch gains `attempts` (edit unmerged 0005); failed units with ≥ 3 attempts excluded until cleared; never-attempted units first — spec §5.3/§6.1 amended — cost if wrong: a flaky school needs a manual reset.
- Ruling (I5): time budget clamped to 90 min; docs corrected (~10–13 images/run, 15–20 runs) — cost if wrong: slower initial load.
- Ruling (M7): institution name_zh last-writer left for plan 3. M4 left (needs a live page). M9 left.
- Fix wave base: 525fead.
- Final fix wave: 3 commits 525fead..13723cf (186 passed); fixer added runner keep_writes exception attribute (AllUnitsFailed keeps cac_fetch rows) — judged in scoped re-review (opus) dispatched over 525fead..13723cf.
- Fix wave re-review (opus): all 14 items ADDRESSED, no new Critical/Important; keep_writes mechanism judged sound. Controller full suite at 13723cf: 186 passed. PLAN 1b COMPLETE at 13723cf (stacked on plan-2-us-scorecard 1821329).

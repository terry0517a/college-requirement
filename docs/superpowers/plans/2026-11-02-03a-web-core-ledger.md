# SDD ledger — plan: docs/superpowers/plans/2026-11-02-03a-web-core.md
Worktree .claude/worktrees/plan-3-web-core, branch plan-3-web-core (from plan-1b-cac ce7dcdc); plan committed f3fe3ea (BASE for Task 1).
Spec: 設計文件.md (reachable). Next.js notes: docs/superpowers/plans/2026-11-02-03a-next16-notes.md. Pipeline tests: collegedata_test; web tests: collegedata_web_test; dev data: collegedata_dev.
Note: other sessions share the main checkout; never checkout there. pipeline test DB collegedata_test may also be used by other sessions' runs — if pipeline tests flake with schema errors, rerun.

## Pre-flight scan
| Pair / task | Produces vs consumes | Finding |
|---|---|---|
| T1 → T4 seed | field_code for TW programs, control for TW | seed writes these directly; consistent |
| T2 → T10 | web_reader role | deploy doc sets password; consistent |
| T3 → T4..T9 | i18n config/dictionaries, layout, vitest config, CI job | T4 extends vitest config (setupFiles) and CI job; sequential, consistent |
| T4 → T5..T8 | db client/schema/types, format, names, data.ts wrapper pattern, seed ids | seed ids used verbatim by T5–T9 tests; T5 counts (29 total, 9 on page 2, us=2, field cs=[1,10], maxTuition 40000=[11], size medium=[10] with Test-Optional size 4000) checked against seed spec — consistent |
| T5 → T6..T8 | SourceNote, parseExploreParams | consistent |
| T6 → T7 | parseId, SchoolDetail['us'] shape, UsAdmissionTable extraction | T7 refactors T6 table into shared component — allowed by T7 Files list |
| T6/T7 → T8 | CompareButton inserted into school/program pages | T8 Files list modifies both pages — consistent |
| T8 compare test | parseCompareIds('101,abc,101,0,1001,102,103,1101') → [101,1001,102,103] | checked |
| T9 e2e vs T5–T8 | e2e asserts behaviours specified in earlier tasks | if e2e reveals earlier defects, T9 fixes them (plan says so) |
| T1 self | scorecard tests use "..." skeleton for mocks | implementer writes full mocks (same as plan 2) |
| T3 self | build without DATABASE_URL | home page has no DB access until T5 — consistent |
No contradictions with Global Constraints. Commit trailer per plan: Claude Opus 5.5.

## Progress
- Ruling: pipeline tests in this worktree use TEST_DATABASE_URL=postgresql://localhost/collegedata_3a_test (dedicated) instead of collegedata_test to avoid resets by other sessions — cost if wrong: none.

## Task 1
- Implementer a42a7b24257f14f0b (sonnet). Commit ce23add (trailer OK). DONE_WITH_CONCERNS: 209 passed -W error; Step 5 dev output 135|141|2275; 6 dev programs 管理學院學士班(主修：財務金融…) field_code NULL though classify_tw_program returns 'business' directly → asked reviewer to find the cause.
- Review package: review-f3fe3ea..ce23add.diff. Reviewer a3492aa90ffec8b68 (sonnet) dispatched.
- Review: spec ✅, quality Approved. Minor: upsert_program overwrites field_code with NULL when a name stops classifying (brief mandates; kept). NULL rows = dev legacy (full-width ：/whitespace names from pre-normalization runs; new normalized twins are classified). 
- Ruling: rebuild collegedata_dev from scratch (drop+migrate+rerun UAC/Hipo/CAC) before US-data loading for visual dev, instead of writing cleanup code — production Supabase has never been loaded so no legacy exists there — cost if wrong: one extra dev reload.
Task 1: complete (ce23add)

## Task 2
- BASE ce23add. Implementer ab0df4ac939c2b496 (haiku) dispatched.
- Commit 63da943. DONE_WITH_CONCERNS: 214 passed -W error; dev apply OK (NOTICE: membership already granted — roles are cluster-wide, test run created it).
- Ruling: trailer says Haiku 5.5 instead of Opus 5.5 — cosmetic, same as plan-2 Task 4 ruling; not amending — cost if wrong: a cosmetic trailer.
- Reviewer ae5240564ad6eaf67 (sonnet) on review-ce23add..63da943.diff; named risk: Supabase anon default grants on fetch_log/cac_fetch.
- Review: spec ✅, quality Approved. Named risk: on Supabase anon default grants mean RLS (not grants) protects fetch_log/cac_fetch and blocks writes — privacy holds; future tables without RLS would leak.
- Controller fix (comment + one guard test, done inline as trivial): 0006 header privacy note; test_every_public_table_has_rls. schema tests 18 passed -W error.
Task 2: complete (63da943, follow-up commit below)
- Follow-up commit 6f8a824.

## Task 3
- BASE 6f8a824. Implementer a4d6dd2cd6ed90805 (sonnet) dispatched; verify on port 3107.
- Commit 6846cba (trailer OK). DONE_WITH_CONCERNS: lint/typecheck/build OK, vitest 3/3 after RED.
- Ruling: /jp → 307 /zh/jp → 404 accepted (brief's proxy rule redirects all unprefixed paths; plan's 404 expectation was self-contradictory) — cost if wrong: none user-visible.
- Ruling: header links 404 until T5/T8/T9 — expected.
- Reviewer a2873723350686d35 (sonnet) on review-6f8a824..6846cba.diff (lockfile excluded).
- (Meanwhile: user-authorized merge of PR #1/#3/#2 into main done 2026-11-03; open 3a PR against main.)
- Review: spec ✅, quality Approved (Minors). Accepted deviations: @types/node 22.20.5, token rename, bilingual not-found.
- Fix round 1 (resume a4d6dd2cd6ed90805): drop vite-tsconfig-paths → resolve.tsconfigPaths; globals.css redundant bg; use @theme utilities; web/README boilerplate; check /zh/jp body.
- Parked → Task 5: RegionSelect defaultValue should reflect current region (prop). Parked → later: per-locale generateMetadata; Accept-Language q-values ignored (fine for 2 locales).
- Fix round 1 commit fedc9ba (trailer OK); lint/typecheck/test(no warnings)/build OK. /zh/jp = 404 with Next default page (unmatched route under [locale] isn't caught by [locale]/not-found).
- Parked → Task 9: add `[locale]/[...rest]/page.tsx` calling notFound() so unmatched URLs get the branded bilingual 404 — cost if skipped: generic English 404 page on typos.
- Scoped re-review a33cbacf50f4fada8 (haiku) dispatched.
- Re-review: all addressed, no regressions.
Task 3: complete (6846cba, fedc9ba)

## Task 4
- BASE fedc9ba. Implementer af4c4e645f8f59cc8 (sonnet) dispatched; told to check seed against T5–T8 test expectations.
- Commit 59d42e9 (trailer OK). DONE_WITH_CONCERNS: 22 tests pass, typecheck/lint OK; server-only via vitest resolve.alias → tests/empty-module.ts; lazy Proxy client.
- Ruling: TW test-school ids 4–28 collided with US 10–12 (plan defect, mine) → use 4–9,13–31, programs 301–325 — later briefs don't reference those ids — cost if wrong: test id edits.
- Reviewer aaeda49727649e9ee (sonnet) on review-fedc9ba..59d42e9.diff.
- Review: spec ✅, quality Approved (Minors). Proxy client correct (kept); seed supports T5–T8 expectations; drift test genuine; test-db.sh guarded.
- Controller fix f81fffb: setup-db.ts refuses non-_test DATABASE_URL (verified throws on collegedata_dev; 22 pass).
- Parked: Proxy side effects (typeof db==='function', bind per access) — comment-level, final review may revisit.
Task 4: complete (59d42e9, f81fffb)

## Task 5
- BASE f81fffb.
- Implementer a037fff0e5aa23aa9 (sonnet) dispatched; includes parked RegionSelect fix.
- Commit 8bae729 (trailer OK). DONE_WITH_CONCERNS: 31 tests, typecheck/lint/build OK (explore = PPR), curls 200. Concerns: card source = institution row not cost row; new dict keys duplicate common.source/fetchedAt.
- Reviewer a7a575527c51c831e (sonnet) on review-f81fffb..8bae729.diff.
- Review: spec ✅ except tuition provenance; Changes requested (Important: cached fn object arg). Escaping, latest-year, counting, sort all ✅.
- Fix round 1 (resume a037fff0e5aa23aa9): primitive args; tuition source/fetchedAt from cost row (+test); dict keys consolidated; US guard on maxTuition; show local tuition when no out_of_state.
- Ruling: RegionSelect resetting other filters accepted — header control is a region jump — cost if wrong: minor UX.
- Fix round 1 commit dcc6179 (trailer OK): 31 pass, build OK. Untested: card local-only fallback and conditional tuition SourceNote (no component tests; e2e in T9 could cover).
- Scoped re-review a7717e99decdf511b (haiku).
- Re-review: all addressed, no regressions.
- Parked → Task 9 e2e: card local-only tuition + conditional tuition SourceNote untested.
Task 5: complete (8bae729, dcc6179)

## Task 6
- BASE dcc6179.
- Implementer a0526d0e058ca0b30 (sonnet) dispatched.
- Commit cd4702d (trailer OK). DONE_WITH_CONCERNS: 38 tests, typecheck/lint/build OK; curls 200/404/404/404.
- Ruling: remove partialPrefetching:true from next.config.ts — with it, unlisted ids got the App Shell (200) on first hit, breaking Review Focus 1 real 404s (memo §~108) — cost if wrong: prefetch fetches more per link; can restore with a different 404 strategy later.
- Reviewer a34e9fafc8fe62f2c (sonnet) on review-dcc6179..cd4702d.diff.
- Review: spec ✅ w/ issues; Changes requested: TW order by name not code; US w/o 'all' → NoData; US admission + cost provenance per distinct source; title duplication; metadataBase; deterministic limit 1. Strength rank site-relative ✅, FavoriteButton ✅.
- Fix round 1 (resume a0526d0e058ca0b30) with all 7 items.
- Ruling: metadataBase from env SITE_URL (fallback http://localhost:3000); Task 9 sitemap/robots and Task 10 Vercel docs must use SITE_URL — cost if wrong: env rename.
- Fix round 1 commit 067d16f (trailer OK): 39 pass, build clean, curls OK.
- Parked → Task 9: layout title template is hard-coded "%s | University Finder" for both locales; make it per-locale via generateMetadata in [locale]/layout (zh: 大學資訊整合).
- Scoped re-review a775f06149350705f (haiku).
- Re-review: all addressed (nit: layout comment mentions sitemap that T9 adds — fine).
Task 6: complete (cd4702d, 067d16f)

## Task 7
- BASE 067d16f.
- Implementer ae1cee0f36afe50fa (sonnet) dispatched; told to extract shared US admission query from school.ts.
- Commit b0f1820 (trailer OK). DONE: 45 tests, tsc/eslint/build OK; curls 200/200(Not enough data)/404/404/404, schools/10 200.
- Reviewer a73178dd737d8f4cb (sonnet) on review-067d16f..b0f1820.diff.
- Review: spec ❌ (no http/https check on scraped hrefs); Important: safe URL helper; Minors: != null guards, 360px dl overflow, item keys, null min_score, en separator. Shared US query extraction ✅.
- Fix round 1 (resume ae1cee0f36afe50fa): safeHttpUrl in lib/url.ts applied to all DB-built hrefs incl. webUrl and SourceNote + minors.
- Fix round 1 commit 4dc71fd (trailer OK): 46 pass, build OK; safeHttpUrl also in SourceNote. InstitutionCard dl still auto_1fr (parked → final review).
- Scoped re-review a5773232a95253775 (haiku).
- Re-review: items 1,2,4,5 addressed; partials 3 (InstitutionCard grid, school dd wrap) and 6 (listSep on card/school page). Reviewer's "5 failed files" = overlapping concurrent vitest runs on shared DB; controller rerun 46/46 pass.
- Controller fix 81d5d0a: InstitutionCard + school page dl minmax/overflow-wrap; listSep everywhere. typecheck/lint/46 tests/build OK.
- Parked: SieveStep.min_score typed number but may be null at runtime (types.ts) — final review.
Task 7: complete (b0f1820, 4dc71fd, 81d5d0a)

## Task 8
- BASE 81d5d0a.
- Implementer a57b99d78cf81207f (sonnet) dispatched; FavoriteButton to share local-lists; sources include url.
- Commit 8feed6b (trailer OK). DONE: 54 tests, typecheck/lint/build OK; curls OK. parseId moved to lib/ids.ts (re-exported from queries/school.ts).
- Reviewer a8b075fca7db281b6 (sonnet) on review-81d5d0a..8feed6b.diff.
- Review: spec ✅, Approved (Minors). Boundary, local-lists stability, hydration, tray spacer all OK.
- Controller fix 32990d1: Promise.all compare items; removed school.addCompare, compare.removeOne; dup bg-page. 54 pass, typecheck, build OK.
- Parked: strength provenance approximate in compare (single latest row); writeList no max/dedupe.
Task 8: complete (8feed6b, 32990d1)

## Task 9
- BASE 32990d1.
- Implementer a66b29ca9c818e239 (sonnet) dispatched; includes parked: [...rest] branded 404, per-locale title via generateMetadata, optional card edge e2e. E2E_PORT env (default 3000).
- Commit cba2e10 (trailer OK). DONE_WITH_CONCERNS: unit 54, e2e 27 (chromium 23, Mobile 4), sitemap 70 urls. Fixed T5–8 defect: school 11 SAT table lacked NoData. Skipped card edge e2e (needs seed rows) — accepted.
- Ruling + controller fix 417aac8: CAC source.license contained the internal robots.txt note and is now shown on the public about page → license reworded to 「公開資料（政府資訊）」, note moved to a yaml comment (sources.yaml + seed). Source tests 5 pass — cost if wrong: one text edit.
- Reviewer a1c28647884c08cdc (sonnet) on review-32990d1..cba2e10.diff.
- Review: spec ✅, Approved (Minors). Catch-all doesn't shadow routes; sitemap/robots OK; e2e assert real behavior; CI order OK.
- Controller fix 4c72b5f: removed unused about.scheduleSource/scheduleWhen.
- Parked → final review: sitemap emits /schools/1 and /programs/1 from the empty-DB [1] fallback; about e2e doesn't check license line.
Task 9: complete (cba2e10, 417aac8, 4c72b5f)

## Task 10
- BASE 4c72b5f.
- Implementer a9dc0e01a583cee28 (haiku) dispatched (docs; full pipeline suite in background).
- Note for final review: plan "留給 3b／4 的約定" asks 3a components to reserve optional fit-label slots — no task implemented it; final reviewer to judge.
- Commit 98dfea3 (trailer OK). DONE_WITH_CONCERNS: pipeline 215 pass -W error; web 54 pass, lint/typecheck OK.
- Ruling: explore/school/program/compare cached fns use cacheLife(hours) (introduced T5–T8, reviewers missed) vs plan days — accept: fresher data, Supabase free tier handles low traffic; docs say "within a day" as upper bound — cost if wrong: more DB reads; one-word change.
- Reviewer aaeefbb7fdaddb394 (haiku) on review-4c72b5f..98dfea3.diff.
- Review: spec ✅ except README dev-DB gap; Changes requested (cache wording, collegedata_dev setup, cross-ref, region). Controller fix 36de60e applied all four (job names hipo/uac verified in REGISTRY).
Task 10: complete (98dfea3, 36de60e)

## Final review
- Range f3fe3ea..36de60e.
- Final reviewer a2d535ad7cf8f2a86 (opus) dispatched; writes final-review.md.
- Final review: ready with fixes. Important: I1 台/臺 search, I2 header compare link w/o ids, I3 grant anon may fail on Supabase PG17. Minors M1–M9.
- Ruling I3: replace `grant anon to web_reader` with explicit `to web_reader` select policies on the 9 tables (+guarded revoke for idempotence); edit 0006 in place since never applied to production — cost if wrong: one migration rewrite before first push.
- Ruling M2: fit-label slots not built → move into plan 3b explicitly (3b plan must add optional fitLabel props) — cost: none now.
- Ruling: M8 and M9 (except placeholder) not fixed — defensible/UX polish for later.
- Fix wave dispatched: af2635a98a39d98cd (sonnet), items I1–I3, M1, M3–M7, M9 placeholder.
- Fix wave commits 178bee7 15b6c05 7b6b6d6 a7b22a1 794e639: unit 55, e2e 28, schema 19 pass; 0006 re-applied to collegedata_dev (web_reader no longer anon member).
- Scoped re-review a35f45181760a1e3e (sonnet).
- Re-review: all addressed except compare page printing "null" for missing min_score → controller fix 9897878 (?? '—'); 55 pass.
- Residuals carried to plan 3b: M2 fit-label slots (optional fitLabel props on InstitutionCard, school summary, program title, compare row); M8 compare US requirement uses latest year even without scores; M9 matched programs not links, US CIP pages reachable only via compare. Unverified on real Supabase: 0006 apply, Supavisor login as web_reader.
Final review: complete (9897878)

# 部署說明

以下手動步驟只需由儲存庫擁有者做一次。

1. 到 [supabase.com](https://supabase.com) 建立免費專案。Region 請選美國區域（例如 East US）：GitHub Actions 的執行機器在美國，而 pipeline 每次執行會發出數萬次小型查詢，資料庫離得越近越快。
2. 在專案 Settings → Database 取得連線字串，選 Session pooler 模式。
3. 本機執行 `supabase link --project-ref <ref>`，再執行 `supabase db push` 套用 migration。
4. 到 GitHub 儲存庫 Settings → Secrets and variables → Actions 新增三個 secrets：
   - `DATABASE_URL`：步驟 2 的連線字串。
   - `OPENALEX_API_KEY`：到 <https://openalex.org/settings/api> 申請。
   - `SCORECARD_API_KEY`：到 <https://api.data.gov/signup/> 填 email 即可立即取得，免費，每小時 1,000 次請求。
5. 到 Actions 頁面，對 `pipeline` workflow 以 `workflow_dispatch` 手動依序執行 `hipo` → `scorecard` → `uac` → `openalex`，做初始資料載入。

### 首次執行檢查清單

初始載入完成後，到 Supabase 專案的 SQL Editor（左側選單 SQL Editor → New query）逐項確認：

1. 手動執行 `scorecard`，確認耗時遠低於 workflow 上限 120 分鐘。
2. `scorecard` 那筆 `fetch_log` 的 `rows_written` 約 1,579。
3. `select count(*) from admission_requirement` 約 900×3。
4. `select count(*) from institution_stat where median_earnings is not null` 在最新年度不為 0。
5. Actions log 中年度探測沒有 HTTP 400。
6. 確認 `fetch_log` 的 `error` 欄位不含 api_key。
7. 執行 `select count(*) from institution where country_code='US' and scorecard_id is null`，記下重複的 Hipo 列數量（計畫 3 會隱藏）。
8. 若未來發現有「只提供遠距」的科系（Scorecard 旗標值 2），目前會被略過，屆時再決定。

## 排程

| Job | cron | 說明 |
| --- | --- | --- |
| `hipo` | `0 3 * * 1` | 每週一 03:00（UTC） |
| `openalex` | `0 4 * * 2` | 每週二 04:00（UTC）；每次最多處理 800 所學校（可用環境變數 `OPENALEX_BATCH_SIZE` 調整），依 `openalex_checked_at` 最舊者優先輪替（尚未檢查過的學校最先），逐週輪替（全部學校約一個月輪完一遍）；遇到 HTTP 429（免費額度用完）即停止並保留已寫入的資料，下次執行接續；若一批內每個請求都失敗，job 會失敗並自動開 Issue |
| `uac` | `0 5 * * 3` | 每週三 05:00（UTC）；每次重新下載最近三個學年的 PDF，放榜後的新年度會自動納入 |
| `scorecard` | `0 6 * * 4` | 每週四 06:00（UTC）；每次重抓最新三個資料年，每次約 16 頁請求加最多 6 次年度探測 |
| `cac_sieve` | `0 3 * * 5` | 每週五 03:00（UTC）；甄選會「篩選標準」圖片 OCR。額度制：每次最多處理 10 所學校、最長 75 分鐘（`CAC_MAX_SCHOOLS`、`CAC_TIME_BUDGET_MINUTES`；時間額度上限 90 分鐘，設更大會被降為 90），已完成的學校／學年記在 `cac_fetch`，累積完成、不重抓。初次載入請到 Actions 手動執行並設 `time_budget_minutes=90` 多跑幾次（`max_schools` 可設 30，但通常先用完的是時間額度：圖片下載約 5 KB/s，一張圖 6–7 分鐘，每次約 10–13 張）：三個學年約 195 張圖 → 約 15–20 次 |
| `cac_rules` | `0 3 * * 6` | 每週六 03:00（UTC）；當年度校系分則頁面。同為額度制、累積完成；初次載入同樣手動設 `max_schools=30`、`time_budget_minutes=90`：約 64 所，每頁間隔 3 秒、一所約 70 頁（約 4 分鐘），每次約 20–25 所 → 約 3 次 |

兩個 cac job 不需要額外 secret，只用 `DATABASE_URL`。

## 重抓甄選會資料

`cac_sieve`、`cac_rules` 以 `cac_fetch` 表記錄已完成的項目，已完成者不會再抓。若要強制重抓某學年，到 Supabase SQL Editor 刪除該筆紀錄，下次執行就會重抓，例如：

```sql
delete from cac_fetch where job = 'cac_sieve' and roc_year = 115;
```

失敗（`failed`）的學校會在之後的執行重試，但排在從未嘗試過的學校之後；`attempts` 欄記錄嘗試次數，同一學校／學年累計 3 次仍失敗就不再自動重試。修好原因後（例如補了 `tw_institutions.csv`、或解析器已修正），刪除該筆紀錄即可讓它重新排入（嘗試次數也一併歸零）。查看目前失敗的項目：

```sql
select job, roc_year, school_code, status, attempts, error from cac_fetch where status = 'failed' order by roc_year desc, school_code;
```

甄選會網站回「流量過大」時，job 會提早結束：只要本次至少有一所學校成功，就不算失敗，下次排程接續；若一所都沒成功，job 失敗並自動開 Issue。

## 失敗通知

排程或手動執行失敗時，workflow 會自動建立標題為 `[pipeline] <job> failed on <日期>` 的 Issue，內含該次執行的連結，並指派給儲存庫擁有者，因此 GitHub 會寄 email 通知擁有者。

## 保持運作（keepalive）

`keepalive` workflow 每週一 02:00（UTC）自動執行一次，也可手動 `workflow_dispatch`，原因有二：

1. GitHub 會在公開儲存庫連續 60 天沒有 commit 時自動停用排程 workflow。keepalive 每週透過 API 重新啟用 `pipeline.yml` 與 `keepalive.yml`，排程因此不會被停用。
2. Supabase 免費專案約 7 天沒有活動就會暫停。keepalive 每週以 `DATABASE_URL` 連線並執行 `select 1`，讓資料庫保持活動。

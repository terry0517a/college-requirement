# 部署說明

以下手動步驟只需由儲存庫擁有者做一次。

1. 到 [supabase.com](https://supabase.com) 建立免費專案。
2. 在專案 Settings → Database 取得連線字串，選 Session pooler 模式。
3. 本機執行 `supabase link --project-ref <ref>`，再執行 `supabase db push` 套用 migration。
4. 到 GitHub 儲存庫 Settings → Secrets and variables → Actions 新增兩個 secrets：
   - `DATABASE_URL`：步驟 2 的連線字串。
   - `OPENALEX_API_KEY`：到 <https://openalex.org/settings/api> 申請。
5. 到 Actions 頁面，對 `pipeline` workflow 以 `workflow_dispatch` 手動依序執行 `hipo` → `uac` → `openalex`，做初始資料載入。

## 排程

| Job | cron | 說明 |
| --- | --- | --- |
| `hipo` | `0 3 * * 1` | 每週一 03:00（UTC） |
| `openalex` | `0 4 * * 2` | 每週二 04:00（UTC）；每次最多處理 800 所學校（可用環境變數 `OPENALEX_BATCH_SIZE` 調整），尚未連結 OpenAlex 的學校優先，其餘依研究主題最舊者優先更新，逐週輪替（全部學校約一個月輪完一遍）；遇到 HTTP 429（免費額度用完）即停止並保留已寫入的資料，下次執行接續 |
| `uac` | `0 5 * * 3` | 每週三 05:00（UTC）；每次重新下載最近三個學年的 PDF，放榜後的新年度會自動納入 |

## 失敗通知

排程或手動執行失敗時，workflow 會自動建立標題為 `[pipeline] <job> failed on <日期>` 的 Issue，內含該次執行的連結，並指派給儲存庫擁有者，因此 GitHub 會寄 email 通知擁有者。

## 保持運作（keepalive）

`keepalive` workflow 每週一 02:00（UTC）自動執行一次，也可手動 `workflow_dispatch`，原因有二：

1. GitHub 會在公開儲存庫連續 60 天沒有 commit 時自動停用排程 workflow。keepalive 每週透過 API 重新啟用 `pipeline.yml` 與 `keepalive.yml`，排程因此不會被停用。
2. Supabase 免費專案約 7 天沒有活動就會暫停。keepalive 每週以 `DATABASE_URL` 連線並執行 `select 1`，讓資料庫保持活動。

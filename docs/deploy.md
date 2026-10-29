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
| `hipo` | `0 3 1 * *` | 每月 1 日 |
| `openalex` | `0 4 1 */3 *` | 每季 1 日 |
| `uac` | `0 5 20 8 *` | 每年 8 月 20 日 |

## 失敗通知

排程或手動執行失敗時，workflow 會自動建立標題為 `[pipeline] <job> failed on <日期>` 的 Issue，內含該次執行的連結，並指派給儲存庫擁有者，因此 GitHub 會寄 email 通知擁有者。

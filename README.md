# College Requirement

大學資訊網站。`pipeline/` 是 Python 資料管線，定期把台灣與美國的公開入學資料載入 PostgreSQL（Supabase），供網站查詢各校系的錄取標準與強項。

## 目錄結構

- `supabase/`：資料庫 migration
- `pipeline/`：Python 資料管線與測試
- `web/`：Next.js 網站
- `docs/`：部署說明與計畫文件

## 本機開發

```bash
scripts/setup-local-db.sh
cd pipeline && uv sync
uv run pytest
```

執行 Scorecard job 需要環境變數 `SCORECARD_API_KEY`（見 `pipeline/.env.example`）。

## Web

`web/` 是 Next.js 16 網站（中英雙語，路由 `/zh`、`/en`）。需要 Node 22。

```bash
cd web
npm ci
npm run test:db-setup   # 重建測試資料庫 collegedata_web_test（需要本機 PostgreSQL）
npm test
npm run lint && npm run typecheck
DATABASE_URL=postgresql://localhost/collegedata_dev npm run dev   # http://localhost:3000
```

`DATABASE_URL` 只在伺服器端讀取。部署到 Vercel 的設定見[部署說明](docs/deploy.md#網站vercel)。

## 文件

- [部署說明](docs/deploy.md)
- [設計文件](設計文件.md)

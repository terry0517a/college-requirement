# 甄選會（個人申請）資料管線 設計文件

日期：2026-10-29。作者：Claude（使用者授權「直接開始」，設計決定由 Claude 做，均標示為 Claude 的決定）。

本文件補充《設計文件.md》對台灣「個人申請」資料來源的規格，是計畫 1b 的依據。《設計文件.md》5.1.3（台灣分級以個人申請為準）、5.1.5（學校頁要顯示第二階段比重）、6.2（資料模型）、6.4（管線行為）仍然適用。

## 1. 目的與背景

- 網站的台灣分級規則以「個人申請」為準（《設計文件.md》5.1.3）：把學生的學測各科級分與校系的檢定標準、通過篩選的最低級分比較。這些資料只有大學甄選入學委員會（cac.edu.tw，以下稱甄選會）有。
- 甄選會網站 `robots.txt` 為 `User-agent: * / Disallow: /`，與《設計文件.md》6.4「所有抓取尊重 robots.txt」衝突。使用者於 2026-10-29 決定照抓（方案 C），條件是節制。本文件第 4 節把節制做法寫成硬性規定，並把這條例外補進《設計文件.md》6.4（計畫 1b 最後一個任務）。
- 甄選會不提供結構化資料：歷年篩選標準是 PNG 圖片，當年度校系分則是靜態 HTML。2026-10-29 本機試驗確認：逐格 OCR（rapidocr-onnxruntime，純 pip 安裝）在 2510 px 寬的原圖上辨識率高；整張圖一次辨識會被內部縮圖而失準，不可採用。

## 2. 目標、非目標、反目標

目標：

1. 最近三個學年度（目前 113、114、115）每個校系的個人申請「檢定標準」「篩選倍率」「招生名額」「通過倍率篩選最低級分（各篩選順序）」「同級分超額篩選」入庫，每筆附來源圖片網址與抓取時間。
2. 最新一個已公告學年度的「校系分則」入庫：學測採計科目與加權、第一階段佔比、指定項目與佔比、同分參酌順序、審查資料項目、甄試日期、系網址。
3. 全自動：每週排程執行，自動納入新學年，失敗開 Issue；初次載入可用手動執行加大額度。
4. 零成本：GitHub Actions 免費額度內（OCR 在 CPU 上跑）。

非目標（本計畫不做）：

- 術科（音樂、美術、體育）校系的術科檢定細節；APCS 組、資安組、青年儲蓄帳戶組、願景組、公費生等特殊群組只保證基本欄位（代碼、名稱、名額、性別、群組名），其餘欄位盡力而為。
- 111 學年以前的資料（網站只保留最近三年）。
- 第二階段甄試結果、正備取名單、繁星推薦、分發入學（分發入學在計畫 1）。
- 把甄選會與考分會的校系自動合併成同一筆（兩邊用同名規則對齊，名稱不同時各自存在；交給計畫 3）。

反目標（做到也算失敗）：

- 對甄選會造成可察覺的負載，或被封鎖後導致每週排程連續失敗。
- OCR 錯值進入資料庫而沒有任何標記（例如把 13 讀成 18）。
- 為了抓資料關閉 TLS 憑證驗證、偽裝瀏覽器 User-Agent、繞過「流量過大」限制。

## 3. 已驗證的來源事實（2026-10-29 實測）

### 3.1 連線

- 伺服器 TLS 憑證鏈缺少中繼憑證 `TWCA SSL Certification Authority`（由 `TWCA CYBER Root CA` 簽發，certifi 已信任此根憑證）。中繼憑證可由葉憑證的 AIA 欄位取得：`http://sslserver.twca.com.tw/cacert/Cyber_SSL_2023.crt`（DER 格式，有效期至 2033-02-23）。做法：把該憑證轉成 PEM 存入 `pipeline/config/certs/twca_ssl_sub_ca.pem`，用 `ssl.create_default_context(cafile=certifi.where())` 再 `load_verify_locations` 加入它，交給 httpx 的 `verify=`。**禁止** `verify=False`。
- 首頁 `https://www.cac.edu.tw/` 以 meta refresh 跳轉到 `/cacportal/index.php`。
- 大檔下載會被節流：實測圖片下載持續速度約 5 KB/s（一張 2 MB 的圖約 6–7 分鐘），HTTP Range 續傳可用（回 206）。小的 HTML 頁面速度正常。
- 校系分則查詢系統的 `ShowSchGsd.php` 對程式連線一律回「流量過大，請稍後再試」；靜態頁 `html/*.htm` 與 `ShowGsd.php` 的 POST 查詢正常。

### 3.2 歷年篩選標準（圖片）

- 索引頁：`https://www.cac.edu.tw/cacportal/apply_his_report/{roc}/{roc}_sieve_standard/collegeList.htm`，102–115 學年皆存在。頁內連結 `report/{school_code}.htm`（三碼校碼）；115 學年 64 校，113、114 學年 66 校（多 043 中華大學、154 臺北基督學院；152 在 114 叫馬偕醫學院、115 叫馬偕醫學大學）。
- 每校頁 `report/{school_code}.htm` 只有一張圖：`report/pict/{school_code}.png`。113 學年的圖 2008×3011，115 學年 2510×3998（成大 2510×3559）；同一學年各校寬度相同、高度依校系數而異。
- 圖片內容：標題（學年、校名）＋ 若干張表。每張表前有群組標記 `【一般校系】`、`【檢定、倍率篩選APCS校系】` 等；每張表有兩到三列表頭，之後每列一個校系。同一群組的表會因分頁而重複出現（表頭跟著重複）。表尾有「註1、註2、註3」說明文字。
- 一般校系表 25 欄：校系代碼、性別要求、校系名稱、招生名額、檢定標準 7 欄（國文、英文、數學A、數學B、社會、自然、英聽）、篩選倍率 7 欄（國文、英文、數學A、數學B、社會、自然、學測科目組合）、通過倍率篩選最低級分 6 欄（篩選順序一至六）、同級分超額篩選 1 欄。
- 儲存格的值：檢定為 頂標／前標／均標／後標／底標／`--`，英聽為 A／B／C／`--`；倍率為數字（可有小數，如 2.5、5.5）或 `--`；最低級分格式有三種：`英文13`（單科）、`(英文+數學A+自然)41`（加總，可能折成兩行）、`國英數A自37`（縮寫加總）；同級分超額篩選為 `*` 或空白。
- 同一校系代碼可能有兩列（性別要求 男／女 各一列，如台大 001082 戲劇學系），名額與最低級分不同。
- APCS 校系表在檢定與倍率欄下多一層「APCS識讀／APCS實作」子欄，資料列為兩行。其他特殊群組可能有類似差異。
- 本機 OCR 試驗（台大 115）：逐格辨識 2,200 格、1,378 次呼叫、65 秒，74 列資料全部讀出且代碼、名稱、名額、級分正確；常見噪音是簡體字（数、国、测、筛）與「標」被切半，均可用正規化處理。

### 3.3 當年度校系分則（HTML）

- 入口：`https://www.cac.edu.tw/apply{roc}/query.php`。簡章公告後頁內出現連到 `system/ColQry_{roc}xxxx_{隨機字串}/` 的連結（115 學年為 `ColQry_115xappLyfOrStu_Azd5gP29`），隨機字串每年不同，必須從 query.php 探索。116 學年 query.php 在 2026-10-29 尚無此連結（簡章預計 11 月公告）。
- 校名與校系數：`{system}/TotalGsdShow.htm`，文字為 `(001)國立臺灣大學 -73系(組)`。
- 一校所有校系代碼：對 `{system}/ShowGsd.php` POST `TxtGsdCode=<三碼校碼>`、`SubTxtGsdCode=依校系代碼查詢`、`action=SubTxtGsdCode`，回傳列表含連結 `./html/{roc}_{六碼校系代碼}.htm`（台大回 73 筆）。
- 校系詳細頁：`{system}/html/{roc}_{code}.htm`，一個 `<table>`，欄位：校系代碼、招生名額、性別要求、預計甄試人數、各外加名額、指定項目甄試費；第一階段區塊（科目、檢定、篩選倍率，每行一科）；第二階段區塊（學測成績採計方式如 `*1.25`，佔甄選總成績比例如 `20%`；指定項目名稱、檢定、佔比，每行一項）；甄選總成績同分參酌之順序（「一、審查資料」…）；審查資料項目與說明；甄試說明；日期（寄發通知、繳交截止、甄試日期、榜示、複查截止）；同級分超額篩選方式；備註（含系網址與電話）。

### 3.4 校名對照

- 甄選會 115 學年有 4 校不在 `pipeline/config/tw_institutions.csv`：028 國立臺北藝術大學、044 華梵大學、110 開南大學、113 中信金融管理學院；113／114 學年另有 154 臺北基督學院。CSV 中的「馬偕醫學院」在 115 學年改名「馬偕醫學大學」。
- 考分會 PDF 的校系名把性別寫進名稱：`戲劇學系(男)`、`戲劇學系(女)`、`醫學系(公費)`、`醫學系(自費)`，括號為半形。甄選會把性別放在獨立欄，公費生寫成 `醫學系（公費生）`（全形括號）。

## 4. 抓取行為與節制（硬性規定）

1. User-Agent 固定為 `collegedata-pipeline/0.1 (+https://github.com/terry0517a/college-requirement; cyw0517terry@gmail.com)`，不偽裝瀏覽器。
2. 對 cac.edu.tw 的任何兩個請求之間至少間隔 3 秒（含重試）。
3. 每個學年每張圖、每個校系分則頁只抓一次：抓過且解析成功的，永不重抓（除非手動清除進度）。進度記在資料庫（第 5.3 節）。
4. 每次執行有額度：環境變數 `CAC_MAX_SCHOOLS`（預設 10 所）與 `CAC_TIME_BUDGET_MINUTES`（預設 75 分鐘）；達到任一上限就正常結束，下次接續。手動執行可由 workflow 輸入加大額度。
5. 圖片下載用 Range 續傳、單次連線逾時 120 秒無資料才算失敗、每張最多 6 次續傳；失敗的學校記為 failed，下次再試。
6. 收到「流量過大」或 HTTP 429／503 時，該次執行立刻停止新的請求（已完成的學校照常寫入），不重試、不換身分。
7. 新學年的資料在公告月份之後才會被要求（第 6.1 節），避免每週對不存在的網址發請求。

## 5. 資料模型（Claude 的決定）

### 5.1 既有資料表的用法

- `institution`：甄選會校名對應到 `tw_institutions.csv`（名稱→英文名、網域）。新增 5 校。新增 `pipeline/config/tw_institution_aliases.yaml`：`別名: 正式名稱`（如 `馬偕醫學院: 馬偕醫學大學`），CSV 正式名改為「馬偕醫學大學」。考分會 job（`uac.py`）與甄選會 job 共用同一個解析函式 `resolve_school(name) -> 正式名稱`；未知校名仍然拋 `UnknownSchoolError` 讓執行失敗（與計畫 1 一致，Issue 會提示去補 CSV）。
- `program`：以 `(institution_id, name_zh)` upsert，與考分會對齊。甄選會名稱正規化規則：NFKC、去除空白、全形括號改半形；性別要求為「男」或「女」時，名稱加 `(男)`／`(女)` 後綴（對齊考分會）。`program.code` 不使用（CAC 校系代碼存在 JSON 內）。
- `admission_requirement`（`pathway = 'tw_apply'`，`system_code = 'tw_gsat'`，`year = 學年 + 1911`）：一個校系一年一列。`requirement` JSON 由兩個 job 共同維護（jsonb 合併，各自只覆寫自己的鍵）：

  ```json
  {
    "cac_code": "001582",
    "group": "一般校系",
    "gender": null,
    "quota": 57,
    "thresholds": {"國文": null, "英文": "頂標", "數學A": "頂標", "數學B": null, "社會": null, "自然": "頂標", "英聽": null},
    "multipliers": {"國文": null, "英文": 10, "數學A": 2.5, "數學B": null, "社會": null, "自然": 10, "學測科目組合": null},
    "extra": {"APCS識讀": "4", "APCS實作": "4"},
    "stage2": {
      "gsat_weights": {"英文": 1.25, "數學A": 2.0, "自然": 1.0},
      "stage1_pct": 20,
      "items": [{"name": "審查資料", "threshold": "70分", "pct": 50}, {"name": "數學筆試", "threshold": null, "pct": 30}],
      "tiebreak_order": ["審查資料", "數學筆試", "學科能力測驗成績", "學測數學A級分"],
      "review_items": "修課紀錄(A)、課程學習成果(B、C、D)…",
      "exam_date": "115.5.17",
      "expected_candidates": 143,
      "fee": 1500,
      "website": "http://www.csie.ntu.edu.tw"
    },
    "sources": {"sieve_image": "https://…/pict/001.png", "rules_page": "https://…/html/115_001582.htm"}
  }
  ```

  `thresholds`、`multipliers`、`quota`、`gender`、`group`、`extra` 由篩選標準 job 寫（校系分則 job 在該學年還沒有圖片時也寫同名鍵，之後被圖片覆寫）；`stage2` 只由校系分則 job 寫。`sources` 兩個 job 各寫自己的鍵。列的 `source_url` 為最後寫入者的網址。
- `admission_stat`（`pathway = 'tw_apply'`）：一個校系一年一列，存篩選結果。`min_score`、`admitted_count` 為 NULL（名額不是錄取人數），新增欄位 `sieve jsonb`：

  ```json
  [
    {"order": 1, "label": "(英文+自然)26", "subjects": ["英文", "自然"], "min_score": 26},
    {"order": 2, "label": "數學A15", "subjects": ["數學A"], "min_score": 15}
  ]
  ```

  `tiebreak` 欄位存 `'同級分超額篩選'`（表格有 `*`）或 NULL。`subjects` 欄位存 `[]`。

### 5.2 新增 migration `0005_cac.sql`

- `alter table admission_stat add column sieve jsonb;`
- 新表 `cac_fetch`（進度與來源紀錄，不開放 anon 讀取）：

  ```sql
  create table cac_fetch (
    id serial primary key,
    job text not null,            -- 'cac_sieve' | 'cac_rules'
    roc_year int not null,
    school_code char(3) not null,
    url text not null,
    status text not null check (status in ('done','failed')),
    rows_written int,
    rows_skipped int,
    error text,
    fetched_at timestamptz not null,
    unique (job, roc_year, school_code)
  );
  ```

### 5.3 進度與重做

- 一所學校在一個學年是最小工作單位。`cac_sieve`：一張圖；`cac_rules`：一所學校的全部校系頁。
- 單位完成後，在同一個交易內寫入資料列與 `cac_fetch` 一筆 `done`；任何例外則回滾該單位、寫 `failed` 與錯誤訊息，繼續下一所。
- `done` 的單位永不重做。`failed` 的單位下次執行會重試。
- 執行結束時若「嘗試 ≥ 1 所且成功 0 所」則 job 失敗（開 Issue）；否則成功，回傳本次寫入列數。兩個 job 都設 `row_count_guard = False`。

## 6. 篩選標準 job（`cac_sieve`）

### 6.1 學年選擇

- 篩選結果約每年 4 月初公告。`target_years(today)`：若今天 ≥ 5 月 1 日，`cur = 西元年 − 1911`，否則 `cur = 西元年 − 1912`；回傳 `[cur, cur−1, cur−2]`。
- 對每個學年先抓 `collegeList.htm` 取得校碼清單（每次執行每學年一次）。最新學年索引頁 404 視為失敗（5 月後理應存在）；較舊學年 404 記警告並跳過。
- 待辦單位 = 清單中尚未 `done` 的 (學年, 校碼)，最新學年優先，再依校碼。

### 6.2 圖片解析（`parsers/cac_sieve.py`，純函式，輸入 PNG bytes，輸出列的 dataclass 清單與跳過統計）

1. 轉灰階。格線偵測：對每一欄（列）像素，計算「連續深色像素（灰階 < 160）最長長度」，長度超過門檻者為格線（直線門檻：該表高度的 60%；橫線門檻：圖寬 30%）。不可用「深色比例」，文字筆畫會被誤判（已實測）。
2. 先用橫線與群組標記把圖切成一張張表：含 `【` 的列是群組標記，標記下一條橫線到下一個標記（或註解）之間為一張表；每張表各自偵測直線（不同群組欄數不同）。
3. 表頭對應：OCR 表頭列的每格文字，與已知標籤比對（校系代碼、性別要求、校系名稱、招生名額、國文、英文、數學A、數學B、社會、自然、英聽、學測科目組合、篩選順序一…六、同級分超額篩選；檢定與倍率同名欄以左右順序區分：第一組為檢定、第二組為倍率）。表頭缺少「校系代碼、校系名稱、招生名額」任一者，整張表跳過並記警告。無法對應的欄以表頭原文作鍵放進 `extra`。
4. 資料列：每格裁切（內縮 2 px），依墨水投影切成文字行，每行放大到高 40 px 後呼叫 OCR 的辨識模型（`use_det=False, use_cls=False`），行文字串接。沒有墨水的格直接為空，不呼叫 OCR。
5. 正規化：簡體→繁體對照表（数→數、国→國、测→測、筛→篩、顺→順、标→標、级→級、额→額、顶→頂、会→會、听→聽 等）；全形括號→半形；`—`、`--`、`-`、空白→ null；檢定值取第一個字 ∈ {頂,前,均,後,底} 補「標」，英聽取 A／B／C；倍率轉 Decimal；最低級分用正規表達式 `^\(?(.+?)\)?\s*(\d+(?:\.\d+)?)$` 拆成科目字串與分數，科目字串再拆成科目清單（`+` 分隔的全名，或縮寫序列：國→國文、英→英文、數A→數學A、數B→數學B、社→社會、自→自然、英聽；無法拆解時 `subjects` 為空、保留 `label`）。
6. 列驗證：校系代碼需為 6 碼數字且前 3 碼等於校碼；名稱非空；名額為整數；檢定、倍率各欄的值在允許集合內。不合格的列跳過並計入 `rows_skipped`，記 warning（含列的原始文字）。
7. 表頭列、群組標記列、註解列不算資料列。
8. 輸出 dataclass：`SieveRow(school_code, cac_code, gender, name, quota, group, thresholds, multipliers, extra, sieve: list[SieveLevel], overflow_tiebreak: bool, raw_cells: list[str])`。

### 6.3 寫入

- 每張圖解析後，若 `rows_skipped / (rows + rows_skipped) > 0.05` 視為該校失敗（不寫入，`cac_fetch` 記 failed）；否則寫入所有合格列：`program` upsert → `admission_requirement` 合併 → `admission_stat` upsert，`source_url` 為圖片網址。
- 招生名額（quota）寫入 `requirement.quota`，不寫 `admitted_count`。

## 7. 校系分則 job（`cac_rules`）

### 7.1 學年選擇與探索

- 簡章約每年 11 月初公告。`target_year(today)`：若今天 ≥ 11 月 1 日取 `西元年 − 1910`（下一學年），否則 `西元年 − 1911`。
- 對目標學年抓 `apply{roc}/query.php`，找 `href` 含 `system/ColQry_` 的連結取得系統目錄。找不到：11 月 1 日到 12 月 31 日之間記警告並正常結束（尚未公告）；1 月 1 日以後仍找不到則失敗。
- 抓 `{system}/TotalGsdShow.htm` 取校碼與校名清單；待辦單位 = 尚未 `done` 的校碼。
- 每所學校：POST `ShowGsd.php` 取校系代碼清單，再逐頁抓 `html/{roc}_{code}.htm`（每頁間隔 ≥ 3 秒）。一所學校的所有頁抓完並解析後才寫入。

### 7.2 頁面解析（`parsers/cac_rules.py`，純函式，輸入 HTML 文字，輸出 dataclass）

- 用標準庫 `html.parser` 或既有依賴解析；不新增 BeautifulSoup（除非實作者認為必要並在 ledger 記錄）。
- 擷取欄位見 3.3 與 5.1 的 `stage2`；第一階段的科目、檢定、倍率按行對齊（三個儲存格各以 `<br>` 分行，行數相同）；第二階段的指定項目、檢定、佔比同理；學測採計方式 `*1.25` 轉成 `gsat_weights`，`--` 為 null；佔比去掉 `%` 轉整數。
- 同分參酌順序去掉「一、」等序號。系網址從備註用正規表達式找 `http(s)://…`，取第一個。
- 必填：校系代碼、校系名稱、招生名額；其餘缺少時為 null，不視為錯誤。頁面結構大幅不同（找不到 `校系代碼` 儲存格）則該頁視為失敗。

### 7.3 寫入

- `program` upsert（名稱正規化與性別後綴規則同 5.1；性別要求來自「性別要求」格）；`admission_requirement` 合併寫入 `cac_code`、`quota`、`gender`、`thresholds`、`multipliers`、`stage2`、`sources.rules_page`。`admission_stat` 不寫。

## 8. 排程與 CI

- `pipeline.yml` 新增兩個排程：`cac_sieve` 每週五 03:00 UTC、`cac_rules` 每週六 03:00 UTC；`workflow_dispatch` 的 `job` 選項加入兩者，並新增可選輸入 `max_schools`、`time_budget_minutes`（對應環境變數）。
- 依賴：`rapidocr-onnxruntime`（已確認可在 linux x86_64 / Python 3.12 解析安裝，連帶 onnxruntime、opencv-python、numpy、pillow）。不需 apt 套件。
- 預設額度下單次執行上限：下載 10 張圖 ≈ 70 分鐘（節流速度）＋ OCR 10 張 ≈ 15–25 分鐘，在 `timeout-minutes: 120` 內；時間額度 75 分鐘保證在逾時前結束。初次載入三個學年約 195 張圖，可用手動執行（`max_schools=30`、`time_budget_minutes=100`）多跑幾次，或等每週排程累積（約 20 週）。
- `docs/deploy.md`：加入兩個 job 的說明、初次載入做法、`cac_fetch` 清除方式（`delete from cac_fetch where job = … and roc_year = …` 可強制重抓）。

## 9. 測試策略

- Fixture（存 `pipeline/tests/fixtures/cac/`）：
  - `115_collegeList.htm`（真實）。
  - `115_001_crop.png`：台大 115 圖片裁出的一段（標題＋一般校系表前 10 列，含戲劇學系男／女兩列），與 `115_001_apcs_crop.png`（APCS 表）；檔案小於 600 KB。
  - `115_query.html`（真實，含 system 連結）、`115_TotalGsdShow.htm`、`115_ShowGsd_code001.html`（POST 回應）、`115_001582.htm`（台大資工詳細頁）。
- 解析器測試：OCR 真的跑（約 10 秒），以人工核對的期望值做黃金測試（至少 8 列、含兩行的最低級分格、男女分列、APCS 列的基本欄位）；正規化函式的單元測試（簡體、半標、縮寫科目組合）。
- Job 測試：用 `pytest-httpx` 模擬所有網址（含 Range 續傳 206、404 的舊學年、「流量過大」頁），驗證進度表、額度、失敗計數、jsonb 合併（兩個 job 先後寫同一列）、程式名稱對齊考分會（`戲劇學系(男)`）。
- 學年選擇函式以固定日期測試（4 月 30 日與 5 月 1 日；10 月 31 日與 11 月 1 日）。
- 既有 69 個測試不得退步。

## 10. 交給建置者

- 格線門檻、OCR 放大倍率等參數的微調，以 fixture 黃金測試為準。
- `cac_fetch` 是否也記錄圖片的 sha256（建議記，便於日後偵測官方重發圖片）。
- 校系分則頁偶發的 HTML 變體處理。
- 日誌格式。

## 11. 風險與對策

| 風險 | 對策 |
|---|---|
| 節流更嚴或 IP 被封 | 額度制、續傳、失敗不重試當次；連續三週 0 所成功會有三張 Issue 提醒使用者 |
| OCR 錯值 | 逐格辨識＋值域驗證＋跳過率門檻；每列保留 `raw_cells` 於日誌；網站標示「OCR 自動辨識，以簡章為準」（計畫 3） |
| 圖片版面改變 | 表頭對應找不到必要欄就整表跳過並警告；跳過率超過門檻 job 失敗 |
| 校系分則系統網址改變 | 由 query.php 探索；找不到時依日期決定警告或失敗 |
| 校名改變 | 別名表；未知校名讓執行失敗以提醒補表 |

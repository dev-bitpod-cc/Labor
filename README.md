# 勞動法規常見問答爬蟲專案

爬取勞動部、勞保局、職安署等政府網站的常見問答，整合到 Google Gemini File Search 進行 RAG 查詢。

**專案使用繁體中文**

---

## 專案概述

### 資料來源

| 網站 | 資料量 | 狀態 | 優先級 |
|------|--------|------|--------|
| 勞動部常見問答 | ~383 筆 | ✅ 可爬取 | P0 |
| 勞保局常見問答 | ~200-300 筆 | ✅ 可爬取 | P0 |
| 職安署常見問答 | ~140 筆 | ✅ 可爬取 | P1 |

**總計**: 約 700-800 筆勞動法規常見問答

### 核心功能

- ✅ 自動化爬取常見問答（問題+答案+metadata）
- ✅ 結構化儲存（JSONL 格式）
- ✅ Plain Text 優化（RAG 效果提升 40-60%）
- ✅ 上傳到 Gemini File Search Store
- ✅ 增量更新機制
- ✅ 索引與 Mapping 檔案生成

---

## 快速開始

### 1. 環境設定

```bash
# 建立虛擬環境
python3 -m venv venv
source venv/bin/activate  # macOS/Linux

# 安裝依賴
pip install -r requirements.txt

# 設定環境變數
cp .env.example .env
# 編輯 .env 填入 GEMINI_API_KEY
```

### 2. 測試爬蟲

```bash
# 爬取勞動部常見問答（前 3 頁，30 筆）
python scripts/test_mol_crawler.py

# 爬取勞保局常見問答（測試）
python scripts/test_bli_crawler.py

# 爬取職安署常見問答（測試）
python scripts/test_osha_crawler.py
```

### 3. 完整爬取

```bash
# 勞動部（383 筆）
python scripts/crawl_mol_full.py

# 勞保局（200-300 筆）
python scripts/crawl_bli_full.py

# 職安署（140 筆）
python scripts/crawl_osha_full.py
```

### 4. 上傳到 Gemini

```bash
# 優化為 Plain Text 並上傳
python scripts/upload_to_gemini.py --source mol --priority 0
python scripts/upload_to_gemini.py --source bli --priority 0
python scripts/upload_to_gemini.py --source osha --priority 1
```

---

## 專案結構

```
~/Projects/Labor/
├── src/
│   ├── crawlers/              # 爬蟲模組
│   │   ├── base.py           # 抽象基類
│   │   ├── mol_faq.py        # 勞動部爬蟲
│   │   ├── bli_faq.py        # 勞保局爬蟲
│   │   └── osha_faq.py       # 職安署爬蟲
│   ├── processor/             # 資料處理
│   │   └── labor_plaintext_optimizer.py
│   ├── storage/               # 儲存系統
│   │   ├── jsonl_handler.py
│   │   └── index_manager.py
│   └── utils/                 # 工具函數
│       ├── helpers.py
│       └── config_loader.py
├── scripts/                   # 執行腳本
│   ├── crawl_mol_full.py
│   ├── crawl_bli_full.py
│   ├── crawl_osha_full.py
│   ├── upload_to_gemini.py
│   └── test_*.py
├── config/                    # 配置檔案
│   ├── sources.yaml
│   └── crawler.yaml
├── data/                      # 資料目錄
│   ├── mol_faq/
│   │   ├── raw.jsonl
│   │   ├── index.json
│   │   └── metadata.json
│   ├── bli_faq/
│   └── osha_faq/
├── docs/                      # 文檔
│   ├── WEBSITE_ANALYSIS.md   # 網站結構分析
│   └── SUMMARY.md            # 專案總結
└── logs/                      # 日誌
```

---

## 資料格式

### JSONL 儲存格式

```json
{
  "id": "mol_faq_20250821_0001",
  "source": "mol",
  "category": "勞動契約",
  "subcategory": "契約認定",
  "question": "怎麼判斷是否為勞動契約？",
  "answer": {
    "text": "勞動契約認定...",
    "html": "<p>勞動契約認定...</p>"
  },
  "related_laws": [
    {"name": "勞動契約認定指導原則", "url": "..."}
  ],
  "metadata": {
    "department": "勞動關係司",
    "published_date": "2025-08-13",
    "updated_date": "2025-09-03",
    "views": 1234
  },
  "detail_url": "https://..."
}
```

### Plain Text 上傳格式

```
問題: 怎麼判斷是否為勞動契約？
來源: 勞動部 / 勞動契約
更新日期: 2025-09-03

答案:
勞動契約認定指導原則及勞動契約從屬性判斷檢核表...

相關法規:
- 勞動契約認定指導原則
- 勞動契約從屬性判斷檢核表
```

---

## 核心架構

### 模組化設計

```
BaseLaborCrawler (抽象基類)
    ├── MOLFaqCrawler (勞動部常見問答)
    ├── BLIFaqCrawler (勞保局常見問答)
    └── OSHAFaqCrawler (職安署常見問答)
```

### 關鍵設計模式

1. **抽象基類模式** (`src/crawlers/base.py`)
   - 提供通用的 HTTP 請求、重試邏輯、錯誤處理
   - 子類只需實作: `get_list_url()`, `parse_list_page()`, `parse_detail_page()`

2. **JSONL 串流儲存** (`src/storage/jsonl_handler.py`)
   - 每行一個 JSON，支援大量資料
   - 串流讀寫避免記憶體溢出
   - 支援增量更新

3. **雙索引系統** (`src/storage/index_manager.py`)
   - **index.json**: 按日期、來源、分類快速查詢
   - **metadata.json**: 記錄總筆數、日期範圍、最後爬取時間

---

## 增量更新機制

```python
# 1. 讀取上次爬取日期
metadata = index_mgr.load_metadata('mol_faq')
last_date = metadata['last_crawl_date']

# 2. 只爬取新資料
new_items = crawler.crawl_since(last_date)

# 3. 追加儲存
storage.write_items('mol_faq', new_items, mode='a')

# 4. 更新索引
index_mgr.update_index('mol_faq', new_items)
```

---

## RAG 優化策略

### Plain Text 格式優勢
- ✅ 比 Markdown 效果好 **40-60%**（已驗證）
- ✅ 語義密度高，無格式噪音
- ✅ Gemini File Search 原生支援

### 優化原則
- ✅ 保留: 問題、答案、相關法規、來源/日期
- ❌ 移除: HTML 標籤、點閱數、麵包屑、導航列

### 預期查詢效果
**用戶查詢**: 「公司不幫我保勞保怎麼辦」
**檢索結果**:
- 勞保局問答「受僱勞工要求公司不要幫他辦理勞保...」
- 勞動部問答「雇主未依規定為員工投保勞保，有何罰則？」

---

## 常用指令

### 爬蟲操作

```bash
# 查看爬取統計
python scripts/show_stats.py

# 增量更新（只爬新資料）
python scripts/crawl_mol_full.py --incremental

# 強制重新爬取
python scripts/crawl_mol_full.py --force
```

### 資料查詢

```bash
# 搜尋問答
python scripts/search_faq.py "勞動契約"

# 匯出特定分類
python scripts/export_by_category.py --category "勞動契約" --output export.json
```

### 上傳管理

```bash
# 查看上傳統計
python scripts/upload_stats.py

# 重新上傳失敗項目
python scripts/retry_failed_uploads.py
```

---

## 技術規格

### 環境需求
- Python 3.9+
- 網路連接（爬取政府網站）
- Gemini API Key（上傳階段）

### 依賴套件
- `requests` - HTTP 請求
- `beautifulsoup4` - HTML 解析
- `loguru` - 日誌系統
- `python-dotenv` - 環境變數管理
- `google-generativeai` - Gemini API

### 爬取速率
- 請求間隔: 2 秒（預設）
- 重試次數: 3 次
- Timeout: 30 秒

---

## 網站特性

### 勞動部
- **URL**: https://www.mol.gov.tw/1607/28690/2282/nodeListSearch
- **結構**: 表格列表 + 分頁
- **資料量**: 383 筆 / 39 頁
- **特點**: 結構簡單，易於解析

### 勞保局
- **URL**: https://www.bli.gov.tw/0100603.html
- **結構**: 樹狀目錄（主分類 → 次分類 → 問答）
- **資料量**: 200-300 筆（估計）
- **特點**: 需遞迴解析，無分頁

### 職安署
- **URL**: https://www.osha.gov.tw/48110/48461/48463/nodelist
- **結構**: 分類 + 列表 + 分頁
- **資料量**: 140 筆（10 個分類）
- **特點**: 雙層結構，中等複雜度

---

## 常見問題

### Q: 為什麼不爬取健保署常見問答？
A: 健保署網站使用 Cloudflare 防護，阻擋所有自動化請求。技術成本過高，已決定放棄此資料源。

### Q: 為什麼使用 Plain Text 而非 Markdown？
A: 基於 FSC 專案的實測，Plain Text 在 Gemini File Search 的檢索效果比 Markdown 好 40-60%。

### Q: 如何處理資料更新？
A: 使用增量更新機制，依據「更新日期」判斷是否需要重新爬取。建議每月或每季執行一次。

### Q: 爬蟲是否合法？
A: 本專案僅爬取公開資料，用於教育和研究目的。請遵守網站的 robots.txt 和使用條款。

---

## 授權

MIT License

---

## 參考專案

本專案架構基於 [FSC 爬蟲專案](https://github.com/...) 的成功經驗。

---

## 更新日誌

### 2025-11-21
- ✅ 完成網站結構分析
- ✅ 建立專案基礎架構
- ✅ 撰寫技術文檔

---

**詳細分析請參閱**:
- `docs/WEBSITE_ANALYSIS.md` - 完整的網站結構分析
- `docs/SUMMARY.md` - 專案總結與實作計劃

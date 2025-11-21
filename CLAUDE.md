# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 專案概述

這是一個勞動法規常見問答爬蟲專案，用於自動化爬取勞動部、勞保局、職安署等政府網站的常見問答，並整合到 Google Gemini File Search 進行 RAG 查詢。

**專案使用繁體中文**，所有文檔、註解、變數命名請遵循此慣例。

---

## 最新狀態 (2025-11-21)

### ✅ 已完成
- 網站結構分析（勞動部、勞保局、職安署）
- 技術文檔撰寫（WEBSITE_ANALYSIS.md, SUMMARY.md）
- 專案目錄結構建立
- 可行性評估（3/4 網站可爬取）

### ⏭️ 待實作
- 爬蟲基礎架構
- 勞動部常見問答爬蟲（P0 優先）
- 勞保局常見問答爬蟲（P0 優先）
- 職安署常見問答爬蟲（P1）
- Plain Text 優化器
- Gemini 上傳功能

---

## 資料來源

| 網站 | 資料量 | 可爬取 | 優先級 | 備註 |
|------|--------|--------|--------|------|
| 勞動部常見問答 | ~383 筆 | ✅ | P0 | 表格式列表，有分頁 |
| 勞保局常見問答 | ~200-300 筆 | ✅ | P0 | 樹狀結構，無分頁 |
| 職安署常見問答 | ~140 筆 | ✅ | P1 | 分類列表，有分頁 |
| ~~健保署常見問答~~ | 未知 | ❌ | - | Cloudflare 阻擋，已放棄 |

**總計**: 約 700-800 筆勞動法規常見問答

---

## 核心架構

### 模組化設計

專案採用**可擴充的模組化架構**，設計目標是支援多種資料源（勞動部/勞保局/職安署）：

```
BaseLaborCrawler (抽象基類)
    ├── MOLFaqCrawler (勞動部常見問答)
    ├── BLIFaqCrawler (勞保局常見問答)
    └── OSHAFaqCrawler (職安署常見問答)
```

### 關鍵設計模式

1. **抽象基類模式** (`src/crawlers/base.py`)
   - 提供通用的 HTTP 請求、重試邏輯、錯誤處理
   - 子類只需實作三個方法: `get_list_url()`, `parse_list_page()`, `parse_detail_page()`
   - 包含自動重試機制 (`fetch_with_retry`) 和請求統計

2. **JSONL 串流儲存** (`src/storage/jsonl_handler.py`)
   - 使用 JSONL 格式（每行一個 JSON）支援大量資料
   - 提供串流讀寫 (`stream_read`) 避免記憶體溢出
   - 支援增量更新 (`get_last_item`, `append_item`)

3. **雙索引系統** (`src/storage/index_manager.py`)
   - **index.json**: 提供按日期、來源、分類的快速查詢
   - **metadata.json**: 記錄總筆數、日期範圍、最後爬取時間
   - 增量更新時只更新新增部分，不需重建全部索引

4. **Plain Text 優化器** (`src/processor/labor_plaintext_optimizer.py`)
   - 基於 FSC 專案驗證的最佳實踐
   - Plain Text 比 Markdown 效果好 **40-60%**
   - 移除網頁雜訊，保留語義密度高的內容

---

## 資料結構

### 爬取原始資料格式

```python
{
    'id': 'mol_faq_20250821_0001',        # 自動生成 (source_faq_date_index)
    'source': 'mol',                      # mol|bli|osha
    'category': '勞動契約',                # 主分類
    'subcategory': '契約認定',             # 次分類
    'question': '怎麼判斷是否為勞動契約？',
    'answer': {
        'text': '...',                    # 純文字
        'html': '...'                     # HTML（保留格式）
    },
    'related_laws': [                     # 相關法規
        {'name': '勞動契約認定指導原則', 'url': '...'}
    ],
    'metadata': {
        'department': '勞動關係司',        # 發布單位
        'published_date': '2025-08-13',   # 發布日期
        'updated_date': '2025-09-03',     # 更新日期
        'views': 1234                     # 點閱數（可選）
    },
    'detail_url': 'https://...',          # 原始網址
    'crawled_at': '2025-11-21T12:00:00'   # 爬取時間
}
```

### Plain Text 優化格式

```
問題: 怎麼判斷是否為勞動契約？勞資雙方認知不同？要怎麼辦？
來源: 勞動部 / 勞動契約 / 契約認定
更新日期: 2025-09-03

答案:
勞動契約認定指導原則及勞動契約從屬性判斷檢核表（108年11月19日訂定），
已公告於勞動部勞動法令查詢系統...

相關法規:
- 勞動契約認定指導原則
- 勞動契約從屬性判斷檢核表
```

---

## 網站特殊處理

### 1. 勞動部常見問答

**URL**: https://www.mol.gov.tw/1607/28690/2282/nodeListSearch

**列表頁結構**:
- 表格式列表（`<table>` 標籤）
- 分頁機制（383 筆 / 39 頁，每頁 10 筆）
- 欄位: 項次、標題、次分類、發布單位、發布日期、更新日期、點閱人氣

**詳細頁結構**:
- 問題標題: `<h2>` 標籤
- 答案內容: 段落文字，包含超連結
- Metadata: 發布單位、發布日期、更新日期（底部）

**爬取策略**:
1. 解析表格行，提取標題和 URL
2. 處理分頁（39 頁）
3. 點擊標題進入詳細頁
4. 提取問題、答案、metadata

### 2. 勞保局常見問答

**URL**: https://www.bli.gov.tw/0100603.html

**目錄頁結構**:
- 樹狀結構（`<ul>/<li>` 嵌套）
- 主分類 → 次分類 → 細分類 → 問答
- 無分頁（全部內容以樹狀列表呈現）

**詳細頁結構**:
- 問題標題: `<h1>` 標籤
- 答案內容: 包含 `<h3>` 次標題、「小提醒」區塊
- 相關連結: 超連結形式
- 更新日期: 「最後更新日期：YYYY-MM-DD」（底部）

**爬取策略**:
1. 遞迴解析樹狀 `<ul>/<li>` 結構
2. 記錄分類路徑（主分類/次分類/細分類）
3. 提取所有問答連結
4. 爬取詳細頁，提取問題、答案、相關法規

### 3. 職安署常見問答

**URL**: https://www.osha.gov.tw/48110/48461/48463/nodelist

**目錄頁結構**:
- 10 個主分類（職業安全衛生管理、作業環境監測等）
- 每個分類連結到獨立列表頁

**列表頁結構**:
- 標題（超連結）
- 發布單位、更新/發布日期、點閱次數
- 分頁機制（如：14 筆 / 2 頁）

**爬取策略**:
1. 提取 10 個分類連結
2. 進入每個分類的列表頁
3. 處理分頁
4. 爬取詳細頁（結構待進一步分析）

---

## 增量更新機制

```python
from src.storage.jsonl_handler import JSONLHandler
from src.storage.index_manager import IndexManager

# 1. 讀取上次爬取日期
metadata = index_mgr.load_metadata('mol_faq')
last_date = metadata['last_crawl_date']

# 2. 只爬取新資料（updated_date > last_crawl_date）
new_items = crawler.crawl_since(last_date)

# 3. 追加儲存（append mode）
storage.write_items('mol_faq', new_items, mode='a')

# 4. 更新索引（只更新新增部分）
index_mgr.update_index('mol_faq', new_items)
```

---

## RAG 優化策略

### Plain Text 格式優勢

基於 **FSC 專案**的實測結果：
- ✅ Plain Text 比 Markdown 效果好 **40-60%**
- ✅ 語義密度高，無格式噪音
- ✅ Gemini File Search 原生支援，檢索準確

### 優化原則

**保留**:
- ✅ 問題標題（主要檢索目標）
- ✅ 答案內容（語義補充）
- ✅ 相關法規（延伸資訊）
- ✅ 來源/分類/日期（篩選條件）

**移除**:
- ❌ HTML 標籤、CSS class
- ❌ 點閱數、發布單位（對檢索無用）
- ❌ 麵包屑、導航列
- ❌ 網頁雜訊（Facebook、Line、友善列印等）

### 預期查詢效果

**用戶查詢**: 「公司不幫我保勞保怎麼辦」

**檢索結果**:
- 勞保局問答「受僱勞工要求公司不要幫他辦理勞保，想繼續在工會加保，可以嗎？」
- 勞動部問答「雇主未依規定為員工投保勞保，有何罰則？」

---

## 配置系統

### config/sources.yaml

定義所有資料源的配置：

```yaml
sources:
  mol_faq:
    name: "勞動部常見問答"
    list_url: "https://www.mol.gov.tw/1607/28690/2282/nodeListSearch"
    base_url: "https://www.mol.gov.tw"
    total_pages: 39
    items_per_page: 10

  bli_faq:
    name: "勞保局常見問答"
    list_url: "https://www.bli.gov.tw/0100603.html"
    base_url: "https://www.bli.gov.tw"
    structure: "tree"

  osha_faq:
    name: "職安署常見問答"
    list_url: "https://www.osha.gov.tw/48110/48461/48463/nodelist"
    base_url: "https://www.osha.gov.tw"
    categories: 10
```

### config/crawler.yaml

爬蟲行為配置：

```yaml
http:
  timeout: 30
  interval: 2.0          # 請求間隔（秒）
  retries: 3
  user_agent: "Mozilla/5.0 ..."

storage:
  format: "jsonl"
  encoding: "utf-8"

gemini:
  store_name: "labor-faqs"
  chunk_size: 2048
  delay: 2.0             # 上傳延遲（秒）
```

---

## 擴充新資料源

新增爬蟲步驟：

1. 在 `config/sources.yaml` 新增資料源配置
2. 建立 `src/crawlers/new_source.py` 繼承 `BaseLaborCrawler`
3. 實作三個必要方法:
   - `get_list_url(page)`: URL 生成邏輯
   - `parse_list_page(html)`: 列表頁解析
   - `parse_detail_page(html, list_item)`: 詳細頁解析
4. 資料自動儲存到 `data/new_source/`
5. 索引自動建立

---

## 待實作功能

### P0 核心功能（優先）
- [ ] 勞動部常見問答爬蟲 (`src/crawlers/mol_faq.py`)
- [ ] 勞保局常見問答爬蟲 (`src/crawlers/bli_faq.py`)
- [ ] Plain Text 優化器 (`src/processor/labor_plaintext_optimizer.py`)
- [ ] Gemini 上傳功能 (`scripts/upload_to_gemini.py`)

### P1 補充功能
- [ ] 職安署常見問答爬蟲 (`src/crawlers/osha_faq.py`)
- [ ] 增量更新機制
- [ ] RAG 查詢介面

### P2 進階功能
- [ ] 相關法規連結提取與標準化
- [ ] 問答關聯分析
- [ ] 自動分類優化

---

## 除錯工具

### 查看 JSONL 內容

```python
from src.storage.jsonl_handler import JSONLHandler
storage = JSONLHandler()

# 讀取所有
items = storage.read_all('mol_faq')

# 串流讀取（大檔案）
for item in storage.stream_read('mol_faq'):
    print(item['question'])

# 取得最後一筆
last = storage.get_last_item('mol_faq')
```

### 查詢索引

```python
from src.storage.index_manager import IndexManager
index_mgr = IndexManager()

# 取得特定日期的行號
line_numbers = index_mgr.get_items_by_date('mol_faq', '2025-09-03')

# 取得特定分類的統計
stats = index_mgr.get_items_by_category('mol_faq', '勞動契約')
```

---

## 日誌系統

專案使用 `loguru` 進行日誌記錄：

```python
from loguru import logger

# 設定日誌
logger.add(
    "logs/labor_crawler.log",
    rotation="100 MB",
    retention="30 days",
    level="DEBUG"
)

# 使用日誌
logger.info("開始爬取勞動部常見問答")
logger.debug(f"處理第 {page} 頁")
logger.error(f"爬取失敗: {e}")
```

日誌檔案位置: `logs/labor_crawler.log`

---

## 重要參考文件

- **WEBSITE_ANALYSIS.md**: 完整的網站結構分析文件（4,600+ 字）
- **SUMMARY.md**: 專案總結與實作計劃（1,500+ 字）
- **README.md**: 使用說明和快速開始

---

## 常見問題

### Q: 為什麼不爬取健保署常見問答？
A: 健保署網站使用 Cloudflare 防護，阻擋所有自動化請求。技術成本過高，已決定放棄此資料源。

### Q: 為什麼沒有附件下載功能？
A: 分析顯示，所有問答均為純文字內容，無實質附件。側邊欄的表單下載非問答專屬，處理無意義。

### Q: 如何與 FSC 專案整合查詢？
A: 未來可建立統一的查詢介面，Gemini API 支援同時查詢最多 5 個 File Search Stores。範例：
```python
file_search_store_names = [
    'fsc-penalties',
    'fsc-law-interpretations',
    'fsc-announcements',
    'labor-faqs'
]
```

---

## 開發指引

### 命名規範
- 檔案名稱: `snake_case`（如：`mol_faq.py`）
- 類別名稱: `PascalCase`（如：`MOLFaqCrawler`）
- 函數名稱: `snake_case`（如：`parse_list_page`）
- 變數名稱: 繁體中文或英文（如：`question`, `答案`）

### 註解規範
- 模組註解: 繁體中文，說明模組功能
- 函數註解: 繁體中文 docstring，說明參數、返回值
- 行內註解: 繁體中文，說明關鍵邏輯

### Git 提交規範
- 使用繁體中文
- 格式: `[類型] 簡短描述`
- 類型: `feat`, `fix`, `docs`, `refactor`, `test`
- 範例: `[feat] 新增勞動部常見問答爬蟲`

---

**IMPORTANT**: 本專案完全基於 **FSC 爬蟲專案**的成功架構和經驗。所有核心模組（`BaseCrawler`, `JSONLHandler`, `IndexManager`, `PlainTextOptimizer`）均可直接參考 FSC 專案實作。

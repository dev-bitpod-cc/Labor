"""勞保局常見問答爬蟲"""

from typing import List, Dict, Any
from bs4 import BeautifulSoup
from loguru import logger

from .base import BaseLaborCrawler
from ..utils.helpers import clean_text, parse_date, normalize_url, extract_related_laws


class BLIFaqCrawler(BaseLaborCrawler):
    """勞保局常見問答爬蟲（樹狀結構）"""

    def __init__(self, config: Dict[str, Any]):
        """
        初始化爬蟲

        Args:
            config: 配置字典
        """
        super().__init__(config)

        # 從配置載入 URL
        from ..utils.config_loader import ConfigLoader
        config_loader = ConfigLoader()
        source_config = config_loader.get_source_config('bli_faq')

        self.list_url = source_config.get('list_url')
        self.base_url = source_config.get('base_url', 'https://www.bli.gov.tw')

        # 禁用 SSL 驗證（政府網站憑證問題）
        self.session.verify = False

        # 禁用警告
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        logger.info("BLIFaqCrawler 初始化成功")

    def parse_tree_structure(self, html: str) -> List[Dict[str, Any]]:
        """
        解析樹狀結構，提取所有 FAQ 項目及其分類

        Args:
            html: HTML 內容

        Returns:
            FAQ 項目列表，包含分類資訊
        """
        soup = BeautifulSoup(html, 'html.parser')
        items = []

        # 策略：遍歷所有 <li> 元素，構建分類層級
        # 使用遞迴方式解析樹狀結構

        def parse_list_recursive(ul_elem, category_path: List[str] = None):
            """
            遞迴解析 <ul> 元素

            Args:
                ul_elem: <ul> 元素
                category_path: 當前分類路徑（如 ['勞工保險', '加保問題']）
            """
            if category_path is None:
                category_path = []

            if not ul_elem:
                return

            # 遍歷所有 <li> 子元素
            for li in ul_elem.find_all('li', recursive=False):
                # 找 <a> 標籤
                link = li.find('a', recursive=False)
                if not link:
                    continue

                href = link.get('href', '')
                text = clean_text(link.get_text())

                if not text:
                    continue

                # 判斷是分類還是 FAQ 項目
                # 分類：href 是 javascript:void(0)
                # FAQ：href 是真實的 URL（如 /0017380.html）
                if 'javascript:void(0)' in href or not href:
                    # 這是分類節點，遞迴處理子節點
                    sub_ul = li.find('ul', recursive=False)
                    if sub_ul:
                        # 將當前分類加入路徑
                        new_path = category_path + [text]
                        parse_list_recursive(sub_ul, new_path)
                else:
                    # 這是 FAQ 項目
                    # 建立完整 URL
                    detail_url = normalize_url(href, self.base_url)

                    # 確定分類
                    main_category = category_path[0] if len(category_path) >= 1 else ''
                    sub_category = category_path[1] if len(category_path) >= 2 else ''

                    item = {
                        'question': text,
                        'detail_url': detail_url,
                        'category': main_category,
                        'subcategory': sub_category,
                        'category_path': ' > '.join(category_path),  # 完整路徑
                    }

                    items.append(item)

        # 找到主要的 FAQ 列表
        # BLI 使用 div.content 內的 ul.multilevel-list
        main_list = soup.select_one('div.content ul.multilevel-list')

        if not main_list:
            # 備用選擇器
            main_list = soup.select_one('div.content ul')

        if main_list:
            logger.debug(f"找到主列表: ul.multilevel-list")
            parse_list_recursive(main_list)
        else:
            logger.warning("未找到主列表")

        logger.info(f"解析樹狀結構: 找到 {len(items)} 筆 FAQ")
        return items

    def get_list_url(self, page: int, **kwargs) -> str:
        """
        生成列表頁 URL（BLI 使用單一樹狀頁面，不分頁）

        Args:
            page: 頁碼（固定為 1）
            **kwargs: 其他參數

        Returns:
            列表頁 URL
        """
        return self.list_url

    def parse_list_page(self, html: str) -> List[Dict[str, Any]]:
        """
        解析列表頁（樹狀結構頁面）

        Args:
            html: HTML 內容

        Returns:
            FAQ 項目列表
        """
        return self.parse_tree_structure(html)

    def parse_detail_page(self, html: str, list_item: Dict[str, Any]) -> Dict[str, Any]:
        """
        解析詳細頁

        Args:
            html: HTML 內容
            list_item: 列表頁的項目資料

        Returns:
            完整的資料
        """
        soup = BeautifulSoup(html, 'html.parser')

        # 基本資料
        detail = list_item.copy()

        try:
            # 提取問題標題（<h1> 或 <h2> 標籤）
            question_elem = soup.find('h1')
            if not question_elem:
                question_elem = soup.find('h2')

            if question_elem:
                question = clean_text(question_elem.get_text())
                if question:
                    detail['question'] = question

            # 提取答案內容
            # 策略：找主要內容區域
            content_area = None

            # 嘗試多種選擇器
            for selector in ['div.main', 'div.content', 'article', 'main']:
                content_area = soup.select_one(selector)
                if content_area:
                    break

            if content_area:
                # 提取答案文字
                answer_text = content_area.get_text(separator='\n', strip=True)

                # 清理答案（移除問題部分）
                if detail.get('question'):
                    answer_text = answer_text.replace(detail['question'], '', 1).strip()

                # 提取答案 HTML（截短）
                answer_html = str(content_area)[:10000]

                detail['answer'] = {
                    'text': answer_text,
                    'html': answer_html
                }

                # 提取相關法規連結
                related_laws = []
                for link in content_area.find_all('a', href=True):
                    link_text = clean_text(link.get_text())
                    href = link.get('href')

                    # 如果連結文字看起來像法規名稱
                    if any(keyword in link_text for keyword in ['法', '辦法', '規則', '條例', '細則']):
                        related_laws.append({
                            'name': link_text,
                            'url': normalize_url(href, self.base_url)
                        })

                detail['related_laws'] = related_laws

                # 從答案文字中提取相關法規（沒有連結的）
                law_names = extract_related_laws(answer_text)
                for law_name in law_names:
                    # 避免重複
                    if not any(law['name'] == law_name for law in related_laws):
                        related_laws.append({'name': law_name, 'url': ''})

            else:
                logger.warning(f"未找到內容區域: {list_item.get('detail_url')}")
                detail['answer'] = {'text': '', 'html': ''}
                detail['related_laws'] = []

            # 提取發布日期（如果有）
            # BLI 可能在頁面底部或特定位置顯示日期
            date_patterns = [
                r'發布日期[：:]?\s*(\d{4}[-/]\d{2}[-/]\d{2})',
                r'更新日期[：:]?\s*(\d{4}[-/]\d{2}[-/]\d{2})',
                r'(\d{4}[-/]\d{2}[-/]\d{2})'
            ]

            import re
            page_text = soup.get_text()
            for pattern in date_patterns:
                match = re.search(pattern, page_text)
                if match:
                    date_str = match.group(1).replace('/', '-')
                    detail['metadata'] = detail.get('metadata', {})
                    detail['metadata']['updated_date'] = parse_date(date_str)
                    break

        except Exception as e:
            logger.error(f"解析詳細頁失敗: {list_item.get('detail_url')} - {e}")
            import traceback
            logger.debug(traceback.format_exc())

        # 添加來源標記
        detail['source'] = 'bli'

        return detail

    def crawl_all(self, source_name: str = 'bli') -> List[Dict[str, Any]]:
        """
        爬取所有 FAQ（BLI 使用單一頁面樹狀結構）

        Args:
            source_name: 資料源名稱

        Returns:
            所有資料列表
        """
        from ..utils.helpers import generate_id

        logger.info(f"\n{'='*70}")
        logger.info(f"開始爬取勞保局常見問答")
        logger.info(f"{'='*70}")

        # 1. 爬取主頁並解析樹狀結構
        logger.info(f"爬取主頁: {self.list_url}")
        response = self.fetch_with_retry(self.list_url)

        if not response:
            logger.error("主頁請求失敗")
            return []

        # 2. 解析樹狀結構，獲取所有 FAQ 項目
        items = self.parse_tree_structure(response.text)

        if not items:
            logger.warning("未找到任何 FAQ 項目")
            return []

        logger.info(f"找到 {len(items)} 筆 FAQ")

        # 3. 爬取每個 FAQ 的詳細頁
        all_data = []
        for i, item in enumerate(items, 1):
            logger.info(f"[{i}/{len(items)}] 爬取: {item['question'][:50]}...")

            # 爬取詳細頁 - fetch_detail 已經呼叫 parse_detail_page 並回傳解析後的 dict
            detail = self.fetch_detail(item['detail_url'], item)
            if detail:
                all_data.append(detail)
            else:
                logger.warning(f"詳細頁爬取失敗: {item['detail_url']}")

            # 控制爬取速度
            if i < len(items):
                import time
                time.sleep(self.request_interval)

        # 4. 生成唯一 ID
        logger.info(f"\n生成唯一 ID...")
        date_counters = {}
        for item in all_data:
            date = item.get('metadata', {}).get('updated_date', 'unknown')

            if date not in date_counters:
                date_counters[date] = 0
            date_counters[date] += 1

            item['id'] = generate_id(source_name, date, date_counters[date])

        logger.info(f"\n爬取完成: 共 {len(all_data)} 筆資料")
        logger.info(f"請求統計: {self.stats}")

        return all_data

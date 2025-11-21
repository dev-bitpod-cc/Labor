"""職安署常見問答爬蟲"""

from typing import List, Dict, Any
from bs4 import BeautifulSoup
from loguru import logger

from .base import BaseLaborCrawler
from ..utils.helpers import clean_text, parse_date, normalize_url, extract_related_laws


class OSHAFaqCrawler(BaseLaborCrawler):
    """職安署常見問答爬蟲"""

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
        source_config = config_loader.get_source_config('osha_faq')

        self.base_url = source_config.get('base_url', 'https://www.osha.gov.tw')
        self.index_url = source_config.get('index_url')

        # 禁用 SSL 驗證（政府網站憑證問題）
        self.session.verify = False

        # 禁用警告
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        # 儲存分類資訊
        self.categories = []

        logger.info("OSHAFaqCrawler 初始化成功")

    def get_categories(self) -> List[Dict[str, str]]:
        """
        取得所有分類（遞迴爬取多層結構）

        Returns:
            分類列表 [{'name': '分類名稱', 'url': 'URL', 'type': 'lpsimplelist|post'}, ...]
            只返回最終的 FAQ 列表頁（lpsimplelist）或單個 FAQ（post）
        """
        if self.categories:
            return self.categories

        logger.info(f"爬取分類頁: {self.index_url}")

        # 遞迴爬取所有層級
        all_endpoints = []
        visited_urls = set()
        endpoint_urls = set()  # 用於去重端點

        def crawl_category_recursive(url: str, parent_name: str = '', depth: int = 0):
            """遞迴爬取分類頁面"""
            if url in visited_urls:
                return
            if depth > 5:  # 防止無限遞迴
                logger.warning(f"達到最大遞迴深度: {url}")
                return

            visited_urls.add(url)

            logger.debug(f"{'  ' * depth}爬取: {url}")
            response = self.fetch_with_retry(url)

            if not response:
                logger.warning(f"請求失敗: {url}")
                return

            soup = BeautifulSoup(response.text, 'html.parser')

            # 找到所有 FAQ 相關的連結
            all_links = soup.find_all('a', href=True)

            for link in all_links:
                href = link.get('href', '')
                name = clean_text(link.get_text())

                if not name or not href:
                    continue

                # 過濾非 FAQ 連結
                if any(keyword in name for keyword in ['回上', '列印', '轉寄', '分享', '首頁', '導覽', 'English', '小', '中', '大', '搜尋', '進階']):
                    continue

                # 只處理 FAQ 路徑下的連結
                if '/48110/48461/48463/' not in href:
                    continue

                full_url = normalize_url(href, self.base_url)

                # 根據 URL 類型決定處理方式
                if 'lpsimplelist' in href:
                    # 這是 FAQ 列表頁，加入結果（去重）
                    if full_url not in endpoint_urls:
                        endpoint_urls.add(full_url)
                        all_endpoints.append({
                            'name': name,
                            'url': full_url,
                            'type': 'lpsimplelist'
                        })
                        logger.debug(f"{'  ' * depth}  [列表] {name}")

                elif href.endswith('/post'):
                    # 這是單個 FAQ，加入結果（去重）
                    if full_url not in endpoint_urls:
                        endpoint_urls.add(full_url)
                        all_endpoints.append({
                            'name': name,
                            'url': full_url,
                            'type': 'post'
                        })
                        logger.debug(f"{'  ' * depth}  [單篇] {name}")

                elif 'nodelist' in href:
                    # 這是子分類頁，需要遞迴（避免重複遞迴）
                    if full_url not in visited_urls:
                        new_parent = f"{parent_name} > {name}" if parent_name else name
                        logger.debug(f"{'  ' * depth}  [分類] {name} → 遞迴")

                        import time
                        time.sleep(self.request_interval)
                        crawl_category_recursive(full_url, new_parent, depth + 1)

        # 從主頁開始遞迴
        crawl_category_recursive(self.index_url)

        logger.info(f"找到 {len(all_endpoints)} 個 FAQ 端點（已去重）")
        for i, ep in enumerate(all_endpoints, 1):
            logger.debug(f"  [{i}] [{ep['type']}] {ep['name']}: {ep['url']}")

        self.categories = all_endpoints
        return all_endpoints

    def get_list_url(self, page: int, **kwargs) -> str:
        """
        生成列表頁 URL（OSHA 使用分類，不是單一列表）

        Args:
            page: 頁碼
            **kwargs: 必須包含 category_url

        Returns:
            列表頁 URL
        """
        category_url = kwargs.get('category_url')
        if not category_url:
            raise ValueError("需要提供 category_url")

        # OSHA 的分頁 URL 格式（如果有的話，需要根據實際情況調整）
        # 目前先假設沒有分頁參數，或者在列表頁中處理
        return category_url

    def parse_list_page(self, html: str) -> List[Dict[str, Any]]:
        """
        解析列表頁

        Args:
            html: HTML 內容

        Returns:
            資料列表
        """
        soup = BeautifulSoup(html, 'html.parser')
        items = []

        # 根據 WebFetch 分析：問答項目是 <a> 標籤，包含「發布單位」、「更新日期」等 metadata
        # 策略：找所有 <a> 標籤，過濾出真正的問答項目

        # 先找主要內容區域
        content_area = None
        for selector in ['div.page_content', 'div.content', 'main', 'article']:
            content_area = soup.select_one(selector)
            if content_area:
                break

        if not content_area:
            content_area = soup

        # 找所有 <a> 標籤
        all_links = content_area.find_all('a', href=True)

        logger.debug(f"找到 {len(all_links)} 個連結")

        for link in all_links:
            try:
                href = link.get('href')
                title = clean_text(link.get_text())

                if not href or not title:
                    continue

                # **關鍵過濾條件 1**：URL 必須是詳細頁（/post 結尾）
                if not href.endswith('/post'):
                    continue

                logger.debug(f"通過 /post 過濾: {href[:50]}...")

                # **關鍵過濾條件 2**：URL 必須在 FAQ 路徑下
                if '/48110/48461/48463/' not in href:
                    logger.debug(f"未通過路徑過濾: {href}")
                    continue

                logger.debug(f"通過路徑過濾: {title[:30]}...")

                # 過濾導航連結
                if any(keyword in title for keyword in ['回上', '列印', '轉寄', '分享', '首頁', '上一頁', '下一頁']):
                    continue

                # 建立詳細頁 URL
                detail_url = normalize_url(href, self.base_url)

                # 提取 metadata（在 grandparent 中，不是 parent）
                # 根據調試：metadata 在 parent.parent 中
                parent = link.parent
                grandparent = parent.parent if parent else None
                item_text = grandparent.get_text() if grandparent else ''

                department = ''
                published_date = None
                updated_date = None

                # **關鍵過濾條件 3**：問答項目應該包含「發布單位」或「更新日期」
                if '發布單位' not in item_text and '更新日期' not in item_text and '發布日期' not in item_text:
                    continue

                # 提取發布單位
                if '發布單位' in item_text:
                    # 格式：「發布單位：綜合規劃組」
                    import re
                    match = re.search(r'發布單位[：:]\s*([^\s]+)', item_text)
                    if match:
                        department = match.group(1).strip()

                # 提取發布日期
                if '發布日期' in item_text:
                    match = re.search(r'發布日期[：:]\s*(\d{4}-\d{2}-\d{2})', item_text)
                    if match:
                        published_date = parse_date(match.group(1))

                # 提取更新日期
                if '更新日期' in item_text:
                    match = re.search(r'更新日期[：:]\s*(\d{4}-\d{2}-\d{2})', item_text)
                    if match:
                        updated_date = parse_date(match.group(1))

                item_data = {
                    'question': title,
                    'detail_url': detail_url,
                    'metadata': {
                        'department': department,
                        'published_date': published_date,
                        'updated_date': updated_date
                    }
                }

                items.append(item_data)

            except Exception as e:
                logger.error(f"解析列表項失敗: {e}")
                continue

        logger.debug(f"解析列表頁: 找到 {len(items)} 筆資料")
        return items

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
            # 提取問題標題（優先 <h2>，OSHA 使用 h2）
            question_elem = soup.find('h2')
            if not question_elem:
                question_elem = soup.find('h1')

            if question_elem:
                question = clean_text(question_elem.get_text())
                if question:  # 確保不是空字串
                    detail['question'] = question

            # 提取答案內容（與 MOL 類似的策略）
            content_area = None

            # 策略 1: 嘗試找 <article> 標籤
            content_area = soup.find('article')

            # 策略 2: 如果沒有 article，找問題標籤的父容器
            if not content_area and question_elem:
                parent = question_elem.parent
                while parent and parent.name not in ['body', 'html']:
                    # 檢查是否包含答案內容（p 或 ol 標籤）
                    if len(parent.find_all(['p', 'ol', 'ul'])) >= 1:
                        content_area = parent
                        break
                    parent = parent.parent

            # 策略 3: 最後嘗試找 main 標籤
            if not content_area:
                content_area = soup.find('main')

            if content_area:
                # 優先從特定區域提取答案
                answer_text = ''
                answer_html = ''

                # 嘗試找答案區域（可能在 ol、ul 或 p 標籤中）
                answer_section = content_area.find(['ol', 'ul', 'div'])
                if answer_section:
                    answer_text = answer_section.get_text(separator='\n', strip=True)
                    answer_html = str(answer_section)[:10000]
                else:
                    # 直接使用整個內容區域
                    answer_text = content_area.get_text(separator='\n', strip=True)
                    answer_html = str(content_area)[:10000]

                # 清理答案（移除問題部分）
                if detail.get('question'):
                    answer_text = answer_text.replace(detail['question'], '', 1).strip()

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

            # 提取分類（從 URL 或麵包屑）
            # OSHA 的分類在爬取時已知，儲存在 kwargs 中
            if 'category' not in detail and detail.get('subcategory'):
                detail['category'] = detail['subcategory']

        except Exception as e:
            logger.error(f"解析詳細頁失敗: {list_item.get('detail_url')} - {e}")
            import traceback
            logger.debug(traceback.format_exc())

        # 添加來源標記
        detail['source'] = 'osha'

        return detail

    def crawl_all_categories(
        self,
        source_name: str = 'osha',
        max_pages_per_category: int = None
    ) -> List[Dict[str, Any]]:
        """
        爬取所有分類的常見問答（支援多層結構）

        Args:
            source_name: 資料源名稱
            max_pages_per_category: 每個分類最大頁數

        Returns:
            所有資料列表
        """
        from ..utils.helpers import generate_id
        import time

        # 1. 取得所有端點（遞迴爬取多層結構）
        endpoints = self.get_categories()

        if not endpoints:
            logger.error("無法取得分類資訊")
            return []

        # 2. 爬取每個端點
        all_data = []

        for i, endpoint in enumerate(endpoints, 1):
            logger.info(f"\n{'='*70}")
            logger.info(f"[{i}/{len(endpoints)}] [{endpoint['type']}] {endpoint['name']}")
            logger.info(f"{'='*70}")

            if endpoint['type'] == 'lpsimplelist':
                # FAQ 列表頁，爬取列表中的所有項目
                items = self.crawl_page(
                    page=1,
                    category_url=endpoint['url'],
                    category_name=endpoint['name']
                )

                # 為每個項目添加分類資訊
                for item in items:
                    item['category'] = endpoint['name']

                all_data.extend(items)
                logger.info(f"✓ 列表頁完成: {len(items)} 筆")

            elif endpoint['type'] == 'post':
                # 單個 FAQ，直接爬取詳細頁
                list_item = {
                    'question': endpoint['name'].split(' > ')[-1],  # 取最後一段作為問題
                    'detail_url': endpoint['url'],
                    'category': endpoint['name'],
                }

                detail = self.fetch_detail(endpoint['url'], list_item)
                if detail:
                    detail['category'] = endpoint['name']
                    all_data.append(detail)
                    logger.info(f"✓ 單篇 FAQ 完成")
                else:
                    logger.warning(f"✗ 單篇 FAQ 爬取失敗")

            # 控制爬取速度
            if i < len(endpoints):
                time.sleep(self.request_interval)

        # 3. 生成唯一 ID
        logger.info(f"\n生成唯一 ID...")
        date_counters = {}
        for item in all_data:
            date = item.get('metadata', {}).get('updated_date')
            if not date:
                date = item.get('metadata', {}).get('published_date', 'unknown')

            if date not in date_counters:
                date_counters[date] = 0
            date_counters[date] += 1

            item['id'] = generate_id(source_name, date, date_counters[date])

        logger.info(f"\n爬取完成: 共 {len(all_data)} 筆資料")
        logger.info(f"請求統計: {self.stats}")

        return all_data

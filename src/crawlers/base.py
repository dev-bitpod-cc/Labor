"""爬蟲抽象基類"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import requests
import time
from loguru import logger


class BaseLaborCrawler(ABC):
    """勞動法規爬蟲抽象基類"""

    def __init__(self, config: Dict[str, Any]):
        """
        初始化爬蟲

        Args:
            config: 配置字典
        """
        self.config = config
        self.session = requests.Session()

        # 設定 HTTP headers
        http_config = config.get('http', {})
        user_agent = http_config.get('user_agent', 'Mozilla/5.0')
        self.session.headers.update({'User-Agent': user_agent})

        # 請求參數
        self.timeout = http_config.get('timeout', 30)
        self.request_interval = http_config.get('interval', 2.0)
        self.max_retries = http_config.get('retries', 3)

        # 統計資訊
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
        }

    @abstractmethod
    def get_list_url(self, page: int, **kwargs) -> str:
        """
        生成列表頁 URL

        Args:
            page: 頁碼
            **kwargs: 其他參數

        Returns:
            列表頁 URL
        """
        pass

    @abstractmethod
    def parse_list_page(self, html: str) -> List[Dict[str, Any]]:
        """
        解析列表頁

        Args:
            html: HTML 內容

        Returns:
            資料列表（包含 detail_url）
        """
        pass

    @abstractmethod
    def parse_detail_page(self, html: str, list_item: Dict[str, Any]) -> Dict[str, Any]:
        """
        解析詳細頁

        Args:
            html: HTML 內容
            list_item: 列表頁的項目資料

        Returns:
            完整的資料
        """
        pass

    def fetch_with_retry(self, url: str, method: str = 'GET', **kwargs) -> Optional[requests.Response]:
        """
        發送 HTTP 請求並自動重試

        Args:
            url: 目標 URL
            method: HTTP 方法 (GET/POST)
            **kwargs: requests 參數

        Returns:
            Response 物件或 None
        """
        for attempt in range(self.max_retries):
            try:
                self.stats['total_requests'] += 1

                # 發送請求
                if method.upper() == 'GET':
                    response = self.session.get(url, timeout=self.timeout, **kwargs)
                elif method.upper() == 'POST':
                    response = self.session.post(url, timeout=self.timeout, **kwargs)
                else:
                    raise ValueError(f"不支援的 HTTP 方法: {method}")

                response.raise_for_status()
                self.stats['successful_requests'] += 1

                # 請求間隔
                time.sleep(self.request_interval)

                return response

            except requests.exceptions.RequestException as e:
                self.stats['failed_requests'] += 1

                if attempt == self.max_retries - 1:
                    logger.error(f"請求失敗 (已重試 {self.max_retries} 次): {url} - {e}")
                    return None

                wait_time = 2 ** attempt  # 指數退避
                logger.warning(f"請求失敗,{wait_time}秒後重試 (第 {attempt + 1}/{self.max_retries} 次): {url}")
                time.sleep(wait_time)

        return None

    def fetch_detail(self, detail_url: str, list_item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        取得詳細頁資料

        Args:
            detail_url: 詳細頁 URL
            list_item: 列表頁的項目資料

        Returns:
            完整的資料或 None
        """
        logger.debug(f"爬取詳細頁: {detail_url}")

        response = self.fetch_with_retry(detail_url)

        if not response:
            logger.error(f"詳細頁請求失敗: {detail_url}")
            return None

        # 解析詳細頁
        try:
            detail = self.parse_detail_page(response.text, list_item)
            return detail

        except Exception as e:
            logger.error(f"詳細頁解析失敗: {detail_url} - {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None

    def crawl_page(self, page: int, **kwargs) -> List[Dict[str, Any]]:
        """
        爬取單頁列表

        Args:
            page: 頁碼
            **kwargs: 其他參數

        Returns:
            該頁的資料列表（包含詳細內容）
        """
        url = self.get_list_url(page, **kwargs)
        logger.info(f"爬取列表頁: Page {page}")

        response = self.fetch_with_retry(url)

        if not response:
            logger.error(f"列表頁請求失敗: Page {page}")
            return []

        # 解析列表頁
        try:
            items = self.parse_list_page(response.text)
            logger.info(f"列表頁解析成功: Page {page} - 找到 {len(items)} 筆資料")

            # 爬取每個項目的詳細頁面
            results = []
            for item in items:
                detail_url = item.get('detail_url')
                if not detail_url:
                    logger.warning(f"缺少 detail_url: {item.get('question', 'N/A')}")
                    continue

                detail = self.fetch_detail(detail_url, item)
                if detail:
                    detail['page'] = page
                    results.append(detail)

            logger.info(f"✓ 第 {page} 頁完成: {len(results)}/{len(items)} 筆")
            return results

        except Exception as e:
            logger.error(f"列表頁解析失敗: Page {page} - {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return []

    def crawl_all(
        self,
        start_page: int = 1,
        max_pages: Optional[int] = None,
        source_name: str = 'mol',
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        爬取多頁資料

        Args:
            start_page: 起始頁碼
            max_pages: 最大頁數 (None 表示爬到最後)
            source_name: 資料源名稱 (mol, bli, osha)
            **kwargs: 其他參數

        Returns:
            所有資料列表
        """
        from ..utils.helpers import generate_id

        all_data = []
        logger.info(f"開始爬取: 從第 {start_page} 頁開始")

        page = start_page
        while True:
            # 檢查是否達到最大頁數
            if max_pages and page >= start_page + max_pages:
                logger.info(f"已達到最大頁數限制: {max_pages}")
                break

            # 爬取單頁
            items = self.crawl_page(page, **kwargs)

            # 如果沒有資料,表示已到最後
            if not items:
                logger.info(f"第 {page} 頁無資料,停止爬取")
                break

            all_data.extend(items)
            page += 1

        # 生成唯一 ID
        logger.info(f"生成唯一 ID...")
        date_counters = {}
        for item in all_data:
            date = item.get('metadata', {}).get('updated_date')
            if not date:
                date = item.get('metadata', {}).get('published_date', 'unknown')

            if date not in date_counters:
                date_counters[date] = 0
            date_counters[date] += 1

            item['id'] = generate_id(source_name, date, date_counters[date])

        logger.info(f"爬取完成: 共 {len(all_data)} 筆資料")
        logger.info(f"請求統計: {self.stats}")

        return all_data

    def get_stats(self) -> Dict[str, int]:
        """取得統計資訊"""
        return self.stats.copy()

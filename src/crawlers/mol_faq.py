"""勞動部常見問答爬蟲"""

from typing import List, Dict, Any
from bs4 import BeautifulSoup
from loguru import logger

from .base import BaseLaborCrawler
from ..utils.helpers import clean_text, parse_date, normalize_url, extract_related_laws


class MOLFaqCrawler(BaseLaborCrawler):
    """勞動部常見問答爬蟲"""

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
        source_config = config_loader.get_source_config('mol_faq')

        self.base_url = source_config.get('base_url', 'https://www.mol.gov.tw')
        self.list_url = source_config.get('list_url')

        # 禁用 SSL 驗證（政府網站憑證問題）
        self.session.verify = False

        # 禁用警告
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        logger.info("MOLFaqCrawler 初始化成功")

    def get_list_url(self, page: int, **kwargs) -> str:
        """
        生成列表頁 URL

        Args:
            page: 頁碼

        Returns:
            列表頁 URL
        """
        return self.list_url

    def parse_list_page(self, html: str) -> List[Dict[str, Any]]:
        """
        解析列表頁（表格式）

        Args:
            html: HTML 內容

        Returns:
            資料列表
        """
        soup = BeautifulSoup(html, 'html.parser')
        items = []

        # 找到表格
        table = soup.find('table')
        if not table:
            logger.warning("未找到表格")
            return []

        # 解析表格行（跳過表頭）
        rows = table.find_all('tr')[1:]  # 跳過第一行表頭

        for row in rows:
            try:
                cells = row.find_all('td')
                if len(cells) < 6:
                    continue

                # 提取欄位
                # 項次、標題、次分類、發布單位、發布日期、更新日期
                index = clean_text(cells[0].get_text())
                title_cell = cells[1]
                subcategory = clean_text(cells[2].get_text())
                department = clean_text(cells[3].get_text())
                published_date_str = clean_text(cells[4].get_text())
                updated_date_str = clean_text(cells[5].get_text())

                # 提取標題和連結
                link = title_cell.find('a')
                if not link:
                    continue

                title = clean_text(link.get_text())
                href = link.get('href')
                detail_url = normalize_url(href, self.base_url)

                # 解析日期
                published_date = parse_date(published_date_str)
                updated_date = parse_date(updated_date_str)

                item = {
                    'list_index': index,
                    'question': title,  # 問題即標題
                    'subcategory': subcategory,
                    'detail_url': detail_url,
                    'metadata': {
                        'department': department,
                        'published_date': published_date,
                        'updated_date': updated_date
                    }
                }

                items.append(item)

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
            # 提取問題標題（<h2> 標籤）
            question_elem = soup.find('h2')
            if question_elem:
                question = clean_text(question_elem.get_text())
                detail['question'] = question

            # 提取答案內容
            # 查找主要內容區域（根據 WebFetch 分析更新選擇器）
            content_area = None

            # 策略 1: 嘗試找 <article> 標籤
            content_area = soup.find('article')

            # 策略 2: 如果沒有 article，找 <h2> 的父容器
            if not content_area and question_elem:
                # 向上找到包含完整內容的容器（通常是 div 或 main）
                parent = question_elem.parent
                while parent and parent.name not in ['body', 'html']:
                    # 檢查是否包含多個 p 標籤（表示這是內容容器）
                    if len(parent.find_all('p')) >= 1:
                        content_area = parent
                        break
                    parent = parent.parent

            # 策略 3: 最後嘗試找 main 標籤
            if not content_area:
                content_area = soup.find('main')

            if content_area:
                # 優先從 <table> 的「答案」欄位提取（更精確，無雜訊）
                answer_text = ''
                answer_html = ''

                table = content_area.find('table')
                if table:
                    # 找到「答案」的 th，使用正則表達式匹配
                    import re
                    answer_th = None
                    for th in table.find_all('th'):
                        if re.search(r'答案', th.get_text()):
                            answer_th = th
                            break

                    if answer_th:
                        # 取得下一個 td
                        answer_td = answer_th.find_next('td')
                        if answer_td:
                            # 提取純文字（從 <p> 或直接從 <td>）
                            answer_text = answer_td.get_text(separator='\n', strip=True)
                            answer_html = str(answer_td)[:10000]

                # 如果沒有找到 table 或答案欄位，使用整個內容區域
                if not answer_text:
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
                    if any(keyword in link_text for keyword in ['法', '辦法', '規則', '條例']):
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

            # 提取分類（從麵包屑或側邊欄）
            breadcrumb = soup.select('.breadcrumb a, nav a')
            if breadcrumb and len(breadcrumb) >= 2:
                # 通常最後第二個是主分類
                main_category = clean_text(breadcrumb[-2].get_text())
                if main_category and main_category != '常見問答':
                    detail['category'] = main_category

            # 如果沒有分類，使用次分類作為主分類
            if 'category' not in detail and detail.get('subcategory'):
                detail['category'] = detail['subcategory']

        except Exception as e:
            logger.error(f"解析詳細頁失敗: {list_item.get('detail_url')} - {e}")
            import traceback
            logger.debug(traceback.format_exc())

        # 添加來源標記
        detail['source'] = 'mol'

        return detail

"""索引管理模組"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from collections import defaultdict
from loguru import logger


class IndexManager:
    """索引管理器 - 提供快速查詢能力"""

    def __init__(self, data_dir: str = "data"):
        """
        初始化索引管理器

        Args:
            data_dir: 資料目錄
        """
        self.data_dir = Path(data_dir)

    def get_index_path(self, source: str) -> Path:
        """取得索引檔案路徑"""
        return self.data_dir / source / "index.json"

    def get_metadata_path(self, source: str) -> Path:
        """取得 metadata 檔案路徑"""
        return self.data_dir / source / "metadata.json"

    def load_index(self, source: str) -> Dict[str, Any]:
        """
        載入索引

        Args:
            source: 資料源名稱

        Returns:
            索引字典
        """
        index_path = self.get_index_path(source)

        if not index_path.exists():
            logger.info(f"索引檔案不存在,返回空索引: {index_path}")
            return self._create_empty_index()

        try:
            with open(index_path, 'r', encoding='utf-8') as f:
                return json.load(f)

        except Exception as e:
            logger.error(f"載入索引失敗: {e}")
            return self._create_empty_index()

    def save_index(self, source: str, index: Dict[str, Any]):
        """
        儲存索引

        Args:
            source: 資料源名稱
            index: 索引字典
        """
        index_path = self.get_index_path(source)
        index_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(index_path, 'w', encoding='utf-8') as f:
                json.dump(index, f, ensure_ascii=False, indent=2)

            logger.info(f"索引已儲存: {index_path}")

        except Exception as e:
            logger.error(f"儲存索引失敗: {e}")
            raise

    def load_metadata(self, source: str) -> Dict[str, Any]:
        """
        載入 metadata

        Args:
            source: 資料源名稱

        Returns:
            metadata 字典
        """
        metadata_path = self.get_metadata_path(source)

        if not metadata_path.exists():
            logger.info(f"Metadata 不存在,返回預設值: {metadata_path}")
            return self._create_empty_metadata(source)

        try:
            with open(metadata_path, 'r', encoding='utf-8') as f:
                return json.load(f)

        except Exception as e:
            logger.error(f"載入 metadata 失敗: {e}")
            return self._create_empty_metadata(source)

    def save_metadata(self, source: str, metadata: Dict[str, Any]):
        """
        儲存 metadata

        Args:
            source: 資料源名稱
            metadata: metadata 字典
        """
        metadata_path = self.get_metadata_path(source)
        metadata_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)

            logger.info(f"Metadata 已儲存: {metadata_path}")

        except Exception as e:
            logger.error(f"儲存 metadata 失敗: {e}")
            raise

    def build_index(self, source: str, items: List[Dict[str, Any]]):
        """
        從資料建立索引

        Args:
            source: 資料源名稱
            items: 資料列表
        """
        logger.info(f"開始建立索引: {source} - {len(items)} 筆資料")

        index = self._create_empty_index()

        # 按日期索引 (updated_date)
        by_date = defaultdict(lambda: {'line_numbers': [], 'count': 0})

        # 按分類索引
        by_category = defaultdict(lambda: {'count': 0, 'latest_line': 0})

        # 按 ID 索引
        by_id = {}

        for line_num, item in enumerate(items, 1):
            # 日期索引 (使用 updated_date)
            date = item.get('metadata', {}).get('updated_date') or item.get('metadata', {}).get('published_date')
            if date:
                by_date[date]['line_numbers'].append(line_num)
                by_date[date]['count'] += 1

            # 分類索引
            category = item.get('category')
            if category:
                by_category[category]['count'] += 1
                by_category[category]['latest_line'] = line_num

            # ID 索引
            if 'id' in item:
                by_id[item['id']] = {
                    'line': line_num,
                    'date': date,
                    'category': category
                }

        # 轉換為普通字典
        index['by_date'] = dict(by_date)
        index['by_category'] = dict(by_category)
        index['by_id'] = by_id

        # 儲存索引
        self.save_index(source, index)

        # 更新 metadata
        metadata = self.load_metadata(source)
        metadata['total_count'] = len(items)
        metadata['last_index_build'] = datetime.now().isoformat()

        if items:
            # 日期範圍
            dates = []
            for item in items:
                date = item.get('metadata', {}).get('updated_date') or item.get('metadata', {}).get('published_date')
                if date:
                    dates.append(date)

            if dates:
                metadata['date_range'] = [min(dates), max(dates)]

            # 最後一筆
            last_item = items[-1]
            last_date = last_item.get('metadata', {}).get('updated_date')
            if last_date:
                metadata['last_crawl_date'] = last_date
            if 'id' in last_item:
                metadata['last_id'] = last_item['id']

        self.save_metadata(source, metadata)

        logger.info(f"索引建立完成: {source}")

    def _create_empty_index(self) -> Dict[str, Any]:
        """建立空索引結構"""
        return {
            'by_date': {},
            'by_category': {},
            'by_id': {}
        }

    def _create_empty_metadata(self, source: str) -> Dict[str, Any]:
        """建立空 metadata 結構"""
        return {
            'data_type': source,
            'total_count': 0,
            'last_crawl_date': None,
            'last_id': None,
            'date_range': [None, None],
            'created_at': datetime.now().isoformat()
        }

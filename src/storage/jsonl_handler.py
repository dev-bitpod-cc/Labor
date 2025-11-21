"""JSONL 儲存處理模組"""

import json
from pathlib import Path
from typing import List, Dict, Any, Iterator, Optional
from datetime import datetime
from loguru import logger


class JSONLHandler:
    """JSONL 檔案處理器"""

    def __init__(self, data_dir: str = "data"):
        """
        初始化處理器

        Args:
            data_dir: 資料目錄
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def get_data_path(self, source: str) -> Path:
        """
        取得資料目錄路徑

        Args:
            source: 資料源名稱 (mol_faq, bli_faq, osha_faq)

        Returns:
            資料目錄 Path
        """
        path = self.data_dir / source
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_jsonl_path(self, source: str) -> Path:
        """
        取得 JSONL 檔案路徑

        Args:
            source: 資料源名稱

        Returns:
            JSONL 檔案 Path
        """
        return self.get_data_path(source) / "raw.jsonl"

    def write_items(self, source: str, items: List[Dict[str, Any]], mode: str = 'a'):
        """
        寫入資料到 JSONL

        Args:
            source: 資料源名稱
            items: 資料列表
            mode: 寫入模式 ('w' 覆蓋, 'a' 追加)
        """
        jsonl_path = self.get_jsonl_path(source)

        try:
            with open(jsonl_path, mode, encoding='utf-8') as f:
                for item in items:
                    # 添加寫入時間戳
                    item['_write_timestamp'] = datetime.now().isoformat()

                    json_line = json.dumps(item, ensure_ascii=False)
                    f.write(json_line + '\n')

            logger.info(f"成功寫入 {len(items)} 筆資料到 {jsonl_path}")

        except Exception as e:
            logger.error(f"寫入 JSONL 失敗: {e}")
            raise

    def append_item(self, source: str, item: Dict[str, Any]):
        """
        追加單筆資料

        Args:
            source: 資料源名稱
            item: 單筆資料
        """
        self.write_items(source, [item], mode='a')

    def read_all(self, source: str) -> List[Dict[str, Any]]:
        """
        讀取所有資料

        Args:
            source: 資料源名稱

        Returns:
            所有資料列表
        """
        jsonl_path = self.get_jsonl_path(source)

        if not jsonl_path.exists():
            logger.warning(f"JSONL 檔案不存在: {jsonl_path}")
            return []

        items = []

        try:
            with open(jsonl_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        item = json.loads(line)
                        items.append(item)
                    except json.JSONDecodeError as e:
                        logger.error(f"JSON 解析失敗 (第 {line_num} 行): {e}")

            logger.info(f"成功讀取 {len(items)} 筆資料從 {jsonl_path}")
            return items

        except Exception as e:
            logger.error(f"讀取 JSONL 失敗: {e}")
            return []

    def stream_read(self, source: str) -> Iterator[Dict[str, Any]]:
        """
        串流讀取資料 (逐行讀取,節省記憶體)

        Args:
            source: 資料源名稱

        Yields:
            每筆資料
        """
        jsonl_path = self.get_jsonl_path(source)

        if not jsonl_path.exists():
            logger.warning(f"JSONL 檔案不存在: {jsonl_path}")
            return

        try:
            with open(jsonl_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        item = json.loads(line)
                        yield item
                    except json.JSONDecodeError as e:
                        logger.error(f"JSON 解析失敗 (第 {line_num} 行): {e}")

        except Exception as e:
            logger.error(f"串流讀取失敗: {e}")

    def get_last_item(self, source: str) -> Optional[Dict[str, Any]]:
        """
        取得最後一筆資料 (用於增量更新)

        Args:
            source: 資料源名稱

        Returns:
            最後一筆資料或 None
        """
        jsonl_path = self.get_jsonl_path(source)

        if not jsonl_path.exists():
            return None

        try:
            with open(jsonl_path, 'rb') as f:
                # 移到檔案末尾
                f.seek(0, 2)
                file_size = f.tell()

                if file_size == 0:
                    return None

                # 往回讀取找到最後一行
                f.seek(-2, 2)
                while f.read(1) != b'\n':
                    if f.tell() <= 2:
                        f.seek(0)
                        break
                    f.seek(-2, 1)

                last_line = f.readline().decode('utf-8').strip()

                if last_line:
                    return json.loads(last_line)

        except Exception as e:
            logger.error(f"讀取最後一筆資料失敗: {e}")

        return None

    def count_items(self, source: str) -> int:
        """
        計算資料筆數

        Args:
            source: 資料源名稱

        Returns:
            資料筆數
        """
        jsonl_path = self.get_jsonl_path(source)

        if not jsonl_path.exists():
            return 0

        try:
            with open(jsonl_path, 'r', encoding='utf-8') as f:
                return sum(1 for line in f if line.strip())

        except Exception as e:
            logger.error(f"計算資料筆數失敗: {e}")
            return 0

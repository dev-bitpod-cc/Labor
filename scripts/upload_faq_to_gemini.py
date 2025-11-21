#!/usr/bin/env python3
"""
勞動 FAQ 上傳到 Gemini File Search

上傳三個來源的 FAQ Plain Text 到 Gemini:
- MOL (勞動部): 383 筆
- OSHA (職業安全衛生署): 124 筆
- BLI (勞工保險局): 987 筆
總計: 1,494 筆

使用方式:
    python scripts/upload_faq_to_gemini.py --test  # 測試模式 (只上傳前 10 筆)
    python scripts/upload_faq_to_gemini.py         # 完整上傳
"""

import os
import sys
import time
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

# 設定專案根目錄
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from loguru import logger

# 設定日誌
log_file = PROJECT_ROOT / 'logs' / f'upload_faq_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
log_file.parent.mkdir(parents=True, exist_ok=True)
logger.add(
    str(log_file),
    rotation="50 MB",
    retention="7 days",
    level="DEBUG"
)

try:
    from google import genai
    from google.genai import types
except ImportError:
    logger.error("請安裝 google-genai: pip install google-genai")
    sys.exit(1)

# 載入環境變數
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / '.env')


class FAQGeminiUploader:
    """勞動 FAQ Gemini 上傳器"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        store_name: str = 'labor-faq',
        max_retries: int = 3,
        retry_delay: float = 2.0
    ):
        """初始化上傳器"""
        self.api_key = api_key or os.getenv('GEMINI_API_KEY')
        if not self.api_key:
            raise ValueError("未設定 GEMINI_API_KEY")

        self.store_name = store_name
        self.client = genai.Client(api_key=self.api_key)
        self.store_id = None
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        # 統計
        self.stats = {
            'total_files': 0,
            'uploaded_files': 0,
            'failed_files': 0,
            'skipped_files': 0,
            'total_bytes': 0,
        }

        # Manifest 記錄
        self.manifest_file = PROJECT_ROOT / 'data' / 'temp_uploads' / 'faq_upload_manifest.json'
        self.manifest_file.parent.mkdir(parents=True, exist_ok=True)
        self.manifest = self._load_manifest()

        logger.info(f"FAQGeminiUploader 初始化: store={store_name}")

    def _load_manifest(self) -> Dict[str, Any]:
        """載入上傳狀態"""
        if self.manifest_file.exists():
            try:
                with open(self.manifest_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"載入 manifest 失敗: {e}")
        return {'uploaded': {}, 'store_id': None}

    def _save_manifest(self):
        """儲存上傳狀態"""
        try:
            self.manifest['store_id'] = self.store_id
            with open(self.manifest_file, 'w', encoding='utf-8') as f:
                json.dump(self.manifest, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"儲存 manifest 失敗: {e}")

    def get_or_create_store(self) -> str:
        """取得或建立 File Search Store"""
        try:
            # 檢查 manifest 中是否已有 store
            if self.manifest.get('store_id'):
                self.store_id = self.manifest['store_id']
                logger.info(f"使用 manifest 中的 Store: {self.store_id}")
                return self.store_id

            # 列出現有 Stores
            logger.info("檢查現有 Stores...")
            stores = list(self.client.file_search_stores.list())

            for store in stores:
                if store.display_name == self.store_name:
                    self.store_id = store.name
                    logger.info(f"找到現有 Store: {self.store_id}")
                    self._save_manifest()
                    return self.store_id

            # 建立新 Store
            logger.info(f"建立新 Store: {self.store_name}")
            store = self.client.file_search_stores.create(
                config=types.CreateFileSearchStoreConfig(
                    display_name=self.store_name
                )
            )
            self.store_id = store.name
            logger.info(f"Store 建立成功: {self.store_id}")
            self._save_manifest()

            return self.store_id

        except Exception as e:
            logger.error(f"取得/建立 Store 失敗: {e}")
            raise

    def upload_file_to_store(
        self,
        filepath: str,
        display_name: Optional[str] = None,
        delay: float = 3.0
    ) -> bool:
        """上傳單一檔案到 Store (帶重試)"""
        filepath_obj = Path(filepath)

        if not filepath_obj.exists():
            logger.error(f"檔案不存在: {filepath}")
            self.stats['failed_files'] += 1
            return False

        if not display_name:
            display_name = filepath_obj.name

        # 重試機制
        for attempt in range(self.max_retries):
            try:
                # 上傳檔案
                if attempt == 0:
                    logger.debug(f"上傳: {display_name}")
                else:
                    logger.info(f"重試 ({attempt + 1}/{self.max_retries}): {display_name}")

                with open(filepath, 'rb') as f:
                    file_obj = self.client.files.upload(
                        file=f,
                        config=types.UploadFileConfig(
                            display_name=display_name,
                            mime_type='text/plain'
                        )
                    )

                # 等待後加入 Store
                time.sleep(delay)

                self.client.file_search_stores.import_file(
                    file_search_store_name=self.store_id,
                    file_name=file_obj.name
                )

                # 更新統計
                self.stats['uploaded_files'] += 1
                self.stats['total_bytes'] += filepath_obj.stat().st_size

                # 記錄到 manifest
                self.manifest['uploaded'][str(filepath)] = {
                    'file_id': file_obj.name,
                    'timestamp': time.time(),
                    'status': 'success',
                    'display_name': display_name
                }
                self._save_manifest()

                return True

            except Exception as e:
                logger.warning(f"上傳失敗 ({attempt + 1}/{self.max_retries}): {e}")

                if attempt < self.max_retries - 1:
                    retry_delay = self.retry_delay * (2 ** attempt)
                    logger.info(f"等待 {retry_delay:.1f} 秒後重試...")
                    time.sleep(retry_delay)
                else:
                    logger.error(f"上傳失敗 (已重試 {self.max_retries} 次): {filepath}")
                    self.stats['failed_files'] += 1

                    self.manifest['uploaded'][str(filepath)] = {
                        'file_id': None,
                        'timestamp': time.time(),
                        'status': 'failed',
                        'error': str(e)
                    }
                    self._save_manifest()

                    return False

        return False

    def upload_directory(
        self,
        directory: str,
        pattern: str = "*.txt",
        delay: float = 3.0,
        skip_existing: bool = True,
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """上傳目錄中的所有檔案"""
        dir_path = Path(directory)

        if not dir_path.exists():
            raise FileNotFoundError(f"目錄不存在: {directory}")

        # 確保 Store 存在
        if not self.store_id:
            self.get_or_create_store()

        # 尋找所有檔案
        all_files = sorted(dir_path.glob(pattern))

        if limit:
            all_files = all_files[:limit]

        self.stats['total_files'] = len(all_files)

        # 過濾已上傳的檔案
        files_to_upload = []
        for filepath in all_files:
            if skip_existing and str(filepath) in self.manifest['uploaded']:
                if self.manifest['uploaded'][str(filepath)].get('status') == 'success':
                    self.stats['skipped_files'] += 1
                    continue
            files_to_upload.append(filepath)

        logger.info(f"找到 {len(all_files)} 個檔案")
        logger.info(f"跳過 {self.stats['skipped_files']} 個已上傳檔案")
        logger.info(f"需上傳 {len(files_to_upload)} 個檔案")

        # 逐一上傳
        for i, filepath in enumerate(files_to_upload, 1):
            logger.info(f"[{i}/{len(files_to_upload)}] {filepath.name}")

            success = self.upload_file_to_store(str(filepath), delay=delay)

            if success:
                logger.info(f"✓ [{i}/{len(files_to_upload)}] 成功")
            else:
                logger.warning(f"✗ [{i}/{len(files_to_upload)}] 失敗")

            # 間隔
            if i < len(files_to_upload):
                time.sleep(delay)

        logger.info("=" * 60)
        logger.info("上傳完成!")
        logger.info(f"總計: {self.stats['total_files']}")
        logger.info(f"成功: {self.stats['uploaded_files']}")
        logger.info(f"失敗: {self.stats['failed_files']}")
        logger.info(f"跳過: {self.stats['skipped_files']}")
        logger.info(f"總大小: {self.stats['total_bytes'] / 1024:.2f} KB")
        logger.info(f"Store ID: {self.store_id}")

        return self.stats


def main():
    """主程式"""
    parser = argparse.ArgumentParser(description='上傳勞動 FAQ 到 Gemini')
    parser.add_argument('--test', action='store_true', help='測試模式 (只上傳前 10 筆)')
    parser.add_argument('--limit', type=int, help='限制上傳數量')
    parser.add_argument('--delay', type=float, default=3.0, help='上傳間隔秒數')
    parser.add_argument('--store-name', default='labor-faq', help='Store 名稱')
    parser.add_argument('--no-skip', action='store_true', help='不跳過已上傳的檔案')
    args = parser.parse_args()

    # 設定限制
    limit = 10 if args.test else args.limit

    logger.info("=" * 60)
    logger.info("勞動 FAQ 上傳到 Gemini File Search")
    logger.info("=" * 60)

    if args.test:
        logger.info("【測試模式】只上傳前 10 筆")

    # 初始化上傳器
    uploader = FAQGeminiUploader(store_name=args.store_name)

    # 上傳目錄
    input_dir = PROJECT_ROOT / 'data' / 'plaintext_optimized' / 'faq_individual'

    if not input_dir.exists():
        logger.error(f"輸入目錄不存在: {input_dir}")
        logger.error("請先執行 FAQ Plain Text 優化: python -m src.processor.faq_plaintext_optimizer")
        sys.exit(1)

    # 開始上傳
    stats = uploader.upload_directory(
        directory=str(input_dir),
        pattern="*.txt",
        delay=args.delay,
        skip_existing=not args.no_skip,
        limit=limit
    )

    # 輸出 mapping 檔案
    mapping_file = PROJECT_ROOT / 'data' / 'faq_gemini_id_mapping.json'
    mapping_data = {
        'store_id': uploader.store_id,
        'store_name': args.store_name,
        'total_files': stats['uploaded_files'] + stats['skipped_files'],
        'uploaded_at': datetime.now().isoformat(),
        'files': {}
    }

    for filepath, info in uploader.manifest['uploaded'].items():
        if info.get('status') == 'success':
            file_id = Path(filepath).stem
            mapping_data['files'][file_id] = {
                'gemini_file_id': info['file_id'],
                'display_name': info.get('display_name', '')
            }

    with open(mapping_file, 'w', encoding='utf-8') as f:
        json.dump(mapping_data, f, indent=2, ensure_ascii=False)

    logger.info(f"Mapping 檔案已儲存: {mapping_file}")
    logger.info("=" * 60)

    return 0


if __name__ == '__main__':
    sys.exit(main())

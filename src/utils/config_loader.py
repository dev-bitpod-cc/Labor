"""配置載入模組"""

import yaml
from pathlib import Path
from typing import Dict, Any
from loguru import logger


class ConfigLoader:
    """配置檔案載入器"""

    def __init__(self, config_dir: str = "config"):
        """
        初始化配置載入器

        Args:
            config_dir: 配置目錄
        """
        self.config_dir = Path(config_dir)

    def load_yaml(self, filename: str) -> Dict[str, Any]:
        """
        載入 YAML 配置檔案

        Args:
            filename: 檔案名稱

        Returns:
            配置字典
        """
        config_path = self.config_dir / filename

        if not config_path.exists():
            logger.warning(f"配置檔案不存在: {config_path}")
            return {}

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                logger.info(f"成功載入配置: {config_path}")
                return config or {}

        except Exception as e:
            logger.error(f"載入配置失敗: {config_path} - {e}")
            return {}

    def get_sources_config(self) -> Dict[str, Any]:
        """載入資料源配置"""
        return self.load_yaml('sources.yaml')

    def get_crawler_config(self) -> Dict[str, Any]:
        """載入爬蟲配置"""
        return self.load_yaml('crawler.yaml')

    def get_source_config(self, source: str) -> Dict[str, Any]:
        """
        取得特定資料源的配置

        Args:
            source: 資料源名稱 (mol_faq, bli_faq, osha_faq)

        Returns:
            資料源配置字典
        """
        sources_config = self.get_sources_config()
        return sources_config.get('sources', {}).get(source, {})

    def get_category_mapping(self) -> Dict[str, str]:
        """取得分類映射表"""
        sources_config = self.get_sources_config()
        return sources_config.get('category_mapping', {})

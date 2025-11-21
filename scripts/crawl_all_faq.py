#!/usr/bin/env python3
"""全量爬取所有 FAQ 資料源"""

import sys
from pathlib import Path

# 加入專案根目錄到 sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger
from src.utils.config_loader import ConfigLoader
from src.crawlers.mol_faq import MOLFaqCrawler
from src.crawlers.osha_faq import OSHAFaqCrawler
from src.crawlers.bli_faq import BLIFaqCrawler
from src.storage.jsonl_handler import JSONLHandler
from src.storage.index_manager import IndexManager

# 設定日誌
logger.add(
    "logs/crawl_all_faq.log",
    rotation="10 MB",
    retention="7 days",
    level="INFO"
)


def crawl_mol():
    """爬取勞動部常見問答"""
    logger.info("=" * 70)
    logger.info("開始爬取: 勞動部常見問答 (MOL)")
    logger.info("=" * 70)

    config_loader = ConfigLoader()
    config = config_loader.get_crawler_config()

    crawler = MOLFaqCrawler(config)

    # 全量爬取（所有頁面）
    all_data = crawler.crawl_all(source_name='mol')

    if all_data:
        # 儲存資料
        storage = JSONLHandler()
        storage.write_items('mol_faq', all_data, mode='w')
        logger.info(f"✓ MOL 資料已儲存: {len(all_data)} 筆")

        # 建立索引
        index_mgr = IndexManager()
        index_mgr.build_index('mol_faq', all_data)
        logger.info("✓ MOL 索引已建立")

    return len(all_data) if all_data else 0


def crawl_osha():
    """爬取職安署常見問答"""
    logger.info("=" * 70)
    logger.info("開始爬取: 職業安全衛生署常見問答 (OSHA)")
    logger.info("=" * 70)

    config_loader = ConfigLoader()
    config = config_loader.get_crawler_config()

    crawler = OSHAFaqCrawler(config)

    # 全量爬取（OSHA 使用分類爬取）
    all_data = crawler.crawl_all_categories(source_name='osha')

    if all_data:
        # 儲存資料
        storage = JSONLHandler()
        storage.write_items('osha_faq', all_data, mode='w')
        logger.info(f"✓ OSHA 資料已儲存: {len(all_data)} 筆")

        # 建立索引
        index_mgr = IndexManager()
        index_mgr.build_index('osha_faq', all_data)
        logger.info("✓ OSHA 索引已建立")

    return len(all_data) if all_data else 0


def crawl_bli():
    """爬取勞保局常見問答"""
    logger.info("=" * 70)
    logger.info("開始爬取: 勞動部勞工保險局常見問答 (BLI)")
    logger.info("=" * 70)

    config_loader = ConfigLoader()
    config = config_loader.get_crawler_config()

    crawler = BLIFaqCrawler(config)

    # 全量爬取
    all_data = crawler.crawl_all(source_name='bli')

    if all_data:
        # 儲存資料
        storage = JSONLHandler()
        storage.write_items('bli_faq', all_data, mode='w')
        logger.info(f"✓ BLI 資料已儲存: {len(all_data)} 筆")

        # 建立索引
        index_mgr = IndexManager()
        index_mgr.build_index('bli_faq', all_data)
        logger.info("✓ BLI 索引已建立")

    return len(all_data) if all_data else 0


def main():
    """主函數"""
    import argparse

    parser = argparse.ArgumentParser(description='全量爬取 FAQ 資料')
    parser.add_argument('--source', choices=['mol', 'osha', 'bli', 'all'],
                        default='all', help='指定爬取來源')
    args = parser.parse_args()

    logger.info("=" * 70)
    logger.info("勞動法規 FAQ 全量爬取")
    logger.info("=" * 70)

    results = {}

    if args.source in ['mol', 'all']:
        results['mol'] = crawl_mol()

    if args.source in ['osha', 'all']:
        results['osha'] = crawl_osha()

    if args.source in ['bli', 'all']:
        results['bli'] = crawl_bli()

    # 總結
    logger.info("\n" + "=" * 70)
    logger.info("爬取完成總結")
    logger.info("=" * 70)

    total = 0
    for source, count in results.items():
        logger.info(f"  {source.upper()}: {count} 筆")
        total += count

    logger.info(f"\n  總計: {total} 筆")
    logger.info("=" * 70)

    # 提示下一步
    logger.info("\n下一步:")
    logger.info("  1. 執行 Plain Text 優化: python -m src.processor.faq_plaintext_optimizer")
    logger.info("  2. 上傳到 Gemini File Search（含機構 metadata filter）")


if __name__ == '__main__':
    main()

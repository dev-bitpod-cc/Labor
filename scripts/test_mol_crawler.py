#!/usr/bin/env python3
"""測試勞動部常見問答爬蟲"""

import sys
from pathlib import Path

# 加入專案根目錄到 sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger
from src.utils.config_loader import ConfigLoader
from src.crawlers.mol_faq import MOLFaqCrawler
from src.storage.jsonl_handler import JSONLHandler
from src.storage.index_manager import IndexManager


def main():
    """主函數"""
    logger.info("=" * 70)
    logger.info("測試勞動部常見問答爬蟲")
    logger.info("=" * 70)

    # 1. 載入配置
    logger.info("\n[1/5] 載入配置")
    config_loader = ConfigLoader()
    config = config_loader.get_crawler_config()
    logger.info("✓ 配置載入成功")

    # 2. 初始化爬蟲
    logger.info("\n[2/5] 初始化爬蟲")
    crawler = MOLFaqCrawler(config)
    logger.info("✓ 爬蟲初始化成功")

    # 3. 測試爬取（前 3 頁，30 筆）
    logger.info("\n[3/5] 開始爬取（前 3 頁）")
    logger.info("-" * 70)

    items = crawler.crawl_all(
        start_page=1,
        max_pages=3,
        source_name='mol'
    )

    logger.info("\n爬取完成！")
    logger.info(f"總筆數: {len(items)}")

    # 4. 儲存資料
    logger.info("\n[4/5] 儲存資料")

    if items:
        storage = JSONLHandler()
        storage.write_items('mol_faq', items, mode='w')
        logger.info(f"✓ 資料已儲存: data/mol_faq/raw.jsonl")

        # 5. 建立索引
        logger.info("\n[5/5] 建立索引")
        index_mgr = IndexManager()
        index_mgr.build_index('mol_faq', items)
        logger.info("✓ 索引已建立")

    # 6. 統計資訊
    logger.info("\n" + "=" * 70)
    logger.info("統計資訊")
    logger.info("=" * 70)

    if items:
        # 統計分類
        categories = {}
        for item in items:
            cat = item.get('category', 'unknown')
            categories[cat] = categories.get(cat, 0) + 1

        logger.info("\n分類分布:")
        for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
            logger.info(f"  {cat or 'None'}: {count} 筆")

        # 統計次分類
        subcategories = {}
        for item in items:
            subcat = item.get('subcategory', 'unknown')
            subcategories[subcat] = subcategories.get(subcat, 0) + 1

        logger.info("\n次分類分布:")
        for subcat, count in sorted(subcategories.items(), key=lambda x: x[1], reverse=True)[:10]:
            logger.info(f"  {subcat or 'None'}: {count} 筆")

        # 統計相關法規
        total_laws = sum(len(item.get('related_laws', [])) for item in items)
        items_with_laws = sum(1 for item in items if item.get('related_laws'))

        logger.info(f"\n相關法規統計:")
        logger.info(f"  有相關法規的問答: {items_with_laws}/{len(items)} ({items_with_laws/len(items)*100:.1f}%)")
        logger.info(f"  總法規數: {total_laws}")
        if items:
            logger.info(f"  平均每筆: {total_laws/len(items):.1f} 個")

        # 顯示範例
        logger.info("\n範例問答:")
        for i, item in enumerate(items[:3], 1):
            logger.info(f"\n[{i}] {item.get('id')}")
            logger.info(f"  問題: {item.get('question', 'N/A')[:60]}...")
            logger.info(f"  分類: {item.get('category', 'N/A')} / {item.get('subcategory', 'N/A')}")
            logger.info(f"  更新日期: {item.get('metadata', {}).get('updated_date', 'N/A')}")
            logger.info(f"  相關法規: {len(item.get('related_laws', []))} 個")

    # 請求統計
    stats = crawler.get_stats()
    logger.info("\n請求統計:")
    logger.info(f"  總請求數: {stats['total_requests']}")
    logger.info(f"  成功: {stats['successful_requests']}")
    logger.info(f"  失敗: {stats['failed_requests']}")

    logger.info("\n" + "=" * 70)
    logger.info("測試完成！")
    logger.info("=" * 70)
    logger.info("\n下一步:")
    logger.info("  1. 檢查 data/mol_faq/raw.jsonl")
    logger.info("  2. 完整爬取: python scripts/crawl_mol_full.py")
    logger.info("  3. 實作 Plain Text 優化器")


if __name__ == '__main__':
    main()

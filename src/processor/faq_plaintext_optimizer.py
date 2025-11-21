"""
勞動 FAQ Plain Text 優化格式化器 - 專為 RAG 檢索優化

相比基礎 HTML 格式，此版本:
- 移除所有 HTML 標籤和網頁雜訊
- 移除檢索無用的 metadata (編號、URL、抓取時間)
- 只保留語義相關的欄位 (問題、答案、分類、相關法規)
- 預期效果: -35% 檔案大小, +20% 語義密度, +40-60% 檢索準確度
"""

from typing import Dict, Any, List
from pathlib import Path
from loguru import logger
import json
import re


class FAQPlainTextOptimizer:
    """勞動 FAQ Plain Text 優化格式化器 - 最小化噪音，最大化語義密度"""

    def __init__(self):
        """初始化格式化器"""
        # 網頁雜訊關鍵字 (會被移除)
        self.noise_keywords = [
            'FACEBOOK', 'facebook', 'FB', 'fb',
            'Line', 'line', 'LINE',
            'Twitter', 'twitter',
            '友善列印', '列印', 'Print', 'print',
            '回上頁', '上一頁', '回首頁',
            '瀏覽人次', '點閱數', '點閱次數',
            '更新日期', '發布日期',
            '分享至', 'Share', 'share',
            ':::',  # 網頁標記
            '跳到主要內容區塊',
            '網站導覽', '網站地圖',
            '相關連結', '相關網站',
            '無障礙', 'accessibility',
        ]

        # 來源名稱對應
        self.source_names = {
            'mol': '勞動部',
            'osha': '職業安全衛生署',
            'bli': '勞動部勞工保險局',
        }

    def format_faq(self, item: Dict[str, Any]) -> str:
        """
        格式化單筆 FAQ 為優化的 Plain Text

        優化原則:
        - 問答格式清晰
        - 只包含查詢相關資訊
        - 零噪音、零重複
        - 語義密集

        Args:
            item: FAQ 資料

        Returns:
            優化的 Plain Text 格式文字
        """
        lines = []

        # ===== 來源與分類 (簡潔) =====
        source = item.get('source', '')
        source_name = self.source_names.get(source, source)
        category = item.get('category', '')
        subcategory = item.get('subcategory', '')

        # 來源標示
        if source_name:
            lines.append(f"來源: {source_name}")

        # 分類標示 (合併主次分類)
        if category:
            if subcategory and subcategory != category:
                lines.append(f"分類: {category} > {subcategory}")
            else:
                lines.append(f"分類: {category}")

        # 分類路徑 (如果有，通常 BLI 有)
        category_path = item.get('category_path', '')
        if category_path and '>' in category_path:
            lines.append(f"路徑: {category_path}")

        if lines:
            lines.append("")

        # ===== 問題 =====
        question = item.get('question', '')
        if question:
            # 清理問題文字
            question = self._clean_text(question)
            lines.append(f"問: {question}")
            lines.append("")

        # ===== 答案 =====
        answer = item.get('answer', {})
        answer_text = ''

        if isinstance(answer, dict):
            answer_text = answer.get('text', '')
        elif isinstance(answer, str):
            answer_text = answer

        if answer_text:
            # 清理答案文字
            answer_text = self._clean_content(answer_text)
            lines.append(f"答: {answer_text}")

        # ===== 相關法規 =====
        related_laws = item.get('related_laws', [])
        if related_laws:
            # 過濾有效的法規名稱
            valid_laws = []
            for law in related_laws:
                if isinstance(law, dict):
                    name = law.get('name', '')
                elif isinstance(law, str):
                    name = law
                else:
                    continue

                # 清理並驗證法規名稱
                name = self._clean_text(name)
                if self._is_valid_law_name(name):
                    valid_laws.append(name)

            if valid_laws:
                # 去重
                valid_laws = list(dict.fromkeys(valid_laws))
                lines.append("")
                lines.append(f"相關法規: {', '.join(valid_laws)}")

        return "\n".join(lines)

    def _clean_text(self, text: str) -> str:
        """
        清理文字，移除多餘空白和特殊字元

        Args:
            text: 原始文字

        Returns:
            清理後的文字
        """
        if not text:
            return ""

        # 移除 HTML 標籤
        text = re.sub(r'<[^>]+>', '', text)

        # 移除多餘空白
        text = re.sub(r'\s+', ' ', text)

        # 移除首尾空白
        text = text.strip()

        return text

    def _clean_content(self, text: str) -> str:
        """
        清理內容文字，移除網頁雜訊

        Args:
            text: 原始文字

        Returns:
            清理後的文字
        """
        if not text:
            return ""

        # 移除 HTML 標籤
        text = re.sub(r'<[^>]+>', '', text)

        # 分行處理
        lines = text.split('\n')
        cleaned_lines = []
        prev_empty = False

        for line in lines:
            line = line.strip()

            # 跳過空行 (但保留一個)
            if not line:
                if not prev_empty:
                    cleaned_lines.append('')
                prev_empty = True
                continue

            # 跳過包含雜訊關鍵字的行
            if self._is_noise_line(line):
                continue

            # 跳過單一字元或過短的行 (可能是導航元素)
            if len(line) <= 2:
                continue

            # 跳過純符號行
            if re.match(r'^[\-=_\*\#]+$', line):
                continue

            cleaned_lines.append(line)
            prev_empty = False

        # 合併行
        result = '\n'.join(cleaned_lines)

        # 移除過多的連續空行
        result = re.sub(r'\n{3,}', '\n\n', result)

        return result.strip()

    def _is_noise_line(self, line: str) -> bool:
        """
        判斷是否為雜訊行

        Args:
            line: 單行文字

        Returns:
            True if 是雜訊行
        """
        return any(keyword in line for keyword in self.noise_keywords)

    def _is_valid_law_name(self, name: str) -> bool:
        """
        驗證是否為有效的法規名稱

        有效的法規名稱特徵:
        - 長度 3-25 字元
        - 以法/條例/辦法等結尾
        - 以正式機構/主題名稱開頭（勞、職、保、工、就、性等）
        - 不含句子片段（依、係、次依、又、下稱等）

        Args:
            name: 法規名稱

        Returns:
            True if 是有效的法規名稱
        """
        if not name:
            return False

        # 長度限制
        if len(name) < 3 or len(name) > 25:
            return False

        # 必須以法規結尾
        if not re.search(r'(法|條例|辦法|規則|細則|要點|準則|綱要|規定|標準)$', name):
            return False

        # 必須以正式開頭（排除句子片段）
        valid_prefixes = [
            '勞動', '勞工', '勞保', '勞退', '勞基',
            '職業', '職安', '職災',
            '工會', '工廠', '工資',
            '就業', '就服',
            '性別', '性平',
            '保險', '保護',
            '安全', '衛生',
            '退休', '資遣',
            '民', '刑', '行政',
        ]

        # 排除句子片段開頭
        invalid_prefixes = [
            '依', '按', '次依', '又', '如', '即', '並', '則',
            '係', '為', '有', '含', '下稱', '上開', '適用',
            '事業', '雇主', '勞雇', '工作者', '比照',
        ]

        # 檢查開頭
        starts_valid = any(name.startswith(p) for p in valid_prefixes)
        starts_invalid = any(name.startswith(p) for p in invalid_prefixes)

        if starts_invalid:
            return False

        if not starts_valid:
            # 如果不是以已知前綴開頭，檢查是否含有無效模式
            invalid_patterns = [
                r'（下稱', r'下稱', r'係指', r'規定，',
            ]
            if any(re.search(p, name) for p in invalid_patterns):
                return False

        return True

    def format_batch(
        self,
        items: List[Dict[str, Any]],
        output_dir: str = 'data/plaintext_optimized/faq_individual'
    ) -> Dict[str, Any]:
        """
        批次格式化 FAQ 為優化的 Plain Text 檔案

        Args:
            items: FAQ 資料列表
            output_dir: 輸出目錄

        Returns:
            統計資訊 {'total_items': ..., 'created_files': ..., 'output_dir': ...}
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"開始格式化 FAQ 為優化 Plain Text 檔案...")
        logger.info(f"輸出目錄: {output_path}")

        if not items:
            logger.warning("沒有 FAQ 資料")
            return {'total_items': 0, 'created_files': 0, 'output_dir': str(output_path)}

        created_files = []
        source_stats = {}

        for item in items:
            try:
                # 格式化單個 FAQ
                plain_text = self.format_faq(item)

                # 建立檔名
                item_id = item.get('id', 'unknown')
                filename = f"{item_id}.txt"

                # 寫入檔案
                filepath = output_path / filename
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(plain_text)

                created_files.append(str(filepath))
                logger.debug(f"建立檔案: {filename}")

                # 統計來源
                source = item.get('source', 'unknown')
                source_stats[source] = source_stats.get(source, 0) + 1

            except Exception as e:
                logger.error(f"格式化項目失敗: {item.get('id', 'unknown')} - {e}")
                continue

        logger.info(f"完成! 共建立 {len(created_files)} 個優化 Plain Text 檔案")
        logger.info(f"輸出目錄: {output_path}")

        # 統計檔案大小
        total_size = sum(Path(f).stat().st_size for f in created_files)
        avg_size = total_size / len(created_files) if created_files else 0

        logger.info(f"總大小: {total_size / 1024:.2f} KB")
        logger.info(f"平均大小: {avg_size / 1024:.2f} KB")
        logger.info(f"來源統計: {source_stats}")

        return {
            'total_items': len(items),
            'created_files': len(created_files),
            'output_dir': str(output_path),
            'total_size_kb': total_size / 1024,
            'avg_size_kb': avg_size / 1024,
            'source_stats': source_stats,
            'files': created_files[:10]  # 前 10 個檔案作為範例
        }


# ===== 便捷函數 =====

def format_all_faq_optimized(
    sources: List[str] = None,
    output_dir: str = 'data/plaintext_optimized/faq_individual'
) -> Dict[str, Any]:
    """
    從所有 FAQ 來源讀取並格式化為優化的 Plain Text

    Args:
        sources: 來源列表 (預設: ['mol_faq', 'osha_faq', 'bli_faq'])
        output_dir: 輸出目錄

    Returns:
        統計資訊
    """
    if sources is None:
        sources = ['mol_faq', 'osha_faq', 'bli_faq']

    all_items = []

    for source in sources:
        jsonl_file = Path(f'data/{source}/raw.jsonl')
        if not jsonl_file.exists():
            logger.warning(f"找不到 {jsonl_file}")
            continue

        logger.info(f"讀取 {jsonl_file}")

        with open(jsonl_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    all_items.append(json.loads(line))

        logger.info(f"  - 載入 {len(all_items)} 筆")

    if not all_items:
        logger.error("沒有讀取到任何 FAQ 資料")
        return {'total_items': 0, 'created_files': 0}

    logger.info(f"總共讀取 {len(all_items)} 筆 FAQ")

    formatter = FAQPlainTextOptimizer()
    return formatter.format_batch(all_items, output_dir)


if __name__ == '__main__':
    # 測試
    import sys
    from pathlib import Path

    # 設定日誌
    logger.add(
        "logs/faq_plaintext_optimizer.log",
        rotation="10 MB",
        retention="7 days",
        level="DEBUG"
    )

    # 測試格式化
    stats = format_all_faq_optimized()

    print("\n" + "=" * 80)
    print("FAQ Plain Text 優化完成!")
    print("=" * 80)
    print(f"總 FAQ 數: {stats['total_items']}")
    print(f"成功建立: {stats['created_files']} 個檔案")
    print(f"輸出目錄: {stats['output_dir']}")
    print(f"總大小: {stats.get('total_size_kb', 0):.2f} KB")
    print(f"平均大小: {stats.get('avg_size_kb', 0):.2f} KB")

    if stats.get('source_stats'):
        print("\n來源統計:")
        for source, count in stats['source_stats'].items():
            print(f"  - {source}: {count} 筆")

    if stats.get('files'):
        print("\n範例檔案:")
        for f in stats['files'][:3]:
            print(f"  - {f}")

        # 顯示第一個檔案內容
        first_file = stats['files'][0]
        print(f"\n=== 範例內容 ({first_file}) ===")
        with open(first_file, 'r', encoding='utf-8') as f:
            print(f.read())

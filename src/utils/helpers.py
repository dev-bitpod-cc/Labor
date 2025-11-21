"""輔助函數模組"""

import re
import hashlib
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin


def generate_id(source: str, date: str, index: int) -> str:
    """
    生成唯一 ID

    Args:
        source: 資料來源 (mol, bli, osha)
        date: 日期 (YYYY-MM-DD)
        index: 索引編號

    Returns:
        唯一 ID (例如: mol_faq_20251121_0001)
    """
    date_str = date.replace('-', '')
    return f"{source}_faq_{date_str}_{index:04d}"


def generate_hash(content: str) -> str:
    """
    生成內容 hash (用於去重)

    Args:
        content: 內容文字

    Returns:
        SHA256 hash
    """
    return hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]


def clean_text(text: str) -> str:
    """
    清理文字

    Args:
        text: 原始文字

    Returns:
        清理後的文字
    """
    if not text:
        return ""

    # 移除多餘空白
    text = re.sub(r'\s+', ' ', text)

    # 移除前後空白
    text = text.strip()

    return text


def parse_date(date_str: str) -> Optional[str]:
    """
    解析日期字串為標準格式

    Args:
        date_str: 日期字串 (支援多種格式)

    Returns:
        標準格式日期 (YYYY-MM-DD) 或 None
    """
    if not date_str:
        return None

    # 常見日期格式
    formats = [
        '%Y-%m-%d',
        '%Y/%m/%d',
        '%Y.%m.%d',
        '%Y年%m月%d日',
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            return dt.strftime('%Y-%m-%d')
        except ValueError:
            continue

    return None


def normalize_url(url: str, base_url: str = None) -> str:
    """
    標準化 URL

    Args:
        url: 原始 URL
        base_url: 基礎 URL (用於相對路徑)

    Returns:
        完整的 URL
    """
    if not url:
        return ""

    # 如果是完整 URL,直接返回
    if url.startswith('http://') or url.startswith('https://'):
        return url

    # 如果是相對路徑,結合基礎 URL
    if base_url:
        return urljoin(base_url, url)

    return url


def extract_related_laws(text: str) -> list:
    """
    從文字中提取相關法規

    Args:
        text: 文字內容

    Returns:
        法規清單 (名稱列表)
    """
    laws = []

    # 匹配模式：XXX法、XXX辦法、XXX規則、XXX條例
    patterns = [
        r'[^。，\n]{2,30}法(?![律規])',
        r'[^。，\n]{2,30}辦法',
        r'[^。，\n]{2,30}規則',
        r'[^。，\n]{2,30}條例',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            cleaned = match.strip()
            # 避免重複
            if cleaned and cleaned not in laws and len(cleaned) > 3:
                laws.append(cleaned)

    return laws

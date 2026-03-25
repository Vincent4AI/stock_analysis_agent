"""共享数据层 — 多数据源实时获取 + 缓存 + 股票代码解析"""
from __future__ import annotations

import re
import time
import urllib.request

try:
    import akshare as ak
    LIVE = True
except ImportError:
    LIVE = False

# ====== 缓存 ======
_cache = {}
_TTL = 300  # 5分钟


def cached(key, fn, retries=2):
    """带TTL的简易缓存，含重试"""
    now = time.time()
    if key in _cache and now - _cache[key][1] < _TTL:
        return _cache[key][0]
    for attempt in range(retries + 1):
        try:
            val = fn()
            _cache[key] = (val, now)
            return val
        except Exception:
            if attempt < retries:
                time.sleep(1)
    return None


# ====== 腾讯实时行情（最稳定）======
def get_realtime_quote(code: str) -> dict | None:
    """
    通过腾讯财经接口获取实时行情
    返回 dict: name, code, price, change_pct, open, high, low,
              volume_yi, market_cap_yi, pe, pb
    """
    try:
        prefix = 'sh' if code.startswith('6') else 'sz'
        url = f'https://qt.gtimg.cn/q={prefix}{code}'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        resp = urllib.request.urlopen(req, timeout=8)
        data = resp.read().decode('gbk')
        parts = data.split('~')
        if len(parts) < 50:
            return None
        return {
            'name': parts[1],
            'code': parts[2],
            'price': float(parts[3]),
            'change_pct': float(parts[32]) if parts[32] else 0,
            'open': float(parts[5]) if parts[5] else 0,
            'high': float(parts[33]) if parts[33] else 0,
            'low': float(parts[34]) if parts[34] else 0,
            'volume_yi': float(parts[37]) / 10000 if parts[37] else 0,  # 万→亿
            'market_cap_yi': float(parts[45]) if parts[45] else 0,     # 已经是亿
            'pe': float(parts[39]) if parts[39] else 0,
            'pb': float(parts[46]) if parts[46] else 0,
        }
    except Exception:
        return None


def get_stock_quote(code: str) -> dict | None:
    """获取股票实时行情（缓存5分钟）"""
    return cached(f'quote:{code}', lambda: get_realtime_quote(code))


# ====== 新浪日K（稳定）======
def get_stock_hist(code: str):
    """获取股票历史日K数据（新浪源），返回 DataFrame 或 None
    列: date, open, high, low, close, volume, amount, ...
    """
    if not LIVE:
        return None
    prefix = 'sh' if code.startswith('6') else 'sz'
    return cached(f'hist:{code}',
                  lambda: ak.stock_zh_a_daily(symbol=f'{prefix}{code}', adjust='qfq'))


# ====== 财务指标（akshare）======
def get_financial_indicator(code: str):
    """获取财务分析指标，返回 DataFrame 或 None"""
    if not LIVE:
        return None
    return cached(f'fin:{code}',
                  lambda: ak.stock_financial_analysis_indicator(
                      symbol=code, start_year="2023"))


# ====== 新闻（akshare 东方财富）======
def get_stock_news(code: str):
    """获取股票新闻，返回 DataFrame 或 None
    列: 关键词, 新闻标题, 新闻内容, 发布时间, 文章来源, 新闻链接
    """
    if not LIVE:
        return None
    return cached(f'news:{code}',
                  lambda: ak.stock_news_em(symbol=code))


# ====== 股票代码解析 ======
def resolve_stock_code(query: str) -> str | None:
    """从查询文本中解析6位股票代码"""
    m = re.search(r'(\d{6})', query)
    return m.group(1) if m else None

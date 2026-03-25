"""新闻搜索和情绪分析工具 — 支持akshare实时新闻"""
from __future__ import annotations

from .registry import tool
from .data import get_stock_news, resolve_stock_code


# ====== 模拟新闻（fallback）======
MOCK_NEWS = {
    "茅台": [
        "贵州茅台发布2024年报，营收同比增长15.3%，净利润增长18.7%",
        "茅台冰淇淋业务全面升级，跨界创新持续推进",
        "外资机构上调茅台目标价至2200元，维持买入评级",
    ],
    "平安": [
        "中国平安寿险改革成效显现，新业务价值大幅增长",
        "平安银行零售转型深化，资产质量持续改善",
    ],
    "五粮液": [
        "五粮液发布新品战略，高端白酒市场竞争加剧",
        "五粮液营收稳步增长，渠道改革成效显著",
    ],
}

# 股票名称 → 代码映射（用于新闻搜索时的名称解析）
_NAME_CODE_MAP = {
    "茅台": "600519", "贵州茅台": "600519",
    "五粮液": "000858",
    "平安": "601318", "中国平安": "601318",
    "招商银行": "600036", "招行": "600036",
    "宁德时代": "300750",
    "比亚迪": "002594",
    "腾讯": "00700", "阿里": "09988",
}


def _resolve_query_to_code(query: str) -> str | None:
    """尝试从查询中解析股票代码"""
    # 1. 直接代码匹配
    code = resolve_stock_code(query)
    if code:
        return code
    # 2. 名称映射
    for name, c in _NAME_CODE_MAP.items():
        if name in query:
            return c
    return None


@tool("搜索股票相关新闻。输入股票名称或代码，返回最近的新闻摘要。")
def search_news(query: str) -> str:
    """
    query: 搜索关键词（股票名称或代码）
    """
    code = _resolve_query_to_code(query)

    # 尝试实时新闻
    if code:
        df = get_stock_news(code)
        if df is not None and not df.empty:
            try:
                items = df.head(5)
                result = f"关于 {query} 的最新新闻:\n"
                for idx, (_, row) in enumerate(items.iterrows()):
                    title = row.get('新闻标题', '')
                    pub_time = str(row.get('发布时间', ''))[:16]
                    source = row.get('文章来源', '')
                    result += f"  {idx+1}. [{pub_time}] {title}"
                    if source:
                        result += f" ({source})"
                    result += "\n"
                return result
            except Exception:
                pass

    # Fallback 模拟新闻
    for key, news_list in MOCK_NEWS.items():
        if key in query:
            return f"[模拟数据] 关于 {query} 的最新新闻:\n" + "\n".join(
                f"  {i+1}. {n}" for i, n in enumerate(news_list)
            )
    return f"未找到关于 {query} 的相关新闻"


@tool("分析新闻文本的市场情绪。输入新闻内容，返回情绪评分(-1到1)和分析。")
def analyze_sentiment(news_text: str) -> str:
    """
    news_text: 要分析的新闻文本内容
    """
    positive_words = ["增长", "上调", "买入", "升级", "改善", "创新", "突破",
                      "增加", "提升", "超预期", "利好", "新高", "强劲", "大幅"]
    negative_words = ["下降", "下调", "卖出", "风险", "亏损", "减持",
                      "下滑", "低于预期", "利空", "暴跌", "萎缩", "违规"]

    pos = sum(1 for w in positive_words if w in news_text)
    neg = sum(1 for w in negative_words if w in news_text)

    if pos + neg == 0:
        score = 0.0
    else:
        score = round((pos - neg) / (pos + neg), 2)

    if score > 0.3:
        label = "积极"
    elif score < -0.3:
        label = "消极"
    else:
        label = "中性"

    return (
        f"情绪评分: {score} ({label})\n"
        f"正面信号: {pos}个, 负面信号: {neg}个\n"
        f"分析依据: 基于{len(positive_words)+len(negative_words)}个金融关键词的文本扫描"
    )

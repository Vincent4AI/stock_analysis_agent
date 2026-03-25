"""因子打分工具 — 对标你AIGEXBot的factor_strategy"""
from .registry import tool


@tool("根据财务指标计算股票综合得分(0-100)。输入PE、ROE、营收增速、净利润增速。")
def calculate_score(pe: float, roe: float, revenue_growth: float, profit_growth: float) -> str:
    """
    pe: 市盈率
    roe: 净资产收益率(%)
    revenue_growth: 营收增速(%)
    profit_growth: 净利润增速(%)
    """
    # 简化版因子打分（面试时对标AIGEXBot的分层打分逻辑）
    pe_score = max(0, min(30, 30 - pe))          # PE越低越好，满分30
    roe_score = min(30, roe)                       # ROE越高越好，满分30
    growth_score = min(20, (revenue_growth + profit_growth) / 2)  # 增速，满分20
    stability_score = 20 if roe > 15 and pe < 40 else 10          # 稳定性，满分20

    total = round(pe_score + roe_score + growth_score + stability_score, 1)

    if total >= 70:
        rating = "强烈推荐"
    elif total >= 50:
        rating = "可以关注"
    else:
        rating = "建议观望"

    return (
        f"综合得分: {total}/100\n"
        f"  估值因子(PE): {round(pe_score,1)}/30\n"
        f"  盈利因子(ROE): {round(roe_score,1)}/30\n"
        f"  成长因子(增速): {round(growth_score,1)}/20\n"
        f"  稳定性因子: {stability_score}/20\n"
        f"投资评级: {rating}"
    )

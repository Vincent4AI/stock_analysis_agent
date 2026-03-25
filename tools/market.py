"""行情数据工具 — 腾讯实时行情 + 新浪日K + akshare财务指标，自动回退模拟数据"""
from .registry import tool
from .data import get_stock_quote, get_stock_hist, get_financial_indicator

# ====== 模拟数据（fallback）======
MOCK_DATA = {
    "600519": {"name": "贵州茅台", "price": 1823.50, "pe": 30.2, "pb": 9.8,
               "roe": 28.5, "revenue_growth": 15.3, "net_profit_growth": 18.7,
               "market_cap": 22900, "dividend_yield": 1.8},
    "000858": {"name": "五粮液", "price": 156.30, "pe": 22.1, "pb": 5.2,
               "roe": 22.3, "revenue_growth": 12.1, "net_profit_growth": 14.5,
               "market_cap": 6070, "dividend_yield": 2.5},
    "601318": {"name": "中国平安", "price": 52.80, "pe": 8.5, "pb": 1.1,
               "roe": 14.2, "revenue_growth": 5.8, "net_profit_growth": 8.3,
               "market_cap": 9650, "dividend_yield": 4.2},
}


@tool("获取股票实时价格和基本信息。输入股票代码（如600519），返回实时价格、涨跌幅、市值等。")
def get_stock_price(stock_code: str) -> str:
    """
    stock_code: 6位股票代码，如 600519
    """
    q = get_stock_quote(stock_code)
    if q:
        return (
            f"股票: {q['name']} ({stock_code})\n"
            f"当前价格: ¥{q['price']}\n"
            f"涨跌幅: {q['change_pct']}%\n"
            f"今开: ¥{q['open']}  最高: ¥{q['high']}  最低: ¥{q['low']}\n"
            f"成交额: {q['volume_yi']:.2f}亿\n"
            f"总市值: {q['market_cap_yi']:.0f}亿\n"
            f"市盈率: {q['pe']}\n"
            f"市净率: {q['pb']}"
        )

    # Fallback
    data = MOCK_DATA.get(stock_code)
    if not data:
        return f"未找到股票 {stock_code} 的数据"
    return (
        f"[模拟数据] 股票: {data['name']} ({stock_code})\n"
        f"当前价格: ¥{data['price']}\n"
        f"市值: {data['market_cap']}亿\n"
        f"股息率: {data['dividend_yield']}%"
    )


@tool("获取股票财务指标。输入股票代码，返回PE、PB、ROE、营收增速等关键财务数据。")
def get_financials(stock_code: str) -> str:
    """
    stock_code: 6位股票代码
    """
    q = get_stock_quote(stock_code)
    fin_df = get_financial_indicator(stock_code)

    if q:
        lines = [
            f"股票: {q['name']} ({stock_code})",
            f"PE(市盈率): {q['pe']}",
            f"PB(市净率): {q['pb']}",
            f"总市值: {q['market_cap_yi']:.0f}亿",
        ]

        # 近5日行情波动
        hist = get_stock_hist(stock_code)
        if hist is not None and len(hist) >= 5:
            recent = hist.tail(5)
            avg_vol = recent['amount'].mean() / 1e8
            change_5d = ((hist.iloc[-1]['close'] / hist.iloc[-5]['close']) - 1) * 100
            lines.append(f"近5日涨跌: {change_5d:.2f}%")
            lines.append(f"近5日均成交额: {avg_vol:.2f}亿")

        # 财务指标
        if fin_df is not None and not fin_df.empty:
            r = fin_df.iloc[0]
            roe = r.get('净资产收益率(%)', 'N/A')
            rev = r.get('主营业务收入增长率(%)', 'N/A')
            profit = r.get('净利润增长率(%)', 'N/A')
            lines += [
                f"ROE(净资产收益率): {roe}%",
                f"营收增速: {rev}%",
                f"净利润增速: {profit}%",
            ]
        else:
            lines.append("（详细财务指标暂不可用，仅展示估值数据）")

        return "\n".join(lines)

    # Fallback
    data = MOCK_DATA.get(stock_code)
    if not data:
        return f"未找到股票 {stock_code} 的财务数据"
    return (
        f"[模拟数据] 股票: {data['name']} ({stock_code})\n"
        f"PE(市盈率): {data['pe']}\n"
        f"PB(市净率): {data['pb']}\n"
        f"ROE(净资产收益率): {data['roe']}%\n"
        f"营收增速: {data['revenue_growth']}%\n"
        f"净利润增速: {data['net_profit_growth']}%"
    )

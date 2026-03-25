"""
NewsAgent — 新闻情绪分析Agent (ReAct模式)

面试重点：作为委托目标Agent，展示多Agent协作
"""
from .base import ReActAgent
from tools.registry import get_tools
from config import MODELS

NEWS_PROMPT = """你是一个金融新闻分析师Agent。你的任务是搜索和分析股票相关新闻的市场情绪。

分析流程：
1. 用search_news搜索相关新闻
2. 用analyze_sentiment分析新闻情绪
3. 综合给出新闻面分析结论

最终回答要包含：关键新闻摘要 + 情绪评分 + 新闻面结论"""


class NewsAgent(ReActAgent):
    def __init__(self):
        tool_names = ["search_news", "analyze_sentiment"]
        schemas, fn_map = get_tools(tool_names)

        super().__init__(
            name="news",
            model=MODELS["news"],
            system_prompt=NEWS_PROMPT,
            tools_schemas=schemas,
            tools_map=fn_map,
            max_turns=3,  # 新闻分析不需要太多轮
        )

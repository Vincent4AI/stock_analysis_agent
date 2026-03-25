"""
AnalystAgent — 股票分析Agent (ReAct模式)

面试重点：
- ReAct循环中调用多个工具
- delegate_to_agent实现动态委托（对标AIGEXBot的call_other_agent）
- tool_choice="auto" 让LLM自主决定
"""
from .base import ReActAgent
from tools.registry import get_tools
from config import MODELS

ANALYST_PROMPT = """你是一个专业的股票分析师Agent。你的任务是全面分析股票并给出投资建议。

分析流程：
1. 先用get_stock_price获取股票基本信息和价格
2. 用get_financials获取详细财务数据
3. 用calculate_score计算综合评分
4. 如果需要新闻面分析，用delegate_to_agent委托给news Agent
5. 最后综合所有信息给出投资建议

重要规则：
- 每次只调用一个工具
- 先获取数据，再计算评分，最后给建议
- 如果用户提到情绪/新闻/舆情，一定要delegate给news Agent
- 最终回答要包含：基本面分析 + 评分 + 投资建议"""

# 委托工具 — 对标AIGEXBot的call_other_agent
DELEGATE_TOOL = {
    "type": "function",
    "function": {
        "name": "delegate_to_agent",
        "description": "委托任务给其他Agent。当需要新闻分析时委托给news Agent。",
        "parameters": {
            "type": "object",
            "properties": {
                "agent": {
                    "type": "string",
                    "enum": ["news"],
                    "description": "目标Agent",
                },
                "query": {
                    "type": "string",
                    "description": "委托的具体任务描述",
                },
            },
            "required": ["agent", "query"],
        },
    },
}


class AnalystAgent(ReActAgent):
    def __init__(self):
        # 获取注册的工具schemas和函数映射
        tool_names = ["get_stock_price", "get_financials", "calculate_score"]
        schemas, fn_map = get_tools(tool_names)

        # 加入委托工具
        schemas.append(DELEGATE_TOOL)

        super().__init__(
            name="analyst",
            model=MODELS["analyst"],
            system_prompt=ANALYST_PROMPT,
            tools_schemas=schemas,
            tools_map=fn_map,
            max_turns=5,
        )

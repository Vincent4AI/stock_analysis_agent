"""
RoutingAgent — 意图路由

面试重点：
- tool_choice="required" 强制结构化输出
- 用最便宜的模型做分类（对标AIGEXBot的Gemini Flash Lite）
"""
import json
from .base import BaseAgent
from config import MODELS

ROUTING_PROMPT = """你是一个路由Agent，负责将用户请求路由到合适的专业Agent。

可用Agent：
- analyst: 股票分析、估值评估、投资建议、财务分析
- news: 新闻搜索、市场情绪分析、舆情监控

路由规则：
1. 涉及股票分析、估值、财务数据 → analyst
2. 涉及新闻、情绪、舆情 → news
3. 综合分析请求（如"分析投资价值"）→ analyst（analyst可以委托news）
4. 不确定时默认 → analyst

你必须调用route_to_agent函数，不要直接回复。"""

ROUTE_TOOL = {
    "type": "function",
    "function": {
        "name": "route_to_agent",
        "description": "将用户请求路由到合适的专业Agent",
        "parameters": {
            "type": "object",
            "properties": {
                "agent": {
                    "type": "string",
                    "enum": ["analyst", "news"],
                    "description": "目标Agent名称",
                },
                "reasoning": {
                    "type": "string",
                    "description": "路由决策的简短理由",
                },
            },
            "required": ["agent", "reasoning"],
        },
    },
}


class RoutingAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="router",
            model=MODELS["router"],
            system_prompt=ROUTING_PROMPT,
        )

    def route(self, query: str, on_event=None) -> tuple[str, str]:
        """
        路由用户请求到目标Agent

        返回: (agent_name, reasoning)
        """
        self._emit(on_event, 'routing_start', '正在分析用户意图...')

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"路由这个请求: {query}"},
        ]

        response = self.call_llm(
            messages,
            tools=[ROUTE_TOOL],
            tool_choice="required",
        )

        if response.tool_calls:
            args = json.loads(response.tool_calls[0].function.arguments)
            agent = args.get("agent", "analyst")
            reasoning = args.get("reasoning", "")
            self._emit(on_event, 'routing_done',
                       f'路由到 {agent} Agent（{reasoning}）',
                       target=agent, reasoning=reasoning)
            return agent, reasoning

        self._emit(on_event, 'routing_done', '默认路由到 analyst Agent',
                   target='analyst', reasoning='default fallback')
        return "analyst", "default fallback"

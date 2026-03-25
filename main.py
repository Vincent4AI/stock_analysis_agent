"""
主入口 — 顶层编排器

路由 → 执行 → 处理委托 → 汇总
"""
# 先导入工具模块，触发@tool装饰器注册
import tools.market
import tools.scoring
import tools.news

from agents.router import RoutingAgent
from agents.analyst import AnalystAgent
from agents.news import NewsAgent


class AIAgent:
    """顶层编排器"""

    def __init__(self):
        self.router = RoutingAgent()
        self.agents = {
            "analyst": AnalystAgent(),
            "news": NewsAgent(),
        }

    def _emit(self, on_event, event_type: str, message: str, **data):
        event = {'type': event_type, 'agent': 'orchestrator', 'message': message}
        if data:
            event['data'] = data
        if on_event:
            on_event(event)
        else:
            print(f"  [orchestrator] {message}")

    def process(self, query: str, on_event=None) -> str:
        """
        完整处理流程：
        1. RoutingAgent路由
        2. 执行目标Agent（ReAct循环）
        3. 处理委托（如果有）
        4. 返回最终结果
        """
        self._emit(on_event, 'start', f'开始分析: {query}', query=query)

        # Step 1: 路由
        agent_name, reasoning = self.router.route(query, on_event=on_event)

        # Step 2: 执行目标Agent
        self._emit(on_event, 'agent_start',
                   f'启动 {agent_name} Agent',
                   agent_name=agent_name)
        agent = self.agents[agent_name]
        result = agent.run(query, on_event=on_event)

        # Step 3: 处理委托
        if result.startswith("__DELEGATE__:"):
            _, delegate_agent, delegate_query = result.split(":", 2)
            self._emit(on_event, 'delegate',
                       f'委托给 {delegate_agent} Agent: {delegate_query}',
                       from_agent=agent_name, to_agent=delegate_agent,
                       delegate_query=delegate_query)

            delegate_result = self.agents[delegate_agent].run(
                delegate_query, on_event=on_event)

            # 将委托结果传回原Agent做最终总结
            self._emit(on_event, 'agent_start',
                       f'回传结果给 {agent_name} Agent 做最终总结',
                       agent_name=agent_name)
            context = f"新闻分析结果:\n{delegate_result}"
            result = agent.run(query, context=context, on_event=on_event)

        self._emit(on_event, 'result', '分析完成', report=result)
        return result


if __name__ == "__main__":
    ai = AIAgent()

    print("\n" + "=" * 30)
    print("测试1: 简单股票分析")
    print("=" * 30)
    ai.process("帮我分析一下贵州茅台（600519）的投资价值")

    print("\n" + "=" * 30)
    print("测试2: 需要新闻情绪的综合分析")
    print("=" * 30)
    ai.process("分析中国平安（601318）的基本面和近期市场情绪")

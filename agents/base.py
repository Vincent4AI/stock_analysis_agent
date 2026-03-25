"""
BaseAgent — Agent基类 + ReAct循环核心实现
"""
import json
import re
import threading
from openai import OpenAI
from typing import Callable

from config import MINIMAX_API_KEY, MINIMAX_BASE_URL

# ====== 线程局部变量：支持前端传入 API Key ======
_request_ctx = threading.local()


def set_request_config(api_key: str, base_url: str = '', model: str = ''):
    """设置当前线程的 API 配置（由 app.py 在每次请求时调用）"""
    _request_ctx.api_key = api_key
    _request_ctx.base_url = base_url
    _request_ctx.model = model
    _request_ctx.client = None


def get_model_override() -> str:
    """获取前端指定的模型（空串表示使用默认）"""
    return getattr(_request_ctx, 'model', '')


def _get_client() -> OpenAI:
    """获取当前线程的 OpenAI 客户端（按需创建，同线程复用）"""
    cached = getattr(_request_ctx, 'client', None)
    if cached:
        return cached
    api_key = getattr(_request_ctx, 'api_key', '') or MINIMAX_API_KEY
    base_url = getattr(_request_ctx, 'base_url', '') or MINIMAX_BASE_URL
    client = OpenAI(api_key=api_key, base_url=base_url)
    _request_ctx.client = client
    return client


def strip_think_tags(content: str) -> str:
    """去除MiniMax M2.7返回的<think>标签"""
    if not content:
        return content or ""
    return re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()


class BaseAgent:
    """Agent基类：封装LLM调用"""

    def __init__(self, name: str, model: str, system_prompt: str):
        self.name = name
        self.model = model
        self.system_prompt = system_prompt

    def _emit(self, on_event, event_type: str, message: str, **data):
        """发射事件，供UI实时展示"""
        event = {'type': event_type, 'agent': self.name, 'message': message}
        if data:
            event['data'] = data
        if on_event:
            on_event(event)
        else:
            print(f"  [{self.name}] {message}")

    def call_llm(self, messages: list[dict], tools: list[dict] = None,
                 tool_choice: str = "auto") -> dict:
        """统一的LLM调用接口"""
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.3,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice

        # 前端指定的模型优先
        override = get_model_override()
        if override:
            kwargs['model'] = override

        client = _get_client()
        response = client.chat.completions.create(**kwargs)
        return response.choices[0].message


class ReActAgent(BaseAgent):
    """ReAct Agent — Think → Act → Observe 循环"""

    def __init__(self, name: str, model: str, system_prompt: str,
                 tools_schemas: list[dict], tools_map: dict[str, Callable],
                 max_turns: int = 5):
        super().__init__(name, model, system_prompt)
        self.tools_schemas = tools_schemas
        self.tools_map = tools_map
        self.max_turns = max_turns

    def run(self, query: str, context: str = "", on_event=None) -> str:
        """执行ReAct循环"""
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"{context}\n\n{query}" if context else query},
        ]

        for turn in range(self.max_turns):
            self._emit(on_event, 'turn',
                       f'第 {turn + 1}/{self.max_turns} 轮思考',
                       turn=turn + 1, max_turns=self.max_turns)

            response = self.call_llm(messages, self.tools_schemas, tool_choice="auto")

            if not response.tool_calls:
                self._emit(on_event, 'answer', 'ReAct循环结束，生成回答')
                return strip_think_tags(response.content)

            messages.append({
                "role": "assistant",
                "content": response.content,
                "tool_calls": [
                    {"id": tc.id, "type": "function",
                     "function": {"name": tc.function.name,
                                  "arguments": tc.function.arguments}}
                    for tc in response.tool_calls
                ],
            })

            for tool_call in response.tool_calls:
                fn_name = tool_call.function.name
                fn_args = json.loads(tool_call.function.arguments)

                self._emit(on_event, 'tool_call',
                           f'{fn_name}({json.dumps(fn_args, ensure_ascii=False)})',
                           tool=fn_name, args=fn_args)

                if fn_name == "delegate_to_agent":
                    self._emit(on_event, 'delegate_request',
                               f'请求委托给 {fn_args["agent"]} Agent',
                               target=fn_args['agent'], query=fn_args['query'])
                    return f"__DELEGATE__:{fn_args['agent']}:{fn_args['query']}"

                if fn_name in self.tools_map:
                    try:
                        result = self.tools_map[fn_name](**fn_args)
                    except Exception as e:
                        result = f"工具执行错误: {str(e)}"
                else:
                    result = f"未知工具: {fn_name}"

                self._emit(on_event, 'tool_result', result,
                           tool=fn_name, result=result)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                })

        self._emit(on_event, 'force_summary', f'达到最大轮数({self.max_turns})，强制总结')
        response = self.call_llm(messages, tool_choice="none")
        return strip_think_tags(response.content)

# Mini Stock Agent — AI选股Agent练手项目

## 项目目标

用 **~300行Python** 构建一个完整的多Agent选股系统，覆盖面试中所有核心Agent概念：

- **Function Calling / Tool Use**：定义工具Schema → LLM决策调用 → 执行 → 结果返回
- **tool_choice**：`"required"` / `"auto"` / `"none"` 三种模式的实际使用
- **ReAct循环**：Think → Act → Observe → Think → ...
- **Multi-Agent编排**：RoutingAgent → PlanningAgent → 专业Agent
- **动态委托**：Agent之间的运行时协作

## 架构概览

```
用户: "分析一下贵州茅台的投资价值"
        │
        ▼
┌──────────────────┐
│  RoutingAgent     │  model: gpt-4o-mini (轻量)
│  tool_choice:     │  tool: route_to_agent()
│  "required"       │  输出: {agent: "analyst", reasoning: "..."}
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  AnalystAgent     │  model: gpt-4o
│  tool_choice:     │  tools: [get_stock_price, get_financials,
│  "auto"           │          calculate_score, delegate_to_agent]
│  max_turns: 5     │
│                   │  ReAct循环:
│  Think: 需要先查价格│  → Act: get_stock_price("600519")
│  Observe: ¥1800   │  → Think: 再查财报
│  Act: get_financials│ → Observe: PE=30, ROE=28%
│  Act: calculate_score│→ Observe: 综合得分78/100
│  Think: 需要新闻情绪│  → Act: delegate_to_agent("news")
│  ...               │
└──────────────────┘
         │ delegate
         ▼
┌──────────────────┐
│  NewsAgent        │  model: gpt-4o-mini
│  tool_choice:     │  tools: [search_news, analyze_sentiment]
│  "auto"           │  max_turns: 3
│  ReAct: 搜新闻 →  │
│  分析情绪 → 返回   │
└──────────────────┘
```

## 目录结构

```
mini-stock-agent/
├── main.py              # 入口 + 顶层编排器（AIAgent）
├── agents/
│   ├── __init__.py
│   ├── base.py          # BaseAgent + ReAct循环核心
│   ├── router.py        # RoutingAgent (tool_choice="required")
│   ├── analyst.py       # AnalystAgent (ReAct + 多工具)
│   └── news.py          # NewsAgent (ReAct + 委托目标)
├── tools/
│   ├── __init__.py
│   ├── registry.py      # 工具注册 + Schema自动生成
│   ├── market.py        # 行情工具: get_stock_price, get_financials
│   ├── scoring.py       # 打分工具: calculate_score
│   └── news.py          # 新闻工具: search_news, analyze_sentiment
├── models.py            # 数据模型 (TaskPlan, ToolCall等)
├── config.py            # 配置 (API keys, model names)
├── requirements.txt
└── PROJECT.md           # 本文件
```

## 核心代码设计

---

### 1. config.py — 配置

```python
"""项目配置"""
import os

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# 不同Agent用不同模型 — 面试话术：按任务复杂度分层选模型
MODELS = {
    "router": "gpt-4o-mini",     # 路由只需分类，用最便宜的
    "analyst": "gpt-4o",          # 分析需要强推理
    "news": "gpt-4o-mini",        # 新闻摘要用轻量模型
}
```

---

### 2. models.py — 数据模型

```python
"""核心数据模型"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"

@dataclass
class TaskStep:
    content: str
    agent: str
    status: TaskStatus = TaskStatus.PENDING
    result: str = ""

@dataclass
class TaskPlan:
    query: str
    steps: list[TaskStep] = field(default_factory=list)
    current_step: int = 0

    @property
    def is_finished(self) -> bool:
        return self.current_step >= len(self.steps) or any(
            s.status == TaskStatus.FAILED for s in self.steps
        )

    def current(self) -> TaskStep:
        return self.steps[self.current_step]

    def advance(self, result: str):
        self.steps[self.current_step].status = TaskStatus.SUCCESS
        self.steps[self.current_step].result = result
        self.current_step += 1
```

---

### 3. tools/registry.py — 工具注册（核心：Schema自动生成）

```python
"""
工具注册中心 — 从Python函数自动生成OpenAI Function Calling Schema

面试重点：这就是Function Calling的工具定义层
"""
import inspect
import json
from typing import Callable, get_type_hints

# 全局工具注册表
_TOOL_REGISTRY: dict[str, dict] = {}

# Python类型 → JSON Schema类型映射
TYPE_MAP = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
}

def tool(description: str):
    """装饰器：注册一个函数为Agent可调用的工具"""
    def decorator(fn: Callable):
        schema = _build_schema(fn, description)
        _TOOL_REGISTRY[fn.__name__] = {
            "function": fn,
            "schema": schema,
        }
        return fn
    return decorator

def _build_schema(fn: Callable, description: str) -> dict:
    """从函数签名自动生成OpenAI tools格式的JSON Schema"""
    hints = get_type_hints(fn)
    sig = inspect.signature(fn)

    properties = {}
    required = []

    for name, param in sig.parameters.items():
        if name in ("self",):
            continue
        ptype = hints.get(name, str)
        json_type = TYPE_MAP.get(ptype, "string")

        # 从docstring提取参数描述
        param_desc = f"Parameter: {name}"
        if fn.__doc__:
            for line in fn.__doc__.split("\n"):
                if name in line and ":" in line:
                    param_desc = line.split(":", 1)[-1].strip()
                    break

        properties[name] = {"type": json_type, "description": param_desc}
        if param.default is inspect.Parameter.empty:
            required.append(name)

    return {
        "type": "function",
        "function": {
            "name": fn.__name__,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }

def get_tools(names: list[str]) -> tuple[list[dict], dict[str, Callable]]:
    """获取指定工具的schemas和函数映射"""
    schemas = []
    fn_map = {}
    for name in names:
        if name in _TOOL_REGISTRY:
            schemas.append(_TOOL_REGISTRY[name]["schema"])
            fn_map[name] = _TOOL_REGISTRY[name]["function"]
    return schemas, fn_map
```

---

### 4. tools/market.py — 行情工具（模拟数据）

```python
"""行情数据工具 — 面试时说明这里可以替换为真实API"""
from .registry import tool

# 模拟股票数据（面试说明：生产环境接入tushare/akshare/wind）
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

@tool("获取股票实时价格和基本信息。输入股票代码（如600519），返回价格、市值等。")
def get_stock_price(stock_code: str) -> str:
    """
    stock_code: 6位股票代码，如 600519
    """
    data = MOCK_DATA.get(stock_code)
    if not data:
        return f"未找到股票 {stock_code} 的数据"
    return (
        f"股票: {data['name']} ({stock_code})\n"
        f"当前价格: ¥{data['price']}\n"
        f"市值: {data['market_cap']}亿\n"
        f"股息率: {data['dividend_yield']}%"
    )

@tool("获取股票财务指标。输入股票代码，返回PE、PB、ROE、营收增速等关键财务数据。")
def get_financials(stock_code: str) -> str:
    """
    stock_code: 6位股票代码
    """
    data = MOCK_DATA.get(stock_code)
    if not data:
        return f"未找到股票 {stock_code} 的财务数据"
    return (
        f"股票: {data['name']} ({stock_code})\n"
        f"PE(市盈率): {data['pe']}\n"
        f"PB(市净率): {data['pb']}\n"
        f"ROE(净资产收益率): {data['roe']}%\n"
        f"营收增速: {data['revenue_growth']}%\n"
        f"净利润增速: {data['net_profit_growth']}%"
    )
```

---

### 5. tools/scoring.py — 打分工具

```python
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
```

---

### 6. tools/news.py — 新闻工具

```python
"""新闻搜索和情绪分析工具"""
from .registry import tool

@tool("搜索股票相关新闻。输入股票名称或代码，返回最近的新闻摘要。")
def search_news(query: str) -> str:
    """
    query: 搜索关键词（股票名称或代码）
    """
    # 模拟新闻数据（生产环境接入新闻API）
    mock_news = {
        "茅台": [
            "贵州茅台发布2024年报，营收同比增长15.3%，净利润增长18.7%",
            "茅台冰淇淋业务全面升级，跨界创新持续推进",
            "外资机构上调茅台目标价至2200元，维持买入评级",
        ],
        "平安": [
            "中国平安寿险改革成效显现，新业务价值大幅增长",
            "平安银行零售转型深化，资产质量持续改善",
        ],
    }
    for key, news_list in mock_news.items():
        if key in query:
            return f"关于 {query} 的最新新闻:\n" + "\n".join(
                f"  {i+1}. {n}" for i, n in enumerate(news_list)
            )
    return f"未找到关于 {query} 的相关新闻"

@tool("分析新闻文本的市场情绪。输入新闻内容，返回情绪评分(-1到1)和分析。")
def analyze_sentiment(news_text: str) -> str:
    """
    news_text: 要分析的新闻文本内容
    """
    # 简化版情绪分析（面试说明：可接入FinBERT等金融NLP模型）
    positive_words = ["增长", "上调", "买入", "升级", "改善", "创新", "突破"]
    negative_words = ["下降", "下调", "卖出", "风险", "亏损", "减持"]

    pos = sum(1 for w in positive_words if w in news_text)
    neg = sum(1 for w in negative_words if w in news_text)

    if pos + neg == 0:
        score = 0.0
    else:
        score = round((pos - neg) / (pos + neg), 2)

    if score > 0.3:
        label = "积极 📈"
    elif score < -0.3:
        label = "消极 📉"
    else:
        label = "中性 ➡️"

    return f"情绪评分: {score} ({label})\n正面信号: {pos}个, 负面信号: {neg}个"
```

---

### 7. agents/base.py — BaseAgent + ReAct核心（最重要的文件）

```python
"""
BaseAgent — Agent基类 + ReAct循环核心实现

面试重点：这个文件展示了ReAct模式的完整实现
"""
import json
from openai import OpenAI
from typing import Callable

from config import OPENAI_API_KEY

client = OpenAI(api_key=OPENAI_API_KEY)


class BaseAgent:
    """Agent基类：封装LLM调用"""

    def __init__(self, name: str, model: str, system_prompt: str):
        self.name = name
        self.model = model
        self.system_prompt = system_prompt

    def call_llm(self, messages: list[dict], tools: list[dict] = None,
                 tool_choice: str = "auto") -> dict:
        """
        统一的LLM调用接口

        tool_choice 三种模式（面试核心概念）：
        - "required": 强制调用工具（RoutingAgent用）
        - "auto": LLM自行决定是否调用工具（AnalystAgent用）
        - "none": 禁止调用工具（纯推理场景）
        """
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.3,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice

        response = client.chat.completions.create(**kwargs)
        return response.choices[0].message


class ReActAgent(BaseAgent):
    """
    ReAct Agent — Think → Act → Observe 循环

    面试重点：这是ReAct论文(Yao et al., 2022)的标准实现
    对标你AIGEXBot中NodeAgent.process()的ReAct循环
    """

    def __init__(self, name: str, model: str, system_prompt: str,
                 tools_schemas: list[dict], tools_map: dict[str, Callable],
                 max_turns: int = 5):
        super().__init__(name, model, system_prompt)
        self.tools_schemas = tools_schemas
        self.tools_map = tools_map
        self.max_turns = max_turns

    def run(self, query: str, context: str = "") -> str:
        """
        执行ReAct循环

        面试话术：每一轮LLM决定是调工具还是直接回答
        如果调工具 → 执行 → 结果append到messages → 下一轮
        如果直接回答 → 结束循环
        max_turns防止无限循环（对标AIGEXBot的reasoning_effort → max_turns映射）
        """
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"{context}\n\n{query}" if context else query},
        ]

        for turn in range(self.max_turns):
            print(f"  [{self.name}] Turn {turn + 1}/{self.max_turns}")

            # Think: LLM推理，决定下一步行动
            response = self.call_llm(messages, self.tools_schemas, tool_choice="auto")

            # 情况1: LLM决定直接回答（没有tool_calls）→ 循环结束
            if not response.tool_calls:
                print(f"  [{self.name}] → 直接回答（ReAct循环结束）")
                return response.content

            # 情况2: LLM决定调用工具 → Act + Observe
            # 先把assistant的tool_calls消息加入历史
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

            # 执行每个工具调用
            for tool_call in response.tool_calls:
                fn_name = tool_call.function.name
                fn_args = json.loads(tool_call.function.arguments)

                print(f"  [{self.name}] → Act: {fn_name}({fn_args})")

                # 特殊处理：委托工具（对标AIGEXBot的call_other_agent）
                if fn_name == "delegate_to_agent":
                    return f"__DELEGATE__:{fn_args['agent']}:{fn_args['query']}"

                # 执行普通工具
                if fn_name in self.tools_map:
                    try:
                        result = self.tools_map[fn_name](**fn_args)
                    except Exception as e:
                        result = f"工具执行错误: {str(e)}"
                else:
                    result = f"未知工具: {fn_name}"

                print(f"  [{self.name}] → Observe: {result[:80]}...")

                # Observe: 将工具结果加入消息历史
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                })

        # 超过max_turns → 强制用"none"让LLM总结
        print(f"  [{self.name}] → 达到max_turns，强制总结")
        response = self.call_llm(messages, tool_choice="none")
        return response.content
```

---

### 8. agents/router.py — RoutingAgent

```python
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

    def route(self, query: str) -> tuple[str, str]:
        """
        路由用户请求到目标Agent

        返回: (agent_name, reasoning)

        关键：tool_choice="required" 强制LLM必须调用route_to_agent
        对标AIGEXBot RoutingAgent的设计
        """
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"路由这个请求: {query}"},
        ]

        response = self.call_llm(
            messages,
            tools=[ROUTE_TOOL],
            tool_choice="required",   # ← 面试核心：强制调用工具
        )

        if response.tool_calls:
            args = json.loads(response.tool_calls[0].function.arguments)
            agent = args.get("agent", "analyst")
            reasoning = args.get("reasoning", "")
            print(f"  [Router] → {agent} (理由: {reasoning})")
            return agent, reasoning

        # Fallback（理论上不会到这里，因为tool_choice="required"）
        return "analyst", "default fallback"
```

---

### 9. agents/analyst.py — AnalystAgent（核心Agent）

```python
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
```

---

### 10. agents/news.py — NewsAgent

```python
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
```

---

### 11. main.py — 顶层编排器（AIAgent）

```python
"""
主入口 — 顶层编排器

面试重点：对标AIGEXBot的AIAgent.process()
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
    """顶层编排器 — 对标AIGEXBot的AIAgent"""

    def __init__(self):
        self.router = RoutingAgent()
        self.agents = {
            "analyst": AnalystAgent(),
            "news": NewsAgent(),
        }

    def process(self, query: str) -> str:
        """
        完整处理流程（对标AIAgent.process()）：
        1. RoutingAgent路由
        2. 执行目标Agent（ReAct循环）
        3. 处理委托（如果有）
        4. 返回最终结果
        """
        print(f"\n{'='*60}")
        print(f"用户: {query}")
        print(f"{'='*60}")

        # Step 1: 路由
        print("\n[Step 1] 路由决策...")
        agent_name, reasoning = self.router.route(query)

        # Step 2: 执行目标Agent
        print(f"\n[Step 2] 执行 {agent_name} Agent...")
        agent = self.agents[agent_name]
        result = agent.run(query)

        # Step 3: 处理委托（对标AIGEXBot的动态委托机制）
        if result.startswith("__DELEGATE__:"):
            _, delegate_agent, delegate_query = result.split(":", 2)
            print(f"\n[Step 3] 委托 → {delegate_agent} Agent: {delegate_query}")

            delegate_result = self.agents[delegate_agent].run(delegate_query)

            # 将委托结果传回原Agent做最终总结
            print(f"\n[Step 4] 回传结果给 {agent_name} Agent 做最终总结...")
            context = f"新闻分析结果:\n{delegate_result}"
            result = agent.run(query, context=context)

        print(f"\n{'='*60}")
        print(f"最终分析:\n{result}")
        print(f"{'='*60}")
        return result


if __name__ == "__main__":
    ai = AIAgent()

    # 测试用例
    print("\n" + "🔥" * 30)
    print("测试1: 简单股票分析")
    print("🔥" * 30)
    ai.process("帮我分析一下贵州茅台（600519）的投资价值")

    print("\n" + "🔥" * 30)
    print("测试2: 需要新闻情绪的综合分析")
    print("🔥" * 30)
    ai.process("分析中国平安（601318）的基本面和近期市场情绪")
```

---

### 12. requirements.txt

```
openai>=1.30.0
```

---

## 运行方式

```bash
# 1. 安装依赖
pip install openai

# 2. 设置API Key
export OPENAI_API_KEY="sk-..."

# 3. 运行
python main.py
```

---

## 面试对标关系

| 本项目概念 | AIGEXBot对标 | CryptoQuantGo对标 |
|-----------|-------------|-------------------|
| `RoutingAgent` + tool_choice="required" | RoutingAgent (Gemini Flash) | - |
| `ReActAgent.run()` 循环 | NodeAgent.process() ReAct循环 | - |
| `delegate_to_agent` 工具 | `call_other_agent` 动态委托 | - |
| `AIAgent.process()` 编排 | AIAgent.process() 顶层编排 | Orchestrator.Run() |
| `@tool` 装饰器自动Schema | schema_generator.py 自动生成 | - |
| `max_turns` 控制 | `_get_max_turns()` 映射 | MaxTurns=1/5 |
| `MOCK_DATA` 模拟数据 | BirdEye API 真实数据 | 30天K线数据 |
| `calculate_score` 打分 | `calculate_factor_scores()` | MeetsThreshold门槛 |
| 分层模型选择 | GPT-4o + Flash Lite + Claude | Claude Opus |

## 扩展建议（面试加分）

如果面试官问"如果继续完善这个项目"：

1. **加入PlanningAgent**：复杂请求先分解为2-4步TaskPlan，对标AIGEXBot
2. **接入真实数据**：tushare/akshare获取A股数据，替换MOCK_DATA
3. **加入Redis缓存**：缓存LLM响应，对标AIGEXBot的10min TTL缓存
4. **加入因子IC分析**：截面IC计算，对标quant_server的factor_analyzer
5. **接入FinBERT**：真实的金融NLP情绪分析，替换关键词匹配
6. **加入回测模块**：简单的选股回测，计算Sharpe/MaxDD

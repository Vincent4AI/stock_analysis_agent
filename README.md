# Mini Stock Agent

AI 多Agent协作的智能选股分析系统，基于 ReAct 模式构建，覆盖 Function Calling、tool_choice、Multi-Agent 编排等核心 Agent 概念。

**在线体验：https://mini-stock-agent.vercel.app**

## 核心 Idea

用一个精简的项目展示 AI Agent 系统的完整架构：

- **不是"调一次 API"**，而是多个 Agent 协作，通过 ReAct 循环自主决策调用哪些工具
- **不是"写死流程"**，而是 LLM 动态规划分析步骤，按需委托其他 Agent
- **不是"模拟数据"**，而是接入真实行情（腾讯财经）和新闻（东方财富）

## 架构

```
用户: "分析贵州茅台的投资价值"
        │
        ▼
┌──────────────────┐
│  RoutingAgent     │  tool_choice="required"
│  意图路由          │  强制调用 route_to_agent()
│                   │  输出: analyst / news
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  AnalystAgent     │  tool_choice="auto"  max_turns=5
│  ReAct 循环:      │
│  Think → Act →    │  工具: get_stock_price
│  Observe → Think  │        get_financials
│  → Act → ...      │        calculate_score
│                   │        delegate_to_agent
└────────┬─────────┘
         │ delegate (按需)
         ▼
┌──────────────────┐
│  NewsAgent        │  tool_choice="auto"  max_turns=3
│  ReAct 循环:      │  工具: search_news
│  搜新闻 → 分析    │        analyze_sentiment
│  情绪 → 返回      │
└──────────────────┘
```

### 关键设计

| 概念 | 实现 |
|------|------|
| **Function Calling** | `@tool` 装饰器从函数签名自动生成 OpenAI tools Schema |
| **tool_choice** | Router 用 `"required"` 强制结构化输出，Analyst/News 用 `"auto"` 自主决策 |
| **ReAct 循环** | `ReActAgent.run()` — Think→Act→Observe 循环，`max_turns` 防无限循环 |
| **Multi-Agent** | `AIAgent` 编排器：路由→执行→委托→汇总 |
| **动态委托** | `delegate_to_agent` 工具实现运行时 Agent 间协作 |

### 数据源

| 数据 | 来源 | 方式 |
|------|------|------|
| 实时行情（价格/PE/PB/市值） | 腾讯财经 | urllib 直连 |
| 历史日K | 新浪财经 | akshare |
| 财务指标（ROE/增速） | 东方财富 | akshare |
| 实时新闻 | 东方财富 | akshare |

所有接口在网络不可用时自动回退模拟数据。

## 项目结构

```
mini-stock-agent/
├── app.py                # Flask Web 服务 + SSE 流式接口
├── main.py               # AIAgent 顶层编排器
├── config.py             # 配置 (API URL, 模型名)
├── models.py             # 数据模型 (TaskPlan, TaskStep)
├── agents/
│   ├── base.py           # BaseAgent + ReActAgent 核心
│   ├── router.py         # RoutingAgent (意图路由)
│   ├── analyst.py        # AnalystAgent (股票分析)
│   └── news.py           # NewsAgent (新闻情绪)
├── tools/
│   ├── registry.py       # @tool 装饰器 + Schema 自动生成
│   ├── data.py           # 共享数据层 (缓存/行情/新闻)
│   ├── market.py         # get_stock_price, get_financials
│   ├── scoring.py        # calculate_score (因子打分)
│   └── news.py           # search_news, analyze_sentiment
├── templates/
│   └── index.html        # 前端 UI (设置/流程/报告)
├── api/
│   └── index.py          # Vercel Serverless 入口
├── vercel.json           # Vercel 部署配置
└── requirements.txt
```

## 使用方法

### 在线使用

打开 https://mini-stock-agent.vercel.app ，点击右上角齿轮配置 MiniMax API Key 即可。

### 本地运行

```bash
# 安装依赖
pip install -r requirements.txt

# 启动 Web 服务
python app.py
# 访问 http://127.0.0.1:5001
```

打开浏览器后在设置中输入 API Key，或在 `.env` 文件中配置：

```
MINIMAX_API_KEY=your_key_here
```

### CLI 模式

```bash
# 设置环境变量
export MINIMAX_API_KEY="your_key_here"

# 运行命令行版本
python main.py
```

## 技术栈

- **LLM**: MiniMax M2.7（兼容 OpenAI SDK）
- **后端**: Flask + SSE 流式推送
- **前端**: 原生 HTML/CSS/JS + marked.js
- **数据**: akshare + 腾讯财经 API
- **部署**: Vercel Serverless Functions

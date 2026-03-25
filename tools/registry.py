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

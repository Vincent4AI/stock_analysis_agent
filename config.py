"""项目配置"""
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # Vercel 环境无 dotenv，API Key 由前端传入

# MiniMax API配置
MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY", "")
MINIMAX_BASE_URL = "https://api.minimax.io/v1"

# 不同Agent用不同模型
MODELS = {
    "router": "MiniMax-M2.7",
    "analyst": "MiniMax-M2.7",
    "news": "MiniMax-M2.7",
}

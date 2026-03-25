"""Vercel Serverless Function 入口 — 导入 Flask app"""
import sys
import os

# 确保项目根目录在 Python 路径中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app import app

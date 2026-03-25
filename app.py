"""Flask Web 服务 — SSE流式推送分析事件"""
import json
import queue
import threading

from flask import Flask, Response, request, render_template

# 触发工具注册
import tools.market
import tools.scoring
import tools.news

from main import AIAgent
from agents.base import set_request_config

app = Flask(__name__)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/analyze', methods=['POST'])
def analyze():
    data = request.get_json() or {}
    query = data.get('query', '').strip()
    api_key = request.headers.get('X-API-Key', '').strip()
    base_url = request.headers.get('X-Base-URL', '').strip()
    model = request.headers.get('X-Model', '').strip()

    if not api_key:
        return Response(
            f"data: {json.dumps({'type': 'error', 'message': '请先在设置中配置 API Key'}, ensure_ascii=False)}\n\n",
            mimetype='text/event-stream',
        )
    if not query:
        return Response(
            f"data: {json.dumps({'type': 'error', 'message': '请输入分析内容'}, ensure_ascii=False)}\n\n",
            mimetype='text/event-stream',
        )

    q = queue.Queue()

    def on_event(event):
        q.put(event)

    def run_agent():
        try:
            set_request_config(api_key, base_url, model)
            ai = AIAgent()
            ai.process(query, on_event=on_event)
        except Exception as e:
            q.put({'type': 'error', 'agent': 'system',
                   'message': f'分析出错: {str(e)}'})
        finally:
            q.put(None)

    thread = threading.Thread(target=run_agent, daemon=True)
    thread.start()

    def generate():
        while True:
            try:
                event = q.get(timeout=120)
            except queue.Empty:
                yield f"data: {json.dumps({'type': 'error', 'message': '分析超时'}, ensure_ascii=False)}\n\n"
                break
            if event is None:
                yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
                break
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
        },
    )


if __name__ == '__main__':
    app.run(debug=True, port=5001, threaded=True)

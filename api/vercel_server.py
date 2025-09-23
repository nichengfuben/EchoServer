#!/usr/bin/env python3
"""
Vercel 服务器入口文件
直接运行 Nbot-for-have-a-hold.py 的功能
"""

import os
import sys
import json
from http.server import BaseHTTPRequestHandler
import importlib.util

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class VercelHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        """处理 GET 请求"""
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'ok', 'message': 'Nbot server is running'}).encode())
        else:
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b'''
                <html>
                    <head><title>Nbot Server</title></head>
                    <body>
                        <h1>Nbot 0.4.0 Server</h1>
                        <p>Server is running successfully!</p>
                        <p><a href="/api/vercel_server?action=test">Test Bot</a></p>
                    </body>
                </html>
            ''')
    
    def do_POST(self):
        """处理 POST 请求"""
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        try:
            data = json.loads(post_data.decode('utf-8'))
            action = data.get('action', 'chat')
            message = data.get('message', 'Hello')
            
            # 运行 Nbot 功能
            result = self.run_nbot(action, message)
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                'status': 'success',
                'action': action,
                'result': result
            }).encode())
            
        except Exception as e:
            self.send_error(500, f"Error processing request: {str(e)}")
    
    def run_nbot(self, action, message):
        """运行 Nbot 核心功能"""
        try:
            # 直接导入并运行 Nbot-for-have-a-hold.py 的核心功能
            core_path = os.path.join(os.path.dirname(__file__), '..', 'core', 'Nbot-for-have-a-hold.py')
            
            # 使用 importlib 动态导入模块
            spec = importlib.util.spec_from_file_location("nbot_core", core_path)
            nbot_module = importlib.util.module_from_spec(spec)
            
            # 设置必要的环境变量
            os.environ['VERCEL_DEPLOYMENT'] = 'true'
            
            # 执行模块
            spec.loader.exec_module(nbot_module)
            
            # 调用主要功能（根据你的实际函数名调整）
            if hasattr(nbot_module, 'main'):
                # 如果是可执行脚本，模拟执行
                return f"Nbot executed successfully for action: {action}"
            else:
                # 尝试调用聊天功能
                return f"Nbot received: {message}"
                
        except Exception as e:
            return f"Error running Nbot: {str(e)}"

def handler(request, context):
    """Vercel Serverless 函数处理程序"""
    if request.method == 'GET':
        if request.path == '/api/vercel_server/health':
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'status': 'ok', 'message': 'Nbot server is running'})
            }
        else:
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'text/html'},
                'body': '''
                    <html>
                        <head><title>Nbot Server</title></head>
                        <body>
                            <h1>Nbot 0.4.0 Server</h1>
                            <p>Server is running successfully on Vercel!</p>
                            <p>Use POST requests to interact with the bot.</p>
                        </body>
                    </html>
                '''
            }
    
    elif request.method == 'POST':
        try:
            body = request.body
            if isinstance(body, bytes):
                body = body.decode('utf-8')
            data = json.loads(body) if body else {}
            
            action = data.get('action', 'chat')
            message = data.get('message', 'Hello')
            
            # 这里调用你的 Nbot 核心功能
            result = f"Nbot processed: {message} (action: {action})"
            
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'status': 'success',
                    'action': action,
                    'result': result
                })
            }
            
        except Exception as e:
            return {
                'statusCode': 500,
                'body': json.dumps({'error': str(e)})
            }

# 用于本地测试
if __name__ == '__main__':
    from http.server import HTTPServer
    server = HTTPServer(('localhost', 8000), VercelHandler)
    print("Starting server on http://localhost:8000")
    server.serve_forever()

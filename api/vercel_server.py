#!/usr/bin/env python3
"""
Vercel 服务器入口文件
直接运行 Nbot-for-have-a-hold.py
"""

import os
import sys
import json
import subprocess
from http.server import BaseHTTPRequestHandler

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
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({
                'status': 'success',
                'action': action,
                'result': result
            }).encode())
            
        except Exception as e:
            self.send_error(500, f"Error processing request: {str(e)}")
    
    def run_nbot(self, action, message):
        """直接运行 Nbot Python 文件"""
        try:
            # 找到 Nbot 核心文件路径
            script_dir = os.path.dirname(os.path.abspath(__file__))
            nbot_path = os.path.join(script_dir, '..', 'core', 'Nbot-for-have-a-hold.py')
            
            # 如果路径不存在，尝试其他可能的路径
            if not os.path.exists(nbot_path):
                nbot_path = os.path.join(script_dir, 'Nbot-for-have-a-hold.py')
            
            if not os.path.exists(nbot_path):
                nbot_path = os.path.join(script_dir, '..', 'Nbot-for-have-a-hold.py')
            
            if not os.path.exists(nbot_path):
                return f"Error: Nbot-for-have-a-hold.py not found"
            
            # 设置环境变量
            env = os.environ.copy()
            env['VERCEL_DEPLOYMENT'] = 'true'
            env['NBOT_ACTION'] = action
            env['NBOT_MESSAGE'] = message
            
            # 直接运行 Python 文件
            result = subprocess.run(
                [sys.executable, nbot_path],
                capture_output=True,
                text=True,
                timeout=30,  # 30秒超时
                env=env,
                cwd=os.path.dirname(nbot_path)
            )
            
            if result.returncode == 0:
                # 成功执行
                output = result.stdout.strip()
                if output:
                    return output
                else:
                    return f"Nbot executed successfully for action: {action}, message: {message}"
            else:
                # 执行出错
                error_msg = result.stderr.strip() if result.stderr else "Unknown error"
                return f"Error executing Nbot: {error_msg}"
                
        except subprocess.TimeoutExpired:
            return "Error: Nbot execution timeout (30s)"
        except Exception as e:
            return f"Error running Nbot: {str(e)}"

def handler(request, context):
    """Vercel Serverless 函数处理程序"""
    try:
        if request.method == 'GET':
            if hasattr(request, 'path') and '/health' in request.path:
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
                                <p>Example: POST {"action": "chat", "message": "Hello"}</p>
                            </body>
                        </html>
                    '''
                }
        
        elif request.method == 'POST':
            try:
                # 获取请求体
                body = getattr(request, 'body', '')
                if hasattr(request, 'get_json'):
                    data = request.get_json() or {}
                else:
                    if isinstance(body, bytes):
                        body = body.decode('utf-8')
                    data = json.loads(body) if body else {}
                
                action = data.get('action', 'chat')
                message = data.get('message', 'Hello')
                
                # 直接运行 Nbot
                result = run_nbot_direct(action, message)
                
                return {
                    'statusCode': 200,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({
                        'status': 'success',
                        'action': action,
                        'result': result
                    })
                }
                
            except Exception as e:
                return {
                    'statusCode': 500,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({'error': f'Processing error: {str(e)}'})
                }
        
        else:
            return {
                'statusCode': 405,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Method not allowed'})
            }
            
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': f'Server error: {str(e)}'})
        }

def run_nbot_direct(action, message):
    """直接运行 Nbot 的独立函数"""
    try:
        # 找到当前文件目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 尝试多个可能的路径
        possible_paths = [
            os.path.join(current_dir, '..', 'core', 'Nbot-for-have-a-hold.py'),
            os.path.join(current_dir, 'Nbot-for-have-a-hold.py'),
            os.path.join(current_dir, '..', 'Nbot-for-have-a-hold.py'),
            os.path.join(current_dir, '..', '..', 'Nbot-for-have-a-hold.py')
        ]
        
        nbot_path = None
        for path in possible_paths:
            if os.path.exists(path):
                nbot_path = path
                break
        
        if not nbot_path:
            return "Error: Nbot-for-have-a-hold.py not found in any expected location"
        
        # 设置环境变量
        env = os.environ.copy()
        env['VERCEL_DEPLOYMENT'] = 'true'
        env['NBOT_ACTION'] = str(action)
        env['NBOT_MESSAGE'] = str(message)
        
        # 直接执行 Python 文件
        result = subprocess.run(
            [sys.executable, nbot_path],
            capture_output=True,
            text=True,
            timeout=25,  # 25秒超时，给 Vercel 留余量
            env=env,
            cwd=os.path.dirname(nbot_path)
        )
        
        if result.returncode == 0:
            output = result.stdout.strip()
            return output if output else f"Nbot executed successfully. Action: {action}, Message: {message}"
        else:
            error_output = result.stderr.strip() if result.stderr else "No error details"
            return f"Execution failed (code: {result.returncode}): {error_output}"
            
    except subprocess.TimeoutExpired:
        return "Error: Nbot execution timeout"
    except FileNotFoundError:
        return "Error: Python interpreter not found"
    except Exception as e:
        return f"Unexpected error: {str(e)}"

# 用于本地测试
if __name__ == '__main__':
    from http.server import HTTPServer
    import threading
    
    def test_nbot():
        """测试 Nbot 执行"""
        print("Testing Nbot execution...")
        result = run_nbot_direct("test", "Hello World")
        print(f"Test result: {result}")
    
    # 启动测试
    test_thread = threading.Thread(target=test_nbot)
    test_thread.start()
    
    # 启动服务器
    server = HTTPServer(('localhost', 8000), VercelHandler)
    print("Starting server on http://localhost:8000")
    print("Test endpoint: http://localhost:8000/health")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped")
        server.shutdown()

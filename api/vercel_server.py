#!/usr/bin/env python3
"""
Vercel 服务器入口文件
直接运行 Nbot-for-have-a-hold.py
"""

import os
import sys
import json
import subprocess
from urllib.parse import parse_qs

def handler(request):
    """Vercel Serverless 函数处理程序 - 标准入口点"""
    try:
        # 获取请求方法
        method = getattr(request, 'method', 'GET')
        
        if method == 'GET':
            # 获取路径
            path = getattr(request, 'path', '/')
            
            if '/health' in path:
                return {
                    'statusCode': 200,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({
                        'status': 'ok', 
                        'message': 'Nbot server is running',
                        'python_version': sys.version
                    })
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
                                <p>Python version: ''' + sys.version + '''</p>
                                <p>Use POST requests to interact with the bot.</p>
                                <p><a href="/health">Health Check</a></p>
                            </body>
                        </html>
                    '''
                }
        
        elif method == 'POST':
            try:
                # 获取请求体
                body = getattr(request, 'body', b'')
                if isinstance(body, bytes):
                    body = body.decode('utf-8')
                
                data = json.loads(body) if body else {}
                action = data.get('action', 'chat')
                message = data.get('message', 'Hello')
                
                # 运行 Nbot
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
                        'message': message,
                        'result': result,
                        'python_version': sys.version
                    })
                }
                
            except Exception as e:
                return {
                    'statusCode': 500,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({
                        'error': f'POST processing error: {str(e)}',
                        'python_version': sys.version
                    })
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
            'body': json.dumps({
                'error': f'Server error: {str(e)}',
                'python_version': sys.version
            })
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
            return f"Error: Nbot-for-have-a-hold.py not found. Searched paths: {possible_paths}"
        
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
            timeout=25,  # 25秒超时
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

# 为了兼容性，也保留旧的处理方式
def app(environ, start_response):
    """WSGI 兼容入口"""
    return handler(environ)

# 本地测试
if __name__ == '__main__':
    # 模拟请求对象进行测试
    class MockRequest:
        def __init__(self):
            self.method = 'GET'
            self.path = '/health'
            self.body = b''
    
    test_request = MockRequest()
    response = handler(test_request)
    print("Test response:", response)

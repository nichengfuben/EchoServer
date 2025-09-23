#!/usr/bin/env python3
"""
Vercel 服务器 - 持续运行 Nbot 并提供状态查看
"""

import os
import sys
import json
import subprocess
import threading
import time
import queue
from datetime import datetime

# 全局变量存储 Nbot 进程和输出
nbot_process = None
output_queue = queue.Queue(maxsize=1000)  # 最多保存1000行输出
nbot_thread = None
process_start_time = None

def start_nbot_background():
    """在后台启动 Nbot 进程"""
    global nbot_process, nbot_thread, process_start_time
    
    if nbot_process and nbot_process.poll() is None:
        return "Nbot is already running"
    
    try:
        # 找到 Nbot 文件
        current_dir = os.path.dirname(os.path.abspath(__file__))
        possible_paths = [
            os.path.join(current_dir, '..', 'core', 'Nbot-for-have-a-hold.py'),
            os.path.join(current_dir, 'Nbot-for-have-a-hold.py'),
            os.path.join(current_dir, '..', 'Nbot-for-have-a-hold.py'),
        ]
        
        nbot_path = None
        for path in possible_paths:
            if os.path.exists(path):
                nbot_path = path
                break
        
        if not nbot_path:
            return f"Error: Nbot-for-have-a-hold.py not found"
        
        # 启动 Nbot 进程
        env = os.environ.copy()
        env['VERCEL_DEPLOYMENT'] = 'true'
        env['PYTHONUNBUFFERED'] = '1'  # 确保输出不被缓冲
        
        nbot_process = subprocess.Popen(
            [sys.executable, nbot_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
            cwd=os.path.dirname(nbot_path),
            bufsize=1  # 行缓冲
        )
        
        process_start_time = datetime.now()
        
        # 启动输出读取线程
        nbot_thread = threading.Thread(target=read_nbot_output, daemon=True)
        nbot_thread.start()
        
        return f"Nbot started successfully at {process_start_time}"
        
    except Exception as e:
        return f"Error starting Nbot: {str(e)}"

def read_nbot_output():
    """读取 Nbot 输出的线程函数"""
    global nbot_process, output_queue
    
    try:
        while nbot_process and nbot_process.poll() is None:
            line = nbot_process.stdout.readline()
            if line:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                log_entry = f"[{timestamp}] {line.strip()}"
                
                # 添加到队列，如果队列满了就丢弃最老的
                try:
                    output_queue.put_nowait(log_entry)
                except queue.Full:
                    try:
                        output_queue.get_nowait()  # 移除最老的
                        output_queue.put_nowait(log_entry)
                    except queue.Empty:
                        pass
    except Exception as e:
        error_msg = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Output reader error: {str(e)}"
        try:
            output_queue.put_nowait(error_msg)
        except queue.Full:
            pass

def get_nbot_status():
    """获取 Nbot 状态信息"""
    global nbot_process, process_start_time
    
    if not nbot_process:
        status = "Not started"
        uptime = "N/A"
    elif nbot_process.poll() is None:
        status = "Running"
        if process_start_time:
            uptime = str(datetime.now() - process_start_time)
        else:
            uptime = "Unknown"
    else:
        status = f"Stopped (exit code: {nbot_process.returncode})"
        uptime = "N/A"
    
    # 获取最近的输出
    recent_output = []
    temp_items = []
    
    # 从队列中获取所有项目
    while True:
        try:
            item = output_queue.get_nowait()
            temp_items.append(item)
        except queue.Empty:
            break
    
    # 把项目放回队列并保存到 recent_output
    for item in temp_items:
        recent_output.append(item)
        try:
            output_queue.put_nowait(item)
        except queue.Full:
            break
    
    return {
        "status": status,
        "uptime": uptime,
        "process_id": nbot_process.pid if nbot_process else None,
        "start_time": process_start_time.isoformat() if process_start_time else None,
        "output_lines": len(recent_output),
        "recent_output": recent_output[-50:] if recent_output else []  # 最近50行
    }

def handler(request):
    """Vercel 函数入口点"""
    try:
        method = getattr(request, 'method', 'GET')
        path = getattr(request, 'path', getattr(request, 'url', '/'))
        
        if method == 'GET':
            if '/stats' in path:
                # 获取 Nbot 状态
                status = get_nbot_status()
                
                # 如果 Nbot 没有运行，自动启动
                if status['status'] == 'Not started':
                    start_result = start_nbot_background()
                    status['auto_start'] = start_result
                
                return {
                    'statusCode': 200,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps(status, indent=2)
                }
                
            elif '/start' in path:
                # 手动启动 Nbot
                result = start_nbot_background()
                return {
                    'statusCode': 200,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({'result': result})
                }
                
            elif '/logs' in path:
                # 获取完整日志
                status = get_nbot_status()
                return {
                    'statusCode': 200,
                    'headers': {'Content-Type': 'text/plain'},
                    'body': '\n'.join(status['recent_output'])
                }
                
            elif '/health' in path:
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
                # 主页 - 显示状态仪表板
                status = get_nbot_status()
                
                # 如果 Nbot 没有运行，自动启动
                if status['status'] == 'Not started':
                    start_nbot_background()
                
                html = f'''
                <html>
                    <head>
                        <title>Nbot Dashboard</title>
                        <meta http-equiv="refresh" content="10">
                        <style>
                            body {{ font-family: Arial, sans-serif; margin: 20px; }}
                            .status {{ padding: 10px; border-radius: 5px; margin: 10px 0; }}
                            .running {{ background-color: #d4edda; }}
                            .stopped {{ background-color: #f8d7da; }}
                            .logs {{ 
                                background-color: #f8f9fa; 
                                border: 1px solid #dee2e6; 
                                padding: 15px; 
                                border-radius: 5px;
                                font-family: monospace;
                                white-space: pre-wrap;
                                max-height: 400px;
                                overflow-y: auto;
                            }}
                            .nav {{ margin: 20px 0; }}
                            .nav a {{ 
                                display: inline-block; 
                                padding: 10px 15px; 
                                margin-right: 10px; 
                                background-color: #007bff; 
                                color: white; 
                                text-decoration: none; 
                                border-radius: 5px; 
                            }}
                        </style>
                    </head>
                    <body>
                        <h1>🤖 Nbot Dashboard</h1>
                        
                        <div class="nav">
                            <a href="/">Dashboard</a>
                            <a href="/stats">JSON Stats</a>
                            <a href="/logs">Raw Logs</a>
                            <a href="/start">Start Nbot</a>
                            <a href="/health">Health Check</a>
                        </div>
                        
                        <div class="status {'running' if 'Running' in status['status'] else 'stopped'}">
                            <strong>Status:</strong> {status['status']}<br>
                            <strong>Uptime:</strong> {status['uptime']}<br>
                            <strong>Process ID:</strong> {status.get('process_id', 'N/A')}<br>
                            <strong>Start Time:</strong> {status.get('start_time', 'N/A')}<br>
                            <strong>Output Lines:</strong> {status['output_lines']}
                        </div>
                        
                        <h3>📋 Recent Console Output:</h3>
                        <div class="logs">{'<br>'.join(status['recent_output'][-20:]) if status['recent_output'] else 'No output yet...'}</div>
                        
                        <p><small>页面每10秒自动刷新 | Python版本: {sys.version}</small></p>
                    </body>
                </html>
                '''
                
                return {
                    'statusCode': 200,
                    'headers': {'Content-Type': 'text/html'},
                    'body': html
                }
        
        elif method == 'POST':
            # 处理 POST 请求，可以用来发送命令给 Nbot
            try:
                body = getattr(request, 'body', b'')
                if isinstance(body, bytes):
                    body = body.decode('utf-8')
                
                data = json.loads(body) if body else {}
                action = data.get('action', 'status')
                
                if action == 'start':
                    result = start_nbot_background()
                elif action == 'status':
                    result = get_nbot_status()
                else:
                    result = f"Unknown action: {action}"
                
                return {
                    'statusCode': 200,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({'result': result})
                }
                
            except Exception as e:
                return {
                    'statusCode': 500,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({'error': str(e)})
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

# 本地测试
if __name__ == '__main__':
    class MockRequest:
        def __init__(self, path='/'):
            self.method = 'GET'
            self.path = path
            self.body = b''
    
    # 测试主页
    response = handler(MockRequest('/'))
    print("Response status:", response['statusCode'])

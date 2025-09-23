#!/usr/bin/env python3
"""
Vercel 服务器 - 简化版本，避免复杂的类继承
"""

import os
import sys
import json
import subprocess
import time
from datetime import datetime

# 全局变量存储进程信息
nbot_info = {
    'process': None,
    'start_time': None,
    'output_log': [],
    'max_log_lines': 100
}

def run_nbot_once(action="status", message=""):
    """运行一次 Nbot 并获取输出"""
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
            return "Error: Nbot-for-have-a-hold.py not found"
        
        # 设置环境变量
        env = os.environ.copy()
        env['VERCEL_DEPLOYMENT'] = 'true'
        env['NBOT_ACTION'] = str(action)
        env['NBOT_MESSAGE'] = str(message)
        
        # 运行 Nbot
        result = subprocess.run(
            [sys.executable, nbot_path],
            capture_output=True,
            text=True,
            timeout=25,
            env=env,
            cwd=os.path.dirname(nbot_path)
        )
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if result.returncode == 0:
            output = result.stdout.strip()
            log_entry = f"[{timestamp}] SUCCESS: {output}"
        else:
            error = result.stderr.strip() if result.stderr else "Unknown error"
            log_entry = f"[{timestamp}] ERROR (code {result.returncode}): {error}"
        
        # 添加到日志
        add_to_log(log_entry)
        
        return log_entry
        
    except subprocess.TimeoutExpired:
        log_entry = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] TIMEOUT: Nbot execution timeout"
        add_to_log(log_entry)
        return log_entry
    except Exception as e:
        log_entry = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] EXCEPTION: {str(e)}"
        add_to_log(log_entry)
        return log_entry

def add_to_log(message):
    """添加消息到日志"""
    global nbot_info
    nbot_info['output_log'].append(message)
    # 保持日志大小限制
    if len(nbot_info['output_log']) > nbot_info['max_log_lines']:
        nbot_info['output_log'] = nbot_info['output_log'][-nbot_info['max_log_lines']:]

def get_status():
    """获取状态信息"""
    return {
        'server_status': 'running',
        'python_version': sys.version,
        'current_time': datetime.now().isoformat(),
        'log_lines': len(nbot_info['output_log']),
        'recent_logs': nbot_info['output_log'][-20:] if nbot_info['output_log'] else []
    }

def handler(request):
    """Vercel 函数入口点"""
    try:
        # 获取请求信息
        method = getattr(request, 'method', 'GET')
        
        # 尝试多种方式获取路径
        path = '/'
        if hasattr(request, 'path'):
            path = request.path
        elif hasattr(request, 'url'):
            path = request.url
        elif hasattr(request, 'query') and 'path' in request.query:
            path = request.query['path']
        
        if method == 'GET':
            
            if '/stats' in path:
                # 运行一次 Nbot 获取最新状态
                run_result = run_nbot_once("status", "health_check")
                status = get_status()
                status['latest_run'] = run_result
                
                return {
                    'statusCode': 200,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps(status, indent=2)
                }
                
            elif '/run' in path:
                # 手动运行 Nbot
                result = run_nbot_once("manual", "test_run")
                return {
                    'statusCode': 200,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({'result': result})
                }
                
            elif '/logs' in path:
                # 获取纯文本日志
                logs = '\n'.join(nbot_info['output_log'])
                return {
                    'statusCode': 200,
                    'headers': {'Content-Type': 'text/plain; charset=utf-8'},
                    'body': logs if logs else 'No logs yet.'
                }
                
            elif '/health' in path:
                return {
                    'statusCode': 200,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({
                        'status': 'healthy',
                        'message': 'Nbot server is working',
                        'python_version': sys.version,
                        'timestamp': datetime.now().isoformat()
                    })
                }
                
            else:
                # 主页 - 显示仪表板
                status = get_status()
                
                # 自动运行一次获取最新状态
                latest_run = run_nbot_once("dashboard", "auto_check")
                
                html_content = f'''
<!DOCTYPE html>
<html>
<head>
    <title>🤖 Nbot Control Panel</title>
    <meta charset="utf-8">
    <meta http-equiv="refresh" content="30">
    <style>
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; 
            max-width: 1200px; 
            margin: 0 auto; 
            padding: 20px; 
            background-color: #f5f5f5; 
        }}
        .header {{ 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white; 
            padding: 20px; 
            border-radius: 10px; 
            margin-bottom: 20px; 
        }}
        .card {{ 
            background: white; 
            padding: 20px; 
            border-radius: 10px; 
            margin-bottom: 20px; 
            box-shadow: 0 2px 10px rgba(0,0,0,0.1); 
        }}
        .status-good {{ color: #28a745; font-weight: bold; }}
        .nav-buttons {{ margin: 20px 0; }}
        .btn {{ 
            display: inline-block; 
            padding: 10px 20px; 
            margin: 5px; 
            background-color: #007bff; 
            color: white; 
            text-decoration: none; 
            border-radius: 5px; 
            transition: background-color 0.3s;
        }}
        .btn:hover {{ background-color: #0056b3; }}
        .logs {{ 
            background-color: #1e1e1e; 
            color: #f8f8f2; 
            padding: 15px; 
            border-radius: 5px; 
            font-family: 'Courier New', monospace; 
            font-size: 12px;
            max-height: 400px; 
            overflow-y: auto; 
            white-space: pre-wrap;
            line-height: 1.4;
        }}
        .info-grid {{ 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); 
            gap: 15px; 
        }}
        .info-item {{ 
            background: #f8f9fa; 
            padding: 15px; 
            border-radius: 5px; 
            border-left: 4px solid #007bff; 
        }}
        .refresh-note {{ 
            text-align: center; 
            color: #6c757d; 
            font-size: 14px; 
            margin-top: 20px; 
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🤖 Nbot Control Panel</h1>
        <p>Real-time monitoring and control interface</p>
    </div>
    
    <div class="nav-buttons">
        <a href="/" class="btn">🏠 Dashboard</a>
        <a href="/stats" class="btn">📊 JSON Stats</a>
        <a href="/logs" class="btn">📋 Raw Logs</a>
        <a href="/run" class="btn">▶️ Run Nbot</a>
        <a href="/health" class="btn">❤️ Health Check</a>
    </div>
    
    <div class="card">
        <h3>📈 System Status</h3>
        <div class="info-grid">
            <div class="info-item">
                <strong>Server Status:</strong><br>
                <span class="status-good">{status['server_status'].upper()}</span>
            </div>
            <div class="info-item">
                <strong>Python Version:</strong><br>
                {sys.version.split()[0]}
            </div>
            <div class="info-item">
                <strong>Current Time:</strong><br>
                {datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")}
            </div>
            <div class="info-item">
                <strong>Log Entries:</strong><br>
                {status['log_lines']} lines
            </div>
        </div>
    </div>
    
    <div class="card">
        <h3>🔥 Latest Execution</h3>
        <div class="logs">{latest_run}</div>
    </div>
    
    <div class="card">
        <h3>📝 Recent Activity Log</h3>
        <div class="logs">{'<br>'.join(status['recent_logs']) if status['recent_logs'] else 'No recent activity...'}</div>
    </div>
    
    <div class="refresh-note">
        🔄 页面每30秒自动刷新 | 📡 实时监控 Nbot 状态
    </div>
</body>
</html>
                '''
                
                return {
                    'statusCode': 200,
                    'headers': {'Content-Type': 'text/html; charset=utf-8'},
                    'body': html_content
                }
        
        elif method == 'POST':
            try:
                # 处理 POST 请求
                body = getattr(request, 'body', b'')
                if isinstance(body, bytes):
                    body = body.decode('utf-8')
                
                data = json.loads(body) if body else {}
                action = data.get('action', 'test')
                message = data.get('message', 'Hello from API')
                
                # 运行 Nbot
                result = run_nbot_once(action, message)
                
                return {
                    'statusCode': 200,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({
                        'success': True,
                        'action': action,
                        'message': message,
                        'result': result,
                        'timestamp': datetime.now().isoformat()
                    })
                }
                
            except Exception as e:
                return {
                    'statusCode': 500,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({'error': f'POST error: {str(e)}'})
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
                'python_version': sys.version,
                'timestamp': datetime.now().isoformat()
            })
        }

# 本地测试
if __name__ == '__main__':
    print("Testing Nbot server...")
    test_result = run_nbot_once("test", "local_test")
    print(f"Test result: {test_result}")

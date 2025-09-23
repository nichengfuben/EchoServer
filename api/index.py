import json
import os
import sys
import subprocess
from datetime import datetime

def handler(event, context=None):
    """标准的 Vercel Python 函数入口点"""
    
    # 获取请求信息
    http_method = event.get('httpMethod', event.get('method', 'GET'))
    path = event.get('path', event.get('rawPath', '/'))
    query = event.get('queryStringParameters') or {}
    
    try:
        if http_method == 'GET':
            
            if 'stats' in path:
                # 运行 Nbot 并返回状态
                result = run_nbot_simple()
                return create_response(200, {
                    'status': 'ok',
                    'python_version': sys.version,
                    'nbot_result': result,
                    'timestamp': datetime.now().isoformat()
                })
            
            elif 'health' in path:
                return create_response(200, {
                    'status': 'healthy',
                    'message': 'Nbot server is working',
                    'python_version': sys.version
                })
            
            elif 'run' in path:
                result = run_nbot_simple()
                return create_response(200, {
                    'action': 'manual_run',
                    'result': result
                })
            
            else:
                # 主页 HTML
                html = create_dashboard_html()
                return create_html_response(html)
        
        elif http_method == 'POST':
            # 处理 POST 请求
            body = event.get('body', '{}')
            if isinstance(body, str):
                try:
                    data = json.loads(body)
                except:
                    data = {}
            else:
                data = body or {}
            
            action = data.get('action', 'test')
            message = data.get('message', 'Hello')
            
            result = run_nbot_simple(action, message)
            
            return create_response(200, {
                'success': True,
                'action': action,
                'message': message,
                'result': result
            })
        
        else:
            return create_response(405, {'error': 'Method not allowed'})
            
    except Exception as e:
        return create_response(500, {
            'error': str(e),
            'python_version': sys.version
        })

def run_nbot_simple(action='status', message='test'):
    """简单运行 Nbot"""
    try:
        # 查找 Nbot 文件
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 可能的路径
        paths_to_try = [
            os.path.join(current_dir, '..', 'core', 'Nbot-for-have-a-hold.py'),
            os.path.join(current_dir, 'Nbot-for-have-a-hold.py'),
            os.path.join(current_dir, '..', 'Nbot-for-have-a-hold.py')
        ]
        
        nbot_path = None
        for path in paths_to_try:
            if os.path.exists(path):
                nbot_path = path
                break
        
        if not nbot_path:
            return f"Nbot file not found. Searched: {paths_to_try}"
        
        # 设置环境变量
        env = os.environ.copy()
        env['NBOT_ACTION'] = str(action)
        env['NBOT_MESSAGE'] = str(message)
        env['VERCEL_ENV'] = 'true'
        
        # 运行 Nbot
        process = subprocess.run(
            [sys.executable, nbot_path],
            capture_output=True,
            text=True,
            timeout=20,
            env=env
        )
        
        if process.returncode == 0:
            output = process.stdout.strip()
            return output if output else f"Nbot ran successfully. Action: {action}"
        else:
            error = process.stderr.strip() if process.stderr else "Unknown error"
            return f"Nbot failed: {error}"
            
    except subprocess.TimeoutExpired:
        return "Nbot execution timeout"
    except Exception as e:
        return f"Error: {str(e)}"

def create_response(status_code, data):
    """创建标准 JSON 响应"""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps(data, ensure_ascii=False)
    }

def create_html_response(html):
    """创建 HTML 响应"""
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'text/html; charset=utf-8'
        },
        'body': html
    }

def create_dashboard_html():
    """创建仪表板 HTML"""
    # 运行 Nbot 获取当前状态
    nbot_result = run_nbot_simple('dashboard', 'status_check')
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🤖 Nbot 控制台</title>
    <meta http-equiv="refresh" content="30">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{ 
            max-width: 1000px; 
            margin: 0 auto; 
            background: white; 
            border-radius: 15px; 
            box-shadow: 0 20px 60px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        .header {{ 
            background: linear-gradient(45deg, #2196F3, #21CBF3); 
            color: white; 
            padding: 30px; 
            text-align: center; 
        }}
        .header h1 {{ font-size: 2.5em; margin-bottom: 10px; }}
        .content {{ padding: 30px; }}
        .status-card {{ 
            background: #f8f9fa; 
            border-radius: 10px; 
            padding: 20px; 
            margin-bottom: 20px;
            border-left: 5px solid #28a745;
        }}
        .nav-grid {{ 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); 
            gap: 15px; 
            margin-bottom: 30px; 
        }}
        .nav-btn {{ 
            display: block; 
            padding: 15px; 
            background: #007bff; 
            color: white; 
            text-decoration: none; 
            border-radius: 8px; 
            text-align: center; 
            font-weight: bold;
            transition: all 0.3s ease;
        }}
        .nav-btn:hover {{ 
            background: #0056b3; 
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0,123,255,0.3);
        }}
        .output-box {{ 
            background: #1e1e1e; 
            color: #00ff00; 
            padding: 20px; 
            border-radius: 8px; 
            font-family: 'Courier New', monospace; 
            font-size: 14px;
            white-space: pre-wrap;
            max-height: 300px;
            overflow-y: auto;
            border: 2px solid #333;
        }}
        .info-grid {{ 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); 
            gap: 20px; 
            margin: 20px 0; 
        }}
        .info-item {{ 
            background: white; 
            padding: 20px; 
            border-radius: 8px; 
            border: 1px solid #eee;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        }}
        .info-item h3 {{ color: #333; margin-bottom: 10px; }}
        .status-badge {{ 
            display: inline-block; 
            padding: 5px 12px; 
            background: #28a745; 
            color: white; 
            border-radius: 20px; 
            font-size: 12px; 
            font-weight: bold;
        }}
        .footer {{ 
            text-align: center; 
            color: #666; 
            padding: 20px; 
            background: #f8f9fa;
            border-top: 1px solid #eee;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 Nbot 控制台</h1>
            <p>实时监控和控制面板</p>
        </div>
        
        <div class="content">
            <div class="status-card">
                <h2>📊 系统状态 <span class="status-badge">运行中</span></h2>
                <p><strong>当前时间:</strong> {current_time}</p>
                <p><strong>Python版本:</strong> {sys.version.split()[0]}</p>
                <p><strong>环境:</strong> Vercel Serverless</p>
            </div>
            
            <div class="nav-grid">
                <a href="/stats" class="nav-btn">📈 JSON 状态</a>
                <a href="/run" class="nav-btn">▶️ 运行 Nbot</a>
                <a href="/health" class="nav-btn">❤️ 健康检查</a>
                <a href="/" class="nav-btn">🔄 刷新页面</a>
            </div>
            
            <div class="info-grid">
                <div class="info-item">
                    <h3>🔥 最新执行结果</h3>
                    <div class="output-box">{nbot_result}</div>
                </div>
                
                <div class="info-item">
                    <h3>📋 快速操作</h3>
                    <p>• 点击上方按钮进行各种操作</p>
                    <p>• 页面每30秒自动刷新</p>
                    <p>• 支持 GET/POST API 调用</p>
                    <p>• 实时显示 Nbot 执行状态</p>
                </div>
            </div>
        </div>
        
        <div class="footer">
            <p>🔄 页面每30秒自动刷新 | 🚀 Powered by Vercel</p>
        </div>
    </div>
</body>
</html>'''

# 为了本地测试
if __name__ == '__main__':
    # 模拟 Vercel 事件
    test_event = {{
        'httpMethod': 'GET',
        'path': '/',
        'queryStringParameters': None
    }}
    
    result = handler(test_event)
    print(f"Status: {{result['statusCode']}}")
    print(f"Content-Type: {{result['headers']['Content-Type']}}")

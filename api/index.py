from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import sys
import os
import subprocess
from datetime import datetime

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # 解析路径
        url_parts = urlparse(self.path)
        path = url_parts.path
        query = parse_qs(url_parts.query)
        
        try:
            if '/stats' in path:
                # 返回状态信息
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                
                status = {
                    'status': 'running',
                    'python_version': sys.version,
                    'timestamp': datetime.now().isoformat(),
                    'path': path
                }
                
                self.wfile.write(json.dumps(status, indent=2).encode())
                
            elif '/health' in path:
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                
                health = {
                    'status': 'healthy',
                    'message': 'Nbot server is working'
                }
                
                self.wfile.write(json.dumps(health).encode())
                
            elif '/run' in path:
                # 运行 Nbot
                result = self.run_nbot()
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                
                response = {
                    'action': 'run_nbot',
                    'result': result,
                    'timestamp': datetime.now().isoformat()
                }
                
                self.wfile.write(json.dumps(response).encode())
                
            else:
                # 主页
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                
                html = self.create_dashboard()
                self.wfile.write(html.encode())
                
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            error = {
                'error': str(e),
                'path': path
            }
            
            self.wfile.write(json.dumps(error).encode())
    
    def do_POST(self):
        try:
            # 获取请求体
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            try:
                data = json.loads(post_data.decode('utf-8'))
            except:
                data = {}
            
            action = data.get('action', 'test')
            message = data.get('message', 'Hello')
            
            # 运行 Nbot
            result = self.run_nbot(action, message)
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            response = {
                'success': True,
                'action': action,
                'message': message,
                'result': result
            }
            
            self.wfile.write(json.dumps(response).encode())
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            error = {'error': str(e)}
            self.wfile.write(json.dumps(error).encode())
    
    def run_nbot(self, action='status', message='test'):
        """运行 Nbot"""
        try:
            # 查找 Nbot 文件
            current_dir = os.path.dirname(os.path.abspath(__file__))
            possible_paths = [
                os.path.join(current_dir, '..', 'core', 'Nbot-for-have-a-hold.py'),
                os.path.join(current_dir, 'Nbot-for-have-a-hold.py'),
                os.path.join(current_dir, '..', 'Nbot-for-have-a-hold.py')
            ]
            
            nbot_path = None
            for path in possible_paths:
                if os.path.exists(path):
                    nbot_path = path
                    break
            
            if not nbot_path:
                return f"Nbot file not found. Searched: {possible_paths}"
            
            # 设置环境变量
            env = os.environ.copy()
            env['NBOT_ACTION'] = str(action)
            env['NBOT_MESSAGE'] = str(message)
            
            # 运行 Nbot
            process = subprocess.run(
                [sys.executable, nbot_path],
                capture_output=True,
                text=True,
                timeout=20,
                env=env
            )
            
            if process.returncode == 0:
                return process.stdout.strip() or f"Nbot executed successfully. Action: {action}"
            else:
                return f"Error: {process.stderr.strip()}"
                
        except subprocess.TimeoutExpired:
            return "Nbot execution timeout"
        except Exception as e:
            return f"Exception: {str(e)}"
    
    def create_dashboard(self):
        """创建仪表板HTML"""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🤖 Nbot 控制台</title>
    <meta http-equiv="refresh" content="30">
    <style>
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
            margin: 0; padding: 20px; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }}
        .container {{ 
            max-width: 800px; margin: 0 auto; 
            background: white; border-radius: 15px; 
            box-shadow: 0 20px 60px rgba(0,0,0,0.1); 
            overflow: hidden;
        }}
        .header {{ 
            background: linear-gradient(45deg, #2196F3, #21CBF3); 
            color: white; padding: 30px; text-align: center; 
        }}
        .content {{ padding: 30px; }}
        .nav-btn {{ 
            display: inline-block; margin: 10px; padding: 12px 24px; 
            background: #007bff; color: white; text-decoration: none; 
            border-radius: 6px; font-weight: bold;
        }}
        .nav-btn:hover {{ background: #0056b3; }}
        .status {{ 
            background: #f8f9fa; padding: 20px; border-radius: 8px; 
            margin: 20px 0; border-left: 4px solid #28a745;
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
            <div class="status">
                <h3>📊 系统状态</h3>
                <p><strong>状态:</strong> 运行中 ✅</p>
                <p><strong>时间:</strong> {current_time}</p>
                <p><strong>Python:</strong> {sys.version.split()[0]}</p>
                <p><strong>平台:</strong> Vercel Serverless</p>
            </div>
            
            <div style="text-align: center;">
                <a href="/api/index" class="nav-btn">🏠 首页</a>
                <a href="/api/index/stats" class="nav-btn">📊 状态</a>
                <a href="/api/index/run" class="nav-btn">▶️ 运行</a>
                <a href="/api/index/health" class="nav-btn">❤️ 健康</a>
            </div>
            
            <div style="text-align: center; margin-top: 30px; color: #666;">
                <p>🔄 页面每30秒自动刷新</p>
            </div>
        </div>
    </div>
</body>
</html>'''

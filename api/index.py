from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import sys
import os
import subprocess
import re
from datetime import datetime

class handler(BaseHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        self.execution_log = []
        self.installed_packages = set()
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        url_parts = urlparse(self.path)
        path = url_parts.path
        
        try:
            if '/stats' in path:
                self.send_json_response(self.get_system_stats())
            elif '/health' in path:
                self.send_json_response({'status': 'healthy', 'message': 'Server running'})
            elif '/run' in path:
                result = self.smart_run_nbot()
                self.send_json_response({
                    'action': 'smart_run_nbot',
                    'result': result,
                    'execution_log': self.execution_log[-10:],
                    'installed_packages': list(self.installed_packages)
                })
            elif '/logs' in path:
                self.send_text_response('\n'.join(self.execution_log))
            else:
                self.send_html_response(self.create_smart_dashboard())
        except Exception as e:
            self.send_json_response({'error': str(e)}, status=500)
    
    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8')) if post_data else {}
            
            action = data.get('action', 'test')
            message = data.get('message', 'Hello')
            
            result = self.smart_run_nbot(action, message)
            
            self.send_json_response({
                'success': True,
                'action': action,
                'result': result,
                'execution_log': self.execution_log[-5:],
                'installed_packages': list(self.installed_packages)
            })
        except Exception as e:
            self.send_json_response({'error': str(e)}, status=500)
    
    def log_execution(self, message):
        """记录执行日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.execution_log.append(log_entry)
        print(log_entry)
        
        # 保持日志大小限制
        if len(self.execution_log) > 100:
            self.execution_log = self.execution_log[-100:]
    
    def extract_missing_modules(self, error_text):
        """从错误信息中提取缺失的模块"""
        missing_modules = set()
        
        # 常见的 ImportError 模式
        patterns = [
            r"ModuleNotFoundError: No module named '([^']+)'",
            r"ImportError: No module named '([^']+)'",
            r"ImportError: cannot import name '([^']+)'",
            r"from ([a-zA-Z_][a-zA-Z0-9_]*) import",
            r"import ([a-zA-Z_][a-zA-Z0-9_]*)",
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, error_text)
            for match in matches:
                # 清理模块名
                module = match.split('.')[0]  # 取主模块名
                if module and not module.startswith('_') and len(module) > 1:
                    missing_modules.add(module)
        
        # 特殊处理常见错误
        if 'requests' in error_text.lower():
            missing_modules.add('requests')
        if 'dotenv' in error_text.lower():
            missing_modules.add('python-dotenv')
        if 'httpx' in error_text.lower():
            missing_modules.add('httpx')
        if 'websocket' in error_text.lower():
            missing_modules.add('websocket-client')
        if 'yaml' in error_text.lower():
            missing_modules.add('pyyaml')
        if 'bs4' in error_text.lower() or 'beautifulsoup' in error_text.lower():
            missing_modules.add('beautifulsoup4')
        if 'PIL' in error_text or 'pillow' in error_text.lower():
            missing_modules.add('pillow')
        if 'cv2' in error_text:
            missing_modules.add('opencv-python')
        if 'numpy' in error_text.lower():
            missing_modules.add('numpy')
        if 'pandas' in error_text.lower():
            missing_modules.add('pandas')
        
        return list(missing_modules)
    
    def smart_install_package(self, package_name):
        """智能安装包"""
        try:
            self.log_execution(f"🔄 正在安装 {package_name}...")
            
            # 尝试安装
            result = subprocess.run(
                [sys.executable, '-m', 'pip', 'install', '--user', '--no-warn-script-location', package_name],
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode == 0:
                self.log_execution(f"✅ {package_name} 安装成功")
                self.installed_packages.add(package_name)
                return True
            else:
                # 尝试常见的包名变体
                alternatives = self.get_package_alternatives(package_name)
                for alt_name in alternatives:
                    self.log_execution(f"🔄 尝试替代包名: {alt_name}")
                    alt_result = subprocess.run(
                        [sys.executable, '-m', 'pip', 'install', '--user', '--no-warn-script-location', alt_name],
                        capture_output=True,
                        text=True,
                        timeout=120
                    )
                    if alt_result.returncode == 0:
                        self.log_execution(f"✅ {alt_name} 安装成功")
                        self.installed_packages.add(alt_name)
                        return True
                
                error_msg = result.stderr.strip() if result.stderr else "未知错误"
                self.log_execution(f"❌ {package_name} 安装失败: {error_msg}")
                return False
                
        except subprocess.TimeoutExpired:
            self.log_execution(f"⏰ {package_name} 安装超时")
            return False
        except Exception as e:
            self.log_execution(f"💥 {package_name} 安装异常: {str(e)}")
            return False
    
    def get_package_alternatives(self, module_name):
        """获取模块的可能包名"""
        alternatives = {
            'cv2': ['opencv-python', 'opencv-contrib-python'],
            'PIL': ['pillow', 'Pillow'],
            'bs4': ['beautifulsoup4', 'BeautifulSoup4'],
            'yaml': ['pyyaml', 'PyYAML'],
            'dotenv': ['python-dotenv'],
            'websocket': ['websocket-client', 'websockets'],
            'sklearn': ['scikit-learn'],
            'skimage': ['scikit-image'],
            'pymongo': ['pymongo'],
            'psycopg2': ['psycopg2-binary'],
        }
        
        return alternatives.get(module_name, [f"{module_name}2", f"py{module_name}", f"{module_name}-python"])
    
    def smart_run_nbot(self, action='status', message='test', max_retries=3):
        """智能运行 Nbot，自动处理依赖错误"""
        nbot_path = self.find_nbot_file()
        if not nbot_path:
            return "❌ Nbot-for-have-a-hold.py 文件未找到"
        
        retry_count = 0
        last_error = ""
        
        while retry_count < max_retries:
            try:
                self.log_execution(f"🚀 尝试运行 Nbot (第 {retry_count + 1} 次)")
                
                # 设置环境变量
                env = os.environ.copy()
                env['NBOT_ACTION'] = str(action)
                env['NBOT_MESSAGE'] = str(message)
                env['PYTHONPATH'] = os.path.dirname(nbot_path) + ':' + env.get('PYTHONPATH', '')
                
                # 执行 Nbot
                process = subprocess.run(
                    [sys.executable, nbot_path],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    env=env,
                    cwd=os.path.dirname(nbot_path)
                )
                
                if process.returncode == 0:
                    output = process.stdout.strip()
                    self.log_execution(f"✅ Nbot 执行成功")
                    return output or f"✅ Nbot 执行成功 (Action: {action})"
                else:
                    # 分析错误并尝试安装缺失依赖
                    error_output = process.stderr.strip()
                    last_error = error_output
                    
                    self.log_execution(f"❌ Nbot 执行失败: {error_output[:200]}...")
                    
                    # 提取缺失的模块
                    missing_modules = self.extract_missing_modules(error_output)
                    
                    if missing_modules:
                        self.log_execution(f"🔍 检测到缺失模块: {missing_modules}")
                        
                        # 尝试安装缺失的模块
                        installed_any = False
                        for module in missing_modules:
                            if self.smart_install_package(module):
                                installed_any = True
                        
                        if installed_any:
                            retry_count += 1
                            self.log_execution(f"🔄 已安装依赖，准备重试...")
                            continue
                        else:
                            self.log_execution("❌ 无法安装所需依赖，停止重试")
                            break
                    else:
                        self.log_execution("❓ 未检测到缺失模块，可能是其他错误")
                        break
                        
            except subprocess.TimeoutExpired:
                error_msg = f"⏰ Nbot 执行超时 (30秒)"
                self.log_execution(error_msg)
                return error_msg
            except Exception as e:
                error_msg = f"💥 执行异常: {str(e)}"
                self.log_execution(error_msg)
                return error_msg
            
            retry_count += 1
        
        # 所有重试都失败了
        final_error = f"❌ Nbot 执行失败，已重试 {max_retries} 次。最后错误: {last_error[:300]}"
        self.log_execution(final_error)
        return final_error
    
    def find_nbot_file(self):
        """查找 Nbot 文件"""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        possible_paths = [
            os.path.join(current_dir, '..', 'core', 'Nbot-for-have-a-hold.py'),
            os.path.join(current_dir, 'Nbot-for-have-a-hold.py'),
            os.path.join(current_dir, '..', 'Nbot-for-have-a-hold.py'),
            os.path.join(current_dir, '..', '..', 'Nbot-for-have-a-hold.py')
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        return None
    
    def get_system_stats(self):
        """获取系统统计信息"""
        return {
            'status': 'running',
            'python_version': sys.version,
            'timestamp': datetime.now().isoformat(),
            'nbot_file_found': self.find_nbot_file() is not None,
            'execution_log_lines': len(self.execution_log),
            'installed_packages': list(self.installed_packages),
            'installed_count': len(self.installed_packages)
        }
    
    def create_smart_dashboard(self):
        """创建智能仪表板"""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        nbot_found = self.find_nbot_file() is not None
        
        return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🤖 Nbot 智能自适应控制台</title>
    <meta http-equiv="refresh" content="45">
    <style>
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
            margin: 0; padding: 20px; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }}
        .container {{ 
            max-width: 1200px; margin: 0 auto; 
            background: white; border-radius: 15px; 
            box-shadow: 0 20px 60px rgba(0,0,0,0.1); 
            overflow: hidden;
        }}
        .header {{ 
            background: linear-gradient(45deg, #FF6B6B, #4ECDC4); 
            color: white; padding: 30px; text-align: center; 
        }}
        .content {{ padding: 30px; }}
        .nav-btn {{ 
            display: inline-block; margin: 8px; padding: 12px 20px; 
            background: #007bff; color: white; text-decoration: none; 
            border-radius: 8px; font-weight: bold; font-size: 14px;
            transition: all 0.3s ease; border: none; cursor: pointer;
        }}
        .nav-btn:hover {{ background: #0056b3; transform: translateY(-2px); }}
        .nav-btn.run {{ background: #28a745; }}
        .nav-btn.run:hover {{ background: #218838; }}
        .status-card {{ 
            background: linear-gradient(135deg, #f8f9fa, #e9ecef); 
            padding: 25px; border-radius: 12px; 
            margin: 20px 0; border-left: 5px solid #007bff;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        }}
        .grid {{ 
            display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); 
            gap: 20px; margin: 20px 0; 
        }}
        .card {{ 
            background: white; padding: 20px; border-radius: 12px; 
            border: 1px solid #dee2e6; box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            transition: transform 0.3s ease;
        }}
        .card:hover {{ transform: translateY(-5px); }}
        .log-box {{ 
            background: #1a1a1a; color: #00ff41; padding: 15px; 
            border-radius: 8px; font-family: 'Courier New', monospace; font-size: 12px;
            max-height: 300px; overflow-y: auto; white-space: pre-wrap;
            border: 2px solid #333;
        }}
        .badge {{ 
            display: inline-block; padding: 4px 12px; border-radius: 15px; 
            font-size: 11px; font-weight: bold; margin: 2px;
        }}
        .badge-success {{ background: #d4edda; color: #155724; }}
        .badge-info {{ background: #d1ecf1; color: #0c5460; }}
        .badge-warning {{ background: #fff3cd; color: #856404; }}
        .pulse {{ animation: pulse 2s infinite; }}
        @keyframes pulse {{ 0% {{ opacity: 1; }} 50% {{ opacity: 0.5; }} 100% {{ opacity: 1; }} }}
        .smart-indicator {{ 
            display: inline-block; width: 12px; height: 12px; 
            background: #28a745; border-radius: 50%; margin-right: 8px;
            animation: pulse 2s infinite;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🧠 Nbot 智能自适应控制台</h1>
            <p><span class="smart-indicator"></span>自动错误检测 | 智能依赖安装 | 自适应运行</p>
        </div>
        
        <div class="content">
            <!-- 系统状态 -->
            <div class="status-card">
                <h3>🎯 智能运行状态</h3>
                <p><strong>🕒 当前时间:</strong> {current_time}</p>
                <p><strong>🐍 Python版本:</strong> {sys.version.split()[0]}</p>
                <p><strong>📁 Nbot文件:</strong> {'✅ 已发现' if nbot_found else '❌ 未找到'}</p>
                <p><strong>🔧 已安装包:</strong> {len(self.installed_packages)} 个</p>
                <p><strong>📝 执行日志:</strong> {len(self.execution_log)} 条记录</p>
            </div>
            
            <!-- 快捷操作 -->
            <div style="text-align: center; margin: 25px 0;">
                <button onclick="runNbot()" class="nav-btn run">🚀 智能运行 Nbot</button>
                <a href="/api/index/stats" class="nav-btn">📊 详细统计</a>
                <a href="/api/index/logs" class="nav-btn">📋 执行日志</a>
                <a href="/api/index" class="nav-btn">🔄 刷新状态</a>
            </div>
            
            <!-- 详细信息网格 -->
            <div class="grid">
                <div class="card">
                    <h4>🧠 智能特性</h4>
                    <p>• <strong>自动错误检测:</strong> 智能解析运行时错误</p>
                    <p>• <strong>智能依赖安装:</strong> 自动识别并安装缺失包</p>
                    <p>• <strong>多重重试机制:</strong> 自动重试失败的操作</p>
                    <p>• <strong>包名智能映射:</strong> 处理常见的包名变体</p>
                    <p>• <strong>实时日志记录:</strong> 详细记录每个操作步骤</p>
                </div>
                
                <div class="card">
                    <h4>📦 已安装的包</h4>
                    {f'''<div>
                        {" ".join([f'<span class="badge badge-success">{pkg}</span>' for pkg in sorted(self.installed_packages)]) if self.installed_packages else '<p style="color: #6c757d;">暂无自动安装的包</p>'}
                    </div>''' if self.installed_packages else '<p style="color: #6c757d;">暂无自动安装的包</p>'}
                </div>
            </div>
            
            <!-- 最近执行日志 -->
            {f'''<div class="card">
                <h4>📋 最近执行日志</h4>
                <div class="log-box">{"<br>".join(self.execution_log[-15:]) if self.execution_log else "暂无执行记录...<br>点击上方按钮开始智能运行！"}</div>
            </div>''' if True else ''}
            
            <div style="text-align: center; margin-top: 30px; color: #666;">
                <p>🧠 智能自适应系统已激活 | 🔄 页面每45秒自动刷新</p>
            </div>
        </div>
    </div>
    
    <script>
        async function runNbot() {{
            const btn = event.target;
            btn.textContent = '🔄 正在智能运行...';
            btn.disabled = true;
            
            try {{
                const response = await fetch('/api/index/run');
                const data = await response.json();
                
                if (data.result) {{
                    alert('运行结果:\\n' + data.result);
                }} else {{
                    alert('运行完成，请查看页面日志了解详情');
                }}
            }} catch (error) {{
                alert('请求失败: ' + error.message);
            }} finally {{
                btn.textContent = '🚀 智能运行 Nbot';
                btn.disabled = false;
                setTimeout(() => location.reload(), 2000);
            }}
        }}
    </script>
</body>
</html>'''
    
    def send_json_response(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2, ensure_ascii=False).encode())
    
    def send_html_response(self, html):
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode())
    
    def send_text_response(self, text):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain; charset=utf-8')
        self.end_headers()
        self.wfile.write(text.encode())

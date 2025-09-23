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
            elif '/test-install' in path:
                # 测试安装 ollama
                result = self.smart_install_package('ollama')
                self.send_json_response({
                    'test_install': 'ollama',
                    'success': result,
                    'log': self.execution_log[-5:]
                })
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
        if len(self.execution_log) > 150:
            self.execution_log = self.execution_log[-150:]
    
    def extract_missing_modules(self, error_text):
        """从错误信息中提取缺失的模块 - 增强版"""
        missing_modules = set()
        
        self.log_execution(f"🔍 分析错误信息: {error_text[:100]}...")
        
        # 更精确的模式匹配
        patterns = [
            r"ModuleNotFoundError: No module named '([^']+)'",
            r"ImportError: No module named '?([^'\s]+)'?",
            r"ImportError: cannot import name '([^']+)'",
            r"from\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+import",
            r"import\s+([a-zA-Z_][a-zA-Z0-9_]*)",
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, error_text, re.IGNORECASE)
            for match in matches:
                module = match.split('.')[0].strip()
                if module and len(module) > 1 and not module.startswith('_'):
                    missing_modules.add(module)
                    self.log_execution(f"📦 检测到缺失模块: {module}")
        
        # 特殊模块映射 - 扩展版
        special_mappings = {
            'requests': 'requests',
            'dotenv': 'python-dotenv',
            'httpx': 'httpx',
            'websocket': 'websocket-client',
            'yaml': 'pyyaml',
            'bs4': 'beautifulsoup4',
            'PIL': 'pillow',
            'cv2': 'opencv-python',
            'numpy': 'numpy',
            'pandas': 'pandas',
            'ollama': 'ollama',  # 重点添加
            'openai': 'openai',
            'anthropic': 'anthropic',
            'transformers': 'transformers',
            'torch': 'torch',
            'tensorflow': 'tensorflow',
            'sklearn': 'scikit-learn',
            'skimage': 'sciite-image',
        }
        
        for key, value in special_mappings.items():
            if key.lower() in error_text.lower():
                missing_modules.add(value)
                self.log_execution(f"🎯 特殊映射检测: {key} -> {value}")
        
        result = list(missing_modules)
        self.log_execution(f"🔍 最终检测到缺失模块: {result}")
        return result
    
    def smart_install_package(self, package_name):
        """智能安装包 - 增强版"""
        try:
            self.log_execution(f"🚀 开始安装 {package_name}...")
            
            # 多种安装策略
            install_commands = [
                # 策略1: 标准安装
                [sys.executable, '-m', 'pip', 'install', '--user', '--no-warn-script-location', package_name],
                # 策略2: 强制重新安装
                [sys.executable, '-m', 'pip', 'install', '--user', '--no-warn-script-location', '--force-reinstall', package_name],
                # 策略3: 不使用缓存
                [sys.executable, '-m', 'pip', 'install', '--user', '--no-warn-script-location', '--no-cache-dir', package_name],
                # 策略4: 使用 --break-system-packages (如果需要)
                [sys.executable, '-m', 'pip', 'install', '--break-system-packages', package_name],
            ]
            
            for i, cmd in enumerate(install_commands):
                try:
                    self.log_execution(f"🔄 尝试安装策略 {i+1}: {' '.join(cmd[-3:])}")
                    
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=180  # 增加超时时间
                    )
                    
                    if result.returncode == 0:
                        self.log_execution(f"✅ {package_name} 安装成功 (策略 {i+1})")
                        self.installed_packages.add(package_name)
                        
                        # 验证安装
                        if self.verify_installation(package_name):
                            self.log_execution(f"✅ {package_name} 安装验证成功")
                            return True
                        else:
                            self.log_execution(f"⚠️ {package_name} 安装成功但验证失败")
                    else:
                        error_msg = result.stderr.strip() if result.stderr else "未知错误"
                        self.log_execution(f"❌ 策略 {i+1} 失败: {error_msg[:100]}")
                        
                except subprocess.TimeoutExpired:
                    self.log_execution(f"⏰ 策略 {i+1} 超时")
                    continue
                except Exception as e:
                    self.log_execution(f"💥 策略 {i+1} 异常: {str(e)}")
                    continue
            
            # 如果标准名称失败，尝试替代包名
            alternatives = self.get_package_alternatives(package_name)
            for alt_name in alternatives:
                self.log_execution(f"🔄 尝试替代包名: {alt_name}")
                try:
                    result = subprocess.run(
                        [sys.executable, '-m', 'pip', 'install', '--user', '--no-warn-script-location', alt_name],
                        capture_output=True,
                        text=True,
                        timeout=180
                    )
                    if result.returncode == 0:
                        self.log_execution(f"✅ {alt_name} 安装成功")
                        self.installed_packages.add(alt_name)
                        return True
                except Exception as e:
                    self.log_execution(f"❌ {alt_name} 安装失败: {str(e)}")
                    continue
            
            self.log_execution(f"❌ {package_name} 所有安装策略都失败了")
            return False
                
        except Exception as e:
            self.log_execution(f"💥 {package_name} 安装过程出现异常: {str(e)}")
            return False
    
    def verify_installation(self, package_name):
        """验证包是否正确安装"""
        try:
            # 尝试导入包来验证安装
            import importlib
            
            # 处理包名映射
            import_names = {
                'python-dotenv': 'dotenv',
                'beautifulsoup4': 'bs4',
                'pillow': 'PIL',
                'opencv-python': 'cv2',
                'scikit-learn': 'sklearn',
                'scikit-image': 'skimage',
                'websocket-client': 'websocket',
                'pyyaml': 'yaml',
            }
            
            import_name = import_names.get(package_name, package_name)
            
            # 尝试导入
            importlib.import_module(import_name)
            return True
            
        except ImportError:
            return False
        except Exception:
            return False
    
    def get_package_alternatives(self, module_name):
        """获取模块的可能包名 - 扩展版"""
        alternatives = {
            'ollama': ['ollama-python', 'python-ollama'],  # 重点添加 ollama 的替代名
            'cv2': ['opencv-python', 'opencv-contrib-python', 'cv2'],
            'PIL': ['pillow', 'Pillow'],
            'bs4': ['beautifulsoup4', 'BeautifulSoup4'],
            'yaml': ['pyyaml', 'PyYAML'],
            'dotenv': ['python-dotenv'],
            'websocket': ['websocket-client', 'websockets'],
            'sklearn': ['scikit-learn'],
            'skimage': ['scikit-image'],
            'pymongo': ['pymongo'],
            'psycopg2': ['psycopg2-binary'],
            'openai': ['openai'],
            'anthropic': ['anthropic'],
        }
        
        return alternatives.get(module_name, [f"{module_name}2", f"py{module_name}", f"{module_name}-python"])
    
    def smart_run_nbot(self, action='status', message='test', max_retries=5):
        """智能运行 Nbot - 增强重试逻辑"""
        nbot_path = self.find_nbot_file()
        if not nbot_path:
            self.log_execution("❌ Nbot-for-have-a-hold.py 文件未找到")
            return "❌ Nbot-for-have-a-hold.py 文件未找到"
        
        self.log_execution(f"📁 找到 Nbot 文件: {nbot_path}")
        
        retry_count = 0
        last_error = ""
        installed_in_this_run = []
        
        while retry_count < max_retries:
            try:
                self.log_execution(f"🚀 尝试运行 Nbot (第 {retry_count + 1}/{max_retries} 次)")
                
                # 设置环境变量
                env = os.environ.copy()
                env['NBOT_ACTION'] = str(action)
                env['NBOT_MESSAGE'] = str(message)
                env['PYTHONPATH'] = os.path.dirname(nbot_path) + ':' + env.get('PYTHONPATH', '')
                env['PYTHONUNBUFFERED'] = '1'
                
                # 执行 Nbot
                process = subprocess.run(
                    [sys.executable, nbot_path],
                    capture_output=True,
                    text=True,
                    timeout=45,  # 增加超时时间
                    env=env,
                    cwd=os.path.dirname(nbot_path)
                )
                
                if process.returncode == 0:
                    output = process.stdout.strip()
                    self.log_execution(f"✅ Nbot 执行成功！")
                    success_msg = output or f"✅ Nbot 执行成功 (Action: {action})"
                    if installed_in_this_run:
                        success_msg += f"\n🔧 本次运行安装的包: {', '.join(installed_in_this_run)}"
                    return success_msg
                else:
                    # 分析错误
                    error_output = process.stderr.strip()
                    if not error_output:
                        error_output = process.stdout.strip()
                    
                    last_error = error_output
                    self.log_execution(f"❌ Nbot 执行失败 (退出码: {process.returncode})")
                    self.log_execution(f"错误详情: {error_output[:300]}")
                    
                    # 提取缺失的模块
                    missing_modules = self.extract_missing_modules(error_output)
                    
                    if missing_modules:
                        self.log_execution(f"🔧 准备安装缺失模块: {missing_modules}")
                        
                        # 尝试安装缺失的模块
                        installed_any = False
                        for module in missing_modules:
                            if self.smart_install_package(module):
                                installed_any = True
                                installed_in_this_run.append(module)
                        
                        if installed_any:
                            retry_count += 1
                            self.log_execution(f"🔄 已安装依赖，准备重试 (第 {retry_count + 1} 次)...")
                            continue
                        else:
                            self.log_execution("❌ 无法安装所需依赖")
                            break
                    else:
                        self.log_execution("❓ 未检测到缺失模块，可能是其他类型的错误")
                        break
                        
            except subprocess.TimeoutExpired:
                error_msg = f"⏰ Nbot 执行超时 (45秒)"
                self.log_execution(error_msg)
                return error_msg
            except Exception as e:
                error_msg = f"💥 执行异常: {str(e)}"
                self.log_execution(error_msg)
                return error_msg
            
            retry_count += 1
        
        # 所有重试都失败了
        final_error = f"❌ Nbot 执行失败，已重试 {max_retries} 次。\n"
        if installed_in_this_run:
            final_error += f"🔧 本次运行安装的包: {', '.join(installed_in_this_run)}\n"
        final_error += f"最后错误: {last_error[:500]}"
        
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
            'installed_count': len(self.installed_packages),
            'recent_log': self.execution_log[-10:] if self.execution_log else []
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
    <title>🤖 Nbot 智能自适应控制台 v2.0</title>
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
        .nav-btn.test {{ background: #ffc107; color: #000; }}
        .nav-btn.test:hover {{ background: #e0a800; }}
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
        .error-highlight {{ background: #fff3cd; padding: 10px; border-radius: 5px; margin: 10px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🧠 Nbot 智能自适应控制台 v2.0</h1>
            <p><span class="smart-indicator"></span>增强错误检测 | Ollama 支持 | 多重安装策略</p>
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
                <button onclick="testInstall()" class="nav-btn test">🧪 测试安装 Ollama</button>
                <a href="/api/index/stats" class="nav-btn">📊 详细统计</a>
                <a href="/api/index/logs" class="nav-btn">📋 执行日志</a>
                <a href="/api/index" class="nav-btn">🔄 刷新状态</a>
            </div>
            
            <!-- Ollama 特别说明 -->
            <div class="error-highlight">
                <h4>🎯 Ollama 支持增强</h4>
                <p>• 自动检测 ollama 模块缺失</p>
                <p>• 多重安装策略确保成功</p>
                <p>• 包名变体自动尝试: ollama, ollama-python, python-ollama</p>
                <p>• 增加安装验证机制</p>
            </div>
            
            <!-- 详细信息网格 -->
            <div class="grid">
                <div class="card">
                    <h4>🧠 增强特性 v2.0</h4>
                    <p>• <strong>增强错误解析:</strong> 更精确的模块名提取</p>
                    <p>• <strong>多重安装策略:</strong> 4种不同的pip安装方法</p>
                    <p>• <strong>安装验证:</strong> 自动验证包是否正确安装</p>
                    <p>• <strong>Ollama 特化:</strong> 专门优化 ollama 包安装</p>
                    <p>• <strong>扩展重试:</strong> 最多重试5次确保成功</p>
                </div>
                
                <div class="card">
                    <h4>📦 已安装的包</h4>
                    {f'''<div>
                        {" ".join([f'<span class="badge badge-success">{pkg}</span>' for pkg in sorted(self.installed_packages)]) if self.installed_packages else '<p style="color: #6c757d;">暂无自动安装的包</p>'}
                    </div>''' if self.installed_packages else '<p style="color: #6c757d;">暂无自动安装的包</p>'}
                </div>
            </div>
            
            <!-- 最近执行日志 -->
            <div class="card">
                <h4>📋 最近执行日志</h4>
                <div class="log-box">{"<br>".join(self.execution_log[-20:]) if self.execution_log else "暂无执行记录...<br>点击上方按钮开始智能运行！"}</div>
            </div>
            
            <div style="text-align: center; margin-top: 30px; color: #666;">
                <p>🧠 智能自适应系统 v2.0 已激活 | 🔄 页面每45秒自动刷新</p>
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
        
        async function testInstall() {{
            const btn = event.target;
            btn.textContent = '🔄 正在安装...';
            btn.disabled = true;
            
            try {{
                const response = await fetch('/api/index/test-install');
                const data = await response.json();
                
                if (data.success) {{
                    alert('Ollama 安装成功！\\n请查看日志了解详情');
                }} else {{
                    alert('Ollama 安装失败\\n请查看日志了解详情');
                }}
            }} catch (error) {{
                alert('请求失败: ' + error.message);
            }} finally {{
                btn.textContent = '🧪 测试安装 Ollama';
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

from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import sys
import os
import subprocess
from datetime import datetime
import importlib.util

class handler(BaseHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        self.install_log = []
        # 启动时自动检查并安装依赖
        self.auto_install_on_start()
        super().__init__(*args, **kwargs)
    
    def auto_install_on_start(self):
        """启动时自动安装依赖"""
        try:
            self.log_install("🚀 启动时自动依赖检查...")
            
            # 检查是否有package.txt
            requirements_path = self.find_requirements_file()
            if requirements_path:
                self.log_install(f"📋 找到 package.txt: {requirements_path}")
                self.install_from_requirements(requirements_path)
            else:
                self.log_install("📋 未找到 package.txt，使用默认依赖列表")
                self.install_default_dependencies()
                
        except Exception as e:
            self.log_install(f"💥 启动时安装依赖失败: {str(e)}")
    
    def do_GET(self):
        url_parts = urlparse(self.path)
        path = url_parts.path
        query = parse_qs(url_parts.query)
        
        try:
            if '/stats' in path:
                self.send_json_response(self.get_system_stats())
                
            elif '/health' in path:
                health_status = self.check_health()
                self.send_json_response(health_status)
                
            elif '/run' in path:
                result = self.run_nbot_safe()
                self.send_json_response({
                    'action': 'run_nbot',
                    'result': result,
                    'timestamp': datetime.now().isoformat()
                })
                
            elif '/install' in path:
                # 手动安装依赖
                install_result = self.install_dependencies()
                self.send_json_response({
                    'action': 'install_dependencies',
                    'result': install_result,
                    'install_log': self.install_log
                })
                
            elif '/install-requirements' in path:
                # 专门安装 package.txt
                result = self.install_requirements_txt()
                self.send_json_response({
                    'action': 'install_requirements_txt',
                    'result': result,
                    'install_log': self.install_log
                })
                
            elif '/logs' in path:
                self.send_text_response('\n'.join(self.install_log) if self.install_log else 'No installation logs.')
                
            else:
                self.send_html_response(self.create_enhanced_dashboard())
                
        except Exception as e:
            self.send_json_response({'error': str(e), 'path': path}, status=500)
    
    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            try:
                data = json.loads(post_data.decode('utf-8'))
            except:
                data = {}
            
            action = data.get('action', 'test')
            message = data.get('message', 'Hello')
            
            if action == 'install_deps':
                result = self.install_dependencies()
            elif action == 'install_requirements':
                result = self.install_requirements_txt()
            else:
                result = self.run_nbot_safe(action, message)
            
            response = {
                'success': True,
                'action': action,
                'message': message,
                'result': result,
                'install_log': self.install_log
            }
            
            self.send_json_response(response)
            
        except Exception as e:
            self.send_json_response({'error': str(e)}, status=500)
    
    def send_json_response(self, data, status=200):
        """发送JSON响应"""
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2, ensure_ascii=False).encode())
    
    def send_html_response(self, html):
        """发送HTML响应"""
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode())
    
    def send_text_response(self, text):
        """发送纯文本响应"""
        self.send_response(200)
        self.send_header('Content-type', 'text/plain; charset=utf-8')
        self.end_headers()
        self.wfile.write(text.encode())
    
    def find_requirements_file(self):
        """查找 package.txt 文件"""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        possible_paths = [
            os.path.join(current_dir, 'package.txt'),
            os.path.join(current_dir, '..', 'package.txt'),
            os.path.join(current_dir, '..', '..', 'package.txt'),
            os.path.join(current_dir, '..', 'core', 'package.txt'),
            os.path.join(os.getcwd(), 'package.txt')
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                self.log_install(f"✅ 找到 package.txt: {path}")
                return path
        
        self.log_install(f"❌ 未找到 package.txt，搜索路径: {possible_paths}")
        return None
    
    def install_requirements_txt(self):
        """安装 package.txt 中的依赖"""
        requirements_path = self.find_requirements_file()
        
        if not requirements_path:
            return self.install_default_dependencies()
        
        return self.install_from_requirements(requirements_path)
    
    def install_from_requirements(self, requirements_path):
        """从 package.txt 文件安装依赖"""
        self.log_install(f"📦 开始从 package.txt 安装依赖: {requirements_path}")
        
        try:
            # 读取 package.txt 内容
            with open(requirements_path, 'r', encoding='utf-8') as f:
                requirements_content = f.read().strip()
            
            self.log_install(f"📋 Requirements 内容:\n{requirements_content}")
            
            # 使用 pip install -r package.txt
            self.log_install(f"🔧 执行: pip install -r {requirements_path}")
            
            result = subprocess.run(
                [sys.executable, '-m', 'pip', 'install', '-r', requirements_path, '--user'],
                capture_output=True,
                text=True,
                timeout=120  # 增加超时时间到2分钟
            )
            
            if result.returncode == 0:
                self.log_install("✅ package.txt 安装成功!")
                self.log_install(f"安装输出: {result.stdout[:500]}...")
                
                return {
                    'success': True,
                    'method': 'package.txt',
                    'file_path': requirements_path,
                    'output': result.stdout
                }
            else:
                error_msg = result.stderr.strip() if result.stderr else "未知错误"
                self.log_install(f"❌ package.txt 安装失败: {error_msg}")
                
                # 如果失败，尝试逐个安装
                return self.install_requirements_individually(requirements_path)
                
        except subprocess.TimeoutExpired:
            self.log_install("⏰ package.txt 安装超时，尝试逐个安装")
            return self.install_requirements_individually(requirements_path)
        except Exception as e:
            self.log_install(f"💥 读取 package.txt 失败: {str(e)}")
            return self.install_default_dependencies()
    
    def install_requirements_individually(self, requirements_path):
        """逐个安装 package.txt 中的依赖"""
        self.log_install("🔄 尝试逐个安装 package.txt 中的依赖...")
        
        try:
            with open(requirements_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            installed_packages = []
            failed_packages = []
            
            for line in lines:
                line = line.strip()
                # 跳过空行和注释
                if not line or line.startswith('#') or line.startswith('-'):
                    continue
                
                package = line.split()[0]  # 获取包名（去除版本号等）
                
                try:
                    self.log_install(f"📦 安装: {package}")
                    
                    result = subprocess.run(
                        [sys.executable, '-m', 'pip', 'install', '--user', package],
                        capture_output=True,
                        text=True,
                        timeout=60
                    )
                    
                    if result.returncode == 0:
                        self.log_install(f"✅ {package} 安装成功")
                        installed_packages.append(package)
                    else:
                        error_msg = result.stderr.strip() if result.stderr else "未知错误"
                        self.log_install(f"❌ {package} 安装失败: {error_msg}")
                        failed_packages.append(package)
                        
                except subprocess.TimeoutExpired:
                    self.log_install(f"⏰ {package} 安装超时")
                    failed_packages.append(package)
                except Exception as e:
                    self.log_install(f"💥 {package} 安装异常: {str(e)}")
                    failed_packages.append(package)
            
            self.log_install(f"📊 逐个安装完成! 成功: {len(installed_packages)}, 失败: {len(failed_packages)}")
            
            return {
                'success': len(failed_packages) == 0,
                'method': 'individual_install',
                'installed': installed_packages,
                'failed': failed_packages,
                'success_count': len(installed_packages),
                'total_count': len(installed_packages) + len(failed_packages)
            }
            
        except Exception as e:
            self.log_install(f"💥 逐个安装失败: {str(e)}")
            return self.install_default_dependencies()
    
    def check_dependencies(self):
        """检查依赖是否安装"""
        # 先检查package.txt中的依赖
        requirements_path = self.find_requirements_file()
        dependencies = []
        
        if requirements_path:
            try:
                with open(requirements_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and not line.startswith('-'):
                            # 提取包名（去除版本要求）
                            package = line.split('==')[0].split('>=')[0].split('<=')[0].split('>')[0].split('<')[0].split('!=')[0]
                            dependencies.append(package)
            except Exception as e:
                self.log_install(f"读取 package.txt 失败: {str(e)}")
        
        # 如果没有package.txt，使用默认依赖
        if not dependencies:
            dependencies = [
                'requests', 'urllib3', 'certifi', 'charset-normalizer', 'idna',
                'python-dotenv', 'httpx', 'anyio', 'sniffio', 'h11'
            ]
        
        missing_deps = []
        available_deps = []
        
        for dep in dependencies:
            try:
                importlib.import_module(dep.replace('-', '_'))
                available_deps.append(dep)
            except ImportError:
                missing_deps.append(dep)
        
        return {
            'missing': missing_deps,
            'available': available_deps,
            'total_checked': len(dependencies),
            'requirements_file_found': requirements_path is not None
        }
    
    def install_dependencies(self):
        """安装依赖的主入口"""
        # 优先尝试从package.txt安装
        return self.install_requirements_txt()
    
    def install_default_dependencies(self):
        """安装默认依赖（当没有package.txt时）"""
        self.log_install("📦 使用默认依赖列表安装...")
        
        # 常用依赖列表
        required_packages = [
            'requests>=2.28.0',
            'python-dotenv>=0.19.0',
            'httpx>=0.24.0',
            'urllib3>=1.26.0'
        ]
        
        installed_packages = []
        failed_packages = []
        
        for package in required_packages:
            try:
                self.log_install(f"正在安装 {package}...")
                
                # 使用 pip 安装
                result = subprocess.run(
                    [sys.executable, '-m', 'pip', 'install', '--user', package],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                
                if result.returncode == 0:
                    self.log_install(f"✅ {package} 安装成功")
                    installed_packages.append(package)
                else:
                    error_msg = result.stderr.strip() if result.stderr else "未知错误"
                    self.log_install(f"❌ {package} 安装失败: {error_msg}")
                    failed_packages.append(package)
                    
            except subprocess.TimeoutExpired:
                self.log_install(f"⏰ {package} 安装超时")
                failed_packages.append(package)
            except Exception as e:
                self.log_install(f"💥 {package} 安装异常: {str(e)}")
                failed_packages.append(package)
        
        self.log_install(f"安装完成! 成功: {len(installed_packages)}, 失败: {len(failed_packages)}")
        
        return {
            'success': len(failed_packages) == 0,
            'method': 'default_packages',
            'installed': installed_packages,
            'failed': failed_packages,
            'success_count': len(installed_packages),
            'total_count': len(required_packages)
        }
    
    def log_install(self, message):
        """记录安装日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.install_log.append(log_entry)
        print(log_entry)  # 也输出到控制台
    
    def run_nbot_safe(self, action='status', message='test'):
        """安全运行 Nbot，包含依赖检查"""
        try:
            # 1. 检查依赖
            deps_status = self.check_dependencies()
            if deps_status['missing']:
                self.log_install(f"发现缺失依赖: {deps_status['missing']}")
                
                # 尝试自动安装
                install_result = self.install_dependencies()
                if install_result.get('failed'):
                    return f"依赖安装失败: {install_result['failed']}. 请查看 /logs 了解详情"
            
            # 2. 查找 Nbot 文件
            nbot_path = self.find_nbot_file()
            if not nbot_path:
                return "Nbot-for-have-a-hold.py 文件未找到"
            
            # 3. 运行 Nbot
            return self.execute_nbot(nbot_path, action, message)
            
        except Exception as e:
            self.log_install(f"运行 Nbot 时发生错误: {str(e)}")
            return f"运行错误: {str(e)}"
    
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
                self.log_install(f"找到 Nbot 文件: {path}")
                return path
        
        self.log_install(f"未找到 Nbot 文件，搜索路径: {possible_paths}")
        return None
    
    def execute_nbot(self, nbot_path, action, message):
        """执行 Nbot"""
        try:
            env = os.environ.copy()
            env['NBOT_ACTION'] = str(action)
            env['NBOT_MESSAGE'] = str(message)
            env['PYTHONPATH'] = os.path.dirname(nbot_path) + ':' + env.get('PYTHONPATH', '')
            
            self.log_install(f"执行 Nbot: {action} - {message}")
            
            process = subprocess.run(
                [sys.executable, nbot_path],
                capture_output=True,
                text=True,
                timeout=25,
                env=env,
                cwd=os.path.dirname(nbot_path)
            )
            
            if process.returncode == 0:
                output = process.stdout.strip()
                self.log_install(f"Nbot 执行成功: {output[:100]}...")
                return output or f"Nbot 执行成功 (Action: {action})"
            else:
                error = process.stderr.strip() if process.stderr else "未知错误"
                self.log_install(f"Nbot 执行失败: {error}")
                return f"执行失败: {error}"
                
        except subprocess.TimeoutExpired:
            self.log_install("Nbot 执行超时")
            return "执行超时 (25秒)"
        except Exception as e:
            self.log_install(f"执行异常: {str(e)}")
            return f"执行异常: {str(e)}"
    
    def get_system_stats(self):
        """获取系统状态"""
        deps_status = self.check_dependencies()
        
        return {
            'status': 'running',
            'python_version': sys.version,
            'timestamp': datetime.now().isoformat(),
            'dependencies': deps_status,
            'install_log_lines': len(self.install_log),
            'nbot_file_found': self.find_nbot_file() is not None,
            'requirements_file_found': self.find_requirements_file() is not None
        }
    
    def check_health(self):
        """健康检查"""
        deps_status = self.check_dependencies()
        nbot_found = self.find_nbot_file() is not None
        requirements_found = self.find_requirements_file() is not None
        
        health_score = 0
        if not deps_status['missing']:
            health_score += 40
        if nbot_found:
            health_score += 40
        if requirements_found:
            health_score += 20
        
        return {
            'status': 'healthy' if health_score >= 80 else 'warning',
            'health_score': health_score,
            'dependencies_ok': len(deps_status['missing']) == 0,
            'nbot_file_found': nbot_found,
            'requirements_file_found': requirements_found,
            'missing_dependencies': deps_status['missing']
        }
    
    def create_enhanced_dashboard(self):
        """创建增强版仪表板"""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        deps_status = self.check_dependencies()
        health = self.check_health()
        requirements_path = self.find_requirements_file()
        
        return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🤖 Nbot 智能控制台</title>
    <meta http-equiv="refresh" content="60">
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
            background: linear-gradient(45deg, #2196F3, #21CBF3); 
            color: white; padding: 30px; text-align: center; 
        }}
        .content {{ padding: 30px; }}
        .nav-btn {{ 
            display: inline-block; margin: 8px; padding: 12px 20px; 
            background: #007bff; color: white; text-decoration: none; 
            border-radius: 6px; font-weight: bold; font-size: 14px;
            transition: all 0.3s ease;
        }}
        .nav-btn:hover {{ background: #0056b3; transform: translateY(-2px); }}
        .nav-btn.requirements {{ background: #28a745; }}
        .nav-btn.requirements:hover {{ background: #1e7e34; }}
        .status-card {{ 
            background: #f8f9fa; padding: 20px; border-radius: 8px; 
            margin: 15px 0; border-left: 4px solid #28a745;
        }}
        .warning {{ border-left-color: #ffc107; }}
        .error {{ border-left-color: #dc3545; }}
        .grid {{ 
            display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); 
            gap: 20px; margin: 20px 0; 
        }}
        .card {{ 
            background: white; padding: 20px; border-radius: 8px; 
            border: 1px solid #dee2e6; box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        }}
        .badge {{ 
            display: inline-block; padding: 4px 8px; border-radius: 12px; 
            font-size: 12px; font-weight: bold; margin: 2px;
        }}
        .badge-success {{ background: #d4edda; color: #155724; }}
        .badge-warning {{ background: #fff3cd; color: #856404; }}
        .badge-danger {{ background: #f8d7da; color: #721c24; }}
        .log-box {{ 
            background: #1e1e1e; color: #00ff00; padding: 15px; 
            border-radius: 6px; font-family: monospace; font-size: 12px;
            max-height: 200px; overflow-y: auto; white-space: pre-wrap;
        }}
        .health-score {{ 
            font-size: 24px; font-weight: bold; 
            color: {'#28a745' if health['health_score'] >= 80 else '#ffc107' if health['health_score'] >= 50 else '#dc3545'};
        }}
        .requirements-info {{
            background: #e7f3ff; border: 1px solid #b3d9ff; 
            padding: 15px; border-radius: 8px; margin: 15px 0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 Nbot 智能控制台</h1>
            <p>自动 package.txt 安装 | 智能依赖管理 | 实时监控</p>
        </div>
        
        <div class="content">
            <!-- Requirements.txt 状态 -->
            <div class="requirements-info">
                <h3>📋 Requirements.txt 状态</h3>
                <p><strong>文件位置:</strong> {requirements_path if requirements_path else '❌ 未找到'}</p>
                <p><strong>自动安装:</strong> {'✅ 已启用' if requirements_path else '⚠️ 使用默认依赖'}</p>
                <p><strong>启动时安装:</strong> ✅ 已启用（每次启动自动检查并安装）</p>
            </div>
            
            <!-- 系统状态 -->
            <div class="status-card {'warning' if health['health_score'] < 80 else ''}">
                <h3>📊 系统健康状态 <span class="health-score">{health['health_score']}%</span></h3>
                <p><strong>状态:</strong> {health['status'].upper()} {'✅' if health['status'] == 'healthy' else '⚠️'}</p>
                <p><strong>时间:</strong> {current_time}</p>
                <p><strong>Python:</strong> {sys.version.split()[0]}</p>
                <p><strong>依赖状态:</strong> {'✅ 完整' if not deps_status['missing'] else '⚠️ 缺失 ' + str(len(deps_status['missing'])) + ' 个'}</p>
                <p><strong>Nbot文件:</strong> {'✅ 已找到' if health['nbot_file_found'] else '❌ 未找到'}</p>
                <p><strong>Requirements:</strong> {'✅ 已找到' if health['requirements_file_found'] else '❌ 未找到'}</p>
            </div>
            
            <!-- 导航按钮 -->
            <div style="text-align: center; margin: 20px 0;">
                <a href="/api/index" class="nav-btn">🏠 首页</a>
                <a href="/api/index/stats" class="nav-btn">📊 详细状态</a>
                <a href="/api/index/run" class="nav-btn">▶️ 运行 Nbot</a>
                <a href="/api/index/install" class="nav-btn">📦 安装依赖</a>
                <a href="/api/index/install-requirements" class="nav-btn requirements">📋 安装 Requirements</a>
                <a href="/api/index/logs" class="nav-btn">📋 安装日志</a>
                <a href="/api/index/health" class="nav-btn">❤️ 健康检查</a>
            </div>
            
            <!-- 详细信息网格 -->
            <div class="grid">
                <div class="card">
                    <h4>📦 依赖状态</h4>
                    <p><strong>已安装:</strong> {len(deps_status['available'])}</p>
                    <p><strong>缺失:</strong> {len(deps_status['missing'])}</p>
                    <p><strong>来源:</strong> {'package.txt' if deps_status['requirements_file_found'] else '默认列表'}</p>
                    
                    {f'''<div style="margin-top: 10px;">
                        <strong>缺失的依赖:</strong><br>
                        {" ".join([f'<span class="badge badge-danger">{dep}</span>' for dep in deps_status['missing']])}
                    </div>''' if deps_status['missing'] else '<p style="color: #28a745;">✅ 所有依赖已就绪</p>'}
                </div>
                
                <div class="card">
                    <h4>🔧 自动化功能</h4>
                    <p>• ✅ 启动时自动检测 package.txt</p>
                    <p>• ✅ 自动运行 pip install -r package.txt</p>
                    <p>• ✅ 失败时逐个安装依赖</p>
                    <p>• ✅ 实时监控和错误诊断</p>
                    <p>• ✅ 支持手动重新安装</p>
                </div>
            </div>
            
            <!-- 安装日志 -->
            {f'''<div class="card">
                <h4>📋 最近安装日志</h4>
                <div class="log-box">{"<br>".join(self.install_log[-15:]) if self.install_log else "暂无安装日志..."}</div>
            </div>''' if self.install_log else ''}
            
            <div style="text-align: center; margin-top: 30px; color: #666;">
                <p>🔄 页面每60秒自动刷新 | 🚀 自动 package.txt 安装已启用</p>
            </div>
        </div>
    </div>
</body>
</html>'''

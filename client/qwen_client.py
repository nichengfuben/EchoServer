#qwen_client.py
import aiohttp
import asyncio
import uuid
import time
import json
import hashlib
import os
import mimetypes
import base64
import hmac
import threading
import random
import pickle
import numpy as np
from datetime import datetime, timezone, timedelta
from urllib.parse import quote, urlencode, parse_qs, urlparse
from typing import List, Dict, AsyncGenerator, Optional, Union, Tuple
from dataclasses import dataclass, field
from asyncio import Lock, Semaphore
from concurrent.futures import ThreadPoolExecutor, as_completed
import re
import math
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)
from ui.consoleui import *
from data.qwen_accounts import *


FILE_TYPE_MAPPING = {
    'image/jpeg': 'image', 'image/jpg': 'image', 'image/png': 'image', 'image/gif': 'image',
    'image/webp': 'image', 'image/bmp': 'image', 'image/svg+xml': 'image', 'image/tiff': 'image',
    'image/ico': 'image', 'video/mp4': 'video', 'video/avi': 'video', 'video/mov': 'video',
    'video/wmv': 'video', 'video/flv': 'video', 'video/webm': 'video', 'video/mkv': 'video',
    'video/3gp': 'video', 'video/m4v': 'video', 'video/quicktime': 'video', 'audio/mp3': 'audio',
    'audio/wav': 'audio', 'audio/flac': 'audio', 'audio/aac': 'audio', 'audio/ogg': 'audio',
    'audio/wma': 'audio', 'audio/m4a': 'audio', 'audio/opus': 'audio', 'audio/mpeg': 'audio',
    'audio/x-wav': 'audio', 'application/pdf': 'file', 'application/msword': 'file',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'file',
    'application/vnd.ms-excel': 'file', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'file',
    'application/vnd.ms-powerpoint': 'file', 'application/vnd.openxmlformats-officedocument.presentationml.presentation': 'file',
    'text/plain': 'file', 'text/csv': 'file', 'application/rtf': 'file', 'application/zip': 'file',
    'application/x-rar-compressed': 'file', 'application/x-7z-compressed': 'file', 'application/json': 'file',
    'application/xml': 'file', 'text/xml': 'file', 'text/html': 'file', 'text/css': 'file',
    'text/javascript': 'file', 'application/javascript': 'file', 'text/x-python': 'file',
    'text/x-java': 'file', 'text/x-c': 'file', 'text/x-c++': 'file', 'text/x-csharp': 'file',
    'text/x-php': 'file', 'text/x-ruby': 'file', 'text/x-go': 'file', 'text/x-rust': 'file',
    'text/x-swift': 'file', 'text/x-kotlin': 'file', 'text/x-scala': 'file', 'text/x-sql': 'file',
    'text/x-shell': 'file',
}

EXTENSION_TO_MIME = {
    '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.gif': 'image/gif',
    '.webp': 'image/webp', '.bmp': 'image/bmp', '.svg': 'image/svg+xml', '.tiff': 'image/tiff',
    '.tif': 'image/tiff', '.ico': 'image/ico', '.mp4': 'video/mp4', '.avi': 'video/avi',
    '.mov': 'video/quicktime', '.wmv': 'video/wmv', '.flv': 'video/flv', '.webm': 'video/webm',
    '.mkv': 'video/mkv', '.3gp': 'video/3gp', '.m4v': 'video/m4v', '.mp3': 'audio/mpeg',
    '.wav': 'audio/wav', '.flac': 'audio/flac', '.aac': 'audio/aac', '.ogg': 'audio/ogg',
    '.wma': 'audio/wma', '.m4a': 'audio/m4a', '.opus': 'audio/opus', '.pdf': 'application/pdf',
    '.doc': 'application/msword', '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    '.xls': 'application/vnd.ms-excel', '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    '.ppt': 'application/vnd.ms-powerpoint', '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    '.txt': 'text/plain', '.csv': 'text/csv', '.rtf': 'application/rtf', '.zip': 'application/zip',
    '.rar': 'application/x-rar-compressed', '.7z': 'application/x-7z-compressed', '.json': 'application/json',
    '.xml': 'application/xml', '.html': 'text/html', '.htm': 'text/html', '.css': 'text/css',
    '.js': 'application/javascript', '.py': 'text/x-python', '.java': 'text/x-java', '.c': 'text/x-c',
    '.cpp': 'text/x-c++', '.cxx': 'text/x-c++', '.cc': 'text/x-c++', '.cs': 'text/x-csharp',
    '.php': 'text/x-php', '.rb': 'text/x-ruby', '.go': 'text/x-go', '.rs': 'text/x-rust',
    '.swift': 'text/x-swift', '.kt': 'text/x-kotlin', '.scala': 'text/x-scala', '.sql': 'text/x-sql',
    '.sh': 'text/x-shell', '.bash': 'text/x-shell', '.zsh': 'text/x-shell',
}

@dataclass
class AccountStats:
    email: str
    success_count: int = 0
    total_attempts: int = 0
    total_message_length: int = 0
    total_first_packet_delay: float = 0.0
    total_generation_tokens: int = 0
    total_generation_time: float = 0.0
    last_updated: float = field(default_factory=time.time)
    
    @property
    def success_rate(self) -> float:
        return self.success_count / max(self.total_attempts, 1)
    
    @property
    def avg_message_length(self) -> float:
        return self.total_message_length / max(self.success_count, 1)
    
    @property
    def avg_first_packet_delay(self) -> float:
        return self.total_first_packet_delay / max(self.success_count, 1)
    
    @property
    def generation_speed(self) -> float:
        return self.total_generation_tokens / max(self.total_generation_time, 0.001)
    
    def update_success(self, message_length: int, first_packet_delay: float, generation_tokens: int, generation_time: float):
        self.success_count += 1
        self.total_attempts += 1
        self.total_message_length += message_length
        self.total_first_packet_delay += first_packet_delay
        self.total_generation_tokens += generation_tokens
        self.total_generation_time += generation_time
        self.last_updated = time.time()
    
    def update_failure(self):
        self.total_attempts += 1
        self.last_updated = time.time()

class AdvancedKLUCBOptimizer:
    
    def __init__(self, stats_file: str = r"E:\我的\python\new\Nbot0.4.0\data\account_stats.pkl", debug: bool = False):
        self.stats_file = stats_file
        self.debug = debug
        self.account_stats: Dict[str, AccountStats] = {}
        self.global_attempts = 0
        self.failed_accounts = set()
        self.load_stats()
    
    def _debug_print(self, message: str):
        if self.debug:
            pass
    
    def load_stats(self):
        try:
            if os.path.exists(self.stats_file):
                with open(self.stats_file, 'rb') as f:
                    data = pickle.load(f)
                    self.account_stats = data.get('account_stats', {})
                    self.global_attempts = data.get('global_attempts', 0)
                    self.failed_accounts = data.get('failed_accounts', set())
        except Exception as e:
            self.account_stats = {}
            self.global_attempts = 0
            self.failed_accounts = set()
    
    def save_stats(self):
        try:
            os.makedirs(os.path.dirname(self.stats_file), exist_ok=True)
            data = {
                'account_stats': self.account_stats,
                'global_attempts': self.global_attempts,
                'failed_accounts': self.failed_accounts
            }
            with open(self.stats_file, 'wb') as f:
                pickle.dump(data, f)
        except Exception as e:
            pass
    
    def _kl_divergence_upper_bound(self, p: float, level: float, precision: float = 1e-6) -> float:
        if p >= 1.0 - precision:
            return 1.0
        
        if level <= precision:
            return p
        
        low, high = p, 1.0
        
        for _ in range(100):
            mid = (low + high) / 2.0
            
            if mid <= precision or mid >= 1.0 - precision:
                break
            
            if p > precision:
                kl_div = p * math.log(p / mid)
            else:
                kl_div = 0
                
            if p < 1.0 - precision:
                kl_div += (1 - p) * math.log((1 - p) / (1 - mid))
            
            if kl_div <= level:
                low = mid
            else:
                high = mid
            
            if high - low < precision:
                break
        
        return (low + high) / 2.0
    
    def calculate_ultimate_score(self, email: str, message_length: int = 0) -> float:
        """计算终极KL-UCB得分，基于四个核心维度"""
        if email not in self.account_stats:
            return float('inf')
        
        stats = self.account_stats[email]
        
        if stats.total_attempts == 0:
            return float('inf')
        
        if email in self.failed_accounts:
            penalty = 0.1
        else:
            penalty = 1.0
        
        confidence_level = math.log(max(self.global_attempts, 1)) / stats.total_attempts
        empirical_success_rate = stats.success_rate
        ucb_bound = self._kl_divergence_upper_bound(empirical_success_rate, confidence_level)
        
        if stats.success_count > 0:
            delay_score = 1.0 / (1.0 + stats.avg_first_packet_delay)
        else:
            delay_score = 0.5
        
        if stats.success_count > 0 and stats.total_generation_time > 0:
            speed_score = min(stats.generation_speed / 50.0, 2.0)
        else:
            speed_score = 0.5
        
        if stats.success_count > 0:
            if message_length > 0:
                length_adaptability = min(stats.avg_message_length / max(message_length, 1), 2.0)
            else:
                length_adaptability = 1.0
        else:
            length_adaptability = 1.0
        
        ultimate_score = (
            ucb_bound * 0.4 +
            delay_score * 0.25 +
            speed_score * 0.25 +
            length_adaptability * 0.1
        ) * penalty
        
        return ultimate_score
    
    def select_optimal_account(self, available_accounts: List, message_length: int = 0) -> Optional:
        """选择最优账号，支持失败轮换"""
        if not available_accounts:
            return None
        
        account_scores = []
        for account in available_accounts:
            score = self.calculate_ultimate_score(account.email, message_length)
            account_scores.append((account, score))
        
        account_scores.sort(key=lambda x: x[1], reverse=True)
        optimal_account = account_scores[0][0]
        
        return optimal_account
    
    def update_account_result(self, email: str, success: bool, 
                            message_length: int = 0, 
                            first_packet_delay: float = 0.0,
                            generation_tokens: int = 0,
                            generation_time: float = 0.0):
        """更新账号结果，记录四个核心维度"""
        if email not in self.account_stats:
            self.account_stats[email] = AccountStats(email=email)
        
        stats = self.account_stats[email]
        
        if success:
            stats.update_success(message_length, first_packet_delay, generation_tokens, generation_time)
            self.failed_accounts.discard(email)
        else:
            stats.update_failure()
            self.failed_accounts.add(email)
        
        self.global_attempts += 1
        
        if self.global_attempts % 5 == 0:
            self.save_stats()
    
    def reset_failed_accounts(self):
        """重置失败账号集合，开始新一轮"""
        self.failed_accounts.clear()
    
    def get_performance_report(self) -> Dict:
        """获取性能报告"""
        if not self.account_stats:
            return {"message": "暂无统计数据"}
        
        sorted_stats = sorted(self.account_stats.items(), 
                            key=lambda x: self.calculate_ultimate_score(x[0]), reverse=True)
        
        report = {
            "total_accounts": len(self.account_stats),
            "global_attempts": self.global_attempts,
            "failed_accounts_count": len(self.failed_accounts),
            "top_performers": [],
            "algorithm_efficiency": 0.0
        }
        
        for email, stats in sorted_stats:
            report["top_performers"].append({
                "email": email,
                "success_rate": round(stats.success_rate * 100, 2),
                "success_count": stats.success_count,
                "total_attempts": stats.total_attempts,
                "avg_first_packet_delay": round(stats.avg_first_packet_delay, 2),
                "generation_speed": round(stats.generation_speed, 1),
                "avg_message_length": round(stats.avg_message_length, 0),
                "ultimate_score": round(self.calculate_ultimate_score(email), 3),
                "is_failed_this_round": email in self.failed_accounts
            })
        
        total_successes = sum(stats.success_count for stats in self.account_stats.values())
        total_attempts = sum(stats.total_attempts for stats in self.account_stats.values())
        if total_attempts > 0:
            report["algorithm_efficiency"] = round(total_successes / total_attempts * 100, 2)
        
        return report

@dataclass
class Account:
    email: str
    password: str
    password_hash: str = field(init=False)
    token: str = ""
    token_expires: float = 0
    user_id: str = ""
    last_used: float = 0
    is_busy: bool = False
    is_logged_in: bool = False
    is_initializing: bool = False
    login_attempts: int = 0
    
    def __post_init__(self):
        self.password_hash = hashlib.sha256(self.password.encode('utf-8')).hexdigest()

@dataclass
class SessionInfo:
    token: str
    chat_id: str
    email: str
    account_id: int
    user_id: str = ""

@dataclass 
class FileInfo:
    file_id: str
    file_url: str
    filename: str
    size: int
    content_type: str
    user_id: str
    file_type: str
    file_class: str

class FileUtils:
    
    @staticmethod
    def get_mime_type(filename: str) -> str:
        ext = os.path.splitext(filename)[1].lower()
        if ext in EXTENSION_TO_MIME:
            return EXTENSION_TO_MIME[ext]
        mime_type, _ = mimetypes.guess_type(filename)
        return mime_type or 'application/octet-stream'
    
    @staticmethod
    def get_file_category(content_type: str) -> tuple:
        if content_type in FILE_TYPE_MAPPING:
            file_type = FILE_TYPE_MAPPING[content_type]
        else:
            file_type = 'file'
        
        if content_type.startswith('image/'):
            file_class = 'vision'
        elif content_type.startswith('video/'):
            file_class = 'vision'
        elif content_type.startswith('audio/'):
            file_class = 'audio'
        else:
            file_class = 'document'
            
        return file_type, file_class
    
    @staticmethod
    def is_url(path: str) -> bool:
        return path.startswith(('http://', 'https://'))
    
    @staticmethod
    def get_filename_from_url(url: str) -> str:
        parsed = urlparse(url)
        path = parsed.path
        if path:
            filename = os.path.basename(path)
            if filename and '.' in filename:
                return filename
        return f"url_file_{int(time.time())}.jpg"
    
    @staticmethod
    async def get_url_file_info(session: aiohttp.ClientSession, url: str, user_id: str) -> FileInfo:
        try:
            async with session.head(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                content_type = response.headers.get('Content-Type', 'image/jpeg')
                if ';' in content_type:
                    content_type = content_type.split(';')[0].strip()
                
                content_length = response.headers.get('Content-Length')
                size = int(content_length) if content_length else 0
                
                filename = FileUtils.get_filename_from_url(url)
                
                if filename != f"url_file_{int(time.time())}.jpg":
                    inferred_type = FileUtils.get_mime_type(filename)
                    if inferred_type != 'application/octet-stream':
                        content_type = inferred_type
                
                file_type, file_class = FileUtils.get_file_category(content_type)
                
                return FileInfo(
                    file_id=str(uuid.uuid4()),
                    file_url=url,
                    filename=filename,
                    size=size,
                    content_type=content_type,
                    user_id=user_id,
                    file_type=file_type,
                    file_class=file_class
                )
        except Exception as e:
            filename = FileUtils.get_filename_from_url(url)
            return FileInfo(
                file_id=str(uuid.uuid4()),
                file_url=url,
                filename=filename,
                size=0,
                content_type='image/jpeg',
                user_id=user_id,
                file_type='image',
                file_class='vision'
            )

class AsyncAccountPool:
    
    def __init__(self, debug: bool = False):
        self.accounts: List[Account] = []
        self.available_accounts: List[Account] = []
        self.lock = None  # 延迟创建
        self.debug = debug
        self.session = None
        self.refresh_task = None
        self.running = True
        self.initialization_task = None
        self.initialized_count = 0
        self.kl_ucb_optimizer = AdvancedKLUCBOptimizer(debug=debug)
        self._initialized = False
        self._init_accounts()
    
    def _debug_print(self, message: str):
        if self.debug:
            pass
    
    def _init_accounts(self):
        for email in ACCOUNTS:
            self.accounts.append(Account(email, email))
    
    async def _ensure_lock(self):
        """确保锁已创建"""
        if self.lock is None:
            self.lock = Lock()
    
    async def initialize(self, session: aiohttp.ClientSession):
        if self._initialized:
            return
            
        await self._ensure_lock()
        self.session = session
        self._start_background_initialization()
        self._start_refresh_task()
        self._initialized = True
    
    def _start_background_initialization(self):
        """启动后台初始化任务"""
        self.initialization_task = asyncio.create_task(self._background_initialization())
    
    async def _background_initialization(self):
        """后台逐个初始化账号"""
        semaphore = Semaphore(3)  # 限制并发登录数
        
        async def login_single_account(account):
            async with semaphore:
                account.is_initializing = True
                success = await self._login_account(account)
                account.is_initializing = False
                
                if success:
                    await self._ensure_lock()
                    async with self.lock:
                        if account not in self.available_accounts:
                            self.available_accounts.append(account)
                            self.initialized_count += 1
                
                return success
        
        # 分批初始化，优先处理前几个账号
        for i in range(0, len(self.accounts), 5):
            batch = self.accounts[i:i+5]
            tasks = [login_single_account(account) for account in batch]
            await asyncio.gather(*tasks, return_exceptions=True)
            
            # 每批次后短暂休息
            await asyncio.sleep(0.5)
    
    async def _login_account(self, account: Account) -> bool:
        max_retries = 2
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                headers = {
                    "Host": "chat.qwen.ai",
                    "Content-Type": "application/json; charset=UTF-8",
                    "User-Agent": "Mozilla/5.0 (Linux; Android 10; BAH3-W09) AppleWebKit/537.36",
                    "Accept": "*/*",
                    "Origin": "https://chat.qwen.ai",
                    "Referer": "https://chat.qwen.ai/auth?action=signin",
                }
                
                data = {
                    "email": account.email,
                    "password": account.password_hash
                }
                
                async with self.session.post(
                    "https://chat.qwen.ai/api/v1/auths/signin",
                    headers=headers,
                    json=data,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    
                    if response.status == 200:
                        result = await response.json()
                        account.token = result.get("token", "")
                        account.token_expires = result.get("expires_at", 0)
                        account.user_id = result.get("id", "")
                        account.is_logged_in = True
                        account.login_attempts = 0
                        return True
                    else:
                        pass
                        
            except Exception as e:
                pass
            
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
        
        account.is_logged_in = False
        account.login_attempts += 1
        return False
    
    def _start_refresh_task(self):
        self.refresh_task = asyncio.create_task(self._token_refresh_worker())
    
    async def _token_refresh_worker(self):
        while self.running:
            try:
                current_time = time.time()
                accounts_to_refresh = []
                
                await self._ensure_lock()
                async with self.lock:
                    for account in self.available_accounts:
                        if account.is_logged_in and account.token_expires <= current_time + 600:
                            accounts_to_refresh.append(account)
                
                for account in accounts_to_refresh:
                    if not await self._login_account(account):
                        await self._ensure_lock()
                        async with self.lock:
                            if account in self.available_accounts:
                                self.available_accounts.remove(account)
                
                await self._ensure_lock()
                async with self.lock:
                    failed_accounts = [acc for acc in self.accounts 
                                     if not acc.is_logged_in and acc.login_attempts < 3 and not acc.is_initializing]
                
                for account in failed_accounts[:3]:  # 限制并发重试数
                    if await self._login_account(account):
                        await self._ensure_lock()
                        async with self.lock:
                            if account not in self.available_accounts:
                                self.available_accounts.append(account)
                
                await asyncio.sleep(30)
                
            except Exception as e:
                await asyncio.sleep(10)
    
    async def get_available_account(self, message_length: int = 0, is_retry: bool = False, wait_timeout: float = 10.0) -> Optional[Account]:
        """获取可用账号，支持等待初始化完成"""
        start_time = time.time()
        
        while time.time() - start_time < wait_timeout:
            await self._ensure_lock()
            async with self.lock:
                idle_accounts = [acc for acc in self.available_accounts 
                               if not acc.is_busy and acc.is_logged_in]
                
                if idle_accounts:
                    if is_retry and len(self.kl_ucb_optimizer.failed_accounts) >= len(idle_accounts):
                        self.kl_ucb_optimizer.reset_failed_accounts()
                    
                    optimal_account = self.kl_ucb_optimizer.select_optimal_account(idle_accounts, message_length)
                    
                    if optimal_account:
                        optimal_account.is_busy = True
                        optimal_account.last_used = time.time()
                        return optimal_account
            
            # 如果没有可用账号，等待一会儿再试
            if self.initialized_count < len(self.accounts):
                await asyncio.sleep(0.5)
            else:
                break
        
        return None
    
    async def release_account(self, account: Account, success: bool = True, 
                            message_length: int = 0,
                            first_packet_delay: float = 0.0,
                            generation_tokens: int = 0,
                            generation_time: float = 0.0):
        """释放账号并更新统计"""
        await self._ensure_lock()
        async with self.lock:
            account.is_busy = False
            
            self.kl_ucb_optimizer.update_account_result(
                account.email, success, message_length, 
                first_packet_delay, generation_tokens, generation_time
            )
    
    async def get_status(self) -> Dict:
        await self._ensure_lock()
        async with self.lock:
            total = len(self.accounts)
            logged_in = len([a for a in self.accounts if a.is_logged_in])
            available = len([a for a in self.available_accounts if not a.is_busy])
            busy = len([a for a in self.available_accounts if a.is_busy])
            initializing = len([a for a in self.accounts if a.is_initializing])
            
            return {
                "total_accounts": total,
                "logged_in": logged_in,
                "available": available,
                "busy": busy,
                "initializing": initializing,
                "initialized_count": self.initialized_count
            }
    
    async def shutdown(self):
        self.running = False
        if self.refresh_task:
            self.refresh_task.cancel()
            try:
                await self.refresh_task
            except asyncio.CancelledError:
                pass
        
        if self.initialization_task:
            self.initialization_task.cancel()
            try:
                await self.initialization_task
            except asyncio.CancelledError:
                pass
        
        self.kl_ucb_optimizer.save_stats()

class AdvancedOSSUploader:
    
    def __init__(self, session: aiohttp.ClientSession, debug: bool = False):
        self.session = session
        self.debug = debug
        self.max_retries = 3
        self.timeout = 60
    
    def _debug_print(self, message: str):
        if self.debug:
            pass
    
    def _generate_oss_authorization(self, 
                                  method: str, 
                                  content_type: str, 
                                  date: str, 
                                  oss_headers: Dict[str, str], 
                                  resource: str, 
                                  access_key_id: str, 
                                  access_key_secret: str) -> str:
        
        canonicalized_oss_headers = ""
        if oss_headers:
            sorted_headers = sorted(oss_headers.items())
            canonicalized_oss_headers = "\n".join([f"{k}:{v}" for k, v in sorted_headers]) + "\n"
        
        string_to_sign = f"{method}\n\n{content_type}\n{date}\n{canonicalized_oss_headers}{resource}"
        
        signature = base64.b64encode(
            hmac.new(
                access_key_secret.encode('utf-8'),
                string_to_sign.encode('utf-8'),
                hashlib.sha1
            ).digest()
        ).decode('utf-8')
        
        return f"OSS {access_key_id}:{signature}"
    
    async def upload_file_with_retry(self, file_path: str, upload_info: Dict) -> str:
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            try:
                if attempt > 0:
                    delay = min(1000 * (2 ** (attempt - 1)), 3000) / 1000
                    await asyncio.sleep(delay)
                
                return await self._upload_with_sts_put(file_path, upload_info)
                
            except Exception as e:
                last_error = e
                
                if attempt == self.max_retries:
                    return upload_info['file_url']
        
        return upload_info['file_url']
    
    async def _upload_with_sts_put(self, file_path: str, upload_info: Dict) -> str:
        filename = os.path.basename(file_path)
        
        with open(file_path, 'rb') as f:
            file_content = f.read()
        
        content_type = FileUtils.get_mime_type(filename)
        
        parsed_url = urlparse(upload_info['file_url'])
        bucket_host = parsed_url.netloc
        object_key = upload_info['file_path']
        
        gmt_date = datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S GMT')
        
        oss_headers = {
            'x-oss-security-token': upload_info['security_token']
        }
        
        bucket_name = bucket_host.split('.')[0]
        resource = f"/{bucket_name}/{object_key}"
        
        authorization = self._generate_oss_authorization(
            method="PUT",
            content_type=content_type,
            date=gmt_date,
            oss_headers=oss_headers,
            resource=resource,
            access_key_id=upload_info['access_key_id'],
            access_key_secret=upload_info['access_key_secret']
        )
        
        headers = {
            "Host": bucket_host,
            "Date": gmt_date,
            "Content-Type": content_type,
            "Content-Length": str(len(file_content)),
            "Authorization": authorization,
            "x-oss-security-token": upload_info['security_token'],
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Origin": "https://chat.qwen.ai",
            "Referer": "https://chat.qwen.ai/",
        }
        
        upload_url = f"https://{bucket_host}/{object_key}"
        
        try:
            async with self.session.put(
                upload_url,
                data=file_content,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            ) as response:
                
                if response.status in [200, 201]:
                    return upload_info['file_url']
                else:
                    return upload_info['file_url']
                    
        except Exception as e:
            raise

class AsyncQwenClient:
    
    def __init__(self, max_concurrent_requests: int = 100, debug: bool = False):
        self.account_pool = AsyncAccountPool(debug=debug)
        self.session_lock = None  # 延迟创建
        self.semaphore = None  # 延迟创建
        self.connector = None
        self.session = None
        self._closing = False
        self._initialized = False
        self.debug = debug
        self.oss_uploader = None
        self._init_lock = None  # 延迟创建
        self.max_concurrent_requests = max_concurrent_requests
        
    def _debug_print(self, message: str):
        if self.debug:
            pass
    
    async def _ensure_async_primitives(self):
        """确保异步原语已创建"""
        if self._init_lock is None:
            self._init_lock = asyncio.Lock()
        if self.session_lock is None:
            self.session_lock = Lock()
        if self.semaphore is None:
            self.semaphore = Semaphore(self.max_concurrent_requests)
        
    async def ensure_initialized(self):
        """确保客户端已初始化"""
        if self._initialized:
            return
        
        await self._ensure_async_primitives()
        async with self._init_lock:
            if self._initialized:
                return
            
            await self.initialize()
    
    async def initialize(self):
        """初始化客户端"""
        if self._initialized:
            return
        
        # 确保在当前事件循环中创建连接
        try:
            self.connector = aiohttp.TCPConnector(
                limit=100, 
                limit_per_host=30,
                keepalive_timeout=30,
                enable_cleanup_closed=True
            )
            self.session = aiohttp.ClientSession(
                connector=self.connector,
                timeout=aiohttp.ClientTimeout(total=30)
            )
            self.oss_uploader = AdvancedOSSUploader(self.session, self.debug)
            await self.account_pool.initialize(self.session)
            self._initialized = True
        except Exception as e:
            # 如果初始化失败，清理资源
            await self._cleanup_resources()
            raise e
        
    async def _cleanup_resources(self):
        """清理资源"""
        try:
            if self.session and not self.session.closed:
                await self.session.close()
        except Exception:
            pass
            
        try:
            if self.connector and not self.connector.closed:
                await self.connector.close()
        except Exception:
            pass
            
    async def close(self):
        """关闭客户端"""
        if self._closing:
            return
        self._closing = True
        
        try:
            await self.account_pool.shutdown()
        except Exception as e:
            pass
        
        await self._cleanup_resources()
        await asyncio.sleep(0.1)
        self._initialized = False
    
    async def _create_new_chat(self, token: str, model: str = "qwen3-coder-plus") -> str:
        """创建新对话"""
        headers = {
            "authorization": f"Bearer {token}",
            "content-type": "application/json; charset=UTF-8",
            "source": "web",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "origin": "https://chat.qwen.ai",
            "referer": "https://chat.qwen.ai/",
            "accept": "application/json",
            "accept-language": "zh-CN,zh;q=0.9",
            "x-request-id": str(uuid.uuid4()),
        }
        
        payload = {
            "title": "新建对话",
            "models": [model],
            "chat_mode": "normal",
            "chat_type": "t2t",
            "timestamp": int(time.time() * 1000)
        }
        
        async with self.session.post(
            "https://chat.qwen.ai/api/v2/chats/new",
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=15)
        ) as response:
            response.raise_for_status()
            data = await response.json()
            
            if not data.get("success"):
                raise Exception(f"创建对话失败: {data}")
            
            chat_id = data.get("data", {}).get("id")
            if not chat_id:
                raise Exception(f"创建对话响应缺少chat_id: {data}")
            
            return chat_id
    
    async def _get_upload_credentials_with_retry(self, filename: str, filesize: int, token: str) -> Dict:
        """获取上传凭据（重试版本）"""
        for attempt in range(3):
            try:
                return await self._get_upload_credentials(filename, filesize, token)
            except Exception as e:
                if attempt == 2:
                    raise
                await asyncio.sleep(1)
    
    async def _get_upload_credentials(self, filename: str, filesize: int, token: str) -> Dict:
        """获取上传凭据"""
        headers = {
            "authorization": f"Bearer {token}",
            "content-type": "application/json; charset=UTF-8",
            "source": "web",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "origin": "https://chat.qwen.ai",
            "referer": "https://chat.qwen.ai/",
            "accept": "*/*",
            "accept-language": "zh-CN,zh;q=0.9",
            "x-request-id": str(uuid.uuid4()),
        }
        
        content_type = FileUtils.get_mime_type(filename)
        file_type, _ = FileUtils.get_file_category(content_type)
        
        payload = {
            "filename": filename,
            "filesize": filesize,
            "filetype": file_type
        }
        
        api_urls = [
            "https://chat.qwen.ai/api/v2/files/getstsToken",
            "https://chat.qwen.ai/api/v1/files/getstsToken"
        ]
        
        last_error = None
        for api_url in api_urls:
            try:
                async with self.session.post(
                    api_url,
                    json=payload, 
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=15)
                ) as response:
                    
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"获取上传凭据失败，状态码: {response.status}, 响应: {error_text}")
                    
                    data = await response.json()
                    
                    if "data" in data:
                        return data["data"]
                    elif all(key in data for key in ["access_key_id", "access_key_secret", "security_token"]):
                        return data
                    else:
                        raise Exception(f"上传凭据响应格式异常: {data}")
                        
            except Exception as e:
                last_error = e
                continue
        
        raise last_error or Exception("所有API都失败")
    
    async def upload_file(self, file_path: str, account: Account) -> FileInfo:
        """上传文件"""
        if not os.path.exists(file_path):
            raise Exception(f"文件不存在: {file_path}")
        
        filename = os.path.basename(file_path)
        filesize = os.path.getsize(file_path)
        content_type = FileUtils.get_mime_type(filename)
        file_type, file_class = FileUtils.get_file_category(content_type)
        
        max_size = 100 * 1024 * 1024
        if filesize > max_size:
            raise Exception(f"文件过大: {filename} ({filesize} bytes)，最大支持100MB")
        
        if filesize == 0:
            raise Exception(f"文件为空: {filename}")
        
        try:
            upload_info = await self._get_upload_credentials_with_retry(
                filename, filesize, account.token
            )
            
            required_fields = ["access_key_id", "access_key_secret", "security_token", "file_url", "file_path"]
            missing_fields = [field for field in required_fields if not upload_info.get(field)]
            if missing_fields:
                raise Exception(f"上传凭据缺少字段: {missing_fields}")
            
            file_url = await self.oss_uploader.upload_file_with_retry(file_path, upload_info)
            
            return FileInfo(
                file_id=upload_info.get('file_id', str(uuid.uuid4())),
                file_url=file_url,
                filename=filename,
                size=filesize,
                content_type=content_type,
                user_id=account.user_id,
                file_type=file_type,
                file_class=file_class
            )
            
        except Exception as e:
            raise Exception(f"文件上传失败 {filename}: {str(e)}")
    
    def _build_file_object(self, file_info: FileInfo) -> Dict:
        """构建文件对象"""
        current_time = int(time.time() * 1000)
        item_id = str(uuid.uuid4())
        upload_task_id = str(uuid.uuid4())
        
        if file_info.file_class == 'vision' and file_info.content_type.startswith('image/'):
            show_type = 'image'
        elif file_info.file_class == 'vision' and file_info.content_type.startswith('video/'):
            show_type = 'video'
        elif file_info.file_class == 'audio':
            show_type = 'audio'
        else:
            show_type = 'file'
        
        return {
            "type": file_info.file_type,
            "file": {
                "created_at": current_time,
                "data": {},
                "filename": file_info.filename,
                "hash": None,
                "id": file_info.file_id,
                "user_id": file_info.user_id,
                "meta": {
                    "name": file_info.filename,
                    "size": file_info.size,
                    "content_type": file_info.content_type
                },
                "update_at": current_time
            },
            "id": file_info.file_id,
            "url": file_info.file_url,
            "name": file_info.filename,
            "collection_name": "",
            "progress": 0,
            "status": "uploaded",
            "greenNet": "success",
            "size": file_info.size,
            "error": "",
            "itemId": item_id,
            "file_type": file_info.content_type,
            "showType": show_type,
            "file_class": file_info.file_class,
            "uploadTaskId": upload_task_id
        }
    
    def _build_payload(self, message: str, chat_id: str, model: str, files: List[Dict] = None) -> Dict:
        """构建请求载荷"""
        if files is None:
            files = [] 
        return {
            "stream": True,
            "incremental_output": True,
            "chat_id": chat_id,
            "chat_mode": "normal",
            "model": model,
            "parent_id": None,
            "messages": [{
                "fid": str(uuid.uuid4()),
                "parentId": None,
                "childrenIds": [str(uuid.uuid4())],
                "role": "user",
                "content": message,
                "user_action": "chat",
                "files": files,
                "timestamp": int(time.time() * 1000),
                "models": [model],
                "chat_type": "t2t",
                "feature_config": {
                    "thinking_enabled": False,
                    "output_schema": "phase",
                    "thinking_budget": 1024,
                    "mcp": {}
                },
            "generate_cfg": {
                "max_input_tokens": 1048576,
                "max_tokens": 1048576,
                "max_new_tokens": 1048576-len(message),
                "seed": -1,
                "function_choice": "none",
                "system_message":" ",
                "fncall_prompt_type":"qwen",
                "incremental_output": True,
                "skip_stopword_postproc": False,
                "max_retries": 3,
                "cache_dir":"./cache"
            },
                "extra": {"meta": {"subChatType": "t2t"}},
                "sub_chat_type": "t2t",
                "parent_id": None,
            }],
            "timestamp": int(time.time() * 1000),
        }
    
    def _estimate_tokens(self, text: str) -> int:
        """估算token数量（简单方法）"""
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        english_words = len(re.findall(r'[a-zA-Z]+', text))
        return chinese_chars + int(english_words * 0.75)
    
    async def chat_stream(
        self, 
        message: str, 
        model: str = "qwen3-coder-plus",
        file_paths: Union[str, List[str]] = None,
        max_retries: int = 2
    ) -> AsyncGenerator[str, None]:
        """流式聊天，支持智能账号轮换"""
        await self.ensure_initialized()
        
        message_length = len(message)
        
        await self._ensure_async_primitives()
        async with self.semaphore:
            for attempt in range(max_retries + 1):
                account = None
                start_time = time.time()
                first_packet_time = None
                generation_start_time = None
                success = False
                total_tokens = 0
                
                try:
                    account = await self.account_pool.get_available_account(
                        message_length, is_retry=(attempt > 0), wait_timeout=15.0
                    )
                    if not account:
                        raise Exception("没有可用的账号")
                    
                    files = []
                    
                    if file_paths:
                        if isinstance(file_paths, str):
                            file_paths = [file_paths]
                        
                        for file_path_or_url in file_paths:
                            if file_path_or_url and file_path_or_url.strip():
                                try:
                                    if FileUtils.is_url(file_path_or_url):
                                        file_info = await FileUtils.get_url_file_info(
                                            self.session, file_path_or_url, account.user_id
                                        )
                                        file_obj = self._build_file_object(file_info)
                                        files.append(file_obj)
                                    else:
                                        file_info = await self.upload_file(file_path_or_url, account)
                                        file_obj = self._build_file_object(file_info)
                                        files.append(file_obj)
                                        
                                except Exception as e:
                                    yield f"[文件处理错误] {file_path_or_url}: {str(e)}\n"
                                    return
                    
                    try:
                        chat_id = await self._create_new_chat(account.token, model)
                    except Exception as e:
                        raise Exception(f"创建对话失败: {str(e)}")
                    async for chunk in self._send_chat_request(account, chat_id, message, model, files):
                        if first_packet_time is None:
                            first_packet_time = time.time()
                            generation_start_time = first_packet_time
                        
                        total_tokens += self._estimate_tokens(chunk)
                        yield chunk
                    
                    success = True
                    return
                    
                except Exception as e:
                    if attempt == max_retries:
                        yield f"[聊天错误] 已重试 {max_retries} 次，最终失败: {str(e)}\n"
                        return
                    else:
                        await asyncio.sleep(1)
                finally:
                    if account:
                        if first_packet_time:
                            first_packet_delay = first_packet_time - start_time
                        else:
                            first_packet_delay = 0.0
                        
                        if generation_start_time and success:
                            generation_time = time.time() - generation_start_time
                        else:
                            generation_time = 0.0
                        
                        await self.account_pool.release_account(
                            account, success, message_length, 
                            first_packet_delay, total_tokens, generation_time
                        )
    
    async def _send_chat_request(
        self, 
        account: Account, 
        chat_id: str, 
        message: str, 
        model: str, 
        files: List[Dict]
    ) -> AsyncGenerator[str, None]:
        """发送聊天请求"""
        headers = {
            "authorization": f"Bearer {account.token}",
            "content-type": "application/json; charset=utf-8",
            "source": "web",
            "x-accel-buffering": "no",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "accept": "text/event-stream",
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
            "accept-charset": "utf-8",
            "origin": "https://chat.qwen.ai",
            "referer": "https://chat.qwen.ai/"
        }
        
        payload = self._build_payload(message, chat_id, model, files)
        request_url = f"https://chat.qwen.ai/api/v2/chat/completions?chat_id={chat_id}"
        async with self.session.post(
            request_url,
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=120)
        ) as response:
            
            if response.status != 200:
                error_text = await response.text()
                raise Exception(f"HTTP {response.status}: {error_text}")
            
            content_received = False
            
            async for line in response.content:
                if not line:
                    continue
                
                try:
                    line_str = line.decode('utf-8', errors='replace').strip()
                except:
                    continue
                
                if not line_str or not line_str.startswith("data: "):
                    continue
                
                data_str = line_str[6:]
                if data_str.strip() == "[DONE]":
                    break
                
                try:
                    data = json.loads(data_str)
                    
                    if "choices" in data and data["choices"]:
                        delta = data["choices"][0].get("delta", {})
                        if delta.get("phase") == "answer" and (content := delta.get("content")):
                            content_received = True
                            yield content
                    elif "error" in data:
                        raise Exception(f"服务器错误: {data['error']}")
                        
                except json.JSONDecodeError:
                    continue
                except Exception as e:
                    continue
            
            if not content_received:
                yield "[警告] 未收到模型回复内容\n"
    
    async def chat_completion(
        self, 
        message: str, 
        model: str = "qwen3-coder-plus",
        file_paths: Union[str, List[str]] = None
    ) -> str:
        """非流式聊天"""
        result_content = []
        async for chunk in self.chat_stream(message, model, file_paths):
            result_content.append(chunk)
        
        final_content = "".join(result_content)
        
        if not final_content or final_content.strip() == "[警告] 未收到模型回复内容":
            final_content = "抱歉，我没有收到有效的回复内容。"
        
        return final_content
    
    async def get_account_status(self) -> Dict:
        """获取账号状态"""
        await self.ensure_initialized()
        return await self.account_pool.get_status()
    
    async def get_kl_ucb_report(self) -> Dict:
        """获取KL-UCB报告"""
        await self.ensure_initialized()
        return self.account_pool.kl_ucb_optimizer.get_performance_report()

# ============= 全局客户端管理 =============

_global_client = None
_client_lock = threading.Lock()

async def get_client() -> AsyncQwenClient:
    """获取全局客户端实例"""
    global _global_client
    
    if _global_client is None:
        with _client_lock:
            if _global_client is None:
                _global_client = AsyncQwenClient(debug=False)
    
    await _global_client.ensure_initialized()
    return _global_client

async def cleanup_client():
    """清理全局客户端"""
    global _global_client
    
    if _global_client:
        try:
            await _global_client.close()
        except Exception as e:
            pass
        finally:
            with _client_lock:
                _global_client = None

# ============= 入口函数 =============

async def quick_chat(message: str, file_paths: Union[str, List[str]] = None,model: str = "qwen3-coder-plus") -> str:
    """
    快速聊天接口（非流式）
    
    Args:
        message: 消息内容
        model: 模型名称
        file_paths: 文件路径（可选）
    
    Returns:
        完整的回复内容
    """
    client = await get_client()
    return await client.chat_completion(message, model, file_paths)

async def quick_stream(message: str, file_paths: Union[str, List[str]] = None,model: str = "qwen3-coder-plus") -> AsyncGenerator[str, None]:
    """
    快速流式聊天接口
    
    Args:
        message: 消息内容
        model: 模型名称
        file_paths: 文件路径（可选）
    
    Yields:
        流式回复内容
    """
    client = await get_client()
    async for chunk in client.chat_stream(message, model, file_paths):
        yield chunk

# ============= 便捷函数 =============

async def chat_with_image(message: str, image_path: str, model: str = "qwen3-coder-plus") -> str:
    """带图片的聊天"""
    return await quick_chat(message, model, image_path)

async def chat_with_url(message: str, image_url: str, model: str = "qwen3-coder-plus") -> str:
    """带URL的聊天"""
    return await quick_chat(message, model, image_url)

async def main():
    """测试函数"""
    try:
        async for chunk in quick_stream("详细描述图片内容",["https://www.10wallpaper.com/wallpaper/1920x1080/1503/Beautiful_green_plain_bay-2015_Bing_theme_wallpaper_1920x1080.jpg"]):
            print(chunk, end="", flush=True)
        print("\n")
    except Exception as e:
        print(f"错误: 文本聊天测试失败: {e}")
    
    await cleanup_client()

if __name__ == "__main__":
    asyncio.run(main())

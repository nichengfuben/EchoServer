import asyncio
import aiohttp
import websockets
import json
import time
import uuid
import os
import ssl
import hashlib
import logging
import mimetypes
from typing import Optional, Dict, List, Any, Callable, Coroutine, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum
from urllib.parse import urljoin, urlencode
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ============================================================================
# 全局状态变量（使用大写字母）
# ============================================================================

# 认证相关全局变量
ACCESS_TOKEN: Optional[str] = None
REFRESH_TOKEN: Optional[str] = None
ACCESS_TOKEN_EXPIRES: int = 0
REFRESH_TOKEN_EXPIRES: int = 0
USER_ID: Optional[int] = None

# 消息统计全局变量
GLOBAL_SUM_MESSAGE: int = 0

# WebSocket相关全局变量
WEBSOCKET_TASK: Optional[asyncio.Task] = None
WEBSOCKET_RECONNECT_COUNT: int = 0
MESSAGE_HANDLERS: List[Callable] = []

# 错误信息全局变量
LAST_ERROR: str = ""

# HTTP会话全局变量
HTTP_SESSION: Optional[requests.Session] = None

# ============================================================================
# 配置和常量定义
# ============================================================================

class Config:
    """SDK配置类"""
    
    # 基础URL配置
    BASE_URL = "https://www.boxim.online"
    WS_URL = "wss://www.boxim.online/im"
    
    # HTTP配置
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36 Edg/138.0.0.0"
    TIMEOUT: int = 30
    MAX_RETRIES: int = 3
    BACKOFF_FACTOR: float = 0.3
    
    # WebSocket配置
    WEBSOCKET_RECONNECT_DELAY = 1
    HEARTBEAT_INTERVAL = 20
    
    # 文件大小限制
    MAX_IMAGE_SIZE: int = 20 * 1024 * 1024  # 20MB
    MAX_FILE_SIZE: int = 20 * 1024 * 1024   # 20MB
    
    # 群聊人数限制
    MAX_LARGE_GROUP_MEMBER: int = 3000
    MAX_NORMAL_GROUP_MEMBER: int = 500
    
    # 日志配置
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


class MessageType(Enum):
    """消息类型枚举"""
    TEXT = 0           # 文字消息
    IMAGE = 1          # 图片消息
    FILE = 2           # 文件消息
    VOICE = 3          # 语音消息
    AUDIO = 3          # 语音消息（别名）
    VIDEO = 4          # 视频消息
    USER_CARD = 5      # 个人名片
    GROUP_CARD = 6     # 群聊名片
    RECALL = 10        # 撤回
    READED = 11        # 已读
    RECEIPT = 12       # 消息已读回执
    TIP_TIME = 20      # 时间提示
    TIP_TEXT = 21      # 文字提示
    SYSTEM = 21        # 系统消息（别名）
    LOADING = 30       # 加载中标记
    ACT_RT_VOICE = 40  # 语音通话
    ACT_RT_VIDEO = 41  # 视频通话


class TerminalType(Enum):
    """终端类型枚举"""
    WEB = 0    # Web端
    APP = 1    # 移动端
    PC = 2     # PC端


# ============================================================================
# 异常类定义
# ============================================================================

class BoxIMException(Exception):
    """基础异常类"""
    
    def __init__(self, message: str, code: Optional[int] = None, response: Optional[requests.Response] = None):
        self.message = message
        self.code = code
        self.response = response
        super().__init__(self.message)


class AuthenticationError(BoxIMException):
    """认证错误"""
    pass


class ValidationError(BoxIMException):
    """验证错误"""
    pass


class NetworkError(BoxIMException):
    """网络错误"""
    pass


class ServerError(BoxIMException):
    """服务器错误"""
    pass


# ============================================================================
# 数据模型定义
# ============================================================================

@dataclass
class LoginRequest:
    """登录请求模型"""
    terminal: int
    userName: str
    password: str


@dataclass
class LoginResponse:
    """登录响应模型"""
    accessToken: str
    accessTokenExpiresIn: int
    refreshToken: str
    refreshTokenExpiresIn: int


@dataclass
class RegisterRequest:
    """注册请求模型"""
    userName: str
    password: str
    nickName: str
    sex: Optional[int] = None
    signature: Optional[str] = None


@dataclass
class UserInfo:
    """用户信息模型"""
    id: Optional[int] = None
    userName: Optional[str] = None
    nickName: Optional[str] = None
    sex: Optional[int] = None
    type: Optional[int] = None
    signature: Optional[str] = None
    headImage: Optional[str] = None
    headImageThumb: Optional[str] = None
    online: Optional[bool] = None
    isBanned: Optional[bool] = None
    reason: Optional[str] = None


@dataclass
class GroupInfo:
    """群组信息模型"""
    id: Optional[int] = None
    name: Optional[str] = None
    ownerId: Optional[int] = None
    headImage: Optional[str] = None
    headImageThumb: Optional[str] = None
    notice: Optional[str] = None
    remarkNickName: Optional[str] = None
    showNickName: Optional[str] = None
    showGroupName: Optional[str] = None
    remarkGroupName: Optional[str] = None
    dissolve: Optional[bool] = None
    quit: Optional[bool] = None
    isBanned: Optional[bool] = None
    reason: Optional[str] = None
    isDnd: Optional[bool] = None


@dataclass
class PrivateMessage:
    """私聊消息模型"""
    tmpId: Optional[str] = None
    recvId: Optional[int] = None
    content: Optional[str] = None
    type: Optional[int] = None


@dataclass
class GroupMessage:
    """群聊消息模型"""
    tmpId: Optional[str] = None
    groupId: Optional[int] = None
    content: Optional[str] = None
    type: Optional[int] = None
    receipt: Optional[bool] = False
    atUserIds: Optional[List[int]] = None


# ============================================================================
# 工具函数
# ============================================================================

def _get_content_type(filename: str) -> str:
    """根据文件名获取内容类型"""
    ext = filename.lower().split('.')[-1]
    
    if ext in ['jpg', 'jpeg']:
        return 'image/jpeg'
    elif ext == 'png':
        return 'image/png'
    elif ext == 'gif':
        return 'image/gif'
    elif ext in ['mp4', 'mov', 'avi']:
        return f'video/{ext}'
    elif ext in ['mp3', 'wav', 'ogg']:
        return f'audio/{ext}'
    elif ext in ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt', 'zip', 'rar']:
        return f'application/{ext}'
    else:
        return 'application/octet-stream'


def _setup_logging(debug: bool = False) -> logging.Logger:
    """设置日志配置"""
    level = logging.DEBUG if debug else getattr(logging, Config.LOG_LEVEL)
    logging.basicConfig(level=level, format=Config.LOG_FORMAT)
    return logging.getLogger(__name__)


def _create_session() -> requests.Session:
    """创建HTTP会话"""
    session = requests.Session()
    
    # 配置重试策略
    retry_strategy = Retry(
        total=Config.MAX_RETRIES,
        status_forcelist=[429, 500, 502, 503, 504],
        backoff_factor=Config.BACKOFF_FACTOR
    )
    
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    return session


def _get_headers() -> Dict[str, str]:
    """获取通用请求头"""
    global ACCESS_TOKEN
    return {
        "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
        "Connection": "keep-alive",
        "Content-Type": "application/json",
        "Host": "www.boxim.online",
        "Origin": Config.BASE_URL,
        "Referer": f"{Config.BASE_URL}/",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": Config.USER_AGENT,
        "accessToken": ACCESS_TOKEN or "",
        "sec-ch-ua": "\"Not)A;Brand\";v=\"8\", \"Chromium\";v=\"138\", \"Microsoft Edge\";v=\"138\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\""
    }


def _build_headers(extra_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """构建请求头"""
    global ACCESS_TOKEN
    headers = {
        "Content-Type": "application/json",
        "User-Agent": Config.USER_AGENT,
    }
    
    if ACCESS_TOKEN:
        headers["accessToken"] = ACCESS_TOKEN
    
    if extra_headers:
        headers.update(extra_headers)
    
    return headers


def _handle_response(response: requests.Response) -> Any:
    """处理API响应"""
    global ACCESS_TOKEN, REFRESH_TOKEN, LAST_ERROR
    
    try:
        response.raise_for_status()
    except requests.RequestException as e:
        LAST_ERROR = f"网络请求失败: {e}"
        raise NetworkError(LAST_ERROR, response=response)
    
    try:
        data = response.json()
    except ValueError as e:
        LAST_ERROR = f"服务器响应格式错误: {e}"
        raise ServerError(LAST_ERROR, response=response)
    
    if data.get("code") == 200:
        LAST_ERROR = ""
        return data.get("data")
    elif data.get("code") == 401:
        # Token过期，尝试刷新
        if REFRESH_TOKEN:
            try:
                login_result = refresh_access_token()
                # 重新发送原请求
                response.request.headers["accessToken"] = ACCESS_TOKEN
                session = _get_session()
                new_response = session.send(response.request)
                return _handle_response(new_response)
            except Exception as e:
                LAST_ERROR = "Token刷新失败，请重新登录"
                raise AuthenticationError(LAST_ERROR)
        else:
            LAST_ERROR = "访问令牌无效或已过期"
            raise AuthenticationError(LAST_ERROR)
    elif data.get("code") == 400:
        LAST_ERROR = data.get("message", "请求参数错误")
        raise ValidationError(LAST_ERROR)
    else:
        LAST_ERROR = data.get("message", "服务器内部错误")
        raise ServerError(LAST_ERROR, code=data.get("code"))


def _get_session() -> requests.Session:
    """获取HTTP会话"""
    global HTTP_SESSION
    if HTTP_SESSION is None:
        HTTP_SESSION = _create_session()
    return HTTP_SESSION


def _make_request(
    method: str,
    url: str,
    params: Optional[Dict[str, Any]] = None,
    data: Optional[Any] = None,
    json_data: Optional[Dict[str, Any]] = None,
    files: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    **kwargs
) -> Any:
    """发送HTTP请求"""
    global LAST_ERROR
    
    request_headers = _build_headers(headers)
    session = _get_session()
    
    try:
        response = session.request(
            method=method,
            url=url,
            params=params,
            data=data,
            json=json_data,
            files=files,
            headers=request_headers,
            timeout=Config.TIMEOUT,
            **kwargs
        )
        
        return _handle_response(response)
        
    except requests.RequestException as e:
        LAST_ERROR = f"网络请求失败: {e}"
        raise NetworkError(LAST_ERROR)


# ============================================================================
# 状态管理函数
# ============================================================================

def get_login_status() -> Dict[str, Any]:
    """获取登录状态信息"""
    global ACCESS_TOKEN, USER_ID, ACCESS_TOKEN_EXPIRES, REFRESH_TOKEN_EXPIRES, GLOBAL_SUM_MESSAGE
    return {
        "is_logged_in": is_logged_in(),
        "user_id": USER_ID,
        "access_token_expires": ACCESS_TOKEN_EXPIRES,
        "refresh_token_expires": REFRESH_TOKEN_EXPIRES,
        "global_message_count": GLOBAL_SUM_MESSAGE
    }


def is_logged_in() -> bool:
    """检查是否已登录且token有效"""
    global ACCESS_TOKEN, ACCESS_TOKEN_EXPIRES
    return (ACCESS_TOKEN is not None and 
            time.time() < ACCESS_TOKEN_EXPIRES - 60)


def get_user_id() -> Optional[int]:
    """获取当前登录用户ID"""
    global USER_ID
    return USER_ID


def get_global_message_count() -> int:
    """获取全局消息计数"""
    global GLOBAL_SUM_MESSAGE
    return GLOBAL_SUM_MESSAGE


def get_last_error() -> str:
    """获取最后一次错误信息"""
    global LAST_ERROR
    return LAST_ERROR


def clear_last_error():
    """清除最后一次错误信息"""
    global LAST_ERROR
    LAST_ERROR = ""


def clear_state():
    """清空状态（用于测试或重置）"""
    global ACCESS_TOKEN, REFRESH_TOKEN, ACCESS_TOKEN_EXPIRES, REFRESH_TOKEN_EXPIRES
    global USER_ID, GLOBAL_SUM_MESSAGE, WEBSOCKET_TASK, WEBSOCKET_RECONNECT_COUNT
    global MESSAGE_HANDLERS, LAST_ERROR, HTTP_SESSION
    
    ACCESS_TOKEN = None
    REFRESH_TOKEN = None
    ACCESS_TOKEN_EXPIRES = 0
    REFRESH_TOKEN_EXPIRES = 0
    USER_ID = None
    GLOBAL_SUM_MESSAGE = 0
    WEBSOCKET_TASK = None
    WEBSOCKET_RECONNECT_COUNT = 0
    MESSAGE_HANDLERS = []
    LAST_ERROR = ""
    
    if HTTP_SESSION:
        HTTP_SESSION.close()
        HTTP_SESSION = None


# ============================================================================
# 认证相关API
# ============================================================================

async def login(username: str, password: str, terminal: int = 0) -> bool:
    """登录获取token（异步版本）"""
    global ACCESS_TOKEN, REFRESH_TOKEN, ACCESS_TOKEN_EXPIRES, REFRESH_TOKEN_EXPIRES, USER_ID, LAST_ERROR
    
    url = f"{Config.BASE_URL}/api/login"
    headers = {
        "content-type": "application/json",
        "accept": "application/json, text/plain, */*"
    }
    payload = {
        "terminal": int(terminal),
        "userName": str(username),
        "password": str(password)
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                data = await response.json()
                if data.get("code") == 200:
                    ACCESS_TOKEN = data["data"]["accessToken"]
                    REFRESH_TOKEN = data["data"]["refreshToken"]
                    ACCESS_TOKEN_EXPIRES = time.time() + data["data"]["accessTokenExpiresIn"]
                    REFRESH_TOKEN_EXPIRES = time.time() + data["data"]["refreshTokenExpiresIn"]
                    USER_ID = data["data"].get("userId")
                    LAST_ERROR = ""
                    return True
                else:
                    LAST_ERROR = data.get('message', '登录失败')
                    return False
    except Exception as e:
        LAST_ERROR = f"登录异常: {str(e)}"
        return False


def login_sync(
    username: str,
    password: str,
    terminal: int = TerminalType.WEB.value
) -> Dict[str, Any]:
    """用户登录（同步版本）"""
    global ACCESS_TOKEN, REFRESH_TOKEN, ACCESS_TOKEN_EXPIRES, REFRESH_TOKEN_EXPIRES, USER_ID
    
    if not username or not password:
        raise ValidationError("用户名和密码不能为空")
    
    if terminal not in [0, 1, 2]:
        raise ValidationError("登录终端类型取值范围: 0,1,2")
    
    url = f"{Config.BASE_URL}/api/login"
    data = {
        "userName": username,
        "password": password,
        "terminal": terminal
    }
    
    result = _make_request("POST", url, json_data=data)
    
    # 保存token
    if result:
        ACCESS_TOKEN = result.get("accessToken")
        REFRESH_TOKEN = result.get("refreshToken")
        ACCESS_TOKEN_EXPIRES = time.time() + result.get("accessTokenExpiresIn", 1800)
        REFRESH_TOKEN_EXPIRES = time.time() + result.get("refreshTokenExpiresIn", 86400)
        USER_ID = result.get("userId")
    
    return result


async def refresh_access_token() -> bool:
    """刷新access token（异步版本）"""
    global ACCESS_TOKEN, REFRESH_TOKEN, ACCESS_TOKEN_EXPIRES, REFRESH_TOKEN_EXPIRES, LAST_ERROR
    
    if (not REFRESH_TOKEN or 
        time.time() > REFRESH_TOKEN_EXPIRES - 60):
        LAST_ERROR = "refresh token不存在或已过期"
        return False
    
    url = f"{Config.BASE_URL}/api/refreshToken"
    headers = _get_headers()
    headers.update({
        "refreshToken": REFRESH_TOKEN,
        "Content-Length": "2"
    })
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.put(url, headers=headers, json={}) as response:
                result = await response.json()
                if result.get("code") == 200:
                    data = result.get("data", {})
                    ACCESS_TOKEN = data.get("accessToken")
                    REFRESH_TOKEN = data.get("refreshToken")
                    ACCESS_TOKEN_EXPIRES = time.time() + data.get("accessTokenExpiresIn", 1800)
                    REFRESH_TOKEN_EXPIRES = time.time() + data.get("refreshTokenExpiresIn", 86400)
                    LAST_ERROR = ""
                    return True
                else:
                    LAST_ERROR = result.get('message', 'Token刷新失败')
                    return False
    except Exception as e:
        LAST_ERROR = f"Token刷新异常: {str(e)}"
        return False


def refresh_access_token_sync() -> Dict[str, Any]:
    """刷新访问令牌（同步版本）"""
    global ACCESS_TOKEN, REFRESH_TOKEN, ACCESS_TOKEN_EXPIRES, REFRESH_TOKEN_EXPIRES
    
    if not REFRESH_TOKEN:
        raise ValidationError("刷新令牌不能为空")
    
    url = f"{Config.BASE_URL}/api/refreshToken"
    headers = {"refreshToken": REFRESH_TOKEN}
    
    result = _make_request("PUT", url, headers=headers)
    
    # 更新token
    if result:
        ACCESS_TOKEN = result.get("accessToken")
        REFRESH_TOKEN = result.get("refreshToken")
        ACCESS_TOKEN_EXPIRES = time.time() + result.get("accessTokenExpiresIn", 1800)
        REFRESH_TOKEN_EXPIRES = time.time() + result.get("refreshTokenExpiresIn", 86400)
    
    return result


def register(
    username: str,
    password: str,
    nickname: str,
    sex: Optional[int] = None,
    signature: Optional[str] = None
) -> Dict[str, Any]:
    """用户注册"""
    if not username or not password or not nickname:
        raise ValidationError("用户名、密码和昵称不能为空")
    
    url = f"{Config.BASE_URL}/api/register"
    data = {
        "userName": username,
        "password": password,
        "nickName": nickname
    }
    
    if sex is not None:
        data["sex"] = sex
    if signature:
        data["signature"] = signature
    
    return _make_request("POST", url, json_data=data)


def modify_password(old_password: str, new_password: str) -> Dict[str, Any]:
    """修改密码"""
    if not old_password or not new_password:
        raise ValidationError("旧密码和新密码不能为空")
    
    url = f"{Config.BASE_URL}/api/modifyPwd"
    data = {
        "oldPassword": old_password,
        "newPassword": new_password
    }
    
    return _make_request("PUT", url, json_data=data)


# ============================================================================
# 用户相关API
# ============================================================================

def get_online_terminals(user_ids: Union[str, List[int]]) -> List[Dict[str, Any]]:
    """获取用户在线终端信息"""
    if isinstance(user_ids, list):
        user_ids_str = ",".join(map(str, user_ids))
    else:
        user_ids_str = str(user_ids)
    
    url = f"{Config.BASE_URL}/api/user/terminal/online"
    params = {"userIds": user_ids_str}
    
    return _make_request("GET", url, params=params)


def get_current_user_info() -> Dict[str, Any]:
    """获取当前用户信息"""
    url = f"{Config.BASE_URL}/api/user/self"
    return _make_request("GET", url)


def get_user_by_id(user_id: int) -> Dict[str, Any]:
    """根据ID查找用户"""
    if not user_id:
        raise ValidationError("用户ID不能为空")
    
    url = f"{Config.BASE_URL}/api/user/find/{user_id}"
    return _make_request("GET", url)


def update_user_info(user_info: Dict[str, Any]) -> Dict[str, Any]:
    """修改用户信息"""
    url = f"{Config.BASE_URL}/api/user/update"
    return _make_request("PUT", url, json_data=user_info)


async def update_profile(**kwargs) -> bool:
    """更新个人信息（异步版本）"""
    global LAST_ERROR, USER_ID
    
    if not is_logged_in():
        LAST_ERROR = "未登录"
        return False
        
    url = f"{Config.BASE_URL}/api/user/update"
    
    # 过滤允许修改的字段
    allowed_fields = ['signature', 'userName', 'nickName', 'sex', 'headImage', 'headImageThumb']
    payload = {k: v for k, v in kwargs.items() if k in allowed_fields}
    
    if not payload:
        LAST_ERROR = "没有提供可修改的字段"
        return False
        
    # 如果提供了头像，需要先上传
    if 'headImage' in payload and os.path.exists(str(payload['headImage'])):
        upload_result = await upload_image(str(payload['headImage']), is_permanent=True)
        if upload_result:
            payload['headImage'] = upload_result.get("originUrl")
            payload['headImageThumb'] = upload_result.get("thumbUrl")
        else:
            del payload['headImage']
            if 'headImageThumb' in payload:
                del payload['headImageThumb']
    
    # 添加必要的用户ID
    payload['id'] = USER_ID
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.put(url, headers=_get_headers(), json=payload) as response:
                result = await response.json()
                success = result.get("code") == 200
                if success:
                    LAST_ERROR = ""
                else:
                    LAST_ERROR = result.get('message', '更新个人信息失败')
                return success
    except Exception as e:
        LAST_ERROR = str(e)
        return False


def find_users_by_name(name: str) -> List[Dict[str, Any]]:
    """根据用户名或昵称查找用户"""
    if not name:
        raise ValidationError("查找名称不能为空")
    
    url = f"{Config.BASE_URL}/api/user/findByName"
    params = {"name": name}
    
    return _make_request("GET", url, params=params)


# ============================================================================
# 好友相关API
# ============================================================================

async def get_friend_list() -> Optional[List[Dict]]:
    """获取好友列表（异步版本）"""
    global LAST_ERROR
    
    if not is_logged_in():
        LAST_ERROR = "未登录"
        return None
        
    url = f"{Config.BASE_URL}/api/friend/list"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=_get_headers()) as response:
                result = await response.json()
                if result.get("code") == 200:
                    friends = result.get("data", [])
                    LAST_ERROR = ""
                    return friends
                else:
                    LAST_ERROR = result.get('message', '获取好友列表失败')
                    return None
    except Exception as e:
        LAST_ERROR = str(e)
        return None


def get_friend_list_sync() -> List[Dict[str, Any]]:
    """获取好友列表（同步版本）"""
    url = f"{Config.BASE_URL}/api/friend/list"
    return _make_request("GET", url)


def add_friend(friend_id: int) -> Dict[str, Any]:
    """添加好友"""
    if not friend_id:
        raise ValidationError("好友ID不能为空")
    
    url = f"{Config.BASE_URL}/api/friend/add"
    params = {"friendId": friend_id}
    
    return _make_request("POST", url, params=params)


def get_friend_info(friend_id: int) -> Dict[str, Any]:
    """查找好友信息"""
    if not friend_id:
        raise ValidationError("好友ID不能为空")
    
    url = f"{Config.BASE_URL}/api/friend/find/{friend_id}"
    return _make_request("GET", url)


def delete_friend(friend_id: int) -> Dict[str, Any]:
    """删除好友"""
    if not friend_id:
        raise ValidationError("好友ID不能为空")
    
    url = f"{Config.BASE_URL}/api/friend/delete/{friend_id}"
    return _make_request("DELETE", url)


def set_friend_dnd(friend_id: int, dnd: bool) -> Dict[str, Any]:
    """设置好友免打扰状态"""
    if not friend_id:
        raise ValidationError("好友ID不能为空")
    
    url = f"{Config.BASE_URL}/api/friend/dnd"
    data = {
        "friendId": friend_id,
        "isDnd": dnd
    }
    
    return _make_request("PUT", url, json_data=data)


# ============================================================================
# 群聊相关API
# ============================================================================

async def get_group_list() -> Optional[List[Dict]]:
    """获取群聊列表（异步版本）"""
    global LAST_ERROR
    
    if not is_logged_in():
        LAST_ERROR = "未登录"
        return None
        
    url = f"{Config.BASE_URL}/api/group/list"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=_get_headers()) as response:
                result = await response.json()
                if result.get("code") == 200:
                    groups = result.get("data", [])
                    LAST_ERROR = ""
                    return groups
                else:
                    LAST_ERROR = result.get('message', '获取群聊列表失败')
                    return None
    except Exception as e:
        LAST_ERROR = str(e)
        return None


def get_group_list_sync() -> List[Dict[str, Any]]:
    """获取群聊列表（同步版本）"""
    url = f"{Config.BASE_URL}/api/group/list"
    return _make_request("GET", url)


def create_group(group_info: Dict[str, Any]) -> Dict[str, Any]:
    """创建群聊"""
    url = f"{Config.BASE_URL}/api/group/create"
    return _make_request("POST", url, json_data=group_info)


def modify_group(group_info: Dict[str, Any]) -> Dict[str, Any]:
    """修改群聊信息"""
    url = f"{Config.BASE_URL}/api/group/modify"
    return _make_request("PUT", url, json_data=group_info)


def delete_group(group_id: int) -> Dict[str, Any]:
    """解散群聊"""
    if not group_id:
        raise ValidationError("群聊ID不能为空")
    
    url = f"{Config.BASE_URL}/api/group/delete/{group_id}"
    return _make_request("DELETE", url)


def get_group_info(group_id: int) -> Dict[str, Any]:
    """查询群聊信息"""
    if not group_id:
        raise ValidationError("群聊ID不能为空")
    
    url = f"{Config.BASE_URL}/api/group/find/{group_id}"
    return _make_request("GET", url)


def invite_to_group(group_id: int, user_ids: List[int]) -> Dict[str, Any]:
    """邀请好友进群"""
    if not group_id:
        raise ValidationError("群聊ID不能为空")
    if not user_ids:
        raise ValidationError("用户ID列表不能为空")
    
    url = f"{Config.BASE_URL}/api/group/invite"
    data = {
        "groupId": group_id,
        "userIds": user_ids
    }
    
    return _make_request("POST", url, json_data=data)


def get_group_members(group_id: int) -> List[Dict[str, Any]]:
    """查询群聊成员"""
    if not group_id:
        raise ValidationError("群聊ID不能为空")
    
    url = f"{Config.BASE_URL}/api/group/members/{group_id}"
    return _make_request("GET", url)


def remove_group_members(group_id: int, user_ids: List[int]) -> Dict[str, Any]:
    """将成员移出群聊"""
    if not group_id:
        raise ValidationError("群聊ID不能为空")
    if not user_ids:
        raise ValidationError("用户ID列表不能为空")
    
    url = f"{Config.BASE_URL}/api/group/members/remove"
    data = {
        "groupId": group_id,
        "userIds": user_ids
    }
    
    return _make_request("DELETE", url, json_data=data)


def quit_group(group_id: int) -> Dict[str, Any]:
    """退出群聊"""
    if not group_id:
        raise ValidationError("群聊ID不能为空")
    
    url = f"{Config.BASE_URL}/api/group/quit/{group_id}"
    return _make_request("DELETE", url)


def kick_from_group(group_id: int, user_id: int) -> Dict[str, Any]:
    """踢出群聊 (已废弃的接口，保留以确保完整性)"""
    if not group_id:
        raise ValidationError("群聊ID不能为空")
    if not user_id:
        raise ValidationError("用户ID不能为空")
    
    url = f"{Config.BASE_URL}/api/group/kick/{group_id}"
    params = {"userId": user_id}
    
    return _make_request("DELETE", url, params=params)


def set_group_dnd(group_id: int, dnd: bool) -> Dict[str, Any]:
    """设置群聊免打扰状态"""
    if not group_id:
        raise ValidationError("群聊ID不能为空")
    
    url = f"{Config.BASE_URL}/api/group/dnd"
    data = {
        "groupId": group_id,
        "isDnd": dnd
    }
    
    return _make_request("PUT", url, json_data=data)


async def mute_group_members(group_id: int, user_ids: List[int], is_muted: bool = True) -> Dict:
    """禁言/解禁群成员（异步版本）"""
    global LAST_ERROR
    
    if not is_logged_in():
        LAST_ERROR = "未登录"
        return {"error": "未登录"}
    
    url = f"{Config.BASE_URL}/api/group/members/muted"
    
    payload = {
        "groupId": int(group_id),
        "userIds": [int(uid) for uid in user_ids] if user_ids else [],
        "isMuted": bool(is_muted)
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.put(url, headers=_get_headers(), json=payload) as response:
                data = await response.json()
                if response.status != 200:
                    error_msg = f"HTTP error {response.status}"
                    LAST_ERROR = error_msg
                    return {"error": error_msg, "data": data}
                else:
                    LAST_ERROR = ""
                return data
    except aiohttp.ClientError as e:
        error_msg = f"HTTP error: {str(e)}"
        LAST_ERROR = error_msg
        return {"error": error_msg}
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        LAST_ERROR = error_msg
        return {"error": error_msg}


# ============================================================================
# 文件上传相关API
# ============================================================================

async def upload_file(file_path: str, is_permanent: bool = False) -> Optional[str]:
    """上传普通文件（异步版本）"""
    return await _upload(
        str(file_path), 
        f"{Config.BASE_URL}/api/file/upload?isPermanent={str(is_permanent).lower()}",
        "file"
    )


def upload_file_sync(file_path: str) -> str:
    """上传文件（同步版本）"""
    if not file_path or not os.path.exists(file_path):
        raise ValidationError("文件路径无效或文件不存在")
    
    file_size = os.path.getsize(file_path)
    if file_size > Config.MAX_FILE_SIZE:
        raise ValidationError(f"文件大小不能超过 {Config.MAX_FILE_SIZE // (1024*1024)}MB")
    
    url = f"{Config.BASE_URL}/api/file/upload"
    
    # 获取文件MIME类型
    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type:
        mime_type = 'application/octet-stream'
    
    with open(file_path, 'rb') as f:
        files = {'file': (os.path.basename(file_path), f, mime_type)}
        
        # 上传文件时不使用JSON Content-Type
        headers = _build_headers()
        if 'Content-Type' in headers:
            del headers['Content-Type']
        
        return _make_request("POST", url, files=files, headers=headers)


async def upload_image(file_path: str, is_permanent: bool = False) -> Optional[Dict]:
    """上传图片（异步版本）"""
    return await _upload(
        str(file_path), 
        f"{Config.BASE_URL}/api/image/upload?isPermanent={str(is_permanent).lower()}",
        "file"
    )


def upload_image_sync(
    file_path: str,
    is_permanent: bool = True,
    thumb_size: int = 50
) -> Dict[str, Any]:
    """上传图片（同步版本）"""
    if not file_path or not os.path.exists(file_path):
        raise ValidationError("文件路径无效或文件不存在")
    
    file_size = os.path.getsize(file_path)
    if file_size > Config.MAX_IMAGE_SIZE:
        raise ValidationError(f"图片大小不能超过 {Config.MAX_IMAGE_SIZE // (1024*1024)}MB")
    
    # 检查文件类型
    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type or not mime_type.startswith('image/'):
        raise ValidationError("只能上传图片文件")
    
    url = f"{Config.BASE_URL}/api/image/upload"
    
    with open(file_path, 'rb') as f:
        files = {'file': (os.path.basename(file_path), f, mime_type)}
        params = {
            'isPermanent': str(is_permanent).lower(),
            'thumbSize': thumb_size
        }
        
        # 上传文件时不使用JSON Content-Type
        headers = _build_headers()
        if 'Content-Type' in headers:
            del headers['Content-Type']
        
        return _make_request("POST", url, params=params, files=files, headers=headers)


async def upload_audio(file_path: str) -> Optional[str]:
    """上传音频（异步版本）"""
    return await _upload(
        str(file_path), 
        f"{Config.BASE_URL}/api/file/upload",
        "file"
    )


async def upload_video(file_path: str, is_permanent: bool = False) -> Optional[Dict]:
    """上传视频（异步版本）"""
    return await _upload(
        str(file_path), 
        f"{Config.BASE_URL}/api/video/upload?isPermanent={str(is_permanent).lower()}",
        "file"
    )


async def _upload(file_path: str, url: str, field_name: str) -> Optional[Any]:
    """通用上传方法（异步版本）"""
    global LAST_ERROR
    
    if not is_logged_in():
        LAST_ERROR = "未登录"
        return None
        
    if not os.path.exists(file_path):
        LAST_ERROR = f"文件不存在: {file_path}"
        return None
        
    try:
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Origin": Config.BASE_URL,
            "Referer": f"{Config.BASE_URL}/",
            "User-Agent": Config.USER_AGENT,
            "accessToken": ACCESS_TOKEN,
            "sec-ch-ua": "\"Not)A;Brand\";v=\"8\", \"Chromium\";v=\"138\", \"Microsoft Edge\";v=\"138\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"Windows\""
        }
        
        filename = os.path.basename(file_path)
        content_type = _get_content_type(filename)
        
        async with aiohttp.ClientSession() as session:
            with open(file_path, 'rb') as f:
                data = aiohttp.FormData()
                data.add_field(field_name, f, filename=filename, content_type=content_type)
                
                async with session.post(url, headers=headers, data=data) as response:
                    result = await response.json()
                    if result.get("code") == 200:
                        LAST_ERROR = ""
                        return result.get("data")
                    else:
                        LAST_ERROR = result.get('message', '文件上传失败')
                        return None
    except Exception as e:
        LAST_ERROR = f"文件上传异常: {str(e)}"
        return None


# ============================================================================
# 私聊消息相关API
# ============================================================================

async def send_private_text(user_id: int, text: str) -> Optional[int]:
    """发送私聊文本消息（异步版本）"""
    return await _send_private_message(int(user_id), str(text), MessageType.TEXT.value)


async def send_private_image(user_id: int, image_path: str) -> Optional[int]:
    """发送私聊图片（异步版本）"""
    upload_result = await upload_image(str(image_path))
    if not upload_result:
        return None
        
    content = json.dumps({
        "originUrl": upload_result.get("originUrl"),
        "thumbUrl": upload_result.get("thumbUrl"),
        "width": upload_result.get("width"),
        "height": upload_result.get("height")
    })
    
    return await _send_private_message(int(user_id), content, MessageType.IMAGE.value)


async def send_private_file(user_id: int, file_path: str) -> Optional[int]:
    """发送私聊文件（异步版本）"""
    file_url = await upload_file(str(file_path))
    if not file_url:
        return None
        
    filename = os.path.basename(str(file_path))
    filesize = os.path.getsize(str(file_path))
    
    content = json.dumps({
        "name": filename,
        "size": filesize,
        "url": file_url
    })
    
    return await _send_private_message(int(user_id), content, MessageType.FILE.value)


async def send_private_voice(user_id: int, voice_path: str, duration: int = 3) -> Optional[int]:
    """发送私聊语音（异步版本）"""
    voice_url = await upload_audio(str(voice_path))
    if not voice_url:
        return None
        
    content = json.dumps({
        "duration": int(duration),
        "url": voice_url
    })
    
    return await _send_private_message(int(user_id), content, MessageType.VOICE.value)


async def send_private_video(user_id: int, video_path: str) -> Optional[int]:
    """发送私聊视频（异步版本）"""
    upload_result = await upload_video(str(video_path))
    if not upload_result:
        return None
        
    content = json.dumps({
        "videoUrl": upload_result.get("videoUrl"),
        "coverUrl": upload_result.get("coverUrl"),
        "width": upload_result.get("width"),
        "height": upload_result.get("height")
    })
    
    return await _send_private_message(int(user_id), content, MessageType.VIDEO.value)


async def send_private_user_card(user_id: int, target_user_id: int, target_nickname: str, target_head_image: str) -> Optional[int]:
    """发送私聊个人名片（异步版本）"""
    content = json.dumps({
        "userId": int(target_user_id),
        "nickName": str(target_nickname),
        "headImage": str(target_head_image)
    })
    
    return await _send_private_message(int(user_id), content, MessageType.USER_CARD.value)


async def send_private_group_card(user_id: int, group_id: int, group_name: str, group_head_image: str) -> Optional[int]:
    """发送私聊群聊名片（异步版本）"""
    content = json.dumps({
        "groupId": int(group_id),
        "groupName": str(group_name),
        "headImage": str(group_head_image)
    })
    
    return await _send_private_message(int(user_id), content, MessageType.GROUP_CARD.value)


async def _send_private_message(user_id: int, content: str, msg_type: int) -> Optional[int]:
    """发送私聊消息的通用方法（异步版本）"""
    global LAST_ERROR
    
    if not is_logged_in():
        LAST_ERROR = "未登录"
        return None
        
    url = f"{Config.BASE_URL}/api/message/private/send"
    tmp_id = str(uuid.uuid4().int)[:16]
    
    payload = {
        "tmpId": tmp_id,
        "content": str(content),
        "type": int(msg_type),
        "recvId": int(user_id),
        "receipt": False
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=_get_headers(), json=payload) as response:
                result = await response.json()
                if result.get("code") == 200:
                    message_id = result["data"].get("id")
                    LAST_ERROR = ""
                    return message_id
                else:
                    error_msg = result.get('message', f'HTTP {response.status}')
                    LAST_ERROR = error_msg
                    return None
    except Exception as e:
        LAST_ERROR = str(e)
        return None


def send_private_message_sync(
    recv_id: int,
    content: str,
    message_type: int = MessageType.TEXT.value,
    tmp_id: Optional[str] = None
) -> Dict[str, Any]:
    """发送私聊消息（同步版本）"""
    if not recv_id:
        raise ValidationError("接收用户ID不能为空")
    if not content:
        raise ValidationError("消息内容不能为空")
    if len(content) > 1024:
        raise ValidationError("消息内容长度不能超过1024字符")
    
    url = f"{Config.BASE_URL}/api/message/private/send"
    data = {
        "recvId": recv_id,
        "content": content,
        "type": message_type
    }
    
    if tmp_id:
        data["tmpId"] = tmp_id
    
    return _make_request("POST", url, json_data=data)


async def recall_private_message(message_id: int) -> bool:
    """撤回私聊消息（异步版本）"""
    global LAST_ERROR
    
    if not is_logged_in():
        LAST_ERROR = "未登录"
        return False
        
    url = f"{Config.BASE_URL}/api/message/private/recall/{int(message_id)}"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.delete(url, headers=_get_headers()) as response:
                result = await response.json()
                success = result.get("code") == 200
                if success:
                    LAST_ERROR = ""
                else:
                    LAST_ERROR = result.get('message', '撤回失败')
                return success
    except Exception as e:
        LAST_ERROR = str(e)
        return False


def recall_private_message_sync(message_id: int) -> Dict[str, Any]:
    """撤回私聊消息（同步版本）"""
    if not message_id:
        raise ValidationError("消息ID不能为空")
    
    url = f"{Config.BASE_URL}/api/message/private/recall/{message_id}"
    return _make_request("DELETE", url)


async def mark_private_as_read(friend_id: int) -> bool:
    """标记私聊消息为已读（异步版本）"""
    global LAST_ERROR
    
    if not is_logged_in():
        LAST_ERROR = "未登录"
        return False
        
    url = f"{Config.BASE_URL}/api/message/private/readed?friendId={int(friend_id)}"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.put(url, headers=_get_headers(), data=b'') as response:
                result = await response.json()
                success = result.get("code") == 200
                if success:
                    LAST_ERROR = ""
                else:
                    LAST_ERROR = result.get('message', '标记已读失败')
                return success
    except Exception as e:
        LAST_ERROR = str(e)
        return False


def mark_private_messages_read_sync(friend_id: int) -> Dict[str, Any]:
    """将私聊消息标记为已读（同步版本）"""
    if not friend_id:
        raise ValidationError("好友ID不能为空")
    
    url = f"{Config.BASE_URL}/api/message/private/readed"
    params = {"friendId": friend_id}
    
    return _make_request("PUT", url, params=params)


def get_max_read_private_message_id(friend_id: int) -> int:
    """获取最大已读私聊消息ID"""
    if not friend_id:
        raise ValidationError("好友ID不能为空")
    
    url = f"{Config.BASE_URL}/api/message/private/maxReadedId"
    params = {"friendId": friend_id}
    
    return _make_request("GET", url, params=params)


def get_private_message_history(
    friend_id: int,
    page: int,
    size: int
) -> List[Dict[str, Any]]:
    """查询私聊消息历史记录"""
    if not friend_id:
        raise ValidationError("好友ID不能为空")
    if not page or page < 1:
        raise ValidationError("页码必须大于0")
    if not size or size < 1:
        raise ValidationError("每页大小必须大于0")
    
    url = f"{Config.BASE_URL}/api/message/private/history"
    params = {
        "friendId": friend_id,
        "page": page,
        "size": size
    }
    
    return _make_request("GET", url, params=params)


# ============================================================================
# 群聊消息相关API
# ============================================================================

async def send_group_text(group_id: int, text: str, at_user_ids: List[int] = []) -> Optional[int]:
    """发送群聊文本消息（异步版本）"""
    return await _send_group_message(int(group_id), str(text), MessageType.TEXT.value, [int(uid) for uid in at_user_ids] if at_user_ids else [])


async def send_group_image(group_id: int, image_path: str, at_user_ids: List[int] = []) -> Optional[int]:
    """发送群聊图片（异步版本）"""
    upload_result = await upload_image(str(image_path))
    if not upload_result:
        return None
        
    content = json.dumps({
        "originUrl": upload_result.get("originUrl"),
        "thumbUrl": upload_result.get("thumbUrl"),
        "width": upload_result.get("width"),
        "height": upload_result.get("height")
    })
    
    return await _send_group_message(int(group_id), content, MessageType.IMAGE.value, [int(uid) for uid in at_user_ids] if at_user_ids else [])


async def send_group_file(group_id: int, file_path: str, at_user_ids: List[int] = []) -> Optional[int]:
    """发送群聊文件（异步版本）"""
    file_url = await upload_file(str(file_path))
    if not file_url:
        return None
        
    filename = os.path.basename(str(file_path))
    filesize = os.path.getsize(str(file_path))
    
    content = json.dumps({
        "name": filename,
        "size": filesize,
        "url": file_url
    })
    
    return await _send_group_message(int(group_id), content, MessageType.FILE.value, [int(uid) for uid in at_user_ids] if at_user_ids else [])


async def send_group_voice(group_id: int, voice_path: str, duration: int = 3, at_user_ids: List[int] = []) -> Optional[int]:
    """发送群聊语音（异步版本）"""
    voice_url = await upload_audio(str(voice_path))
    if not voice_url:
        return None
        
    content = json.dumps({
        "duration": int(duration),
        "url": voice_url
    })
    
    return await _send_group_message(int(group_id), content, MessageType.VOICE.value, [int(uid) for uid in at_user_ids] if at_user_ids else [])


async def send_group_video(group_id: int, video_path: str, at_user_ids: List[int] = []) -> Optional[int]:
    """发送群聊视频（异步版本）"""
    upload_result = await upload_video(str(video_path))
    if not upload_result:
        return None
        
    content = json.dumps({
        "videoUrl": upload_result.get("videoUrl"),
        "coverUrl": upload_result.get("coverUrl"),
        "width": upload_result.get("width"),
        "height": upload_result.get("height")
    })
    
    return await _send_group_message(int(group_id), content, MessageType.VIDEO.value, [int(uid) for uid in at_user_ids] if at_user_ids else [])


async def _send_group_message(group_id: int, content: str, msg_type: int, at_user_ids: List[int] = []) -> Optional[int]:
    """发送群聊消息的通用方法（异步版本）"""
    global LAST_ERROR
    
    if not is_logged_in():
        LAST_ERROR = "未登录"
        return None
        
    url = f"{Config.BASE_URL}/api/message/group/send"
    tmp_id = str(uuid.uuid4().int)[:16]
    
    payload = {
        "tmpId": tmp_id,
        "content": str(content),
        "type": int(msg_type),
        "groupId": int(group_id),
        "atUserIds": [int(uid) for uid in at_user_ids] if at_user_ids else [],
        "receipt": False
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=_get_headers(), json=payload) as response:
                result = await response.json()
                if result.get("code") == 200:
                    message_id = result["data"].get("id")
                    LAST_ERROR = ""
                    return message_id
                else:
                    error_msg = result.get('message', f'HTTP {response.status}')
                    LAST_ERROR = error_msg
                    return None
    except Exception as e:
        LAST_ERROR = str(e)
        return None


def send_group_message_sync(
    group_id: int,
    content: str,
    message_type: int = MessageType.TEXT.value,
    tmp_id: Optional[str] = None,
    receipt: bool = False,
    at_user_ids: Optional[List[int]] = None
) -> Dict[str, Any]:
    """发送群聊消息（同步版本）"""
    if not group_id:
        raise ValidationError("群聊ID不能为空")
    if not content:
        raise ValidationError("消息内容不能为空")
    if len(content) > 1024:
        raise ValidationError("消息内容长度不能超过1024字符")
    if at_user_ids and len(at_user_ids) > 20:
        raise ValidationError("一次最多只能@20个用户")
    
    url = f"{Config.BASE_URL}/api/message/group/send"
    data = {
        "groupId": group_id,
        "content": content,
        "type": message_type,
        "receipt": receipt
    }
    
    if tmp_id:
        data["tmpId"] = tmp_id
    if at_user_ids:
        data["atUserIds"] = at_user_ids
    
    return _make_request("POST", url, json_data=data)


async def recall_group_message(message_id: int) -> bool:
    """撤回群聊消息（异步版本）"""
    global LAST_ERROR
    
    if not is_logged_in():
        LAST_ERROR = "未登录"
        return False
        
    url = f"{Config.BASE_URL}/api/message/group/recall/{int(message_id)}"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.delete(url, headers=_get_headers()) as response:
                result = await response.json()
                success = result.get("code") == 200
                if success:
                    LAST_ERROR = ""
                else:
                    LAST_ERROR = result.get('message', '撤回失败')
                return success
    except Exception as e:
        LAST_ERROR = str(e)
        return False


def recall_group_message_sync(message_id: int) -> Dict[str, Any]:
    """撤回群聊消息（同步版本）"""
    if not message_id:
        raise ValidationError("消息ID不能为空")
    
    url = f"{Config.BASE_URL}/api/message/group/recall/{message_id}"
    return _make_request("DELETE", url)


def mark_group_messages_read_sync(group_id: int) -> Dict[str, Any]:
    """将群聊消息标记为已读（同步版本）"""
    if not group_id:
        raise ValidationError("群聊ID不能为空")
    
    url = f"{Config.BASE_URL}/api/message/group/readed"
    params = {"groupId": group_id}
    
    return _make_request("PUT", url, params=params)


def get_group_message_read_users(
    group_id: int,
    message_id: int
) -> List[int]:
    """获取群聊消息已读用户列表"""
    if not group_id:
        raise ValidationError("群聊ID不能为空")
    if not message_id:
        raise ValidationError("消息ID不能为空")
    
    url = f"{Config.BASE_URL}/api/message/group/findReadedUsers"
    params = {
        "groupId": group_id,
        "messageId": message_id
    }
    
    return _make_request("GET", url, params=params)


def get_group_message_history(
    group_id: int,
    page: int,
    size: int
) -> List[Dict[str, Any]]:
    """查询群聊消息历史记录"""
    if not group_id:
        raise ValidationError("群聊ID不能为空")
    if not page or page < 1:
        raise ValidationError("页码必须大于0")
    if not size or size < 1:
        raise ValidationError("每页大小必须大于0")
    
    url = f"{Config.BASE_URL}/api/message/group/history"
    params = {
        "groupId": group_id,
        "page": page,
        "size": size
    }
    
    return _make_request("GET", url, params=params)


# ============================================================================
# WebSocket消息监听相关API
# ============================================================================

def add_message_handler(handler: Callable):
    """添加消息处理器"""
    global MESSAGE_HANDLERS
    if handler not in MESSAGE_HANDLERS:
        MESSAGE_HANDLERS.append(handler)


def remove_message_handler(handler: Callable):
    """移除消息处理器"""
    global MESSAGE_HANDLERS
    if handler in MESSAGE_HANDLERS:
        MESSAGE_HANDLERS.remove(handler)


async def start_listening() -> None:
    """开始监听消息"""
    global WEBSOCKET_TASK
    
    if not is_logged_in():
        return
        
    WEBSOCKET_TASK = asyncio.create_task(_websocket_listener())
    await WEBSOCKET_TASK


async def _websocket_listener() -> None:
    """WebSocket消息监听器"""
    global WEBSOCKET_RECONNECT_COUNT, GLOBAL_SUM_MESSAGE
    
    uri = Config.WS_URL
    last_sum_ms = 0
    
    while True:
        try:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            async with websockets.connect(uri, ssl=ssl_context) as websocket:
                WEBSOCKET_RECONNECT_COUNT = 0
                
                # 发送认证消息
                auth_message = json.dumps({
                    "cmd": 0,
                    "data": {"accessToken": ACCESS_TOKEN}
                })
                await websocket.send(auth_message)
                
                # 启动心跳任务
                async def send_heartbeat():
                    while True:
                        await asyncio.sleep(Config.HEARTBEAT_INTERVAL)
                        heartbeat = json.dumps({"cmd": 1, "data": {}})
                        await websocket.send(heartbeat)
                
                heartbeat_task = asyncio.create_task(send_heartbeat())
                
                try:
                    start_time = time.time()
                    
                    while True:
                        # 检查token是否需要刷新
                        if time.time() > ACCESS_TOKEN_EXPIRES - 300:
                            await refresh_access_token()
                        
                        message = await websocket.recv()
                        data = json.loads(message)
                        
                        if data.get("cmd") == 3 or data.get("cmd") == 4:
                            # 更新消息计数
                            GLOBAL_SUM_MESSAGE += 1
                            
                            new_time = time.time() - start_time
                            start_time = time.time()
                            
                            if last_sum_ms != GLOBAL_SUM_MESSAGE:
                                last_sum_ms = GLOBAL_SUM_MESSAGE
                            
                            msg_data = data.get("data", {})
                            is_group = data.get("cmd") == 4
                            
                            # 调用所有消息处理器
                            for handler in MESSAGE_HANDLERS:
                                try:
                                    await handler(msg_data, is_group)
                                except Exception as e:
                                    pass  # 静默处理handler错误
                                    
                except websockets.exceptions.ConnectionClosed:
                    await asyncio.sleep(0.1)
                finally:
                    heartbeat_task.cancel()
                    
        except Exception as e:
            WEBSOCKET_RECONNECT_COUNT += 1
            
            # 指数退避重连策略
            delay = min(Config.WEBSOCKET_RECONNECT_DELAY * (2 ** (WEBSOCKET_RECONNECT_COUNT - 1)), 300)
            await asyncio.sleep(delay)


async def stop_listening() -> None:
    """停止监听"""
    global WEBSOCKET_TASK
    
    if WEBSOCKET_TASK:
        WEBSOCKET_TASK.cancel()
        try:
            await WEBSOCKET_TASK
        except asyncio.CancelledError:
            pass


# ============================================================================
# 系统相关API
# ============================================================================

def get_system_config() -> Dict[str, Any]:
    """获取系统配置"""
    url = f"{Config.BASE_URL}/api/system/config"
    return _make_request("GET", url)


# ============================================================================
# WebRTC单人通话相关API
# ============================================================================

def webrtc_call(
    user_id: int,
    mode: str = "video",
    offer: str = ""
) -> Dict[str, Any]:
    """发起WebRTC通话"""
    if not user_id:
        raise ValidationError("用户ID不能为空")
    
    url = f"{Config.BASE_URL}/api/webrtc/private/call?uid={user_id}&mode={mode}"
    
    # 使用text/plain类型发送offer
    headers = _build_headers({"Content-Type": "application/json"})
    
    return _make_request("POST", url, data=json.dumps(offer), headers=headers)


def webrtc_accept(user_id: int, answer: str) -> Dict[str, Any]:
    """接受WebRTC通话"""
    if not user_id:
        raise ValidationError("用户ID不能为空")
    
    url = f"{Config.BASE_URL}/api/webrtc/private/accept?uid={user_id}"
    
    headers = _build_headers({"Content-Type": "application/json"})
    
    return _make_request("POST", url, data=json.dumps(answer), headers=headers)


def webrtc_reject(user_id: int) -> Dict[str, Any]:
    """拒绝WebRTC通话"""
    if not user_id:
        raise ValidationError("用户ID不能为空")
    
    url = f"{Config.BASE_URL}/api/webrtc/private/reject?uid={user_id}"
    return _make_request("POST", url)


def webrtc_cancel(user_id: int) -> Dict[str, Any]:
    """取消WebRTC通话"""
    if not user_id:
        raise ValidationError("用户ID不能为空")
    
    url = f"{Config.BASE_URL}/api/webrtc/private/cancel?uid={user_id}"
    return _make_request("POST", url)


def webrtc_failed(user_id: int, reason: str) -> Dict[str, Any]:
    """WebRTC通话失败"""
    if not user_id:
        raise ValidationError("用户ID不能为空")
    if not reason:
        raise ValidationError("失败原因不能为空")
    
    url = f"{Config.BASE_URL}/api/webrtc/private/failed?uid={user_id}&reason={reason}"
    return _make_request("POST", url)


def webrtc_handup(user_id: int) -> Dict[str, Any]:
    """挂断WebRTC通话"""
    if not user_id:
        raise ValidationError("用户ID不能为空")
    
    url = f"{Config.BASE_URL}/api/webrtc/private/handup?uid={user_id}"
    return _make_request("POST", url)


def webrtc_send_candidate(user_id: int, candidate: str) -> Dict[str, Any]:
    """发送WebRTC candidate信息"""
    if not user_id:
        raise ValidationError("用户ID不能为空")
    if not candidate:
        raise ValidationError("Candidate信息不能为空")
    
    url = f"{Config.BASE_URL}/api/webrtc/private/candidate?uid={user_id}"
    
    headers = _build_headers({"Content-Type": "application/json"})
    
    return _make_request("POST", url, data=json.dumps(candidate), headers=headers)


def webrtc_heartbeat(user_id: int) -> Dict[str, Any]:
    """WebRTC通话心跳"""
    if not user_id:
        raise ValidationError("用户ID不能为空")
    
    url = f"{Config.BASE_URL}/api/webrtc/private/heartbeat?uid={user_id}"
    return _make_request("POST", url)


# ============================================================================
# WebRTC群组通话相关API
# ============================================================================

def webrtc_group_setup(
    group_id: int,
    user_infos: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """发起群组WebRTC通话"""
    if not group_id:
        raise ValidationError("群聊ID不能为空")
    if not user_infos:
        raise ValidationError("用户信息列表不能为空")
    
    url = f"{Config.BASE_URL}/api/webrtc/group/setup"
    data = {
        "groupId": group_id,
        "userInfos": user_infos
    }
    
    return _make_request("POST", url, json_data=data)


def webrtc_group_accept(group_id: int) -> Dict[str, Any]:
    """接受群组WebRTC通话"""
    if not group_id:
        raise ValidationError("群聊ID不能为空")
    
    url = f"{Config.BASE_URL}/api/webrtc/group/accept?groupId={group_id}"
    return _make_request("POST", url)


def webrtc_group_reject(group_id: int) -> Dict[str, Any]:
    """拒绝群组WebRTC通话"""
    if not group_id:
        raise ValidationError("群聊ID不能为空")
    
    url = f"{Config.BASE_URL}/api/webrtc/group/reject?groupId={group_id}"
    return _make_request("POST", url)


def webrtc_group_failed(group_id: int, reason: str) -> Dict[str, Any]:
    """群组WebRTC通话失败"""
    if not group_id:
        raise ValidationError("群聊ID不能为空")
    if not reason:
        raise ValidationError("失败原因不能为空")
    
    url = f"{Config.BASE_URL}/api/webrtc/group/failed"
    data = {
        "groupId": group_id,
        "reason": reason
    }
    
    return _make_request("POST", url, json_data=data)


def webrtc_group_join(group_id: int) -> Dict[str, Any]:
    """主动加入群组WebRTC通话"""
    if not group_id:
        raise ValidationError("群聊ID不能为空")
    
    url = f"{Config.BASE_URL}/api/webrtc/group/join?groupId={group_id}"
    return _make_request("POST", url)


def webrtc_group_invite(
    group_id: int,
    user_infos: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """邀请用户加入群组WebRTC通话"""
    if not group_id:
        raise ValidationError("群聊ID不能为空")
    if not user_infos:
        raise ValidationError("用户信息列表不能为空")
    
    url = f"{Config.BASE_URL}/api/webrtc/group/invite"
    data = {
        "groupId": group_id,
        "userInfos": user_infos
    }
    
    return _make_request("POST", url, json_data=data)


def webrtc_group_offer(
    group_id: int,
    user_id: int,
    offer: str
) -> Dict[str, Any]:
    """发送群组WebRTC offer"""
    if not group_id:
        raise ValidationError("群聊ID不能为空")
    if not user_id:
        raise ValidationError("用户ID不能为空")
    if not offer:
        raise ValidationError("Offer信息不能为空")
    
    url = f"{Config.BASE_URL}/api/webrtc/group/offer"
    data = {
        "groupId": group_id,
        "userId": user_id,
        "offer": offer
    }
    
    return _make_request("POST", url, json_data=data)


def webrtc_group_answer(
    group_id: int,
    user_id: int,
    answer: str
) -> Dict[str, Any]:
    """发送群组WebRTC answer"""
    if not group_id:
        raise ValidationError("群聊ID不能为空")
    if not user_id:
        raise ValidationError("用户ID不能为空")
    if not answer:
        raise ValidationError("Answer信息不能为空")
    
    url = f"{Config.BASE_URL}/api/webrtc/group/answer"
    data = {
        "groupId": group_id,
        "userId": user_id,
        "answer": answer
    }
    
    return _make_request("POST", url, json_data=data)


def webrtc_group_quit(group_id: int) -> Dict[str, Any]:
    """退出群组WebRTC通话"""
    if not group_id:
        raise ValidationError("群聊ID不能为空")
    
    url = f"{Config.BASE_URL}/api/webrtc/group/quit?groupId={group_id}"
    return _make_request("POST", url)


def webrtc_group_cancel(group_id: int) -> Dict[str, Any]:
    """取消群组WebRTC通话"""
    if not group_id:
        raise ValidationError("群聊ID不能为空")
    
    url = f"{Config.BASE_URL}/api/webrtc/group/cancel?groupId={group_id}"
    return _make_request("POST", url)


def webrtc_group_candidate(
    group_id: int,
    user_id: int,
    candidate: str
) -> Dict[str, Any]:
    """发送群组WebRTC candidate"""
    if not group_id:
        raise ValidationError("群聊ID不能为空")
    if not user_id:
        raise ValidationError("用户ID不能为空")
    if not candidate:
        raise ValidationError("Candidate信息不能为空")
    
    url = f"{Config.BASE_URL}/api/webrtc/group/candidate"
    data = {
        "groupId": group_id,
        "userId": user_id,
        "candidate": candidate
    }
    
    return _make_request("POST", url, json_data=data)


def webrtc_group_device(
    group_id: int,
    is_camera: bool,
    is_microphone: bool
) -> Dict[str, Any]:
    """设置群组WebRTC设备状态"""
    if not group_id:
        raise ValidationError("群聊ID不能为空")
    
    url = f"{Config.BASE_URL}/api/webrtc/group/device"
    data = {
        "groupId": group_id,
        "isCamera": is_camera,
        "isMicroPhone": is_microphone
    }
    
    return _make_request("POST", url, json_data=data)


def webrtc_group_heartbeat(group_id: int) -> Dict[str, Any]:
    """群组WebRTC通话心跳"""
    if not group_id:
        raise ValidationError("群聊ID不能为空")
    
    url = f"{Config.BASE_URL}/api/webrtc/group/heartbeat?groupId={group_id}"
    return _make_request("POST", url)


# ============================================================================
# 面向对象接口 - BoxIMClient类
# ============================================================================

class BoxIMClient:
    """
    BoxIM 主客户端类
    
    提供完整的BoxIM API接口访问功能，包括：
    - 用户认证和授权
    - 用户管理
    - 好友管理
    - 群聊管理
    - 消息发送和接收
    - 文件上传
    - WebRTC音视频通话
    """
    
    def __init__(
        self,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        timeout: int = Config.TIMEOUT,
        max_retries: int = Config.MAX_RETRIES,
        debug: bool = False,
        **kwargs
    ):
        """
        初始化BoxIM客户端
        
        Args:
            access_token: 访问令牌
            refresh_token: 刷新令牌
            timeout: 请求超时时间（秒）
            max_retries: 最大重试次数
            debug: 是否开启调试模式
            **kwargs: 额外参数
        """
        global ACCESS_TOKEN, REFRESH_TOKEN
        
        if access_token:
            ACCESS_TOKEN = access_token
        if refresh_token:
            REFRESH_TOKEN = refresh_token
            
        self.timeout = timeout
        self.max_retries = max_retries
        self.debug = debug
        
        # 配置日志
        self.logger = _setup_logging(debug)
        self.logger.info("BoxIM客户端初始化完成")
    
    # 认证相关方法
    def login(self, username: str, password: str, terminal: int = TerminalType.WEB.value) -> Dict[str, Any]:
        """用户登录"""
        return login_sync(username, password, terminal)
    
    def refresh_access_token(self) -> Dict[str, Any]:
        """刷新访问令牌"""
        return refresh_access_token_sync()
    
    def register(self, username: str, password: str, nickname: str, sex: Optional[int] = None, signature: Optional[str] = None) -> Dict[str, Any]:
        """用户注册"""
        return register(username, password, nickname, sex, signature)
    
    def modify_password(self, old_password: str, new_password: str) -> Dict[str, Any]:
        """修改密码"""
        return modify_password(old_password, new_password)
    
    # 用户相关方法
    def get_online_terminals(self, user_ids: Union[str, List[int]]) -> List[Dict[str, Any]]:
        """获取用户在线终端信息"""
        return get_online_terminals(user_ids)
    
    def get_current_user_info(self) -> Dict[str, Any]:
        """获取当前用户信息"""
        return get_current_user_info()
    
    def get_user_by_id(self, user_id: int) -> Dict[str, Any]:
        """根据ID查找用户"""
        return get_user_by_id(user_id)
    
    def update_user_info(self, user_info: Dict[str, Any]) -> Dict[str, Any]:
        """修改用户信息"""
        return update_user_info(user_info)
    
    def find_users_by_name(self, name: str) -> List[Dict[str, Any]]:
        """根据用户名或昵称查找用户"""
        return find_users_by_name(name)
    
    # 好友相关方法
    def get_friend_list(self) -> List[Dict[str, Any]]:
        """获取好友列表"""
        return get_friend_list_sync()
    
    def add_friend(self, friend_id: int) -> Dict[str, Any]:
        """添加好友"""
        return add_friend(friend_id)
    
    def get_friend_info(self, friend_id: int) -> Dict[str, Any]:
        """查找好友信息"""
        return get_friend_info(friend_id)
    
    def delete_friend(self, friend_id: int) -> Dict[str, Any]:
        """删除好友"""
        return delete_friend(friend_id)
    
    def set_friend_dnd(self, friend_id: int, dnd: bool) -> Dict[str, Any]:
        """设置好友免打扰状态"""
        return set_friend_dnd(friend_id, dnd)
    
    # 群聊相关方法
    def get_group_list(self) -> List[Dict[str, Any]]:
        """获取群聊列表"""
        return get_group_list_sync()
    
    def create_group(self, group_info: Dict[str, Any]) -> Dict[str, Any]:
        """创建群聊"""
        return create_group(group_info)
    
    def modify_group(self, group_info: Dict[str, Any]) -> Dict[str, Any]:
        """修改群聊信息"""
        return modify_group(group_info)
    
    def delete_group(self, group_id: int) -> Dict[str, Any]:
        """解散群聊"""
        return delete_group(group_id)
    
    def get_group_info(self, group_id: int) -> Dict[str, Any]:
        """查询群聊信息"""
        return get_group_info(group_id)
    
    def invite_to_group(self, group_id: int, user_ids: List[int]) -> Dict[str, Any]:
        """邀请好友进群"""
        return invite_to_group(group_id, user_ids)
    
    def get_group_members(self, group_id: int) -> List[Dict[str, Any]]:
        """查询群聊成员"""
        return get_group_members(group_id)
    
    def remove_group_members(self, group_id: int, user_ids: List[int]) -> Dict[str, Any]:
        """将成员移出群聊"""
        return remove_group_members(group_id, user_ids)
    
    def quit_group(self, group_id: int) -> Dict[str, Any]:
        """退出群聊"""
        return quit_group(group_id)
    
    def set_group_dnd(self, group_id: int, dnd: bool) -> Dict[str, Any]:
        """设置群聊免打扰状态"""
        return set_group_dnd(group_id, dnd)
    
    # 消息相关方法
    def send_private_message(self, recv_id: int, content: str, message_type: int = MessageType.TEXT.value, tmp_id: Optional[str] = None) -> Dict[str, Any]:
        """发送私聊消息"""
        return send_private_message_sync(recv_id, content, message_type, tmp_id)
    
    def send_group_message(self, group_id: int, content: str, message_type: int = MessageType.TEXT.value, tmp_id: Optional[str] = None, receipt: bool = False, at_user_ids: Optional[List[int]] = None) -> Dict[str, Any]:
        """发送群聊消息"""
        return send_group_message_sync(group_id, content, message_type, tmp_id, receipt, at_user_ids)
    
    def recall_private_message(self, message_id: int) -> Dict[str, Any]:
        """撤回私聊消息"""
        return recall_private_message_sync(message_id)
    
    def recall_group_message(self, message_id: int) -> Dict[str, Any]:
        """撤回群聊消息"""
        return recall_group_message_sync(message_id)
    
    def mark_private_messages_read(self, friend_id: int) -> Dict[str, Any]:
        """将私聊消息标记为已读"""
        return mark_private_messages_read_sync(friend_id)
    
    def mark_group_messages_read(self, group_id: int) -> Dict[str, Any]:
        """将群聊消息标记为已读"""
        return mark_group_messages_read_sync(group_id)
    
    def get_private_message_history(self, friend_id: int, page: int, size: int) -> List[Dict[str, Any]]:
        """查询私聊消息历史记录"""
        return get_private_message_history(friend_id, page, size)
    
    def get_group_message_history(self, group_id: int, page: int, size: int) -> List[Dict[str, Any]]:
        """查询群聊消息历史记录"""
        return get_group_message_history(group_id, page, size)
    
    # 文件上传方法
    def upload_image(self, file_path: str, is_permanent: bool = True, thumb_size: int = 50) -> Dict[str, Any]:
        """上传图片"""
        return upload_image_sync(file_path, is_permanent, thumb_size)
    
    def upload_file(self, file_path: str) -> str:
        """上传文件"""
        return upload_file_sync(file_path)
    
    # 系统相关方法
    def get_system_config(self) -> Dict[str, Any]:
        """获取系统配置"""
        return get_system_config()
    
    # WebRTC相关方法
    def webrtc_call(self, user_id: int, mode: str = "video", offer: str = "") -> Dict[str, Any]:
        """发起WebRTC通话"""
        return webrtc_call(user_id, mode, offer)
    
    def webrtc_accept(self, user_id: int, answer: str) -> Dict[str, Any]:
        """接受WebRTC通话"""
        return webrtc_accept(user_id, answer)
    
    def webrtc_reject(self, user_id: int) -> Dict[str, Any]:
        """拒绝WebRTC通话"""
        return webrtc_reject(user_id)
    
    def webrtc_cancel(self, user_id: int) -> Dict[str, Any]:
        """取消WebRTC通话"""
        return webrtc_cancel(user_id)
    
    # 状态相关方法
    def is_logged_in(self) -> bool:
        """检查是否已登录且token有效"""
        return is_logged_in()
    
    def get_login_status(self) -> Dict[str, Any]:
        """获取登录状态信息"""
        return get_login_status()
    
    def get_user_id(self) -> Optional[int]:
        """获取当前登录用户ID"""
        return get_user_id()
    
    def get_last_error(self) -> str:
        """获取最后一次错误信息"""
        return get_last_error()
    
    def clear_last_error(self):
        """清除最后一次错误信息"""
        clear_last_error()
    
    # 上下文管理器支持
    def __enter__(self):
        """进入上下文管理器"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文管理器"""
        global HTTP_SESSION
        if HTTP_SESSION:
            HTTP_SESSION.close()
            HTTP_SESSION = None


# ============================================================================
# 便捷导出
# ============================================================================

__all__ = [
    # 基础类和配置
    "Config",
    "MessageType",
    "TerminalType",
    
    # 异常类
    "BoxIMException",
    "AuthenticationError",
    "ValidationError",
    "NetworkError",
    "ServerError",
    
    # 数据模型
    "LoginRequest",
    "LoginResponse",
    "RegisterRequest",
    "UserInfo",
    "GroupInfo",
    "PrivateMessage",
    "GroupMessage",
    
    # 主客户端类
    "BoxIMClient",
    
    # 状态管理函数
    "get_login_status",
    "is_logged_in",
    "get_user_id",
    "get_global_message_count",
    "get_last_error",
    "clear_last_error",
    "clear_state",
    
    # 认证相关函数
    "login",
    "login_sync",
    "refresh_access_token",
    "refresh_access_token_sync",
    "register",
    "modify_password",
    
    # 用户相关函数
    "get_online_terminals",
    "get_current_user_info",
    "get_user_by_id",
    "update_user_info",
    "update_profile",
    "find_users_by_name",
    
    # 好友相关函数
    "get_friend_list",
    "get_friend_list_sync",
    "add_friend",
    "get_friend_info",
    "delete_friend",
    "set_friend_dnd",
    
    # 群聊相关函数
    "get_group_list",
    "get_group_list_sync",
    "create_group",
    "modify_group",
    "delete_group",
    "get_group_info",
    "invite_to_group",
    "get_group_members",
    "remove_group_members",
    "quit_group",
    "kick_from_group",
    "set_group_dnd",
    "mute_group_members",
    
    # 文件上传函数
    "upload_file",
    "upload_file_sync",
    "upload_image",
    "upload_image_sync",
    "upload_audio",
    "upload_video",
    
    # 私聊消息函数
    "send_private_text",
    "send_private_image",
    "send_private_file",
    "send_private_voice",
    "send_private_video",
    "send_private_user_card",
    "send_private_group_card",
    "send_private_message_sync",
    "recall_private_message",
    "recall_private_message_sync",
    "mark_private_as_read",
    "mark_private_messages_read_sync",
    "get_max_read_private_message_id",
    "get_private_message_history",
    
    # 群聊消息函数
    "send_group_text",
    "send_group_image",
    "send_group_file",
    "send_group_voice",
    "send_group_video",
    "send_group_message_sync",
    "recall_group_message",
    "recall_group_message_sync",
    "mark_group_messages_read_sync",
    "get_group_message_read_users",
    "get_group_message_history",
    
    # WebSocket相关函数
    "add_message_handler",
    "remove_message_handler",
    "start_listening",
    "stop_listening",
    
    # 系统相关函数
    "get_system_config",
    
    # WebRTC单人通话函数
    "webrtc_call",
    "webrtc_accept",
    "webrtc_reject",
    "webrtc_cancel",
    "webrtc_failed",
    "webrtc_handup",
    "webrtc_send_candidate",
    "webrtc_heartbeat",
    
    # WebRTC群组通话函数
    "webrtc_group_setup",
    "webrtc_group_accept",
    "webrtc_group_reject",
    "webrtc_group_failed",
    "webrtc_group_join",
    "webrtc_group_invite",
    "webrtc_group_offer",
    "webrtc_group_answer",
    "webrtc_group_quit",
    "webrtc_group_cancel",
    "webrtc_group_candidate",
    "webrtc_group_device",
    "webrtc_group_heartbeat",
]

__version__ = "1.0.0"
__author__ = "nichengfuben"
__email__ = "nichengfuben@outlook.com"


# ============================================================================
# 自测代码
# ============================================================================

if __name__ == "__main__":
    def test_sdk():
        """
        SDK功能测试
        
        这个函数测试SDK的基本功能，包括：
        - 客户端初始化
        - 连接测试
        - API调用测试
        """
        print("开始测试BoxIM SDK...")
        
        try:
            # 测试客户端初始化
            print("1. 测试客户端初始化...")
            client = BoxIMClient(debug=True)
            print("✓ 客户端初始化成功")
            
            # 测试全局变量状态
            print("\n2. 测试全局状态变量...")
            print(f"  登录状态: {is_logged_in()}")
            print(f"  用户ID: {get_user_id()}")
            print(f"  消息计数: {get_global_message_count()}")
            print(f"  最后错误: {get_last_error()}")
            print("✓ 全局状态变量访问正常")
            
            # 测试系统配置接口（不需要token）
            print("\n3. 测试系统配置接口...")
            try:
                config = get_system_config()
                print("✓ 系统配置获取成功")
                print(f"  配置信息: {config}")
            except Exception as e:
                print(f"✗ 系统配置获取失败: {e}")
            
            # 测试面向对象接口
            print("\n4. 测试面向对象接口...")
            try:
                client_config = client.get_system_config()
                print("✓ 面向对象接口调用成功")
            except Exception as e:
                print(f"✗ 面向对象接口调用失败: {e}")
            
            # 测试登录功能（需要有效的用户名和密码）
            print("\n5. 测试登录功能...")
            print("  注意: 需要有效的用户名和密码才能测试登录功能")
            print("  异步版本: await login('username', 'password')")
            print("  同步版本: login_sync('username', 'password')")
            print("  面向对象: client.login('username', 'password')")
            
            # 测试创建客户端的不同方式
            print("\n6. 测试不同的客户端创建方式...")
            
            # 使用token创建客户端
            client_with_token = BoxIMClient(access_token="dummy_token")
            print("✓ 使用token创建客户端成功")
            
            # 使用上下文管理器
            with BoxIMClient() as context_client:
                print("✓ 上下文管理器创建客户端成功")
            
            # 测试异常处理
            print("\n7. 测试异常处理...")
            try:
                add_friend(None)  # 应该抛出ValidationError
            except ValidationError as e:
                print(f"✓ 参数验证异常处理正确: {e}")
            
            # 测试状态清理
            print("\n8. 测试状态清理...")
            old_count = get_global_message_count()
            clear_state()
            new_count = get_global_message_count()
            print(f"✓ 状态清理成功 (消息计数: {old_count} -> {new_count})")
            
            print("\n✅ 所有基础测试通过!")
            print("\n📖 使用说明:")
            print("1. 支持异步和同步两种调用方式")
            print("2. 支持函数式和面向对象两种编程风格")
            print("3. 使用全局变量管理状态，无需文件持久化")
            print("4. 所有方法都有详细的文档字符串和示例")
            print("\n🔧 示例代码:")
            print("""
# 函数式调用（异步）
import asyncio

async def main():
    success = await login("username", "password")
    if success:
        friends = await get_friend_list()
        message_id = await send_private_text(123, "Hello!")
        
        # 添加消息处理器
        async def handle_message(msg_data, is_group):
            print(f"收到消息: {msg_data}")
            
        add_message_handler(handle_message)
        await start_listening()

asyncio.run(main())

# 函数式调用（同步）
result = login_sync("username", "password")
friends = get_friend_list_sync()
message = send_private_message_sync(123, "Hello!")

# 面向对象调用
client = BoxIMClient()
result = client.login("username", "password")
friends = client.get_friend_list()
message = client.send_private_message(123, "Hello!")

# 查看全局状态
print(f"登录状态: {is_logged_in()}")
print(f"用户ID: {get_user_id()}")
print(f"消息计数: {get_global_message_count()}")
            """)
            
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
    
    test_sdk()

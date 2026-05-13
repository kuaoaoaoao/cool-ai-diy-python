# ============================================================
# 安全认证模块
# ============================================================
#
# 本模块提供身份认证和授权相关的安全功能
#
# 主要功能：
# 1. 密码哈希与验证（bcrypt）
# 2. JWT令牌创建与验证
# 3. 当前用户获取
# 4. 权限检查
#
# 安全最佳实践：
# - 密码使用bcrypt加密，不可逆
# - JWT签名使用HS256算法
# - Token设置合理的过期时间
#
# Author: CoolAI Team
# Date: 2026-05-13
# ============================================================

from datetime import datetime, timedelta, timezone
from typing import Optional
from functools import wraps

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings


# ============================================================
# 密码加密工具
# ============================================================

# 创建密码哈希上下文
# bcrypt 是目前推荐的密码哈希算法
# scheme="bcrypt" 指定使用bcrypt算法
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """
    对密码进行哈希加密
    
    使用bcrypt算法对密码进行单向加密
    加密后的哈希值可以安全存储，即使泄露也无法还原原始密码
    
    Args:
        password: 明文密码
        
    Returns:
        str: 加密后的密码哈希
        
    Example:
        hashed = hash_password("my_secret_password")
        # 结果类似: $2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5lWq4.X6CvH3e
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证密码是否正确
    
    将用户输入的明文密码与存储的哈希值进行比对
    bcrypt的verify方法是常量时间比较，防止时序攻击
    
    Args:
        plain_password: 用户输入的明文密码
        hashed_password: 数据库中存储的哈希密码
        
    Returns:
        bool: 密码是否匹配
    """
    return pwd_context.verify(plain_password, hashed_password)


# ============================================================
# JWT令牌工具
# ============================================================

# JWT Bearer认证方案
security = HTTPBearer()


def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    创建JWT访问令牌
    
    生成签名的JWT令牌，包含用户信息
    令牌可以被验证其真实性和有效性
    
    Args:
        data: 要编码到token中的数据字典
        expires_delta: 令牌过期时间增量，None则使用默认配置
        
    Returns:
        str: 编码后的JWT字符串
        
    Example:
        token = create_access_token(
            data={"sub": "user123", "role": "admin"},
            expires_delta=timedelta(hours=24)
        )
    """
    # 复制数据字典，避免修改原始数据
    to_encode = data.copy()
    
    # 设置过期时间
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.APP_ACCESS_TOKEN_EXPIRE_MINUTES
        )
    
    # 添加过期时间字段
    to_encode.update({"exp": expire})
    
    # 添加创建时间字段（可选，用于调试）
    to_encode.update({"iat": datetime.now(timezone.utc)})
    
    # 使用HS256算法签名
    encoded_jwt = jwt.encode(
        claims=to_encode,
        key=settings.APP_SECRET_KEY,
        algorithm=settings.APP_JWT_ALGORITHM
    )
    
    return encoded_jwt


def verify_token(token: str) -> Optional[dict]:
    """
    验证并解码JWT令牌
    
    验证令牌签名和过期时间，解码后返回payload
    
    Args:
        token: JWT令牌字符串
        
    Returns:
        dict: 解码后的payload数据，验证失败返回None
        
    Note:
        - 如果token已过期或签名不合法，返回None
        - 生产环境中应该抛出异常而不是静默返回None
    """
    try:
        # 解码并验证token
        payload = jwt.decode(
            token,
            key=settings.APP_SECRET_KEY,
            algorithms=[settings.APP_JWT_ALGORITHM]
        )
        return payload
    except JWTError:
        # 令牌过期或签名不合法
        return None


def decode_token(token: str) -> dict:
    """
    解码JWT令牌（不解试验证）
    
    仅解码不验证，用于需要查看token内容但不验证的场景
    
    Args:
        token: JWT令牌字符串
        
    Returns:
        dict: 解码后的payload数据
        
    Raises:
        JWTError: token格式错误
    """
    return jwt.decode(
        token,
        key=settings.APP_SECRET_KEY,
        algorithms=[settings.APP_JWT_ALGORITHM],
        options={"verify_signature": False}  # 不验证签名
    )


# ============================================================
# 用户认证依赖
# ============================================================

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    获取当前登录用户
    
    这是一个FastAPI依赖函数
    从请求头中提取JWT令牌，验证后返回当前用户信息
    
    Args:
        credentials: HTTP认证凭证，由FastAPI自动注入
        
    Returns:
        dict: 用户信息字典，包含user_id、username等
        
    Raises:
        HTTPException: 认证失败时抛出异常
        
    Example:
        @app.get("/profile")
        async def get_profile(current_user: dict = Depends(get_current_user)):
            return {"user": current_user}
    """
    # 从Bearer token中提取token字符串
    token = credentials.credentials
    
    # 验证token
    payload = verify_token(token)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌无效或已过期",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 提取用户标识
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌格式错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 返回用户信息
    return {
        "user_id": user_id,
        "username": payload.get("username"),
        "role": payload.get("role", "user"),
    }


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        HTTPBearer(auto_error=False)
    )
) -> Optional[dict]:
    """
    获取当前用户（可选）
    
    与get_current_user类似，但不会强制要求登录
    用于某些可选认证的接口
    
    Args:
        credentials: HTTP认证凭证，可能为None
        
    Returns:
        Optional[dict]: 用户信息，未登录则返回None
    """
    if credentials is None:
        return None
    
    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None


# ============================================================
# 权限检查装饰器
# ============================================================

def require_role(*allowed_roles):
    """
    角色权限检查装饰器
    
    用于限制接口只能被特定角色的用户访问
    
    Args:
        *allowed_roles: 允许访问的角色列表
        
    Returns:
        装饰器函数
        
    Example:
        @app.delete("/users/{user_id}")
        @require_role("admin")
        async def delete_user(user_id: str):
            ...
        
        # 多角色
        @require_role("admin", "superuser")
        async def sensitive_operation():
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(
            *args,
            current_user: dict = Depends(get_current_user),
            **kwargs
        ):
            user_role = current_user.get("role", "user")
            
            if user_role not in allowed_roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"需要以下角色之一: {', '.join(allowed_roles)}"
                )
            
            return await func(*args, current_user=current_user, **kwargs)
        
        return wrapper
    return decorator


def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """
    管理员权限检查
    
    快捷函数，用于检查当前用户是否为管理员
    
    Args:
        current_user: 当前用户信息
        
    Returns:
        dict: 用户信息（验证通过时）
        
    Raises:
        HTTPException: 非管理员用户抛出403异常
    """
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    return current_user


# ============================================================
# Token刷新机制
# ============================================================

def create_refresh_token(user_id: str) -> str:
    """
    创建刷新令牌
    
    刷新令牌的过期时间通常比访问令牌长
    用于在访问令牌过期后获取新的访问令牌
    
    Args:
        user_id: 用户ID
        
    Returns:
        str: 刷新令牌字符串
    """
    return create_access_token(
        data={
            "sub": user_id,
            "type": "refresh"  # 标记为刷新令牌
        },
        expires_delta=timedelta(days=30)  # 刷新令牌30天过期
    )


def verify_refresh_token(token: str) -> Optional[str]:
    """
    验证刷新令牌
    
    Args:
        token: 刷新令牌
        
    Returns:
        Optional[str]: 验证通过返回user_id，否则返回None
    """
    payload = verify_token(token)
    
    if payload is None:
        return None
    
    # 检查令牌类型
    if payload.get("type") != "refresh":
        return None
    
    return payload.get("sub")

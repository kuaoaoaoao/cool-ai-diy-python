# ============================================================
# 认证API路由
# ============================================================
#
# 本模块处理用户认证相关的API接口
#
# 主要功能：
# 1. 用户注册
# 2. 用户登录
# 3. 令牌刷新
# 4. 获取当前用户信息
#
# Author: CoolAI Team
# Date: 2026-05-13
# ============================================================

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    verify_refresh_token,
    get_current_user,
)
from app.core.config import settings
from app.models import User
from app.schemas import (
    UserCreate,
    UserLogin,
    UserResponse,
    TokenResponse,
)


# ============================================================
# 路由配置
# ============================================================

router = APIRouter(
    prefix="/auth",
    tags=["认证相关"],
    summary="用户认证接口",
)


# ============================================================
# 用户注册
# ============================================================

@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="用户注册",
    description="创建新用户账户",
)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    用户注册接口
    
    Args:
        user_data: 用户注册信息，包含用户名、邮箱、密码
        db: 数据库会话
        
    Returns:
        UserResponse: 创建的用户信息
        
    Raises:
        HTTPException: 用户名或邮箱已存在
    """
    # 检查用户名是否已存在
    stmt = select(User).where(User.username == user_data.username)
    result = await db.execute(stmt)
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已存在"
        )
    
    # 检查邮箱是否已存在
    stmt = select(User).where(User.email == user_data.email)
    result = await db.execute(stmt)
    existing_email = result.scalar_one_or_none()
    
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邮箱已被注册"
        )
    
    # 创建新用户
    # 密码需要哈希存储，保证安全性
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        password_hash=hash_password(user_data.password),
        full_name=user_data.full_name,
    )
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    return new_user


# ============================================================
# 用户登录
# ============================================================

@router.post(
    "/login",
    response_model=TokenResponse,
    summary="用户登录",
    description="使用用户名和密码登录，返回访问令牌",
)
async def login(
    login_data: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    """
    用户登录接口
    
    验证用户名和密码，成功则返回JWT令牌
    
    Args:
        login_data: 登录信息，包含用户名和密码
        db: 数据库会话
        
    Returns:
        TokenResponse: 包含access_token和refresh_token
        
    Raises:
        HTTPException: 用户名或密码错误
    """
    # 查找用户
    stmt = select(User).where(User.username == login_data.username)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误"
        )
    
    # 验证密码
    if not verify_password(login_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误"
        )
    
    # 检查账户是否激活
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账户已被禁用"
        )
    
    # 生成访问令牌
    # JWT payload中包含用户基本信息
    access_token = create_access_token(
        data={
            "sub": str(user.id),           # 用户ID
            "username": user.username,     # 用户名
            "role": user.role,              # 用户角色
        }
    )
    
    # 生成刷新令牌
    refresh_token = create_refresh_token(str(user.id))
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.APP_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


# ============================================================
# 刷新令牌
# ============================================================

@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="刷新令牌",
    description="使用刷新令牌获取新的访问令牌",
)
async def refresh_token(
    refresh_token: str,
    db: AsyncSession = Depends(get_db)
):
    """
    刷新访问令牌
    
    使用refresh_token获取新的access_token
    
    Args:
        refresh_token: 刷新令牌
        db: 数据库会话
        
    Returns:
        TokenResponse: 新的访问令牌
        
    Raises:
        HTTPException: 刷新令牌无效
    """
    # 验证刷新令牌
    user_id = verify_refresh_token(refresh_token)
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="刷新令牌无效或已过期"
        )
    
    # 查找用户
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在或账户已被禁用"
        )
    
    # 生成新的访问令牌
    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "username": user.username,
            "role": user.role,
        }
    )
    
    # 生成新的刷新令牌（一次性使用）
    new_refresh_token = create_refresh_token(str(user.id))
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=settings.APP_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


# ============================================================
# 获取当前用户信息
# ============================================================

@router.get(
    "/me",
    response_model=UserResponse,
    summary="获取当前用户",
    description="获取已登录用户的详细信息",
)
async def get_me(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取当前登录用户信息
    
    Args:
        current_user: 从JWT令牌解析出的用户信息
        db: 数据库会话
        
    Returns:
        UserResponse: 用户详细信息
    """
    # 从数据库获取最新用户信息
    stmt = select(User).where(User.id == current_user["user_id"])
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    return user

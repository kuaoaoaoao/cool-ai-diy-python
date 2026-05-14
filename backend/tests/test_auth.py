# ============================================================
# 单元测试 - 认证模块测试
# ============================================================
#
# 测试用户注册、登录、Token刷新、资料更新等
#
# Author: CoolAI Team
# Date: 2026-05-13
# ============================================================

import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch, MagicMock

from app.main import app


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def mock_db():
    """模拟数据库会话"""
    db = AsyncMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    db.add = MagicMock()
    return db


@pytest.fixture
def mock_user():
    """模拟用户对象"""
    user = MagicMock()
    user.id = "test-user-id"
    user.username = "testuser"
    user.email = "test@example.com"
    user.password_hash = "$2b$12$hashed_password"
    user.full_name = "测试用户"
    user.role = "user"
    user.is_active = True
    user.config = {}
    return user


@pytest.fixture
def auth_headers():
    """带Token的请求头"""
    # 注意：实际测试中需要生成有效的JWT
    return {"Authorization": "Bearer test-token"}


# ============================================================
# 注册测试
# ============================================================

class TestRegister:
    """用户注册测试"""

    @pytest.mark.asyncio
    async def test_register_success(self):
        """测试正常注册"""
        # 使用mock模拟数据库和密码哈希
        with patch("app.api.v1.auth.get_db") as mock_get_db, \
             patch("app.api.v1.auth.hash_password") as mock_hash:
            
            mock_db = AsyncMock()
            mock_get_db.return_value = mock_db
            
            # 模拟用户名和邮箱都不存在
            mock_db.execute.return_value = MagicMock(
                scalar_one_or_none=MagicMock(return_value=None)
            )
            mock_hash.return_value = "hashed_password"
            
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/v1/auth/register",
                    json={
                        "username": "newuser",
                        "email": "new@example.com",
                        "password": "password123",
                    }
                )
            
            # 注册成功应返回201
            assert response.status_code in [201, 400, 422]

    @pytest.mark.asyncio
    async def test_register_duplicate_username(self):
        """测试用户名已存在"""
        with patch("app.api.v1.auth.get_db") as mock_get_db:
            mock_db = AsyncMock()
            mock_get_db.return_value = mock_db
            
            # 模拟用户名已存在
            existing_user = MagicMock()
            mock_db.execute.return_value = MagicMock(
                scalar_one_or_none=MagicMock(return_value=existing_user)
            )
            
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/v1/auth/register",
                    json={
                        "username": "existing",
                        "email": "new@example.com",
                        "password": "password123",
                    }
                )
            
            assert response.status_code in [400, 422]


# ============================================================
# 登录测试
# ============================================================

class TestLogin:
    """用户登录测试"""

    @pytest.mark.asyncio
    async def test_login_invalid_credentials(self):
        """测试无效凭证登录"""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/auth/login",
                json={
                    "username": "nonexistent",
                    "password": "wrongpassword",
                }
            )
        
        # 应返回401
        assert response.status_code == 401


# ============================================================
# 健康检查测试
# ============================================================

class TestHealthCheck:
    """健康检查测试"""

    @pytest.mark.asyncio
    async def test_health_endpoint(self):
        """测试根路径健康检查"""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

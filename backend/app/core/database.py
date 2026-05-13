# ============================================================
# 数据库连接模块
# ============================================================
"""
本模块负责管理数据库连接和会话
使用SQLAlchemy 2.0的异步ORM进行数据库操作
"""

from typing import AsyncGenerator
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool, QueuePool

from app.core.config import settings


Base = declarative_base()


def create_engine_with_pool():
    """创建带连接池的异步数据库引擎"""
    pool_class = NullPool if settings.DEBUG else QueuePool
    
    engine = create_async_engine(
        settings.DATABASE_URL,
        poolclass=pool_class,
        pool_size=settings.DATABASE_POOL_SIZE if not settings.DEBUG else None,
        max_overflow=settings.DATABASE_MAX_OVERFLOW if not settings.DEBUG else None,
        echo=settings.DEBUG,
    )
    return engine


engine = create_engine_with_pool()


async_session_maker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话的依赖注入生成器"""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """上下文管理器方式获取数据库会话"""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """初始化数据库"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_db():
    """删除所有数据库表"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def check_db_connection() -> bool:
    """检查数据库连接是否正常"""
    try:
        async with async_session_maker() as session:
            await session.execute("SELECT 1")
            return True
    except Exception:
        return False

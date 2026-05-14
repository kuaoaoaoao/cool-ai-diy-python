# ============================================================
# 测试公共配置和fixtures
# ============================================================

import pytest
import os

# 设置测试环境变量（在导入app之前）
os.environ["DEBUG"] = "true"
os.environ["DATABASE_URL"] = "postgresql+asyncpg://test:test@localhost:5432/test_coolai"
os.environ["OPENAI_API_KEY"] = "test-key"
os.environ["APP_SECRET_KEY"] = "test-secret-key-for-testing"

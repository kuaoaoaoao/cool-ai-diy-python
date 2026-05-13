# ============================================================
# Dockerfile - CoolAI 后端服务
# ============================================================
#
# 基于Python 3.11的Docker镜像配置
# 用于构建后端服务的生产环境镜像
#
# 构建命令：
# docker build -t coolai-backend:latest .
#
# 运行命令：
# docker run -d -p 8000:8000 --env-file .env coolai-backend:latest
#
# Author: CoolAI Team
# Date: 2026-05-13
# ============================================================

# ============================================================
# 阶段1：构建阶段
# ============================================================

# 使用Python 3.11作为基础镜像
FROM python:3.11-slim as builder

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 设置工作目录
WORKDIR /app

# 安装构建依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装
COPY requirements.txt .

# 安装依赖
RUN pip install --no-cache-dir -r requirements.txt


# ============================================================
# 阶段2：运行阶段
# ============================================================

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai

WORKDIR /app

# 安装运行时依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# 复制已安装的包
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# 复制应用代码
COPY . .

# 创建数据目录
RUN mkdir -p /app/data/{uploads,tts_output,logs}

# 创建非root用户
RUN adduser --disabled-password --gecos "" appuser && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

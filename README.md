# CoolAI 智能业务平台

## 项目简介

CoolAI 是一个综合性的AI业务平台，基于主流技术栈构建，提供以下核心能力：

- 🤖 **AI Agent** - 智能代理，支持多种推理模式
- 📚 **RAG知识库** - 检索增强生成，支持文档问答
- 🔊 **TTS语音合成** - 文字转语音，多种音色可选
- 🎤 **声音克隆** - 个性化声音定制

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | React 18 + TypeScript + Ant Design |
| 后端 | Python FastAPI + LangChain |
| 数据库 | PostgreSQL + Redis |
| 向量库 | Milvus |
| 部署 | Docker + docker-compose |

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- Docker & Docker Compose

### 1. 克隆项目

```bash
git clone https://github.com/coolai/coolai.git
cd coolai
```

### 2. 配置环境变量

```bash
cp backend/.env.example backend/.env
# 编辑 .env 填写你的配置
```

### 3. 启动服务

```bash
# 启动所有服务
docker-compose up -d

# 或仅启动后端
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### 4. 访问应用

- 前端界面：http://localhost:3000
- API文档：http://localhost:8000/docs
- Grafana监控：http://localhost:3001

## 项目结构

```
coolAi/
├── backend/           # 后端项目
│   ├── app/           # 应用代码
│   │   ├── api/      # API路由
│   │   ├── core/     # 核心配置
│   │   ├── models/    # 数据模型
│   │   ├── schemas/   # Pydantic模式
│   │   └── services/  # 业务服务
│   └── requirements.txt
│
├── frontend/          # 前端项目
│   └── src/
│       ├── pages/     # 页面组件
│       ├── components/ # 公共组件
│       └── services/  # API服务
│
├── deploy/            # 部署配置
│   ├── docker/        # Docker配置
│   └── monitoring/    # 监控配置
│
└── docs/              # 文档
    ├── 需求文档.md
    └── 设计文档.md
```

## API文档

详细API文档请访问：http://localhost:8000/docs

主要接口：

| 模块 | 接口 |
|------|------|
| 认证 | POST /api/v1/auth/login |
| 对话 | POST /api/v1/chat/ |
| 知识库 | POST /api/v1/knowledge/bases |
| TTS | POST /api/v1/tts/synthesize |

## 开发指南

### 后端开发

```bash
cd backend

# 安装依赖
pip install -r requirements.txt

# 运行开发服务器
uvicorn app.main:app --reload

# 运行测试
pytest tests/
```

### 前端开发

```bash
cd frontend

# 安装依赖
npm install

# 运行开发服务器
npm run dev

# 构建生产版本
npm run build
```

## 监控

- Prometheus：http://localhost:9090
- Grafana：http://localhost:3001 (admin/admin)
- Alertmanager：http://localhost:9093

## License

MIT License

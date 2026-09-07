# JobCraft 求职助手

> AI 驱动的全流程求职管理平台，帮助求职者系统性管理求职各环节。

## 功能特性

- **经历卡管理** — 上传简历自动解析为结构化经历卡，支持手动编辑和 AI 润色
- **JD 深度分析** — 智能解析岗位要求，匹配度评分，生成能力差距报告
- **定制简历生成** — 根据岗位要求自动匹配经历卡，生成定制化 Markdown/HTML 简历
- **面试准备** — 按维度预测面试题，生成答题要点和参考话术
- **面试复盘** — 上传面试录音，AI 自动拆分 QA 对并生成详细复盘报告
- **求职仪表盘** — 统一管理所有投递记录，追踪各阶段进度

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.12 + FastAPI + LangGraph + MySQL + Redis |
| 前端 | React 18 + TypeScript + Vite + Ant Design |
| AI | 智谱 GLM-4-Flash (通过 OpenAI 兼容接口) |
| 部署 | Docker Compose (5 服务: mysql/redis/backend/frontend/worker) |

## 快速开始

### 环境要求

- Docker & Docker Compose
- Git

### 启动步骤

```bash
# 克隆项目
git clone https://github.com/Frangipanelu/jobcraft.git
cd jobcraft

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入你的智谱 API Key

# 启动所有服务
cd docker
docker compose up -d

# 访问应用
# 前端: http://localhost
# 后端 API: http://localhost:8000
# API 文档: http://localhost:8000/docs
```

### 本地开发

```bash
# 后端开发
uv sync
uv run uvicorn app.api.server:app --reload --port 8000

# 前端开发
cd frontend-jobcraft
npm install
npm run dev
```

## 项目结构

```
jobcraft/
├── app/                       # 后端主代码
│   ├── api/                   # FastAPI 路由
│   ├── agents/                # AI Agent 节点
│   ├── core/                  # 基础设施 (LLM, DB)
│   ├── schemas/               # Pydantic 数据模型
│   ├── tools/                 # 业务工具函数
│   └── workflows/             # LangGraph 工作流
├── frontend-jobcraft/         # React 前端
│   ├── src/
│   │   ├── api/               # API 调用封装
│   │   ├── components/        # UI 组件
│   │   ├── context/           # React Context (全局状态)
│   │   ├── types/             # TypeScript 类型定义
│   │   └── utils/             # 工具函数
│   └── package.json
├── docker/                    # Docker 配置
│   ├── docker-compose.yaml    # 服务编排
│   ├── Dockerfile.backend     # 后端镜像
│   └── Dockerfile.frontend    # 前端镜像
├── prompts/                   # LLM Prompt 模板 (版本化)
├── migrations/                # 数据库迁移脚本
├── tests/                     # 测试套件
├── docs/                      # 设计文档与决策记录
├── scripts/                   # 工具脚本
├── AGENTS.md                  # AI 协作行为规范
├── PRODUCT.md                 # 产品需求边界
├── ARCHITECTURE.md            # 技术架构约束
├── PROGRESS.md                # 进度追踪
└── pyproject.toml             # Python 依赖配置
```

## 核心数据流

```
用户上传简历 → 经历卡抽取 → AI 结构化 (STAR)
                              ↓
用户输入 JD → JD 深度分析 → 能力匹配评分
                              ↓
                      选择经历卡 → 生成定制简历
                              ↓
                      面试准备 → 面试复盘
```

## 开发规范

### 代码提交

```bash
# 后端代码质量检查
uv run ruff check --fix .
uv run ruff format .
uv run pytest tests/ -q

# 前端代码质量检查
cd frontend-jobcraft
npm run build
```

### Commit 规范

```
feat: 新功能
fix: 修复 bug
refactor: 重构
docs: 文档更新
chore: 杂项
```

## License

MIT

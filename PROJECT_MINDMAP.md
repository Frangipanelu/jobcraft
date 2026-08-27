# JobCraft 求职助手 · 项目结构思维导图

```
JobCraft/
├── 📋 项目文档
│   ├── README.md                    # 项目说明、快速开始、API 概览
│   ├── AGENTS.md                    # AI 协作行为规范、红线、代码规范
│   ├── PRODUCT.md                   # 产品愿景、MVP 边界、验收标准
│   ├── ARCHITECTURE.md              # 技术架构、目录结构、数据模型
│   ├── PROGRESS.md                  # 版本进度与历史决策（v0.2-v0.12）
│   └── docs/
│       ├── CODE_REVIEW.md           # 代码审查清单与问题记录
│       ├── UI_DESIGN.md             # 设计系统文档（极简编辑风格）
│       └── design-decisions/        # 7 篇设计决策文档
│           ├── 02-岗位分析模块设计.md
│           ├── 03-缺口分析与润色建议合并设计.md
│           ├── 04-全流程数据架构设计.md
│           ├── 05-求职系统CRM化重构设计.md
│           ├── 06-面试准备增强与手动补录设计.md
│           ├── 07-主页卡片UI顺序与引导设计.md
│           └── 08-Agent-Workbench-重构方案.md
│
├── 🐍 后端 (Python 3.12)
│   ├── app/
│   │   ├── api/                    # Controller 层：FastAPI 路由与入口
│   │   │   ├── server.py           # 主应用：路由注册、参数校验、统一响应
│   │   │   ├── monitor.py          # 健康检查与监控
│   │   │   └── context.py          # 请求上下文管理
│   │   │
│   │   ├── workflows/              # Workflow 层：LangGraph StateGraph 编排
│   │   │   ├── base.py             # Workflow 基类
│   │   │   ├── interview_review_flow.py  # 面试复盘 Multi-Agent（6节点）
│   │   │   ├── job_analysis_flow.py      # 岗位分析（step1/step2/旧版兼容）
│   │   │   ├── question_table_flow.py    # 问题表生成（3节点）
│   │   │   ├── interview_prep_flow.py    # 面试准备
│   │   │   └── extract_flow.py           # 经历卡抽取/标签/简历解析/回填
│   │   │
│   │   ├── agents/                 # Agent 层：可复用 LLM 调用节点（单一职责）
│   │   │   ├── base_agent.py       # Agent 节点基类
│   │   │   ├── structured_caller.py # LLM 结构化调用封装
│   │   │   │
│   │   │   ├── 🎤 面试复盘相关
│   │   │   │   ├── router_agent.py      # 问题分类路由
│   │   │   │   ├── tech_analyzer.py     # 技术类问题分析
│   │   │   │   ├── soft_analyzer.py     # 行为/业务类问题分析
│   │   │   │   └── gate_agent.py        # 质检/一致性检查
│   │   │   │
│   │   │   ├── 🔍 岗位分析相关
│   │   │   │   ├── jd_ats_agent.py      # JD ATS 解析
│   │   │   │   ├── ats_recommend_agent.py # Step1: ATS+推荐卡（合并一次LLM）
│   │   │   │   ├── score_match_agent.py # 卡片语义评分
│   │   │   │   ├── gap_polish_agent.py  # Step2: 缺口+润色
│   │   │   │   └── sug_agent.py         # 旧版优化建议
│   │   │   │
│   │   │   ├── 📋 经历卡相关
│   │   │   │   ├── extract_agent.py     # 结构化抽取/简历解析/标签推荐
│   │   │   │   ├── question_table_agent.py # 问题表意图识别
│   │   │   │   └── question_intent_agent.py # 解析预览意图识别
│   │   │   │
│   │   │   ├── 🏢 公司相关
│   │   │   │   └── company_research_agent.py # 公司调研（Tavily+缓存）
│   │   │   │
│   │   │   └── 🎤 面试准备相关
│   │   │       └── interview_prep_agent.py # 面试逐字稿生成
│   │   │
│   │   ├── tools/                  # Tool 层：纯函数（无 LLM 调用）
│   │   │   ├── db_tools.py         # 数据库 CRUD（所有表操作）
│   │   │   ├── llm_json.py         # LLM 底层调用封装（唯一允许LLM的工具）
│   │   │   ├── interview_review.py # 规则引擎 + prompt 构建
│   │   │   ├── interview_pre.py    # 面试准备 prompt 构建 + DB 读取
│   │   │   ├── jobcraft_analyze.py # 本地匹配纯函数（compute_match等）
│   │   │   ├── jobcraft_resume.py  # 简历生成编排
│   │   │   ├── jobcraft_resume_gen.py # Markdown 简历模板（无 LLM）
│   │   │   ├── upload_file_read_tool.py # 文件读取
│   │   │   └── tavily_tool.py      # 网络搜索
│   │   │
│   │   ├── schemas/                # Pydantic 数据模型
│   │   │   └── jobcraft.py         # 所有 Schema 定义
│   │   │
│   │   ├── core/                   # 核心基础设施
│   │   │   └── llm.py              # 模型初始化（glm-4-flash）
│   │   │
│   │   ├── utils/                  # 工具函数
│   │   │   ├── path_utils.py       # 路径工具
│   │   │   └── word_converter.py   # Word 文档转换
│   │   │
│   │   └── output/                 # 结果输出目录
│   │
│   ├── tests/                      # 测试用例
│   │   ├── TEST_PLAN.md            # 测试计划文档
│   │   ├── conftest.py             # pytest 配置
│   │   ├── test_jobcraft_e2e.py    # 端到端测试（5-11 用例）
│   │   ├── test_agents_mock_unit.py # Agent 单测（14 个 mock）
│   │   ├── test_fuse_gap_scores_unit.py # 融合评分单测（5 个）
│   │   ├── test_jobcraft_analyze_unit.py # 岗位分析单测（10 个）
│   │   ├── test_resume_gen_unit.py  # 简历生成单测（10 个）
│   │   ├── test_misc_unit.py        # 杂项单测（9 个）
│   │   ├── test_qa_pairs_unit.py    # QA 配对单测
│   │   ├── check_*.py              # 调试脚本（不参与 pytest 收集）
│   │   └── *.txt                   # 测试数据文件
│   │
│   ├── pyproject.toml              # Python 依赖（uv 管理）
│   ├── uv.lock                     # 依赖锁文件
│   ├── .python-version             # Python 版本指定
│   ├── .env / .env.example         # 环境变量配置
│   └── .pre-commit-config.yaml     # Git hooks 配置
│
├── ⚛️ 前端 (React 18 + TypeScript)
│   ├── frontend-jobcraft/
│   │   ├── src/
│   │   │   ├── pages/              # 页面组件（6个）
│   │   │   │   ├── CareerRoutePage.tsx    # 🏠 求职路线（主页）
│   │   │   │   ├── ExperiencePage.tsx     # 📋 经历卡管理
│   │   │   │   ├── JDAnalysisPage.tsx     # 🔍 JD 分析库
│   │   │   │   ├── JobPage.tsx            # 🔧 JD 定制工作台
│   │   │   │   ├── InterviewPrepPage.tsx  # 🎤 面试准备
│   │   │   │   └── InterviewReviewPage.tsx# 📝 面试复盘
│   │   │   │
│   │   │   ├── components/         # 可复用组件
│   │   │   ├── api.ts              # 后端接口封装
│   │   │   ├── types.ts            # TypeScript 类型定义（从 Schema 同步）
│   │   │   ├── useRoute.ts         # Hash 路由（支持参数化 prep/:id review/:id）
│   │   │   ├── App.tsx             # 应用入口、路由配置
│   │   │   ├── main.tsx            # React 入口、ConfigProvider 主题
│   │   │   └── index.css           # 全局样式（--jc-* 设计系统）
│   │   │
│   │   ├── index.html              # HTML 入口
│   │   ├── vite.config.ts          # Vite 配置（代理、manualChunks）
│   │   ├── tsconfig.json           # TypeScript 配置
│   │   ├── package.json            # npm 依赖
│   │   └── dist/                   # 构建产物
│   │
│   └── 🐳 Docker 配置
│       └── docker/
│           ├── docker-compose.yaml # MySQL 8.4 容器配置
│           └── mysql/
│               └── jobcraft.sql    # 数据库初始化脚本
│
├── 🗄️ 数据库表结构
│   ├── experience_card              # 经历卡（raw_text + tags + ai_structured）
│   ├── card_versions               # 定制简历版本快照
│   ├── job_analysis                # JD 分析结果（ATS + 暗话解码 + 8维能力）
│   ├── resume_submission           # 投递记录（pipeline 核心）
│   ├── interview_preps             # 面试准备稿
│   ├── interview_records           # 面试复盘记录
│   ├── interview_qa_pairs          # 复盘 QA 对
│   ├── company_research            # 公司调研缓存（7天过期）
│   └── experience_job_mapping      # 经历卡 ↔ 投递关联
│
├── 🔧 配置文件
│   ├── .gitignore                  # Git 忽略规则
│   ├── .ruff_cache/                # Ruff 缓存
│   ├── .pytest_cache/              # Pytest 缓存
│   └── .vscode/                    # VSCode 配置
│
└── 📊 项目数据流
    经历卡 (experience_card)
        │ raw_text + tags + ai_structured 缓存
        ▼
    JD 分析 (job_analysis) ──▶ 定制简历 (card_versions 版本快照)
                                  │
                                  ▼
                    resume_submission（投递记录，pipeline 核心）
                          │                 │
                          ▼                 ▼
              interview_preps（面试准备）  interview_records（面试复盘）
```

## 📈 版本演进

```
v0.2  经历卡架构重构（raw_text + tags + ai_structured 缓存）
  ↓
v0.3  岗位分析模块重构（ATS+推荐合并、缺口+润色合并、简历模板化）
  ↓
v0.4  求职系统 CRM 化重构（投递记录为核心、JD分析原子化）
  ↓
v0.5  面试准备增强 + 手动补录（公司调研、多轮衔接、4态按钮）
  ↓
v0.6  Agent Workbench 重构（Multi-Agent Workflow、LLM 下沉 agents）
  ↓
v0.7  Bug 修复 + 功能补全（12个Bug + 8个Feature）
  ↓
v0.8  暗话分析 + 简历生成（JD潜台词解码、HTML预览、PDF导出）
  ↓
v0.9  极简编辑风格 + 四项待办（设计系统、卡片回填、多维评估、PDF下载）
  ↓
v0.10 hallmark audit 落地（token化、响应式、字体、对比度、图标）
  ↓
v0.11 UI 迭代（重复标题修复、经历卡分类分组、求职路线视觉化）
  ↓
v0.12 求职路线 + 经历卡 + JD 库体验优化（空态UI、公司聚合、STAR原则）
```

## 🏗️ 架构分层

```
┌─────────────────────────────────────────────────────────────┐
│  前端 React + Ant Design                                    │
│  • Hash 路由（useRoute.ts）                                  │
│  • 页面懒加载（React.lazy + Suspense）                       │
│  • 设计系统（--jc-* token）                                  │
└─────────────────────┬───────────────────────────────────────┘
                      │ HTTP (REST API)
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  Controller (app/api/server.py)                             │
│  • 路由注册                                                 │
│  • 参数校验（Pydantic）                                      │
│  • 统一响应格式 {code, msg, data}                            │
│  • 全局异常处理                                              │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  Workflow (app/workflows/*)                                 │
│  • LangGraph StateGraph 编排                                 │
│  • 面试复盘：6节点 Multi-Agent（Router→Tech/Soft→Gate）       │
│  • 岗位分析/面试准备/经历卡：单节点 Workflow                   │
│  • 可观测：每步 State 可日志、可打断、可重试                    │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  Agent (app/agents/*)                                       │
│  • 单一职责：每个 Agent 只做一件事                            │
│  • 无状态：所有输入输出通过 State 传递                        │
│  • 单次节点最多 1 次 LLM 调用                                │
│  • Pydantic 类型标注                                         │
│  • 14 个 Agent 节点                                         │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  Tool (app/tools/*)                                         │
│  • 纯函数：不包含 LLM 调用（llm_json 除外）                  │
│  • DB CRUD / 文件解析 / 规则引擎 / 本地匹配                  │
│  • 所有函数有类型提示与 Docstring                             │
└─────────────────────────────────────────────────────────────┘
```

## 🔑 核心数据模型

```
ExperienceCardSchema
├── raw_text: str              # 用户原始输入（唯一必填）
├── tags: list[str]            # 扁平标签（LLM推荐 + 用户编辑）
├── ai_structured: dict        # AI结构化缓存（按需生成）
│   ├── summary: str           # 一句话总结
│   └── achievements: list     # STAR结构成就
│       ├── situation: str     # 背景
│       ├── action: str        # 行动（含困难与解决）
│       └── result: str        # 结果
├── card_type: str             # work/intern/project
├── company: str               # 公司（可选）
├── role: str                  # 角色（可选）
└── period: str                # 时间段（可选）

ResumeSubmission（Pipeline 核心）
├── id: int                    # 主键
├── job_analysis_id: int       # 关联JD分析
├── position: str              # 岗位名称
├── company: str               # 公司名称
├── jd_text: str               # JD原文
├── resume_markdown: str       # 投出的简历全文
├── resume_file_path: str      # 上传的文件路径
├── card_version_ids: list     # 润色版本快照
├── status: str                # 已投递→面试邀约→一面→二面→Offer/已关闭
└── is_manual: bool            # 是否手动补录

JobAnalysisResult
├── ats: ATSProfile            # ATS画像
│   ├── position: str          # 岗位
│   ├── experience: str        # 经验要求
│   ├── education: str         # 学历要求
│   ├── hard_skills: list      # 硬技能
│   ├── soft_skills: list      # 软技能
│   ├── keywords: list         # 关键词
│   ├── dimensions: dict       # D1-D8 8维能力
│   └── subtext_decoded: list  # 暗话解码（3-6条）
├── recommendations: list      # 推荐经历卡
├── gap_items: list            # 缺口分析
└── polish_suggestions: list   # 润色建议
```

## 🎯 核心功能模块

### 1. 求职路线（Dashboard）
- 投递时间线展示（按时间倒序）
- 5步按钮矩阵：JD分析 → 润色卡片 → 简历 → 面试准备 → 复盘
- 按钮4态：todo/done/locked/ready
- 状态流转：已投递 → 面试邀约 → 一面 → 二面 → Offer/已关闭
- 空状态引导用户去JD分析库

### 2. 经历卡管理
- 支持上传简历/输入文本 → AI抽取结构化经历卡
- 原始文本存储 + AI结构化缓存（S/A/R）
- 标签推荐（LLM + 用户手动编辑）
- 按公司分组展示，支持工作/实习/项目分类
- 版本历史面板（哪些投递在使用哪些润色版本）

### 3. JD 分析库（独立工作台）
- 原子功能：不绑定卡片/流程，可被多个场景复用
- ATS画像提取（D1-D8 8维能力）
- 暗话解码（表面要求→实际期望→关键能力→证明方式）
- 经历卡匹配 + 缺口分析 + 润色建议
- 定制简历生成（HTML预览、PDF下载）

### 4. 面试准备
- 基于投递记录的JD + 实际投出的简历 + 经历卡
- 轮次选择：技术面/业务面/HR面
- 预测题 + 答题要点 + 可关联经历卡
- 公司调研（Tavily + 7天缓存）
- 多轮衔接（自动提取上一轮复盘摘要）

### 5. 面试复盘
- 上传面试记录文本 → 说话人拆分 → QA配对
- 问题表汇总（勾选问题触发详细解析）
- Multi-Agent分析：Router分类 → Tech/Soft并行 → Gate质检
- 结构化输出：intent/标准答案/反馈/改进建议/评分

## 🔧 技术栈详情

### 后端
- **运行时**: Python 3.12
- **Web框架**: FastAPI + Uvicorn
- **LLM编排**: LangGraph（StateGraph）+ LangChain
- **数据校验**: Pydantic v2
- **数据库**: MySQL 8.4
- **搜索**: Tavily（公司调研）
- **依赖管理**: uv
- **代码质量**: ruff（lint + format）
- **测试**: pytest

### 前端
- **框架**: React 18 + TypeScript
- **构建**: Vite 7
- **UI库**: Ant Design 5
- **路由**: 自实现Hash路由（useRoute.ts）
- **样式**: CSS变量设计系统（--jc-* token）
- **懒加载**: React.lazy + Suspense
- **PDF导出**: html2canvas + jspdf

## 📊 API 接口概览

### 经历卡
- `POST /experience/upload` - 上传简历→抽取经历卡
- `GET /experience/cards` - 经历卡列表
- `POST /experience/cards` - 手动创建
- `PATCH /experience/cards/{id}` - 更新
- `DELETE /experience/cards/{id}` - 删除
- `POST /experience/cards/{id}/structure` - 生成/刷新结构化缓存
- `POST /experience/cards/{id}/recommend-tags` - 标签推荐

### JD分析与简历
- `POST /job/step1-ats-recommend` - Step1：ATS画像+推荐卡
- `POST /job/step2-gap-polish` - Step2：缺口分析+润色建议
- `POST /job/save-card-version` - 保存润色版本
- `POST /job/save-resume` - 生成并保存简历
- `POST /job/analyze-ats` - 仅ATS解析
- `POST /job/{id}/resume-preview` - 简历HTML预览

### 投递记录
- `POST /submission` - 创建投递
- `POST /submission/manual` - 手动补录
- `GET /dashboard` - 主页数据
- `PATCH /submission/{id}` - 更新状态

### 面试准备/复盘
- `POST /job/{id}/interview-prep` - 生成面试准备稿
- `POST /interview-review` - 面试复盘分析
- `POST /interview-review/parse-preview` - 解析预览
- `POST /interview-review/{id}/question-table` - 生成问题表
- `POST /interview-review/{id}/analyze` - 勾选问题详细解析

## 🎨 设计系统

### Token 变量（--jc-*）
- **颜色**: 祖母绿强调色 `#0f6b52`、暖米白底、灰阶文字
- **字体**: Fraunces 衬线标题（离线回退 Georgia/Songti）
- **圆角**: 12px（卡片）、4px（按钮）
- **间距**: 40px（页边距）、16px（卡片内边距）
- **响应式**: `minmax(min(320px,100%),1fr)` 网格
- **无障碍**: `prefers-reduced-motion` 降级

### 页面路由
- `#/dashboard` - 求职路线（主页）
- `#/experience` - 经历卡管理
- `#/jd-analysis` - JD分析库
- `#/job/:jobId` - JD定制工作台
- `#/prep/:submissionId` - 面试准备
- `#/review/:submissionId` - 面试复盘

## 🚀 快速启动

```bash
# 1. 启动MySQL
docker compose -f docker/docker-compose.yaml up -d

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 填写 API Key

# 3. 安装依赖
uv sync                          # 后端
cd frontend-jobcraft && npm install  # 前端

# 4. 启动服务
uv run uvicorn app.api.server:app --host 127.0.0.1 --port 8000  # 后端
cd frontend-jobcraft && npm run dev  # 前端

# 5. 访问
# 前端: http://localhost:5175
# 后端API: http://localhost:8000/docs
```

## 🧪 测试

```bash
# 单元测试（无LLM/DB依赖）
uv run pytest tests/ -q

# 代码质量
uv run ruff check --fix .
uv run ruff format .

# 前端构建
cd frontend-jobcraft && npm run build
```

## 📝 版本历史

- **v0.2-v0.3**: 经历卡与岗位分析架构重构
- **v0.4**: 求职系统CRM化（投递记录为核心）
- **v0.5**: 面试准备增强 + 手动补录
- **v0.6**: Agent Workbench重构（Multi-Agent Workflow）
- **v0.7**: Bug修复 + 功能补全（12个Bug + 8个Feature）
- **v0.8**: 暗话分析 + 简历生成
- **v0.9**: 极简编辑风格 + 四项待办
- **v0.10**: hallmark audit落地
- **v0.11**: UI迭代
- **v0.12**: 求职路线 + 经历卡 + JD库体验优化

## 🔮 待办事项

- [ ] 面试复盘长文本稳定性优化（Groq TPM限制）
- [ ] 经历卡与JD匹配的LLM评分校准
- [ ] 前端错误处理与加载状态统一
- [ ] 配置CI自动运行pytest + ruff
- [ ] 用户注册/登录（Non-Goal，排期在MVP之后）

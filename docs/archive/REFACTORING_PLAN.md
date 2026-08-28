# JobCraft 上线重构计划

> 目标：将项目从原型阶段提升至生产级标准
> 预计周期：8-12周（可根据资源调整）
> 评审标准：REVIEW_DIMENSIONS.md 中的 P0/P1 检查项全部通过

---

## 一、总体规划

### 1.1 阶段划分

```
┌─────────────────────────────────────────────────────────────┐
│  Phase 0: 安全加固（第1-2周）                                  │
│  目标：消除所有 P0 安全隐患                                    │
│  交付：安全审计报告通过                                        │
└─────────────────────┬───────────────────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  Phase 1: 架构重构（第3-5周）                                  │
│  目标：解决架构债务，支持多用户                                 │
│  交付：架构评审通过                                            │
└─────────────────────┬───────────────────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  Phase 2: 功能完善（第6-8周）                                  │
│  目标：补齐核心功能，提升用户体验                               │
│  交付：功能测试通过                                            │
└─────────────────────┬───────────────────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  Phase 3: 质量保障（第9-10周）                                 │
│  目标：完善测试、监控、文档                                    │
│  交付：上线检查清单通过                                        │
└─────────────────────┬───────────────────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  Phase 4: 上线准备（第11-12周）                                │
│  目标：部署、压测、验收                                        │
│  交付：生产环境就绪                                            │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 里程碑定义

| 里程碑 | 时间 | 验收标准 | 阻塞项 |
|--------|------|----------|--------|
| M0: 安全基线 | 第2周末 | P0 安全问题清零 | 安全审计通过 |
| M1: 架构就绪 | 第5周末 | 多用户可用，连接池正常 | 架构评审通过 |
| M2: 功能完整 | 第8周末 | 核心流程跑通 | 功能测试通过 |
| M3: 质量达标 | 第10周末 | 测试覆盖>80%，监控完善 | 质量评审通过 |
| M4: 生产上线 | 第12周末 | 生产环境部署完成 | 上线审批通过 |

---

## 二、Phase 0: 安全加固（第1-2周）

### 2.1 任务清单

#### Week 1: 紧急修复

| 编号 | 任务 | 负责人 | 预估工时 | 优先级 | 依赖 |
|------|------|--------|----------|--------|------|
| S01 | 修复 CORS 配置 | 后端 | 2h | P0 | 无 |
| S02 | 修复错误信息泄露 | 后端 | 4h | P0 | 无 |
| S03 | 添加输入验证（所有接口） | 后端 | 8h | P0 | 无 |
| S04 | 文件名清洗 | 后端 | 2h | P0 | 无 |
| S05 | 环境变量安全检查 | 后端 | 2h | P0 | 无 |

#### Week 2: 安全加固

| 编号 | 任务 | 负责人 | 预估工时 | 优先级 | 依赖 |
|------|------|--------|----------|--------|------|
| S06 | 引入 JWT 认证（基础版） | 后端 | 16h | P0 | S01 |
| S07 | user_id 从 Token 提取 | 后端 | 4h | P0 | S06 |
| S08 | 添加速率限制 | 后端 | 4h | P1 | 无 |
| S09 | SQL 注入检查 | 后端 | 4h | P0 | 无 |
| S10 | 安全测试报告 | 测试 | 8h | P1 | S01-S09 |

### 2.2 详细方案

#### S01: 修复 CORS 配置

**当前代码** (`app/api/server.py:67-73`):
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 问题：允许所有来源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**修复方案**:
```python
# 从环境变量读取允许的来源
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:5175").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
```

**验收标准**:
- [x] CORS 仅允许指定域名
- [x] 仅允许必要方法
- [x] 仅允许必要头
- [ ] 单元测试通过

---

#### S02: 修复错误信息泄露

**当前问题**:
```python
# 多处直接暴露异常信息
except Exception as e:
    raise HTTPException(status_code=500, detail=f"创建经历卡失败: {e}")
```

**修复方案**:
```python
# 1. 创建自定义异常类
class JobCraftException(Exception):
    def __init__(self, message: str, code: int = 500, details: Any = None):
        self.message = message
        self.code = code
        self.details = details

# 2. 统一异常处理
@app.exception_handler(JobCraftException)
async def jobcraft_exception_handler(request: Request, exc: JobCraftException):
    logger.error(f"业务异常: {exc.message}", exc_info=exc.details)
    return JSONResponse(
        status_code=exc.code,
        content={"code": exc.code, "msg": exc.message, "data": {}}
    )

# 3. 修改所有 except 块
except Exception as e:
    logger.exception("创建经历卡失败")
    raise JobCraftException("创建失败，请稍后重试", code=500)
```

**验收标准**:
- [x] 生产环境不暴露堆栈
- [x] 开发环境可查看完整错误
- [x] 所有异常统一处理

---

#### S06: 引入 JWT 认证

**实现方案**:

```python
# 1. 新增依赖
# pyproject.toml
dependencies = [
    ...
    "python-jose[cryptography]>=3.3.0",
    "passlib[bcrypt]>=1.7.4",
]

# 2. 创建认证模块 app/auth/__init__.py
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-here")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7天

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None

# 3. 创建认证中间件 app/auth/middleware.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    payload = verify_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭证"
        )
    return payload.get("user_id")

# 4. 修改所有接口
@app.get("/api/jobcraft/experience/cards")
async def jobcraft_experience_list(
    user_id: int = Depends(get_current_user),  # 从 Token 提取
    include_inactive: bool = False,
):
    ...
```

**数据库表**:
```sql
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    email VARCHAR(200),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

**验收标准**:
- [ ] 登录接口可用
- [ ] Token 签发和验证正常
- [ ] 所有接口需要认证
- [ ] user_id 从 Token 提取
- [ ] 旧的 user_id=1 默认值移除

---

### 2.3 验收检查点

**Week 1 结束检查**:
```bash
# 静态安全扫描
bandit -r app/ -f json -o security-report.json

# 依赖漏洞检查
pip-audit

# CORS 测试
curl -H "Origin: http://evil.com" http://localhost:8000/api/jobcraft/experience/cards
# 预期：被拒绝

# 错误信息测试
curl -X POST http://localhost:8000/api/jobcraft/experience/upload -F "file=@malicious.exe"
# 预期：返回通用错误，不暴露堆栈
```

**Week 2 结束检查**:
```bash
# JWT 认证测试
TOKEN=$(curl -X POST http://localhost:8000/api/auth/login -d '{"username":"test","password":"test"}' | jq -r .token)
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/jobcraft/experience/cards
# 预期：返回数据

# 无 Token 测试
curl http://localhost:8000/api/jobcraft/experience/cards
# 预期：返回 401

# 速率限制测试
for i in {1..100}; do curl http://localhost:8000/api/jobcraft/experience/cards; done
# 预期：超过限制后返回 429
```

---

## 三、Phase 1: 架构重构（第3-5周）

### 3.1 任务清单

#### Week 3: 数据库重构

| 编号 | 任务 | 负责人 | 预估工时 | 优先级 | 依赖 |
|------|------|--------|----------|--------|------|
| A01 | 引入 SQLAlchemy + Alembic | 后端 | 16h | P0 | 无 |
| A02 | 数据库模型定义 | 后端 | 8h | P0 | A01 |
| A03 | 迁移脚本编写 | 后端 | 8h | P0 | A02 |
| A04 | 移除运行时 DDL | 后端 | 4h | P0 | A03 |

#### Week 4: 连接管理

| 编号 | 任务 | 负责人 | 预估工时 | 优先级 | 依赖 |
|------|------|--------|----------|--------|------|
| A05 | 配置连接池 | 后端 | 8h | P0 | A01 |
| A06 | 重构 db_tools | 后端 | 16h | P0 | A05 |
| A07 | 添加数据库迁移测试 | 测试 | 4h | P1 | A03 |

#### Week 5: 中间件完善

| 编号 | 任务 | 负责人 | 预估工时 | 优先级 | 依赖 |
|------|------|--------|----------|--------|------|
| A08 | 添加请求 ID 中间件 | 后端 | 4h | P1 | 无 |
| A09 | 添加结构化日志 | 后端 | 8h | P1 | 无 |
| A10 | 添加健康检查接口 | 后端 | 2h | P1 | 无 |
| A11 | 添加 API 文档 | 后端 | 4h | P1 | 无 |

### 3.2 详细方案

#### A01: 引入 SQLAlchemy + Alembic

**实现方案**:

```python
# 1. 新增依赖
# pyproject.toml
dependencies = [
    ...
    "sqlalchemy>=2.0.0",
    "alembic>=1.12.0",
]

# 2. 创建数据库配置 app/db/config.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
import os

DATABASE_URL = f"mysql+mysqlconnector://{os.getenv('MYSQL_USER')}:{os.getenv('MYSQL_PASSWORD')}@{os.getenv('MYSQL_HOST')}:{os.getenv('MYSQL_PORT')}/{os.getenv('MYSQL_DATABASE')}"

engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 3. 创建模型 app/db/models.py
from sqlalchemy import Column, Integer, String, Text, JSON, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from .config import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    email = Column(String(200))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    experience_cards = relationship("ExperienceCard", back_populates="user")
    job_analyses = relationship("JobAnalysis", back_populates="user")

class ExperienceCard(Base):
    __tablename__ = "experience_card"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(300), nullable=False)
    raw_text = Column(Text)
    tags = Column(JSON)
    ai_structured = Column(JSON)
    company = Column(String(200))
    role = Column(String(100))
    period = Column(String(100))
    card_type = Column(String(32), default="work")
    source = Column(String(50), default="manual")
    is_active = Column(Boolean, default=True)
    version = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    user = relationship("User", back_populates="experience_cards")

# ... 其他模型类似

# 4. 初始化 Alembic
alembic init alembic

# 5. 生成迁移脚本
alembic revision --autogenerate -m "initial migration"

# 6. 执行迁移
alembic upgrade head
```

**验收标准**:
- [ ] 数据库表结构正确
- [ ] 迁移脚本可执行
- [ ] 连接池正常工作
- [ ] 旧数据可迁移

---

#### A06: 重构 db_tools

**重构策略**:

1. **保留接口兼容**：现有 API 不变
2. **内部实现替换**：db_tools 内部使用 SQLAlchemy
3. **逐步迁移**：先迁移核心函数，再迁移其他

```python
# 重构后的 db_tools.py
from sqlalchemy.orm import Session
from app.db.config import get_db
from app.db.models import ExperienceCard, JobAnalysis, ...

def list_cards(user_id: int, include_inactive: bool = False) -> List[Dict[str, Any]]:
    """获取用户经历卡列表（重构后）"""
    with next(get_db()) as db:
        query = db.query(ExperienceCard).filter(ExperienceCard.user_id == user_id)
        if not include_inactive:
            query = query.filter(ExperienceCard.is_active == True)
        cards = query.order_by(
            ExperienceCard.company,
            ExperienceCard.period,
            ExperienceCard.updated_at.desc()
        ).all()
        return [_card_to_dict(card) for card in cards]

def _card_to_dict(card: ExperienceCard) -> Dict[str, Any]:
    """模型转字典（保持向后兼容）"""
    return {
        "id": card.id,
        "user_id": card.user_id,
        "title": card.title,
        "raw_text": card.raw_text,
        "tags": card.tags or [],
        "ai_structured": card.ai_structured,
        "company": card.company,
        "role": card.role,
        "period": card.period,
        "card_type": card.card_type,
        "source": card.source,
        "is_active": card.is_active,
        "version": card.version,
        "created_at": card.created_at.isoformat() if card.created_at else None,
        "updated_at": card.updated_at.isoformat() if card.updated_at else None,
    }
```

**验收标准**:
- [ ] 所有 API 接口正常
- [ ] 数据库操作使用连接池
- [ ] 无运行时 DDL
- [ ] 性能无退化

---

### 3.3 验收检查点

**Week 3 结束检查**:
```bash
# 数据库迁移测试
alembic upgrade head
alembic downgrade -1
alembic upgrade head

# 模型测试
pytest tests/test_models.py -v
```

**Week 5 结束检查**:
```bash
# 连接池监控
SHOW STATUS LIKE 'Threads_connected';

# 压力测试
locust -f locustfile.py --host=http://localhost:8000

# 日志检查
curl http://localhost:8000/health
# 预期：返回健康状态
```

---

## 四、Phase 2: 功能完善（第6-8周）

### 4.1 任务清单

#### Week 6: 分页与搜索

| 编号 | 任务 | 负责人 | 预估工时 | 优先级 | 依赖 |
|------|------|--------|----------|--------|------|
| F01 | 添加分页接口 | 后端 | 8h | P1 | 无 |
| F02 | 前端分页组件 | 前端 | 8h | P1 | F01 |
| F03 | 添加搜索功能 | 后端 | 8h | P1 | 无 |
| F04 | 前端搜索组件 | 前端 | 4h | P1 | F03 |

#### Week 7: 异步处理

| 编号 | 任务 | 负责人 | 预估工时 | 优先级 | 依赖 |
|------|------|--------|----------|--------|------|
| F05 | 引入 Celery + Redis | 后端 | 16h | P1 | 无 |
| F06 | LLM 调用异步化 | 后端 | 8h | P1 | F05 |
| F07 | 任务状态查询接口 | 后端 | 4h | P1 | F06 |
| F08 | 前端任务状态展示 | 前端 | 8h | P1 | F07 |

#### Week 8: 数据导出

| 编号 | 任务 | 负责人 | 预估工时 | 优先级 | 依赖 |
|------|------|--------|----------|--------|------|
| F09 | JSON 导出接口 | 后端 | 4h | P2 | 无 |
| F10 | CSV 导出接口 | 后端 | 4h | P2 | 无 |
| F11 | 前端导出按钮 | 前端 | 4h | P2 | F09, F10 |
| F12 | 批量操作接口 | 后端 | 8h | P2 | 无 |

### 4.2 详细方案

#### F01: 添加分页接口

**实现方案**:

```python
# 1. 创建分页 Schema app/schemas/common.py
from pydantic import BaseModel
from typing import TypeVar, Generic, List, Optional
from pydantic.generics import GenericModel

T = TypeVar("T")

class PaginationParams(BaseModel):
    page: int = 1
    page_size: int = 20
    
    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

class PaginatedResponse(GenericModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int

# 2. 修改接口
@app.get("/api/jobcraft/experience/cards")
async def jobcraft_experience_list(
    user_id: int = Depends(get_current_user),
    include_inactive: bool = False,
    page: int = 1,
    page_size: int = 20,
):
    """列出用户经历卡（支持分页）"""
    total = db_tools.count_cards(user_id, include_inactive)
    cards = db_tools.list_cards(
        user_id, 
        include_inactive,
        offset=(page - 1) * page_size,
        limit=page_size
    )
    return {
        "items": cards,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }
```

**验收标准**:
- [ ] 分页参数生效
- [ ] 返回总数
- [ ] 前端分页组件正常

---

#### F05: 引入 Celery + Redis

**实现方案**:

```python
# 1. 新增依赖
# pyproject.toml
dependencies = [
    ...
    "celery[redis]>=5.3.0",
    "redis>=5.0.0",
]

# 2. 创建 Celery 配置 app/tasks/celery_app.py
from celery import Celery
import os

celery_app = Celery(
    "jobcraft",
    broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5分钟超时
    task_soft_time_limit=240,  # 4分钟软超时
)

# 3. 创建异步任务 app/tasks/llm_tasks.py
from celery import shared_task
from app.agents.structured_caller import invoke_structured
from app.db.config import SessionLocal
from app.db.models import JobAnalysis

@shared_task(bind=True, max_retries=3)
def run_step1_ats_recommend(self, job_id: int, jd_text: str, card_ids: List[int]):
    """异步执行 Step1: ATS 解析 + 推荐卡片"""
    try:
        # 执行 LLM 调用
        result = ats_and_recommend(jd_text, cards)
        
        # 更新数据库
        with SessionLocal() as db:
            job = db.query(JobAnalysis).get(job_id)
            job.jd_requirements = result["ats"]
            job.status = "completed"
            db.commit()
        
        return {"job_id": job_id, "status": "completed", "result": result}
    except Exception as exc:
        # 重试
        self.retry(exc=exc, countdown=60)

# 4. 修改 API 接口
@app.post("/api/jobcraft/job/step1-ats-recommend")
async def jobcraft_step1_ats_recommend(
    payload: ATSRecommendPayload,
    user_id: int = Depends(get_current_user),
):
    """Step 1: ATS 解析 + 推荐卡片（异步）"""
    # 创建任务记录
    job_id = db_tools.insert_job_analysis({
        "user_id": user_id,
        "company": payload.company,
        "position": payload.position,
        "jd_text": payload.jd_text,
        "status": "pending",
    })
    
    # 启动异步任务
    task = run_step1_ats_recommend.delay(
        job_id=job_id,
        jd_text=payload.jd_text,
        card_ids=[],  # 将在任务中获取
    )
    
    return {
        "job_id": job_id,
        "task_id": task.id,
        "status": "processing",
        "message": "任务已提交，请稍后查询结果",
    }

@app.get("/api/jobcraft/job/{job_id}/status")
async def jobcraft_job_status(job_id: int):
    """查询任务状态"""
    job = db_tools.get_job_analysis(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {
        "job_id": job_id,
        "status": job.get("status", "unknown"),
        "result": job if job.get("status") == "completed" else None,
    }
```

**验收标准**:
- [ ] Redis 连接正常
- [ ] 任务异步执行
- [ ] 状态查询正常
- [ ] 超时和重试正常

---

### 4.3 验收检查点

**Week 6 结束检查**:
```bash
# 分页测试
curl "http://localhost:8000/api/jobcraft/experience/cards?page=1&page_size=10"
# 预期：返回分页数据

# 搜索测试
curl "http://localhost:8000/api/jobcraft/experience/cards?search=Python"
# 预期：返回匹配结果
```

**Week 8 结束检查**:
```bash
# 异步任务测试
curl -X POST http://localhost:8000/api/jobcraft/job/step1-ats-recommend -d '...'
# 预期：返回 task_id

# 任务状态查询
curl http://localhost:8000/api/jobcraft/job/{job_id}/status
# 预期：返回任务状态

# 导出测试
curl http://localhost:8000/api/jobcraft/experience/export?format=json
# 预期：返回 JSON 文件
```

---

## 五、Phase 3: 质量保障（第9-10周）

### 5.1 任务清单

#### Week 9: 测试完善

| 编号 | 任务 | 负责人 | 预估工时 | 优先级 | 依赖 |
|------|------|--------|----------|--------|------|
| Q01 | 单元测试补充 | 后端 | 16h | P1 | 无 |
| Q02 | 集成测试编写 | 测试 | 16h | P1 | 无 |
| Q03 | E2E 测试编写 | 测试 | 16h | P1 | 无 |
| Q04 | 覆盖率报告 | 测试 | 4h | P1 | Q01-Q03 |

#### Week 10: 监控与文档

| 编号 | 任务 | 负责人 | 预估工时 | 优先级 | 依赖 |
|------|------|--------|----------|--------|------|
| Q05 | Prometheus 集成 | 后端 | 8h | P1 | 无 |
| Q06 | Grafana 仪表盘 | 运维 | 8h | P1 | Q05 |
| Q07 | 告警规则配置 | 运维 | 4h | P1 | Q06 |
| Q08 | API 文档完善 | 后端 | 8h | P1 | 无 |
| Q09 | 运维文档编写 | 后端 | 8h | P2 | 无 |

### 5.2 详细方案

#### Q05: Prometheus 集成

**实现方案**:

```python
# 1. 新增依赖
# pyproject.toml
dependencies = [
    ...
    "prometheus-fastapi-instrumentator>=6.0.0",
]

# 2. 集成到 FastAPI app/api/server.py
from prometheus_fastapi_instrumentator import Instrumentator

app = FastAPI(title="JobCraft API", lifespan=lifespan)

# 添加 Prometheus 中间件
Instrumentator().instrument(app).expose(app, endpoint="/metrics")

# 3. 自定义指标 app/metrics/llm_metrics.py
from prometheus_client import Counter, Histogram

# LLM 调用计数
llm_calls_total = Counter(
    "jobcraft_llm_calls_total",
    "Total LLM calls",
    ["agent_name", "status"]
)

# LLM 调用耗时
llm_call_duration_seconds = Histogram(
    "jobcraft_llm_call_duration_seconds",
    "LLM call duration in seconds",
    ["agent_name"],
    buckets=[1, 2, 5, 10, 30, 60]
)

# 数据库查询耗时
db_query_duration_seconds = Histogram(
    "jobcraft_db_query_duration_seconds",
    "Database query duration in seconds",
    ["operation"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1, 5]
)
```

**验收标准**:
- [ ] /metrics 接口可用
- [ ] 指标正确上报
- [ ] Grafana 仪表盘可查看

---

#### Q03: E2E 测试编写

**测试用例**:

```python
# tests/e2e/test_jobcraft_e2e.py
import pytest
from playwright.async_api import async_playwright

@pytest.mark.e2e
class TestJobCraftE2E:
    
    async def test_experience_card_flow(self, page):
        """测试经历卡完整流程"""
        # 1. 访问经历卡页面
        await page.goto("http://localhost:5175/#/experience")
        
        # 2. 创建经历卡
        await page.click("text=新建经历卡")
        await page.fill('input[name="title"]', "测试经历")
        await page.fill('textarea[name="raw_text"]', "这是一段测试经历...")
        await page.click("text=保存")
        
        # 3. 验证创建成功
        await page.wait_for_selector("text=测试经历")
        
        # 4. 编辑经历卡
        await page.click("text=测试经历")
        await page.fill('input[name="title"]', "修改后的经历")
        await page.click("text=保存")
        
        # 5. 验证修改成功
        await page.wait_for_selector("text=修改后的经历")
        
        # 6. 删除经历卡
        await page.click("text=删除")
        await page.click("text=确认")
        
        # 7. 验证删除成功
        assert await page.query_selector("text=修改后的经历") is None
    
    async def test_job_analysis_flow(self, page):
        """测试 JD 分析完整流程"""
        # ... 类似实现
    
    async def test_interview_prep_flow(self, page):
        """测试面试准备完整流程"""
        # ... 类似实现
```

**验收标准**:
- [ ] 核心流程 E2E 测试通过
- [ ] 测试可重复执行
- [ ] 测试报告生成

---

### 5.3 验收检查点

**Week 9 结束检查**:
```bash
# 单元测试
pytest tests/unit/ -v --cov=app --cov-report=html
# 预期：覆盖率 >80%

# 集成测试
pytest tests/integration/ -v
# 预期：全部通过

# E2E 测试
pytest tests/e2e/ -v --headed
# 预期：核心流程通过
```

**Week 10 结束检查**:
```bash
# Prometheus 指标
curl http://localhost:8000/metrics
# 预期：返回指标数据

# Grafana 仪表盘
# 访问 http://localhost:3000
# 预期：看到 JobCraft 仪表盘
```

---

## 六、Phase 4: 上线准备（第11-12周）

### 6.1 任务清单

#### Week 11: 部署准备

| 编号 | 任务 | 负责人 | 预估工时 | 优先级 | 依赖 |
|------|------|--------|----------|--------|------|
| D01 | Docker Compose 配置 | 运维 | 8h | P1 | 无 |
| D02 | Nginx 配置 | 运维 | 4h | P1 | D01 |
| D03 | SSL 证书配置 | 运维 | 4h | P1 | D02 |
| D04 | 环境变量管理 | 运维 | 4h | P1 | 无 |
| D05 | 数据库备份策略 | 运维 | 4h | P1 | 无 |

#### Week 12: 压测与上线

| 编号 | 任务 | 负责人 | 预估工时 | 优先级 | 依赖 |
|------|------|--------|----------|--------|------|
| D06 | 压力测试 | 测试 | 8h | P1 | D01 |
| D07 | 性能调优 | 后端 | 8h | P1 | D06 |
| D08 | 上线检查清单 | 全员 | 4h | P0 | D01-D07 |
| D09 | 灰度发布 | 运维 | 8h | P1 | D08 |
| D10 | 监控告警验证 | 运维 | 4h | P1 | D09 |

### 6.2 详细方案

#### D01: Docker Compose 配置

**docker-compose.prod.yml**:

```yaml
version: '3.8'

services:
  # 后端 API
  api:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=mysql+mysqlconnector://user:password@db:3306/jobcraft
      - REDIS_URL=redis://redis:6379/0
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}
      - ALLOWED_ORIGINS=https://yourdomain.com
    depends_on:
      - db
      - redis
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # 前端
  frontend:
    build:
      context: ./frontend-jobcraft
      dockerfile: Dockerfile
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - api
    restart: unless-stopped

  # 数据库
  db:
    image: mysql:8.4
    ports:
      - "3306:3306"
    environment:
      - MYSQL_ROOT_PASSWORD=${MYSQL_ROOT_PASSWORD}
      - MYSQL_DATABASE=jobcraft
      - MYSQL_USER=jobcraft
      - MYSQL_PASSWORD=${MYSQL_PASSWORD}
    volumes:
      - mysql_data:/var/lib/mysql
      - ./docker/mysql/jobcraft.sql:/docker-entrypoint-initdb.d/init.sql
    restart: unless-stopped

  # Redis
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    restart: unless-stopped

  # Celery Worker
  celery_worker:
    build:
      context: .
      dockerfile: Dockerfile
    command: celery -A app.tasks.celery_app worker --loglevel=info
    environment:
      - DATABASE_URL=mysql+mysqlconnector://user:password@db:3306/jobcraft
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis
    restart: unless-stopped

  # Prometheus
  prometheus:
    image: prom/prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    restart: unless-stopped

  # Grafana
  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD}
    volumes:
      - grafana_data:/var/lib/grafana
    restart: unless-stopped

volumes:
  mysql_data:
  redis_data:
  prometheus_data:
  grafana_data:
```

**验收标准**:
- [ ] docker-compose up 正常启动
- [ ] 所有服务健康
- [ ] 可访问前端和后端

---

### 6.3 上线检查清单

```markdown
# 上线检查清单

## 一、安全检查（必须全部通过）

- [ ] CORS 配置正确，仅允许生产域名
- [ ] JWT 认证正常，Token 过期机制有效
- [ ] 所有接口需要认证
- [ ] user_id 从 Token 提取，无法篡改
- [ ] 输入验证完整，有长度限制
- [ ] SQL 全部使用参数化查询
- [ ] 文件名已清洗，防止路径穿越
- [ ] 错误信息不暴露堆栈
- [ ] 环境变量已配置，无硬编码密钥
- [ ] .env 文件不在 Git 中
- [ ] 速率限制已配置
- [ ] HTTPS 已配置

## 二、架构检查

- [ ] 数据库使用连接池
- [ ] 无运行时 DDL
- [ ] 迁移脚本已执行
- [ ] 请求 ID 中间件正常
- [ ] 结构化日志正常
- [ ] 健康检查接口正常

## 三、功能检查

- [ ] 核心流程可走通
- [ ] 分页功能正常
- [ ] 搜索功能正常
- [ ] 异步任务正常
- [ ] 数据导出正常

## 四、性能检查

- [ ] P95 响应时间 < 3秒（简单接口）
- [ ] P95 响应时间 < 10秒（LLM 接口）
- [ ] 并发支持 > 100
- [ ] 无内存泄漏
- [ ] 数据库慢查询 < 1%

## 五、监控检查

- [ ] Prometheus 指标正常
- [ ] Grafana 仪表盘正常
- [ ] 告警规则配置
- [ ] 日志可查询

## 六、运维检查

- [ ] Docker Compose 正常
- [ ] 备份策略配置
- [ ] 回滚方案准备
- [ ] 文档完善

## 七、测试检查

- [ ] 单元测试覆盖率 > 80%
- [ ] 集成测试通过
- [ ] E2E 测试通过
- [ ] 安全测试通过
- [ ] 性能测试通过
```

---

## 七、资源估算

### 7.1 人力需求

| 角色 | 人数 | 周期 | 主要职责 |
|------|------|------|----------|
| 后端开发 | 2人 | 12周 | 架构重构、功能开发 |
| 前端开发 | 1人 | 8周 | 前端适配、组件开发 |
| 测试工程师 | 1人 | 6周 | 测试编写、安全测试 |
| 运维工程师 | 1人 | 4周 | 部署、监控、运维 |

### 7.2 时间估算

| 阶段 | 周期 | 主要产出 |
|------|------|----------|
| Phase 0 | 2周 | 安全基线 |
| Phase 1 | 3周 | 架构就绪 |
| Phase 2 | 3周 | 功能完整 |
| Phase 3 | 2周 | 质量达标 |
| Phase 4 | 2周 | 生产上线 |
| **总计** | **12周** | **生产级系统** |

### 7.3 成本估算

| 项目 | 月成本 | 说明 |
|------|--------|------|
| 云服务器 | ¥2,000 | 2核4G |
| 数据库 | ¥500 | RDS MySQL |
| Redis | ¥200 | 云 Redis |
| 对象存储 | ¥100 | 文件存储 |
| 域名 + SSL | ¥100 | 年费分摊 |
| **总计** | **¥2,900/月** | - |

---

## 八、风险与应对

### 8.1 技术风险

| 风险 | 概率 | 影响 | 应对措施 |
|------|------|------|----------|
| LLM 服务不稳定 | 中 | 高 | 多供应商备份、降级策略 |
| 数据库性能瓶颈 | 中 | 高 | 读写分离、缓存 |
| 前端兼容性问题 | 低 | 中 | 多浏览器测试 |
| 安全漏洞修复不及时 | 中 | 高 | 建立安全响应流程 |

### 8.2 进度风险

| 风险 | 概率 | 影响 | 应对措施 |
|------|------|------|----------|
| 需求变更 | 高 | 高 | 严格需求管理 |
| 技术难点攻关 | 中 | 中 | 预留缓冲时间 |
| 人员变动 | 低 | 高 | 文档完善、知识共享 |
| 依赖服务延迟 | 中 | 中 | 提前准备、Mock 测试 |

---

## 九、成功标准

### 9.1 上线标准

- [ ] 所有 P0 安全问题修复
- [ ] 所有 P1 架构问题修复
- [ ] 核心功能测试通过
- [ ] 性能测试达标
- [ ] 监控告警完善
- [ ] 文档完善
- [ ] 上线检查清单通过

### 9.2 运营指标

| 指标 | 目标 | 说明 |
|------|------|------|
| 可用性 | 99.9% | 月度可用时间 |
| 响应时间 | P95 < 3s | 简单接口 |
| 错误率 | < 0.1% | 5xx 错误 |
| 并发支持 | > 100 | 同时在线用户 |

### 9.3 质量指标

| 指标 | 目标 | 说明 |
|------|------|------|
| 测试覆盖率 | > 80% | 单元测试 |
| 代码重复率 | < 5% | 重复代码占比 |
| 技术债务 | < 100 | SonarQube 评分 |
| 文档完整性 | > 90% | 接口文档覆盖 |

---

## 十、总结

### 10.1 当前状态

- **安全评分**: 3/10（多个致命漏洞）
- **架构评分**: 5/10（有严重债务）
- **功能评分**: 6/10（核心可用，细节缺失）
- **质量评分**: 5/10（测试不足，代码重复）
- **综合评分**: 4.4/10（不可上线）

### 10.2 目标状态

- **安全评分**: 9/10（符合生产标准）
- **架构评分**: 8/10（清晰、可扩展）
- **功能评分**: 9/10（完整、易用）
- **质量评分**: 9/10（高覆盖、低债务）
- **综合评分**: 8.5/10（可上线）

### 10.3 行动建议

1. **立即行动**: 修复 CORS、错误泄露、输入验证（1-2天）
2. **本周行动**: 引入 JWT 认证、数据库连接池（1周）
3. **本月行动**: 完成 Phase 0-1（4-5周）
4. **下月行动**: 完成 Phase 2-3（5-6周）
5. **第三月**: 完成 Phase 4 并上线（2-3周）

**预计上线时间**: 12周后（可根据资源调整）

---

**文档版本**: v1.0
**创建日期**: 2026-08-27
**最后更新**: 2026-08-27
**负责人**: 架构师 + 产品经理

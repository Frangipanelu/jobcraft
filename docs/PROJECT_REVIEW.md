# JobCraft 项目严厉评审报告

> 评审视角：产品负责人 + 架构师 + 安全审计员
> 评审日期：2026-08-27
> 评审标准：生产级项目、可商业化、可维护、安全合规

---

## 🚨 一、架构设计问题（严重）

### 1.1 单用户硬编码 - 设计债务 🔴 严重

```python
# server.py 多处硬编码 user_id=1
class JobAnalyzePayload(BaseModel):
    user_id: int = 1  # 硬编码默认值

class ATSRecommendPayload(BaseModel):
    user_id: int = 1  # 硬编码默认值

# 路由参数默认值
def jobcraft_experience_list(user_id: int = 1):
def jobcraft_dashboard(user_id: int = 1):
```

**问题分析**：
- 这不是"临时方案"，这是**架构债务**
- 所有 API 都假设单用户，多用户改造成本极高
- 数据隔离依赖 user_id 参数，但参数可以被任意篡改
- 如果未来接入用户系统，所有接口都需要重构

**改进建议**：
- 立即引入 JWT Token 认证
- user_id 从 Token 中提取，不再从请求体传入
- 添加数据隔离中间件

### 1.2 数据库连接管理混乱 🔴 严重

```python
# db_tools.py 每次操作都新建连接
def _jc_config() -> Dict[str, Any]:
    return get_db_config({"database": JOBCRAFT_DB})

def list_cards(user_id: int, include_inactive: bool = False):
    config = _jc_config()
    with connect(**config) as conn:  # 每次操作新建连接
        with conn.cursor(dictionary=True) as cur:
            cur.execute(...)
```

**问题分析**：
- 没有连接池，每次请求都创建新连接
- 高并发下会耗尽数据库连接
- 性能极差，不适合生产环境
- 没有连接超时、重试机制

**改进建议**：
- 使用连接池（如 `mysql-connector-pool`）
- 或使用 SQLAlchemy 的连接池管理
- 添加连接健康检查

### 1.3 `_ensure_*_columns()` 运行时 DDL 🔴 严重

```python
def _ensure_experience_card_columns() -> None:
    """确保 experience_card 表有新架构字段（兼容旧库）"""
    config = _jc_config()
    with connect(**config) as conn:
        with conn.cursor() as cur:
            cur.execute("SHOW COLUMNS FROM experience_card")
            existing = {c[0] for c in cur.fetchall()}
            for col, dtype in old_columns + new_columns:
                if col not in existing:
                    cur.execute(
                        "ALTER TABLE experience_card ADD COLUMN %s %s" % (col, dtype)
                    )
```

**问题分析**：
- 每次数据库操作都执行 `SHOW COLUMNS` 检查
- 生产环境每次请求都执行 DDL 检查，性能灾难
- 并发请求可能导致 DDL 冲突
- 没有版本管理，无法追踪数据库变更

**改进建议**：
- 使用数据库迁移工具（Alembic / Flyway）
- DDL 变更必须通过迁移脚本
- 移除运行时 DDL 检查

### 1.4 缺乏中间件和横切关注点 🟡 中等

```python
# server.py 没有统一的中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 严重安全隐患
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**问题分析**：
- 缺乏请求 ID 追踪
- 缺乏结构化日志
- 缺乏速率限制
- 缺乏认证/授权中间件
- CORS 配置过于宽松

---

## 🔐 二、安全隐患（致命）

### 2.1 CORS 配置漏洞 🔴 致命

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源
    allow_credentials=True,  # 允许携带凭证
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**风险**：
- 任何网站都可以发送跨域请求
- 可能被用于 CSRF 攻击
- 用户数据可能被恶意网站窃取

**修复**：
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5175"],  # 只允许前端地址
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
```

### 2.2 SQL 注入风险 🟡 中等

```python
# db_tools.py 存在字符串拼接
def get_table_data(table_name) -> str:
    sql = f"SELECT * FROM {table_name} LIMIT 100"  # 直接拼接表名
    cursor.execute(sql)
```

**风险**：
- 表名直接拼接到 SQL 中
- 虽然当前是内部工具，但存在被滥用的风险

**修复**：
- 表名白名单校验
- 使用参数化查询（虽然表名不能参数化）

### 2.3 文件上传安全 🟡 中等

```python
# server.py 文件上传
saved_path = target_dir / file.filename
with saved_path.open("wb") as buf:
    shutil.copyfileobj(file.file, buf)
```

**风险**：
- 使用原始文件名，可能包含路径穿越（`../../etc/passwd`）
- 没有文件名清洗
- 没有文件类型深度校验（仅检查扩展名）

**修复**：
```python
import re
from pathlib import Path

def sanitize_filename(filename: str) -> str:
    # 移除路径分隔符和特殊字符
    filename = re.sub(r'[\\/:*?"<>|]', '_', filename)
    # 限制长度
    filename = filename[:255]
    return filename

safe_name = sanitize_filename(file.filename)
saved_path = target_dir / safe_name
```

### 2.4 环境变量泄露 🟡 中等

```bash
# .env.example 暴露了数据库密码
MYSQL_PASSWORD=root
```

**风险**：
- 示例文件暴露了默认密码
- 如果 .env 被提交，数据库密码泄露

**修复**：
- .env.example 使用占位符
- 添加 README 提醒用户修改默认密码

### 2.5 错误信息泄露 🔴 严重

```python
# 多处直接暴露内部错误
except Exception as e:
    raise HTTPException(status_code=500, detail=f"创建经历卡失败: {e}")
```

**风险**：
- 异常信息可能包含数据库结构、文件路径、内部实现细节
- 攻击者可以利用这些信息进行进一步攻击

**修复**：
```python
except Exception as e:
    logger.exception("创建经历卡失败")  # 记录完整错误
    raise HTTPException(status_code=500, detail="服务器内部错误，请稍后重试")  # 返回通用信息
```

### 2.6 缺乏输入验证 🔴 严重

```python
# 多处缺乏长度限制
class InterviewReviewCreatePayload(BaseModel):
    raw_text: str  # 没有长度限制

# 文件大小限制不一致
MAX_BYTES = 10 * 1024 * 1024  # 10MB，但不同接口可能不同
```

**风险**：
- 恶意用户可以发送超大文本，导致 OOM
- LLM 调用成本不受控（prompt injection 攻击）

**修复**：
```python
from pydantic import Field

class InterviewReviewCreatePayload(BaseModel):
    raw_text: str = Field(..., max_length=100000)  # 限制100KB
```

---

## 🎯 三、产品逻辑问题（设计缺陷）

### 3.1 投递记录只能通过简历生成创建 🔴 严重

```markdown
# PRODUCT.md 中的设计
### 2.3 投递记录（Pipeline 核心）
- **创建方式**：仅通过 JD 分析页「为该 JD 定制简历」流程自动创建，不支持手动新建。
```

**问题分析**：
- 用户无法手动创建投递记录
- 实际求职中，很多投递没有定制简历
- 产品逻辑与实际使用场景脱节
- 手动补录功能虽然存在，但体验割裂

**改进建议**：
- 支持手动创建投递记录
- JD 分析后自动建议创建投递
- 投递记录应该独立于简历生成

### 3.2 面试准备和复盘绑定投递记录 🟡 中等

```markdown
# 设计决策
面试准备和复盘从投递记录进入，不占导航位
```

**问题分析**：
- 用户可能想为未投递的岗位准备面试
- 面试复盘可能来自非投递的面试（如内推、猎头）
- 强绑定导致灵活性差

**改进建议**：
- 面试准备/复盘应该可以独立创建
- 可选关联投递记录
- 保持当前入口，但支持独立创建

### 3.3 缺乏数据导出和迁移 🟡 中等

**问题分析**：
- 没有数据导出功能
- 用户无法迁移数据
- 无法备份重要信息
- 无法跨平台使用

**改进建议**：
- 支持 JSON/CSV 导出
- 支持简历 PDF/Word 导出
- 支持数据备份/恢复

### 3.4 缺乏版本控制和历史 🔴 严重

```python
# 经历卡没有版本历史
def update_card(card_id: int, updates: Dict[str, Any]) -> bool:
    # 直接覆盖，没有历史记录
    cur.execute("UPDATE experience_card SET " + ", ".join(sets) + " WHERE id=%s", ...)
```

**问题分析**：
- 修改后无法恢复
- 无法查看修改历史
- 无法对比不同版本
- 对于求职材料来说，这是致命缺陷

**改进建议**：
- 引入版本快照表
- 记录每次修改的变更
- 支持版本对比和回滚

### 3.5 缺乏搜索和筛选 🟡 中等

```python
# 经历卡列表没有搜索功能
def list_cards(user_id: int, include_inactive: bool = False):
    # 只能按公司+时间排序，无法搜索
    cur.execute("SELECT * FROM experience_card WHERE user_id=%s ORDER BY company, period, updated_at DESC", ...)
```

**问题分析**：
- 经历卡多了后无法快速定位
- JD 分析历史无法搜索
- 投递记录无法筛选

**改进建议**：
- 添加全文搜索
- 支持标签筛选
- 支持状态筛选

### 3.6 缺乏批量操作 🟡 中等

**问题分析**：
- 无法批量删除经历卡
- 无法批量更新状态
- 无法批量导出

**改进建议**：
- 添加批量操作接口
- 支持多选操作
- 支持批量状态更新

---

## ⚡ 四、性能问题（瓶颈）

### 4.1 LLM 调用无缓存 🔴 严重

```python
# 每次调用都重新执行 LLM
def run_step1_workflow(...):
    result = ats_and_recommend(jd_text, cards)  # 每次都调用 LLM
```

**问题分析**：
- 相同 JD 多次分析会重复调用 LLM
- 成本不可控
- 响应时间不稳定

**改进建议**：
- 添加 LLM 结果缓存（基于输入哈希）
- 设置缓存过期时间
- 支持手动刷新缓存

### 4.2 无异步处理 🔴 严重

```python
# 所有接口都是同步的
@app.post("/api/jobcraft/job/step1-ats-recommend")
def jobcraft_step1_ats_recommend(payload: ATSRecommendPayload):
    # 同步执行，阻塞请求
    result = run_step1_workflow(...)
    return result
```

**问题分析**：
- LLM 调用耗时 3-10 秒
- 同步处理导致用户等待
- 无法处理长任务
- 并发能力差

**改进建议**：
- 引入任务队列（Celery / Redis Queue）
- 长任务异步执行
- 支持任务状态查询
- 支持 WebSocket 推送

### 4.3 无分页 🔴 严重

```python
# 列表接口没有分页
def list_cards(user_id: int, include_inactive: bool = False):
    # 返回所有数据
    cur.execute("SELECT * FROM experience_card WHERE user_id=%s", ...)
    rows = cur.fetchall()  # 全部加载到内存
```

**问题分析**：
- 数据量大时内存溢出
- 响应时间随数据量线性增长
- 前端渲染性能差

**改进建议**：
- 添加分页参数（offset, limit）
- 返回总数
- 前端实现虚拟滚动

### 4.4 无速率限制 🔴 严重

```python
# 没有任何速率限制
@app.post("/api/jobcraft/job/step1-ats-recommend")
def jobcraft_step1_ats_recommend(payload: ATSRecommendPayload):
    # 可以被无限调用
```

**问题分析**：
- LLM 调用成本不受控
- 可能被恶意刷接口
- 服务可能被打挂

**改进建议**：
- 使用 `slowapi` 添加速率限制
- 按 IP/用户限制
- 按接口限制

### 4.5 无监控和告警 🟡 中等

```python
# monitor.py 存在但未被充分利用
from app.api.monitor import monitor
monitor.report_tool(tool_name="...", args={})
```

**问题分析**：
- 缺乏性能监控
- 缺乏错误告警
- 缺乏业务指标
- 无法主动发现问题

**改进建议**：
- 集成 Prometheus
- 添加 Grafana 仪表盘
- 设置告警规则

---

## 🧹 五、代码质量问题（技术债）

### 5.1 代码重复严重 🔴 严重

```python
# server.py 中重复的文件处理逻辑
# experience/upload
MAX_BYTES = 10 * 1024 * 1024
if file.size is not None and file.size > MAX_BYTES:
    raise HTTPException(...)

# submission/manual
MAX_BYTES = 10 * 1024 * 1024
if file.size is not None and file.size > MAX_BYTES:
    raise HTTPException(...)

# interview-review/upload
MAX_BYTES = 10 * 1024 * 1024
if file.size is not None and file.size > MAX_BYTES:
    raise HTTPException(...)
```

**问题分析**：
- 相同逻辑重复 5+ 次
- 修改需要同步多处
- 容易遗漏导致不一致

**改进建议**：
- 提取公共函数
- 使用装饰器
- 创建中间件

### 5.2 类型标注不完整 🟡 中等

```python
# 多处缺少类型标注
def get_table_data(table_name) -> str:  # table_name 缺少类型
def execute_sql_query(query) -> str:  # query 缺少类型
```

**改进建议**：
- 使用 mypy 检查类型
- 补充所有参数和返回值类型
- 启用 strict 模式

### 5.3 错误处理不一致 🟡 中等

```python
# 有的地方抛 HTTPException
raise HTTPException(status_code=400, detail="...")

# 有的地方返回错误对象
return {"error": "拒绝访问: 只能下载 output 目录下的文件"}

# 有的地方 raise ValueError
raise ValueError("JD 文本不能为空")
```

**改进建议**：
- 统一错误处理策略
- 使用自定义异常类
- 统一错误响应格式

### 5.4 魔法数字 🟡 中等

```python
# server.py
if len(resume_text.strip()) < 50:  # 50 是什么？
    raise HTTPException(...)

# db_tools.py
cur.execute("SELECT * FROM experience_card WHERE user_id=%s LIMIT 100", ...)  # 100 是什么？
```

**改进建议**：
- 提取为命名常量
- 添加注释说明
- 统一配置管理

### 5.5 缺乏文档 🟡 中等

```python
# 很多函数没有 docstring
def _jc_config() -> Dict[str, Any]:
    return get_db_config({"database": JOBCRAFT_DB})
```

**改进建议**：
- 为所有公共函数添加 docstring
- 使用 Google 风格
- 说明参数、返回值、异常

---

## 🏗️ 六、架构改进建议（优先级排序）

### P0 - 立即修复（1-2天）

1. **修复 CORS 配置**
   - 限制允许的来源
   - 限制允许的方法
   - 限制允许的头

2. **修复错误信息泄露**
   - 返回通用错误信息
   - 记录完整错误到日志

3. **添加输入验证**
   - 所有接口添加长度限制
   - 文件名清洗
   - 类型验证

### P1 - 短期修复（1-2周）

1. **引入用户认证**
   - JWT Token 认证
   - user_id 从 Token 提取
   - 数据隔离中间件

2. **引入数据库连接池**
   - 使用 SQLAlchemy 或连接池库
   - 配置连接池参数
   - 添加健康检查

3. **添加分页**
   - 所有列表接口添加分页
   - 返回总数
   - 前端适配

### P2 - 中期改进（1-2月）

1. **引入任务队列**
   - Celery + Redis
   - 异步 LLM 调用
   - 任务状态查询

2. **引入数据库迁移**
   - Alembic
   - 版本管理
   - 自动迁移

3. **引入缓存**
   - Redis 缓存
   - LLM 结果缓存
   - 查询结果缓存

### P3 - 长期规划（3-6月）

1. **多用户支持**
   - 完整的用户系统
   - 数据隔离
   - 权限管理

2. **微服务拆分**
   - LLM 服务独立
   - 文件服务独立
   - 消息队列

3. **生产化部署**
   - Docker Compose
   - Kubernetes
   - CI/CD

---

## 📊 七、产品逻辑改进建议

### 7.1 核心流程优化

**当前流程**：
```
经历卡 → JD 分析 → 定制简历 → 投递记录 → 面试准备 → 面试复盘
```

**问题**：
- 流程过于线性
- 缺乏灵活性
- 与实际求职场景脱节

**建议流程**：
```
经历卡 ──┐
          ├─→ JD 分析 ──→ 面试准备 ──→ 面试复盘
投递记录 ─┘
```

- 经历卡是独立的
- JD 分析可以独立使用
- 投递记录可以手动创建
- 面试准备/复盘可以独立创建
- 各模块可以灵活组合

### 7.2 功能优先级

**高优先级**：
1. 支持手动创建投递记录
2. 支持独立创建面试准备/复盘
3. 添加数据导出功能
4. 添加批量操作

**中优先级**：
1. 添加搜索和筛选
2. 添加版本历史
3. 添加数据同步
4. 添加移动端适配

**低优先级**：
1. 添加团队协作
2. 添加数据分析
3. 添加智能推荐
4. 添加 AI 模拟面试

### 7.3 用户体验优化

**当前问题**：
- 加载状态不明确
- 错误提示不友好
- 操作反馈不及时
- 移动端体验差

**改进建议**：
- 添加骨架屏
- 优化错误提示
- 添加操作确认
- 响应式设计

---

## 🎯 八、总结

### 必须立即修复（阻塞上线）

| 问题 | 严重程度 | 修复时间 |
|------|----------|----------|
| CORS 配置漏洞 | 🔴 致命 | 1小时 |
| 错误信息泄露 | 🔴 严重 | 2小时 |
| 文件名注入 | 🔴 严重 | 2小时 |
| 输入验证缺失 | 🔴 严重 | 4小时 |

### 短期必须修复（影响可用性）

| 问题 | 严重程度 | 修复时间 |
|------|----------|----------|
| 单用户硬编码 | 🔴 严重 | 3天 |
| 数据库连接管理 | 🔴 严重 | 2天 |
| 无分页 | 🔴 严重 | 2天 |
| 无速率限制 | 🔴 严重 | 1天 |

### 中期改进（影响可维护性）

| 问题 | 严重程度 | 修复时间 |
|------|----------|----------|
| 代码重复 | 🟡 中等 | 3天 |
| 无版本控制 | 🟡 中等 | 5天 |
| 无缓存 | 🟡 中等 | 3天 |
| 无异步处理 | 🟡 中等 | 1周 |

### 长期规划（影响可扩展性）

| 问题 | 严重程度 | 修复时间 |
|------|----------|----------|
| 无监控告警 | 🟡 中等 | 1周 |
| 无数据导出 | 🟡 中等 | 3天 |
| 无搜索功能 | 🟡 中等 | 1周 |
| 产品流程优化 | 🟡 中等 | 2周 |

---

## 📝 九、最终评价

### 优点

1. **架构清晰**：Controller → Workflow → Agent → Tool 四层架构设计合理
2. **文档完善**：PRODUCT.md、ARCHITECTURE.md、AGENTS.md 文档齐全
3. **功能完整**：核心求职流程（经历卡 → JD 分析 → 面试准备/复盘）已实现
4. **技术选型合理**：FastAPI + LangGraph + React 技术栈适合 AI 应用

### 缺点

1. **安全隐患严重**：CORS、错误信息泄露、输入验证缺失
2. **架构债务重**：单用户硬编码、无连接池、运行时 DDL
3. **性能瓶颈明显**：无缓存、无异步、无分页
4. **产品逻辑僵化**：流程过于线性，缺乏灵活性
5. **代码质量差**：重复代码多、类型标注不完整、错误处理不一致

### 评分

| 维度 | 评分 | 说明 |
|------|------|------|
| 架构设计 | 7/10 | 分层清晰，但有严重债务 |
| 安全性 | 3/10 | 多个致命漏洞 |
| 性能 | 4/10 | 无缓存、无异步、无分页 |
| 代码质量 | 5/10 | 重复多、类型不完整 |
| 产品设计 | 6/10 | 功能完整，但流程僵化 |
| 可维护性 | 5/10 | 文档好，但代码质量差 |
| **综合评分** | **5/10** | **不可上线，需重大重构** |

---

## 🚀 十、行动建议

### 第一阶段：安全加固（1-2天）
1. 修复 CORS 配置
2. 修复错误信息泄露
3. 添加输入验证
4. 文件名清洗

### 第二阶段：架构修复（1-2周）
1. 引入用户认证（JWT）
2. 引入数据库连接池
3. 添加分页
4. 添加速率限制

### 第三阶段：产品优化（2-4周）
1. 支持手动创建投递记录
2. 支持独立创建面试准备/复盘
3. 添加数据导出
4. 添加批量操作

### 第四阶段：性能优化（1-2月）
1. 引入任务队列
2. 引入缓存
3. 引入数据库迁移
4. 添加监控告警

---

**评审结论**：该项目目前处于**原型阶段**，存在多个严重安全隐患和架构债务，**不可直接上线**。建议立即进行安全加固，然后进行架构重构，最后进行产品优化。预计需要 2-3 个月的重构才能达到生产级标准。

# JobCraft 验收标准与检查点

> 本文档定义每个阶段的验收标准、检查点、通过条件，确保每个里程碑可量化、可验证。

---

## 一、验收流程

```
┌─────────────────────────────────────────────────────────────┐
│  开发完成 → 自测通过 → 提交验收 → 验收测试 → 问题修复 → 通过  │
└─────────────────────────────────────────────────────────────┘
```

### 1.1 验收角色

| 角色 | 职责 | 权限 |
|------|------|------|
| 开发者 | 提交验收、修复问题 | 无 |
| 测试工程师 | 执行验收测试、出具报告 | 有 |
| 架构师 | 架构评审、技术把关 | 有一票否决权 |
| 产品经理 | 功能验收、体验评审 | 有业务否决权 |
| 安全专家 | 安全审计、漏洞确认 | 有安全否决权 |

### 1.2 验收流程

1. **开发者自测**: 所有测试通过，代码审查完成
2. **提交验收**: 填写验收申请，附自测报告
3. **验收测试**: 测试工程师执行验收用例
4. **问题修复**: 开发者修复发现的问题
5. **复验**: 测试工程师复验问题修复
6. **验收通过**: 出具验收报告，里程碑关闭

---

## 二、Phase 0 验收标准（安全加固）

### 2.1 验收用例

#### 用例 S01: CORS 配置验证

| 项目 | 内容 |
|------|------|
| **用例ID** | SEC-CORS-001 |
| **前置条件** | 服务启动，前端运行 |
| **测试步骤** | 1. 从 http://localhost:5175 发送请求<br>2. 从 http://evil.com 发送请求<br>3. 检查响应头 |
| **预期结果** | 1. 允许 localhost:5175<br>2. 拒绝 evil.com<br>3. 响应头包含正确的 Access-Control-Allow-Origin |
| **验证命令** | `curl -H "Origin: http://evil.com" http://localhost:8000/api/jobcraft/experience/cards` |
| **通过标准** | 返回 CORS 错误，不返回数据 |

#### 用例 S02: 错误信息泄露验证

| 项目 | 内容 |
|------|------|
| **用例ID** | SEC-ERROR-001 |
| **前置条件** | 服务启动 |
| **测试步骤** | 1. 发送非法请求触发异常<br>2. 检查响应内容<br>3. 检查日志内容 |
| **预期结果** | 1. 响应包含通用错误信息<br>2. 不包含堆栈、文件路径<br>3. 日志包含完整错误 |
| **验证命令** | `curl -X POST http://localhost:8000/api/jobcraft/experience/upload -F "file=@malicious.exe"` |
| **通过标准** | 返回"文件格式不支持"，不暴露内部信息 |

#### 用例 S03: JWT 认证验证

| 项目 | 内容 |
|------|------|
| **用例ID** | SEC-AUTH-001 |
| **前置条件** | 服务启动，用户已注册 |
| **测试步骤** | 1. 不带 Token 访问接口<br>2. 带有效 Token 访问<br>3. 带过期 Token 访问<br>4. 带无效 Token 访问 |
| **预期结果** | 1. 返回 401<br>2. 返回数据<br>3. 返回 401<br>4. 返回 401 |
| **验证命令** | 见下方脚本 |
| **通过标准** | 认证机制正常工作 |

```bash
# 测试脚本
# 1. 无 Token
curl http://localhost:8000/api/jobcraft/experience/cards
# 预期：401

# 2. 有效 Token
TOKEN=$(curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"test","password":"test123"}' | jq -r .token)
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/jobcraft/experience/cards
# 预期：200，返回数据

# 3. 过期 Token
curl -H "Authorization: Bearer expired_token" http://localhost:8000/api/jobcraft/experience/cards
# 预期：401

# 4. 无效 Token
curl -H "Authorization: Bearer invalid_token" http://localhost:8000/api/jobcraft/experience/cards
# 预期：401
```

#### 用例 S04: 输入验证验证

| 项目 | 内容 |
|------|------|
| **用例ID** | SEC-INPUT-001 |
| **前置条件** | 服务启动 |
| **测试步骤** | 1. 发送超长文本<br>2. 发送空字段<br>3. 发送非法格式 |
| **预期结果** | 1. 返回长度限制错误<br>2. 返回必填字段错误<br>3. 返回格式错误 |
| **验证命令** | 见下方脚本 |
| **通过标准** | 所有输入验证生效 |

```bash
# 测试脚本
# 1. 超长文本
python -c "print('A' * 100000)" | curl -X POST http://localhost:8000/api/jobcraft/interview-review \
  -H "Content-Type: application/json" \
  -d @-
# 预期：返回长度限制错误

# 2. 空字段
curl -X POST http://localhost:8000/api/jobcraft/experience/cards \
  -H "Content-Type: application/json" \
  -d '{"title":"","raw_text":""}'
# 预期：返回必填字段错误

# 3. 非法格式
curl -X POST http://localhost:8000/api/jobcraft/job/step1-ats-recommend \
  -H "Content-Type: application/json" \
  -d '{"jd_text":123}'
# 预期：返回格式错误
```

### 2.2 验收检查点

| 检查项 | 验证方法 | 通过标准 | 状态 |
|--------|----------|----------|------|
| CORS 配置 | curl 测试 | 仅允许指定域名 | ☐ |
| 错误泄露 | 异常触发测试 | 返回通用错误 | ☐ |
| JWT 认证 | 接口测试 | 认证机制正常 | ☐ |
| 输入验证 | Fuzz 测试 | 验证生效 | ☐ |
| SQL 安全 | 代码审查 | 无拼接 | ☐ |
| 文件安全 | 上传测试 | 文件名已清洗 | ☐ |
| 速率限制 | 压力测试 | 限制生效 | ☐ |
| 环境变量 | 代码审查 | 无硬编码 | ☐ |

### 2.3 验收报告模板

```markdown
# Phase 0 验收报告

## 基本信息
- 验收日期: YYYY-MM-DD
- 验收人员: [姓名]
- 版本号: v0.x.0

## 验收结果
- 总用例数: X
- 通过数: X
- 失败数: X
- 通过率: X%

## 问题列表
| 编号 | 问题描述 | 严重程度 | 状态 |
|------|----------|----------|------|
| 1 | ... | P0/P1/P2 | 待修复/已修复 |

## 结论
- [ ] 验收通过
- [ ] 验收不通过，需修复后复验

## 签名
- 测试工程师: ___________ 日期: ___________
- 架构师: ___________ 日期: ___________
- 安全专家: ___________ 日期: ___________
```

---

## 三、Phase 1 验收标准（架构重构）

### 3.1 验收用例

#### 用例 A01: 数据库连接池验证

| 项目 | 内容 |
|------|------|
| **用例ID** | ARCH-DB-001 |
| **前置条件** | 服务启动 |
| **测试步骤** | 1. 并发发送 100 个请求<br>2. 监控数据库连接数<br>3. 检查响应时间 |
| **预期结果** | 1. 所有请求成功<br>2. 连接数 ≤ 20<br>3. 响应时间稳定 |
| **验证命令** | `locust -f locustfile.py --host=http://localhost:8000 -u 100 -r 10` |
| **通过标准** | 无连接泄漏，响应时间 P95 < 1s |

#### 用例 A02: 多用户数据隔离验证

| 项目 | 内容 |
|------|------|
| **用例ID** | ARCH-USER-001 |
| **前置条件** | 两个用户已注册 |
| **测试步骤** | 1. 用户 A 创建经历卡<br>2. 用户 B 尝试访问 A 的卡片<br>3. 用户 B 创建自己的卡片 |
| **预期结果** | 1. A 创建成功<br>2. B 无法访问 A 的卡片<br>3. B 只能看到自己的卡片 |
| **验证命令** | 见下方脚本 |
| **通过标准** | 数据完全隔离 |

```bash
# 测试脚本
# 1. 用户 A 登录
TOKEN_A=$(curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"user_a","password":"pass123"}' | jq -r .token)

# 2. 用户 A 创建卡片
curl -X POST http://localhost:8000/api/jobcraft/experience/cards \
  -H "Authorization: Bearer $TOKEN_A" \
  -H "Content-Type: application/json" \
  -d '{"title":"A的经历","raw_text":"..."}'

# 3. 用户 B 登录
TOKEN_B=$(curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"user_b","password":"pass123"}' | jq -r .token)

# 4. 用户 B 获取卡片列表
curl -H "Authorization: Bearer $TOKEN_B" http://localhost:8000/api/jobcraft/experience/cards
# 预期：不包含 A 的卡片

# 5. 用户 B 尝试访问 A 的卡片
curl -H "Authorization: Bearer $TOKEN_B" http://localhost:8000/api/jobcraft/experience/cards/1
# 预期：返回 404 或 403
```

#### 用例 A03: 数据库迁移验证

| 项目 | 内容 |
|------|------|
| **用例ID** | ARCH-MIGRATE-001 |
| **前置条件** | 旧数据库存在 |
| **测试步骤** | 1. 执行迁移脚本<br>2. 验证表结构<br>3. 验证数据完整性 |
| **预期结果** | 1. 迁移成功<br>2. 表结构正确<br>3. 数据无丢失 |
| **验证命令** | `alembic upgrade head && python -m pytest tests/test_migrate.py` |
| **通过标准** | 迁移成功，数据完整 |

### 3.2 验收检查点

| 检查项 | 验证方法 | 通过标准 | 状态 |
|--------|----------|----------|------|
| 连接池 | 压力测试 | 连接数 ≤ 20 | ☐ |
| 数据隔离 | 接口测试 | 无数据泄露 | ☐ |
| 迁移脚本 | 执行测试 | 成功执行 | ☐ |
| 运行时 DDL | 代码审查 | 无 DDL 语句 | ☐ |
| 请求 ID | 日志检查 | 包含 Request ID | ☐ |
| 结构化日志 | 日志检查 | JSON 格式 | ☐ |
| 健康检查 | curl 测试 | 返回健康状态 | ☐ |
| API 文档 | Swagger 测试 | 文档完整 | ☐ |

---

## 四、Phase 2 验收标准（功能完善）

### 4.1 验收用例

#### 用例 F01: 分页功能验证

| 项目 | 内容 |
|------|------|
| **用例ID** | FUNC-PAGE-001 |
| **前置条件** | 有 50 条经历卡 |
| **测试步骤** | 1. 请求第 1 页，每页 10 条<br>2. 请求第 5 页<br>3. 请求超出范围的页 |
| **预期结果** | 1. 返回 10 条，total=50<br>2. 返回 10 条<br>3. 返回空列表 |
| **验证命令** | `curl "http://localhost:8000/api/jobcraft/experience/cards?page=1&page_size=10"` |
| **通过标准** | 分页功能正常 |

#### 用例 F02: 异步任务验证

| 项目 | 内容 |
|------|------|
| **用例ID** | FUNC-ASYNC-001 |
| **前置条件** | Redis 启动 |
| **测试步骤** | 1. 提交 LLM 任务<br>2. 获取 task_id<br>3. 轮询状态<br>4. 获取结果 |
| **预期结果** | 1. 立即返回 task_id<br>2. 状态为 processing<br>3. 最终状态为 completed<br>4. 返回完整结果 |
| **验证命令** | 见下方脚本 |
| **通过标准** | 异步任务正常完成 |

```bash
# 测试脚本
# 1. 提交任务
RESPONSE=$(curl -X POST http://localhost:8000/api/jobcraft/job/step1-ats-recommend \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"company":"测试","position":"开发","jd_text":"..."}')
TASK_ID=$(echo $RESPONSE | jq -r .task_id)
JOB_ID=$(echo $RESPONSE | jq -r .job_id)

# 2. 轮询状态
for i in {1..30}; do
  STATUS=$(curl -H "Authorization: Bearer $TOKEN" \
    http://localhost:8000/api/jobcraft/job/$JOB_ID/status | jq -r .status)
  echo "Attempt $i: $STATUS"
  if [ "$STATUS" = "completed" ]; then
    break
  fi
  sleep 10
done

# 3. 获取结果
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/jobcraft/job/$JOB_ID
```

### 4.2 验收检查点

| 检查项 | 验证方法 | 通过标准 | 状态 |
|--------|----------|----------|------|
| 分页 | 接口测试 | 分页正确 | ☐ |
| 搜索 | 接口测试 | 搜索结果正确 | ☐ |
| 异步任务 | 端到端测试 | 任务正常完成 | ☐ |
| 任务状态 | 接口测试 | 状态更新正确 | ☐ |
| 数据导出 | 接口测试 | 导出文件正确 | ☐ |
| 批量操作 | 接口测试 | 操作生效 | ☐ |
| 前端适配 | UI 测试 | 组件正常 | ☐ |

---

## 五、Phase 3 验收标准（质量保障）

### 5.1 验收用例

#### 用例 Q01: 测试覆盖率验证

| 项目 | 内容 |
|------|------|
| **用例ID** | QUAL-COVER-001 |
| **前置条件** | 测试代码完成 |
| **测试步骤** | 1. 运行单元测试<br>2. 生成覆盖率报告<br>3. 检查关键模块 |
| **预期结果** | 1. 所有测试通过<br>2. 总覆盖率 > 80%<br>3. 核心模块覆盖率 > 90% |
| **验证命令** | `pytest tests/unit/ --cov=app --cov-report=html` |
| **通过标准** | 覆盖率达标 |

#### 用例 Q02: 监控告警验证

| 项目 | 内容 |
|------|------|
| **用例ID** | QUAL-MON-001 |
| **前置条件** | Prometheus + Grafana 启动 |
| **测试步骤** | 1. 访问 /metrics<br>2. 检查指标<br>3. 检查 Grafana 仪表盘<br>4. 触发告警 |
| **预期结果** | 1. 指标正常上报<br>2. 仪表盘显示数据<br>3. 告警正常触发 |
| **验证命令** | `curl http://localhost:8000/metrics` |
| **通过标准** | 监控系统正常工作 |

### 5.2 验收检查点

| 检查项 | 验证方法 | 通过标准 | 状态 |
|--------|----------|----------|------|
| 单元测试 | pytest | 全部通过 | ☐ |
| 覆盖率 | 覆盖率报告 | > 80% | ☐ |
| 集成测试 | pytest | 全部通过 | ☐ |
| E2E 测试 | Playwright | 核心流程通过 | ☐ |
| Prometheus | curl 测试 | 指标正常 | ☐ |
| Grafana | UI 检查 | 仪表盘正常 | ☐ |
| 告警 | 触发测试 | 告警正常 | ☐ |
| API 文档 | Swagger 检查 | 文档完整 | ☐ |
| 运维文档 | 文档审查 | 内容完整 | ☐ |

---

## 六、Phase 4 验收标准（上线准备）

### 6.1 上线检查清单

```markdown
# 上线检查清单

## 一、安全检查（必须全部通过）

- [ ] S01: CORS 配置正确
- [ ] S02: JWT 认证正常
- [ ] S03: 数据隔离有效
- [ ] S04: 输入验证完整
- [ ] S05: SQL 安全
- [ ] S06: 错误处理正确
- [ ] S07: 敏感信息保护
- [ ] S08: 速率限制生效
- [ ] S09: HTTPS 配置
- [ ] S10: 文件上传安全

## 二、架构检查

- [ ] A01: 连接池正常
- [ ] A02: 无运行时 DDL
- [ ] A03: 迁移已执行
- [ ] A04: 请求 ID 中间件
- [ ] A05: 结构化日志
- [ ] A06: 健康检查接口
- [ ] A07: API 文档完整

## 三、功能检查

- [ ] F01: 核心流程可用
- [ ] F02: 分页功能正常
- [ ] F03: 搜索功能正常
- [ ] F04: 异步任务正常
- [ ] F05: 数据导出正常

## 四、性能检查

- [ ] P01: P95 < 3s（简单接口）
- [ ] P02: P95 < 10s（LLM 接口）
- [ ] P03: 并发 > 100
- [ ] P04: 无内存泄漏
- [ ] P05: 慢查询 < 1%

## 五、监控检查

- [ ] M01: Prometheus 正常
- [ ] M02: Grafana 正常
- [ ] M03: 告警配置
- [ ] M04: 日志可查询

## 六、运维检查

- [ ] O01: Docker Compose 正常
- [ ] O02: 备份策略配置
- [ ] O03: 回滚方案准备
- [ ] O04: 文档完善

## 七、测试检查

- [ ] T01: 单元测试覆盖 > 80%
- [ ] T02: 集成测试通过
- [ ] T03: E2E 测试通过
- [ ] T04: 安全测试通过
- [ ] T05: 性能测试通过
```

### 6.2 压力测试标准

| 指标 | 目标 | 测试方法 |
|------|------|----------|
| 并发用户 | > 100 | Locust |
| 请求成功率 | > 99% | Locust |
| P95 响应时间 | < 3s | Locust |
| 错误率 | < 1% | Locust |
| 吞吐量 | > 50 RPS | Locust |

### 6.3 验收报告模板

```markdown
# 上线验收报告

## 基本信息
- 验收日期: YYYY-MM-DD
- 验收人员: [姓名]
- 版本号: v1.0.0
- 目标环境: 生产环境

## 验收结果
- 检查项总数: X
- 通过数: X
- 未通过数: X
- 通过率: X%

## 问题列表
| 编号 | 问题描述 | 严重程度 | 状态 | 备注 |
|------|----------|----------|------|------|
| 1 | ... | P0/P1/P2 | 待修复/已修复 | ... |

## 性能测试结果
| 指标 | 目标 | 实际 | 是否达标 |
|------|------|------|----------|
| 并发用户 | > 100 | X | 是/否 |
| P95 响应时间 | < 3s | Xs | 是/否 |
| 错误率 | < 1% | X% | 是/否 |

## 结论
- [ ] 可以上线
- [ ] 不可以上线，需修复后复验

## 审批
- 测试工程师: ___________ 日期: ___________
- 架构师: ___________ 日期: ___________
- 安全专家: ___________ 日期: ___________
- 产品经理: ___________ 日期: ___________
- 技术负责人: ___________ 日期: ___________
```

---

## 七、自动化验收脚本

### 7.1 安全验收脚本

```bash
#!/bin/bash
# scripts/security_acceptance.sh

echo "=== 安全验收测试 ==="

# 1. CORS 测试
echo "1. CORS 配置测试"
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" \
  -H "Origin: http://evil.com" \
  http://localhost:8000/api/jobcraft/experience/cards)
if [ "$RESPONSE" = "403" ] || [ "$RESPONSE" = "401" ]; then
  echo "   ✓ CORS 配置正确"
else
  echo "   ✗ CORS 配置错误，响应码: $RESPONSE"
fi

# 2. 错误泄露测试
echo "2. 错误信息泄露测试"
RESPONSE=$(curl -s http://localhost:8000/api/jobcraft/experience/upload \
  -F "file=@malicious.exe")
if echo "$RESPONSE" | grep -q "堆栈\|traceback\|Traceback"; then
  echo "   ✗ 存在错误信息泄露"
else
  echo "   ✓ 无错误信息泄露"
fi

# 3. 认证测试
echo "3. JWT 认证测试"
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" \
  http://localhost:8000/api/jobcraft/experience/cards)
if [ "$RESPONSE" = "401" ]; then
  echo "   ✓ 认证机制正常"
else
  echo "   ✗ 认证机制异常，响应码: $RESPONSE"
fi

echo "=== 安全验收完成 ==="
```

### 7.2 功能验收脚本

```bash
#!/bin/bash
# scripts/functional_acceptance.sh

echo "=== 功能验收测试 ==="

# 登录获取 Token
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"test","password":"test123"}' | jq -r .token)

# 1. 经历卡 CRUD
echo "1. 经历卡 CRUD 测试"
# 创建
CARD_ID=$(curl -s -X POST http://localhost:8000/api/jobcraft/experience/cards \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"测试经历","raw_text":"这是一段测试经历"}' | jq -r .id)

# 读取
RESPONSE=$(curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/jobcraft/experience/cards/$CARD_ID)
if echo "$RESPONSE" | jq -e .title > /dev/null; then
  echo "   ✓ 创建和读取成功"
else
  echo "   ✗ 创建或读取失败"
fi

# 更新
curl -s -X PATCH http://localhost:8000/api/jobcraft/experience/cards/$CARD_ID \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"修改后的经历"}' > /dev/null

# 删除
curl -s -X DELETE http://localhost:8000/api/jobcraft/experience/cards/$CARD_ID \
  -H "Authorization: Bearer $TOKEN" > /dev/null

echo "   ✓ 更新和删除成功"

# 2. 分页测试
echo "2. 分页功能测试"
RESPONSE=$(curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/jobcraft/experience/cards?page=1&page_size=10")
TOTAL=$(echo "$RESPONSE" | jq -r .total)
PAGE_SIZE=$(echo "$RESPONSE" | jq -r .page_size)
if [ "$PAGE_SIZE" = "10" ]; then
  echo "   ✓ 分页功能正常"
else
  echo "   ✗ 分页功能异常"
fi

echo "=== 功能验收完成 ==="
```

### 7.3 性能验收脚本

```bash
#!/bin/bash
# scripts/performance_acceptance.sh

echo "=== 性能验收测试 ==="

# 1. 简单接口性能
echo "1. 简单接口性能测试"
ab -n 1000 -c 10 -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/jobcraft/experience/cards

# 2. 并发测试
echo "2. 并发测试"
locust -f locustfile.py \
  --host=http://localhost:8000 \
  -u 100 \
  -r 10 \
  --headless \
  --run-time 1m \
  --html=performance_report.html

echo "=== 性能验收完成 ==="
```

---

## 八、验收时间表

| 阶段 | 验收时间 | 验收人员 | 产出 |
|------|----------|----------|------|
| Phase 0 | 第2周末 | 安全专家 + 测试 | 安全验收报告 |
| Phase 1 | 第5周末 | 架构师 + 测试 | 架构验收报告 |
| Phase 2 | 第8周末 | 产品经理 + 测试 | 功能验收报告 |
| Phase 3 | 第10周末 | 测试 + 架构师 | 质量验收报告 |
| Phase 4 | 第12周末 | 全员 | 上线验收报告 |

---

## 九、问题管理

### 9.1 问题等级定义

| 等级 | 定义 | 处理时间 |
|------|------|----------|
| P0 | 阻塞上线，必须修复 | 立即 |
| P1 | 影响可用性，应尽快修复 | 1天内 |
| P2 | 体验问题，可后续优化 | 1周内 |

### 9.2 问题跟踪流程

1. **发现**: 测试工程师发现问题
2. **记录**: 在 Issue 系统创建 Issue
3. **分配**: 分配给对应开发者
4. **修复**: 开发者修复问题
5. **验证**: 测试工程师验证修复
6. **关闭**: 确认修复后关闭 Issue

---

## 十、总结

### 10.1 验收标准清单

| 阶段 | 用例数 | 通过标准 | 关键检查项 |
|------|--------|----------|------------|
| Phase 0 | 10 | 全部通过 | CORS、认证、输入验证 |
| Phase 1 | 8 | 全部通过 | 连接池、数据隔离、迁移 |
| Phase 2 | 7 | 全部通过 | 分页、异步、导出 |
| Phase 3 | 9 | 全部通过 | 覆盖率、监控、文档 |
| Phase 4 | 25+ | 全部通过 | 上线检查清单 |
| **总计** | **59+** | - | - |

### 10.2 验收原则

1. **零容忍**: P0 问题必须修复才能通过
2. **可回滚**: 上线失败必须能快速回滚
3. **可监控**: 上线后必须能监控系统状态
4. **可追溯**: 所有变更必须有记录

### 10.3 成功标准

- 所有 P0 问题清零
- 所有 P1 问题 ≤ 5个
- 验收用例通过率 > 95%
- 上线检查清单全部通过
- 压力测试达标
- 监控告警正常

---

**文档版本**: v1.0
**创建日期**: 2026-08-27
**最后更新**: 2026-08-27
**负责人**: 测试工程师 + 架构师

# JobCraft 功能测试计划

## 1. 测试目标

验证 JobCraft 求职助手的核心链路是否完整可用：

- 经历卡管理（五段式结构、按工作经历分组）
- 岗位分析（JD 解析、匹配度、缺口分析、经历卡优化、定制简历）
- 面试准备（匹配度、个人介绍、维度问题库、完整文字版）
- 前后端 API 联通

## 2. 测试环境

### 2.1 启动依赖

```powershell
# 1. 启动 MySQL
cd d:\A-pythonProject\AI-learning\multi-agent\jobcraft
docker compose -f docker\docker-compose.yaml up -d

# 2. 启动后端
.\.venv\Scripts\python.exe -m uvicorn app.api.server:app --reload --reload-dir app --host 0.0.0.0 --port 8000

# 3. 启动前端
cd frontend-jobcraft
npm run dev
```

### 2.2 访问地址

- 前端：`http://localhost:5175/`
- 后端 Swagger：`http://localhost:8000/docs`

### 2.3 配置文件

确保 `.env` 中已配置：

```env
MYSQL_HOST=localhost
MYSQL_PORT=3307
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=jobcraft
# LLM KEY（当前使用 dashscope / qwen）
DASHSCOPE_API_KEY=your_key
```

## 3. 自动化测试

### 3.1 快速测试（不调用 LLM，约 10-20 秒）

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_jobcraft_e2e.py -v -m "not slow"
```

预期结果：5 passed

覆盖用例：

| 用例 | 说明 |
|------|------|
| test_create_experience_card | 创建含五段式的经历卡 |
| test_list_cards | 列出经历卡 |
| test_update_experience_card | 更新经历卡（PATCH） |
| test_analyze_job_without_cards | 无卡片时岗位分析返回 400 |
| test_interview_prep_without_job | 不存在岗位时返回 400/404 |

### 3.2 完整测试（含 LLM，耗时取决于模型响应）

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_jobcraft_e2e.py -v --runslow
```

覆盖用例：

| 用例 | 说明 |
|------|------|
| test_analyze_job_basic | 岗位分析返回完整结构 |
| test_list_job_analyses | 历史分析列表包含本次分析 |
| test_save_resume | 生成定制简历并下载验证 |
| test_generate_interview_prep | 生成面试准备稿 |
| test_generate_interview_prep_without_card_ids | 不传 card_ids 自动复用关联卡片 |
| test_get_interview_prep | 读取历史面试准备稿 |

如果 LLM 响应慢导致超时，可加大超时：

```powershell
$env:JOBCRAFT_TEST_LLM_TIMEOUT="600"
.\.venv\Scripts\python.exe -m pytest tests\test_jobcraft_e2e.py -v --runslow
```

## 4. 手动功能测试

### 4.1 经历梳理页面

| 步骤 | 操作 | 预期结果 |
|------|------|----------|
| 4.1.1 | 打开 `http://localhost:5175/#/experience` | 页面加载，左侧菜单「经历梳理」高亮 |
| 4.1.2 | 点击「新建工作内容」 | 弹出 Modal，包含公司/角色/任职时间/标题/一句话总结/标签/行业/角色类型/量化指标/五段式字段 |
| 4.1.3 | 填写五段式内容并保存 | 卡片按公司+角色+时间分组展示 |
| 4.1.4 | 点击卡片上的编辑图标 | Modal 回填当前卡片内容 |
| 4.1.5 | 修改 summary 并保存 | 卡片 summary 更新 |
| 4.1.6 | 上传简历（PDF/Word/MD/TXT） | 后端解析并抽取经历卡，页面刷新后展示 |
| 4.1.7 | 点击删除图标并确认 | 卡片被移除，数据库中删除 |

### 4.2 岗位分析页面

| 步骤 | 操作 | 预期结果 |
|------|------|----------|
| 4.2.1 | 打开 `http://localhost:5175/#/job` | 显示 Step 1：公司背调 |
| 4.2.2 | 输入公司名称，点击「公司背调」 | 展示公司画像（行业、规模、业务等） |
| 4.2.3 | 点击「下一步：JD 分析」 | 进入 Step 2：JD 输入与卡片选择 |
| 4.2.4 | 输入岗位名称、JD 文本，勾选经历卡，点击「开始分析」 | 显示分析 loading，完成后展示 4 个 Tab |
| 4.2.5 | 切换到「岗位画像」Tab | 展示 ATS 解析结果和公司画像 |
| 4.2.6 | 切换到「匹配与缺口」Tab | 展示匹配度、缺口列表、参考改写、原文对比 |
| 4.2.7 | 切换到「经历卡优化」Tab | 可编辑每张卡片的 optimization，可勾选是否选入简历 |
| 4.2.8 | 切换到「定制简历」Tab | 显示匹配度和已选数量，可预览 Markdown / 生成并下载 |
| 4.2.9 | 点击「生成并下载 .md 简历」 | 跳转 Step 3，展示下载链接 |
| 4.2.10 | 点击 Step 3 的「去面试准备页」 | 跳转到 `http://localhost:5175/#/interview` |

### 4.3 面试准备页面

| 步骤 | 操作 | 预期结果 |
|------|------|----------|
| 4.3.1 | 打开 `http://localhost:5175/#/interview` | 页面加载，左侧菜单「面试准备」高亮 |
| 4.3.2 | 选择岗位分析、面试轮次 | 下拉框正常填充 |
| 4.3.3 | 点击「生成面试准备」 | 调用后端，显示匹配度、个人介绍、维度问题库、完整文字版、HTML 预览 |
| 4.3.4 | 查看「维度问题库」 | 问题按维度分组，每个问题显示绑定卡片和深挖回答 |
| 4.3.5 | 查看「完整文字版」 | 显示按卡片组织的无时间限制叙述 |
| 4.3.6 | 查看「HTML 预览」 | iframe 中渲染格式化面试稿 |

## 5. API 接口清单

| 方法 | 路径 | 用途 |
|------|------|------|
| POST | `/api/jobcraft/experience/upload` | 上传简历提取经历卡 |
| GET | `/api/jobcraft/experience/cards` | 列出经历卡 |
| POST | `/api/jobcraft/experience/cards` | 创建经历卡 |
| PATCH | `/api/jobcraft/experience/cards/{id}` | 更新经历卡 |
| DELETE | `/api/jobcraft/experience/cards/{id}` | 删除经历卡 |
| POST | `/api/jobcraft/company/search` | 公司背调 |
| POST | `/api/jobcraft/job/analyze` | 岗位分析 |
| GET | `/api/jobcraft/job/analyses` | 列出岗位分析 |
| POST | `/api/jobcraft/job/save-resume` | 生成定制简历 |
| GET | `/api/jobcraft/resume/download` | 下载简历 |
| POST | `/api/jobcraft/job/{id}/interview-prep` | 生成面试准备稿 |
| GET | `/api/jobcraft/job/{id}/interview-prep` | 获取面试准备稿 |

## 6. 常见问题排查

### 6.1 前端报错 404

现象：`Request failed: 404 {"detail":"Not Found"}`

原因：前端 `api.ts` 中的请求路径缺少 `/jobcraft` 前缀。

检查点：

- `listCards` 应请求 `/api/jobcraft/experience/cards`
- `analyzeJob` 应请求 `/api/jobcraft/job/analyze`
- `generateInterviewPrep` 应请求 `/api/jobcraft/job/{id}/interview-prep`

修复：统一在 `src/api.ts` 中使用 `/api/jobcraft/*` 前缀。

### 6.2 后端 analyze 接口超时

现象：岗位分析一直 loading，最终超时。

排查：

- 检查 `.env` 中 LLM API Key 是否配置正确
- 检查网络是否能访问 LLM 服务
- 测试脚本加大 `JOBCRAFT_TEST_LLM_TIMEOUT`

### 6.3 数据库表字段缺失

现象：接口报错 `Unknown column 'xxx' in 'field list'`。

原因：使用了旧数据库，缺少五段式或 dimension_requirements 字段。

修复：

```sql
-- 重新执行初始化脚本
docker exec -i mysql-jobcraft mysql -uroot -p jobcraft < docker/mysql/jobcraft.sql
```

或重启后端，db_tools.py 中的 `_ensure_*_columns` 会自动添加缺失字段。

### 6.4 前端页面空白

排查步骤：

1. 检查浏览器控制台是否有 JS 报错
2. 检查 `npm run dev` 是否正常运行
3. 检查 Vite proxy 是否配置 `/api` 到 `http://localhost:8000`
4. 检查后端 `http://localhost:8000/docs` 是否能访问

## 7. 测试通过标准

- [ ] 快速自动化测试 5/5 passed
- [ ] 手动经历梳理页面：新建/编辑/删除/上传均正常
- [ ] 手动岗位分析页面：4 个 Tab 均正常展示
- [ ] 手动面试准备页面：能生成并展示面试稿
- [ ] 后端 Swagger 所有 JobCraft 接口均可正常调用
- [ ] 无 404/500 报错

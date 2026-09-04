# TODO - 认证闭环（方案 A：强制 JWT + 登录/注册）

## 目标
所有业务端点强制 JWT 认证、注册加固、前端登录/注册闭环，移除 default-login 后门。

## 任务清单
- [x] 业务端点全部改为 `Depends(get_current_user)`（experience/job_analysis/submission/interview_prep/interview_review/tasks）
- [x] 注册加固：密码强度（≥8 含字母+数字）、邮箱格式正则、邮箱唯一性
- [x] 移除 experience card create 的 user_id 入参；question-table 端点去 body 参数
- [x] db_user 提供 `get_user_by_email` 并 re-export
- [x] 测试：test_auth_security（56）、_AuthedClient 包装器、e2e 注册一次性用户
- [x] 前端 auth.ts：login/register、autoLogin 校验 token；Context 暴露 isAuthenticated/login/register/logout 并修 loadDashboard 越权
- [x] AuthPage 登录/注册页 + App 认证门 + TopHeader 登出实连
- [x] 移除后端 `POST /api/auth/default-login`
- [x] 验证：前端 build + tsc 通过；后端 ruff + pytest 315 passed/6 skipped（提交快照同样通过）
- [x] commit 1：`8599e80` feat(auth): enforce JWT on business endpoints and harden registration
- [x] commit 2：`6a0f121` feat(frontend): add login and register flow; remove default-login
- [x] 已 push 至 GitHub（`6a0f121`；含基线/路线图文档）

## 开始时间: 2026-09-02
## 完成时间: 2026-09-02

## 状态
- [x] 进行中
- [x] 已完成
- [x] 已提交（2 commits）
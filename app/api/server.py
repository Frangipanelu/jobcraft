"""
JobCraft 求职助手 — FastAPI 接口层

承载所有 JobCraft REST 接口，只做轻量参数校验和 Workflow 调用。
"""

import logging
import os
import shutil
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from app.tools import (
    db_tools,
    jobcraft_resume,
)
from app.workflows.job_analysis_flow import run_job_analysis_workflow
from app.schemas.jobcraft import (
    ExperienceCardCreate,
    ExperienceCardUpdate,
)
from app.tools.upload_file_read_tool import read_file_content
from app.auth.router import router as auth_router
from app.auth.dependencies import get_current_user, get_optional_user
from app.monitoring import setup_monitoring


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield


# 当前文件位于 app/api/server.py, project_root 应上溯 2 层到 jobcraft
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent.parent

app = FastAPI(title="JobCraft API", lifespan=lifespan)

# 注册认证路由
app.include_router(auth_router)

# 设置监控
setup_monitoring(app)

# 统一 logger: 让 /api/jobcraft/* 路由里的 logger.exception 真正写到 stderr
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("jobcraft.api")

# output 目录用于存放生成文件
output_dir = project_root / "output"
output_dir.mkdir(exist_ok=True)

# updated 暂存用户上传文件
updated_dir = project_root / "updated"
updated_dir.mkdir(exist_ok=True)

# CORS 配置：从环境变量读取允许的来源，限制方法和头
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:5174,http://localhost:5175").split(",")
ALLOWED_METHODS = ["GET", "POST", "PATCH", "DELETE", "OPTIONS"]
ALLOWED_HEADERS = ["Authorization", "Content-Type", "Accept"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=ALLOWED_METHODS,
    allow_headers=ALLOWED_HEADERS,
)


class APIResponse:
    """统一 API 响应结构: {code, msg, data}"""

    @staticmethod
    def success(data: Optional[dict] = None, msg: str = "success") -> dict:
        return {"code": 0, "msg": msg, "data": data or {}}

    @staticmethod
    def error(code: int, msg: str, data: Optional[dict] = None) -> dict:
        return {"code": code, "msg": msg, "data": data or {}}


@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    """统一处理 FastAPI HTTPException，返回 {code, msg, data}"""
    return JSONResponse(
        status_code=exc.status_code,
        content=APIResponse.error(code=exc.status_code, msg=exc.detail),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    """统一处理请求参数校验失败（422），返回 {code, msg, data}"""
    errors = exc.errors()
    first = errors[0] if errors else {}
    loc = " -> ".join(str(x) for x in first.get("loc", []))
    msg = f"参数校验失败 [{loc}]: {first.get('msg', '未知错误')}"
    return JSONResponse(
        status_code=422,
        content=APIResponse.error(code=422, msg=msg, data={"errors": errors}),
    )


@app.exception_handler(Exception)
async def general_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    """兜底异常处理器，防止未捕获异常直接暴露堆栈"""
    logger.exception("未捕获的服务器异常")
    return JSONResponse(
        status_code=500,
        content=APIResponse.error(code=500, msg="服务器内部错误，请稍后重试"),
    )


# ============================================================
#  健康检查与监控
# ============================================================


@app.get("/health")
async def health_check():
    """
    健康检查接口

    用于负载均衡器和监控系统检查服务状态。
    """
    return {
        "status": "healthy",
        "service": "jobcraft-api",
        "version": "0.6.0",
    }


@app.get("/api/jobcraft/health")
async def api_health_check():
    """
    API 健康检查接口

    包含数据库连接检查。
    """
    try:
        # 检查数据库连接
        from app.db import engine
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        db_status = "healthy"
    except Exception as e:
        logger.warning(f"数据库健康检查失败: {e}")
        db_status = "unhealthy"

    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "service": "jobcraft-api",
        "version": "0.6.0",
        "checks": {
            "database": db_status,
        },
    }


# ============================================================
#  异步任务管理
# ============================================================


@app.post("/api/jobcraft/tasks/submit")
async def submit_task(payload: Dict[str, Any]):
    """
    提交异步任务

    支持的任务类型：
    - resume_generate: 简历生成
    - interview_prep: 面试准备
    - export_pdf: PDF导出
    """
    try:
        from app.tasks import get_task_manager
        from app.tasks.handlers import get_task_handler

        task_type = payload.get("task_type")
        if not task_type:
            raise HTTPException(status_code=400, detail="task_type 不能为空")

        handler = get_task_handler(task_type)
        if not handler:
            raise HTTPException(status_code=400, detail=f"不支持的任务类型: {task_type}")

        manager = get_task_manager()
        task_id = manager.submit_task(
            task_type=task_type,
            params=payload.get("params", {}),
        )

        return {
            "task_id": task_id,
            "task_type": task_type,
            "status": "pending",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"提交任务失败: {e}")


@app.get("/api/jobcraft/tasks/{task_id}")
async def get_task_status(task_id: str):
    """
    查询任务状态

    :param task_id: 任务 ID
    :return: 任务信息
    """
    try:
        from app.tasks import get_task_manager

        manager = get_task_manager()
        task = manager.get_task(task_id)

        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")

        return task.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询任务失败: {e}")


@app.post("/api/jobcraft/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    """
    取消任务

    :param task_id: 任务 ID
    :return: 操作结果
    """
    try:
        from app.tasks import get_task_manager

        manager = get_task_manager()
        success = manager.cancel_task(task_id)

        if not success:
            raise HTTPException(
                status_code=400,
                detail="任务不存在或已完成，无法取消"
            )

        return {"message": "任务已取消"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"取消任务失败: {e}")


@app.get("/api/jobcraft/tasks")
async def list_tasks(
    status: Optional[str] = None,
    limit: int = 50,
):
    """
    列出任务

    :param status: 过滤状态（pending/running/completed/failed/cancelled）
    :param limit: 返回数量限制
    :return: 任务列表
    """
    try:
        from app.tasks import get_task_manager
        from app.tasks.worker import TaskStatus

        manager = get_task_manager()

        # 转换状态参数
        task_status = None
        if status:
            try:
                task_status = TaskStatus(status)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"无效的状态值: {status}"
                )

        tasks = manager.list_tasks(status=task_status, limit=limit)

        return {
            "items": [task.to_dict() for task in tasks],
            "total": len(tasks),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"列出任务失败: {e}")


# ============================================================
#  JobCraft 求职助手 REST 接口
# ============================================================


class JobAnalyzePayload(BaseModel):
    """岗位分析请求体（旧版，逐步废弃）"""

    user_id: int = 1
    company: str = ""
    position: str
    jd_text: str
    card_ids: List[int]


class ATSRecommendPayload(BaseModel):
    """Step 1: ATS 解析 + 推荐卡片"""

    user_id: int = 1
    company: str
    position: str
    jd_text: str


class GapPolishPayload(BaseModel):
    """Step 2: 缺口分析 + 润色建议"""

    job_analysis_id: int
    user_id: int = 1
    card_ids: List[int]


class SaveCardVersionPayload(BaseModel):
    """保存卡片定制版本"""

    user_id: int = 1
    card_id: int
    source_type: str = "job_analysis"  # 'job_analysis' | 'interview_review'
    source_id: int
    raw_text: str
    title: Optional[str] = None
    tags: Optional[List[str]] = None
    note: Optional[str] = None


class ATSOnlyPayload(BaseModel):
    """只做 ATS 解析（轻量）"""

    user_id: int = 1
    position: str = ""
    jd_text: str


class SaveResumePayload(BaseModel):
    """生成定制简历请求体"""

    job_analysis_id: int
    selected_card_ids: List[int]
    # {card_id: edited_text}，用户编辑后的终稿
    card_versions: Optional[Dict[int, str]] = None
    # 简历头部个人信息（姓名/电话/邮箱等）
    personal_info: Optional[Dict[str, Any]] = None


class InterviewPrepPayload(BaseModel):
    """生成面试逐字稿请求体"""

    user_id: int = 1
    round_type: str = "技术面"  # 技术面 / 业务面 / HR 面
    card_ids: List[int]
    submission_id: Optional[int] = None


@app.post("/api/jobcraft/experience/upload")
async def jobcraft_experience_upload(
    file: UploadFile = File(...),
    user_id: int = Form(1),
):
    """
    上传简历 → 创建经历卡 (raw_text 存储, 不强制抽取)

    流程:
    1. 校验文件格式与大小
    2. 读取文件文本
    3. 创建一张经历卡, raw_text 存全文
    4. AI 自动抽取结构化缓存 (可选,异常不影响主流程)
    5. 返回新创建的经历卡

    错误情况:
    - 文件 > 10MB
    - 不支持的格式 (.doc / .pages 等)
    - 解析后文本 < 50 字符
    """
    MAX_BYTES = 10 * 1024 * 1024
    if file.size is not None and file.size > MAX_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"文件过大 ({file.size / 1024 / 1024:.1f}MB > 10MB)",
        )

    upload_id = uuid.uuid4().hex[:12]
    target_dir = updated_dir / f"jobcraft_{upload_id}"
    target_dir.mkdir(parents=True, exist_ok=True)
    saved_path = target_dir / file.filename
    with saved_path.open("wb") as buf:
        shutil.copyfileobj(file.file, buf)

    SUPPORTED_EXTS = {".pdf", ".docx", ".md", ".txt"}
    ext = saved_path.suffix.lower()
    if ext not in SUPPORTED_EXTS:
        raise HTTPException(
            status_code=400,
            detail=f"暂不支持「{ext or '无后缀'}」格式, 请使用 PDF / DOCX / MD / TXT",
        )

    from app.api.context import set_session_context, reset_session_context

    token = set_session_context(str(target_dir))
    try:
        resume_text = read_file_content.invoke(str(saved_path))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"文件读取失败: {e}")
    finally:
        reset_session_context(token)

    if not resume_text or not resume_text.strip():
        raise HTTPException(status_code=400, detail="文件内容为空")
    if resume_text.startswith("错误"):
        raise HTTPException(status_code=400, detail=resume_text)
    if len(resume_text.strip()) < 50:
        raise HTTPException(
            status_code=400,
            detail="内容过少 (可能为扫描件)，请使用纯文本简历",
        )

    # AI 解析简历 → 多段经历
    try:
        from app.workflows.extract_flow import run_parse_resume_entries_workflow

        entries = run_parse_resume_entries_workflow(resume_text.strip())
    except Exception:
        logger.warning("简历解析失败，降级为单卡")
        entries = []

    # 创建经历卡：逐段原文存 raw_text，识别 card_type，同公司+同岗位去重
    created_cards = []
    seen: set = set()
    try:
        if entries:
            for ent in entries:
                company = (ent.get("company") or "").strip()
                role = (ent.get("role") or "").strip()
                # 去重：同公司 + 同岗位（active 卡）只保留最原始真实的一份
                dedup_key = f"{company}::{role}"
                if company and dedup_key in seen:
                    continue
                existing = db_tools.find_card_by_company_role(user_id, company, role)
                if existing:
                    seen.add(dedup_key)
                    continue
                seen.add(dedup_key)
                card_data = {
                    "user_id": user_id,
                    "title": ent.get("title")
                    or role
                    or company
                    or file.filename
                    or "未命名经历",
                    "raw_text": db_tools._rebuild_entry_text(ent),
                    "company": company,
                    "role": role,
                    "period": ent.get("period", ""),
                    "card_type": (ent.get("card_type") or "work"),
                    "source": "resume_upload",
                    "tags": [],
                    "ai_structured": {
                        "summary": ent.get("summary", ""),
                        "achievements": ent.get("achievements", []),
                    },
                }
                card_id = db_tools.insert_card(card_data)
                card = db_tools.get_card(card_id)
                if card:
                    created_cards.append(card)
        else:
            # 降级：整份简历创建一张卡片，AI 结构化抽取
            card_data = {
                "user_id": user_id,
                "title": file.filename or "未命名经历",
                "raw_text": resume_text.strip(),
                "source": "resume_upload",
            }
            card_id = db_tools.insert_card(card_data)
            card = db_tools.get_card(card_id)
            if card:
                try:
                    from app.workflows.extract_flow import (
                        run_extract_structured_workflow,
                        run_recommend_tags_workflow,
                    )

                    cache = run_extract_structured_workflow(resume_text.strip())
                    if cache:
                        db_tools.update_card(card_id, {"ai_structured": cache})
                    tags = run_recommend_tags_workflow(resume_text.strip())
                    if tags:
                        db_tools.update_card(card_id, {"tags": tags})
                except Exception:
                    logger.warning("自动结构化抽取失败")
                created_cards.append(card)

        return {"cards": created_cards}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建经历卡失败: {e}")


@app.get("/api/jobcraft/experience/cards")
def jobcraft_experience_list(
    user_id: int = 1,
    include_inactive: bool = False,
    page: int = 1,
    page_size: int = 20,
):
    """
    列出用户经历卡（支持分页）

    :param user_id: 用户 ID
    :param include_inactive: 是否包含归档卡片
    :param page: 页码（从1开始）
    :param page_size: 每页数量（1-100）
    :return: 分页后的经历卡列表
    """
    try:
        # 参数校验
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 20
        if page_size > 100:
            page_size = 100

        # 计算偏移量
        offset = (page - 1) * page_size

        # 获取总数和数据
        total = db_tools.count_cards(user_id, include_inactive)
        cards = db_tools.list_cards_paginated(user_id, include_inactive, offset, page_size)

        # 计算总页数
        total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0

        return {
            "items": cards,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {e}")


@app.get("/api/jobcraft/experience/cards/search")
def jobcraft_experience_search(
    q: str,
    user_id: int = 1,
    include_inactive: bool = False,
    page: int = 1,
    page_size: int = 20,
):
    """
    搜索用户经历卡

    支持按标题、公司、角色、标签、内容进行全文搜索。

    :param q: 搜索关键词
    :param user_id: 用户 ID
    :param include_inactive: 是否包含归档卡片
    :param page: 页码（从1开始）
    :param page_size: 每页数量（1-100）
    :return: 搜索结果（分页格式）
    """
    try:
        # 参数校验
        if not q or not q.strip():
            raise HTTPException(status_code=400, detail="搜索关键词不能为空")
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 20
        if page_size > 100:
            page_size = 100

        # 计算偏移量
        offset = (page - 1) * page_size

        # 获取搜索结果总数和数据
        total = db_tools.count_search_cards(user_id, q, include_inactive)
        cards = db_tools.search_cards(user_id, q, include_inactive, offset, page_size)

        # 计算总页数
        total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0

        return {
            "items": cards,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "query": q,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"搜索失败: {e}")


@app.get("/api/jobcraft/experience/export")
def jobcraft_experience_export(
    user_id: int = 1,
    card_ids: Optional[List[int]] = None,
    format: str = "json",
):
    """
    导出用户经历卡

    支持导出格式：
    - json: JSON 格式（默认）
    - csv: CSV 格式
    - markdown: Markdown 格式

    :param user_id: 用户 ID
    :param card_ids: 要导出的卡片 ID 列表（为空则导出全部）
    :param format: 导出格式
    :return: 导出数据
    """
    try:
        # 获取要导出的卡片
        if card_ids:
            cards = [db_tools.get_card(cid) for cid in card_ids if db_tools.get_card(cid)]
        else:
            cards = db_tools.list_cards(user_id, include_inactive=True)

        if not cards:
            raise HTTPException(status_code=404, detail="没有可导出的经历卡")

        # 根据格式返回
        if format == "json":
            return {
                "format": "json",
                "count": len(cards),
                "data": cards,
            }

        elif format == "csv":
            # 构建 CSV 内容
            import csv
            import io

            output = io.StringIO()
            writer = csv.writer(output)

            # 写入表头
            headers = ["id", "company", "role", "period", "title", "tags", "is_active", "created_at"]
            writer.writerow(headers)

            # 写入数据
            for card in cards:
                row = [
                    card.get("id", ""),
                    card.get("company", ""),
                    card.get("role", ""),
                    card.get("period", ""),
                    card.get("title", ""),
                    ",".join(card.get("tags", [])),
                    card.get("is_active", True),
                    card.get("created_at", ""),
                ]
                writer.writerow(row)

            return {
                "format": "csv",
                "count": len(cards),
                "content": output.getvalue(),
                "filename": f"experience_cards_{user_id}.csv",
            }

        elif format == "markdown":
            # 构建 Markdown 内容
            md_lines = ["# 经历卡导出\n"]
            md_lines.append(f"导出时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            md_lines.append(f"用户ID: {user_id}\n")
            md_lines.append(f"卡片数量: {len(cards)}\n\n")

            for card in cards:
                md_lines.append(f"## {card.get('company', '未知公司')} - {card.get('role', '未知岗位')}\n")
                md_lines.append(f"- **时间段**: {card.get('period', '未知')}\n")
                md_lines.append(f"- **标题**: {card.get('title', '无标题')}\n")
                md_lines.append(f"- **标签**: {', '.join(card.get('tags', []))}\n")
                md_lines.append(f"- **状态**: {'活跃' if card.get('is_active') else '归档'}\n")
                if card.get("raw_text"):
                    md_lines.append(f"\n### 详细内容\n\n{card['raw_text']}\n")
                md_lines.append("\n---\n\n")

            return {
                "format": "markdown",
                "count": len(cards),
                "content": "\n".join(md_lines),
                "filename": f"experience_cards_{user_id}.md",
            }

        else:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的导出格式: {format}，支持: json, csv, markdown"
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导出失败: {e}")


@app.post("/api/jobcraft/experience/cards/batch")
def jobcraft_experience_batch(payload: Dict[str, Any]):
    """
    批量操作经历卡

    支持的操作类型：
    - archive: 批量归档
    - restore: 批量恢复
    - delete: 批量删除
    - tag: 批量添加标签

    请求体示例：
    {
        "action": "archive",
        "card_ids": [1, 2, 3],
        "params": {}
    }
    """
    try:
        action = payload.get("action")
        card_ids = payload.get("card_ids", [])
        params = payload.get("params", {})

        if not action:
            raise HTTPException(status_code=400, detail="action 不能为空")
        if not card_ids:
            raise HTTPException(status_code=400, detail="card_ids 不能为空")

        results = {"success": [], "failed": []}

        if action == "archive":
            # 批量归档
            for card_id in card_ids:
                try:
                    ok = db_tools.update_card(card_id, {"is_active": False})
                    if ok:
                        results["success"].append(card_id)
                    else:
                        results["failed"].append({"card_id": card_id, "reason": "卡片不存在"})
                except Exception as e:
                    results["failed"].append({"card_id": card_id, "reason": str(e)})

        elif action == "restore":
            # 批量恢复
            for card_id in card_ids:
                try:
                    ok = db_tools.update_card(card_id, {"is_active": True})
                    if ok:
                        results["success"].append(card_id)
                    else:
                        results["failed"].append({"card_id": card_id, "reason": "卡片不存在"})
                except Exception as e:
                    results["failed"].append({"card_id": card_id, "reason": str(e)})

        elif action == "delete":
            # 批量删除
            for card_id in card_ids:
                try:
                    ok = db_tools.delete_card(card_id)
                    if ok:
                        results["success"].append(card_id)
                    else:
                        results["failed"].append({"card_id": card_id, "reason": "卡片不存在"})
                except Exception as e:
                    results["failed"].append({"card_id": card_id, "reason": str(e)})

        elif action == "tag":
            # 批量添加标签
            tags_to_add = params.get("tags", [])
            if not tags_to_add:
                raise HTTPException(status_code=400, detail="tags 不能为空")

            for card_id in card_ids:
                try:
                    card = db_tools.get_card(card_id)
                    if not card:
                        results["failed"].append({"card_id": card_id, "reason": "卡片不存在"})
                        continue

                    existing_tags = card.get("tags", [])
                    new_tags = list(set(existing_tags + tags_to_add))
                    ok = db_tools.update_card(card_id, {"tags": new_tags})

                    if ok:
                        results["success"].append(card_id)
                    else:
                        results["failed"].append({"card_id": card_id, "reason": "更新失败"})
                except Exception as e:
                    results["failed"].append({"card_id": card_id, "reason": str(e)})

        else:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的操作类型: {action}，支持: archive, restore, delete, tag"
            )

        return {
            "action": action,
            "total": len(card_ids),
            "success_count": len(results["success"]),
            "failed_count": len(results["failed"]),
            "results": results,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"批量操作失败: {e}")


@app.get("/api/jobcraft/experience/cards/{card_id}/versions")
def jobcraft_experience_versions(card_id: int):
    """
    获取经历卡版本历史

    :param card_id: 卡片 ID
    :return: 版本历史列表
    """
    try:
        # 检查卡片是否存在
        card = db_tools.get_card(card_id)
        if not card:
            raise HTTPException(status_code=404, detail="卡片不存在")

        # 获取版本历史
        versions = db_tools.get_card_versions_by_card_id(card_id)

        return {
            "card_id": card_id,
            "versions": versions,
            "total": len(versions),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取版本历史失败: {e}")


@app.post("/api/jobcraft/experience/cards/{card_id}/versions")
def jobcraft_experience_create_version(card_id: int, payload: Dict[str, Any]):
    """
    创建经历卡新版本

    :param card_id: 卡片 ID
    :param payload: 版本信息
    :return: 新创建的版本
    """
    try:
        # 检查卡片是否存在
        card = db_tools.get_card(card_id)
        if not card:
            raise HTTPException(status_code=404, detail="卡片不存在")

        # 构建版本数据
        version_data = {
            "card_id": card_id,
            "version_type": payload.get("version_type", "manual"),
            "source_type": payload.get("source_type", "manual"),
            "source_id": payload.get("source_id", 0),
            "title": payload.get("title", card.get("title", "")),
            "raw_text": payload.get("raw_text", card.get("raw_text", "")),
            "tags": payload.get("tags", card.get("tags", [])),
            "note": payload.get("note", ""),
        }

        # 创建版本
        version_id = db_tools.insert_card_version(version_data)

        return {
            "version_id": version_id,
            "message": "版本创建成功",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建版本失败: {e}")


@app.post("/api/jobcraft/experience/cards")
def jobcraft_experience_create(payload: ExperienceCardCreate):
    """手动新建一张经历卡 (source=manual)"""
    try:
        data = payload.model_dump()
        data["source"] = "manual"
        card_id = db_tools.insert_card(data)
        return db_tools.get_card(card_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"新建失败: {e}")


@app.patch("/api/jobcraft/experience/cards/{card_id}")
def jobcraft_experience_update(card_id: int, payload: ExperienceCardUpdate):
    """编辑经历卡 (任意字段可选,仅更新传入字段)"""
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    if "user_id" in updates:
        updates.pop("user_id")
    try:
        ok = db_tools.update_card(card_id, updates)
        if not ok:
            raise HTTPException(status_code=404, detail="卡片不存在或无变化")
        return db_tools.get_card(card_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新失败: {e}")


@app.delete("/api/jobcraft/experience/cards/{card_id}")
def jobcraft_experience_delete(card_id: int):
    """
    物理删除一张经历卡 (不可恢复, 会同步清理 experience_job_mapping 关联)

    与 PATCH is_active=False 归档的区别:
      - 归档: 软删除, 可在「显示归档」中恢复
      - 物理删除: 不可恢复, 建议仅在「测试数据 / 重复抽取」时使用
    """
    try:
        ok = db_tools.delete_card(card_id)
        if not ok:
            raise HTTPException(status_code=404, detail="卡片不存在")
        return {"deleted": True, "card_id": card_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败: {e}")


class StructCachePayload(BaseModel):
    """触发结构化缓存生成"""

    user_id: int = 1


@app.post("/api/jobcraft/experience/cards/{card_id}/structure")
def jobcraft_experience_structure(card_id: int, payload: StructCachePayload):
    """
    对一段经历生成/刷新 AI 结构化缓存

    读取 card.raw_text → LLM 抽取 achievements[] → 写入 card.ai_structured
    """
    try:
        card = db_tools.get_card(card_id)
        if not card:
            raise HTTPException(status_code=404, detail="卡片不存在")
        raw_text = card.get("raw_text", "")
        if not raw_text or len(raw_text.strip()) < 20:
            raise HTTPException(
                status_code=400,
                detail="经历内容过短（至少 20 字符），请补充后再试",
            )
        # LLM 抽取
        from app.workflows.extract_flow import run_extract_structured_workflow

        cache = run_extract_structured_workflow(raw_text)
        if not cache:
            raise HTTPException(
                status_code=500,
                detail="AI 结构化抽取失败，请检查经历内容是否清晰完整",
            )
        db_tools.update_card(card_id, {"ai_structured": cache})
        return db_tools.get_card(card_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("结构化抽取失败")
        raise HTTPException(status_code=500, detail=f"结构化抽取失败: {e}")


@app.post("/api/jobcraft/experience/cards/{card_id}/recommend-tags")
def jobcraft_experience_recommend_tags(card_id: int):
    """
    由 LLM 推荐标签（不写库，仅返回推荐列表供用户确认）
    """
    try:
        card = db_tools.get_card(card_id)
        if not card:
            raise HTTPException(status_code=404, detail="卡片不存在")
        from app.workflows.extract_flow import run_recommend_tags_workflow

        tags = run_recommend_tags_workflow(card.get("raw_text", ""))
        return {"tags": tags}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("标签推荐失败")
        raise HTTPException(status_code=500, detail=f"标签推荐失败: {e}")


class BackfillPayload(BaseModel):
    """触发旧数据单卡拆分"""

    user_id: int = 1
    min_chars: int = 100


@app.post("/api/jobcraft/experience/cards/backfill")
def jobcraft_experience_backfill(payload: BackfillPayload):
    """
    把「单卡装下整份简历」的旧数据拆分成多张经历卡

    用 parse_resume_entries 解析出每段经历, 每段新建一张卡;
    原卡归档(is_active=0)可恢复。返回拆分明细供前端展示。
    """
    try:
        from app.workflows.extract_flow import run_backfill_workflow

        result = run_backfill_workflow(payload.user_id, payload.min_chars)
        return result
    except Exception as e:
        logger.exception("卡片回填失败")
        raise HTTPException(status_code=500, detail=f"回填失败: {e}")


# ============================================================
#  新版两步岗位分析（用户已确认）
# ============================================================


@app.post("/api/jobcraft/job/step1-ats-recommend")
def jobcraft_step1_ats_recommend(payload: ATSRecommendPayload):
    """
    Step 1: ATS 解析 + 推荐卡片（合并一次 LLM 调用）

    流程:
      1. 校验 JD
      2. 拉取用户所有经历卡
      3. 合并调用 LLM: ATS 解析 + 卡片推荐
      4. 落库 job_analysis（含 ATS 结果）
      5. 返回 {job_analysis_id, ats, recommended_cards}
    """
    if not payload.jd_text or not payload.jd_text.strip():
        raise HTTPException(status_code=400, detail="JD 文本不能为空")
    if len(payload.jd_text) > 10000:
        raise HTTPException(status_code=400, detail="JD 文本过长")
    try:
        from app.workflows.job_analysis_flow import run_step1_workflow

        all_cards = db_tools.list_cards(payload.user_id, include_inactive=False)
        result = run_step1_workflow(
            user_id=payload.user_id,
            company=payload.company,
            position=payload.position,
            jd_text=payload.jd_text,
            cards=all_cards,
        )

        # 落库 job_analysis（存 ATS + JD）
        job_id = db_tools.insert_job_analysis(
            {
                "user_id": payload.user_id,
                "company": payload.company,
                "position": payload.position or result["ats"].get("job_title", ""),
                "jd_text": payload.jd_text,
                "jd_requirements": result["ats"],
            }
        )

        return {
            "job_analysis_id": job_id,
            "ats": result["ats"],
            "recommended_cards": result["recommended_cards"],
            "all_cards": all_cards,
        }
    except Exception as e:
        logger.exception("ATS+推荐失败")
        raise HTTPException(status_code=500, detail=f"分析失败: {e}")


@app.post("/api/jobcraft/job/step2-gap-polish")
def jobcraft_step2_gap_polish(payload: GapPolishPayload):
    """
    Step 2: 缺口分析 + 润色建议（合并一次 LLM 调用）

    流程:
      1. 从 job_analysis 读取 ATS + JD
      2. 拉取用户勾选的经历卡
      3. 合并调用 LLM: 缺口分析 + 逐卡润色建议
      4. 返回 {per_card, global_suggestions}
      5. 用户在前端逐卡确认/修改后, 调用 /save-card-version 落库
    """
    if not payload.card_ids:
        raise HTTPException(status_code=400, detail="请至少选择 1 张经历卡")
    try:
        from app.workflows.job_analysis_flow import run_step2_workflow

        result = run_step2_workflow(payload.job_analysis_id, payload.card_ids)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("缺口+润色失败")
        raise HTTPException(status_code=500, detail=f"分析失败: {e}")


@app.post("/api/jobcraft/job/save-card-version")
def jobcraft_job_save_card_version(payload: SaveCardVersionPayload):
    """
    保存经历卡定制版本（用户确认润色建议后调用）

    存 card_versions 表, 不修改原卡。
    生成简历时优先读 card_versions 的最新版本。
    """
    if not payload.raw_text or not payload.raw_text.strip():
        raise HTTPException(status_code=400, detail="内容不能为空")
    try:
        version_id = db_tools.insert_card_version(
            {
                "card_id": payload.card_id,
                "version_type": "polished",
                "source_type": payload.source_type,
                "source_id": payload.source_id,
                "title": payload.title,
                "raw_text": payload.raw_text,
                "tags": payload.tags,
                "note": payload.note,
            }
        )
        return {"version_id": version_id, "status": "saved"}
    except Exception as e:
        logger.exception("保存版本失败")
        raise HTTPException(status_code=500, detail=f"保存失败: {e}")


@app.post("/api/jobcraft/job/analyze")
def jobcraft_job_analyze(payload: JobAnalyzePayload):
    """
    岗位分析（旧版兼容，推荐使用新版 step1 + step2 接口）
    """
    if not payload.company or not payload.company.strip():
        raise HTTPException(status_code=400, detail="公司名不能为空")
    if not payload.position or not payload.position.strip():
        raise HTTPException(status_code=400, detail="岗位名不能为空")
    if not payload.jd_text or not payload.jd_text.strip():
        raise HTTPException(status_code=400, detail="JD 文本不能为空")
    if len(payload.jd_text) > 10000:
        raise HTTPException(
            status_code=400, detail=f"JD 文本过长 ({len(payload.jd_text)} 字)"
        )
    if not payload.card_ids:
        raise HTTPException(status_code=400, detail="请至少选择 1 张经历卡")
    try:
        return run_job_analysis_workflow(
            user_id=payload.user_id,
            company=payload.company,
            position=payload.position,
            jd_text=payload.jd_text,
            card_ids=payload.card_ids,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("岗位分析失败")
        raise HTTPException(status_code=500, detail=f"岗位分析失败: {e}")


@app.get("/api/jobcraft/job/analyses")
def jobcraft_job_list(user_id: int = 1, limit: int = 20):
    """列出用户历史岗位分析 (按时间倒序)"""
    try:
        return {"analyses": db_tools.list_job_analyses(user_id, limit)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {e}")


@app.get("/api/jobcraft/job/analyze/{job_id}")
def jobcraft_job_get(job_id: int):
    """获取单条岗位分析详情"""
    try:
        analysis = db_tools.get_job_analysis(job_id)
        if not analysis:
            raise HTTPException(status_code=404, detail="记录不存在")
        return analysis
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {e}")


@app.delete("/api/jobcraft/job/analyze/{job_id}")
def jobcraft_job_delete(job_id: int):
    """删除岗位分析记录"""
    try:
        ok = db_tools.delete_job_analysis(job_id)
        if not ok:
            raise HTTPException(status_code=404, detail="记录不存在")
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败: {e}")


@app.post("/api/jobcraft/job/save-resume")
def jobcraft_job_save_resume(payload: SaveResumePayload):
    """
    生成定制简历（纯模板拼装，无 LLM）

    输出 Markdown + 预设排版 HTML（前端预览 + 打印导出 PDF）。
    落盘到 output/job_resume/，写 experience_job_mapping
    """
    if not payload.selected_card_ids:
        raise HTTPException(status_code=400, detail="请至少选择 1 张经历卡")
    try:
        return jobcraft_resume.generate_resume(
            job_analysis_id=payload.job_analysis_id,
            selected_card_ids=payload.selected_card_ids,
            card_versions=payload.card_versions,
            personal_info=payload.personal_info,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成简历失败: {e}")


def _get_previous_review_summary(submission_id: Optional[int]) -> Optional[str]:
    """查 submission 下最新复盘记录的[优势][劣势]摘要"""
    if not submission_id:
        return None
    try:
        from app.tools import db_tools

        rows = db_tools.list_interview_records_by_submission(submission_id)
        if not rows:
            return None
        latest = rows[0]
        analysis = latest.get("analysis_json") or {}
        parts = []
        if analysis.get("strengths"):
            parts.append(f"优势：{'、'.join(analysis['strengths'][:3])}")
        if analysis.get("weaknesses"):
            parts.append(f"劣势：{'、'.join(analysis['weaknesses'][:3])}")
        if analysis.get("action_items"):
            parts.append(f"改进项：{'、'.join(analysis['action_items'][:3])}")
        return "\n".join(parts) if parts else None
    except Exception:
        return None


@app.post("/api/jobcraft/job/{job_id}/interview-prep")
def jobcraft_job_interview_prep(job_id: int, payload: InterviewPrepPayload):
    """
    生成面试逐字稿

    基于 JD + 选中经历卡 + 公司调研 + 已投简历 + 面试轮次，生成完整面试逐字稿。
    若 payload.card_ids 为空，则自动复用该岗位分析时选中的经历卡。
    """
    from app.tools import db_tools
    from app.workflows.interview_prep_flow import run_interview_prep_workflow

    card_ids = payload.card_ids
    if not card_ids:
        card_ids = db_tools.get_selected_card_ids_by_job(job_id)
    if not card_ids:
        raise HTTPException(
            status_code=400, detail="该岗位分析未关联经历卡，请从岗位分析页重新分析"
        )

    # 加载增强数据
    company_research = None
    resume_markdown = None
    previous_review_summary = None
    try:
        analysis = db_tools.get_job_analysis(job_id)
        company = (analysis or {}).get("company", "")
        if company:
            from app.agents.company_research_agent import get_or_search_company

            company_research = get_or_search_company(company)

        submission = None
        if payload.submission_id:
            submission = db_tools.get_submission(payload.submission_id)
        elif analysis:
            subs = db_tools.list_submissions(payload.user_id)
            for s in subs:
                if s.get("job_analysis_id") == job_id:
                    submission = db_tools.get_submission(s["id"])
                    break
        if submission:
            resume_markdown = submission.get("resume_markdown")

        previous_review_summary = _get_previous_review_summary(
            payload.submission_id or (submission.get("id") if submission else None)
        )
    except Exception:
        logger.warning("加载面试增强数据失败", exc_info=True)

    try:
        result = run_interview_prep_workflow(
            job_analysis_id=job_id,
            round_type=payload.round_type,
            card_ids=card_ids,
            user_id=payload.user_id,
            submission_id=payload.submission_id,
            company_research=company_research,
            resume_markdown=resume_markdown,
            previous_review_summary=previous_review_summary,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("生成面试稿失败")
        raise HTTPException(status_code=500, detail=f"生成面试稿失败: {e}")


@app.get("/api/jobcraft/job/{job_id}/selected-cards")
def jobcraft_job_get_selected_cards(job_id: int):
    """获取岗位分析时选中的经历卡 ID 列表"""
    try:
        card_ids = db_tools.get_selected_card_ids_by_job(job_id)
        return {"card_ids": card_ids}
    except Exception as e:
        logger.exception("获取选中卡片失败")
        raise HTTPException(status_code=500, detail=f"获取选中卡片失败: {e}")


@app.get("/api/jobcraft/job/{job_id}/interview-prep")
def jobcraft_job_get_interview_prep(job_id: int, user_id: int = 1):
    """获取已保存的面试逐字稿"""
    from app.tools import interview_pre

    try:
        result = interview_pre.get_interview_prep(job_id)
        if not result:
            raise HTTPException(status_code=404, detail="面试稿不存在")
        return result.model_dump()
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("获取面试稿失败")
        raise HTTPException(status_code=500, detail=f"获取面试稿失败: {e}")


@app.get("/api/jobcraft/resume/download")
def jobcraft_resume_download(path: str):
    """
    下载定制简历 (与 /api/download 同样的安全边界: 必须在 output 下)

    单独提供便于前端区分下载类别
    """
    try:
        abs_path = Path(path).resolve()
        output_abs = output_dir.resolve()
        if not abs_path.is_relative_to(output_abs):
            return {"error": "拒绝访问: 只能下载 output 目录下的文件"}
    except Exception:
        return {"error": "无效的路径参数"}
    if not abs_path.exists():
        return {"error": "文件不存在"}
    return FileResponse(abs_path, filename=abs_path.name, media_type="text/markdown")


# ============================================================
#  新增(HR 视角重构): 独立端点
# ============================================================


@app.post("/api/jobcraft/job/analyze-ats")
def jobcraft_job_analyze_ats(payload: ATSOnlyPayload):
    """
    只跑 JD ATS 解析（轻量，比 /analyze 快很多）
    返回 {ats_profile}
    """
    if not payload.jd_text or not payload.jd_text.strip():
        raise HTTPException(status_code=400, detail="JD 文本不能为空")
    if len(payload.jd_text) > 10000:
        raise HTTPException(
            status_code=400, detail=f"JD 文本过长 ({len(payload.jd_text)} 字)"
        )
    try:
        from app.workflows.job_analysis_flow import run_analyze_ats_workflow

        ats = run_analyze_ats_workflow(payload.jd_text)
        return {"ats_profile": ats}
    except Exception as e:
        logger.exception("ATS 解析失败")
        raise HTTPException(status_code=500, detail=f"ATS 解析失败: {e}")


@app.post("/api/jobcraft/job/{job_id}/resume-preview")
def jobcraft_job_resume_preview(job_id: int, payload: Optional[dict] = None):
    """
    根据 job_analysis_id 重新生成 Markdown 简历预览

    payload (可选): {selected_card_ids?: List[int], sort_by?: 'score'|'time'}
    不传则用分析时选的卡
    """
    payload = payload or {}
    try:
        from app.tools import db_tools as _db

        analysis = _db.get_job_analysis(job_id)
        if not analysis:
            raise HTTPException(
                status_code=404, detail=f"job_analysis #{job_id} 不存在"
            )
        # 拉卡片
        selected_ids = (
            payload.get("selected_card_ids") or analysis.get("selected_card_ids") or []
        )
        cards = []
        for cid in selected_ids:
            c = _db.get_card(cid)
            if c and c.get("is_active"):
                cards.append(c)
        if not cards:
            raise HTTPException(status_code=400, detail="无可用经历卡")

        # 重新跑 ATS 解析 + 匹配 (因为分析时间可能已过很久, 卡片可能也改过)
        from app.workflows.job_analysis_flow import run_resume_preview_workflow

        result = run_resume_preview_workflow(job_id, selected_ids)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("简历预览失败")
        raise HTTPException(status_code=500, detail=f"简历预览失败: {e}")


# ============================================================
#  投递记录 (resume_submission) CRUD
# ============================================================


class CreateSubmissionPayload(BaseModel):
    user_id: int = 1
    job_analysis_id: Optional[int] = None
    position: str
    company: str = ""
    jd_text: str = ""
    resume_markdown: Optional[str] = None
    is_manual: bool = False
    status: str = "已投递"


class UpdateSubmissionPayload(BaseModel):
    position: Optional[str] = None
    company: Optional[str] = None
    jd_text: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    resume_markdown: Optional[str] = None
    job_analysis_id: Optional[int] = None
    card_version_ids: Optional[List[int]] = None


@app.post("/api/jobcraft/submission")
def jobcraft_submission_create(payload: CreateSubmissionPayload):
    try:
        sid = db_tools.insert_submission(payload.model_dump())
        return db_tools.get_submission(sid)
    except Exception as e:
        logger.exception("创建投递失败")
        raise HTTPException(status_code=500, detail=f"创建投递失败: {e}")


@app.get("/api/jobcraft/submission/{submission_id}")
def jobcraft_submission_get(submission_id: int):
    s = db_tools.get_submission(submission_id)
    if not s:
        raise HTTPException(status_code=404, detail="投递记录不存在")
    return s


@app.patch("/api/jobcraft/submission/{submission_id}")
def jobcraft_submission_update(submission_id: int, payload: UpdateSubmissionPayload):
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    try:
        ok = db_tools.update_submission(submission_id, updates)
        if not ok:
            raise HTTPException(status_code=404, detail="投递记录不存在或无变化")
        return db_tools.get_submission(submission_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新失败: {e}")


@app.delete("/api/jobcraft/submission/{submission_id}")
def jobcraft_submission_delete(submission_id: int):
    try:
        ok = db_tools.delete_submission(submission_id)
        if not ok:
            raise HTTPException(status_code=404, detail="投递记录不存在")
        return {"deleted": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败: {e}")


@app.post("/api/jobcraft/submission/manual")
async def jobcraft_submission_manual(
    file: UploadFile = File(...),
    position: str = Form(...),
    company: str = Form(""),
    jd_text: str = Form(""),
    user_id: int = Form(1),
):
    """
    手动补录投递：上传已投简历 → 解析简历 + 抽取经历卡 → 创建投递记录

    流程:
    1. 读取上传简历文本
    2. 创建经历卡（同 /experience/upload 逻辑）
    3. 创建投递记录（is_manual=true, resume_markdown=简历文本）
    """
    # 读取文件
    MAX_BYTES = 10 * 1024 * 1024
    if file.size is not None and file.size > MAX_BYTES:
        raise HTTPException(status_code=400, detail="文件过大")

    upload_id = uuid.uuid4().hex[:12]
    target_dir = updated_dir / f"jobcraft_manual_{upload_id}"
    target_dir.mkdir(parents=True, exist_ok=True)
    saved_path = target_dir / file.filename
    with saved_path.open("wb") as buf:
        shutil.copyfileobj(file.file, buf)

    SUPPORTED_EXTS = {".pdf", ".docx", ".md", ".txt"}
    ext = saved_path.suffix.lower()
    if ext not in SUPPORTED_EXTS:
        raise HTTPException(status_code=400, detail=f"暂不支持 {ext} 格式")

    from app.api.context import set_session_context, reset_session_context

    token = set_session_context(str(target_dir))
    try:
        resume_text = read_file_content.invoke(str(saved_path))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"文件读取失败: {e}")
    finally:
        reset_session_context(token)

    if not resume_text or not resume_text.strip():
        raise HTTPException(status_code=400, detail="文件内容为空")
    if len(resume_text.strip()) < 50:
        raise HTTPException(status_code=400, detail="内容过少，请使用纯文本简历")

    resume_text = resume_text.strip()

    # 解析简历 → 逐段经历卡（识别 card_type + 去重）
    try:
        from app.workflows.extract_flow import run_parse_resume_entries_workflow

        entries = run_parse_resume_entries_workflow(resume_text)
    except Exception:
        logger.warning("简历解析失败，降级为单卡")
        entries = []

    created_ids: List[int] = []
    seen: set = set()
    try:
        if entries:
            for ent in entries:
                company = (ent.get("company") or "").strip()
                role = (ent.get("role") or "").strip()
                dedup_key = f"{company}::{role}"
                if company and dedup_key in seen:
                    continue
                if db_tools.find_card_by_company_role(user_id, company, role):
                    seen.add(dedup_key)
                    continue
                seen.add(dedup_key)
                card_id = db_tools.insert_card(
                    {
                        "user_id": user_id,
                        "title": ent.get("title") or role or company or file.filename,
                        "raw_text": db_tools._rebuild_entry_text(ent),
                        "company": company,
                        "role": role,
                        "period": ent.get("period", ""),
                        "card_type": (ent.get("card_type") or "work"),
                        "source": "manual_upload",
                        "tags": [],
                        "ai_structured": {
                            "summary": ent.get("summary", ""),
                            "achievements": ent.get("achievements", []),
                        },
                    }
                )
                created_ids.append(card_id)
        else:
            card_data = {
                "user_id": user_id,
                "title": file.filename or "已投简历",
                "raw_text": resume_text,
                "source": "manual_upload",
            }
            card_id = db_tools.insert_card(card_data)
            created_ids.append(card_id)
    except Exception as e:
        logger.exception("创建经历卡失败")
        raise HTTPException(status_code=500, detail=f"创建经历卡失败: {e}")

    # 创建投递记录
    try:
        sid = db_tools.insert_submission(
            {
                "user_id": user_id,
                "position": position,
                "company": company,
                "jd_text": jd_text,
                "resume_markdown": resume_text,
                "is_manual": 1,
                "status": "已投递",
            }
        )
        return db_tools.get_submission(sid)
    except Exception as e:
        logger.exception("创建投递记录失败")
        raise HTTPException(status_code=500, detail=f"创建投递记录失败: {e}")


@app.get("/api/jobcraft/dashboard")
def jobcraft_dashboard(user_id: int = 1):
    """主页：所有投递记录 + 各按钮状态"""
    try:
        return {"submissions": db_tools.get_dashboard(user_id)}
    except Exception as e:
        logger.exception("获取主页数据失败")
        raise HTTPException(status_code=500, detail=f"获取主页数据失败: {e}")


# ============================================================
#  面试复盘
# ============================================================


class InterviewReviewCreatePayload(BaseModel):
    """创建面试复盘请求体"""

    user_id: int = 1
    title: str = ""
    company: str = ""
    position: str = ""
    round_type: str = "业务面"  # 技术面 / 业务面 / HR 面
    job_analysis_id: Optional[int] = None
    submission_id: Optional[int] = None
    raw_text: str


@app.post("/api/jobcraft/interview-review")
def jobcraft_interview_review_create(payload: InterviewReviewCreatePayload):
    """
    创建面试复盘记录并生成问题表（含轻量意图识别）。
    返回 record_id、解析后的 QA 对（已含意图标签）等预览信息，供前端确认/选择问题。
    """
    from app.tools import interview_review

    if not payload.raw_text or not payload.raw_text.strip():
        raise HTTPException(status_code=400, detail="面试记录文本不能为空")
    try:
        record_id = interview_review.create_interview_record(
            user_id=payload.user_id,
            title=payload.title,
            company=payload.company,
            position=payload.position,
            round_type=payload.round_type,
            raw_text=payload.raw_text,
            job_analysis_id=payload.job_analysis_id,
            submission_id=payload.submission_id,
        )
        dialogue = interview_review._parse_dialogue(payload.raw_text)
        from app.workflows.question_table_flow import run_question_table_workflow

        qa_pairs_with_intent = run_question_table_workflow(
            record_id, user_id=payload.user_id
        )
        return {
            "record_id": record_id,
            "status": "parsed",
            "qa_pairs": qa_pairs_with_intent,
            "qa_pair_count": len(qa_pairs_with_intent),
            "dialogue": dialogue,
            "speaker_count": len({d["speaker"] for d in dialogue}),
            "role_counts": {
                "interviewer": sum(
                    1 for d in dialogue if d.get("role") == "interviewer"
                ),
                "candidate": sum(1 for d in dialogue if d.get("role") == "candidate"),
                "unknown": sum(
                    1
                    for d in dialogue
                    if d.get("role") not in ("interviewer", "candidate")
                ),
            },
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("面试复盘创建失败")
        raise HTTPException(status_code=500, detail=f"面试复盘创建失败: {e}")


@app.post("/api/jobcraft/interview-review/upload")
async def jobcraft_interview_review_upload(
    file: UploadFile = File(...),
    user_id: int = Form(1),
    title: str = Form(""),
    company: str = Form(""),
    position: str = Form(""),
    round_type: str = Form("业务面"),
    job_analysis_id: Optional[int] = Form(None),
    submission_id: Optional[int] = Form(None),
):
    """
    上传文件（TXT / PDF / DOCX / MD）自动解析为面试记录文本并生成问题表（含轻量意图识别）。
    """
    from app.tools import interview_review
    from app.api.context import set_session_context, reset_session_context

    if not position or not position.strip():
        raise HTTPException(status_code=400, detail="岗位名称不能为空")

    MAX_BYTES = 10 * 1024 * 1024
    if file.size is not None and file.size > MAX_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"文件过大 ({file.size / 1024 / 1024:.1f}MB > 10MB)",
        )

    SUPPORTED_EXTS = {".txt", ".md", ".pdf", ".docx"}
    ext = (file.filename or "").lower()
    suffix = Path(ext).suffix
    if suffix not in SUPPORTED_EXTS:
        raise HTTPException(
            status_code=400,
            detail=f"暂不支持 {suffix or '无后缀'} 格式，请上传 TXT / PDF / DOCX / MD",
        )

    upload_id = uuid.uuid4().hex[:12]
    target_dir = updated_dir / f"interview_review_{upload_id}"
    target_dir.mkdir(parents=True, exist_ok=True)
    saved_path = target_dir / file.filename
    with saved_path.open("wb") as buf:
        shutil.copyfileobj(file.file, buf)

    token = set_session_context(str(target_dir))
    try:
        try:
            raw_text = read_file_content.invoke(str(saved_path))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"文件解析失败: {e}")
    finally:
        reset_session_context(token)

    if not raw_text or not raw_text.strip():
        raise HTTPException(status_code=400, detail="文件内容为空")
    if raw_text.startswith("错误"):
        raise HTTPException(status_code=400, detail=raw_text)
    if len(raw_text.strip()) < 30:
        raise HTTPException(
            status_code=400,
            detail=f"文件内容过短 (仅 {len(raw_text.strip())} 字符)，请检查文件",
        )

    try:
        record_id = interview_review.create_interview_record(
            user_id=user_id,
            title=title,
            company=company,
            position=position,
            round_type=round_type,
            raw_text=raw_text,
            job_analysis_id=job_analysis_id,
            submission_id=submission_id,
        )
        dialogue = interview_review._parse_dialogue(raw_text)
        from app.workflows.question_table_flow import run_question_table_workflow

        qa_pairs_with_intent = run_question_table_workflow(record_id, user_id=user_id)
        return {
            "record_id": record_id,
            "status": "parsed",
            "qa_pairs": qa_pairs_with_intent,
            "qa_pair_count": len(qa_pairs_with_intent),
            "dialogue": dialogue,
            "speaker_count": len({d["speaker"] for d in dialogue}),
            "role_counts": {
                "interviewer": sum(
                    1 for d in dialogue if d.get("role") == "interviewer"
                ),
                "candidate": sum(1 for d in dialogue if d.get("role") == "candidate"),
                "unknown": sum(
                    1
                    for d in dialogue
                    if d.get("role") not in ("interviewer", "candidate")
                ),
            },
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("面试复盘文件创建失败")
        raise HTTPException(status_code=500, detail=f"面试复盘文件创建失败: {e}")


@app.post("/api/jobcraft/interview-review/parse-preview")
async def jobcraft_interview_review_parse_preview(
    raw_text: str = Form(""),
    file: Optional[UploadFile] = File(None),
    company: str = Form(""),
    position: str = Form(""),
    round_type: str = Form("业务面"),
    job_analysis_id: Optional[int] = Form(None),
    with_intent: bool = Form(False),
):
    """
    预览解析结果：把原始文本或上传文件解析成对话轮次，不写入数据库。
    可选 with_intent=true 时，会调用轻量 LLM 为每个问题生成意图标签。
    """
    from app.tools import interview_review
    from app.api.context import set_session_context, reset_session_context

    text = raw_text or ""

    if file and file.filename:
        MAX_BYTES = 10 * 1024 * 1024
        if file.size is not None and file.size > MAX_BYTES:
            raise HTTPException(
                status_code=400,
                detail=f"文件过大 ({file.size / 1024 / 1024:.1f}MB > 10MB)",
            )

        SUPPORTED_EXTS = {".txt", ".md", ".pdf", ".docx"}
        ext = (file.filename or "").lower()
        suffix = Path(ext).suffix
        if suffix not in SUPPORTED_EXTS:
            raise HTTPException(
                status_code=400,
                detail=f"暂不支持 {suffix or '无后缀'} 格式，请上传 TXT / PDF / DOCX / MD",
            )

        upload_id = uuid.uuid4().hex[:12]
        target_dir = updated_dir / f"interview_preview_{upload_id}"
        target_dir.mkdir(parents=True, exist_ok=True)
        saved_path = target_dir / file.filename
        with saved_path.open("wb") as buf:
            shutil.copyfileobj(file.file, buf)

        token = set_session_context(str(target_dir))
        try:
            file_text = read_file_content.invoke(str(saved_path))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"文件解析失败: {e}")
        finally:
            reset_session_context(token)

        if not file_text or not file_text.strip():
            raise HTTPException(status_code=400, detail="文件内容为空")
        if file_text.startswith("错误"):
            raise HTTPException(status_code=400, detail=file_text)
        if len(file_text.strip()) < 30:
            raise HTTPException(
                status_code=400,
                detail=f"文件内容过短 (仅 {len(file_text.strip())} 字符)，请检查文件",
            )
        text = file_text

    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="面试记录文本不能为空")
    if len(text.strip()) < 30:
        raise HTTPException(
            status_code=400,
            detail=f"面试记录文本过短 (仅 {len(text.strip())} 字符)，请补充内容",
        )

    dialogue = interview_review._parse_dialogue(text)
    qa_pairs = interview_review._build_qa_pairs(dialogue)

    jd_text = ""
    if job_analysis_id:
        analysis = db_tools.get_job_analysis(job_analysis_id)
        if analysis:
            jd_text = analysis.get("jd_text", "")

    if with_intent:
        qa_pairs = interview_review.preview_question_intents(
            qa_pairs=qa_pairs,
            company=company,
            position=position,
            round_type=round_type,
            jd_text=jd_text,
        )

    return {
        "dialogue": dialogue,
        "qa_pairs": qa_pairs,
        "qa_pair_count": len(qa_pairs),
        "speaker_count": len({d["speaker"] for d in dialogue}),
        "role_counts": {
            "interviewer": sum(1 for d in dialogue if d.get("role") == "interviewer"),
            "candidate": sum(1 for d in dialogue if d.get("role") == "candidate"),
            "unknown": sum(
                1 for d in dialogue if d.get("role") not in ("interviewer", "candidate")
            ),
        },
    }


@app.get("/api/jobcraft/interview-review")
def jobcraft_interview_review_list(user_id: int = 1):
    """列出面试复盘历史记录"""
    try:
        return {"records": db_tools.list_interview_records(user_id=user_id)}
    except Exception as e:
        logger.exception("获取面试复盘列表失败")
        raise HTTPException(status_code=500, detail=f"获取面试复盘列表失败: {e}")


class InterviewReviewQuestionTablePayload(BaseModel):
    """生成/刷新面试问题表请求体"""

    user_id: int = 1


class InterviewReviewAnalyzePayload(BaseModel):
    """对选中问题进行详细分析请求体"""

    user_id: int = 1
    selected_sequences: List[int]


@app.post("/api/jobcraft/interview-review/{record_id}/question-table")
def jobcraft_interview_review_question_table(
    record_id: int, payload: InterviewReviewQuestionTablePayload
):
    """
    为已保存的面试记录生成完整问题表（含意图、维度、难度）。
    会覆盖该记录下已有的 QA 对基础信息。
    """
    from app.workflows.question_table_flow import run_question_table_workflow

    try:
        questions = run_question_table_workflow(
            record_id=record_id, user_id=payload.user_id
        )
        return {
            "record_id": record_id,
            "status": "question_table",
            "questions": questions,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("生成面试问题表失败")
        raise HTTPException(status_code=500, detail=f"生成面试问题表失败: {e}")


@app.post("/api/jobcraft/interview-review/{record_id}/analyze")
def jobcraft_interview_review_analyze(
    record_id: int, payload: InterviewReviewAnalyzePayload
):
    """
    对面试记录中勾选的问题进行详细分析（Multi-Agent Workflow）。
    返回结果包含完整问题表汇总 + 勾选问题的详细解析。
    """
    from app.workflows.interview_review_flow import run_interview_review_workflow

    if not payload.selected_sequences:
        raise HTTPException(status_code=400, detail="请至少选择 1 个问题进行详细解析")
    if len(payload.selected_sequences) > 8:
        raise HTTPException(
            status_code=400, detail="因模型输出长度限制，每次最多选择 8 个问题"
        )
    try:
        result = run_interview_review_workflow(
            record_id=record_id,
            selected_sequences=payload.selected_sequences,
            user_id=payload.user_id,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("面试复盘详细分析失败")
        raise HTTPException(status_code=500, detail=f"面试复盘详细分析失败: {e}")


@app.get("/api/jobcraft/interview-review/{record_id}")
def jobcraft_interview_review_detail(record_id: int, user_id: int = 1):
    """获取单条面试复盘详情"""
    try:
        record = db_tools.get_interview_record(record_id)
        if not record:
            raise HTTPException(status_code=404, detail="面试记录不存在")
        qa_pairs = db_tools.list_interview_qa_pairs(record_id)
        return {
            "record": record,
            "qa_pairs": qa_pairs,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("获取面试复盘详情失败")
        raise HTTPException(status_code=500, detail=f"获取面试复盘详情失败: {e}")


@app.delete("/api/jobcraft/interview-review/{record_id}")
def jobcraft_interview_review_delete(record_id: int, user_id: int = 1):
    """删除面试复盘记录"""
    try:
        db_tools.delete_interview_record(record_id)
        return {"status": "deleted", "record_id": record_id}
    except Exception as e:
        logger.exception("删除面试复盘失败")
        raise HTTPException(status_code=500, detail=f"删除面试复盘失败: {e}")


if __name__ == "__main__":
    uvicorn.run("app.api.server:app", host="0.0.0.0", port=8000, reload=True)

"""
JobCraft 求职助手 — FastAPI 接口层

承载所有 JobCraft REST 接口，只做轻量参数校验和 Workflow 调用。
"""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, Optional

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.experience import router as experience_router
from app.api.job_analysis import router as job_analysis_router
from app.api.submission import router as submission_router
from app.api.interview_prep import router as interview_prep_router
from app.api.interview_review import router as interview_review_router
from app.auth.dependencies import get_current_user
from app.auth.router import router as auth_router
from app.monitoring import setup_monitoring


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield


current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent.parent

app = FastAPI(title="JobCraft API", lifespan=lifespan)

app.include_router(auth_router)
app.include_router(experience_router)
app.include_router(job_analysis_router)
app.include_router(submission_router)
app.include_router(interview_prep_router)
app.include_router(interview_review_router)

setup_monitoring(app)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("jobcraft.api")

output_dir = project_root / "output"
output_dir.mkdir(exist_ok=True)

updated_dir = project_root / "updated"
updated_dir.mkdir(exist_ok=True)

ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://localhost:5174,http://localhost:5175",
).split(",")
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
        from app.db import engine
        from sqlalchemy import text

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
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


@app.post("/api/jobcraft/tasks/submit")
async def submit_task(
    payload: Dict[str, Any],
    current_user: int = Depends(get_current_user),
):
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
            raise HTTPException(
                status_code=400, detail=f"不支持的任务类型: {task_type}"
            )

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
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=f"任务服务暂不可用（Redis 未就绪）: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"提交任务失败: {e}")


@app.get("/api/jobcraft/tasks/{task_id}")
async def get_task_status(task_id: str, current_user: int = Depends(get_current_user)):
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
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=f"任务服务暂不可用（Redis 未就绪）: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询任务失败: {e}")


@app.post("/api/jobcraft/tasks/{task_id}/cancel")
async def cancel_task(task_id: str, current_user: int = Depends(get_current_user)):
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
            raise HTTPException(status_code=400, detail="任务不存在或已完成，无法取消")

        return {"message": "任务已取消"}

    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=f"任务服务暂不可用（Redis 未就绪）: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"取消任务失败: {e}")


@app.get("/api/jobcraft/tasks")
async def list_tasks(
    status: Optional[str] = None,
    limit: int = 50,
    current_user: int = Depends(get_current_user),
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

        task_status = None
        if status:
            try:
                task_status = TaskStatus(status)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"无效的状态值: {status}")

        tasks = manager.list_tasks(status=task_status, limit=limit)

        return {
            "items": [task.to_dict() for task in tasks],
            "total": len(tasks),
        }

    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=f"任务服务暂不可用（Redis 未就绪）: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"列出任务失败: {e}")


if __name__ == "__main__":
    uvicorn.run("app.api.server:app", host="0.0.0.0", port=8000, reload=True)

"""
JobCraft 异步任务模块

基于 Redis + RQ 的异步任务执行框架。
支持长时间运行的任务（简历生成、报告导出等）。
"""

from .worker import TaskManager, TaskStatus, get_task_manager, run_worker

__all__ = ["TaskManager", "TaskStatus", "get_task_manager", "run_worker"]

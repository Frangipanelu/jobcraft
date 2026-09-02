"""
JobCraft 端到端 API 测试

覆盖范围:
  1. 经历卡 CRUD（含五段式字段）
  2. 岗位分析（JD 解析 + 匹配度 + 缺口 + 8 维能力要求）
  3. 定制简历生成与下载
  4. 面试准备稿生成与读取
  5. 历史列表查询

运行方式:
  # 只跑非 LLM 用例（快速，约 10-20 秒）
  python -m pytest tests/test_jobcraft_e2e.py -v

  # 跑全部（含 LLM，时间取决于模型响应，默认单接口 300 秒超时）
  python -m pytest tests/test_jobcraft_e2e.py -v --runslow

  # LLM 较慢时加大超时（单位：秒）
  $env:JOBCRAFT_TEST_LLM_TIMEOUT="600"
  python -m pytest tests/test_jobcraft_e2e.py -v --runslow

前置条件:
  - MySQL 已启动（docker compose up -d）
  - 后端已启动（uvicorn app.api.server:app --port 8000）
  - .env 中 LLM 配置正确
"""

import os
from typing import Any, Dict

import pytest
import requests

BASE_URL = os.environ.get("JOBCRAFT_TEST_BASE_URL", "http://localhost:8000")
USER_ID = int(os.environ.get("JOBCRAFT_TEST_USER_ID", "1"))
LLM_TIMEOUT = int(os.environ.get("JOBCRAFT_TEST_LLM_TIMEOUT", "300"))


def api_url(path: str) -> str:
    return f"{BASE_URL}{path}"


_AUTH_HEADERS: Dict[str, str] = {}


def _get_auth_headers() -> Dict[str, str]:
    """注册一次性 e2e 用户并获取认证头（缓存于模块级）"""
    global _AUTH_HEADERS
    if _AUTH_HEADERS:
        return _AUTH_HEADERS
    import uuid

    username = f"e2e_{uuid.uuid4().hex[:10]}"
    resp = requests.post(
        api_url("/api/auth/register"),
        json={"username": username, "password": "E2eTest123"},
        timeout=30,
    )
    assert resp.ok, f"注册 e2e 用户失败: {resp.status_code} {resp.text[:300]}"
    _AUTH_HEADERS = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    return _AUTH_HEADERS


def req(method: str, path: str, **kwargs) -> Dict[str, Any]:
    """封装请求并做基础断言（自动携带认证头）"""
    url = api_url(path)
    headers = kwargs.pop("headers", {})
    merged = dict(_get_auth_headers())
    merged.update(headers)
    resp = requests.request(
        method, url, timeout=kwargs.pop("timeout", 120), headers=merged, **kwargs
    )
    if not resp.ok:
        raise AssertionError(
            f"{method.upper()} {url} failed: {resp.status_code} {resp.text[:500]}"
        )
    try:
        return resp.json()
    except Exception:
        return {"_raw": resp.text}


# ---------- fixtures ----------


@pytest.fixture(scope="module")
def server_ok(server_available: bool) -> None:
    """服务器不在线时跳过全部 e2e 用例"""
    if not server_available:
        pytest.skip("后端服务未启动，跳过 e2e 测试")


@pytest.fixture(scope="module")
def sample_card(server_ok) -> Dict[str, Any]:
    """创建一个测试经历卡，测试结束后自动清理"""
    payload = {
        "user_id": USER_ID,
        "company": "测试科技有限公司",
        "role": "高级产品经理",
        "period": "2021.03 - 2023.05",
        "title": "AI 推荐策略优化",
        "summary": "通过重构推荐漏斗，用户留存提升 18%，GMV 增长 32%。",
        "background": "站内信息流点击率持续下滑，用户反馈内容同质化严重。",
        "problem": "拆解后发现召回层覆盖率低，排序模型未考虑长期兴趣。",
        "solution": "引入多兴趣向量召回 + 强化学习排序，权衡短期点击与长期留存。",
        "execution": "分 3 个阶段灰度上线，协调算法、工程、运营 3 个团队。",
        "result": "人均使用时长 +22%，次日留存 +18%，GMV +32%，方法论沉淀为团队 SOP。",
        "content": "负责站内信息流推荐优化，重构召回与排序策略，最终实现 GMV 增长 32%。",
        "raw_text": "负责站内信息流推荐优化，重构召回与排序策略，最终实现 GMV 增长 32%。",
        "tags": ["推荐策略", "增长", "AI"],
        "metrics": {"GMV": "+32%", "次日留存": "+18%", "使用时长": "+22%"},
        "dimensions": ["D2", "D3", "D4", "D6"],
        "industry": "电商",
        "role_type": "产品",
    }
    created = req("POST", "/api/jobcraft/experience/cards", json=payload)
    card_id = created["id"]
    yield created
    # teardown
    try:
        req("DELETE", f"/api/jobcraft/experience/cards/{card_id}")
    except AssertionError:
        pass


@pytest.fixture(scope="module")
def sample_jd() -> str:
    return """
高级产品经理（AI 方向）

岗位职责：
1. 负责电商搜索/推荐产品策略，提升转化率和用户体验；
2. 深入理解用户搜索意图，设计排序、召回、个性化策略；
3. 与技术、运营、数据团队紧密协作，推动算法模型落地；
4. 基于数据复盘持续优化策略，输出方法论。

任职要求：
1. 3 年以上产品经验，有搜索/推荐/广告策略背景优先；
2. 优秀的数据敏感度，熟练使用 SQL/Python 进行数据分析；
3. 具备较强的项目推动力和跨团队协作能力；
4. 对 AI 和大模型应用有实践经验者优先。
"""


@pytest.fixture(scope="module")
def analyzed_job(sample_card: Dict[str, Any], sample_jd: str) -> Dict[str, Any]:
    """调用岗位分析，返回分析结果"""
    payload = {
        "user_id": USER_ID,
        "company": "测试科技",
        "position": "高级产品经理（AI 方向）",
        "jd_text": sample_jd,
        "card_ids": [sample_card["id"]],
    }
    result = req("POST", "/api/jobcraft/job/analyze", json=payload, timeout=LLM_TIMEOUT)
    assert "job_analysis_id" in result
    return result


# ---------- 经历卡测试 ----------


def test_create_experience_card(sample_card: Dict[str, Any]):
    assert sample_card["company"] == "测试科技有限公司"
    assert sample_card["role"] == "高级产品经理"
    assert sample_card["background"]
    assert sample_card["problem"]
    assert sample_card["solution"]
    assert sample_card["execution"]
    assert sample_card["result"]
    assert sample_card["dimensions"]


def test_list_cards(sample_card: Dict[str, Any]):
    data = req("GET", "/api/jobcraft/experience/cards", params={"user_id": USER_ID})
    cards = data["items"]
    assert any(c["id"] == sample_card["id"] for c in cards)


def test_update_experience_card(sample_card: Dict[str, Any]):
    card_id = sample_card["id"]
    updated = req(
        "PATCH",
        f"/api/jobcraft/experience/cards/{card_id}",
        json={"summary": "更新后的总结：留存提升 20%"},
    )
    assert updated["summary"] == "更新后的总结：留存提升 20%"


# ---------- 岗位分析测试（慢） ----------


@pytest.mark.slow
def test_analyze_job_basic(analyzed_job: Dict[str, Any]):
    assert analyzed_job["match_score"] >= 0
    assert analyzed_job["match_score"] <= 1
    assert analyzed_job["gap_analysis"]
    assert analyzed_job["gap_items"]
    assert analyzed_job["per_card_scores"]
    assert analyzed_job["suggestions"]
    assert analyzed_job.get("ats_profile")
    assert analyzed_job.get("company_context")
    assert analyzed_job.get("dimension_requirements") or analyzed_job.get("ats_profile")


@pytest.mark.slow
def test_list_job_analyses(analyzed_job: Dict[str, Any]):
    data = req("GET", "/api/jobcraft/job/analyses", params={"user_id": USER_ID})
    analyses = data["analyses"]
    assert any(a["id"] == analyzed_job["job_analysis_id"] for a in analyses)


# ---------- 简历生成测试（慢） ----------


@pytest.mark.slow
def test_save_resume(analyzed_job: Dict[str, Any], sample_card: Dict[str, Any]):
    payload = {
        "job_analysis_id": analyzed_job["job_analysis_id"],
        "selected_card_ids": [sample_card["id"]],
        "suggestions": [
            {"card_id": sample_card["id"], "optimization": "突出 AI 推荐策略与数据结果"}
        ],
    }
    result = req(
        "POST", "/api/jobcraft/job/save-resume", json=payload, timeout=LLM_TIMEOUT
    )
    assert result["file_path"]
    assert result["file_name"]
    assert result["size_bytes"] > 0
    assert result["selected_count"] == 1
    # 下载验证
    dl_resp = requests.get(
        api_url("/api/jobcraft/resume/download"),
        params={"path": result["file_path"]},
        timeout=30,
    )
    assert dl_resp.status_code == 200
    assert "测试科技有限公司" in dl_resp.text or sample_card["title"] in dl_resp.text


# ---------- 面试准备稿测试（慢） ----------


@pytest.mark.slow
def test_generate_interview_prep(
    analyzed_job: Dict[str, Any], sample_card: Dict[str, Any]
):
    payload = {
        "user_id": USER_ID,
        "round_type": "业务面",
        "card_ids": [sample_card["id"]],
    }
    result = req(
        "POST",
        f"/api/jobcraft/job/{analyzed_job['job_analysis_id']}/interview-prep",
        json=payload,
        timeout=LLM_TIMEOUT,
    )
    assert result["job_analysis_id"] == analyzed_job["job_analysis_id"]
    assert result["round_type"] == "业务面"
    assert result["elevator_pitch"]
    assert result["dimension_questions"]
    assert result["full_version"]
    assert result["html_content"]


@pytest.mark.slow
def test_generate_interview_prep_without_card_ids(analyzed_job: Dict[str, Any]):
    """验证面试准备页不传 card_ids 时，后端自动复用岗位分析关联卡片"""
    payload = {
        "user_id": USER_ID,
        "round_type": "技术面",
        "card_ids": [],
    }
    result = req(
        "POST",
        f"/api/jobcraft/job/{analyzed_job['job_analysis_id']}/interview-prep",
        json=payload,
        timeout=LLM_TIMEOUT,
    )
    assert result["round_type"] == "技术面"
    assert result["dimension_questions"]


@pytest.mark.slow
def test_get_interview_prep(analyzed_job: Dict[str, Any]):
    result = req(
        "GET",
        f"/api/jobcraft/job/{analyzed_job['job_analysis_id']}/interview-prep",
        params={"user_id": USER_ID},
        timeout=120,
    )
    assert result["job_analysis_id"] == analyzed_job["job_analysis_id"]
    assert result["dimension_questions"]


# ---------- 错误场景 ----------


def test_analyze_job_without_cards(sample_jd: str, server_ok):
    payload = {
        "user_id": USER_ID,
        "company": "测试科技",
        "position": "测试岗位",
        "jd_text": sample_jd,
        "card_ids": [],
    }
    resp = requests.post(api_url("/api/jobcraft/job/analyze"), json=payload, timeout=30)
    assert resp.status_code == 400


def test_interview_prep_without_job(server_ok):
    payload = {"user_id": USER_ID, "round_type": "技术面", "card_ids": []}
    resp = requests.post(
        api_url("/api/jobcraft/job/999999/interview-prep"), json=payload, timeout=30
    )
    assert resp.status_code in (400, 404)

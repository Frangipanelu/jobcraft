"""T-M8-1 反馈闸门（feedback_candidates 决策台账）单元测试。

覆盖三层：
1. DB 层 decide/list/get 的幂等语义与非法值拒绝（mock db_conn，不连真库）；
2. API 层 GET 候选合并（analysis_json 唯一内容来源 + 台账决策）与 gate_status 推导；
3. API 层 accept/reject 的写卡、幂等短路、越权与不存在候选的拒绝。
"""

import pytest

from app.tools import db_interview

RECORD = {
    "id": 7,
    "user_id": 1,
    "analysis": {
        "experienceFeedbacks": [
            {
                "experienceId": "42",
                "experienceTitle": "RAG 评测体系",
                "discoveredIssues": ["缺商业闭环量化"],
                "suggestions": ["补充选型对比"],
                "currentVersion": "V1",
                "proposedVersion": "V2",
                "proposedChanges": [{"field": "results", "before": "a", "after": "b"}],
            }
        ]
    },
}


@pytest.fixture
def gate_client(monkeypatch):
    """构造带闸门依赖桩的 client（db_tools 全部走内存态）。"""
    from tests.test_api_routes_unit import client

    state = {
        "record": RECORD,
        "ledger": [],
        "card": {"id": 42, "version": 1},
        "update_calls": [],
    }

    def get_record(record_id, user_id=None):
        return state["record"] if state["record"] else None

    def list_ledger(record_id, user_id=None):
        return list(state["ledger"])

    def get_candidate(record_id, target_type, target_ref):
        for row in state["ledger"]:
            if (
                row["interview_record_id"] == record_id
                and row["target_type"] == target_type
                and row["target_ref"] == target_ref
            ):
                return row
        return None

    def decide(
        record_id,
        user_id,
        target_type,
        target_ref,
        decision,
        card_version=None,
        analysis_run_id="",
    ):
        row = {
            "id": len(state["ledger"]) + 1,
            "user_id": user_id,
            "interview_record_id": record_id,
            "target_type": target_type,
            "target_ref": target_ref,
            "analysis_run_id": analysis_run_id,
            "decision": decision,
            "card_version": card_version,
            "decided_at": "2026-10-04 12:00:00",
        }
        for i, old in enumerate(state["ledger"]):
            if (
                old["interview_record_id"] == record_id
                and old["target_type"] == target_type
                and old["target_ref"] == target_ref
            ):
                state["ledger"][i] = row
                return row
        state["ledger"].append(row)
        return row

    def get_card(card_id, user_id=None):
        return state["card"] if state["card"] else None

    def update_card(card_id, updates, user_id=None, confirm=False):
        state["update_calls"].append((card_id, dict(updates)))
        state["card"] = {**state["card"], "version": state["card"]["version"] + 1}
        return True

    monkeypatch.setattr(
        "app.api.interview_review.db_tools.get_interview_record", get_record
    )
    monkeypatch.setattr(
        "app.api.interview_review.db_tools.list_feedback_candidates", list_ledger
    )
    monkeypatch.setattr(
        "app.api.interview_review.db_tools.get_feedback_candidate", get_candidate
    )
    monkeypatch.setattr(
        "app.api.interview_review.db_tools.decide_feedback_candidate", decide
    )
    monkeypatch.setattr("app.api.interview_review.db_tools.get_card", get_card)
    monkeypatch.setattr("app.api.interview_review.db_tools.update_card", update_card)
    return client, state


class TestFeedbackGateApi:
    """GET /api/jobcraft/interview-review/{record_id}/feedback-candidates"""

    def test_pending_candidates_gate_awaiting_confirmation(self, gate_client):
        client, _ = gate_client
        resp = client.get("/api/jobcraft/interview-review/7/feedback-candidates")
        assert resp.status_code == 200
        data = resp.json()
        assert data["candidate_count"] == 1
        assert data["pending_count"] == 1
        assert data["gate_status"] == "awaiting_confirmation"
        item = data["candidates"][0]
        assert item["target_ref"] == "42"
        assert item["decision"] == "pending"
        # 候选正文来自 analysis_json（台账不复制内容）
        assert item["experience_title"] == "RAG 评测体系"
        assert item["suggestions"] == ["补充选型对比"]

    def test_all_decided_gate_done_and_decision_visible(self, gate_client):
        client, state = gate_client
        state["ledger"] = [
            {
                "id": 1,
                "user_id": 1,
                "interview_record_id": 7,
                "target_type": "experience",
                "target_ref": "42",
                "analysis_run_id": "",
                "decision": "accepted",
                "card_version": 3,
                "decided_at": "2026-10-04 12:00:00",
            }
        ]
        resp = client.get("/api/jobcraft/interview-review/7/feedback-candidates")
        data = resp.json()
        assert data["gate_status"] == "done"
        assert data["pending_count"] == 0
        # T-M8-1 核心：决策状态刷新后仍在（不再只活在 FE cache）
        assert data["candidates"][0]["decision"] == "accepted"
        assert data["candidates"][0]["card_version"] == 3

    def test_no_candidates_gate_none(self, gate_client):
        client, state = gate_client
        state["record"] = {"id": 7, "user_id": 1, "analysis": {}}
        resp = client.get("/api/jobcraft/interview-review/7/feedback-candidates")
        assert resp.json()["gate_status"] == "none"

    def test_missing_record_returns_404(self, gate_client):
        client, state = gate_client
        state["record"] = None
        resp = client.get("/api/jobcraft/interview-review/7/feedback-candidates")
        assert resp.status_code == 404


class TestFeedbackGateAccept:
    """POST /api/jobcraft/interview-review/{record_id}/feedback-candidates/accept"""

    def test_accept_writes_card_and_records_ledger(self, gate_client):
        client, state = gate_client
        resp = client.post(
            "/api/jobcraft/interview-review/7/feedback-candidates/accept",
            json={
                "target_ref": "42",
                "background": "bg",
                "problem": "pb",
                "actions": "ac",
                "results": "rs",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["decision"] == "accepted"
        assert data["idempotent"] is False
        assert data["card_version"] == 2  # update_card 后端版本 +1
        assert data["gate_status"] == "done"
        # 服务端写卡（四槽位透传，未传字段不入 updates）
        assert state["update_calls"] == [
            (
                42,
                {
                    "background": "bg",
                    "problem": "pb",
                    "actions": "ac",
                    "results": "rs",
                },
            )
        ]

    def test_accept_is_idempotent_no_second_write(self, gate_client):
        client, state = gate_client
        payload = {"target_ref": "42", "results": "rs"}
        first = client.post(
            "/api/jobcraft/interview-review/7/feedback-candidates/accept", json=payload
        )
        second = client.post(
            "/api/jobcraft/interview-review/7/feedback-candidates/accept", json=payload
        )
        assert first.status_code == 200 and second.status_code == 200
        assert second.json()["idempotent"] is True
        # SPEC：重跑复盘/重复确认 MUST NOT 重复落永久反馈 → 只写一次卡
        assert len(state["update_calls"]) == 1
        assert len(state["ledger"]) == 1

    def test_accept_unknown_candidate_returns_404(self, gate_client):
        client, _ = gate_client
        resp = client.post(
            "/api/jobcraft/interview-review/7/feedback-candidates/accept",
            json={"target_ref": "999"},
        )
        assert resp.status_code == 404

    def test_accept_missing_card_returns_404(self, gate_client):
        client, state = gate_client
        state["card"] = None
        resp = client.post(
            "/api/jobcraft/interview-review/7/feedback-candidates/accept",
            json={"target_ref": "42", "results": "rs"},
        )
        assert resp.status_code == 404
        assert state["update_calls"] == []

    def test_accept_empty_target_ref_returns_400(self, gate_client):
        client, _ = gate_client
        resp = client.post(
            "/api/jobcraft/interview-review/7/feedback-candidates/accept",
            json={"target_ref": "  "},
        )
        assert resp.status_code == 400


class TestFeedbackGateReject:
    """POST /api/jobcraft/interview-review/{record_id}/feedback-candidates/reject"""

    def test_reject_records_without_writing_card(self, gate_client):
        client, state = gate_client
        resp = client.post(
            "/api/jobcraft/interview-review/7/feedback-candidates/reject",
            json={"target_ref": "42"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["decision"] == "rejected"
        assert data["gate_status"] == "done"
        assert state["update_calls"] == []
        assert state["ledger"][0]["decision"] == "rejected"

    def test_reject_unknown_candidate_returns_404(self, gate_client):
        client, _ = gate_client
        resp = client.post(
            "/api/jobcraft/interview-review/7/feedback-candidates/reject",
            json={"target_ref": "999"},
        )
        assert resp.status_code == 404

    def test_reject_then_accept_switches_decision(self, gate_client):
        """反悔路径：忽略后可再确认（台账同键覆盖，不新增行）"""
        client, state = gate_client
        client.post(
            "/api/jobcraft/interview-review/7/feedback-candidates/reject",
            json={"target_ref": "42"},
        )
        resp = client.post(
            "/api/jobcraft/interview-review/7/feedback-candidates/accept",
            json={"target_ref": "42", "results": "rs"},
        )
        assert resp.json()["decision"] == "accepted"
        assert len(state["ledger"]) == 1
        assert len(state["update_calls"]) == 1


class TestFeedbackCandidateLedger:
    """DB 层：唯一键幂等 + 非法决策值拒绝（mock db_conn，不连真库）"""

    def test_decide_rejects_illegal_decision(self):
        with pytest.raises(ValueError, match="非法决策值"):
            db_interview.decide_feedback_candidate(
                record_id=7,
                user_id=1,
                target_type="experience",
                target_ref="42",
                decision="maybe",
            )

    def test_decide_uses_upsert_on_duplicate_key(self, monkeypatch):
        captured = {}

        def fake_execute(sql, params=None):
            captured["sql"] = sql
            captured["params"] = params

        monkeypatch.setattr(
            db_interview, "_ensure_feedback_candidates_table", lambda: None
        )
        monkeypatch.setattr(db_interview, "execute", fake_execute)
        monkeypatch.setattr(
            db_interview,
            "get_feedback_candidate",
            lambda *a: {
                "id": 1,
                "interview_record_id": 7,
                "target_type": "experience",
                "target_ref": "42",
                "decision": "accepted",
                "card_version": 5,
                "decided_at": "2026-10-04 12:00:00",
            },
        )
        row = db_interview.decide_feedback_candidate(
            record_id=7,
            user_id=1,
            target_type="experience",
            target_ref="42",
            decision="accepted",
            card_version=5,
        )
        assert "ON DUPLICATE KEY UPDATE" in captured["sql"]
        assert captured["params"][:4] == (1, 7, "experience", "42")
        assert row["card_version"] == 5

    def test_list_filters_by_user_and_orders(self, monkeypatch):
        captured = {}

        def fake_query_all(sql, params):
            captured["sql"] = sql
            captured["params"] = params
            return [
                {
                    "id": 1,
                    "user_id": 1,
                    "interview_record_id": 7,
                    "target_type": "experience",
                    "target_ref": "42",
                    "analysis_run_id": "",
                    "decision": "accepted",
                    "card_version": 2,
                    "decided_at": None,
                }
            ]

        monkeypatch.setattr(
            db_interview, "_ensure_feedback_candidates_table", lambda: None
        )
        monkeypatch.setattr(db_interview, "query_all", fake_query_all)
        rows = db_interview.list_feedback_candidates(7, 1)
        assert "AND user_id=%s" in captured["sql"]
        assert captured["params"] == (7, 1)
        assert rows[0]["decision"] == "accepted"
        assert rows[0]["decided_at"] is None

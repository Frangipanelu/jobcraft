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
        "apply_calls": [],
        "advance_calls": [],
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

    def apply_write(
        record_id,
        user_id,
        target_type,
        target_ref,
        card_id,
        updates,
        analysis_run_id="",
        decision="accepted",
    ):
        """T-M8-9：写卡 + 记台账收敛为一次单事务调用。"""
        state["apply_calls"].append(
            {
                "record_id": record_id,
                "card_id": card_id,
                "updates": dict(updates),
                "decision": decision,
                "analysis_run_id": analysis_run_id,
            }
        )
        update_card(card_id, updates, user_id=user_id)
        row = decide(
            record_id=record_id,
            user_id=user_id,
            target_type=target_type,
            target_ref=target_ref,
            decision=decision,
            card_version=state["card"]["version"],
            analysis_run_id=analysis_run_id,
        )
        return {"card_version": state["card"]["version"], "ledger": row}

    def advance(record_id, target, user_id=None):
        state["advance_calls"].append((record_id, target))
        return target

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
    monkeypatch.setattr(
        "app.api.interview_review.db_tools.apply_feedback_card_write", apply_write
    )
    monkeypatch.setattr(
        "app.api.interview_review.db_tools.advance_interview_record_status", advance
    )
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
                "actions": ["ac1", "ac2"],
                "results": ["rs1"],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["decision"] == "accepted"
        assert data["idempotent"] is False
        assert data["card_version"] == 2  # update_card 后端版本 +1
        assert data["gate_status"] == "done"
        # 服务端写卡（四槽位透传，未传字段不入 updates；actions/results 为列表）
        assert state["update_calls"] == [
            (
                42,
                {
                    "background": "bg",
                    "problem": "pb",
                    "actions": ["ac1", "ac2"],
                    "results": ["rs1"],
                },
            )
        ]

    def test_accept_is_idempotent_no_second_write(self, gate_client):
        client, state = gate_client
        payload = {"target_ref": "42", "results": ["rs"]}
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
            json={"target_ref": "42", "results": ["rs"]},
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
            json={"target_ref": "42", "results": ["rs"]},
        )
        assert resp.json()["decision"] == "accepted"
        assert len(state["ledger"]) == 1
        assert len(state["update_calls"]) == 1

    def test_reject_accepted_candidate_returns_409(self, gate_client):
        """T-M8-9：已确认沉淀的候选禁止直接忽略（否则卡已写、状态却说已忽略）"""
        client, state = gate_client
        client.post(
            "/api/jobcraft/interview-review/7/feedback-candidates/accept",
            json={"target_ref": "42", "results": ["rs"]},
        )
        resp = client.post(
            "/api/jobcraft/interview-review/7/feedback-candidates/reject",
            json={"target_ref": "42"},
        )
        assert resp.status_code == 409
        assert "回滚" in resp.json()["error"]["message"]
        assert state["ledger"][0]["decision"] == "accepted"

    def test_reject_repeated_is_idempotent_flagged(self, gate_client):
        client, state = gate_client
        first = client.post(
            "/api/jobcraft/interview-review/7/feedback-candidates/reject",
            json={"target_ref": "42"},
        )
        second = client.post(
            "/api/jobcraft/interview-review/7/feedback-candidates/reject",
            json={"target_ref": "42"},
        )
        assert first.json()["idempotent"] is False
        assert second.json()["idempotent"] is True
        assert len(state["ledger"]) == 1


class TestFeedbackGateAtomicityAndPhase:
    """T-M8-9：单事务写卡 + edited 决策 + 全决策后阶段推进 done"""

    def test_accept_uses_single_transaction_helper(self, gate_client):
        """写卡与台账必须收敛为一次 apply_feedback_card_write（DATA_MODEL §31）"""
        client, state = gate_client
        resp = client.post(
            "/api/jobcraft/interview-review/7/feedback-candidates/accept",
            json={"target_ref": "42", "results": ["rs"]},
        )
        assert resp.status_code == 200
        assert len(state["apply_calls"]) == 1
        call = state["apply_calls"][0]
        assert call["card_id"] == 42
        assert call["decision"] == "accepted"
        assert call["updates"] == {"results": ["rs"]}

    def test_edited_flag_records_edited_decision(self, gate_client):
        """SPEC §23：用户手工改过槽位 → 台账记 edited"""
        client, state = gate_client
        resp = client.post(
            "/api/jobcraft/interview-review/7/feedback-candidates/accept",
            json={"target_ref": "42", "problem": "我自己改过", "edited": True},
        )
        assert resp.status_code == 200
        assert resp.json()["decision"] == "edited"
        assert state["ledger"][0]["decision"] == "edited"

    def test_all_decided_advances_phase_to_done(self, gate_client):
        client, state = gate_client
        resp = client.post(
            "/api/jobcraft/interview-review/7/feedback-candidates/reject",
            json={"target_ref": "42"},
        )
        assert resp.json()["gate_status"] == "done"
        assert state["advance_calls"] == [(7, "done")]

    def test_pending_candidate_does_not_advance_phase(self, gate_client):
        """仍有待决策候选 → 不推进阶段（awaiting_confirmation 保持）"""
        client, state = gate_client
        state["record"] = {
            **RECORD,
            "analysis": {
                "experienceFeedbacks": [
                    *RECORD["analysis"]["experienceFeedbacks"],
                    {"experienceId": "43", "experienceTitle": "另一段经历"},
                ]
            },
        }
        resp = client.post(
            "/api/jobcraft/interview-review/7/feedback-candidates/reject",
            json={"target_ref": "42"},
        )
        assert resp.json()["gate_status"] == "awaiting_confirmation"
        assert state["advance_calls"] == []

    def test_idempotent_accept_does_not_rewite_card(self, gate_client):
        client, state = gate_client
        client.post(
            "/api/jobcraft/interview-review/7/feedback-candidates/accept",
            json={"target_ref": "42", "results": ["rs"]},
        )
        resp = client.post(
            "/api/jobcraft/interview-review/7/feedback-candidates/accept",
            json={"target_ref": "42", "results": ["rs"]},
        )
        assert resp.json()["idempotent"] is True
        assert len(state["apply_calls"]) == 1
        assert len(state["update_calls"]) == 1


class TestInterviewRecordStatusProgression:
    """T-M8-9：状态推进序（防降级）——替代原 `status != "done"` 字面量判断"""

    def test_rank_order_matches_spec_six_states(self):
        assert db_interview.status_rank("planned") == 0
        assert db_interview.status_rank("parsed") == 1
        assert db_interview.status_rank("question_table") == 2
        assert db_interview.status_rank("analyzed") == 3
        assert db_interview.status_rank("awaiting_confirmation") == 4
        assert db_interview.status_rank("done") == 5

    def test_failed_and_unknown_rank_lowest_for_retry(self):
        assert db_interview.status_rank("failed") == -1
        assert db_interview.status_rank("unknown_state") == -1
        assert db_interview.status_rank(None) == -1

    def test_advance_skips_downgrade(self, monkeypatch):
        monkeypatch.setattr(
            db_interview, "get_interview_record", lambda *a, **k: {"status": "done"}
        )
        writes = []
        monkeypatch.setattr(
            db_interview,
            "update_interview_record_status",
            lambda rid, st: writes.append((rid, st)),
        )
        result = db_interview.advance_interview_record_status(7, "question_table")
        assert result == "done"
        assert writes == [], "已 done 不得降级回 question_table"

    def test_advance_writes_when_rank_increases(self, monkeypatch):
        monkeypatch.setattr(
            db_interview,
            "get_interview_record",
            lambda *a, **k: {"status": "question_table"},
        )
        writes = []
        monkeypatch.setattr(
            db_interview,
            "update_interview_record_status",
            lambda rid, st: writes.append((rid, st)),
        )
        result = db_interview.advance_interview_record_status(7, "analyzed")
        assert result == "analyzed"
        assert writes == [(7, "analyzed")]

    def test_advance_rejects_unknown_target(self):
        with pytest.raises(ValueError, match="未知面试记录状态"):
            db_interview.advance_interview_record_status(7, "not_a_stage")

    def test_analysis_without_feedback_marks_analyzed(self, monkeypatch):
        captured = {}

        def fake_execute(sql, params=None):
            captured["params"] = params

        monkeypatch.setattr(
            db_interview, "_ensure_interview_records_table", lambda: None
        )
        monkeypatch.setattr(db_interview, "execute", fake_execute)
        db_interview.update_interview_record_analysis(7, {"summary": "x"})
        assert captured["params"][1] == "analyzed"

    def test_analysis_with_feedback_marks_awaiting_confirmation(self, monkeypatch):
        captured = {}

        def fake_execute(sql, params=None):
            captured["params"] = params

        monkeypatch.setattr(
            db_interview, "_ensure_interview_records_table", lambda: None
        )
        monkeypatch.setattr(db_interview, "execute", fake_execute)
        db_interview.update_interview_record_analysis(
            7, {"patch": {"experienceFeedbacks": [{"experienceId": "42"}]}}
        )
        assert captured["params"][1] == "awaiting_confirmation"


class TestFeedbackCardWriteTransaction:
    """T-M8-9：apply_feedback_card_write 单事务编排（mock 连接，不连真库）"""

    def test_illegal_decision_rejected_before_touching_db(self):
        with pytest.raises(ValueError, match="非法决策值"):
            db_interview.apply_feedback_card_write(
                record_id=7,
                user_id=1,
                target_type="experience",
                target_ref="42",
                card_id=42,
                updates={"results": ["rs"]},
                decision="maybe",
            )

    def test_missing_card_raises_value_error(self, monkeypatch):
        monkeypatch.setattr(
            db_interview, "_ensure_interview_records_table", lambda: None
        )
        monkeypatch.setattr(
            db_interview, "_ensure_feedback_candidates_table", lambda: None
        )
        monkeypatch.setattr(
            db_interview,
            "transaction",
            lambda: _NullTransaction(_FakeConn(_ScriptedCursor([None]))),
        )
        with pytest.raises(ValueError, match="经历卡不存在"):
            db_interview.apply_feedback_card_write(
                record_id=7,
                user_id=1,
                target_type="experience",
                target_ref="42",
                card_id=42,
                updates={"results": ["rs"]},
            )

    def test_writes_card_and_ledger_in_one_transaction(self, monkeypatch):
        calls = {"commit": 0, "rollback": 0}
        cursor = _ScriptedCursor(
            [
                {"id": 42, "version": 3},
                {"version": 4},
                {
                    "id": 1,
                    "decision": "accepted",
                    "card_version": 4,
                    "decided_at": "2026-10-04 12:00:00",
                },
            ]
        )
        conn = _FakeConn(cursor)
        conn.on_commit = lambda: calls.__setitem__("commit", calls["commit"] + 1)
        conn.on_rollback = lambda: calls.__setitem__("rollback", calls["rollback"] + 1)
        monkeypatch.setattr(
            db_interview, "_ensure_interview_records_table", lambda: None
        )
        monkeypatch.setattr(
            db_interview, "_ensure_feedback_candidates_table", lambda: None
        )
        monkeypatch.setattr(db_interview, "update_card_with_conn", lambda *a, **k: True)
        monkeypatch.setattr(db_interview, "transaction", lambda: _NullTransaction(conn))
        result = db_interview.apply_feedback_card_write(
            record_id=7,
            user_id=1,
            target_type="experience",
            target_ref="42",
            card_id=42,
            updates={"results": ["rs"]},
            decision="accepted",
        )
        assert result["card_version"] == 4
        assert result["ledger"]["decision"] == "accepted"
        assert calls == {"commit": 0, "rollback": 0}, "替身事务不自行提交"
        sqls = [sql for sql, _ in cursor.executed]
        assert any("INSERT INTO feedback_candidates" in s for s in sqls)


class _NullTransaction:
    """最小 transaction() 替身：只做上下文管理，不连真库、不提交。"""

    def __init__(self, conn):
        self._conn = conn

    def __enter__(self):
        return self._conn

    def __exit__(self, *exc):
        return False


class _FakeConn:
    """最小连接替身：cursor 复用同一脚本化游标。"""

    def __init__(self, cursor):
        self._cursor = cursor
        self.on_commit = None
        self.on_rollback = None

    def cursor(self, dictionary=False):
        return self._cursor

    def commit(self):
        if self.on_commit:
            self.on_commit()

    def rollback(self):
        if self.on_rollback:
            self.on_rollback()

    def close(self):
        return None


class _ScriptedCursor:
    """按 fetchone 次数顺序吐预设行的游标替身。"""

    def __init__(self, rows):
        self._rows = list(rows)
        self._fetch_idx = 0
        self.rowcount = 1
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self.executed.append((" ".join(sql.split()), params))

    def fetchone(self):
        row = self._rows[self._fetch_idx]
        self._fetch_idx += 1
        return row


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

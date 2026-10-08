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
        "batch_calls": [],
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

    def apply_batch(record_id, user_id, writes):
        """批量单事务桩：记录整批并逐条落卡 + 台账（与真库语义一致）。"""
        state["batch_calls"].append([dict(w) for w in writes])
        results = []
        for w in writes:
            target_type = w.get("target_type", "experience")
            if w["decision"] == "rejected":
                row = decide(
                    record_id=record_id,
                    user_id=user_id,
                    target_type=target_type,
                    target_ref=w["target_ref"],
                    decision="rejected",
                    card_version=None,
                    analysis_run_id=w.get("analysis_run_id", ""),
                )
                results.append(
                    {
                        "target_type": target_type,
                        "target_ref": w["target_ref"],
                        "decision": "rejected",
                        "card_version": None,
                        "decided_at": row["decided_at"],
                    }
                )
            else:
                out = apply_write(
                    record_id=record_id,
                    user_id=user_id,
                    target_type=target_type,
                    target_ref=w["target_ref"],
                    card_id=int(w.get("card_id") or w["target_ref"]),
                    updates=w.get("updates") or {},
                    analysis_run_id=w.get("analysis_run_id", ""),
                    decision=w["decision"],
                )
                results.append(
                    {
                        "target_type": target_type,
                        "target_ref": w["target_ref"],
                        "decision": out["ledger"]["decision"],
                        "card_version": out["card_version"],
                        "decided_at": out["ledger"]["decided_at"],
                    }
                )
        return results

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
        "app.api.interview_review.db_tools.apply_feedback_decisions", apply_batch
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


class TestFeedbackBatchConfirm:
    """POST .../feedback-candidates/confirm（§24.2 汇总一次确认，T-M8-9 遗留 C）

    关键语义：整批校验先行、单事务写入、结果与入参同序、幂等短路不重复写卡。
    """

    URL = "/api/jobcraft/interview-review/7/feedback-candidates/confirm"

    @staticmethod
    def _ledger_row(ref, decision, card_version=3):
        return {
            "id": len(str(ref)),
            "user_id": 1,
            "interview_record_id": 7,
            "target_type": "experience",
            "target_ref": ref,
            "analysis_run_id": "",
            "decision": decision,
            "card_version": card_version,
            "decided_at": "2026-10-04 12:00:00",
        }

    @staticmethod
    def _two_candidates(state):
        """独立构造含 42/43 两个候选的记录（不污染模块级 RECORD）。"""
        import copy

        state["record"] = copy.deepcopy(RECORD)
        feedbacks = state["record"]["analysis"]["experienceFeedbacks"]
        feedbacks.append(
            {
                "experienceId": "43",
                "experienceTitle": "第二段经历",
                "discoveredIssues": ["缺口径"],
                "suggestions": ["补指标"],
                "currentVersion": "V1",
                "proposedVersion": "V2",
                "proposedChanges": [],
            }
        )

    def test_mixed_accept_and_reject_in_one_transaction(self, gate_client):
        client, state = gate_client
        self._two_candidates(state)
        resp = client.post(
            self.URL,
            json={
                "decisions": [
                    {"target_ref": "42", "decision": "accepted", "results": ["rs"]},
                    {"target_ref": "43", "decision": "rejected"},
                ]
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["decision_count"] == 2
        # 结果与入参同序
        assert [r["target_ref"] for r in data["results"]] == ["42", "43"]
        assert [r["decision"] for r in data["results"]] == ["accepted", "rejected"]
        assert all(r["idempotent"] is False for r in data["results"])
        assert data["gate_status"] == "done"
        # 一次请求 = 一次批量事务调用（非两次单条）
        assert len(state["batch_calls"]) == 1
        assert len(state["batch_calls"][0]) == 2
        # 接受型写卡（四槽位），忽略型不写卡
        assert state["update_calls"] == [(42, {"results": ["rs"]})]
        assert [row["target_ref"] for row in state["ledger"]] == ["42", "43"]
        # 全部决策完成 → 阶段推进 done
        assert (7, "done") in state["advance_calls"]

    def test_already_decided_items_skip_write_idempotently(self, gate_client):
        client, state = gate_client
        self._two_candidates(state)
        state["ledger"] = [self._ledger_row("42", "accepted")]
        resp = client.post(
            self.URL,
            json={
                "decisions": [
                    {"target_ref": "42", "decision": "accepted"},
                    {"target_ref": "43", "decision": "accepted"},
                ]
            },
        )
        assert resp.status_code == 200
        results = resp.json()["results"]
        assert results[0]["idempotent"] is True
        assert results[0]["decision"] == "accepted"
        assert results[1]["idempotent"] is False
        # 只有 43 进入批量事务；42 不重复写卡
        assert len(state["batch_calls"]) == 1
        assert [w["target_ref"] for w in state["batch_calls"][0]] == ["43"]
        assert len(state["update_calls"]) == 1
        assert state["update_calls"][0][0] == 43

    def test_conflict_validates_whole_batch_before_any_write(self, gate_client):
        """合法条目排在前面也不能先写：409 前整批零写入。"""
        client, state = gate_client
        self._two_candidates(state)
        state["ledger"] = [self._ledger_row("42", "accepted")]
        resp = client.post(
            self.URL,
            json={
                "decisions": [
                    {"target_ref": "43", "decision": "accepted"},
                    {"target_ref": "42", "decision": "rejected"},
                ]
            },
        )
        assert resp.status_code == 409
        assert state["batch_calls"] == []
        assert state["update_calls"] == []
        assert len(state["ledger"]) == 1, "冲突批次不得落任何决策"

    def test_unknown_candidate_404_without_partial_write(self, gate_client):
        client, state = gate_client
        resp = client.post(
            self.URL,
            json={
                "decisions": [
                    {"target_ref": "42", "decision": "accepted"},
                    {"target_ref": "999", "decision": "accepted"},
                ]
            },
        )
        assert resp.status_code == 404
        assert state["batch_calls"] == []
        assert state["update_calls"] == []

    def test_missing_card_404_without_partial_write(self, gate_client):
        client, state = gate_client
        self._two_candidates(state)
        state["card"] = None
        resp = client.post(
            self.URL,
            json={
                "decisions": [
                    {"target_ref": "42", "decision": "accepted"},
                    {"target_ref": "43", "decision": "accepted"},
                ]
            },
        )
        assert resp.status_code == 404
        assert state["batch_calls"] == []

    def test_invalid_payloads_rejected(self, gate_client):
        client, _ = gate_client
        cases = [
            {"decisions": []},  # 空批次
            {  # 批次内重复
                "decisions": [
                    {"target_ref": "42", "decision": "accepted"},
                    {"target_ref": "42", "decision": "rejected"},
                ]
            },
            {"decisions": [{"target_ref": "42", "decision": "maybe"}]},  # 非法决策
            {"decisions": [{"target_ref": "  ", "decision": "accepted"}]},  # 空 ref
        ]
        for body in cases:
            resp = client.post(self.URL, json=body)
            assert resp.status_code == 400, body

    def test_repeated_reject_is_idempotent_flagged(self, gate_client):
        client, state = gate_client
        state["ledger"] = [self._ledger_row("42", "rejected", card_version=None)]
        resp = client.post(
            self.URL,
            json={"decisions": [{"target_ref": "42", "decision": "rejected"}]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["results"][0]["idempotent"] is True
        assert data["results"][0]["decision"] == "rejected"
        assert state["batch_calls"] == []

    def test_edited_decision_records_edited_label(self, gate_client):
        client, state = gate_client
        resp = client.post(
            self.URL,
            json={
                "decisions": [
                    {
                        "target_ref": "42",
                        "decision": "edited",
                        "background": "bg2",
                    }
                ]
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["results"][0]["decision"] == "edited"
        assert data["results"][0]["idempotent"] is False
        assert state["ledger"][0]["decision"] == "edited"
        assert state["update_calls"] == [(42, {"background": "bg2"})]

    def test_missing_record_returns_404(self, gate_client):
        client, state = gate_client
        state["record"] = None
        resp = client.post(
            self.URL,
            json={"decisions": [{"target_ref": "42", "decision": "accepted"}]},
        )
        assert resp.status_code == 404


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
        cursor = _ScriptedCursor([])
        monkeypatch.setattr(
            db_interview, "_ensure_interview_records_table", lambda: None
        )
        monkeypatch.setattr(
            db_interview, "_ensure_feedback_candidates_table", lambda: None
        )
        monkeypatch.setattr(
            db_interview,
            "transaction",
            lambda: _NullTransaction(_FakeConn(cursor)),
        )
        db_interview.update_interview_record_analysis(7, {"summary": "x"})
        updates = [p for s, p in cursor.executed if "UPDATE interview_records" in s]
        assert updates and updates[0][1] == "analyzed"
        deletes = [
            p for s, p in cursor.executed if "DELETE FROM feedback_candidates" in s
        ]
        assert deletes and deletes[0] == (7,), "无候选时应清空该记录 pending 行"

    def test_analysis_with_feedback_marks_awaiting_confirmation(self, monkeypatch):
        cursor = _ScriptedCursor([])
        monkeypatch.setattr(
            db_interview, "_ensure_interview_records_table", lambda: None
        )
        monkeypatch.setattr(
            db_interview, "_ensure_feedback_candidates_table", lambda: None
        )
        monkeypatch.setattr(
            db_interview,
            "transaction",
            lambda: _NullTransaction(_FakeConn(cursor)),
        )
        # 候选形状：顶层 experienceFeedbacks（与 GET /feedback-candidates 及
        # FE mapper `const patch = analysis` 一致，非嵌套 patch 键）
        db_interview.update_interview_record_analysis(
            7, {"experienceFeedbacks": [{"experienceId": "42"}]}, user_id=1
        )
        updates = [p for s, p in cursor.executed if "UPDATE interview_records" in s]
        assert updates and updates[0][1] == "awaiting_confirmation"
        inserts = [
            p for s, p in cursor.executed if "INSERT INTO feedback_candidates" in s
        ]
        # VALUES 内 analysis_run_id='' 与 decision='pending' 为字面量
        assert inserts and inserts[0] == (1, 7, "experience", "42")
        assert any("ON DUPLICATE KEY UPDATE id=id" in s for s, _ in cursor.executed), (
            "物化必须幂等：唯一键命中只写 id=id，不覆盖已有决策"
        )

    def test_analysis_without_user_id_reads_owner_from_record(self, monkeypatch):
        cursor = _ScriptedCursor([(9,)])
        monkeypatch.setattr(
            db_interview, "_ensure_interview_records_table", lambda: None
        )
        monkeypatch.setattr(
            db_interview, "_ensure_feedback_candidates_table", lambda: None
        )
        monkeypatch.setattr(
            db_interview,
            "transaction",
            lambda: _NullTransaction(_FakeConn(cursor)),
        )
        db_interview.update_interview_record_analysis(
            7, {"experienceFeedbacks": [{"experienceId": "42"}]}
        )
        inserts = [
            p for s, p in cursor.executed if "INSERT INTO feedback_candidates" in s
        ]
        assert inserts and inserts[0][0] == 9, "缺省 user_id 时应回读记录归属用户"


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
        monkeypatch.setattr(db_interview, "_ensure_validations_table", lambda: None)
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
        monkeypatch.setattr(db_interview, "_ensure_validations_table", lambda: None)
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

    @staticmethod
    def _patch_env(monkeypatch, cursor):
        """把真实事务编排接到脚本游标上（ensure 全部短路，不连真库）。"""
        monkeypatch.setattr(
            db_interview, "_ensure_interview_records_table", lambda: None
        )
        monkeypatch.setattr(
            db_interview, "_ensure_feedback_candidates_table", lambda: None
        )
        monkeypatch.setattr(db_interview, "_ensure_validations_table", lambda: None)
        monkeypatch.setattr(
            db_interview, "update_card_with_conn", lambda *a, **k: False
        )
        monkeypatch.setattr(
            db_interview, "transaction", lambda: _NullTransaction(_FakeConn(cursor))
        )

    @staticmethod
    def _ledger_row(decision, row_id=1):
        return {
            "id": row_id,
            "decision": decision,
            "card_version": 3,
            "decided_at": "2026-10-07 12:00:00",
        }

    @pytest.mark.parametrize("decision", ["accepted", "edited"])
    def test_accepted_path_writes_user_confirmation_validation(
        self, monkeypatch, decision
    ):
        """T-M9-1：accepted/edited 与写卡/台账同事务追加 user_confirmed Validation
        （锁定 `decision in ("accepted", "edited")` 两分支）。"""
        cursor = _ScriptedCursor([{"id": 42, "version": 3}, self._ledger_row(decision)])
        self._patch_env(monkeypatch, cursor)
        db_interview.apply_feedback_card_write(
            record_id=7,
            user_id=1,
            target_type="experience",
            target_ref="42",
            card_id=42,
            updates={"results": ["rs"]},
            decision=decision,
        )
        inserts = [
            (sql, params)
            for sql, params in cursor.executed
            if "INSERT INTO validations" in sql
        ]
        assert len(inserts) == 1, f"{decision} 必须恰好写一条 Validation"
        sql, params = inserts[0]
        assert "WHERE NOT EXISTS" in sql
        assert params[0] == 1  # user_id
        assert params[1] == "experience"  # target_type 直通
        assert params[2] == "42"  # target_id = target_ref
        assert params[3] == "user_confirmation"  # source_type
        assert params[4] == "7"  # source_id = interview_record_id
        assert params[5] == "user_confirmed"
        assert params[6] == "moderate"
        # evidence_refs 回指台账行：fc:<ledger_row_id>
        assert "fc:1" in params[7]

    def test_rejected_path_skips_validation_insert(self, monkeypatch):
        """T-M9-1：rejected 只记台账，不产生 Validation 插入。"""
        cursor = _ScriptedCursor(
            [{"id": 42, "version": 3}, self._ledger_row("rejected", row_id=9)]
        )
        self._patch_env(monkeypatch, cursor)
        db_interview.apply_feedback_card_write(
            record_id=7,
            user_id=1,
            target_type="experience",
            target_ref="42",
            card_id=42,
            updates={"results": ["rs"]},
            decision="rejected",
        )
        sqls = [sql for sql, _ in cursor.executed]
        assert any("INSERT INTO feedback_candidates" in s for s in sqls)
        assert not any("INSERT INTO validations" in s for s in sqls), (
            "rejected 不得写 Validation"
        )

    def test_batch_mixed_writes_validation_only_for_accepted(self, monkeypatch):
        """T-M9-1 混批：accepted 条写 Validation，rejected 条不写（真实函数+脚本游标）。"""
        cursor = _ScriptedCursor(
            [
                {"id": 42, "version": 3},  # accepted：卡片查询
                self._ledger_row("accepted"),  # accepted：台账回读
                self._ledger_row("rejected", row_id=2),  # rejected：台账回读
            ]
        )
        self._patch_env(monkeypatch, cursor)
        results = db_interview.apply_feedback_decisions(
            7,
            1,
            [
                {
                    "target_type": "experience",
                    "target_ref": "42",
                    "card_id": 42,
                    "updates": {"results": ["rs"]},
                    "decision": "accepted",
                },
                {
                    "target_type": "experience",
                    "target_ref": "43",
                    "decision": "rejected",
                },
            ],
        )
        assert [r["decision"] for r in results] == ["accepted", "rejected"]
        val_inserts = [
            (sql, params)
            for sql, params in cursor.executed
            if "INSERT INTO validations" in sql
        ]
        assert len(val_inserts) == 1, "整批只应写 accepted 条的 Validation"
        assert val_inserts[0][1][2] == "42", "写入的 target 必须是 accepted 的 ref"
        assert val_inserts[0][1][4] == "7"


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

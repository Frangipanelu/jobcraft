"""run_review_eval 链失败保留旧结果单测（S4 收尾跟进）。

场景：限流风暴中重跑 case，链在 Router/Analyzer 处 429 失败——
不得用 error 条目冲掉 out-dir 报告里上次成功的 l1/judge。
"""

from __future__ import annotations

import json

import pytest

from evaluation import run_review_eval as rre

_CASE = {
    "case_id": "t_preserve",
    "company": "测试公司",
    "position": "后端工程师",
    "round_type": "技术面",
    "raw_text": (
        "面试官：你好，请介绍自己。\n候选人：我是张三。\n"
        "面试官：说说你的项目。\n候选人：做了一个电商系统。"
    ),
    "jd_text": "",
    "cards": [],
}

_PREV_L1 = {
    "total": 4,
    "passed": 4,
    "failed": 0,
    "pass_rate": 1.0,
    "failures": [],
}

_PREV_JUDGE = {
    "accuracy": 5,
    "completeness": 5,
    "actionability": 5,
    "safety": 10,
    "overall": 6,
    "strengths": ["s"],
    "weaknesses": ["w"],
    "rationale": "r",
}


def _write_dataset(tmp_path):
    ds = tmp_path / "cases.jsonl"
    ds.write_text(json.dumps(_CASE, ensure_ascii=False) + "\n", encoding="utf-8")
    return ds


def _boom(*_args, **_kwargs):
    raise RuntimeError("Error code: 429 mock 限流")


class TestChainFailurePreservesPrevious:
    """链失败时保留旧报告的 l1/judge。"""

    def test_preserves_l1_and_judge(self, tmp_path, monkeypatch):
        ds = _write_dataset(tmp_path)
        out = tmp_path / "out"
        out.mkdir()
        seed = {
            "per_case": [
                {
                    "case_id": "t_preserve",
                    "l1": _PREV_L1,
                    "overall_score": 50,
                    "n_questions": 2,
                    "judge": _PREV_JUDGE,
                }
            ]
        }
        (out / "surface_review_report.json").write_text(
            json.dumps(seed, ensure_ascii=False), encoding="utf-8"
        )
        monkeypatch.setattr(rre, "_run_review_chain", _boom)

        report = rre.run_eval(
            dataset_path=ds, case_id="t_preserve", l1_only=True, out_dir=out
        )

        row = report["per_case"][0]
        assert "mock" in row["error"]
        assert row["chain_preserved"] is True
        assert row["l1"]["pass_rate"] == 1.0
        assert row["n_questions"] == 2
        assert row["judge"]["overall"] == 6

    def test_no_previous_keeps_error_only(self, tmp_path, monkeypatch):
        ds = _write_dataset(tmp_path)
        out = tmp_path / "out"
        monkeypatch.setattr(rre, "_run_review_chain", _boom)

        report = rre.run_eval(
            dataset_path=ds, case_id="t_preserve", l1_only=True, out_dir=out
        )

        row = report["per_case"][0]
        assert "mock" in row["error"]
        assert "l1" not in row
        assert "chain_preserved" not in row

    def test_corrupt_previous_report_ignored(self, tmp_path, monkeypatch):
        ds = _write_dataset(tmp_path)
        out = tmp_path / "out"
        out.mkdir()
        (out / "surface_review_report.json").write_text("{broken", encoding="utf-8")
        monkeypatch.setattr(rre, "_run_review_chain", _boom)

        report = rre.run_eval(
            dataset_path=ds, case_id="t_preserve", l1_only=True, out_dir=out
        )
        assert "mock" in report["per_case"][0]["error"]


class TestRunEvalArgs:
    """参数校验。"""

    def test_unknown_case_id_raises(self, tmp_path):
        ds = _write_dataset(tmp_path)
        with pytest.raises(ValueError, match="不在"):
            rre.run_eval(
                dataset_path=ds, case_id="nope", l1_only=True, out_dir=tmp_path
            )

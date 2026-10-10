"""简历要点改写工具单测 — T-M6-3

覆盖：空原文 ValueError、prompt 渲染注入、invoke_structured 出参与空结果 RuntimeError。
"""

from types import SimpleNamespace

import pytest


class TestRewriteResumeBullet:
    """app.tools.resume_rewrite.rewrite_resume_bullet"""

    def test_empty_original_raises_value_error(self, monkeypatch):
        from app.tools.resume_rewrite import rewrite_resume_bullet

        def fake_invoke(*a, **k):
            raise AssertionError("空原文不应触发 LLM 调用")

        monkeypatch.setattr("app.tools.resume_rewrite.invoke_structured", fake_invoke)
        with pytest.raises(ValueError, match="要点原文为空"):
            rewrite_resume_bullet("   ")

    def test_success_renders_prompt_and_strips(self, monkeypatch):
        from app.tools.resume_rewrite import rewrite_resume_bullet

        seen = {}

        def fake_invoke(model, schema, prompt, **kw):
            seen.update(prompt=prompt, **kw)
            return SimpleNamespace(rewritten_text="  改写后的要点  ")

        monkeypatch.setattr("app.tools.resume_rewrite.invoke_structured", fake_invoke)
        out = rewrite_resume_bullet(
            "  负责系统开发  ",
            dimension="D1-编程语言",
            gap_current="缺少 Go",
            jd_evidence="要求熟练 Go",
            rewrite_hint="补入 Go 关键词",
        )
        assert out == "改写后的要点"
        assert seen["debug_label"] == "resume_rewrite"
        assert seen["prompt_version"] == "2"
        # T-P7-4：v2 注入表达方法论（文档化框架落 prompt）
        assert "表达方法论" in seen["prompt"]
        assert "三增量" in seen["prompt"]
        # prompt 已渲染：注入原文与缺口上下文
        assert "负责系统开发" in seen["prompt"]
        assert "要求熟练 Go" in seen["prompt"]
        assert "补入 Go 关键词" in seen["prompt"]
        assert "{{" not in seen["prompt"]

    def test_empty_rewritten_raises_runtime_error(self, monkeypatch):
        from app.tools.resume_rewrite import rewrite_resume_bullet

        monkeypatch.setattr(
            "app.tools.resume_rewrite.invoke_structured",
            lambda *a, **k: SimpleNamespace(rewritten_text="   "),
        )
        with pytest.raises(RuntimeError, match="返回内容为空"):
            rewrite_resume_bullet("要点原文")

    def test_missing_gap_fields_use_defaults(self, monkeypatch):
        from app.tools.resume_rewrite import rewrite_resume_bullet

        seen = {}

        def fake_invoke(model, schema, prompt, **kw):
            seen["prompt"] = prompt
            return SimpleNamespace(rewritten_text="ok")

        monkeypatch.setattr("app.tools.resume_rewrite.invoke_structured", fake_invoke)
        assert rewrite_resume_bullet("要点") == "ok"
        assert "未指定" in seen["prompt"]
        assert "未提供" in seen["prompt"]
        assert "按岗位要求优化表达" in seen["prompt"]

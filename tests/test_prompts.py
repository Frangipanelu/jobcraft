"""
测试 prompts/ 目录模板：占位符完整性、loader 渲染、格式一致性。
"""

from pathlib import Path

from app.core.prompts import PROMPTS_DIR, _PLACEHOLDER_RE, load_prompt

# 每个模板必须提供的占位符（值与注册表一致性由测试校验）
_REQUIRED_FIELDS = {
    ("experience", "extract_structured"): {"raw_text"},
    ("experience", "parse_resume_entries"): {"resume_text"},
    ("experience", "recommend_tags"): {"raw_text"},
    ("experience", "polish"): {"company", "role", "raw_text"},
    ("jd", "jd_ats_analysis"): {"dims", "jd_text"},
    ("jd", "ats_recommend"): {"jd_text", "cards_section"},
    ("jd", "score_match"): {
        "hard_skills",
        "soft_skills",
        "keywords",
        "responsibilities",
        "cards_section",
    },
    ("jd", "gap_polish"): {
        "job_title",
        "required_skills",
        "preferred_skills",
        "responsibilities",
        "key_metrics",
        "culture_keywords",
        "dims_text",
        "subtext_text",
        "cards_section",
    },
    ("jd", "suggestions"): {"jd_requirements", "cards_lines"},
    ("interview", "question_router"): {
        "position",
        "company",
        "questions_text",
    },
    ("interview", "tech_analyzer"): {
        "round_type",
        "position",
        "company",
        "rubric_text",
        "jd_section",
        "cards_text",
        "qa_text",
    },
    ("interview", "soft_analyzer"): {
        "round_type",
        "position",
        "company",
        "rubric_text",
        "jd_section",
        "cards_text",
        "qa_text",
    },
    ("interview", "gate_check"): {"position", "company", "results_text"},
    ("interview", "question_table_intent"): {
        "round_type",
        "position",
        "company",
        "jd_section",
        "rubric_text",
        "level_score_map",
        "questions_text",
    },
    ("interview", "interview_prep_script"): {
        "position",
        "round_type",
        "company",
        "jd_text",
        "dim_text",
        "cards_section",
        "company_section",
        "resume_section",
        "review_section",
        "section_order",
    },
    ("interview", "company_research"): {"company", "search_data"},
    ("interview", "mock_interview_chat"): {
        "round_type",
        "company",
        "position",
        "candidate_background",
    },
    ("core", "json_fallback_suffix"): {"schema_hint"},
}


# 非默认版本额外占位符（对应各 loader 自己的填充实参，如 jd_ats_analysis v4 额外传 structured_summary）
_VERSION_EXTRA_FIELDS = {
    ("jd", "jd_ats_analysis", 4): {"structured_summary"},
}


def _all_templates():
    """返回 [(subdir, name, path)]，覆盖 prompts/ 下全部 .txt。"""
    templates = []
    for path in sorted(PROMPTS_DIR.rglob("*.txt")):
        subdir = path.parent.name
        name = path.stem.rsplit("_v", 1)[0]
        templates.append((subdir, name, path))
    return templates


def _version_number(path: Path) -> int:
    """从 'name_vN.txt' 提取 N。"""
    return int(path.stem.rsplit("_v", 1)[1])


def test_every_registered_template_exists_and_fields_match():
    """注册表每个模板（默认 v1）都存在，且每个版本占位符 = 注册字段 ∪ 该版本额外字段。"""
    existing = {(subdir, name) for subdir, name, _ in _all_templates()}
    assert set(_REQUIRED_FIELDS) == existing, (
        f"差异:\n- 仅注册未建文件: {set(_REQUIRED_FIELDS) - existing}\n"
        f"- 仅文件未注册: {existing - set(_REQUIRED_FIELDS)}"
    )

    for (subdir, name), fields in _REQUIRED_FIELDS.items():
        version_files = sorted(
            (PROMPTS_DIR / subdir).glob(f"{name}_v*.txt"), key=_version_number
        )
        assert version_files, f"{subdir}/{name}: 缺少版本文件"
        for path in version_files:
            ver = _version_number(path)
            expected = fields | _VERSION_EXTRA_FIELDS.get((subdir, name, ver), set())
            text = path.read_text(encoding="utf-8")
            template_fields = {m.group(1) for m in _PLACEHOLDER_RE.finditer(text)}
            assert template_fields == expected, (
                f"{subdir}/{name} v{ver}: 模板占位符 {sorted(template_fields)} "
                f"!= 期望 {sorted(expected)}"
            )


def test_templates_contain_no_double_brace_artifacts():
    """模板中除 {{name}} 占位符外，不应出现双花括号残留。"""
    for subdir, name, path in _all_templates():
        text = path.read_text(encoding="utf-8")
        # 把占位符挖掉后，不应再有 '{{' 或 '}}'
        stripped = _PLACEHOLDER_RE.sub("", text)
        assert "{{" not in stripped, f"{subdir}/{name} 含未闭合 {{"
        assert "}}" not in stripped, f"{subdir}/{name} 含未闭合 }}"


def test_extract_structured_v2_anti_fabrication():
    """EXP-P1-04：extract_structured_v2 必须体现「提取到的填/没提取留空/禁止编造量化」。"""
    text = (PROMPTS_DIR / "experience" / "extract_structured_v2.txt").read_text(
        encoding="utf-8"
    )
    assert "禁止编造量化" in text
    assert "留空" in text
    assert "原文" in text
    # 不再要求「尽量包含量化指标」这类诱导编造的表述
    assert "尽量包含量化" not in text


def test_extract_structured_v3_tags_output():
    """EXP-P1-06c：extract_structured_v3 在反编造基础上升级为「STAR + 标签一次输出」。"""
    text = (PROMPTS_DIR / "experience" / "extract_structured_v3.txt").read_text(
        encoding="utf-8"
    )
    assert "禁止编造量化" in text
    assert "tags" in text
    assert "技术栈 / 业务领域 / 能力维度 / 行业" in text
    assert "禁止编造原文没有的标签" in text


def test_parse_resume_entries_v2_no_forced_percent():
    """EXP-P1-04：parse_resume_entries_v2 移除强制 'xx%' 格式。"""
    text = (PROMPTS_DIR / "experience" / "parse_resume_entries_v2.txt").read_text(
        encoding="utf-8"
    )
    # v1 的「带来xx%提升」强制格式必须移除
    assert "带来xx%提升" not in text
    assert "xx%提升" not in text
    assert "尽量提取量化结果" not in text
    # 保留占位符，但量化只允许原文举证
    assert "resume_text" in text
    assert "原文" in text


def test_load_prompt_renders_placeholders():
    """load_prompt 应返回已填充、无残留占位符的字符串，且字面花括号保留。"""
    for (subdir, name), fields in _REQUIRED_FIELDS.items():
        kwargs = {f: f"<{subdir}/{name}/{f}>" for f in fields}
        rendered = load_prompt(subdir, name, **kwargs)
        assert isinstance(rendered, str) and rendered
        # 占位符全部替换，无残留
        assert _PLACEHOLDER_RE.search(rendered) is None
        for f in fields:
            assert f"<{subdir}/{name}/{f}>" in rendered


def test_literal_braces_are_preserved():
    """模板中未被占位符占用的字面花括号应原样保留。"""
    from app.core.prompts import _fill

    template = '输出 JSON: {"items": ["a"], "b": 1} 完成 {{name}} 后结束'
    out = _fill(template, {"name": "X"})
    assert out == '输出 JSON: {"items": ["a"], "b": 1} 完成 X 后结束'

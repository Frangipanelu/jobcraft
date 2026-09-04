"""测试 prompts/ 目录模板：占位符完整性、loader 渲染、格式一致性。"""

from app.core.prompts import PROMPTS_DIR, _PLACEHOLDER_RE, load_prompt

# 每个模板必须提供的占位符（值与注册表一致性由测试校验）
_REQUIRED_FIELDS = {
    ("experience", "extract_structured"): {"raw_text"},
    ("experience", "parse_resume_entries"): {"resume_text"},
    ("experience", "recommend_tags"): {"raw_text"},
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


def _all_templates():
    """返回 [(subdir, name, path)]，覆盖 prompts/ 下全部 .txt。"""
    templates = []
    for path in sorted(PROMPTS_DIR.rglob("*.txt")):
        subdir = path.parent.name
        name = path.stem.rsplit("_v", 1)[0]
        templates.append((subdir, name, path))
    return templates


def test_every_registered_template_exists_and_fields_match():
    """注册表每个模板都存在，且注册字段集与模板实际占位符一致。"""
    existing = {(subdir, name) for subdir, name, _ in _all_templates()}
    assert set(_REQUIRED_FIELDS) == existing, (
        f"差异:\n- 仅注册未建文件: {set(_REQUIRED_FIELDS) - existing}\n"
        f"- 仅文件未注册: {existing - set(_REQUIRED_FIELDS)}"
    )

    for (subdir, name), fields in _REQUIRED_FIELDS.items():
        text = (PROMPTS_DIR / subdir / f"{name}_v1.txt").read_text(
            encoding="utf-8"
        )
        template_fields = {
            m.group(1) for m in _PLACEHOLDER_RE.finditer(text)
        }
        assert template_fields == fields, (
            f"{subdir}/{name}: 模板占位符 {template_fields} != 注册占位符 {fields}"
        )


def test_templates_contain_no_double_brace_artifacts():
    """模板中除 {{name}} 占位符外，不应出现双花括号残留。"""
    for subdir, name, path in _all_templates():
        text = path.read_text(encoding="utf-8")
        # 把占位符挖掉后，不应再有 '{{' 或 '}}'
        stripped = _PLACEHOLDER_RE.sub("", text)
        assert "{{" not in stripped, f"{subdir}/{name} 含未闭合 {{"
        assert "}}" not in stripped, f"{subdir}/{name} 含未闭合 }}"


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

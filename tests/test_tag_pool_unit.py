"""规则标签池单测：technical/soft/business 词典命中、同义词、大小写、去重、上限、空输入。

EXP-P1-06c："规则标签池无候选才 LLM"（§26），本模块零 LLM。
"""

from app.tools.tag_pool import MAX_TAGS, recommend_tags_from_pool


def test_technical_skills_hit():
    """技术栈词典命中（technical_skills.json）。"""
    tags = recommend_tags_from_pool("使用 Python 开发推荐系统后端，部署 Docker 容器")
    assert "Python" in tags
    assert "Docker" in tags


def test_soft_skills_hit():
    """能力维度词典命中（soft_skills.json）。"""
    tags = recommend_tags_from_pool(
        "具备良好的沟通能力与团队协作能力，结果导向推进落地"
    )
    assert "沟通能力" in tags
    assert "团队协作" in tags


def test_business_field_hit():
    """业务领域词典命中（business_fields.json tag + keywords 同义词）。"""
    tags = recommend_tags_from_pool("负责跨境电商平台订单履约链路")
    assert "电商" in tags


def test_business_field_synonym_keyword_hit():
    """同义词关键词命中（如 'SaaS' 命中企业服务）。"""
    tags = recommend_tags_from_pool("在 SaaS 产品团队承担核心研发")
    assert "企业服务" in tags


def test_ascii_case_insensitive():
    """ASCII 关键词大小写不敏感。"""
    tags = recommend_tags_from_pool("python 编程与 node.js 服务端开发")
    assert "Python" in tags
    assert "Node.js" in tags


def test_tags_dedup_and_order():
    """技术栈优先，业务领域其次，能力维度最后，且去重。"""
    tags = recommend_tags_from_pool(
        "Python 后端开发，负责电商系统，强调团队协作与执行力"
    )
    assert tags.count("Python") == 1
    assert tags.index("Python") < tags.index("电商")
    assert tags.index("电商") < tags.index("团队协作")


def test_max_tags_cap():
    """命中超过 MAX_TAGS 时截断。"""
    text = " ".join(
        [
            "Python",
            "Docker",
            "K8s",
            "Redis",
            "MySQL",
            "Java",
            "React",
            "Vue",
            "机器学习",
            "数据分析",
        ]
    )
    tags = recommend_tags_from_pool(text)
    assert len(tags) <= MAX_TAGS


def test_no_match_returns_empty():
    """无词典命中返回空列表。"""
    assert recommend_tags_from_pool("我做了一段经历") == []


def test_empty_or_whitespace_input():
    """空/空白输入返回空列表。"""
    assert recommend_tags_from_pool("") == []
    assert recommend_tags_from_pool("   ") == []

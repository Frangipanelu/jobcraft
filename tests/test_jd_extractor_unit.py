"""jd_extractor 单测：算法抽取（无 LLM）。"""

from app.pipeline.jd_classifier import ClassLabel, ClassifiedItem, classify_jd
from app.pipeline.jd_extractor import (
    JDExtraction,
    extract_jd,
    extract_keywords,
    _capability_parts,
    _find_tech_tokens,
)
from app.pipeline.jd_structurer import SectionKind, structure_jd
from app.schemas.jobcraft import ATSProfile


def _item(
    text: str, label: ClassLabel, section: SectionKind = SectionKind.REQUIREMENTS
):
    return ClassifiedItem(
        item_id="t",
        section=section,
        text=text,
        start=0,
        end=len(text),
        label=label,
        confidence=1.0,
        rule="test",
    )


def _extract(jd_text: str) -> JDExtraction:
    return extract_jd(structure_jd(jd_text), classify_jd(structure_jd(jd_text)))


class TestFindTechTokens:
    def test_multiword_prefers_longer(self):
        assert "Vue.js" in _find_tech_tokens("负责 Vue.js 前端开发")

    def test_substring_inside_longer_dropped(self):
        tokens = _find_tech_tokens("掌握 Redis 缓存使用")
        assert "Redis" in tokens

    def test_case_insensitive(self):
        assert "pytest" in _find_tech_tokens("编写 pytest 测试")


class TestCapabilityRemainder:
    def test_strip_verb_and_connector(self):
        assert _capability_parts("精通数据链路设计") == ["数据链路设计"]

    def test_no_verb_returns_empty(self):
        assert _capability_parts("数据报表") == []

    def test_splits_noun_list(self):
        assert _capability_parts("熟悉功能测试、回归测试、自动化测试") == [
            "功能测试",
            "回归测试",
            "自动化测试",
        ]


class TestEducationYearsSalaryLocation:
    def test_education_from_gate(self):
        out = _extract("职位描述\n岗位要求：\n1）统招本科及以上学历，计算机相关专业；")
        assert out.education and "本科" in out.education

    def test_years_from_gate(self):
        out = _extract("职位描述\n岗位要求：\n1）3年以上后端开发经验；")
        assert out.years_of_experience and "3年以上" in out.years_of_experience

    def test_salary_and_location_from_meta(self):
        out = _extract("坐标北京\n薪资：25-40K·14薪\n职位描述\n岗位要求：\n熟悉 Python")
        assert out.salary and "25" in out.salary
        assert out.location and "北京" in out.location


class TestSkills:
    def test_tech_tokens_extracted(self):
        items = [
            _item("熟悉 Python、FastAPI", ClassLabel.REQUIRED),
            _item("掌握 MySQL、Redis", ClassLabel.REQUIRED),
        ]
        out = extract_jd(structure_jd(""), items)
        assert set(out.required_skills) == {"Python", "FastAPI", "MySQL", "Redis"}

    def test_preferred_separate(self):
        items = [
            _item("熟悉 Python", ClassLabel.REQUIRED),
            _item("了解 Flink", ClassLabel.PREFERRED),
        ]
        out = extract_jd(structure_jd(""), items)
        assert out.required_skills == ["Python"]
        assert out.preferred_skills == ["Flink"]

    def test_unseen_skill_falls_back_to_phrase(self):
        out = extract_jd(
            structure_jd(""), [_item("精通数据链路设计", ClassLabel.REQUIRED)]
        )
        assert "数据链路设计" in out.required_skills

    def test_responsibility_mentions_are_required_skills(self):
        items = [
            _item(
                "负责搭建Flink实时计算链路",
                ClassLabel.RESPONSIBILITY,
                SectionKind.RESPONSIBILITIES,
            ),
            _item(
                "参与 CI/CD 流程建设",
                ClassLabel.RESPONSIBILITY,
                SectionKind.RESPONSIBILITIES,
            ),
        ]
        out = extract_jd(structure_jd(""), items)
        assert {"Flink", "CI/CD"} <= set(out.required_skills)

    def test_soft_skills_kept(self):
        out = extract_jd(
            structure_jd(""),
            [_item("具备良好的沟通能力和团队协作精神", ClassLabel.SOFT_SKILL)],
        )
        assert out.soft_skills == ["具备良好的沟通能力和团队协作精神"]


class TestMetrics:
    def test_percent_metric(self):
        out = extract_jd(
            structure_jd(""), [_item("将商品转化率提升20%以上", ClassLabel.REQUIRED)]
        )
        assert any("20%" in m for m in out.key_metrics)

    def test_customer_count_metric(self):
        out = extract_jd(
            structure_jd(""),
            [_item("服务500+客户，覆盖 30 家门店", ClassLabel.RESPONSIBILITY)],
        )
        assert any("500" in m for m in out.key_metrics)
        assert any("30" in m for m in out.key_metrics)


class TestKeywords:
    def test_level_weights(self):
        important = _item("必须熟练掌握 Python 网络编程", ClassLabel.REQUIRED)
        normal = _item("熟悉 Python 基础语法", ClassLabel.REQUIRED)
        signals = extract_keywords([important, normal])
        python = next(s for s in signals if s.keyword == "Python")
        assert python.importance == "high"
        assert python.score >= 5

    def test_preferred_weighs_less(self):
        sig = extract_keywords(
            [_item("了解 Flink 流处理", ClassLabel.PREFERRED, SectionKind.PREFERRED)]
        )
        flink = next(s for s in sig if s.keyword == "Flink")
        assert flink.score <= 3

    def test_categories(self):
        soft = next(
            s
            for s in extract_keywords(
                [_item("具备较强的沟通协调能力", ClassLabel.REQUIRED)]
            )
            if s.category == "soft"
        )
        assert soft.category == "soft"

        prod = extract_keywords([_item("负责需求分析与原型设计", ClassLabel.REQUIRED)])
        assert any(s.category == "product" for s in prod)


class TestAtsProfileContract:
    def test_legacy_dict_still_validates(self):
        ats = ATSProfile.model_validate(
            {
                "job_title": "后端工程师",
                "required_skills": ["Python"],
                "responsibilities": ["接口开发"],
                "culture_keywords": ["代码规范"],
                "salary": "25K",
            }
        )
        assert ats.required_skills == ["Python"]
        assert ats.soft_skills == []
        assert ats.core_keywords == []

    def test_new_optional_fields_roundtrip(self):
        ats = ATSProfile.model_validate(
            {
                "job_title": "后端工程师",
                "soft_skills": ["沟通能力"],
                "core_keywords": [
                    {
                        "keyword": "Python",
                        "category": "technical",
                        "importance": "high",
                        "score": 5,
                        "evidence": "熟悉 Python",
                    }
                ],
            }
        )
        assert ats.soft_skills == ["沟通能力"]
        assert ats.core_keywords[0].keyword == "Python"


class TestEndToEnd:
    def test_minimal_jd(self):
        jd = """职位描述
岗位职责：
1）负责核心交易系统后端开发；
2）优化接口性能，提升响应速度20%；
岗位要求：
1）本科及以上学历，计算机相关专业；
2）5年以上 Java 开发经验，熟悉 Spring Cloud、Redis；
3）具备良好的沟通能力。
加分项：
- 熟悉 Kafka"""
        out = _extract(jd)
        assert out.education and "本科" in out.education
        assert out.years_of_experience and "5年以上" in out.years_of_experience
        assert {"Java", "Spring Cloud", "Redis"} <= set(out.required_skills)
        assert "Kafka" in out.preferred_skills
        assert out.responsibilities
        assert any("20%" in m for m in out.key_metrics)
        assert out.soft_skills
        assert any(s.importance == "high" for s in out.core_keywords)

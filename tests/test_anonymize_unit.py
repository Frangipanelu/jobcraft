"""脱敏管线单测（T-EVAL-2 A2 跟进）。

覆盖 scrub_text 正则替换、load_text_file 多格式读取、docx 段落提取
（stdlib zipfile+ElementTree）、build_review_case 端到端脱敏。
"""

from __future__ import annotations

import json
import zipfile

import pytest

from evaluation.anonymize import (
    build_prep_case,
    build_review_case,
    load_text_file,
    normalize_transcript,
    parse_speaker_map,
    scrub_text,
)

_DOCX_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>面试官：你好，请介绍自己。</w:t></w:r></w:p>
    <w:p><w:r><w:t>候选人：我叫张三，手机13800138000</w:t></w:r></w:p>
    <w:p><w:r><w:t>邮箱zhangsan@example.com</w:t><w:tab/><w:t>微信zhangsan_wx</w:t></w:r></w:p>
  </w:body>
</w:document>
"""


def _make_docx(path, xml: str = _DOCX_XML) -> None:
    """在临时目录构造含 word/document.xml 的最小合法 docx。"""
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("word/document.xml", xml)


class TestScrubText:
    """scrub_text 确定性正则替换。"""

    def test_phone(self):
        assert "[手机]" in scrub_text("我的电话是13800138000，谢谢")
        assert "13800138000" not in scrub_text("我的电话是13800138000")

    def test_phone_with_country_prefix(self):
        assert "[手机]" in scrub_text("联系电话 +86 13800138000")

    def test_email(self):
        out = scrub_text("联系邮箱 test@example.com 谢谢")
        assert "[邮箱]" in out
        assert "test@example.com" not in out

    def test_idcard_before_phone(self):
        """18 位身份证先于手机号替换，不被手机号正则截断误伤。"""
        out = scrub_text("身份证号 110101199001011234")
        assert "[身份证]" in out
        assert "110101" not in out

    def test_wechat_and_qq(self):
        assert "[微信]" in scrub_text("微信 abcdefg123 加我")
        assert "[QQ]" in scrub_text("QQ 12345678 加我")

    def test_names_replaced_longest_first(self):
        out = scrub_text("张三丰和张三都来了", names=["张三", "张三丰"])
        assert "张三" not in out.replace("[候选人]", "")
        assert out.count("[候选人]") == 2

    def test_school_replaced(self):
        assert "[学校]" in scrub_text("毕业于华中科技大学", school="华中科技大学")

    def test_company_kept(self):
        """公司名保留（评测需要真实语境）。"""
        text = "面试官：你在字节跳动做什么？"
        assert "字节跳动" in scrub_text(text)

    def test_empty_input(self):
        assert scrub_text("") == ""


class TestLoadTextFile:
    """load_text_file 多格式读取。"""

    def test_txt(self, tmp_path):
        p = tmp_path / "a.txt"
        p.write_text("面试官：你好", encoding="utf-8")
        assert load_text_file(p) == "面试官：你好"

    def test_md(self, tmp_path):
        p = tmp_path / "a.md"
        p.write_text("# 标题\n\n面试官：你好", encoding="utf-8")
        assert "面试官：你好" in load_text_file(p)

    def test_docx(self, tmp_path):
        p = tmp_path / "a.docx"
        _make_docx(p)
        out = load_text_file(p)
        assert "面试官：你好，请介绍自己。" in out
        assert "候选人：我叫张三" in out
        # 段落换行 + 段内 tab 保留
        assert "邮箱zhangsan@example.com\t微信zhangsan_wx" in out

    def test_unsupported_extension(self, tmp_path):
        p = tmp_path / "a.pdf"
        p.write_bytes(b"%PDF")
        with pytest.raises(ValueError, match="不支持"):
            load_text_file(p)

    def test_broken_docx(self, tmp_path):
        p = tmp_path / "a.docx"
        p.write_bytes(b"not a zip")
        with pytest.raises(ValueError, match="非法 docx"):
            load_text_file(p)


class TestNormalizeTranscript:
    """normalize_transcript 会议转录归一化。"""

    RAW = (
        "聚智科技产品助理岗位面试沟通\n\n\n关键词\n产品助理 顺德\n\n\n"
        "全文概要\n求职者与公司讨论了产品助理岗位。\n\n\n"
        "讲话人1 - 0:00\n我看一下你的简历，你之前是做项目助理的，那你能为产品助理岗位带来什么呢？\n\n"
        "讲话人2 - 0:40\n我觉得项目助理和产品助理本质上有一部分工作内容是可以迁移的，我在之前的实习中也参与过需求分析。\n\n"
        "讲话人1 - 5:47\n啊行，你把你扫回过来就一个多小时的了。对。\n\n\n"
        "（内容由AI生成）"
    )

    def test_parse_speaker_map(self):
        assert parse_speaker_map("1=面试官,2=候选人") == {"1": "面试官", "2": "候选人"}
        assert parse_speaker_map(" 1 = 面试官 , 2=候选人 ") == {
            "1": "面试官",
            "2": "候选人",
        }
        assert parse_speaker_map("bad,,=x") == {}

    def test_strip_preamble_and_footer(self):
        out = normalize_transcript(self.RAW, speaker_map={"1": "面试官", "2": "候选人"})
        assert "关键词" not in out
        assert "全文概要" not in out
        assert "（内容由AI生成）" not in out
        assert "聚智科技产品助理岗位面试沟通" not in out
        assert out.splitlines()[0].startswith("面试官 0:00")

    def test_speaker_map_rewrites_label_and_joins_content(self):
        out = normalize_transcript(self.RAW, speaker_map={"1": "面试官", "2": "候选人"})
        lines = out.splitlines()
        assert lines[0].startswith("面试官 0:00 我看一下你的简历")
        assert lines[1].startswith("候选人 0:40 我觉得项目助理和产品助理")
        assert all("讲话人" not in line for line in lines)

    def test_speaker_map_none_keeps_structure(self):
        out = normalize_transcript(self.RAW)
        assert "讲话人1 - 0:00" in out
        assert "我看一下你的简历" in out
        assert "（内容由AI生成）" not in out

    def test_unmapped_speaker_keeps_original_form(self):
        out = normalize_transcript(self.RAW, speaker_map={"1": "面试官"})
        assert "面试官 0:00" in out
        assert "讲话人2 - 0:40" in out

    def test_normalized_text_parses_with_explicit_roles(self):
        """归一化后 _parse_dialogue 直接识别显式角色（绕过内容启发式）。"""
        from app.tools.interview_dialogue import _build_qa_pairs, _parse_dialogue

        out = normalize_transcript(self.RAW, speaker_map={"1": "面试官", "2": "候选人"})
        dialogue = _parse_dialogue(out)
        assert dialogue, "解析不应为空"
        roles = {(d["speaker"], d["role"]) for d in dialogue}
        assert ("面试官", "interviewer") in roles
        assert ("候选人", "candidate") in roles
        assert len(_build_qa_pairs(dialogue)) >= 1


class TestBuildCase:
    """build_review_case / build_prep_case 端到端。"""

    def test_review_case_scrubbed_and_company_kept(self):
        case = build_review_case(
            "候选人：我是张三，13800138000，公司是字节跳动",
            case_id="rev_t1",
            company="字节跳动",
            position="后端",
            round_type="技术面",
            names=["张三"],
        )
        assert case["source"] == "real"
        assert "张三" not in case["raw_text"].replace("[候选人]", "")
        assert "13800138000" not in case["raw_text"]
        assert case["company"] == "字节跳动"

    def test_prep_case_scrubs_cards(self):
        case = build_prep_case(
            case_id="prep_t1",
            company="美团",
            position="后端",
            round_type="技术面",
            jd_text="联系 HR hr@meituan.com",
            cards=[
                {
                    "id": 1,
                    "title": "张三的项目",
                    "summary": "做订单",
                    "content": "",
                    "tags": [],
                }
            ],
            names=["张三"],
        )
        assert "[邮箱]" in case["jd_text"]
        assert case["cards"][0]["title"] == "[候选人]的项目"
        assert case["company"] == "美团"

    def test_jsonl_row_is_utf8_serializable(self):
        case = build_review_case(
            "面试官：你好",
            case_id="rev_t2",
            company="腾讯",
            position="后端",
            round_type="技术面",
        )
        line = json.dumps(case, ensure_ascii=False)
        assert json.loads(line)["case_id"] == "rev_t2"

"""规则分块器回归测试（EXPERIENCE_SPEC §29.1）。

对 tests/fixtures/resume_samples/ 下的脱敏简历跑纯规则分块，
逐块比对 expected.json 的（company/role/period/title）。
"""

import glob
import json
import os

import pytest

from app.tools.resume_splitter import split_resume_text

SAMPLES_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "resume_samples")

_SAMPLE_FILES = sorted(glob.glob(os.path.join(SAMPLES_DIR, "*.txt")))


def _block_hit(got, expected_entry) -> bool:
    """任一关键字段（period/title/company/role）命中即视为该块被识别。"""
    for g in got:
        if expected_entry["period"] and expected_entry["period"] == g.get("period"):
            return True
        if expected_entry["title"] and expected_entry["title"] == g.get("title"):
            return True
        if expected_entry["company"] and expected_entry["company"] == g.get("company"):
            return True
        if expected_entry["role"] and expected_entry["role"] == g.get("role"):
            return True
    return False


@pytest.mark.parametrize(
    "txt_path",
    [os.path.basename(p) for p in _SAMPLE_FILES],
    ids=[os.path.basename(p)[: -len(".txt")] for p in _SAMPLE_FILES],
)
def test_split_resume_sample(txt_path: str):
    """每份样本：块数与内容均应与预期一致（或返回 None 触发 LLM 兜底）。"""
    base = txt_path[: -len(".txt")]
    with open(os.path.join(SAMPLES_DIR, txt_path), encoding="utf-8") as f:
        raw_text = f.read()
    with open(
        os.path.join(SAMPLES_DIR, base + ".expected.json"), encoding="utf-8"
    ) as f:
        expected = json.load(f)

    got = split_resume_text(raw_text)
    exp_entries = expected["entries"]

    # 规则无法切分视为合法降级（调用方会走 LLM 兜底）
    if got is None:
        assert len(exp_entries) < 4, (
            f"{base}: 规则分块返回 None，但期望 {len(exp_entries)} 块"
        )
        return

    assert len(got) == len(exp_entries), (
        f"{base}: 块数不符 expected={len(exp_entries)} got={len(got)}"
    )
    for e in exp_entries:
        assert _block_hit(got, e), f"{base}: 未识别块 {e}"


def test_all_samples_have_expected():
    """每个 .txt 必须有配对 expected.json，且无孤立 expected。"""
    txt_bases = {os.path.basename(p)[: -len(".txt")] for p in _SAMPLE_FILES}
    exp_bases = {
        os.path.basename(p)[: -len(".expected.json")]
        for p in glob.glob(os.path.join(SAMPLES_DIR, "*.json"))
    }
    assert txt_bases == exp_bases
    assert len(txt_bases) >= 10


def test_rules_never_invent_fields():
    """规则产物不编造：period/title/company/role 只来自原文子串。

    例外白名单：``[个人项目]`` 占位（仅 project 卡，非原文子串）。
    """
    for txt in _SAMPLE_FILES:
        raw_text = open(txt, encoding="utf-8").read()
        got = split_resume_text(raw_text)
        if not got:
            continue
        for e in got:
            for field in ("period", "company", "role", "title"):
                val = (e.get(field) or "").strip()
                if not val or val == "[个人项目]":
                    continue
                if val not in raw_text:
                    pytest.fail(f"{os.path.basename(txt)}: 编造字段 {field}={val}")


def test_narrative_company_not_dependent_on_role_verb_table():
    """叙述式公司锚与动词表解绑：动词表外动词只造成 role 留空，不丢块不丢公司。"""
    raw = (
        "工作经历\n\n"
        "我于星辰科技主导支付模块重构，系统吞吐由 800 QPS 提升至 3000 QPS。\n\n"
        "此前在锐锋科技做功能测试，设计并落地了回归用例库。"
    )
    got = split_resume_text(raw)
    assert got is not None
    assert [e["company"] for e in got] == ["星辰科技", "锐锋科技"]
    assert got[0]["role"] == ""  # 动词表盲区：role 留空
    assert got[1]["role"] == "功能测试"


def test_project_placeholder_only_for_empty_company():
    """project 卡 company 为空 → [个人项目]；work 卡空公司保持留空（不编造）。"""
    project_raw = (
        "项目经历\n2021.03 - 2022.07  共享单车订单系统重构\n个人主导重构了订单状态机。"
    )
    got_project = split_resume_text(project_raw)
    assert got_project is not None
    entry = got_project[0]
    assert entry["card_type"] == "project"
    assert entry["company"] == "[个人项目]"
    assert entry["period"] == "2021.03 - 2022.07"

    work_raw = "工作经历\n2020.01 - 2020.06"
    got_work = split_resume_text(work_raw)
    assert got_work is not None
    work_entry = got_work[0]
    assert work_entry["card_type"] == "work"
    assert work_entry["company"] == ""


def test_project_section_signal_drives_card_type():
    """时间锚点 + 「项目经历」章节信号 → project 卡（不依赖能否提取 company）。"""
    raw = (
        "项目经历\n"
        "2022.10 - 2023.04  在线教育用户行为分析（课程项目）\n"
        "爬取课程数据 5w 条并完成分析。"
    )
    got = split_resume_text(raw)
    assert got is not None
    assert got[0]["card_type"] == "project"
    assert got[0]["company"] == "[个人项目]"

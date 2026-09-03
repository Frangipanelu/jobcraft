"""SubmissionStatus 状态机单元测试（app/schemas/submission_status.py）"""


def _mod():
    from app.schemas import submission_status

    return submission_status


def test_enum_values_are_english_codes():
    """枚举值应为英文码，不含中文。"""
    m = _mod()
    values = {s.value for s in m.SubmissionStatus}
    assert values == {
        "APPLIED", "INVITED", "ROUND_1", "ROUND_2", "OFFER", "CLOSED"
    }


def test_cn_map_covers_all_statuses():
    """每个枚举都有中文显示。"""
    m = _mod()
    assert len(m.SUBMISSION_STATUS_CN) == 6
    assert m.SUBMISSION_STATUS_CN[m.SubmissionStatus.APPLIED] == "已投递"
    assert m.SUBMISSION_STATUS_CN[m.SubmissionStatus.INVITED] == "面试邀约"
    assert m.SUBMISSION_STATUS_CN[m.SubmissionStatus.ROUND_1] == "一面"
    assert m.SUBMISSION_STATUS_CN[m.SubmissionStatus.ROUND_2] == "二面"
    assert m.SUBMISSION_STATUS_CN[m.SubmissionStatus.OFFER] == "Offer"
    assert m.SUBMISSION_STATUS_CN[m.SubmissionStatus.CLOSED] == "已关闭"


def test_normalize_status_english_and_legacy_cn():
    """新旧值都应归一化为枚举。"""
    m = _mod()
    assert m.normalize_status("APPLIED") is m.SubmissionStatus.APPLIED
    assert m.normalize_status("已投递") is m.SubmissionStatus.APPLIED
    assert m.normalize_status("面试邀约") is m.SubmissionStatus.INVITED
    assert m.normalize_status("一面") is m.SubmissionStatus.ROUND_1
    assert m.normalize_status("二面") is m.SubmissionStatus.ROUND_2
    assert m.normalize_status("offer") is m.SubmissionStatus.OFFER
    assert m.normalize_status("已关闭") is m.SubmissionStatus.CLOSED
    assert m.normalize_status("未知状态") is None
    assert m.normalize_status(None) is None


def test_is_valid_transition_forward():
    """顺向推进合法。"""
    m = _mod()
    assert m.is_valid_transition("APPLIED", "INVITED")
    assert m.is_valid_transition("INVITED", "ROUND_1")
    assert m.is_valid_transition("ROUND_1", "ROUND_2")
    assert m.is_valid_transition("ROUND_2", "OFFER")


def test_is_valid_transition_closed_from_any_stage():
    """任意阶段可提前 CLOSED。"""
    m = _mod()
    for stage in ("APPLIED", "INVITED", "ROUND_1", "ROUND_2"):
        assert m.is_valid_transition(stage, "CLOSED")


def test_is_valid_transition_illegal():
    """非法流转被拒绝。"""
    m = _mod()
    assert not m.is_valid_transition("APPLIED", "OFFER")
    assert not m.is_valid_transition("APPLIED", "ROUND_2")
    assert not m.is_valid_transition("INVITED", "OFFER")
    # 终态不可再流转
    assert not m.is_valid_transition("OFFER", "CLOSED")
    assert not m.is_valid_transition("CLOSED", "APPLIED")
    assert not m.is_valid_transition("unknown", "APPLIED")
    assert not m.is_valid_transition("APPLIED", None)


def test_next_statuses():
    """可达状态集合。"""
    m = _mod()
    assert m.next_statuses("APPLIED") == {
        m.SubmissionStatus.INVITED,
        m.SubmissionStatus.CLOSED,
    }
    assert m.next_statuses("ROUND_2") == {
        m.SubmissionStatus.OFFER,
        m.SubmissionStatus.CLOSED,
    }
    assert m.next_statuses("OFFER") == set()
    assert m.next_statuses("unknown") == set()


def test_status_to_cn():
    """状态→中文；未知回退原值。"""
    m = _mod()
    assert m.status_to_cn("APPLIED") == "已投递"
    assert m.status_to_cn("Offer") == "Offer"
    assert m.status_to_cn("乱码") == "乱码"
    assert m.status_to_cn(None) == ""

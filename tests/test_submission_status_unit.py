"""SubmissionStatus 状态机单元测试（app/schemas/submission_status.py）"""


def _mod():
    from app.schemas import submission_status

    return submission_status


def test_enum_values_are_english_codes():
    """枚举值应为英文码，不含中文。"""
    m = _mod()
    values = {s.value for s in m.SubmissionStatus}
    assert values == {
        "PREPARED",
        "APPLIED",
        "INVITED",
        "ROUND_1",
        "ROUND_2",
        "OFFER",
        "CLOSED",
    }


def test_cn_map_covers_all_statuses():
    """每个枚举都有中文显示。"""
    m = _mod()
    assert len(m.SUBMISSION_STATUS_CN) == 7
    assert m.SUBMISSION_STATUS_CN[m.SubmissionStatus.PREPARED] == "待投递"
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


# ============================================================
# P11-a：创建 ≠ 投递（PREPARED / APPLIED 语义对齐）
# ============================================================


def test_prepared_normalizes_from_legacy_cn():
    """P11-a：中文「待投递」归一化为 PREPARED。"""
    m = _mod()
    assert m.normalize_status("待投递") is m.SubmissionStatus.PREPARED
    assert m.normalize_status("PREPARED") is m.SubmissionStatus.PREPARED


def test_prepared_transitions():
    """P11-a：待投递可推进到已投递 / 面试邀约 / 已关闭。"""
    m = _mod()
    assert m.is_valid_transition("PREPARED", "APPLIED")
    assert m.is_valid_transition("PREPARED", "INVITED")
    assert m.is_valid_transition("PREPARED", "CLOSED")
    # 未投递不可倒退为面试流程
    assert not m.is_valid_transition("PREPARED", "ROUND_1")


def test_effective_status_projects_legacy_applied_without_delivery():
    """P11-a：存量 `APPLIED + delivered=0` 读时投影为「待投递」。"""
    m = _mod()
    assert m.effective_status("APPLIED", False) == "PREPARED"
    assert m.effective_status("APPLIED", True) == "APPLIED"
    assert m.effective_status("PREPARED", False) == "PREPARED"
    assert m.effective_status("INVITED", False) == "INVITED"
    assert m.effective_status("乱码", False) == "乱码"
    assert m.effective_status(None, False) is None


def test_requires_delivered():
    """P11-a：面试/offer 类状态隐含已投递。"""
    m = _mod()
    for s in ("INVITED", "ROUND_1", "ROUND_2", "OFFER"):
        assert m.requires_delivered(s)
    for s in ("PREPARED", "APPLIED", "CLOSED"):
        assert not m.requires_delivered(s)
    assert not m.requires_delivered("乱码")
    assert not m.requires_delivered(None)

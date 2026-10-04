"""方向词典规则匹配（T-M4-3，零 LLM，feature-alignment Q4 裁决）。

职责：从 JD 文本（岗位名/职责/要求拼接）按「关键词命中计数」匹配方向模板，
返回四维建议（industry / product / scenario / skills）与建议方向名，
供结构化表单「词典建议」按钮使用（低置信 → 用户确认，全自动归 Phase-2）。

词典：``app/pipeline/data/direction_dictionary.json``（无新表，同 tag_pool 惯例）：
每条含 ``name`` / ``keywords`` / 四维字符串；词典**不产** job_function /
primary_role（职能与主角色由用户手动填写，Q4 范围只含 Industry/Product/Scenario/Skills）。

原则：
- 零 LLM、无状态、确定性：相同输入 → 相同输出。
- 命中关键词最多者优先，平手按词典顺序（先出现者胜）。
- 维度值受 payload 长度约束（industry 100 / product 200 / scenario 200 /
  skills 500），词典结构测试守卫越界。
"""

import json
from pathlib import Path
from typing import Dict, List

_DATA_DIR = Path(__file__).resolve().parent.parent / "pipeline" / "data"

_DICTIONARY: List[Dict[str, object]] = json.loads(
    (_DATA_DIR / "direction_dictionary.json").read_text(encoding="utf-8")
)["directions"]

# 词典产出的维度（顺序即响应字段顺序；job_function/primary_role 不在其中）
_DIM_FIELDS = ("industry", "product", "scenario", "skills")


def suggest_direction(text: str) -> Dict[str, str]:
    """词典匹配方向模板，返回建议方向名与四维。

    :param text: JD 文本（岗位名/职责/要求的拼接，可为空）
    :return: 未命中返回 ``{}``；命中返回
        ``{"direction_name": ..., "industry": ..., "product": ...,
        "scenario": ..., "skills": ...}``——词典未给出的维度省略键。
        确定性：命中关键词数最多者优先，平手按词典顺序。
    """
    if not text or not text.strip():
        return {}

    text_lower = text.lower()
    best_entry: Dict[str, object] | None = None
    best_hits = 0

    for entry in _DICTIONARY:
        keywords = entry.get("keywords")
        if not isinstance(keywords, list):
            continue
        hits = 0
        for kw in keywords:
            kw_lower = str(kw).lower().strip()
            if kw_lower and kw_lower in text_lower:
                hits += 1
        # 严格大于：平手保留先出现者（词典顺序即优先级）
        if hits > best_hits:
            best_hits = hits
            best_entry = entry

    if best_entry is None:
        return {}

    result: Dict[str, str] = {"direction_name": str(best_entry["name"])}
    for dim in _DIM_FIELDS:
        value = best_entry.get(dim)
        if isinstance(value, str) and value.strip():
            result[dim] = value.strip()
    return result

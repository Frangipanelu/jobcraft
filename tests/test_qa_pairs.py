import sys

sys.path.insert(0, r"d:\A-pythonProject\AI-learning\multi-agent\jobcraft")
from app.tools.interview_review import (
    _parse_dialogue,
    _build_qa_pairs,
)

with open("tests/long_user_sample.txt", "r", encoding="utf-8") as f:
    raw = f.read()

dialogue = _parse_dialogue(raw)
qa_pairs = _build_qa_pairs(dialogue)
print(f"QA pairs: {len(qa_pairs)}")
for qa in qa_pairs[:5]:
    print(f"Q{qa['sequence']} [{qa['start_time']}] {qa['question_text'][:60]!r}")
    print(f"  A: {qa['my_answer'][:80]!r}")

print(f"\nTotal QA pairs: {len(qa_pairs)}")

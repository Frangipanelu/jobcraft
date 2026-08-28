import sys

sys.path.insert(0, r"d:\A-pythonProject\AI-learning\multi-agent\jobcraft")
from app.tools.interview_review import _parse_dialogue

samples = {
    "standard": """面试官 09:00 请你先做一个自我介绍。
我：我叫李明。
面试官 09:02 你们订单系统每天的量级大概是多少？
我：日均几百万单。""",
    "qa_colon": """Q: 请你先做一个自我介绍。
A: 我叫李明。
Q: 你们订单系统每天的量级多少？
A: 日均几百万单。""",
    "speaker12": """Speaker 1: 请你先做一个自我介绍。
Speaker 2: 我叫李明。
Speaker 1: 你们订单系统量级多少？
Speaker 2: 日均几百万单。""",
    "timestamp_only": """09:00 请你先做一个自我介绍。
09:01 我叫李明。
09:02 你们订单系统量级多少？
09:03 日均几百万单。""",
    "continuation": """面试官：遇到过什么性能问题？
我：大促时数据库压力大。
我们做了缓存。
也做了分库分表。""",
    "with_title": """面试记录

讲话人1 - 0:22 请自我介绍。
讲话人2 - 0:26 我叫李明。""",
}

for name, text in samples.items():
    print(f"--- {name} ---")
    for d in _parse_dialogue(text):
        print(f"  {d['role']:12} {d['speaker']}: {d['content'][:40]!r}")
    print()

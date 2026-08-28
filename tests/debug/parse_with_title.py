import sys

sys.path.insert(0, r"d:\A-pythonProject\AI-learning\multi-agent\jobcraft")
from app.tools.interview_review import _parse_dialogue

text = """陆晶晶面试记录

讲话人1 - 0:22 
 那麻烦您做一个简单的自我介绍。面试官你好。 
 
 讲话人2 - 0:26 
 我是陆晶晶，毕业于广东技术师范大学... 
"""

for d in _parse_dialogue(text):
    print(
        f"{d['sequence']:2} {d['role']:12} {d['speaker']} {d['time']} {d['content'][:40]!r}"
    )

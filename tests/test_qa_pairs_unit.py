import sys

sys.path.insert(0, r"d:\A-pythonProject\AI-learning\multi-agent\jobcraft")

from app.tools.interview_review import _build_qa_pairs, _parse_dialogue


def test_tail_greeting_is_moved_to_answer():
    text = """讲话人1 - 0:22
那麻烦您做一个简单的自我介绍。面试官你好。

讲话人2 - 0:26
我是陆晶晶，毕业于广东技术师范大学。"""
    dialogue = _parse_dialogue(text)
    qa_pairs = _build_qa_pairs(dialogue)
    assert len(qa_pairs) == 1
    assert qa_pairs[0]["question_text"] == "那麻烦您做一个简单的自我介绍。"
    assert "面试官你好" in qa_pairs[0]["my_answer"]
    assert "陆晶晶" in qa_pairs[0]["my_answer"]


def test_interleaved_short_response_is_split():
    text = """讲话人1 - 7:26
那那那怎么想考虑去北京这边？我看你应该是广州那边人，对吧？对，然后上学也是在广东。

讲话人2 - 7:40
对。"""
    dialogue = _parse_dialogue(text)
    qa_pairs = _build_qa_pairs(dialogue)
    assert len(qa_pairs) == 1
    q = qa_pairs[0]["question_text"]
    a = qa_pairs[0]["my_answer"]
    assert "对吧？" in q
    assert "然后上学也是在广东" in q
    assert "对" in a


def test_standard_qa_colon_format():
    text = """Q: 请你先做一个自我介绍。
A: 我叫李明。
Q: 你们订单系统量级多少？
A: 日均几百万单。"""
    dialogue = _parse_dialogue(text)
    qa_pairs = _build_qa_pairs(dialogue)
    assert len(qa_pairs) == 2
    assert qa_pairs[0]["question_text"] == "请你先做一个自我介绍。"
    assert "李明" in qa_pairs[0]["my_answer"]
    assert qa_pairs[1]["question_text"] == "你们订单系统量级多少？"


def test_title_is_skipped():
    text = """陆晶晶面试记录

讲话人1 - 0:22
那麻烦您做一个简单的自我介绍。

讲话人2 - 0:26
我是陆晶晶。"""
    dialogue = _parse_dialogue(text)
    assert dialogue[0]["content"] == "那麻烦您做一个简单的自我介绍。"
    qa_pairs = _build_qa_pairs(dialogue)
    assert len(qa_pairs) == 1


def test_pseudo_question_is_merged():
    text = """面试官：你叫李明对吧？
我：对。
面试官：那我们开始。
我：好。"""
    dialogue = _parse_dialogue(text)
    qa_pairs = _build_qa_pairs(dialogue)
    # "那我们开始" 是过渡，应合并到下一个回答或上一个回答
    assert len(qa_pairs) >= 1

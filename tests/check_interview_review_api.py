import textwrap

import requests

raw_text = textwrap.dedent("""
面试官 09:00 请你先做一个自我介绍。
候选人：我叫李明，毕业于某某大学计算机专业，之前在一家电商公司做了3年后端开发，主要负责订单系统和支付链路。
面试官 09:02 你们订单系统每天的量级大概是多少？遇到过什么性能问题？
候选人：日均几百万单吧。性能问题主要是大促时数据库压力大，我们做了缓存和分库分表。
面试官 09:05 能具体说说分库分表的策略吗？
候选人：就是按用户ID取模，分成64个库，每个库16张表。
面试官 09:08 为什么要按用户ID取模，而不是按订单ID？有什么优缺点？
候选人：这个……当时 leader 定的，我没太深入想。
面试官 09:10 你对我们这个岗位最感兴趣的地方是什么？
候选人：我觉得贵公司业务发展很快，技术挑战也比较大，想过来学习成长。
""").strip()

payload = {
    "user_id": 1,
    "company": "测试公司",
    "position": "高级后端工程师",
    "round_type": "技术面",
    "job_analysis_id": None,
    "raw_text": raw_text,
}

if __name__ == "__main__":
    print("1. 创建面试复盘...")
    resp = requests.post(
        "http://127.0.0.1:8000/api/jobcraft/interview-review", json=payload, timeout=300
    )
    print(f"status: {resp.status_code}")
    if resp.status_code != 200:
        print(resp.text)
        exit(1)

    result = resp.json()
    record_id = result.get("record_id")
    print(f"record_id: {record_id}, overall_score: {result.get('overall_score')}")
    print(f"summary: {result.get('summary', '')[:100]}...")
    print(f"questions count: {len(result.get('questions', []))}")
    print("\n2. 问题维度分布:")
    for q in result.get("questions", []):
        print(
            f"  - [{q.get('dimension')}] {q.get('question_text')[:40]}... | score={q.get('score')}, level={q.get('level')}"
        )
    print("\n3. strengths:", result.get("strengths", []))
    print("4. weaknesses:", result.get("weaknesses", []))
    print("5. action_items:", result.get("action_items", []))

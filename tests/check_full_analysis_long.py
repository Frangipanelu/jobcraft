import requests

with open("tests/long_user_sample.txt", "r", encoding="utf-8") as f:
    raw_text = f.read()

payload = {
    "user_id": 1,
    "company": "测试公司",
    "position": "项目专员",
    "round_type": "业务面",
    "job_analysis_id": None,
    "raw_text": raw_text,
}

url = "http://127.0.0.1:8000/api/jobcraft/interview-review"
print("Sending request...")
resp = requests.post(url, json=payload, timeout=300)
print(f"status: {resp.status_code}")
if resp.status_code == 200:
    data = resp.json()
    print(f"overall_score: {data.get('overall_score')}")
    print(f"questions count: {len(data.get('questions', []))}")
    for q in data.get("questions", []):
        print(
            f"  Q{q.get('sequence')} [{q.get('dimension')}] {q.get('question_text')[:40]!r} score={q.get('score')}"
        )
else:
    print(resp.text)

import requests

with open(
    r"d:\A-pythonProject\AI-learning\multi-agent\jobcraft\tests\long_user_sample.txt",
    "r",
    encoding="utf-8",
) as f:
    raw = f.read()

url = "http://127.0.0.1:8000/api/jobcraft/interview-review/parse-preview"
resp = requests.post(url, data={"raw_text": raw}, timeout=30)
print("status:", resp.status_code)
if resp.status_code == 200:
    data = resp.json()
    print("speaker_count:", data.get("speaker_count"))
    print("qa_pair_count:", data.get("qa_pair_count"))
    print(
        "qa_pairs keys:",
        list(data.get("qa_pairs", [{}])[0].keys()) if data.get("qa_pairs") else [],
    )
    for qa in data.get("qa_pairs", [])[:3]:
        print(f"  Q{qa['sequence']} [{qa['start_time']}] {qa['question_text'][:50]!r}")
        print(f"    A: {qa['my_answer'][:60]!r}")
else:
    print(resp.text)

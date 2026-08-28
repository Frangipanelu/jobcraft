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
    print("role_counts:", data.get("role_counts"))
    for d in data.get("dialogue", []):
        print(f"  {d['role']:12} {d['speaker']} {d['time']} {d['content'][:50]!r}")
else:
    print(resp.text)

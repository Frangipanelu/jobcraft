import requests

raw = """陆晶晶面试记录

讲话人1 - 0:22 
 那麻烦您做一个简单的自我介绍。面试官你好。 
 
 讲话人2 - 0:26 
 我是陆晶晶，毕业于广东技术师范大学... 
"""

url = "http://127.0.0.1:8000/api/jobcraft/interview-review/parse-preview"
resp = requests.post(url, data={"raw_text": raw}, timeout=30)
print("status:", resp.status_code)
if resp.status_code == 200:
    data = resp.json()
    print("speaker_count:", data.get("speaker_count"))
    print("role_counts:", data.get("role_counts"))
    for d in data.get("dialogue", []):
        print(f"  {d['role']:12} {d['speaker']} {d['time']} {d['content'][:40]!r}")
else:
    print(resp.text)

import requests

raw_text = """09:00 请你先做一个自我介绍。
09:01 我叫李明，毕业于某某大学计算机专业。
09:02 你们订单系统每天的量级大概是多少？
09:03 日均几百万单。"""

url = "http://127.0.0.1:8000/api/jobcraft/interview-review/parse-preview"
try:
    resp = requests.post(url, data={"raw_text": raw_text}, timeout=30)
    print("status:", resp.status_code)
    print(resp.json())
except Exception as e:
    print("error:", e)

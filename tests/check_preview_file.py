import requests

raw_text = """面试官 09:00 请你先做一个自我介绍。
我：我叫李明，毕业于某某大学计算机专业。
面试官 09:02 你们订单系统每天的量级大概是多少？
我：日均几百万单。"""

with open("_preview_test.txt", "w", encoding="utf-8") as f:
    f.write(raw_text)

url = "http://127.0.0.1:8000/api/jobcraft/interview-review/parse-preview"
try:
    with open("_preview_test.txt", "rb") as f:
        resp = requests.post(
            url, files={"file": ("preview_test.txt", f, "text/plain")}, timeout=30
        )
    print("status:", resp.status_code)
    print(resp.json())
except Exception as e:
    print("error:", e)

import requests

with open(
    r"d:\A-pythonProject\AI-learning\multi-agent\jobcraft\tests\long_user_sample.txt",
    "r",
    encoding="utf-8",
) as f:
    text = f.read()

# 1. 普通 UTF-8 文件
with open(
    r"d:\A-pythonProject\AI-learning\multi-agent\jobcraft\tests\user_sample_utf8.txt",
    "w",
    encoding="utf-8",
) as f:
    f.write(text)

# 2. 带 BOM 的 UTF-8 文件
with open(
    r"d:\A-pythonProject\AI-learning\multi-agent\jobcraft\tests\user_sample_bom.txt",
    "w",
    encoding="utf-8-sig",
) as f:
    f.write(text)

url = "http://127.0.0.1:8000/api/jobcraft/interview-review/parse-preview"

for name, path in [
    ("utf8", "tests/user_sample_utf8.txt"),
    ("bom", "tests/user_sample_bom.txt"),
]:
    with open(path, "rb") as f:
        resp = requests.post(url, files={"file": f}, timeout=30)
    print(f"--- {name} --- status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(
            f"speaker_count: {data.get('speaker_count')}, role_counts: {data.get('role_counts')}"
        )
    else:
        print(resp.text)

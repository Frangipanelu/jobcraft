# 测试基建：2026-07-31 检查与修复

## 问题发现

运行 `uv run pytest tests/ -q` 时收集阶段直接失败（4 errors），原因：

1. **调试脚本被 pytest 误收集**：多个 `test_*.py` 是手工调试脚本，模块顶层就发 HTTP 请求（`requests.post("http://127.0.0.1:8000/...")`），pytest 收集时 import 即执行 → `ConnectionError`。
2. **e2e 测试无服务器保护**：`test_jobcraft_e2e.py` 依赖后端在线，无服务器时 2 failed + 3 errors。
3. **真实 bug**：`_split_bullets()` 未过滤 `**背景**：xxx` 这类 markdown 加粗行，导致简历 HTML 里混入 `**xxx**` 噪声。
4. **SyntaxWarning**：`test_jobcraft_e2e.py` docstring 中 `\S` 触发 `invalid escape sequence`。

## 修复动作

### 1. 调试脚本重命名（避免 pytest 收集）

`test_*.py` → `check_*.py`（pytest 默认只收集 `test_*` / `*_test.py` 前缀）：

- test_file_preview → check_file_preview
- test_full_analysis_long → check_full_analysis_long
- test_preview_title → check_preview_title
- test_preview_user_sample → check_preview_user_sample
- test_preview_file → check_preview_file
- test_interview_review_parse_preview → check_interview_review_parse_preview
- test_interview_review_api → check_interview_review_api
- test_interview_review_api_long → check_interview_review_api_long

### 2. e2e 服务器保护

- `tests/conftest.py`：新增 session 级 `server_available` fixture，探测 `/health` `/` `/docs`，全部 ConnectionError 则返回 False。
- `tests/test_jobcraft_e2e.py`：新增 `server_ok` fixture，服务器离线时 `pytest.skip` 整模块；两个非 fixture 用例（`test_analyze_job_without_cards` / `test_interview_prep_without_job`）显式依赖 `server_ok`。
- 效果：无服务器时 e2e 明确 skip（5 skipped），不阻塞单元测试。

### 3. 修复 `_split_bullets`

`jobcraft_resume_gen.py`：
```python
if line.startswith("**") and line.endswith("**"):   # 旧：只过滤纯加粗行
if line.startswith("**"):                            # 新：过滤 **背景**：xxx 整行
```

### 4. 修复 SyntaxWarning

`test_jobcraft_e2e.py` docstring 去掉 `\.venv\Scripts\python.exe`（改为 `python`）。

## 新增单元测试（不依赖 LLM/DB/服务器）

| 文件 | 覆盖 |
|------|------|
| `tests/test_resume_gen_unit.py` (10) | `_split_bullets` / `_card_header` / `_personal_info_lines` / Markdown / HTML（A4 打印样式、个人信息注入、header+bullets、XSS 转义、空卡占位） |
| `tests/test_jobcraft_analyze_unit.py` (10) | `_normalize` / `_match_term_to_blob` / `_ats_to_jdreq` / `_build_gap_text` / `_match_level` / `compute_match` |
| `tests/test_misc_unit.py` (9) | `_get_card_text`（版本/结构化/回退优先级）/ `_extract_json` / `_truncate_text` |
| `tests/test_qa_pairs_unit.py` (5) | 原有面试对话解析 |

## 验证结果

```powershell
uv run pytest tests/ -q -m "not slow"
# 39 passed, 5 skipped, 6 deselected   (服务器离线时)
# 服务器在线 + --runslow 时 e2e 全量可跑
```

- ruff check / format ✅
- 修复前后对比：收集 4 errors → 0；单元测试 5 → 39。

## 注意事项

- `check_*.py` 是调试脚本，需要手动运行（如 `uv run python tests/check_preview_api.py`），不会被 pytest 收集。
- 启动后端后再跑 e2e：`uv run pytest tests/test_jobcraft_e2e.py -v --runslow`。

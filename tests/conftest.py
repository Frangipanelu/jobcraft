import os

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--runslow", action="store_true", default=False, help="run slow tests"
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--runslow"):
        return
    skip_slow = pytest.mark.skip(reason="need --runslow option to run")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip_slow)


@pytest.fixture(scope="session")
def server_available() -> bool:
    """检测后端服务是否在线，不可用时跳过 e2e 测试（不阻塞单元测试）"""
    import requests

    base = os.environ.get("JOBCRAFT_TEST_BASE_URL", "http://localhost:8000")
    for path in ("/health", "/", "/docs"):
        try:
            resp = requests.get(f"{base}{path}", timeout=3)
            if resp.status_code < 500:
                return True
        except requests.ConnectionError:
            continue
    return False

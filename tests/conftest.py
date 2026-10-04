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


@pytest.fixture(autouse=True)
def _reset_schema_bootstrap_state():
    """每个测试前后重置运行时 DDL 引导标志，隔离 db_conn 全局状态。"""
    from app.tools import db_conn

    db_conn.reset_schema_ready()
    yield
    db_conn.reset_schema_ready()


@pytest.fixture(autouse=True)
def _block_external_network(request):
    """TEST-ISOLATION-01：单测禁止真实外部网络调用。

    出站 TCP（socket.connect / connect_ex）仅放行回环地址，非回环一律
    RuntimeError 快速失败——把「未 mock 的真实调用」变成确定性失败而非
    429 偶发。slow 标记（--runslow 真 e2e）豁免；AF_UNIX 等非 IP 地址放行。
    """
    if "slow" in request.node.keywords:
        yield
        return

    import socket

    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex

    def _host_of(address):
        if isinstance(address, tuple) and address:
            return address[0]
        return None

    def _blocked(address):
        host = _host_of(address)
        if host is None or host in ("127.0.0.1", "localhost", "::1"):
            return False
        raise RuntimeError(
            f"TEST-ISOLATION-01: 单测禁止真实外部调用（出站 {address!r}）。"
            "请 mock 该依赖；确需真实网络的用例标 @pytest.mark.slow "
            "并以 --runslow 运行。"
        )

    def guarded_connect(sock, address):
        _blocked(address)
        return original_connect(sock, address)

    def guarded_connect_ex(sock, address):
        _blocked(address)
        return original_connect_ex(sock, address)

    socket.socket.connect = guarded_connect
    socket.socket.connect_ex = guarded_connect_ex
    yield
    socket.socket.connect = original_connect
    socket.socket.connect_ex = original_connect_ex

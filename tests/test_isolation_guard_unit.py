"""TEST-ISOLATION-01：conftest 出站网络守卫回归验证。

守卫（tests/conftest.py `_block_external_network`）把未 mock 的真实外部
调用变成确定性 RuntimeError，而非 429 偶发失败。
"""

import socket

import pytest


def test_external_connect_blocked():
    with pytest.raises(RuntimeError, match="TEST-ISOLATION-01"):
        socket.create_connection(("203.0.113.1", 443), timeout=1)


def test_external_connect_ex_blocked():
    sock = socket.socket()
    try:
        with pytest.raises(RuntimeError, match="TEST-ISOLATION-01"):
            sock.connect_ex(("203.0.113.1", 80))
    finally:
        sock.close()


def test_loopback_connect_allowed():
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]
    try:
        client = socket.create_connection(("127.0.0.1", port), timeout=2)
        client.close()
    finally:
        server.close()


def test_closed_loopback_port_reports_protocol_error_not_guard():
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()

    sock = socket.socket()
    sock.settimeout(1)
    try:
        with pytest.raises(OSError):
            sock.connect(("127.0.0.1", port))
    finally:
        sock.close()

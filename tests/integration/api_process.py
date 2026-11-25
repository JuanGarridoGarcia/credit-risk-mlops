"""The API served by a process of its own, as in compose, for the tests that need a real
server: the load test (T18.13) and the simulated investor of the clock story (T21).

A test must not share an interpreter (and its lock) with the server it calls (E-045).
"""

import os
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager

import httpx

from tests.api_support import ADMIN_KEY, PREDICT_KEY


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@contextmanager
def api_process(dbname: str, prefix: str, *, ready: bool = True, **env: str) -> Iterator[str]:
    """Serve the API on a free port; yield its URL once it runs (and, if ``ready``, once
    it has its champions and its database)."""
    port = free_port()
    server = subprocess.Popen(
        [sys.executable, "-m", "credit_risk.api", "--port", str(port)],
        env={
            **os.environ,
            "POSTGRES_DB": dbname,
            "API_MODEL_PREFIX": prefix,
            "API_KEYS_PREDICT": f"replayer:{PREDICT_KEY}",
            "API_KEYS_ADMIN": f"flow:{ADMIN_KEY}",
            **env,
        },
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    url = f"http://127.0.0.1:{port}"
    try:
        with httpx.Client(base_url=url, trust_env=False, timeout=5) as http:
            deadline = time.monotonic() + 60
            path = "/health" if ready else "/health/live"
            while True:
                assert server.poll() is None, server.stderr.read() if server.stderr else ""
                assert time.monotonic() < deadline, f"the API did not answer {path}"
                try:
                    if http.get(path).status_code == 200:
                        break
                except httpx.TransportError:
                    pass
                time.sleep(0.2)
        yield url
    finally:
        server.terminate()
        server.wait(timeout=10)
        if server.stderr is not None:
            server.stderr.close()

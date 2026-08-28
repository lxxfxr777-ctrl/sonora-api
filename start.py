from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from urllib.request import urlopen

BGUTIL_PORT = 4416
WORKER_PORT = 8787
PUBLIC_PORT = int(os.environ.get("PORT", "10000"))


def wait_http(url: str, timeout: int = 30) -> None:
    deadline = time.time() + timeout
    last_error = None
    while time.time() < deadline:
        try:
            with urlopen(url, timeout=2) as response:
                if 200 <= response.status < 500:
                    return
        except Exception as exc:
            last_error = exc
        time.sleep(1)
    raise RuntimeError(f"Service did not become ready: {url} ({last_error})")


def main() -> None:
    processes: list[subprocess.Popen] = []

    def cleanup(*_args) -> None:
        for process in reversed(processes):
            if process.poll() is None:
                try:
                    process.terminate()
                except Exception:
                    pass
        for process in reversed(processes):
            try:
                process.wait(timeout=5)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass

    signal.signal(signal.SIGTERM, cleanup)
    signal.signal(signal.SIGINT, cleanup)

    print("=== SONORA: starting bgutil ===", flush=True)
    bgutil = subprocess.Popen([
        "node", "/opt/bgutil/server/build/main.js", "--port", str(BGUTIL_PORT)
    ])
    processes.append(bgutil)
    wait_http(f"http://127.0.0.1:{BGUTIL_PORT}/ping")
    print(f"[OK] bgutil on 127.0.0.1:{BGUTIL_PORT}", flush=True)

    print("=== SONORA: starting local worker + Invidious fallback ===", flush=True)
    worker = subprocess.Popen([
        sys.executable, "worker_boot.py"
    ])
    processes.append(worker)
    wait_http(f"http://127.0.0.1:{WORKER_PORT}/health")
    print(f"[OK] worker on 127.0.0.1:{WORKER_PORT}", flush=True)

    print("=== SONORA: starting public API ===", flush=True)
    try:
        os.execv(sys.executable, [
            sys.executable, "-m", "uvicorn", "main:app",
            "--host", "0.0.0.0", "--port", str(PUBLIC_PORT)
        ])
    finally:
        cleanup()


if __name__ == "__main__":
    main()
